# Independent Pebble Index client specification and gap audit

Last updated: 2026-08-20 (Asia/Singapore)

This is an implementation contract derived from the exact `03202f5`
Haversine artifacts, their native dependencies, the decompiled same-revision
Android AAR, and the open-source app at the matching Haversine update. It
separates behavior that can be implemented from behavior that still needs a
device capture or firmware evidence.

The safest first independent client is **read-only**: pair at the operating
system BLE layer, subscribe to the two Telesto characteristics, download a
whole collection by index, save the exact bytes durably, and decode them
offline. Do not add an erase or acknowledgement write. No collection
acknowledgement/deletion command was found in the transfer implementation.

## 1. Confidence labels

- **Proven**: exact constants, layouts, or control flow recovered from the
  `03202f5` binaries/IR and cross-checked across implementations.
- **Observed**: supplied in the brief from an actual app/ring interaction, but
  not completely explained by the static binaries.
- **Recommended**: safer independent-client policy; it may deliberately be
  stricter than Haversine.
- **Unresolved**: must not be filled in by assumption.

## 2. End-to-end client state machine

```text
scan for either Haversine service UUID
  -> user selects/authorizes one peripheral
  -> establish OS BLE pairing/bond as applicable
  -> connect and discover Haversine service
  -> discover ctrl, data, and system-input characteristics
  -> enable notifications on ctrl, then data
  -> Telesto READ stored-index range
  -> select first unread index using modular UInt16 arithmetic
  -> for every index:
       Telesto READ complete collection object
       assemble notification fragments to response.length
       validate and durably save exact collection bytes
       parse/decode collection
       transactionally advance local checkpoint
  -> re-read stored-index range to catch newly completed collections
  -> if empty, read current advertisement state
       if still recording/in collection state: poll again
       otherwise: finish
```

Only one Telesto operation should be outstanding at a time.

## 3. Discovery and advertisement parsing

### 3.1 Service filters

Scan for either service UUID:

| Form | UUID |
| --- | --- |
| Bluetooth-base/16-bit form | `0000FCC9-0000-1000-8000-00805F9B34FB` |
| 128-bit form | `607B5C9B-3700-4E94-F44A-2DF900BCB0C3` |

Android Haversine installs both scan filters. On service discovery it tries the
16-bit form first, then the 128-bit form. An independent client should accept
either and should not require a device-name match. The app's RSSI thresholds,
`CoreRing` name checks, and companion-picker UI are selection policy, not wire
protocol.

Identify the selected ring using the OS peripheral identifier:

- iOS: the CoreBluetooth peripheral UUID;
- Android: the normalized Bluetooth address in the current app.

Persist all local resume state under that identifier. This is an identifier,
not a cryptographic key.

### 3.2 Optional manufacturer payload

The native parser accepts either six bytes or eight bytes. For the eight-byte
form it skips the first two bytes, which are compatible with a manufacturer
identifier prefix. It then interprets:

```text
u32le fingerprint
u8    truncatedCollectionCount
u8    flags
```

Flag bits used by Haversine are:

| Bit | Meaning |
| ---: | --- |
| 7 | moving |
| 6 | needs servicing |
| 5 | in collection/recording state |
| 4 | debug information available |
| 3 | extracted internally but not exposed by the recovered public object |

The collection count is the low eight bits of a collection end index. It is a
scan optimization, not a substitute for reading the authoritative stored
index range.

The transfer operation's ten-byte “current advertisement data” read eventually
feeds bytes 4 through 9 of that response to the same six-byte parser. For the
download loop, only flag bit 5 is required.

## 4. Pairing, bonding, and registration

### 4.1 BLE bond

BLE link security and Haversine application data are separate:

- The current Android app explicitly requests an OS bond with
  `BluetoothDevice.createBond()`.
- iOS has no equivalent public explicit-bond API; pairing is normally triggered
  by accessing a characteristic whose GATT permissions require encryption or
  authentication.
