"""Pure protocol boundary. No wallet, network, or reader implementation imports."""
import hashlib
import re
import uuid

CAPABILITIES = frozenset('IDENTIFY READ WRITE AUTH EMULATE NDEF APDU BEACON PROXIMITY HEALTH'.split())
# Implemented OGPASS operations, not everything advertised by a chip datasheet.
DRIVERS = {'rc522': ['IDENTIFY', 'READ', 'HEALTH'], 'pn532': ['HEALTH'],
           'ble': ['BEACON', 'HEALTH']}


def normalize(payload):
    if not isinstance(payload, dict):
        raise ValueError('An event must be an object')
    if set(payload) - {'event_id', 'request_id', 'device_id', 'reader', 'technology', 'protocol', 'uid', 'purpose', 'timestamp', 'metadata', 'capabilities'}:
        raise ValueError('Unsupported event fields')
    technology = str(payload.get('technology', '')).upper()
    protocol = str(payload.get('protocol', '')).upper()
    source = str(payload.get('reader', '')).lower()
    if source not in DRIVERS:
        raise ValueError('Unknown driver')
    if 'capabilities' in payload and payload['capabilities'] != DRIVERS[source]:
        raise ValueError('Capabilities do not match implemented driver')
    metadata = payload.get('metadata', {})
    if not isinstance(metadata, dict) or set(metadata) - {'sak', 'atqa', 'type', 'latency_ms', 'rssi'}:
        raise ValueError('Unsupported metadata')
    for key, value in metadata.items():
        if key == 'type':
            valid = isinstance(value, str) and len(value) <= 80
        else:
            low, high = {'sak': (0, 255), 'atqa': (0, 65535), 'latency_ms': (0, 60000), 'rssi': (-127, 20)}[key]
            valid = type(value) is int and low <= value <= high
        if not valid:
            raise ValueError('Invalid metadata value')
    uid = str(payload.get('uid', '')).upper().replace(':', '').replace(' ', '')
    known = technology == 'NFC' and protocol == 'ISO14443A' and source == 'rc522'
    if known:
        if not re.fullmatch(r'(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})', uid):
            raise ValueError('Invalid ISO14443A UID')
    elif technology == 'BLE' and protocol == 'IBEACON' and source == 'ble':
        # Reserved for lab adapters. A beacon identifier proves no ownership.
        uid = str(uuid.UUID(str(payload.get('uid', ''))))
    elif not uid or len(uid) > 100:
        raise ValueError('Invalid identifier')
    if not technology or len(technology) > 24 or not protocol or len(protocol) > 32:
        raise ValueError('Invalid technology or protocol')
    return {'technology': technology, 'protocol': protocol, 'source': source, 'uid': uid,
            'metadata': metadata, 'capabilities': DRIVERS[source],
            'identifier_hash': hashlib.sha256(f'{technology}:{protocol}:{uid}'.encode()).hexdigest(),
            'recognized': known}
