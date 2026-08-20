# Haversine / Pebble Index 01 Recording Format — Reverse-Engineering Report

Artifacts analyzed:

| Artifact | Contents |
|---|---|
| `haversine-iosarm64-03202f5.klib` | Kotlin IR only (common + iOS expect/actual), no native objects |
| `haversine-iossimulatorarm64-03202f5.klib` | Same Kotlin IR; identical class/function structure to iosarm64 |
| `haversine-android-03202f5.aar` (+ `-debug`) | classes.jar (JVM bytecode of the *same* common Kotlin code) + native `libhaversinesatellitelibrary.so`, `libppcommon.so` (arm64-v8a et al.) |

The two iOS klibs contain **Kotlin IR only** (no LLVM bitcode/objects). The Android AARs ship the *same*
shared C sources compiled natively (`libppcommon.so` = ring-data parser/codec, `libhaversinesatellitelibrary.so`
= BLE transport), with source paths (`.../haversine/PPCommon-Ring/PPCommon/...`,
`.../haversine/HaversineSatelliteLibrary/Sources/Shared/*.c`) proving they are the shared implementation used
by all targets including iOS. The **android-debug** `.so` files are compiled `-O0` and were disassembled
function-by-function (ARM64) to reconstruct the algorithms below. Conclusions were spot-verified against the
optimized release `.so` (identical logic).

---

## 1. Executive answer

- **What the Index stores/transmits:** each recording ("collection") is a self-contained binary blob — a
  length header followed by a sequence of typed length-prefixed **records**. Audio is stored as either a
  `COMPRESSED_16BIT_AUDIO` record (type 81) containing a **custom "DD-Rice" bitstream — double-delta
  (2× integrated) prediction + Rice/Golomb-style entropy coding of the residuals** — or an
  `UNCOMPRESSED_16BIT_AUDIO` record (type 80) of raw little-endian PCM16. The sample rate travels **inside
  the audio record** as a u32 (value chosen by ring firmware; not fixed by the library).
- **What Haversine receives:** the whole collection blob is downloaded as the response to a single Telesto
  `READ_MEMORY` request against the virtual address `0x40020000 | collectionIndex`, streamed over the
  `telestoData` BLE characteristic in ≤20-byte chunks (BLE notifications), with a 12-byte Telesto response
  frame on the `telestoCtrl` characteristic bounding/acknowledging it.
- **What Haversine outputs:** `PPCollection.createFromBinaryData()` → `PPCollection_createAudioTimeline()`
  decodes the DD-Rice bitstream into **signed 16-bit mono samples** (`ShortArray`, LE), reassembles
  multi-part collections (`COLLECTION_MULTI_PART_INFO` records) via `MultipartCollection`, and emits
  `TransferStatus.TransferComplete(samples, sampleRate, …)` to the app.
- **Encryption at rest: no evidence of any.** The stored/transferred bytes are parsed and decoded by pure,
  keyless algorithms (length checks + entropy decoding). No crypto primitives exist anywhere in either
  native library (no AES/ChaCha/SHA/HMAC/ECDH imports, strings, constants, or call paths).
- **Application-layer encryption in transit: no.** Only standard BLE link encryption (handled by
  CoreBluetooth/BLE stack) protects the transfer.
- **Registration-derived shared secret: does not exist.** Registration ("programming") writes a
  **non-secret** 141-byte `PPRingApplicationData` blob (version, user-ID string, timestamp, and a *weak
  non-cryptographic fingerprint hash* of the user ID) to the ring's application-data store. No key is
  generated, exchanged, or stored. Decoding recordings requires **no** per-ring secret.

## 2. End-to-end data path

