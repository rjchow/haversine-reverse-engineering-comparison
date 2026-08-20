# Telesto protocol: phone-side reverse-engineering

## Scope and confidence

This document describes the **complete Telesto implementation visible in the Haversine phone libraries**: BLE endpoints, wire structures, request/response sequencing, controller state, cancellation, collection transfer, virtual-address map, exposed payload structures, and Haversine operations.

It does **not** claim that the ring-firmware implementation has been completely recovered. The supplied Haversine KLIBs and native archives contain the phone-side client and C/Swift bridge, not the symbolized firmware handler for each address. Consequently, the wire protocol and client-side behavior are known, while some firmware-side meanings of `info`, destructive operations, sensor payloads, and image programming remain unknown.

Primary evidence:

- `work-hsl-meta.txt`: cinterop layouts, public constants, and operation APIs.
- `transfer-dwarf.txt`: C DWARF type/field/enum information.
- `telestoctrl-disasm.txt`: TelestoController state and framing.
- `telestoop-disasm.txt`: request construction and program-data ownership.
- `linkctrl-disasm.txt`: HaversineLinkController queue/connection state machine.
- `transferop-c-disasm.txt`, `transfer-dwarf.txt`: collection-transfer compound operation.
- `work-hsl/CBConnectedPeripheralAdaptor.o`: CoreBluetooth characteristic roles and write modes.

The target is little-endian ARM64. All multi-byte wire fields below are little-endian unless explicitly stated otherwise.

## 1. What Telesto is

Telesto is the Index firmware's command/data service as used by Haversine. It exposes a virtual address space and operations analogous to read, erase, and program memory. It is not:

- the Bluetooth Link Layer;
- a BLE encryption scheme;
- the recording codec;
- the collection TLV format.

The recording path is:

```text
BLE ATT/GATT
  -> Telesto Ctrl/Data streams
  -> TelestoController
  -> TelestoOperation
  -> Index virtual address
  -> raw collection bytes
  -> PPCollection parser
  -> DDRice or uncompressed audio decoder
```

Telesto also supplies the Haversine client with platform versions, serial numbers, application data, diagnostics, sensor data, firmware-image regions, and system-input writes.

## 2. BLE service and characteristics

| Role | UUID | Direction/use |
| --- | --- | --- |
| Telesto/Haversine service | `607B5C9B-3700-4E94-F44A-2DF900BCB0C3` | service discovery |
| Telesto Data | `DAAD3D52-237C-90A7-B54B-8854A134D801` | Telesto data writes and notifications |
| Telesto Ctrl | `C0EF558A-2058-FABF-A140-8D5ACDE50B39` | 13-byte request writes and 12-byte response notifications |
| System Input | `1D1F4039-23F5-33B2-C24E-704351F20585` | fixed 7-byte system-input writes |

The mapping is supported by `CBConnectedPeripheralAdaptor.o` send paths and the three callbacks in `HaversineLinkTransportDelegateTable` (`work-hsl-meta.txt:1572-1627`). The open iOS pairing helper also confirms that a write of `00` with response to `DAAD...` is used to establish/trigger pairing (`external-mobileapp/libindex/src/iosMain/kotlin/coredevices/libindex/device/IndexPairing.ios.kt:15-39`).

### BLE write behavior

The logical Telesto controller gives the transport one complete Ctrl or Data buffer. The Apple adaptor then fragments it using `maximumWriteValueLengthForType(.withoutResponse)` and queues each fragment with CoreBluetooth write-without-response. The adaptor invokes `telestoCtrlBytesSent`/`telestoDataBytesSent` after the writes are handed to CoreBluetooth. These callbacks are **local handoff confirmations**, not ring acknowledgements.

System Input is sent with CoreBluetooth write-with-response. Its sent callback is still a local completion callback; a later CoreBluetooth write error becomes a transport error.

BLE ATT packet boundaries are not Telesto boundaries. A 13-byte request, 12-byte response, or data payload may be split across notifications/writes.

## 3. Wire structures