- The brief reports an iOS sequence that connects, discovers the 128-bit
  service and `DAAD...` characteristic, writes one byte `00` with response,
  and disconnects. Treat that as an **observed bond-trigger ritual**, not as a
  Telesto message: Telesto requests are 13 bytes and are written to the control
  characteristic, while `DAAD...` is the data characteristic.

The static client binary does not reveal the live GATT security permissions,
the pairing method, or whether the `00` write is required on all firmware
versions. A practical iOS implementation may reproduce the observed sequence,
wait for the OS pairing UI/result, then reconnect. It must keep that write
outside the Telesto state machine and should capture/verify it on hardware
before shipping.

No application-level challenge/response, key exchange, or shared-secret
authentication precedes a collection read.

### 4.2 User/application-data programming is not a secret exchange

The Pebble app additionally programs a user identity. This is registration
metadata, not recording decryption material. An already registered ring should
be tested read-only before overwriting it.

Version-1 application data is exactly 141 bytes:

```text
offset  size  value
0       4     u32le version = 1
4       4     u32le noncryptographic fingerprint
8       4     u32le Unix timestamp
12      129   zero-padded, NUL-terminated user UID bytes
```

The UID must fit in 128 bytes plus a terminator. Haversine's fingerprint
algorithm is deterministic and non-secret:

1. Copy the UID into a zeroed 132-byte scratch area.
2. Read it as 33 little-endian `uint32` words.
3. Apply the following 32-bit wrapping mixer to each word and XOR all results:

```text
mix(x):
    x = (x + 0x7ed55d16 + (x << 12)) mod 2^32
    x = (x ^ 0xc761c23c ^ (x >> 19)) mod 2^32
    x = (x + (x << 5)) mod 2^32
    x = (((x << 9) + 0xaccf6200) ^
         (x + 0xe9f8cc1d)) mod 2^32
    x = (x + 0xfd7046c5 + (x << 3))  mod 2^32
    x = (x ^ 0xb55a4f09 ^ (x >> 16)) mod 2^32
```

Only the low 16 fingerprint bits are used by the normal UID/no-user matching
helpers. Failsafe matching uses the exact value `0xDEADDEAD`.

To program the 141-byte record, Haversine first makes:

```text
u32le totalSize = 145
u8    applicationData[141]
```

It then performs Telesto `ERASE_THEN_PROGRAM` (operation `5`) at virtual
address `0x40000000`, offset `0`, length `145`, and sends those 145 bytes on
the data characteristic. Drain the 13-byte request on the control
characteristic first, then drain the 145-byte body on the data characteristic,
and await the ordinary 12-byte response. Do not expect a secret or another
registration payload in that response.

This programming flow is implementable, but whether it is required for a
third-party downloader or enforced by firmware remains unresolved. The
recovered Haversine access checks are app-side device/user selection checks,
not cryptographic authorization.

## 5. GATT connection contract

### 5.1 Characteristics

Discover these characteristics in the selected Haversine service:

| Role | UUID | Normal use |
| --- | --- | --- |
| Telesto control | `C0EF558A-2058-FABF-A140-8D5ACDE50B39` | write 13-byte requests; receive 12-byte responses as notifications |
| Telesto data | `DAAD3D52-237C-90A7-B54B-8854A134D801` | send program data; receive read payload bytes as notifications |
| System input | `1D1F4039-23F5-33B2-C24E-704351F20585` | Haversine connection/disconnect convention; not used for recording bytes |

Haversine requires all three to be present before declaring the connection
ready. A minimal downloader only carries protocol data over control and data,
but discovering all three is a useful firmware-compatibility check.

Enable notifications by writing the standard CCCD
`00002902-0000-1000-8000-00805F9B34FB` on:

1. control;
2. data.

Do not send a Telesto request until both subscriptions succeed.

### 5.2 Outgoing fragmentation

GATT write boundaries are not Telesto/audio frame boundaries.

- The Android build slices outgoing buffers into 20-byte writes and configures
  the Telesto characteristics for write-without-response.