```
microphone
  -> [ring firmware: 16-bit PCM, sample rate chosen by firmware (u32 in record), value unknown from these binaries]
  -> DD-Rice compression (double-delta + Rice coding) on ring        [inferred: encoder is the mirror of the shipped decoder]
  -> stored in flash as a "collection":
       [container header][TLV records: MULTI_PART_INFO?, BUTTON_PRESS_SEQUENCE?, PLATFORM_VERSIONS?,
        DEVICE_ID?, LIFETIME_COLLECTION_COUNT?, COMPRESSED_16BIT_AUDIO (or UNCOMPRESSED_16BIT_AUDIO)]
  -> Telesto READ_MEMORY(0x40020000 | collectionIndex)
       ctrl channel (C0EF558A-…): 13-byte request {type=3, address u32le, offset u32le, length u32le}
       data channel (DAAD3D52-…): response payload, notifications, ≤20 bytes/write, u32le length framing when >MTU
  -> HaversineLinkController / TelestoController reassembly (length accounting, 640 KiB cap per collection)
  -> HaversineTransferCollectionsOperation: collectionTransferDidFinish(data: ByteArray, collectionIndex)
  -> Kotlin HaversineTransferDelegate.handleDidFinish
  -> PPCollection.createFromBinaryData (libppcommon: GSParseRecordsInRawData)
  -> PPCollection.createAudioTimeline (libppcommon: DDRice decode -> u16 samples)
  -> PPAudioTimeline (LE PCM16 ShortArray + sampleRateHz UInt)
  -> MultipartCollection (multi-part buffering, writeShortLe) -> emitCompleteTransfer
  -> TransferStatus.TransferComplete(samples: ShortArray, sampleRate: Long, …)
  -> Pebble app: DC-bias removal -> resample sampleRate -> 16 kHz -> LE bytes -> mono PCM16
```

No encryption step exists anywhere in this pipeline.

## 3. Codec analysis — "DD-Rice" (delta-delta Rice) custom codec

**Evidence (all from `libppcommon.so`, android-debug arm64-v8a, disassembly in `disasm/`):**

- `PPCollection_createAudioTimeline` (0x2f964): if an `UNCOMPRESSED_16BIT_AUDIO` record exists use it
  (payload = `[sampleRateHz u32le][PCM16LE…]`); else if a `COMPRESSED_16BIT_AUDIO` record exists, run the
  DDRice decoder; else error 7 ("Incomplete raw data").
- Decoder entry points: `DDRiceDecompressionDecoder_init` (0x309e8), `DDRiceDecompressionChannel_init`
  (0x30930), `DDRiceDecompressionChannel_decodeDiff` (0x30bcc), `DDRiceDecompressionChannel_nextWord`
  (0x30f9c), `DDRiceDecompressionDecoder_readBit/readBits` (0x30a48/0x30b18).
- Symbols/strings: `DDRiceCompressionChannel_encodeWord`, `DDRiceDecompressionChannel_decodeDiff`,
  `DDRiceCompressionEncoder_appendBits`, `DDRiceDecompressionDecoder_noBit`, etc.
  (`nm -D libppcommon.so`, `strings`).

**COMPRESSED_16BIT_AUDIO record wire format** (record = `[type=81:1][payloadLen:4 LE][payload]`):

| Payload offset | Size | Meaning |
|---:|---:|---|
| +0 | 1 | config byte: high nibble = `limit` (unary escape threshold, 0–15); low nibble = `m` (scale shift, 0–15) |
| +1 | 4 | `bitCount` u32 LE — total number of bits in the bitstream |
| +5 | 4 | `sampleRateHz` u32 LE |
| +9 | ⌈bitCount/8⌉ | Rice bitstream, **MSB-first** bit order within each byte |

(Decoder asserts `bitCount ≤ (payloadLen−9)·8`.)

**UNCOMPRESSED_16BIT_AUDIO record** (type 80, also 4-byte length field):

| Payload offset | Size | Meaning |
|---:|---:|---|
| +0 | 4 | `sampleRateHz` u32 LE |
| +4 | 2·N | PCM samples, signed 16-bit, **little-endian**, mono |

**COLLECTION_MULTI_PART_INFO record** (type 82, 2-byte length field):

| Payload offset | Size | Meaning |
|---:|---:|---|
| +0 | 4 | `collectionStartIndex` u32 LE (index of first collection of a multi-part recording) |
| +4 | 1 | `isMultiPart` flag (≠0) |
| +5 | 1 | `isFinalPart` flag (≠0) |

