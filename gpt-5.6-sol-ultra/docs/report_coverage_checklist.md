# Final-report coverage checklist

Date: 2026-08-20
Target release: `03202f5`
Scope: independent audit of `brief.md` against `PROGRESS.md` and the completed
evidence reports in `analysis/`.

## Audit result

The evidence is sufficient to answer every requested final-report section,
provided the report preserves three boundaries:

1. The client-visible object returned from the ring is known byte-for-byte,
   but the ring's physical flash representation is not.
2. Haversine has application-level length/completeness checks, but no
   application CRC, MAC, FEC, per-chunk sequence/ack, or retry scheme.
3. The protocol supports both uncompressed `0x50` and compressed `0x51`
   records. No capture establishes which one shipping firmware normally emits,
   its numeric source sample rate, or its usual DD-Rice configuration.

Legend used below:

- **Direct**: established by exact IR, metadata, DWARF, symbols, relocation-aware
  disassembly, or a native test.
- **Strong inference**: multiple direct facts support the conclusion, but the
  missing ring firmware prevents literal proof.
- **Unknown**: not recoverable from the client artifacts.
- **Caution**: a nearby statement is easy to overstate or is stale/incorrect in
  one intermediate note.

## Source precedence

Use the completed focused reports as the current source of truth:

1. `analysis/collection_framing.md`
2. `analysis/pairing_crypto_audit.md`
3. `analysis/sim_inventory.md`
4. `analysis/device_inventory.md`
5. `analysis/toolchain_strategy.md`
6. exact generated IR/disassembly/DWARF and the decoder scripts

`PROGRESS.md` is a chronological log. Its early “in progress” sentences are
historical and are superseded by later completed entries. In particular,
`PROGRESS.md:310-311`, `:323-324`, and `:333-358` are stale relative to
`PROGRESS.md:176-198` and the completed pairing report.

## Required headline answers

| Brief question | Evidence-supported answer | Strongest evidence | Caveat |
|---|---|---|---|
| What format is transmitted? | A complete Haversine collection containing either `0x50` PCM16LE or `0x51` custom one-channel DD-Rice second-difference audio. | `PPParsing.o::_GSParseRecordsInRawData`; `PPCollection.o::_PPCollection_createAudioTimeline` at `0x3b4`; `analysis/collection_framing.md`; `analysis/device_inventory.md` | Which branch real firmware normally emits is unknown without a collection capture. |
| What is stored on the ring? | The ring exposes a storage-like virtual collection object at `0x40020000 \| uint16(index)` and serves the directly parseable collection bytes. | `HaversineTransferCollectionsOperation-*.o`, `_TransferOperation_startNextChild` `0x130..0x1cc`; DWARF enum `TELESTO_COLLECTION_BASE`; `analysis/sim_inventory.md` | Physical flash bytes, a possible materialization step, and transparent firmware/hardware encryption are unknown. Do not state that the physical at-rest format is proven to equal the served object. |
| Raw PCM, ADPCM, Speex, Opus, or other? | `0x50` is raw signed PCM16LE. `0x51` is custom bounded-unary/raw-escape coding of second differences followed by two wrapping integrations. It is not IMA ADPCM, Speex, or Opus. | `DDRiceCompression.o` functions at `0x3b8`, `0x47c`, `0x608`; native harness and four exact encoder vectors; `scripts/decode_index_collection.py` | “DD-Rice” is the shipped symbol/source label, not permission to substitute a generic Rice decoder. |
| Encrypted in the Haversine application layer? | No. Telesto payload bytes flow directly into the collection parser and audio decoder, with no key/decrypt stage. | Exact transfer-to-parser chain; keyless decoder signatures; `analysis/pairing_crypto_audit.md` crypto-reachability audit | Normal BLE link encryption remains a separate OS/controller layer. |
| Encrypted at rest? | Unknown for physical flash. No Haversine-managed at-rest recording cipher or app secret exists. | `analysis/pairing_crypto_audit.md`, especially layer-by-layer conclusion and remaining unknowns | Executive wording should answer “physical at-rest encryption: unknown,” not simply “no.” |
| Registration-derived shared secret? | No. Registration programs UID fingerprint + Unix timestamp + UID, with no challenge, exchange, KDF, key, nonce, or secret result. | `PPRingApplicationData.o` offsets `0x000..0x394`; exact KLIB IR `7889..8045`; `ProgramApplicationDataOperation_init`; `analysis/pairing_crypto_audit.md` | BLE bond keys may exist, but are OS/firmware controlled and are not recording decoder inputs. |
| Numeric source sample rate? | Unknown. Each audio record carries an explicit `u32le sampleRateHz`, which is propagated unchanged to `TransferComplete`. | `PPCollection_createAudioTimeline` raw load at `0x478`, compressed load at `0x580`; exact IR `1409..1428` | 16 kHz is the app's resampling target, not proof of the ring's source rate. |
| Width/channel/order/frame size? | 16-bit signed app-facing samples; operationally one channel/mono; raw bytes little-endian; compressed bits MSB-first; no fixed codec frame size or stored sample count. | `PPResultAudioTimeline_t` ABI; one decoder-channel initialization; `DDRiceDecompressionDecoder_readBit` `0x3b8`; `RingSync.kt` | “Mono” is a strong operational conclusion: there is one sample stream and no channel-count/interleave field. |
| Incremental or complete object? | BLE/Telesto delivery is arbitrarily fragmented, but Haversine buffers one entire collection before PPCommon parsing. A logical recording can span multiple complete collections. | `TelestoController_receive{Ctrl,Data}Bytes`; transfer operation buffer/callback; Swift completion closure `0x394..0x4c4`; IR bridge `5176..5196` | BLE notification boundaries are not codec frames. |
| Integrity? | Length/error/index/contiguity checks exist. No application CRC/checksum/hash/MAC/FEC, per-chunk sequence, per-chunk acknowledgement, or retry. | Telesto structs and controller; `GSParseRecordsInRawData`; `MultipartCollection` IR; `analysis/sim_inventory.md` | The 12-byte Telesto response is operation-level status, not a consumer acknowledgement or per-audio-frame ACK. |