### 3.1 `TelestoRequest`: 13 bytes

```c
// packed; offsets are wire offsets
struct TelestoRequest {
    uint8_t  type;       // +0
    uint32_t address;    // +1
    uint32_t offset;     // +5
    uint32_t length;     // +9
};                         // sizeof = 13
```

`TelestoRequest` is packed/aligned to one byte in cinterop metadata (`work-hsl-meta.txt:1813-1867`). `TelestoOperation` serializes the fields byte-by-byte in `telestoop-disasm.txt:39-198`.

Operation type values:

| Value | Name | Data stream |
| ---: | --- | --- |
| `0` | `TELESTO_NO_OPERATION` | invalid/idle |
| `1` | `TELESTO_ERASE_MEMORY` | no outbound data in reviewed client |
| `2` | `TELESTO_PROGRAM_MEMORY` | `length` bytes on Telesto Data |
| `3` | `TELESTO_READ_MEMORY` | returned bytes on Telesto Data |
| `4` | `TELESTO_CANCEL_OPERATION` | cancel request; no new data |
| `5` | `TELESTO_ERASE_AND_PROGRAM_MEMORY` | `length` bytes on Telesto Data |

`TELESTO_LENGTH_INFER_FROM_PREFIX = 0` and `TELESTO_LENGTH_INDEFINITE = 0xffffffff`. For collection reads, Haversine uses length zero so firmware infers the returned length from the collection prefix.

### 3.2 `TelestoResponse`: 12 bytes

```c
// packed; offsets are wire offsets
struct TelestoResponse {
    uint32_t error;      // +0
    uint32_t info;       // +4
    uint32_t length;     // +8
};                         // sizeof = 12
```

The cinterop layout is explicit at `work-hsl-meta.txt:2117-2163`. `TelestoController_receiveCtrlBytes` accumulates exactly 12 bytes before treating the header as complete (`telestoctrl-disasm.txt:361-408`).

- `error` is the firmware operation result.
- `length` controls the expected Data stream size for a READ.
- `info` is retained in the response structure but is not interpreted by the reviewed controller. Its firmware-side meaning is unknown.

A successful response has `error = 0`. On a cancelled request, the phone controller maps a successful cancel response to local error 65 (`TELESTO_ERROR_CANCELLED_BY_REQUEST`); a nonzero firmware error is preserved.

### 3.3 `TelestoInputParameters`: phone-side only

```c
struct TelestoInputParameters {
    TelestoRequest request; // +0, 13 bytes
    // padding for pointer alignment
    uint8_t *dataToSend;    // +16
};                           // sizeof = 24, align = 8
```

This is not sent as one wire structure. `request` becomes the Ctrl frame; `dataToSend`, when present, becomes the Data stream after the Ctrl frame has been handed to the transport. `TelestoOperation` deep-copies `dataToSend` only for operation types PROGRAM and ERASE_AND_PROGRAM.

### 3.4 `TelestoLengthPrefixedData`

```c
struct TelestoLengthPrefixedData {
    uint32_t length; // +0
    uint8_t bytes[]; // +4
};
```

The cinterop minimum size is four bytes (`work-hsl-meta.txt:2166-2208`). This is a generic Telesto payload helper. It must not be confused with the separate PPCollection 3-byte collection prefix or audio-record lengths.

### 3.5 System Input: fixed 7 bytes

System Input is a separate fixed-size write, not a TelestoRequest:

```c
struct HaversineSystemInput {
    uint8_t type;                         // +0
    struct SystemInputInterruptParameters interrupt; // +1, 6 bytes
};                                         // sizeof = 7
```

`SystemInputInterruptParameters` is six bytes:

| Offset | Bits/size | Field |
| ---: | --- | --- |
| 0 | 1 bit each | `sleepChange`, `sleepState`, `largeImpact`, `fifoWatermark`, `inCollectionOrientationUpdate`, `inCollectionOrientation`, `offClubUpdate`, `motionFSMUpdate` |
| 1 | 1 bit | `motionFSMValue` |
| 1 | 1 bit | `smallImpact` |
| 1 | 6 bits | reserved |
| 2 | 2 bytes | `collectionSignal.updates`, `collectionSignal.values` |
| 4 | 1 byte | `calibrationAccelOctant` |
| 5 | 1 byte | `reserved2` |