**Decoding algorithm (reconstructed, sufficient to reimplement):**

```
state: A = 0, B = 0            # two u16 integrators ("double delta")
decoder(data, bitCount)        # bit cursor, MSB-first; reading past bitCount -> "no bit"

repeat:
    # --- decode one residual diff ---
    bit = readBit()
    if bit == NO_BIT: break                      # normal end of stream (DDRice error 3)
    if bit == 1:
        diff = 0                                  # shortcut for zero residual
    else:
        n = 1
        loop:
            if n >= limit:                        # escape: raw bits follow
                v = readBits(16 - m); break
            n += 1
            b = readBit()
            if b == 1:                            # unary terminator
                v = n - 1
                s = readBit()                     # sign bit
                if s == 1: v = (65536 >> m) - v   # two's-complement-style negation in the 2^(16-m) window
                break
        diff = v
    # --- zigzag-style map to signed in window 2^(16-m) ---
    if diff >= (32768 >> m): diff -= (65536 >> m)

    # --- reconstruct sample (double integration) ---
    B = (B + diff) & 0xFFFF
    A = (A + B)   & 0xFFFF
    sample[i++] = (A << m) & 0xFFFF               # stored as u16, read as s16 LE
```

Notes:
- Because the predictor is a **double integrator starting at 0**, the decoded signal can carry a large DC
  ramp/offset — exactly why the app performs DC-bias removal before resampling.
- The channel object also keeps 14 statistics buckets (`histogram[clamp(diff+7,0,14)]++`, counters at
  channel+0x18..0x77) — telemetry only, not needed for decoding.
- `sampleCount` in the result = number of samples actually decoded when bits ran out (not a header field).
- This is **not** IMA/OKI ADPCM, Speex, Opus, or any standard codec: no step-size tables, no LPC, no
  overlap-add — just unary/Rice codes over double-deltas with a configurable escape.

## 4. Frame / protocol structure

### 4.1 Collection container (the "stored recording" and the READ_MEMORY response body)

`GSParseRecordsInRawData` (libppcommon 0x2d644, debug; 0x2345c release) accepts three header variants:

| Variant | Header bytes | Validity check | Header size |
|---|---|---|---:|
| A | `[size_le24:3][0x00]` | `size_le24 == total_size` and `byte[3]==0` (i.e. u32 LE total size < 2²⁴) | 4 |
| B | `[0xFF][len_le16:2]` | `len_le16 == total_size − 3` | 3 |
| C | `[len_be24:3]` | `len_be24 == total_size − 3` | 3 |

Then a sequence of TLV records until end of buffer:

| Record part | Size | Meaning |
|---|---|---|
| type | 1 | record type (see enum below) |
| length | 2 LE (types 80/81: **4 LE**) | payload size in bytes |
| payload | length | type-specific (see §3) |

Record types recovered (via JNI constant getters, `nm` + `mov w8, #imm`):

`DEVICE_ID=1, SWING_UTC=2, IMPACT_TIME=3, ACCEL_CALIBRATION=4, GYRO_CALIBRATION=5, IMU_DATA=6,
MAG_CALIBRATION=7, MAG_DATA=8, SENSOR_TEMPERATURE=9, TARGET_LINE_AIM=10, SWING_SETUP=11,
CLUB_SETTINGS=12, VSR_DATA=13, MULTI_ACCEL_DATA=14, ACCEL_2_CALIBRATION=15, GYRO_2_CALIBRATION=16,
HACCEL_1_CALIBRATION=17, HACCEL_2_CALIBRATION=18, ST_FIFO_COMPRESSED=33, ST_SENSOR_CONFIG=34,
FULL_CLUB_SETTINGS=35 (rejected with PPErr 1 by this parser), ALL_SENSOR_CALIBRATIONS=36,
PLATFORM_VERSIONS=37, USER_DATA=38, APPLICATION_DATA_STORE=39, ST_FIFO_FIRMWARE_COMPRESSED=40,
DETECTOR_DATA=41, LAST_STATIONARY_DATA=48, STATIONARY_DATA_VERSION=49, CROPPED_STATIONARY_DATA=50,
STATIONARY_DATA_SENSOR_CONFIGS=51, COLLECTION_SENSOR_CONFIGS=52, SWING_TIME_CORRECTION=53,
UNCOMPRESSED_16BIT_AUDIO=80, COMPRESSED_16BIT_AUDIO=81, COLLECTION_MULTI_PART_INFO=82,
BUTTON_PRESS_SEQUENCE=83, LIFETIME_COLLECTION_COUNT=84`.
(Types 19–32, 42–47, 54–79 → parse error 6 "Invalid raw data". Golf-swing heritage is evident.)