## Section 1: Executive answer

The report must explicitly cover all six requested questions:

- [x] **What the Index stores.**
  - Direct: it exposes indexed objects at
    `TELESTO_COLLECTION_BASE = 0x40020000`.
  - Strong inference: the served collection is likely the storage object because
    a whole-object READ by index is immediately parsed.
  - Unknown: raw physical flash representation and transparent firmware
    transformation/encryption.
  - Evidence:
    `analysis/iossimulatorarm64-transfer-c-arm64-dwarf.txt:325-367`;
    `analysis/iossimulatorarm64-transfer-c-arm64-disassembly.txt`,
    `_TransferOperation_startNextChild` `0x130..0x1cc`;
    `analysis/sim_inventory.md`, “Collection transfer and chunking.”

- [x] **What it transmits.**
  - One complete collection object, delivered in arbitrary GATT notification
    fragments, with audio record `0x50` or `0x51`.
  - Evidence:
    `_TransferOperation_handleReceivedDataFromChild` at `0x244`;
    `_TransferOperation_handleCompletionFromChild` at `0x310`;
    Swift collection-finish closure at `0x394` and delegate call at `0x4c4`;
    `analysis/collection_framing.md`.

- [x] **What Haversine receives.**
  - A 12-byte control response plus `response.length` data bytes over the
    Telesto control/data characteristics; the data bytes are the collection,
    with no additional Haversine wrapper around each notification.
  - Evidence:
    `TelestoController.o::_TelestoController_receiveCtrlBytes` at `0x56c`;
    `_TelestoController_receiveDataBytes` at `0x628`;
    `LinkTransport.java:657-675`.

- [x] **What Haversine outputs.**
  - `TransferStatus.TransferComplete.samples` is a Kotlin `ShortArray` containing
    decoded 16-bit sample bit patterns, plus the record-provided sample rate.
  - Evidence:
    exact IR `analysis/toolchain_iosarm64_dump_ir.txt:1371-1428`;
    `PPAudioTimeline.ios.kt` IR `8276-8390`.

- [x] **Whether recordings are encrypted at rest or in transit.**
  - Application layer in transit: **no**.
  - Haversine-managed at rest: **no**.
  - Physical flash at rest: **unknown**.
  - BLE link: platform controlled; exact negotiated mode unknown.

- [x] **Whether registration derives a shared secret.**
  - **No.** The exact serialized record and programming path are completely
    recovered and keyless.

Required executive caveats:

- Do not pick `0x50` or `0x51` as the normal production format.
- Do not supply a numeric source sample rate.
- Do not call physical at-rest encryption “no.”
- Do not identify the observed one-byte `00` write as a secret exchange.

## Section 2: End-to-end data path

The evidence supports this exact high-level pipeline:

```text
microphone
  -> [physical ring representation: unknown]
  -> ring virtual collection object at 0x40020000 | uint16(index)
  -> collection containing 0x50 PCM16LE
     OR 0x51 one-channel DD-Rice second-difference bitstream
  -> optional BLE link security (OS/controller; outside Haversine)
  -> arbitrary GATT notification fragments on Telesto data
  -> Telesto length-based accumulation
  -> complete collection ByteArray
  -> GSParseRecordsInRawData
  -> PPCollection_createAudioTimeline
  -> direct PCM copy OR DD-Rice decoding
  -> PPAudioTimeline memcpy to Kotlin ShortArray
  -> decoded-PCM multipart concatenation
  -> TransferStatus.TransferComplete(samples, source sampleRate, ...)
  -> app removes DC bias
  -> app resamples to 16,000 Hz
  -> app writes mono PCM16LE
```

Coverage and evidence:

- [x] **Microphone-to-storage boundary marked unknown.**
  - Requires firmware or raw-flash analysis.
- [x] **Ring virtual address and collection read.**
  - `_TransferOperation_startNextChild` constructs READ type `3`;
    address `0x40020000 | currentIndex`; offset and requested length zero.
- [x] **BLE characteristics.**
  - Service `607B5C9B-3700-4E94-F44A-2DF900BCB0C3` or assigned `FCC9`.
  - Data `DAAD3D52-237C-90A7-B54B-8854A134D801`.
  - Control `C0EF558A-2058-FABF-A140-8D5ACDE50B39`.
  - System input `1D1F4039-23F5-33B2-C24E-704351F20585`.
  - Evidence:
    `HaversineUUID.java:9-13`; `LinkTransport.java:579-596`.
- [x] **Complete-object boundary.**
  - Collection buffer maximum in this implementation is `0xA0000`
    (655,360) bytes.
  - Evidence:
    transfer C object allocation and phase-1 bounds check;
    `analysis/ghidra_decompiled/libhaversine_protocol_helpers.c`.
- [x] **Decode boundary.**
  - `PPCollection_createFromBinaryData` copies and parses; timeline creation
    then handles `0x50`/`0x51`.
- [x] **App boundary.**
  - `RingSync.kt:220-223` removes DC bias after receiving `TransferComplete`.
  - `RingSync.kt:118,129-132,523-536` resamples to 16 kHz and writes LE shorts.

Caution:

- `removeDCBias` is packaged in Haversine, but it is invoked by the host app
  after `TransferComplete`; it is not part of collection decoding.

## Section 3: Codec analysis

### Required classification

- [x] `0x50`: uncompressed PCM, signed 16-bit interpretation, little-endian.
- [x] `0x51`: custom DD-Rice, bit-packed, second-order/double-delta
  reconstruction.