- The iOS adaptor uses `maximumWriteValueLength(for:)`. It normally sends
  without response and, when supported, inserts a with-response write after
  three no-response packets for pacing/confirmation.

A 13-byte control request normally fits in one write. Application-data
programming is fragmented. An independent iOS client should honor the live
characteristic properties and CoreBluetooth flow control; it must not hardcode
Android's 20-byte size.

Using with-response for every packet is acceptable only if the live
characteristic advertises that property and hardware testing confirms it.
Otherwise mirror the recovered no-response flow and use
`canSendWriteWithoutResponse`/the platform equivalent.

Incoming control and data notifications may be split independently and may
interleave. Never decode a notification as a complete response, collection,
or audio frame.

## 6. Telesto wire format

### 6.1 Request

Every request is a packed 13-byte little-endian structure:

```text
offset  size  field
0       1     operation
1       4     address
5       4     offset
9       4     length
```

Operation values:

| Value | Meaning |
| ---: | --- |
| 0 | no operation |
| 1 | erase |
| 2 | program |
| 3 | read |
| 4 | cancel |
| 5 | erase then program |

### 6.2 Response

The control response is packed and exactly 12 bytes:

```text
offset  size  field
0       4     u32le error
4       4     u32le info
8       4     u32le dataLength
```

Accumulate control notifications until exactly 12 bytes are present. Haversine
treats an unexpected response or any control chunk exceeding the remaining 12
bytes as a controller error.

For a read, collect data notifications until `dataLength` bytes have arrived.
The recovered controller tolerates data arriving before all 12 control bytes:
it streams those bytes to the operation, then checks the declared length when
the response is complete. An independent client should support this ordering
while enforcing the operation-specific maximum allocation.

Completion conditions:

- read: complete control response and `receivedData == dataLength`;
- non-read: complete response after outgoing request/data writes have drained;
- any nonzero `error`: operation failure.

Preserve `info` in diagnostics. Its complete semantic/error-code mapping is not
recovered.

Haversine caps excess read data at the declared length and warns. A new client
should treat excess bytes as protocol desynchronization, disconnect, and resume
from its last durable collection checkpoint.

### 6.3 Cancellation

To cancel an active request, Haversine sends operation `4` with the original
address, offset, and length. Cancellation is not an acknowledgement and does
not delete a collection. Disconnecting is safer than attempting to continue
after malformed or misrouted bytes.

There is no request ID or sequence number. This is why one-outstanding-operation
discipline is mandatory.

## 7. Stored collection range and modular indexing

Read the authoritative range with:

```text
operation = READ (3)
address   = 0x40030005
offset    = 0
length    = 4
```

Require a four-byte result:

```text
u16le rangeStart
u16le rangeEnd
```

The range is half-open and uses 16-bit modular arithmetic:

```text
[rangeStart, rangeEnd) modulo 65536
```

`start == end` is empty. Iterate with:

```text
i = start
while i != end:
    use i
    i = (i + 1) & 0xffff
```

Do not implement range membership with ordinary signed ordering. Native
Haversine increments a `uint16` and compares modular distances, and its
membership walk has a safety guard at approximately `0x200` increments.
Current Kotlin bridge code converts the endpoints to a normal `IntRange`; that
bridge is not a reliable model for a `start > end` rollover case.

As a recommended client policy, reject an advertised modular span greater than
512 as implausible. The recovered native membership walk has a defensive guard
at roughly `0x200` increments, but that does not establish a firmware wire
maximum. The client cap prevents a corrupt range from driving an effectively
unbounded download.

### 7.1 Local resume state

Persist, per OS ring identifier:

- `processedNextCollectionIndex: UInt16?`;
- optionally the last fully saved collection hash/path and multipart state.

Select `processedNextCollectionIndex` only if it lies in the current modular
half-open range. Otherwise start at `rangeStart`. A robust test is:

```text
distance(a, b) = (b - a) & 0xffff
inRange(x, start, end) =
    distance(start, x) < distance(start, end)
```