### 4.2 Haversine/Telesto application protocol (BLE GATT)

Service `607B5C9B-3700-4E94-F44A-2DF900BCB0C3` (also 16-bit `FCC9`); characteristics
(`HaversineUUID.java`): `telestoData = DAAD3D52-…`, `telestoCtrl = C0EF558A-…`,
`systemInput = 1D1F4039-…`.

**Request (app → ring):**
- ctrl channel: 13-byte serialized `TelestoRequest` = `{type:1, address:4 LE, offset:4 LE, length:4 LE}`
  (`TelestoController_addOperation` → outbox writer at 0xf7d4; template constants at .rodata 0x8720/0x8738).
- data channel: request payload bytes (for PROGRAM_MEMORY), framed `[u32 LE length][data]` when larger than
  one packet (`TelestoLengthPrefixedData_create`, 0x19000); transported in ≤20-byte writes **with response**
  (`LinkTransport.sendOutboxDataToCharacteristic`, `maxPacketSize = 20`).

**Operation types** (`TelestoOperationType.java`): `ERASE_MEMORY=1, PROGRAM_MEMORY=2, READ_MEMORY=3,
CANCEL_OPERATION=4`.

**Virtual addresses** (`TelestoVirtualAddress.java`): `APPLICATION_DATA_STORE=0x40000000`,
`COLLECTION_BASE=0x40020000`, `STORED_COLLECTION_INDEXES=0x40030005`, `PLATFORM_VERSIONS=0x40030006`
(+ `0x4003000E` "advertising data", 10 bytes, from the transfer-op templates).

**Response (ring → app):** 12-byte `TelestoResponse` on ctrl channel (assert
`currentResponseSize == sizeof(TelestoResponse)`, 0xc); data bytes accumulate on the data channel until the
expected size (from the ctrl response) is reached (`TelestoController_receiveDataBytes`, 0xf2fc; excess
bytes are dropped with a warning). Transfer operation phases (strings):
`READ_ADVERTISING_DATA` → `READ_STORED_INDEXES` (4-byte response = two u16: stored range start/end,
512-slot ring with wraparound/rollover handling) → `READ_COLLECTIONS` (loop: read `0x40020000|idx`,
deliver blob, idx++/wrap, repeat while in range).

**Integrity mechanisms (complete list):**
- length-prefix + total-length accounting (container header, record length fields, ctrl response size);
- BLE write-with-response for every app→ring packet (`pendingConfirmation` outbox state machine);
- collection-index bookkeeping (`lastSuccessfulCollectionIndex` persisted; resume from `lastEnd+1`,
  `TransferFailed` on error, re-transfer on reconnect);
- `isContiguous` check on multi-part indices; `isFinalPart` sequencing; sample-rate consistency check
  ("Sample rate mismatch" in `MultipartCollection`).
- **No CRC, no checksum, no hash, no sequence numbers, no FEC, no retransmission protocol** at the
  application layer (beyond GATT-level write acks and the re-read-on-reconnect resume logic above).
  Corruption inside a collection is only caught if a length/value check fails, else it decodes to garbage.