- [x] Not IMA ADPCM: no 4-bit nibbles, IMA step/index tables, or IMA predictor.
- [x] Not Speex/Opus/CELT/SILK: no decoder call/import or frame structure in the
  reachable timeline path.
- [x] Not application encrypted: bitstream enters `DDRiceDecompressionDecoder`
  directly and has no key/nonce/tag.

Strongest native evidence:

- `extracted/iosarm64-cinterop-PPCommon/static_objects/PPCollection.o`
  - `_PPCollection_createAudioTimeline` `0x3b4`.
  - Raw branch `0x450..0x484`.
  - Compressed branch `0x490..0x5a8`.
- `extracted/iossimulatorarm64-native-objects/ppcommon-arm64/DDRiceCompression.o`
  - `_DDRiceDecompressionChannel_init` `0x370`.
  - `_DDRiceDecompressionDecoder_init` `0x39c`.
  - `_DDRiceDecompressionDecoder_readBit` `0x3b8`.
  - `_DDRiceDecompressionDecoder_readBits` `0x414`.
  - `_DDRiceDecompressionChannel_decodeDiff` `0x47c`.
  - `_DDRiceDecompressionChannel_nextWord` `0x608`.
- `scripts/ddrice_native_harness.c` linked to the exact shipped ARM64 object.
- `scripts/decode_index_collection.py` exact-native vectors for configurations
  `0x30`, `0x40`, `0x51`, and `0x72`.

### Canonical decoder pseudocode

The final report should include code equivalent to the following. It preserves
the native decoder's actual bounded-unary edge behavior rather than describing
only a generic Rice code:

```text
s = config & 0x0f
L = config >> 4
M = 1 << (16 - s)
signThreshold = M >> 1

firstDifference = 0       # uint16 state, reset per audio record
sampleBase = 0            # uint16 state, reset per audio record
reader = MSB-first reader limited to compressedBitCount

while reader has declared bits:
    first = readBit()

    if first == 1:
        encoded = 0
    else:
        zeroCount = 1
        terminator = 0

        while zeroCount < L:
            zeroCount += 1
            terminator = readBit()
            if terminator == 1:
                break

        if terminator == 0:
            encoded = readBits(16 - s)       # modular literal escape
        else:
            magnitude = zeroCount - 1
            sign = readBit()
            encoded = magnitude if sign == 0 else M - magnitude

    signedSecondDifference =
        encoded if encoded < signThreshold else encoded - M

    firstDifference =
        uint16(firstDifference + signedSecondDifference)
    sampleBase =
        uint16(sampleBase + firstDifference)
    emit int16(uint16(sampleBase << s))
```

For normal `L >= 1` configurations, this is equivalently:

- `1` encodes zero;
- `m` zero bits, a `1`, and a sign bit encode signed magnitude
  `1 <= m < L`;
- `L` zero bits plus a `(16-s)`-bit modular literal encode the escape.

Edge caution:

- With `L == 0`, the native decoder still consumes one leading zero before the
  literal escape because `zeroCount` starts at one. Preserve the canonical
  pseudocode if implementing full compatibility.
- The **shipped encoder initializer** rejects configuration values above
  `0xef`. The **decompression path used by collection transfer does not
  perform that validation**; it mechanically accepts a high nibble of `0xf`.
  Do not state that `PPCollection` or the decoder rejects `0xF0..0xFF`.

### Quantization/losslessness

- [x] `s == 0`: the transform is reversible modulo 16 bits.
- [x] `s > 0`: output is quantized to multiples of `2^s`; exact native vectors
  demonstrate changed samples for shifts one and two.
- [x] No blanket “lossless” claim should be made for every config.

### Sample count and framing

- [x] Raw sample count is `(payloadLength - 4) / 2`.
- [x] Compressed sample count is not stored; one output is emitted per complete
  codeword until the explicit bit limit.
- [x] There is no fixed codec frame size, sync word, or per-frame header.
- [x] Predictor state resets for each compressed audio record; multipart
  collections are decoded individually and concatenated as PCM.

## Section 4: Frame/protocol structure

### Telesto request

Directly supported table:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 1 | operation type |
| 1 | 4 | address, `u32le` |
| 5 | 4 | offset, `u32le` |
| 9 | 4 | length, `u32le` |

Evidence:
`analysis/iossimulatorarm64-transfer-c-arm64-dwarf.txt:1268-1308`;
`TelestoRequest` byte size `0x0d`.

Operation types:

| Value | Meaning |
|---:|---|
| 0 | no operation |
| 1 | erase memory |
| 2 | program memory |
| 3 | read memory |
| 4 | cancel |
| 5 | erase and program |

Evidence:
same DWARF enum immediately before `TelestoRequest`;
`TELESTO_ERASE_AND_PROGRAM_MEMORY = 5`.

### Telesto response

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | error, `u32le` |
| 4 | 4 | info, `u32le` |
| 8 | 4 | following data length, `u32le` |

Evidence:
`analysis/iossimulatorarm64-TelestoController-arm64-dwarf.txt:2379-2411`;
byte size `0x0c`.

Caveat:

- The current client uses error and length for completion. The meaning of
  `info` is not established; do not invent one.

### Recording enumeration and reads

| Purpose | Address | Requested length | Returned interpretation |
|---|---:|---:|---|
| stored index range | `0x40030005` | 4 | `u16le rangeStart`, `u16le rangeEnd` |
| collection `i` | `0x40020000 \| uint16(i)` | 0 | whole virtual object; response supplies actual length |
| current advertisement | `0x4003000e` | 10 | used to detect collection-state/new-data changes |

Evidence:

- DWARF enum values in
  `analysis/iossimulatorarm64-transfer-c-arm64-dwarf.txt:270-407`.
- `_TransferOperation_startNextChild` `0x130..0x1d4`.
- `TelestoStoredCollectionIndexes` is four bytes with fields at offsets zero
  and two:
  `analysis/iossimulatorarm64-transfer-c-arm64-dwarf.txt:1458-1483`.