Treat `processedNext == end` as no work.

Haversine has two resume layers:

1. Its native per-ring cache stores `lastTransferEndIndex`, meaning the next
   index after the last transport-successful collection. If that value lies in
   the new range, the native operation moves the range start to it.
2. The Kotlin app storage records the last successful collection index and
   chooses `max(rangeStart, last + 1)`.

The second rule is non-modular. More importantly, Kotlin advances its value
before checking for empty data or successfully parsing/decoding the collection.
Do not reproduce that ordering.

**Recommended transaction:** receive the complete declared object, validate
its envelope, and durably store the exact raw bytes as a staging artifact.
Decode and durably commit the resulting recording/metadata, then atomically
advance `processedNextCollectionIndex = index + 1`. Never advance this
processing/resume checkpoint on transport, parse, or decode failure. A client
may maintain a separate raw-download inventory so that it can retry offline
decode without losing the captured blob, but it must not silently use that
inventory to mark a corrupt/unprocessed recording complete.

Telesto has an offset field, but Haversine always reads a collection from
offset zero and does not resume inside a collection. After a disconnect, re-read
the whole object.

## 8. Collection download loop

For collection index `i`, issue:

```text
operation = READ (3)
address   = 0x40020000 | i
offset    = 0
length    = 0
```

The zero request length means “return the whole virtual object”; the response
provides its actual byte length. Haversine allocates at most `0xA0000`
(655,360) bytes for one collection. Apply that bound before accepting/allocating
the response.

After each complete collection:

1. stage it durably with its `UInt16` index;
2. validate/decode and commit it before advancing the processing checkpoint;
3. increment the wire index modulo 65536;
4. continue until the selected half-open range end;
5. read `0x40030005` again, because a recording may have produced more
   collections during the download.

When the stored range is empty, Haversine reads:

```text
operation = READ (3)
address   = 0x4003000E
offset    = 0
length    = 10
```

If bit 5 of the final flags byte is set, it loops back to the stored-index read.
If clear, it completes. A production client needs an overall timeout/cancel
policy because no poll delay or maximum “still recording” duration was
established as a protocol requirement.

On a child-read failure, Haversine emits failure callbacks for the current and
remaining indexes and ends the operation. It has no collection-read retry loop.
Retry by reconnecting and applying the durable local checkpoint; do not assume
the protocol retransmits a failed notification chunk.

## 9. Collection object parser

Validate the complete object before iterating records. The native parser accepts
three outer forms:

| Condition | Length field | Records start |
| --- | --- | ---: |
| at least four bytes and byte 3 is zero | `u32le` total buffer length at bytes 0..3 | 4 |
| otherwise byte 0 is `0xff` | `u16le` payload length at bytes 1..2, equal to `size - 3` | 3 |
| otherwise | 24-bit big-endian payload length at bytes 0..2, equal to `size - 3` | 3 |

Every record starts with:

```text
u8    type
```

The remaining header is selected by that type:

```text
type 0x50 or 0x51:
    u32le payloadLength
all other recognized types:
    u16le payloadLength
u8    payload[payloadLength]
```

Check every addition and bound before advancing. Relevant types:

| Type | Meaning |
| ---: | --- |
| `0x50` | uncompressed 16-bit audio |
| `0x51` | compressed 16-bit DDRice audio |
| `0x52` | multipart audio metadata |
| `0x53` | button sequence |
| `0x54` | lifetime collection count |

If both audio types exist, Haversine prefers `0x50`.

### 9.1 Multipart metadata record

`0x52` is a normal/u16-length record. Its six-byte payload is:

```text
u32le collectionStartIndex
u8    isMultiPart
u8    isFinalPart
```

Reject a shorter payload. Treat nonzero booleans as true for compatibility.

## 10. Audio decoding

### 10.1 Uncompressed record `0x50`

Payload:

```text
u32le sampleRateHz
i16le samples[(payloadLength - 4) / 2]
```