**The pairing write of `0x00`** to the telestoData characteristic (observed in the visible Pebble app) does
**not** match any Haversine frame format (Haversine's data-channel writes are ≥4-byte length-prefixed, and
ctrl requests are 13 bytes). It is therefore an app/firmware-level trigger outside the Haversine transfer
protocol; it exchanges no secret (nothing in Haversine reads or stores anything from such a write).

## 5. Cryptography analysis

| Layer | Verdict | Evidence |
|---|---|---|
| BLE link encryption | yes (standard, not app-level) | CoreBluetooth/BLE stack; not present in Haversine code beyond GATT calls |
| Haversine application-layer encryption | **no** | Full decode path disassembled (§3): pure length-parsing + Rice decoding; no cipher calls, no keys, no nonces. `nm -D --undefined-only` on both `.so`: zero imports matching aes/sha/md5/crypto/cipher/rand/ssl/chacha/poly/ecdh; `strings`: no crypto identifiers; no crypto constants (S-boxes, SHA-256 K table, etc.) in `.rodata` |
| Encryption at rest on the ring | **no evidence — almost certainly no** | The exact bytes the ring stores are the bytes Haversine parses and decodes keylessly via shared C code; any at-rest encryption would have to be transparently undone inside these same keyless functions, which is impossible. Residual uncertainty: ring *firmware* not available |

The only hash-like primitives are:
- `mixBits32` (0x31854) — an add/xor/shift avalanche finalizer with fixed constants;
- `_fingerprint(const char*)` (0x31910) — iterates `mixBits32` over the user-ID string (≤132 chars).
Both are used by `PPRingApplicationData_fingerprintMatchesUserId/…NoUser/…Failsafe` to decide whether a
transferred collection belongs to the current user — a **non-cryptographic, non-secret** fingerprint for
user matching, never applied to audio and never inverted or used as a key.

## 6. Key-management analysis

- **Per-ring shared secret: none.** No key generation, no key exchange, no key storage anywhere in
  Haversine (Kotlin IR + both native libraries).
- **Registration ("programming the satellite")** = `KMPHaversineSatelliteManager.programSatelliteWithUserID`
  → `PPRingUser_init(userId)` → `PPRingApplicationData_init(user, unixTime)` → `_serialize_v1` →
  `ProgramApplicationDataOperation` (PROGRAM_MEMORY to virtual address 0x40000000).
  Serialized blob: 141 bytes = `{version:1 (=1), timestamp:4, ?, userId[128] (NUL-padded), fingerprint:4?}`
  — contains only the plain user-ID string, a timestamp and the weak fingerprint. **No secret.**
- **Persistent state** (per ring, Android `SharedPreferences "com.wtlp.haversinecache"`, keyed by satellite
  id; iOS equivalent in the klib IR): platform versions, serial number, sensor-config version,
  `applicationData` (the blob above), `advertisedFingerprint`, `lastTransferEndIndex`. Nothing secret;
  nothing required to decode audio.
- **Does decoding depend on pairing state? No.** `PPCollection_createFromBinaryData/createAudioTimeline`
  take only (bytes, size). Removing pairing/bond information does not invalidate the ability to decode a
  previously captured recording blob.
- **The only persistent cryptographic relationship is the BLE bond itself** (link-layer keys managed by the
  OS Bluetooth stack), which affects *connectability*, not decodability.

## 7. Relevant symbols / functions (chain to TransferComplete)

Kotlin (identical in both iOS klibs and the Android classes.jar):
- `coredevices.haversine.HaversineTransferDelegate`
  - `collectionTransferDidFinish(data: ByteArray, collectionIndex, satellite)` (event channel)
  - `handleDidFinish` → `PPCollection(index, data)` → `getAudioTimeline()` → `PPAudioTimeline`
  - `processMultiPartAudio` / `processSinglePartAudio` → `MultipartCollection.addPart/flushBuffer`
    (kotlinx-io `Buffer.writeShortLe/readShortLe` ⇒ LE PCM16 out)
  - `emitCompleteTransfer` → **`TransferStatus.TransferComplete(satellite, collectionStartCount,
    buttonSequence, collectionIndex, samples: ShortArray, sampleRate: Long, buttonReleaseTimestamp,
    transferCompleteTimestamp, isContiguous)`**