Range semantics:

- [x] The native state machine treats `rangeEnd` as exclusive.
- [x] Incrementing a `uint16_t` naturally wraps.
- [x] Collection index is object ordering/identity, not a per-chunk sequence
  field.
- [x] The `contains` helper has a `0x200` sanity guard. Avoid presenting this as
  a wire-format maximum without noting it is an implementation assertion and
  its comparison order has an off-by-one edge.

### Collection envelope

| Form | Header | First TLV | Exact check |
|---|---|---:|---|
| normal | `u24be bodyLength` | 3 | `bodyLength == inputLength - 3` |
| records transfer | `ff` + `u16le bodyLength` | 3 | `bodyLength == inputLength - 3` |
| legacy/alternate total | `u32le totalLength`, selected when byte 3 is zero | 4 | `totalLength == inputLength` |

Evidence:

- `PPParsing.o::_GSParseRecordsInRawData`.
- Device ARM64 header logic `0x48..0xe4`; TLV loop `0x1a0..0x424`.
- Simulator x86_64 equivalents `0x29..0xc5`, `0x24e..0x505`.
- `analysis/collection_framing.md`, “Outer collection envelope.”

Required caveats:

- No envelope version, terminator, record count, CRC, or multi-byte magic.
- `0xff` is an outer marker (`RECORDS_DATA_TRANSFER`), not a valid inner TLV.
- The “byte 3 is zero” byte is the high byte of the LE32 total length, not a
  terminator.
- All three forms are accepted; which form current firmware emits is unknown.

### Inner TLV grammar

```text
ordinary:
    u8 type
    u16le payloadLength
    u8 payload[payloadLength]

audio 0x50/0x51:
    u8 type
    u32le payloadLength
    u8 payload[payloadLength]
```

Additional behavior:

- Duplicate types are accepted; the parser slot retains the last instance.
- Timeline creation checks uncompressed `0x50` first, so it wins if both audio
  types are present.
- The native parser verifies the exact outer length and record type but does
  not precheck inner length-field availability or reject a final TLV overshoot.
- A safe independent parser should enforce per-TLV bounds and exact final
  termination, even though this is stricter than native code.

### Audio `0x50`

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 1 | type `0x50` |
| 1 | 4 | payload length, `u32le` |
| 5 | 4 | sample rate Hz, `u32le` |
| 9 | variable | signed PCM16LE sample bytes |

Evidence:
`_PPCollection_createAudioTimeline` `0x450..0x484`.

### Audio `0x51`

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 1 | type `0x51` |
| 1 | 4 | payload length, `u32le` |
| 5 | 1 | DD-Rice config |
| 6 | 4 | compressed bit count, `u32le` |
| 10 | 4 | sample rate Hz, `u32le` |
| 14 | variable | MSB-first compressed bitstream |

Evidence:
`_PPCollection_createAudioTimeline` `0x490..0x5a8`;
`_DDRiceDecompressionDecoder_readBit` `0x3b8..0x410`.

Caution:

- The generic collection parser does not enforce the nine-byte minimum or
  bit-count bound. Timeline creation contains an assertion/precondition for
  `compressedBitCount <= (payloadLength - 9) * 8`. Describe the correct actor
  and do not imply graceful authenticated integrity checking.

### Multipart `0x52`

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 1 | type `0x52` |
| 1 | 2 | payload length, nominally 6, `u16le` |
| 3 | 4 | multipart group start index, `u32le` |
| 7 | 1 | `isMultiPart` (`!= 0` means true) |
| 8 | 1 | `isFinalPart` (`!= 0` means true) |

Evidence:
`analysis/collection_framing.md`, including architecture parity at
`PPCollection` ARM64 `0x3f4..0x418`.

Semantics to state:

- `startIndex` is the repeated group origin, not the current part index.
- Current index comes from the transfer layer.
- No total part count exists.
- Final flag does not prove all intervening parts arrived.
- Samples are concatenated in processing order; the set check does not reorder.
- A noncontiguous final group is still emitted with `isContiguous = false`.

### Other adjacent metadata

- `0x53`: nominal eight-byte payload:
  `u32le sequence`, `u32le count`; bits are interpreted LSB-first,
  `1 = "long"`, `0 = "short"`.
- `0x54`: nominal four-byte payload, `u32le lifetimeCollectionCount`.
- Audio records do not contain a timestamp. `PPCollection_unixTime` obtains
  timing from separate collection metadata (`SWING_UTC`, type `0x02`); timing
  is not needed to decode audio.
- The `0x53` field named `sequence` is a button-gesture sequence, not a
  transport integrity sequence number.

### BLE/Telesto fragmentation

- [x] Subscribe to notifications on Telesto control and data.
- [x] Write the 13-byte request directly to control.
- [x] Accumulate exactly 12 control bytes.
- [x] Stream/cap data against response length.
- [x] Incoming notification bytes are forwarded unchanged.
- [x] There is no Haversine header around each GATT notification.
- [x] iOS fragments outgoing data at CoreBluetooth's maximum write length.
- [x] Android's corroborating adapter uses 20-byte outgoing slices.

Do not call any notification a codec frame.

## Focused integrity audit

### Present mechanisms

| Mechanism | Scope | Evidence and limitation |
|---|---|---|
| Telesto error | operation | Nonzero error fails the operation; not a checksum. |
| Telesto response length | whole response data | Controller waits for the declared byte count and caps excess. |
| Exact outer collection length | whole collection | Detects simple truncation/extension before parsing. |
| TLV payload lengths | record stepping | Native bounds enforcement is incomplete; safe client must add it. |
| compressed bit count | compressed audio | Bounds the MSB-first reader; does not authenticate bits. |
| collection index/range | object ordering | Detects/organizes objects, not arbitrary GATT chunks. |
| multipart contiguity | logical recording | Detects gaps after assembly but still emits noncontiguous output. |
| multipart sample-rate equality | logical recording | Prevents silently combining different rates. |
| CoreBluetooth write confirmation | GATT pacing/error | Lower transport confirmation, not a Haversine audio ACK. |

