# Protocol adapters

`backend/apps/credentials/normalizer.py` is the server protocol boundary; drivers
emit `Detection` and the transport encodes `schemas/hardware-event.v1.json`.
The server assigns device identity from the authenticated reader, never from UID.

Active: RC522, ISO14443A, 4/7/10-byte UID identification. `READ` means identifier
and selection metadata only; no card memory access, Crypto1 authorization,
NDEF decoding, APDU session, writing or cloning is enabled.

PN532: I2C diagnostic only, with `HEALTH`. An ACK is not proof of a PN532 firmware
version or usable NFC protocol. BLE iBeacon: separate lab build with `BEACON` and
`HEALTH`; proximity reception/calibration has not been implemented or verified.

Future ISO14443B/4, ISO15693, NFC Forum types, DESFire, FeliCa, LF 125/134 kHz,
QR and UWB require a compatible driver and protocol tests. An undetected signal
cannot be reported as a technology that this hardware cannot observe. A reported
but unsupported protocol becomes `UNKNOWN_TECHNOLOGY`, without wallet association.
