# Driver contract

Implement `core/OgpassReader.h`, declare only implemented capabilities, register
the driver in `src/main.cpp`, and add native and bench tests. Driver code must
not import Django concepts, identity, ledger, Wi-Fi or backend pricing.

| Driver | Role | Enabled operations |
|---|---|---|
| Rc522Reader | PRIMARY | IDENTIFY, READ (UID/SAK/ATQA), HEALTH |
| Pn532Diagnostic | OPTIONAL | HEALTH (I2C ACK only) |
| BleBeacon | RADIO, lab build only | BEACON, HEALTH (stack state) |

WRITE/AUTH/EMULATE/NDEF/APDU/PROXIMITY are vocabulary, not claimed support.
`write()` and `emulate()` return UNSUPPORTED. Do not enable a datasheet capability
until the driver, permissions and physical validation implement it.

Optional begin/probe/poll runs on a separate FreeRTOS task on core 0. The primary
loop only polls RC522 and consumes optional events already present in a queue.
Network TLS requests run on another task. No wait/join on the optional task occurs
in setup or loop. PN532 probe has a 40 ms Wire timeout and is retried only by an
explicit I2CSCAN command. This software isolation does not protect against shared
power faults, electrical shorts or a system-wide memory corruption/watchdog fault.

Networking requires the private config header and never uses insecure TLS. One
in-flight event is stored in NVS before transmission and removed only after its
matching acknowledgment; queued RAM-only detections can be lost on power failure.
They are observations, never offline payment approvals. Rejected events remain
pending for operator investigation, rather than being silently discarded.