### Absent mechanisms

- [x] No application CRC.
- [x] No application checksum.
- [x] No cryptographic hash/MAC/tag.
- [x] No FEC.
- [x] No Telesto transaction or per-chunk sequence number.
- [x] No per-chunk/per-frame application acknowledgement.
- [x] No collection-consumed acknowledgement.
- [x] No application retransmission loop.
- [x] No safe recording delete command identified in the official path.

Important distinctions:

- The 12-byte Telesto response is an operation-level response/status and can be
  called an operation acknowledgement only with that qualification.
- GATT `.withResponse` packets inserted by the iOS sender are pacing/transport
  confirmations.
- BLE Link Layer CRC, acknowledgements, retransmission, and encryption are
  below the application layer and explicitly outside the requested payload
  analysis.
- Transfer failure reports remaining collection failures and completes; it does
  not retry the failed read.
- `HaversineTransferDelegate.handleDidFinish` advances the app-provided
  inclusive last-success index before parsing. Corrupt-but-completely-received
  bytes become `IrrecoverableDataDetected` and are not automatically reread.
  Evidence: exact IR `975..1247`, especially `979` before construction.

## Section 5: Cryptography analysis

The final report needs this three-layer table:

| Layer | Answer | Proof / limitation |
|---|---|---|
| BLE link encryption | platform controlled; actual session/mode unknown | Android explicitly invokes `createBond`; iOS relies on CoreBluetooth/connection-triggered pairing. Firmware permissions or an HCI trace are needed for exact SMP mode and whether a given session is encrypted. |
| Haversine application-layer recording encryption | **No** | Complete transfer path feeds Telesto bytes directly to collection parsing and DD-Rice/PCM decoding. No key, nonce, IV, tag, or decrypt input/call exists. |
| Haversine-managed storage encryption | **No** | No Haversine key/cipher or registration secret exists. |
| Firmware/hardware transparent physical flash encryption | **Unknown** | It could exist below the virtual-address interface and be invisible to the client. |

Positive proof is more important than name searches:

```text
Telesto data bytes
  -> complete collection callback
  -> PPCollection_createFromBinaryData
  -> GSParseRecordsInRawData
  -> PPCollection_createAudioTimeline
  -> raw memcpy or DDRice decode
```

No intermediate function accepts a ring identity, key, UID, cached state,
registration token, nonce, or tag.

Negative inventory is corroborating evidence:

- no reachable AES/CCM/GCM/CTR/CBC/XTS;
- no ChaCha/Salsa/Poly1305;
- no HKDF/HMAC/SHA-256;
- no Curve25519/X25519/P-256/ECDH;
- no CommonCrypto/CryptoKit/`SecKey`/`SecItem` path;
- no Java crypto/Android Keystore path;
- no crypto native dependency.

Caution:

- A generic Security framework linker option and an unrelated debug upload
  `apiKey` are not recording encryption evidence.

## Section 6: Key-management analysis

All nine explicit shared-secret questions are covered:

| Question | Required answer | Strongest evidence |
|---|---|---|
| Application secret generated during registration? | No; fingerprint + timestamp only. | Exact KLIB IR `7889..8045`; `PPRingApplicationData.o`. |
| Secret received from ring? | No; programming ends in ordinary Telesto status and ignores data. | `ProgramApplicationDataOperation_init`; response/callback path in `analysis/pairing_crypto_audit.md`. |
| Public/private exchange? | None. | Complete registration path and absent exchange/random/key APIs. |
| Persistent Haversine key? | None. | iOS/Android cache field inventory. |
| Where stored/indexed? | Not applicable. Ordinary state is keyed by CoreBluetooth UUID on iOS or normalized MAC on Android. | `HaversineEnvironment.o` and Android cache classes. |
| Does decode reference it? | No. | Keyless `PPCollection`/timeline/DD-Rice call signatures. |
| Does clearing pairing invalidate old bytes? | No for already captured collection bytes. It may block future BLE access until re-pairing. | Self-contained decoder path. |
| Does registration exchange it? | No. It writes a public 141-byte identity record. | Serialized layout below. |
| Is BLE bonding the only persistent cryptographic relationship? | It is the only one evidenced in these artifacts; exact bond/link properties remain OS/firmware territory. | Android pairing source; iOS CoreBluetooth path; no app key storage. |

Exact version-1 registration record:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | version `1`, `u32le` |
| 4 | 4 | noncryptographic UID fingerprint, `u32le` |
| 8 | 4 | Unix timestamp, `u32le` |
| 12 | 129 | UID bytes, NUL-terminated/zero-padded |

Total serialized size: 141 bytes. Telesto prepends a `u32le` total size,
producing a 145-byte program object. It is sent using operation type `5` to
`0x40000000`.

Strong object/function evidence:

- Device `PPRingApplicationData.o`:
  - `_mixBits32` `0x000`
  - `__fingerprint` `0x064`
  - `_PPRingApplicationData_fingerprintMatchesUserId` `0x160`
  - `_PPRingApplicationData_init` `0x1bc`
  - `_PPRingUser_init` `0x240`
  - `__serialize_v1` `0x250`
  - `_PPRingApplicationData_serializedSize` `0x38c`
  - `_PPRingApplicationData_serialize` `0x394`
- Android linked native corroboration:
  `ProgramApplicationDataOperation_init` VA `0xd180`;
  `TelestoLengthPrefixedData_create` VA `0x18820`.

Persistence:

- iOS:
  `NSUserDefaults`, key `HaversineSatelliteState_<UUID>`, JSON-encoded data.
  `HaversineEnvironment.o`: prefix getter `0x0a70`,
  `fetchCachedState` `0x0aa0`, `cacheState` `0x0ca0`.
- Android:
  SharedPreferences file `com.wtlp.haversinecache`, normalized MAC key, Base64
  Java serialization.
- Fields:
  identity/name/version/config/application data/fingerprint/last index; no
  recording key.

Observed `00` write:

- `DAAD...` is Telesto's generic data channel.
- One byte is not the recovered 145-byte Haversine registration object.
- It may prompt OS pairing/protected-characteristic access, but exact intent
  requires a synchronized BLE/HCI capture.
- Do not call it a secret, challenge, or complete Haversine registration.

## Section 7: Relevant symbols/functions

### Exact chain to `TransferComplete`

The final report should list the wrapper layer explicitly:

```text
Swift HaversineTransferCollectionsOperation completion closure
  [Swift object symbol ...cfU1_, starts 0x394;
   objc collectionTransferDidFinish... call at 0x4c4]
-> IOSHaversineTransferDelegate.collectionTransferDidFinishWith
  [exact IR 5176..5196]
-> HaversineTransferDelegate.collectionTransferDidFinish
  [IR 774..787]
-> event channel / processEvents
-> HaversineTransferDelegate.handleDidFinish
  [IR 975..1247]
-> PPCollection(index, ByteArray)
  [IR 8391..8675]
-> PPCollection_createFromBinaryData
  [native PPCollection.o 0x0c]
-> GSParseRecordsInRawData
  [native PPParsing.o 0x0]
-> cinterop PPCollectionSimple_createAudioTimeline
  [IR call 8612; cstubs-defined wrapper]
-> native PPCollection_createAudioTimeline
  [PPCollection.o 0x3b4]
-> raw memcpy OR DDRice decode
-> native PPResultAudioTimeline_t
-> PPAudioTimeline copies sampleCount * 2 into ShortArray
  [IR 8276..8390, memcpy at 8379]
-> processSinglePartAudio OR processMultiPartAudio
  [IR 1248..1370]
-> MultipartCollection.addPart / flushBuffer
-> emitCompleteTransfer
  [IR 1371..1435]
-> TransferStatus.TransferComplete constructor
  [IR 1409..1428]
```

Do not omit `PPCollectionSimple_createAudioTimeline`: the Kotlin IR calls this
cinterop convenience wrapper, whose bitcode imports/calls the native
`PPCollection_createAudioTimeline`.

### Native transfer and protocol symbols

- `_HaversineTransferCollectionsOperation_init` `0x000`
- `__TransferOperation_start` `0x078`
- `__TransferOperation_startNextChild` `0x130`
- `__TransferOperation_handleReceivedDataFromChild` `0x244`
- `__TransferOperation_handleCompletionFromChild` `0x310`
- `_TelestoController_receiveCtrlBytes` `0x56c`
- `_TelestoController_receiveDataBytes` `0x628`
- `_TelestoController_init` `0x7f8`

### PPCommon symbols

- `_GSParseRecordsInRawData` `0x000`
- `_PPCollection_createFromBinaryData` `0x00c`
- `_PPCollection_createAudioTimeline` `0x3b4`
- `_PPCollection_freeAudioTimeline` `0x5ac`
- `_DDRiceDecompressionDecoder_readBit` `0x3b8`
- `_DDRiceDecompressionChannel_decodeDiff` `0x47c`
- `_DDRiceDecompressionChannel_nextWord` `0x608`

### Native result ABI

`PPResultAudioTimeline_t`, 32 bytes on ARM64:

| Offset | Field | Type |
|---:|---|---|
| 0 | collection start index | `uint32_t` |
| 4 | sample rate Hz | `uint32_t` |
| 8 | sample count | `size_t` |
| 16 | sample pointer | `uint16_t *` |
| 24 | multipart flag | `bool` |
| 25 | final-part flag | `bool` |

Caution:

- iOS `PPAudioTimeline` performs a native `memcpy`, not an explicit byte-order
  conversion. Because all target architectures are little-endian and the native
  record loads/copies are little-endian, the resulting bit patterns are correct.
  The Android wrapper independently uses an explicitly little-endian
  `ByteBuffer`.

## Section 8: Evidence

### Artifact provenance

The report should identify the exact target artifacts:

- physical iOS ARM64 KLIB:
  SHA-256
  `4f14675b857cff246dbc8ad607c3003972cc04506823e5ab40a42055eb7ec576`
- simulator ARM64 KLIB:
  SHA-256
  `9ba0534f81762d59c2e73b24f053933836fe10cbdf7497d578f8e950f53e46a7`

Companion KLIBs:

- device PPCommon:
  `d77e25abb94f8a199dab7857cb8250d0022460e0319a843fc8805c46244d2732`
- device satellite:
  `d515f1a62ad2ed7479fa964cbeb2f63e68443d4309d83c87fed4ba8f9ab1dc21`
- simulator PPCommon:
  `d6ada452614b9c178206f3ca81ed9c70499dc021b70fd21af15dd11442aa117b`
- simulator satellite:
  `98cf6bad80999aa22bc58597b43bf5400ce7e0a486481199b8a757f0f54555bf`

Evidence files:
`analysis/artifact_sha256.txt`,
`analysis/device_inventory.md`,
`analysis/sim_inventory.md`,
`analysis/pairing_crypto_audit.md`.

### Archive structure

- Both main KLIBs are ZIPs with 50 entries / 40 regular files.
- They carry serialized Kotlin IR and link metadata, not the native codec.
- Their manifests name the PPCommon and satellite cinterop KLIBs.
- Device PPCommon contains eight ARM64 objects; satellite contains 37.
- Simulator companions contain matching universal ARM64/x86_64 archives.
- The exact Kotlin/Native 2.2.20 IR dumps are byte-identical, SHA-256:
  `0217f3549e3c5d54b79c2b8092a687f4cd22106d6f029b4ba62e66722ab8f300`.
