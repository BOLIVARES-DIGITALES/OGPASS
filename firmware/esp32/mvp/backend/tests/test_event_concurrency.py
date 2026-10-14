import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connection, connections
from django.test import TransactionTestCase
from core.models import Reader, CardScan, Operation
from backend.apps.devices.services import record_hardware_event, device_for
from backend.apps.devices.models import HardwareEvent


class EventConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL row locks')
        self.reader = Reader.objects.create(name='parallel-event', token_hash=hashlib.sha256(b'fixture').hexdigest(), amount=1000, cost=700)
        device_for(self.reader)

    def payload(self):
        return {'event_id': str(uuid.uuid4()), 'reader':'rc522', 'technology':'NFC', 'protocol':'ISO14443A', 'uid':'11223344'}

    def parallel(self, payloads):
        barrier = Barrier(2)
        def worker(payload):
            try:
                reader = Reader.objects.get(pk=self.reader.pk)
                barrier.wait(timeout=10)
                return record_hardware_event(reader, payload)[1]
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(worker, payloads))

    def test_parallel_duplicate_creates_one_scan_and_event(self):
        payload = self.payload()
        self.assertEqual(sorted(self.parallel([payload, payload])), [False, True])
        self.assertEqual(HardwareEvent.objects.count(), 1)
        self.assertEqual(CardScan.objects.count(), 1)
        self.assertEqual(Operation.objects.count(), 0)

    def test_parallel_distinct_events_preserve_both_observations(self):
        self.assertEqual(self.parallel([self.payload(), self.payload()]), [True, True])
        self.assertEqual(HardwareEvent.objects.count(), 2)
        self.assertEqual(CardScan.objects.count(), 2)
        self.assertEqual(Operation.objects.count(), 0)
