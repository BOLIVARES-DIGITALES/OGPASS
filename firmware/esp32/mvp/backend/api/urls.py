from django.urls import path
from core.views import health
from core.realtime import events, staff_events
from . import views as v

urlpatterns = [
    path('me/', v.me), path('wallet/', v.wallet), path('devices/', v.devices),
    path('devices/register/', v.register), path('devices/heartbeat/', v.heartbeat),
    path('devices/<uuid:device_id>/disable/', v.disable), path('readers/', v.devices),
    path('credentials/', v.credentials), path('credentials/scan/', v.scan),
    path('credentials/assign/', v.assign), path('events/', events),
    path('events/staff/', staff_events), path('events/recent/', v.recent_events),
    path('health/', health),
]