- `coredevices.haversine.ppcommon.PPCollection` — calls native `PPCollection_createFromBinaryData`,
  `PPCollectionSimple_unixTime/buttonPressSequenceString/lifetimeCollectionCount/createAudioTimeline`
  (Kotlin IR strings file, lines for `ppcommonPPCollection`).
- `coredevices.haversine.ppcommon.PPAudioTimeline` — wraps `PPResultAudioTimeline_t`, converts the native
  u16 buffer via `MakeBytesFromUInt16Buffer` + LE `ShortBuffer` to `ShortArray`.
- `com.wtlp.haversinesatellitelibrary.operations.TransferCollectionsOperation` /
  `AndroidHaversineTransferDelegate` — bridge to native transfer operation.

Native (libppcommon.so, android-debug arm64):
- `PPCollection_createFromBinaryData` 0x2f1b0 → `GSParseRecordsInRawData` 0x2d644 (container/TLV parser)
- `PPCollection_createAudioTimeline` 0x2f964 (record dispatch + DD-Rice decode loop; returns
  `PPResult_t`, audio timeline at +8: `{collectionStartIndex u32, sampleRateHz u32, sampleCount u64,
  samples u16*, isMultiPart u8, isFinalPart u8}`)
- `DDRiceDecompressionDecoder_init/readBit/readBits` 0x309e8/0x30a48/0x30b18 (MSB-first bit reader,
  `noBit` = 0xFF sentinel, error 3 = end-of-stream)
- `DDRiceDecompressionChannel_init/decodeDiff/nextWord/prevWord` 0x30930/0x30bcc/0x30f9c/0x31030
  (config nibbles, unary+escape+sign codes, zigzag, double integrator, `sample = A << m`)
- `PPRingApplicationData_serialize/_serialize_v1` 0x3201c/0x31d10, `_fingerprint` 0x31910,
  `mixBits32` 0x31854 (registration data; non-secret)

Native (libhaversinesatellitelibrary.so, android-debug arm64):
- `TelestoController_addOperation` 0xe344 (13-byte ctrl request outbox, data outbox, 12-byte response
  state machine), `TelestoController_receiveCtrlBytes` 0xf130 / `receiveDataBytes` 0xf2fc,
  `TelestoLengthPrefixedData_create` 0x19000 (`[u32 LE len][data]`)
- `HaversineTransferCollectionsOperation_init` 0x1623c + inlined state machine (0x16468 startNextChild,
  0x16714 handleReceivedData, 0x169dc handleCompletion): phases, virtual-address reads, 640 KiB
  collection buffer at op+0x7f, index ring/rollover logic
- `HaversineLinkController_*`, `LinkTransport` (20-byte chunked write-with-response transport)

## 8. Evidence index

- Kotlin structure & call chain: `decomp/coredevices/haversine/*.java` (Vineflower output of AAR
  classes.jar); corroborated by Kotlin IR strings of both iOS klibs (`work_strings_iosarm64.txt`).
- Record-type enum values: JNI constant getters in libppcommon.so (e.g.
  `Java_..._COMPRESSED_116BIT_1AUDIO_1get` @0x21174 returns 81; script-extracted all 50+ constants).
- Container/TLV format: full disassembly of `GSParseRecordsInRawData` (`disasm/gsparerecordsinrawdata.txt`)
  incl. jump table at .rodata 0x15730 mapping record types → struct slots.
- Audio record layouts + decode loop: `disasm/createaudiotimeline.txt`.
- DD-Rice algorithm: `disasm/ddrice_decoder_init_readbits.txt`, `disasm/ddrice_decodediff_nextword.txt`.
- Telesto framing: `disasm/telesto_outboxes.txt`, `disasm/telesto_receiveCtrlBytes.txt`,
  `disasm/telesto_receiveDataBytes.txt`, `disasm/telestooperation_init.txt`,
  `disasm/telestocontroller_addoperation.txt`, `TelestoLengthPrefixedData_create` disassembly.