- The published sources JAR is empty except for its manifest.

### Architecture parity

- Collection parser behavior is independently matched between device ARM64 and
  simulator x86_64, including type dispatch and length widths.
- The main wrapper IR is identical across device and simulator.
- Android is corroboration, not the sole proof for target-iOS conclusions.
- Major codec claims should cite the iOS native objects and exact IR first, then
  Android/Ghidra as a readability cross-check.

### Executable validation

Current checks pass:

```text
python3 scripts/decode_index_collection.py --self-test
PASS: 4 exact-native vectors

python3 scripts/test_decode_index_collection.py
Ran 4 tests ... OK
```

The test suite covers:

- all three outer envelopes;
- uncompressed PCM;
- multipart/button/lifetime metadata;
- malformed record overrun rejection;
- four exact native compressed vectors, including nonzero shifts.

## Section 9: Remaining unknowns

Every unresolved item should name the artifact that would resolve it:

| Unknown | Why client binaries cannot answer | Resolving evidence |
|---|---|---|
| Real recording's numeric source rate | It is a dynamic `u32le` record field. | One captured complete collection. |
| Whether production emits `0x50` or `0x51` | Decoder supports both; no emitter/firmware is present. | One captured collection or ring firmware. |
| Normal DD-Rice config/compression ratio | Config is dynamic. | Captured compressed collection. |
| Normal outer-envelope variant | Parser accepts all three. | Captured collection. |
| Physical ring flash representation | Client sees only the virtual read result. | Firmware, raw flash, or firmware+flash comparison. |
| Transparent physical flash encryption | Could be below Telesto and invisible. | Firmware/hardware analysis and raw flash comparison. |
| Exact BLE SMP association/security mode | CoreBluetooth abstracts it. | Firmware GATT permissions and HCI/SMP trace. |
| Exact meaning of observed one-byte `00` write | It is not the complete recovered registration object. | Timestamped full GATT/HCI trace from that app build. |
| Safe recording acknowledgement/deletion command | Official path only reads and updates local state. | Firmware, vendor protocol source, or a controlled device experiment backed by flash/index observations. |
| Meaning of Telesto response `info` | Current client does not establish it. | Firmware/protocol source or varied controlled responses. |

Do not list “Haversine source” as necessary for the already recovered wire
format; it would be useful corroboration, but the relevant behavior is already
implemented and tested independently.

## Section 10: Independent-client implications

### 1. Discover an Index

Status: **understood enough to implement**.

- Scan for either advertised service UUID:
  `FCC9` or `607B5C9B-3700-4E94-F44A-2DF900BCB0C3`.
- Android corroboration uses both scan filters and reads the single manufacturer
  data item.
- Exact manufacturer-data decoding is not required merely to connect and read,
  though it is useful for state/fingerprint filtering.

Evidence:
`CentralManager.java:253-263`;
`HaversineUUID.java:9-13`.

### 2. Connect and establish channels

Status: **understood**.

- Discover the Haversine service.
- Discover data, control, and system-input characteristics.
- Subscribe to control and data notifications.
- Forward incoming bytes unchanged to the corresponding accumulator.

Evidence:
`LinkTransport.java:565-623,657-675`;
`CBConnectedPeripheralAdaptor.o`.

### 3. Authenticate/pair/register

Status: **application registration understood; BLE security details partially
unknown**.

- Let CoreBluetooth trigger/manage any required OS pairing by accessing the
  protected service/characteristic.
- If registration is required, construct the 141-byte version-1 UID record,
  prepend the four-byte total length, and issue erase-and-program type `5` to
  `0x40000000`.
- There is no application secret exchange.
- Exact SMP mode, MITM requirement, and characteristic permissions require a
  device/trace.

Safety:

- Do not model the isolated one-byte `00` write as the full registration flow.

### 4. Enumerate recordings

Status: **understood**.

- READ address `0x40030005`, offset zero, length four.
- Parse two `u16le` values as a half-open stored range.
- Iterate in `uint16_t` modular order from start until end, with a defensive
  bound.
- Maintain resume state separately from ring data.

Caution:

- The exact Kotlin wrapper converts the native range to an ordinary `IntRange`,
  which is not a model to copy for a wrapped `start > end` range. An independent
  implementation should preserve modular `uint16_t` semantics.

### 5. Download a recording

Status: **understood**.

- Issue a Telesto READ type `3` to
  `0x40020000 | uint16(collectionIndex)`, offset zero, length zero.
- Accumulate a 12-byte response and exactly its declared data length.
- Enforce a configurable size ceiling; Haversine's ceiling is `0xA0000`.
- Validate the complete collection before committing progress.

### 6. Decode to PCM

Status: **implemented and tested**.

- Parse any of the three envelope forms.
- Parse ordinary/audio TLV length widths safely.
- Select last `0x50` if present, otherwise last `0x51`.
- Decode using the canonical algorithm above.
- For multipart, require a common sample rate, preserve modular index
  progression, concatenate decoded PCM in index order, and retain a
  noncontiguous/error status if a gap exists.
- Output mono signed PCM16; serialize little-endian or wrap as WAV.

Reference implementation:
`scripts/decode_index_collection.py`.

### 7. Acknowledge/delete safely

Status: **not understood; must remain outstanding**.

- The official Haversine transfer state machine sends recording READs only.
- It keeps local resume indexes and relies on the ring's bounded/wrapping range.
- Generic Telesto ERASE exists, but no evidence establishes that erasing a
  collection virtual address is a supported or safe recording-delete command.
- Do not issue speculative ERASE requests to collection addresses.

Recommended independent-client commit policy:

1. receive the full object;
2. validate envelope/TLV bounds;
3. decode all audio;
4. validate multipart continuity and sample-rate agreement;
5. durably write/commit the decoded result;
6. only then advance the local last-processed index.

This is deliberately more robust than the observed Haversine ordering, which
advances `CollectionIndexStorage` before parsing.

## Contradictions, stale notes, and unsupported-claim traps

1. **DD-Rice config validation**
   - The initial audit found that `analysis/device_inventory.md` described the
     configuration byte as generally limited to `0xef`; that note has now been
     corrected to distinguish encoder and decoder.
   - That check is in `_DDRiceCompressionChannel_init`, the encoder initializer.
     The collection decode path calls `_DDRiceDecompressionChannel_init`, which
     does not validate it.
   - `scripts/decode_index_collection.py` now accepts high nibble `0xf`, and a
     decoder-only regression covers config `0xf0`.
   - Final report wording: encoder-valid emitted configs are `<= 0xef`;
     native decoder mechanically accepts all byte values.

2. **Wrong actor for compressed-bit validation**
   - The initial audit found `analysis/sim_inventory.md` saying “The parser
     enforces” the bit-count bound; that note has now been corrected.
   - `GSParseRecordsInRawData` does not; the check/assertion is in
     `PPCollection_createAudioTimeline`.
   - Final report must distinguish generic framing parser from downstream audio
     decoding.

3. **Native parser is not a safe bounds validator**
   - Outer length/type checks are direct.
   - It accepts a final TLV whose claimed end overshoots the outer end and may
     read a short length field without a precheck.
   - Do not say all TLV lengths are validated. The Python decoder intentionally
     adds stricter checks.

4. **At-rest wording**
   - “No application-layer encryption” is direct.
   - “No Haversine-managed at-rest encryption” is direct.
   - “The physical recording is plaintext in flash” is unsupported.
   - The correct physical at-rest answer is unknown.

5. **Normal codec/sample rate**
   - Both `0x50` and `0x51` are supported.
   - No artifact proves which current firmware normally emits.
   - No artifact proves 16 kHz, or any other numeric source rate.

6. **`0xff` classification**
   - It is an outer records-transfer marker.
   - It is invalid as an inner TLV.
   - Avoid tables that place it alongside `0x50..0x54` without stating that
     scope difference.

7. **“Two envelope variants” script docstring**
   - `parse_records` says “two collection-envelope variants,” but implements
     three forms.
   - The completed framing report correctly documents all three.

8. **Exact timeline wrapper**
   - Exact iOS IR calls `PPCollectionSimple_createAudioTimeline`, a generated
     cinterop wrapper that invokes/imports native
     `PPCollection_createAudioTimeline`.
   - A shortened call chain that names only the native routine is directionally
     correct but should include the wrapper in the detailed symbols section.

9. **Byte-order wording at the Kotlin copy**
   - iOS performs `memcpy`, not an explicit little-endian conversion.
   - Little-endian wire interpretation is established by the target
     architectures/native loads and independently by Android's explicit
     little-endian `ByteBuffer`.

10. **Acknowledgement terminology**
    - Telesto supplies an operation-level response.
    - CoreBluetooth may supply a write confirmation for pacing.
    - There is no per-audio-chunk ACK, post-decode consumption ACK, or
      recording delete ACK.

11. **Deletion**
    - Generic Telesto operation `1` means erase, and application-data erasure at
      `0x40000000` is known.
    - No evidence maps it to safe collection deletion.
    - Never infer a delete address/length from the collection READ address.

12. **BLE bonding wording**
    - Android public code explicitly calls `createBond`.
    - iOS exact/client behavior relies on CoreBluetooth and connection-triggered
      pairing, but the exact SMP mode and whether a particular session is
      encrypted are not proven by Haversine.
    - “Only evidenced persistent cryptographic relationship” is supportable;
      “exactly this BLE cipher/mode is always active” is not.

13. **Progress-log status**
    - Early device inventory and `PROGRESS.md` passages say crypto and transfer
      work remains in progress.
    - Later completed reports supersede them. These are chronology, not an
      unresolved technical contradiction.

14. **Data-excess behavior**
    - Oversized control input is treated as controller error.
    - Excess data input is capped/truncated with a warning.
    - Avoid merging these into one generic “rejects excess” statement.

15. **Multipart finality**
    - `isFinalPart` triggers emission.
    - It is not proof of completeness; a gap is merely reported through
      `isContiguous = false`, and samples are still emitted.

16. **Collection progress semantics**
    - Native transfer result stores the exclusive next/end index.
    - App `CollectionIndexStorage` stores the inclusive last successfully
      received index.
    - Keep these two local progress values distinct in the independent-client
      discussion.

## Final report release gate

Before declaring the final report complete, verify:

- [x] All ten requested section headings are present.
- [x] Executive at-rest answer says `unknown` for physical flash.
- [x] Executive answer says both `0x50` and `0x51`, not a guessed default.
- [x] Numeric source sample rate is explicitly `unknown/dynamic`.
- [x] Exact decoder pseudocode includes codeword parsing and two integrations.
- [x] Decoder/encoder configuration validation distinction is correct.
- [x] All protocol layers are separated: GATT fragment, Telesto response/data,
  collection envelope, TLV, audio bitstream.
- [x] Integrity section separates operation response and BLE transport
  confirmation from recording/chunk acknowledgement.
- [x] Native parser validation gaps are disclosed.
- [x] Shared-secret hypothesis is answered question by question.
- [x] Observed one-byte `00` write is not misidentified.
- [x] `TransferComplete` chain includes the cinterop simple wrapper and exact
  IR/native evidence.
- [x] Independent-client section refuses speculative collection erase/delete.
- [x] Remaining unknowns name concrete resolving artifacts.
- [x] Device and simulator parity and exact hashes are cited.
- [x] Standalone decoder tests are rerun and their result reported.