Require `payloadLength >= 4` and an even number of sample bytes. Haversine
copies these bytes directly; the result is signed mono PCM16 little-endian.

### 10.2 Compressed record `0x51`

Payload:

```text
u8    config
u32le compressedBitCount
u32le sampleRateHz
u8    bitstream[payloadLength - 9]
```

Require:

```text
payloadLength >= 9
compressedBitCount <= (payloadLength - 9) * 8
```

There is one decoder channel, no sample-count field, and no fixed frame size.
Read bits most-significant-bit first. Let:

```text
shift = config & 0x0f
limit = config >> 4
width = 16 - shift
modulus = 1 << width
```

The shipped encoder initializer limits canonical emitted configurations to
`<= 0xef`, but the collection decoder does not repeat that check and accepts
all byte values, including `limit == 15`. A compatible decoder must not reject
`0xf0..0xff` solely because the shipped encoder would not produce them.

Initialize predictor state:

```text
firstDelta = 0
sampleBase = 0
```

Decode one second difference:

```text
lead = readBit()
if no bit remains before lead:
    end of stream

if lead == 1:
    diff = 0
else:
    zeros = 1
    foundTerminator = false

    while zeros < limit:
        bit = readBit()
        if no bit remains:
            truncated code
        if bit == 1:
            foundTerminator = true
            break
        zeros += 1

    if foundTerminator:
        magnitude = zeros
        sign = readBit()
        if no bit remains:
            truncated code
        encoded = magnitude if sign == 0 else modulus - magnitude
    else:
        encoded = readBitsMSB(width)
        if insufficient bits:
            truncated code

    diff = encoded if encoded < modulus / 2 else encoded - modulus
```

Reconstruct one sample using wrapping 16-bit arithmetic:

```text
firstDelta = (firstDelta + diff) & 0xffff
sampleBase = (sampleBase + firstDelta) & 0xffff
sampleBits = (sampleBase << shift) & 0xffff
sample = signedInt16(sampleBits)
```

Repeat until the exact bit count is exhausted. Predictor state resets for each
compressed audio record, including each collection part.

The native decoder returns the same status `3` when no lead bit remains and
when EOF occurs during the unary run, sign bit, or raw escape. The collection
loop accepts any status `3` as successful. Thus it accepts an incomplete final
codeword, not just clean EOF between codewords. For byte-for-byte Haversine
compatibility, a client can stop at that point; a safer standalone decoder
should reject/flag “ended mid-symbol.” There is no encoded sample count or CRC
with which to prove that the final sample sequence is complete.

This branch is visible independently in the simulator objects: all ARM64
mid-code EOF branches converge on status 3 at `DDRiceCompression.o:0x5e8`, and
`PPCollection.o:0x578..0x580` accepts status 3; the x86_64 equivalents converge
at `DDRiceCompression.o:0x55f/0x564` and are accepted at
`PPCollection.o:0x55d..0x568`.

This is custom second-order delta/unary-with-escape coding named
`DDRiceCompression` in the binary. It is not Opus, Speex, or IMA ADPCM.
Nonzero `shift` may discard low bits, so only `shift == 0` is unambiguously
lossless.

### 10.3 Output properties and unresolved capture values

| Property | Implementable result |
| --- | --- |
| width | signed 16-bit PCM |
| byte order when serialized | little-endian |
| channels | one/mono |
| sample rate | the per-record `u32le sampleRateHz` |
| compressed bit order | MSB first |
| codec frame size | none |

Do not hardcode 16 kHz. The Pebble app resamples the reported source rate to
16 kHz later. The actual Index source rate, normal record type, and normal
compression config need a real collection capture.

## 11. Multipart reconstruction

For `isMultiPart == false`, emit the decoded PCM from that collection as one
recording and use the collection's own index as its logical start.

For `isMultiPart == true`:

1. group parts by `collectionStartIndex`;
2. require the same sample rate in every part;
3. require unique, modularly consecutive collection indexes;
4. decode each part independently, resetting DDRice predictor state;
5. concatenate decoded PCM16 samples in collection-index order;
6. emit only when the part with `isFinalPart != 0` has arrived and no gap
   remains.