The fields and offsets are exposed in `work-hsl-meta.txt:1880-2110`. System Input type values are:

| Value | Name |
| ---: | --- |
| 0 | `INPUT_BASE` |
| 1 | `INPUT_INTERRUPT` |
| 2 | `INPUT_RESERVED` |
| 3 | `INPUT_PHOTODIODE_LIGHT` |
| 4 | `INPUT_PHOTODIODE_DARK` |
| 5 | `INPUT_APPLICATION_DATA_UPDATED` |
| 6 | `INPUT_SENSOR_CONFIG_UPDATED` |
| 7 | `INPUT_ENTER_STREAMING_STATE` |
| 8 | `INPUT_EXIT_STREAMING_STATE` |
| 9 | `INPUT_PRIMARY_DISCONNECTED` |
| 10 | `INPUT_UPDATE_ADVERTISING` |
| 11 | `INPUT_FORCE_COLLECTION_WRITE` |
| 12 | `INPUT_PANIC` |
| 13 | `INPUT_CALIBRATION_COMPLETE` |
| 14 | `INPUT_DEBUG_INFO_UPDATED` |
| 15 | `INPUT_ENTER_DARK_STATE` |
| 16 | `INPUT_MAX` |

The exact firmware behavior triggered by each type is not fully recoverable from phone-side code; destructive/firmware-state-changing types should not be sent by a recording client.

## 4. TelestoController state machine

### 4.1 Queue and outboxes

Haversine maintains one FIFO Telesto operation queue and two outboxes:

```text
Ctrl outbox: 13-byte request
Data outbox: optional PROGRAM/ERASE_AND_PROGRAM payload
```

At most one Telesto operation is outstanding. The controller serializes Ctrl before Data:

```pseudo
startNext():
    require no outstanding request
    reset responseBytes and receivedDataBytes
    queue request bytes in Ctrl outbox
    if type is PROGRAM or ERASE_AND_PROGRAM:
        queue request.length payload bytes in Data outbox
    processOutbox()

processOutbox():
    if Ctrl pending or Data pending:
        return
    if Ctrl has bytes:
        mark Ctrl pending
        outstandingType = request.type
        sendTelestoCtrlBytes(full13Bytes)
        return
    if Data has bytes:
        mark Data pending
        sendTelestoDataBytes(fullPayload)
```

The controller does not assign transaction IDs. Response correlation is solely through the one `outstandingRequestType`.

`*BytesSent` clears the corresponding local pending flag and permits the next outbox to be processed. It does not parse or acknowledge a ring response.

### 4.2 Receiving the Ctrl response

The Ctrl notification stream contains the 12-byte `TelestoResponse`. The header can arrive in multiple notifications. The reviewed controller rejects an input call that would cross the remaining 12-byte header capacity rather than partially consuming it.

```pseudo
receiveCtrl(chunk):
    if closed: ignore
    if outstandingType == NONE:
        controllerError(UNEXPECTED_CTRL_INPUT)
    if chunk.size > 12 - responseBytes:
        controllerError(UNEXPECTED_CTRL_INPUT)
    append response header
    responseBytes += chunk.size
    completeIfPossible()
```

### 4.3 Receiving Data

Data is legal for READ, or for a CANCEL whose cancelled operation was READ.

For a READ, Haversine forwards data to the current operation callback rather than retaining the complete payload in TelestoController. The collection-transfer compound operation performs its own buffering.

