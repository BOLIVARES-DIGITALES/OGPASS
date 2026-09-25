"""Committed wallet events + one PostgreSQL LISTEN connection per ASGI worker."""
import asyncio
import json
import logging
import time
from collections import defaultdict
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db import connection, transaction
from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET
from .models import Wallet, WalletEvent

logger = logging.getLogger(__name__)
CHANNEL = 'ogpass_wallet_events'


@transaction.atomic
def emit_event(wallet_id, kind):
    event = WalletEvent.objects.create(wallet_id=wallet_id,kind=kind)
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_notify(%s, %s)',[CHANNEL,str(wallet_id)])
    return event


def latest(wallet_id):
    events = WalletEvent.objects.filter(wallet_id=wallet_id) if wallet_id else WalletEvent.objects.all()
    return events.order_by('-id').values_list('id',flat=True).first() or 0


def frame(version):
    # Every connection sends a refresh, even if its Last-Event-ID is ahead or lost.
    return f'id: {version}\nevent: wallet\ndata: '+json.dumps({'version':version})+'\n\n'


class EventHub:
    def __init__(self):
        self.listeners = defaultdict(set)
        self.task = None

    def notify(self, wallet_id=None):
        groups = [self.listeners.get(wallet_id,()), self.listeners.get(0,())] if wallet_id is not None else list(self.listeners.values())
        for group in groups:
            for queue in list(group):
                if queue.empty(): queue.put_nowait(True)

    async def listen(self):
        import psycopg
        db = settings.DATABASES['default']
        while self.listeners:
            try:
                async with await psycopg.AsyncConnection.connect(host=db['HOST'],dbname=db['NAME'],user=db['USER'],password=db['PASSWORD'],port=db.get('PORT') or 5432,autocommit=True,connect_timeout=5) as conn:
                    await conn.execute('LISTEN '+CHANNEL)
                    self.notify()  # Close the race between subscribing and LISTEN becoming ready.
                    while self.listeners:
                        async for notification in conn.notifies(timeout=10,stop_after=100):
                            if notification.payload.isdigit(): self.notify(int(notification.payload))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning('Wallet notification listener disconnected; reconnecting')
                self.notify()
                await asyncio.sleep(2)

    def subscribe(self, wallet_id):
        queue = asyncio.Queue(maxsize=1)
        self.listeners[wallet_id].add(queue)
        if self.task is None or self.task.done(): self.task = asyncio.create_task(self.listen())
        return queue

    def unsubscribe(self, wallet_id, queue):
        self.listeners[wallet_id].discard(queue)
        if not self.listeners[wallet_id]: del self.listeners[wallet_id]


hub = EventHub()


async def async_stream(wallet_id):
    postgres = settings.DATABASES['default']['ENGINE'].endswith('postgresql')
    queue = hub.subscribe(wallet_id) if postgres else None
    deadline = time.monotonic()+30  # Reauthenticate periodically, including after logout/revocation.
    try:
        version = await sync_to_async(latest)(wallet_id)
        yield 'retry: 1000\n\n'+frame(version)
        while time.monotonic()<deadline:
            notified = False
            if queue:
                try:
                    await asyncio.wait_for(queue.get(),timeout=min(10,max(.1,deadline-time.monotonic())))
                    notified = True
                except asyncio.TimeoutError: pass
            else:
                await asyncio.sleep(.5)  # Development SQLite only; production uses NOTIFY.
            new_version = await sync_to_async(latest)(wallet_id)
            if notified or new_version != version:
                version = new_version
                yield frame(version)
            else: yield ': heartbeat\n\n'
    finally:
        if queue: hub.unsubscribe(wallet_id,queue)


def sync_stream(wallet_id):
    # Compatibility with Django's test server. Production uses ASGI.
    version = latest(wallet_id)
    yield 'retry: 1000\n\n'+frame(version)
    deadline = time.monotonic()+15
    while time.monotonic()<deadline:
        time.sleep(.5)
        new_version = latest(wallet_id)
        if new_version != version:
            version = new_version
            yield frame(version)
        else: yield ': heartbeat\n\n'


@login_required
@require_GET
def events(request):
    wallet,_ = Wallet.objects.get_or_create(user=request.user)
    stream = async_stream(wallet.pk) if hasattr(request,'scope') else sync_stream(wallet.pk)
    return StreamingHttpResponse(stream,content_type='text/event-stream',headers={'Cache-Control':'no-store, no-transform','X-Accel-Buffering':'no'})


@staff_member_required
@require_GET
def staff_events(request):
    stream = async_stream(0) if hasattr(request,'scope') else sync_stream(0)
    return StreamingHttpResponse(stream,content_type='text/event-stream',headers={'Cache-Control':'no-store, no-transform','X-Accel-Buffering':'no'})