Haversine appends parts in arrival order, detects duplicate indexes and sample
rate mismatch, and reports whether the set is contiguous. If a new
`collectionStartIndex` arrives while a previous multipart object is open, it
flushes the previous object as incomplete and starts another. A safer client
should retain/report the incomplete group rather than presenting it as a
normal complete recording.

Do not concatenate compressed bitstreams. Multipart joining occurs after each
collection has become PCM16.

## 12. Integrity and error policy

Mechanisms actually present:

- response-declared total data length;
- exact collection-envelope length;
- per-record lengths;
- compressed bit-count bound;
- collection indexes and a stored half-open range;
- multipart start/index/sample-rate checks;
- Telesto operation error code;
- BLE/GATT's lower-layer delivery and optional write confirmation.

Mechanisms absent from this application path:

- CRC/checksum;
- cryptographic hash or MAC;
- per-chunk sequence number;
- FEC;
- audio-frame acknowledgement;
- application retransmission.

Recommended failure handling:

| Failure | Action |
| --- | --- |
| service/characteristic/subscription failure | disconnect; rescan/reconnect |
| control bytes exceed 12 or arrive with no operation | declare desync; disconnect |
| data on a non-read operation | declare desync; disconnect |
| nonzero Telesto error | fail operation; retain diagnostic `error/info` |
| response exceeds operation cap | cancel/disconnect without allocating |
| short/excess data relative to response length | do not checkpoint; reconnect |
| malformed collection/TLV | preserve raw bytes separately; do not claim decoded success |
| decoder ends mid-symbol | emit a corruption warning at minimum |
| multipart gap/rate/start mismatch | retain/report incomplete; do not silently merge |

No protocol timeout constants were recovered as a stable wire requirement.
Make connection, response, data-progress, and overall-recording-poll timeouts
configurable and log the last state/checkpoint.

## 13. Acknowledgement, retention, and deletion

This is the critical safety boundary.

The recovered collection transfer performs only:

- `READ 0x40030005` for the range;
- `READ 0x40020000 | index` for each collection;
- `READ 0x4003000E` for current advertisement state.

It never sends:

- an application acknowledgement for a collection;
- a “mark consumed” request;
- an erase/program request at a collection address;
- an explicit delete after `TransferComplete`.

Its `lastTransferEndIndex` and the app's `lastSuccessfulCollectionIndex` are
local cache values. Updating them does not notify the ring.

Therefore:

1. A Telesto response is only operation completion, not recording
   acknowledgement.
2. A CoreBluetooth write response is only GATT delivery confirmation, not
   recording acknowledgement.
3. The generic Telesto erase operation must not be aimed at guessed collection
   addresses.
4. It is unresolved whether reading the virtual collection object has a
   firmware-side consume side effect, whether the ring independently advances
   its range, or whether retention is entirely firmware-managed.

An independent client can safely download and locally checkpoint. It cannot
yet promise “acknowledge/delete safely.” Keep deletion disabled until a
before/after hardware experiment or firmware analysis proves the lifecycle:

```text
read stored range A
read one collection exactly once
read stored range B without programming or erasing
disconnect/reconnect
read stored range C
```

Record whether the collection remains readable and how the range changes.
Perform this first on expendable test recordings.

## 14. Unresolved gap audit