```pseudo
receiveData(chunk):
    if closed: ignore
    if outstandingType not in {READ, CANCEL}:
        controllerError(UNEXPECTED_DATA_INPUT)
    if outstandingType == CANCEL and cancelledType != READ:
        controllerError(UNEXPECTED_DATA_INPUT)

    if responseBytes == 12:
        accepted = min(chunk.size,
                       response.length - receivedDataBytes)
        excess bytes are ignored
    else:
        accepted = chunk.size       // length not known yet

    if not cancelling-a-read:
        operation.receiveData(chunk[0:accepted])
    receivedDataBytes += accepted
    completeIfPossible()
```

Thus a compliant independent client should not assume the 12-byte header arrives before data unless live firmware testing establishes that ordering. It should buffer and validate the final count.

### 4.4 Completion gate

A Telesto operation completes only when:

- the full 12-byte response header has arrived;
- Ctrl/Data local handoff confirmation is complete;
- for READ, at least `response.length` Data bytes have arrived.

Extra Data bytes after the declared length are ignored by the phone controller. A robust independent client should reject or log them rather than silently treating them as a second response.

The next queued operation can be started before the previous operation's external completion callback is invoked. This is a phone-side reentrancy detail.

### 4.5 Cancellation

For a queued operation, Haversine removes it and completes it locally with error 65.

For the current operation:

- unsent PROGRAM data is dropped;
- data already handed to CoreBluetooth cannot be recalled;
- if the original Ctrl frame is pending, cancellation waits for its local sent callback;
- the cancel frame reuses the original request's address, offset, and length and changes only byte 0 to `4`.

```pseudo
cancelRequest = originalRequest
cancelRequest.type = TELESTO_CANCEL_OPERATION
```

During cancellation of a READ, incoming data is drained/discarded. A successful cancel response is reported locally as `TELESTO_ERROR_CANCELLED_BY_REQUEST` (65).

### 4.6 Controller errors

| Code | Name |
| ---: | --- |
| 1 | `TELESTO_CONTROLLER_ERROR_UNEXPECTED_CTRL_INPUT` |
| 2 | `TELESTO_CONTROLLER_ERROR_UNEXPECTED_DATA_INPUT` |
| 3 | `TELESTO_CONTROLLER_ERROR_UNEXPECTED_CTRL_OUTPUT` |
| 4 | `TELESTO_CONTROLLER_ERROR_UNEXPECTED_DATA_OUTPUT` |

The controller turns these into a Haversine error and expects its owner to close the controller. Closing with an error fails the queued operations.

## 5. HaversineLinkController connection/scheduling layer

TelestoController is wrapped by `HaversineLinkController`, which owns the BLE connection and one current top-level operation.

States:

| Value | State |
| ---: | --- |
| 0 | `DISCONNECTED` |
| 1 | `CONNECTING` |
| 2 | `CONNECTED` |
| 3 | `DISCONNECTING` |

Events are serialized through an internal event loop:

```text
CONNECTION_ESTABLISHED
CONNECTION_TERMINATED
ADD_OPERATION
COMMIT_OPERATIONS
CANCEL_OPERATION
OPERATION_COMPLETED
TIME_UPDATE
TRANSPORT_ERROR
```

Operations are added to an uncommitted FIFO queue and moved to the committed queue by COMMIT. Priority chooses connection priority; it does not reorder execution. When committed work exists while disconnected, the link enters CONNECTING. When the committed queue is empty after an operation, it disconnects instead of retaining an idle link.

On connection establishment it creates TelestoController and SystemInputController. On unexpected termination it fails current/committed work with connection failure and closes controllers. A connecting watchdog reports timeout after 16 seconds based on `TIME_UPDATE` events.

This layer is not an additional wire frame. It is Haversine's local scheduler and lifecycle implementation.

## 6. Error namespaces

### Telesto operation errors

These are values carried in `TelestoResponse.error` or synthesized locally:

| Value | Name |
| ---: | --- |
| 0 | `TELESTO_ERROR_NONE` |
| 64 | `TELESTO_BASE` |
| 65 | `TELESTO_ERROR_CANCELLED_BY_REQUEST` |
| 66 | `TELESTO_ERROR_CANCELLED_BY_WRITE` |
| 67 | `TELESTO_ERROR_BAD_REQUEST` |

### Transport errors