- Transfer state machine & virtual addresses: `disasm/transferop_init.txt` + rodata request templates
  0x8720/0x8738 + `TelestoVirtualAddress.java`.
- No-crypto: `nm -D --undefined-only` (both .so) grep for crypto primitives → empty; `strings` audit;
  full decode-path disassembly.
- Persistence/registration: `HaversineSharedPreferencesCache.java`,
  `HaversineSatelliteCacheableState.java`, `KMPHaversineSatelliteManager.java`
  (`programSatelliteWithUserID`), `_serialize_v1`/`_fingerprint`/`mixBits32` disassembly.
- PPErr semantics: `PPErr_description` jump table 0x15880 (e.g. 6 = "Invalid raw data",
  7 = "Incomplete raw data", 19 = "Malloc failed").

## 9. Remaining unknowns

| Unknown | What would resolve it |
|---|---|
| Actual sample-rate value(s) used by ring firmware (transported per-record; app resamples to 16 kHz regardless) | ring firmware, or one captured recording, or GATT sniff |
| Ring-side storage layout beyond the collection blob (flash organization, erase semantics) | ring firmware |
| Exact meaning/semantics of the app-level `0x00` write to telestoData during pairing (outside Haversine) | ring firmware / Pebble app source |
| Full 12-byte TelestoResponse field layout (only size and role established) | more disassembly of the ctrl-response parser (0xeea4) or a GATT capture |
| Whether ring ever emits UNCOMPRESSED_16BIT_AUDIO in practice | a captured transfer |
| Multi-part part-count/rollover edge semantics (512-slot ring) | firmware or captures |
| `PPRingApplicationData` exact 141-byte field split (version/timestamp/user[128]/fingerprint) | minor; more disassembly of `_serialize_v1` prologue |

## 10. Independent-client implications

An independent iOS client is feasible **without any secret**. Already understood from this work:

1. **Discover:** scan for the Haversine service UUID `FCC9` / `607B5C9B-…` (advertisement parsing:
   `HaversineAdvertisementData_parseManufacturedData`, includes collection-count/fingerprint fields).
2. **Connect:** standard BLE connect + subscribe to notifications on `telestoCtrl` and `telestoData`.
   (Whether the ring requires bonding is a policy question outside these binaries.)
3. **Authenticate/pair:** nothing to authenticate at the application layer — no secret exists. Optional:
   PROGRAM_MEMORY the 141-byte application-data blob (user ID + timestamp + fingerprint) to `0x40000000`
   so the ring associates recordings with your user ID (affects `fingerprintMatchesUserId` filtering only).
4. **Enumerate recordings:** READ_MEMORY `0x40030005` (4-byte response: u16 range start, u16 range end of
   stored collection indexes; 512-slot ring with wraparound).
5. **Download one:** READ_MEMORY `0x40020000 | index` (13-byte ctrl request
   `{03, addr le32, offset le32=0, length le32=0}`); collect data-channel notifications until the
   ctrl-channel response indicates completion (≤640 KiB).
6. **Decode to PCM:** parse the container (§4.1) and decode the `COMPRESSED_16BIT_AUDIO` record with the
   DD-Rice decoder pseudocode in §3 (≈60 lines of code); resample from the record's `sampleRateHz` to
   16 kHz; remove DC bias first.
7. **Acknowledge/delete safely:** the library itself only advances the stored-index consumption via
   re-reading; destructive operations exist as Telesto ops (`ERASE_MEMORY`, and Haversine's SUOTA/service
   ops for `ERASE_STATIONARY_DATA`, `RESET_SATELLITE`, etc.) — the exact erase address/semantics for
   recordings still need confirmation from firmware or captures before an independent client should erase
   anything.

Still requiring reverse engineering for a fully independent client: the 12-byte TelestoResponse field
layout (to know response lengths robustly), the ring's bonding requirements, the pairing `0x00` write
semantics, and safe erase procedures.