| ID | Unresolved item | Why static client evidence is insufficient | Evidence/test needed |
| --- | --- | --- | --- |
| G1 | Actual Index sample rate | decoder carries a value; it does not prescribe one | one raw collection capture |
| G2 | Which of `0x50`/`0x51` current firmware emits | both paths are supported | capture from target firmware |
| G3 | Normal DDRice config and golden decode output | config is stored in each record; no fixture shipped | capture plus native-vs-independent decoder comparison |
| G4 | Firmware-internal at-rest bytes/encryption | client sees only the virtual read result | firmware, flash image, or instrumented ring |
| G5 | Exact iOS bond trigger/security permissions | CoreBluetooth hides bond storage; GATT permissions are runtime state | live service dump and pairing capture |
| G6 | Whether lone `00` to `DAAD...` is universally required/safe | observed behavior is outside normal Telesto request framing | paired/unpaired captures across firmware versions |
| G7 | Whether programming UID is required for reads | client programs it, but no Telesto auth exchange exists | read-only test on unregistered and registered rings |
| G8 | Complete Telesto error and `info` meanings | layout is known, semantic table is not | firmware headers/logs or induced failures |
| G9 | Exact rollover behavior and maximum live range | native arithmetic is modular; current bridge uses ordinary `IntRange`; no rollover capture | synthetic/native tests and ring near wrap |
| G10 | Poll interval and maximum “in collection state” duration | recovered operation loops but no stable wire timing rule | long-recording capture |
| G11 | Read side effects, acknowledgement, retention, deletion | no explicit command appears | before/after range and re-read experiment |
| G12 | Partial collection resume support | Telesto has `offset`, but Haversine always re-reads offset 0/length 0 | firmware probing; do not assume |
| G13 | Detection of truncated compressed tail | no sample count/CRC and native accepts generic end-of-bits | capture corruption tests or firmware encoder contract |
| G14 | Manufacturer company/prefix semantics | parser deliberately skips the optional two bytes | BLE advertisement capture/assigned ID lookup if needed |
| G15 | Live characteristic property/MTU matrix | static adaptors support multiple modes | runtime GATT dump on physical Index |

## 15. Suggested implementation order

1. Implement offline packed Telesto/collection parsers and strict bounds tests.
2. Implement DDRice with synthetic vectors and compare it to
   `analysis/native_validation/ddrice_native_harness`.
3. Build a read-only BLE probe that discovers/subscribes and reads only
   `0x40030005`.
4. Download one collection, save the exact indexed blob atomically, and
   disconnect before decoding.
5. Compare independent decode with Haversine/native output.
6. Add modular range resume and multipart persistence.
7. Validate long-running collection-state polling and reconnect behavior.
8. Investigate lifecycle semantics separately. Keep all erase/program features
   behind explicit developer controls; keep collection deletion absent.

## 16. Evidence anchors

Primary retained evidence:

- `analysis/sim_inventory.md` — consolidated protocol, codec, crypto, and
  persistence findings.
- `analysis/device_inventory.md` — exact physical-device artifacts, PPCommon
  record/decoder evidence, and crypto inventory.
- `analysis/toolchain_strategy.md` — exact IR recovery and native-analysis
  workflow.
- `analysis/toolchain_iosarm64_dump_ir.txt` — exact common/iOS wrapper control
  flow, including resume and multipart behavior.
- `analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/transport/HaversineUUID.java`
  — service/characteristic UUID constants.
- `analysis/decompiled_android_debug/com/wtlp/haversinesatellitelibrary/transport/LinkTransport.java`
  — Android discovery, subscriptions, writes, and notification routing.
- `analysis/decompiled_android_debug/coredevices/haversine/AndroidHaversineTransferDelegate.java`
  and `HaversineTransferDelegate.java` — range bridge, local resume, decode
  event ordering.
- `analysis/ghidra_decompiled/libhaversine_protocol.c` and
  `libhaversine_protocol_helpers.c` — Telesto controller and collection
  operation.
- `analysis/TelestoController_x86_64_dwarf.txt` — packed request/response
  layouts.
- `analysis/ghidra_decompiled/libppcommon_audio.c` and
  `libppcommon_helpers.c` — collection parsing and DDRice decoder.
- `analysis/mobileapp_repo/experimental/src/commonMain/kotlin/coredevices/ring/service/RingPairing.kt`
  and platform pairing sources — current app bonding/registration flow.

The exact iOS ARM64 and simulator main KLIB IR dumps are byte-identical, so the
Kotlin-level behavior in this specification applies to both published targets.