These are phone/OS/link errors, not Telesto response values:

| Value | Name |
| ---: | --- |
| 1 | Bluetooth unavailable |
| 2 | connection failure |
| 3 | service discovery failure |
| 4 | characteristic discovery failure |
| 5 | characteristic subscription failure |
| 6 | characteristic write failure |
| 7 | characteristic update failure |
| 8 | timeout |
| 9 | unexpected disconnection |
| 10 | internal inconsistency |
| 11 | scanning failure |
| 12 | connection limit reached |
| 13 | simultaneous connection requests not allowed |
| 14 | connection in use |

### Controller errors

See section 4.6. Application errors are a separate Haversine mapping layer.

## 7. Virtual address map

The following values are public `TelestoVirtualAddress` constants from `work-hsl-meta.txt:4766-5015` and `transfer-dwarf.txt:282-454`.

### 7.1 Single-sector/application region

| Name | Address |
| --- | ---: |
| `TELESTO_VIRTUAL_ADDRESS_BASE` | `0x40000000` |
| `TELESTO_SINGLE_SECTOR_START` | `0x40000000` |
| `TELESTO_APPLICATION_DATA_STORE` | `0x40000000` |
| `TELESTO_APPLICATION_DOMAIN` | `0x40000001` |
| `TELESTO_STATIONARY_DATA` | `0x40000002` |
| `TELESTO_SENSOR_CALIBRATIONS` | `0x40000003` |
| `TELESTO_PROGRAMMED_SERIAL_NUMBER` | `0x40000004` |
| `TELESTO_RESERVED_1` | `0x40000005` |
| `TELESTO_PRINT_LOGS` | `0x40000006` |
| `TELESTO_SINGLE_SECTOR_END` | `0x4000ffff` |

### 7.2 Debug/collection region

| Name | Address |
| --- | ---: |
| `TELESTO_CRASH_COREDUMP` | `0x40010000` |
| `TELESTO_COLLECTION_BASE` | `0x40020000` |
| `TELESTO_COLLECTION_MAX` | `0x4002ffff` |

A collection index is encoded as:

```text
address = TELESTO_COLLECTION_BASE | (collectionIndex & 0xffff)
offset  = 0
length  = TELESTO_LENGTH_INFER_FROM_PREFIX  // 0
```

### 7.3 Scalar/status region

| Name | Address |
| --- | ---: |
| `TELESTO_COLLECTION_COUNT` | `0x40030000` |
| `TELESTO_UNIX_TIME` | `0x40030001` |
| `TELESTO_LSM6DSO32_FREQ_FINE` | `0x40030002` |
| `TELESTO_BATTERY_VOLTAGE` | `0x40030003` |
| `TELESTO_PRODUCT_HEADER` | `0x40030004` |
| `TELESTO_STORED_COLLECTION_INDEXES` | `0x40030005` |
| `TELESTO_PLATFORM_VERSIONS` | `0x40030006` |
| `TELESTO_LAST_PROGRAMMED_UNIX_TIME` | `0x40030007` |
| `TELESTO_SERIAL_NUMBER` | `0x40030008` |
| `TELESTO_PHOTOTRANSISTOR_VOLTAGE` | `0x40030009` |
| `TELESTO_GPIO_STATUS` | `0x4003000a` |
| `TELESTO_RECENT_SATELLITE_EVENTS` | `0x4003000b` |
| `TELESTO_MOST_RECENT_STATIONARY_DATA` | `0x4003000c` |
| `TELESTO_CROPPED_STATIONARY_DATA` | `0x4003000d` |
| `TELESTO_CURRENT_ADVERTISING_DATA` | `0x4003000e` |
| `TELESTO_LAST_RX_RSSI` | `0x4003000f` |
| `TELESTO_LIFETIME_COLLECTION_COUNT` | `0x40030010` |
| `TELESTO_LED_SEQUENCE` | `0x40030011` |

### 7.4 Sensor region

| Name | Address |
| --- | ---: |
| `TELESTO_SENSOR_0_FIFO` | `0x40040000` |
| `TELESTO_SENSOR_0_CURRENT_CONFIG` | `0x40040001` |
| `TELESTO_SENSOR_0_LAST_OUTPUT` | `0x40040002` |
| `TELESTO_SENSOR_0_STATE_CONFIGS` | `0x40050000` |
| `TELESTO_SENSOR_0_STREAMING_CONFIG` | `0x40050001` |
| `TELESTO_SENSOR_0_STATE_CONFIG_0` | `0x40050100` |
| `TELESTO_SENSOR_0_STATE_CONFIG_1` | `0x40050101` |
| `TELESTO_SENSOR_0_STATE_CONFIG_MAX` | `0x40050200` |

### 7.5 Firmware/reboot region

| Name | Address |
| --- | ---: |
| `TELESTO_PRIMARY_IMAGE` | `0x40060000` |
| `TELESTO_FAILSAFE_IMAGE` | `0x40060001` |
| `TELESTO_REBOOT_TRACKING` | `0x40060002` |

The address constants describe the virtual map. They do not by themselves prove that every region is safe to read or write on every firmware version.

## 8. Known payload structures

### Stored collection indexes

```c
struct TelestoStoredCollectionIndexes {
    uint16_t rangeStart; // +0
    uint16_t rangeEnd;   // +2
};                         // sizeof = 4
```

The transfer operation reads exactly four bytes from `0x40030005`.

The representation is an inclusive range in Haversine's iteration logic, subject to 16-bit rollover handling. The transfer operation can select a subrange after an optional `lastTransferEndIndex` and may re-read the index range after advertising indicates that collection is still active.

### Platform versions

```c
struct TelestoPlatformVersions {
    uint8_t hardwareVersionMajor; // +0
    uint8_t hardwareVersionMinor; // +1
    uint8_t firmwareVersionMajor; // +2
    uint8_t firmwareVersionMinor; // +3
};                                  // sizeof = 4
```

### Unix time

```c
struct TelestoUnixTime {
    uint32_t secondsSince1970; // +0
};                              // sizeof = 4
```

### Serial number

The Haversine serial-number wrapper is six bytes (`work-hsl-meta.txt:3228-3250`). The exact firmware-side encoding/character presentation is handled by Haversine wrappers.

### Sensor configuration header

```c
struct TelestoSensorConfigsHeader {
    uint32_t headerLength; // +0
    uint32_t version;      // +4
    uint8_t  info[32];     // +8
    uint32_t dataOffsets[];// +40
};                          // minimum size = 44
```

`dataOffsets` is a variable-length array. The header length and version must be honored; do not assume one fixed number of sensors.

### Stationary data

```c
struct TelestoStationaryDataHeader {
    uint32_t headerLength; // +0
    uint8_t  version;      // +4
    uint32_t openDataSets[2]; // +5, packed/unaligned
};                             // sizeof = 13

struct TelestoStationaryDataSetV1 {
    uint32_t unixTime;     // +0
    uint8_t  fifoSlots[7][8]; // +4
};                            // sizeof = 60
```

Constants:

```text
TELESTO_STATIONARY_DATA_V1_DATA_SET_SIZE = 60
TELESTO_STATIONARY_DATA_V1_DATA_SET_MAX_COUNT = 68
TELESTO_STATIONARY_DATA_V1_DATA_SET_STARTING_OFFSET = 16
```

The HSL sensor stream operation calls PPCommon stationary-data parsing functions; that sensor sample interpretation is outside the audio transfer path.

### Sensor calibrations

```c
struct TelestoSensorCalibrations {
    uint32_t length; // +0
    uint8_t  serializedSensorCalibrationData[]; // +4
};
```

The cinterop minimum size is five bytes because the original C declaration uses a one-element trailing array. Actual payload size is controlled by `length`.

## 9. Haversine operation inventory

All of the following ultimately use `TelestoOperation_init` or a compound operation that creates Telesto child operations (`work-hsl-meta.txt:3973-4238`).

### Direct/basic operation

`TelestoOperation_init` accepts a `TelestoInputParameters` request and optional Data payload. It is the generic one-request abstraction:

```text
Ctrl: request
Data: optional program payload
Ctrl: response
Data: optional read result
```

Several direct Haversine methods expose exact request parameters:

| API | Type | Address | Offset | Length |
| --- | --- | ---: | ---: | ---: |
| `readCollectionCounts()` | READ | `0x40030000` | 0 | 2 |
| `programCollectionCount(UInt16)` | PROGRAM | `0x40030000` | 0 | 2 |
| `readRxRSSI(...)` | READ | `0x4003000f` | 0 | 1 |
| `readCollectionData(at:)` | READ | `0x40020000 | index` | 0 | 0/infer prefix |
| `programLEDSequence([UInt8])` | PROGRAM | `0x40030011` | 0 | array count |

Evidence: `work-hsl/HaversineSatellite-disasm.txt` around `0x1aa30-0x1aa54` (collection count program), `0x1d788-0x1d7c4` (collection read), `0x1dcf4-0x1dd04` (LED program), and `work-hsl/HaversineReadRxRSSIOperation-disasm.txt` (`__TEXT,__const` request bytes `03 0f 00 03 40 00 00 00 00 01 00 00 00`). RSSI averaging is performed by the phone operation after one-byte reads; the requested count is not a Telesto field.

### Collection transfer

`HaversineTransferCollectionsOperation` is a compound operation with phases:

```text
0 READ_STORED_INDEXES
1 READ_COLLECTIONS
2 READ_ADVERTISING_DATA
3 FINISHED
```

Sequence:

1. Read four bytes at `0x40030005`.
2. Parse `rangeStart`/`rangeEnd`.
3. For each selected collection index, issue READ at `0x40020000 | index`, offset zero, length zero.
4. Accumulate collection Data into a `0xa0000` (655,360-byte) buffer.
5. Deliver the complete collection to the collection delegate.
6. Advance the index and continue.
7. Read ten bytes at `0x4003000e`.
8. Parse the advertising TLV payload after its two-byte TLV header.
9. Finish, or return to stored-index discovery if the ring remains in collection state.

The collection buffer is at internal object offset `0x7f` and the current-byte counter is at offset `0xa0090`; the ARM64 immediate `0xa0, lsl #12` is `0xa0000`, not `0xa000` (`transferop-c-disasm.txt:244-300`).

The complete collection callback carries raw bytes and the collection index. Telesto does not parse the PPCollection container.

### Cache update

`HaversineUpdateCacheOperation` reads platform/state data through multiple Telesto child operations, including platform versions, serial/application data, and sensor configuration data. The phone-side object parses `TelestoSensorConfigsHeader`, length-prefixed payloads, and failsafe-dependent fields. The exact per-firmware payload contents are not fully documented here.

### Sensor stream/service

`HaversineSensorStreamOperation` reads sensor FIFO/configuration/calibration/status payloads and invokes PPCommon functions such as:

```text
PPParseStationaryDataSets
PPParseStationaryDataHeader
PPParseCompressedSTFIFOData
PPDeserializeCalibrations
```

`HaversineSensorServiceOperation` is a small multi-phase Telesto service operation driven by current hardware version and current Unix time. Its exact request constants and firmware-side service semantics require separate sensor-focused reconstruction.

### Diagnostics and debug

The public operations are:

```text
HaversineReadDebugInfoOperation_init
HaversineReadRxRSSIOperation_init
HaversineDiagnosticOperation_init
HaversineReadLastAudioSamplesOperation_init
```

They use ordinary Telesto READ operations against the status/debug regions and parse the returned payloads. `HaversineReadLastAudioSamplesOperation` additionally reads collections and invokes `PPCollection_createAudioTimeline`, which is the audio path documented in `report.md`.

### Programming/erase/update

Application data is stored in the Telesto application-data region. The PPCommon application payload used by the current pairing path is:

```c
struct PPRingApplicationData {
    uint32_t fingerprint;
    uint32_t timestamp;
    char uid[129];
}; // serialized size 141 (0x8d) bytes
```

Haversine's `programWithApplicationData` uses the program-with-erase path against the application-data address (`0x40000000`) and sends the payload on Telesto Data. The phone-side code also exposes explicit application-data erase/clear operations. The exact firmware erase granularity and authorization rules are not established.

The public satellite API exposes:

```text
programWithApplicationData
eraseApplicationData
clearApplicationData
eraseDebugData
programCollectionCount
programLEDSequence
programFirmware
```

The phone-side library has Telesto ERASE, PROGRAM, and ERASE_AND_PROGRAM request types. Application-data programming uses the `0x40000000` region and a length/payload. Firmware uses `HaversineSuotaOperation` and the primary/failsafe image regions. These are destructive or state-changing and should not be inferred from the read-only collection path.

### System input

`HaversineSystemInputOperation` creates a fixed seven-byte system-input write and sends it over the System Input characteristic, not the Telesto Ctrl/Data channels. It is scheduled by the same HaversineLinkController but does not use a TelestoResponse.

## 10. Recording-transfer example

For collection index `0x37`, the request bytes are:

```text
03 37 00 02 40 00 00 00 00 00 00 00 00
```

Interpretation:

```text
type    = 0x03 READ_MEMORY
address = 0x40020037
offset  = 0
length  = 0 (infer from prefix)
```

The ring returns a 12-byte Ctrl header:

```text
error  = u32le(response[0:4])
info   = u32le(response[4:8])
length = u32le(response[8:12])
```

Then `length` Data bytes form the logical collection. The collection begins with the PPCollection 3-byte length prefix, not a Telesto header. The caller should preserve the complete returned collection and pass it to the PPCollection parser.

For stored indexes, use:

```text
03 05 00 03 40 00 00 00 00 04 00 00 00
```

For current advertising data, use:

```text
03 0e 00 03 40 00 00 00 00 0a 00 00 00
```

## 11. Independent-client implementation rules

For a read-only client:

1. Discover the service and all three characteristics.
2. Establish the OS BLE bond. Do not implement application encryption.
3. Subscribe to Ctrl and Data notifications.
4. Send a complete 13-byte READ request on Ctrl.
5. Assemble the 12-byte Ctrl response across notifications.
6. Accept Data notifications before or after the Ctrl header; buffer them.
7. Stop at the declared response length; flag excess bytes.
8. Parse the four-byte stored-index range.
9. Read collection addresses with request length zero.
10. Validate the returned collection prefix and record lengths.
11. Decode the PPCollection/DDRice layer separately from Telesto.
12. Avoid ERASE, PROGRAM, CANCEL, System Input, and firmware operations until live-tested.

There is no transaction ID, CRC, checksum, application-layer encryption, or Telesto-level FEC in the structures recovered here. BLE link encryption and ATT reliability remain below this protocol.

## 12. Confirmed versus unresolved

### Known from binary evidence

- BLE service/characteristic roles and UUIDs.
- Request and response sizes/fields/endian order.
- Operation-type values.
- Ctrl/Data sequencing in Haversine's controller.
- Streaming READ Data behavior.
- Collection transfer addresses and phase machine.
- Virtual address constants.
- Several fixed payload layouts.
- Cancellation frame construction and client-side error mapping.

### Strong inference

- Telesto is a general firmware virtual-memory/RPC interface used for collections, sensors, state, diagnostics, and programming.
- The Index normally permits one active connection, so a client should serialize operations and release the link when idle.

### Unknown without ring firmware or live capture

- Meaning of `TelestoResponse.info`.
- Firmware validation rules and permissions for each address.
- Exact ERASE/PROGRAM sector semantics.
- Firmware image chunk size, bootloader protocol, and verification.
- Full sensor FIFO/calibration sample semantics.
- Whether every firmware build uses identical virtual-address behavior.
- Any ring-side flash encryption transparent to Telesto.
- Exact notification ordering under all firmware/transport conditions.
