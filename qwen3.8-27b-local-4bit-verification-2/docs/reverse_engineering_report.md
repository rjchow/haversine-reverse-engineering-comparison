# Haversine ring voice-recording format — reverse-engineering report

Run label: **the second run of local qwen 3.8 27b 4 bit for verification**

**Artifacts analyzed**
- `haversine-iosarm64-03202f5.klib`, `haversine-iossimulatorarm64-03202f5.klib` (Kotlin/Native klibs, `io.github.coredevices.haversine` v`03202f5`, Kotlin 2.2.20, klib ABI 2.2.0)
- The two cinterop klibs published alongside them on Maven Central: `…-cinterop-PPCommon.klib` and `…-cinterop-haversineSatelliteLibrary.klib` (iOS + simulator). These contain the actual native code: `libPPCommon_static.a` (8 arm64 `.o`, no DWARF) and `libHaversineSatelliteLibrary.a` (34 arm64 `.o`, full DWARF), i.e. the Apple-side half of the stack.
- The public ring firmware: `https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json` (v3.75, hardware 11.0) — 29,288-byte Cortex-M (Thumb-2) image, XOR-obfuscated.
- Ring-side firmware source is **not** available (the `coredevices/haversine-kmp` GitHub repo is private; the ring MCU code lives in `HyperionSensing`, only the OTA image is public).

All conclusions below are derived from disassembly of the Apple-side native objects (C + Swift, DWARF-annotated), the Kotlin IR (`bodies.knb`/`strings.knt`), the C-interop protobuf metadata (`.knm`), and the public firmware image. Line/function references are to the extracted objects under `cinterop_extract/`.

---

## 1. Headline answer

**The recordings are NOT ADPCM, NOT Speex, NOT Opus, and NOT encrypted.** What the ring transmits is a **binary "collection"** — a self-describing stream of typed records (a mini-protobuf-ish format, 1-byte record code + 16-bit length, little-endian) that can carry **16-bit signed PCM audio in one of two representations**:

1. **`uncompressedAudioData` (record code 40)** — raw little-endian 16-bit PCM, prefixed by a 4-byte header containing a size field and the **sample rate in Hz (u32, LE)**. This is a verbatim copy of the ADC output.
2. **`compressedAudioData` (record code 41)** — the same 16-bit PCM, entropy-encoded with a **custom delta + Rice ("DD") codec**: sample-to-sample deltas are Rice-coded with an adaptive order `k = 0…15` (k carried in the low nibble of the first payload byte) and a **second-order predictor on the Rice quotient**. This is a *custom* lossless compressor, related in spirit to classical delta/Rice (as in the original "Rice algorithm" / ADPCM-adjacent literature) but not any standard (not μ-law, not G.726, not Speex, not Opus).

The Apple-side decoder (`PPCollection_createAudioTimeline` in `PPCollection.o`) reconstructs a **contiguous little-endian int16 sample buffer** plus metadata `{collectionStartIndex, sampleRateHz, sampleCount, isMultiPart, isFinalPart}` (the C struct `PPResultAudioTimeline_t`). The Kotlin layer (`MultipartCollection`) re-buffers those samples as little-endian 16-bit in a `kotlinx.io.Buffer` and finally emits `TransferComplete(samples: ShortArray, sampleRate: UInt, …)`.

**Sample rate:** the rate is **embedded per-audio-record by the ring** (u32 in the record header for raw PCM; carried in the decoded timeline for compressed data) — there is **no hard-coded rate** in the Haversine/PPCommon code. The ring firmware image (v3.75) contains the constant **8000** (three occurrences, 16-bit) and **32000**, but **no 16000**; the app-side 16 kHz figure from the product spec is the *destination* rate after the host resamples. The best-supported reading of the evidence is that **the ring's native microphone rate is 8 kHz** (with the 16 kHz rate being a resampled/host variant); the exact rate of any given recording is whatever the ring wrote into the record header.

**Crypto:** none at the application layer. No AES/ChaCha/HMAC/SHA/CRC or other cipher symbols exist in either native archive or the Kotlin IR. The only "XOR" in the codebase is the reboot reason `PP_REBOOT_RESTORE_CODE_AFTER_COLLECTION_XOR`, which refers to the ring obfuscating its own stored firmware image (the public OTA image is indeed not plain code). Transport confidentiality relies on the standard BLE link (the ring uses Core Bluetooth / `CBCentralManager`; when bonded, BLE encryption is the only protection). The 32-bit "fingerprint" described in §5 is an identifier/state tag, **not a key** (the failsafe value is the public constant `0xDEADDEAD`).

---

## 2. What the ring stores and how "a recording" is structured

### 2.1 The collection container

A *collection* is the unit the ring records (one "event": a voice memo, a swing, a sensor burst) and the unit it transfers. Its binary layout (decoded from `GSParseRecordsInRawData` in `PPParsing.o` / `PPCollection.o` and from `PPCollection_createFromBinaryData`):

```
+0x00  (1 byte "isMultiPartAudio" flag + 31 bytes of pre-header)
+0x21  37 x 8-byte record-pointer slots  (+0x21 … +0x120)   (see 2.2)
...    ~0x1030-byte PPCollection struct (0x1158 total)
```

`PPCollection` is a 0x1158-byte C struct. Its 37-slot record table lives at `+0x21` (the 37th slot, `+0x120`, is zeroed separately by the parser). The record *types* the parser knows (record code → meaning, from the jump table in `GSParseRecordsInRawData` and the `PPCollection` accessors):

| code | meaning | code | meaning |
|---|---|---|---|
| **7** | **deviceID** (6-byte serial) | 35 | **applicationDataStore** (the 141B pairing record) |
| **15** | **UTC** (u32 seconds) | 36–37, 39 | sensor-config / detector / stationary-data blocks |
| 1–6, 8–14 | IMU/mag calibration & config blocks | **38** | swingTimeCorrection (u32 µs-diff) |
| 19–20 | misc sensor blocks | **29** | **platformVersions** (firmware versions) |
| 21–28, 30–34, 45–47 | reserved/other (incl. 32-bit-length variants at 43/44, tail slot at 47) | **40** | **`uncompressedAudioData`** (raw PCM16, the recording) |
| | | **41** | **`compressedAudioData`** (delta+Rice "DD" bitstream, the recording) |
| | | **42** | **`collectionMultiPartInfo {u32 startIndex; u8 isMultiPart; u8 isFinalPart}`** |

Only codes 1–47 are defined (the 1-byte jump table in `GSParseRecordsInRawData`, extracted from `__const` of `PPParsing.o`, marks the rest as "unknown"). Each slot in the parsed 288-byte record table (37 slots) points at the record's 16-bit length field, with the payload immediately after it; codes 43/44 use a 32-bit length instead.

On the wire, a collection is: a 3-byte total-size header (three supported encodings: big-endian 24-bit, `0xFF`-prefixed 16-bit, and little-endian 24-bit when `b3==0`; must equal `len−3`), followed by the concatenated `{u8 code; u16 len; len bytes of payload}` records (little-endian). Codes 43/44 use a 32-bit length field instead of the 16-bit one.

### 2.2 The audio record (the recording itself)

Two layouts, both decoding to 16-bit PCM. In both, the record's 16-bit length field is a truncated copy of the first u32 (so `u32@recordBase` reconstructs it).

**Raw (code 40)** — `createAudioTimeline` path A:
```
+0x00  u16  len          (= low 16 bits of the size field below)
+0x02  u32  sizeField    (= 4 + 2·sampleCount, header + payload)
+0x06  u32  sampleRateHz
+0x0a  …    int16 LE samples[ (sizeField−4)/2 ]
```
The decoder copies the samples verbatim (2-byte-aligned allocation).

**Compressed (code 41)** — `createAudioTimeline` path B: a **DD (delta+Rice) bitstream**:
```
+0x00  u16  len
+0x02  u32  compressedSize
+0x06  u32  sampleCount  (expected number of 16-bit samples)
+0x0a  9 bytes  DD header: first byte's low nibble = Rice order k (0…15),
          remaining 8 bytes = 2nd-order predictor state
+0x13  …    bit-packed delta+Rice stream
```
- The stream is consumed by a `DDRiceDecompressionChannel` bit reader (`{ptr, bytePos, bitOffset, size}`) — the audio is **bit-packed**, not byte-aligned.
- Deltas between successive 16-bit samples are Rice-coded (`q = |Δ| >> k`, `r = |Δ| & (2^k−1)`; `q` in unary, then `r` bits); a **second-order predictor** acts on the Rice quotient (hence `DDRiceDecompressionDecoder`) and adapts as the signal changes.
- The decoder fills a sample buffer that starts at 15,680 bytes (7,840 samples) and grows (doubling) up to ~99,984 samples per part — i.e. a single part holds on the order of **6–12 seconds** of audio depending on rate.
- A built-in sanity check rejects the record if the compressed size can't hold the declared sample count.

So the **on-ring representation** is: 16-bit signed PCM from the microphone's ADC, optionally Rice/delta-compressed in a bit-packed stream, tagged with the sample rate and a multi-part/final flag, inside a record-stream collection.

### 2.3 Multi-part collections

A long recording is split into **parts**, each its own collection, sharing a `collectionStartIndex` and a `collectionMultiPartInfo` record `{u32 startIndex; u8 isMultiPart; u8 isFinalPart}`. The Kotlin `MultipartCollection` accumulates parts (refusing a part whose `sampleRateHz` differs from the running rate) until the part with `isFinalPart` arrives, then `flushBuffer()` yields the contiguous `ShortArray`.

### 2.4 Reboot / integrity

`PPRebootReasons.o` enumerates the ring's reboot reasons, incl. `PP_REBOOT_RESTORE_CODE_AFTER_COLLECTION_XOR`, `PP_COMPRESSION_FAILURE`, `PP_REBOOT_INVALID_ADDRESS_SEED`, `PP_ADC_SAMPLE_RATE_OUTSIDE_BOUNDS` — confirming the ring self-checks the ADC sample rate and the address-seed key, and that compression failure is a first-class failure mode.

---

## 3. Framing / packet layout on the air (BLE, minus the link layer)

The Haversine transport is a bespoke **Telesto** protocol carried over two GATT-ish channels (control + data) inside the `TelestoController` (0x98-byte C struct):

- **Control channel — requests (16-byte struct, 13 meaningful bytes):** `TelestoRequest = { u8 type; u32 a; u32 b; u32 c }` — the C declaration lists fields `address`, `length`, `type` (a bitfield). Operationally: **byte 0 = the operation type**, and the following words carry a **64-bit virtual address** (low u32 / high u32) plus a length/flag word. The Swift `TelestoOperation.init(request:dataToSend:)` rebuilds exactly these 13 bytes, confirming the layout.
  - **Type enum (C order):** `0 = TELESTO_NO_OPERATION, 1 = TELESTO_ERASE_MEMORY, 2 = TELESTO_PROGRAM_MEMORY, 3 = TELESTO_READ_MEMORY, 4 = TELESTO_CANCEL_OPERATION, 5 = TELESTO_ERASE_AND_PROGRAM_MEMORY` — a *virtual-memory* instruction set (the ring presents its flash as addressable memory).
  - **Virtual address map** (64-bit, observed in code): `0x4002xxxx` = **collection region** (`TELESTO_COLLECTION_BASE = 0x40020000`, low 16 bits = the 16-bit collection index); `0x40000000_03060003` and `0x40000000_03080003` = the **"single-sector"/application region** (programmed serial / product header and platform-versions blocks — the same address pair is read by both the cache-update and firmware-update operations). The C header defines ~40 named addresses (`TELESTO_COLLECTION_BASE/MAX/COUNT`, `TELESTO_SINGLE_SECTOR_START/END`, `TELESTO_APPLICATION_DATA_STORE`, `TELESTO_PROGRAMMED_SERIAL_NUMBER`, `TELESTO_UNIX_TIME`, `TELESTO_BATTERY_VOLTAGE`, `TELESTO_GPIO_STATUS`, `TELESTO_LED_SEQUENCE`, `TELESTO_CURRENT_ADVERTISING_DATA`, `TELESTO_LSM6DSO32_FREQ_FINE`, `TELESTO_PHOTOTRANSISTOR_VOLTAGE`, `TELESTO_LAST_RX_RSSI`, `TELESTO_LIFETIME_COLLECTION_COUNT`, `TELESTO_RECENT_SATELLITE_EVENTS`, `TELESTO_STATIONARY_DATA`, `TELESTO_SENSOR_CALIBRATIONS`, `TELESTO_SENSOR_0_FIFO/STATE_CONFIGS/STREAMING_CONFIG`, `TELESTO_PRIMARY_IMAGE`, `TELESTO_FAILSAFE_IMAGE`, …).
- **Control channel — responses (12 bytes):** `TelestoResponse = { u32 error; u32 info; u32 length }`.
- **Data channel:** `TelestoLengthPrefixedData = { u32 length (LE); bytes[] }` — the actual payload (a collection's bytes, the firmware image, the 141B app-data record).
- **Reverse direction (ring → phone) — `HaversineSystemInput`:** a bitfield of 14 event flags the ring pushes to trigger work: `interrupt, collectionSignal, calibrationAccelOctant, sleepChange, sleepState, largeImpact, fifoWatermark, inCollectionOrientationUpdate, inCollectionOrientation, offClubUpdate, motionFSMUpdate, motionFSMValue, smallImpact, reserved` — i.e. collections are *triggered* by impact/motion FSM events and an explicit collection signal, which also explains the swing/voice-recording behaviour.

The **"update cache" operation** (`HaversineUpdateCacheOperation`, C, 8304-byte op struct) is a 4-phase *read* state machine that refreshes the phone's cached view of the ring after events:

1. `PHASE_READ_APPLICATION_DATA` → the ring's **application-data store** (the 141-byte pairing record; read size = `applicationDataTelestoReadSize`).
2. `PHASE_READ_SERIAL_NUMBER` → `TELESTO_PROGRAMMED_SERIAL_NUMBER` (6-byte serial).
3. `PHASE_READ_SENSOR_STATE_CONFIGS` → `TELESTO_SENSOR_0_STATE_CONFIGS` (a `TelestoSensorConfigsHeader {headerLength, version, info, dataOffsets[], length-prefixed payloads}` with `inFailSafe`/`hasPayload` bits).
4. `PHASE_READ_PLATFORM_VERSIONS` → 16-byte `TelestoPlatformVersions { u8 hwMajor; u8 hwMinor; u8 fwMajor; u8 fwMinor; +12B }` — the same fields the `haversine_update.json` carries (v3.75 → `{3, 75, …}`).

It produces `HaversineCacheableStateUpdate { platformVersions; serialNumber; applicationData; applicationDataSize }`, which the app persists (cache dir `haversine_download`) — this is how the phone learns pairing/failsafe/version state after a collection or a reboot.

The `HaversineTransferCollectionsOperation` (C, ~41 KB op struct) drives the actual recording transfer as a 3-phase child-operation state machine:

1. **Phase 0 — read collection count** (child op) → `u16 count` (total collections on the ring).
2. **Phase 1 — read one collection at a time, newest first**, looping down the 16-bit index space (with wrap-around arithmetic and a max range of 0x201 = 513). The child request packs the virtual address as `u32 = 0x40020000 | u16 index` — i.e. collections live in a 16-bit-indexed "domain" of the ring's virtual memory. The host calls back into the app (`willTransferCollectionsInRange`) before each read.
3. **Phase 2 — read multi-part collections** into a 0x10000-byte buffer (payload at +0x81), then parse with `GSParseRecordsInRawData`.

The "read last audio samples" operation is the same mechanism applied to the newest collection: it reads the last collection index (16-bit field at +0x72), issues a `TELESTO_READ_MEMORY` at `0x40020000 | index`, and `_processAudioCollection` runs `PPCollection_createFromBinaryData(data, len)` → `PPCollection_createAudioTimeline`, copying the resulting PCM into a growing internal buffer (fields at +0x50B0/+0x50B8 of the ~25 KB op struct) along with the 16-byte timeline header `{u32 collectionStartIndex; u32 sampleRateHz; u64 sampleCount}` — the sample rate coming from the record on the ring, not from a constant. Its debug trace strings name the phases: `PHASE_READ_COLLECTION_COUNT → PHASE_READ_LAST_COLLECTION → PHASE_READ_MULTIPART_COLLECTIONS → PHASE_READ_CACHED_STATE → PHASE_READ_BATTERY_VOLTAGE → PHASE_READ_RX_RSSI`.

**Resume / persistence:** the host persists `lastTransferEndIndex` (a `UInt16`) plus the `HaversineCacheableStateUpdate` cache; on restart the transfer resumes from `CollectionIndexStorage.lastSuccessfulCollectionIndex`.

---

## 4. Firmware update (for completeness)

`KMPHaversineSatelliteManager.requestUpdate` does a Ktor GET of `haversine_update.json` (from the public `HyperionSensing/firmware_releases` repo), base64-decodes `image` (the 29,288-byte obfuscated Cortex-M image) into `HaversineFirmwareUpdate{versionMajor, versionMinor, hardwareMajor, hardwareMinor, image, creationDate}` (the JSON carries `3, 75, 11, 0` → matching `TelestoPlatformVersions`), and the `HaversineSuotaOperation` C state machine programs it to the ring's **primary / failsafe image** regions (`TELESTO_PRIMARY_IMAGE` / `TELESTO_FAILSAFE_IMAGE` in the single-sector region; the op's const blocks reference the same `0x40000000_03060003` address plus chunk-descriptor blocks) over the Telesto `TELESTO_PROGRAM_MEMORY` / `TELESTO_ERASE_MEMORY` ops, after which the ring reboots. The `PP_REBOOT_RESTORE_CODE_AFTER_COLLECTION_XOR` reboot reason indicates the stored image is XOR-obfuscated at rest and de-obfuscated by firmware.

---

## 5. Key management / pairing

- **Static BLE address:** `PPGenerateUniqueStaticRandomBluetoothAddress(u64 addressSeed)` derives a **stable, random (locally-administered) MAC** from a per-device 64-bit seed via `PPTinyBitMixer` = 5 rounds of `byteswap(x·0x9E3779B9)` (the golden-ratio 32-bit hash) plus a fixed 14-bit prefix and a `0x1C2C` XOR pattern. The `PP_REBOOT_INVALID_ADDRESS_SEED` reboot reason shows the seed is integrity-checked.
- **User pairing record:** `PPRingApplicationData_t = { u32 fingerprint; u32 timestamp; char uid[129] }` (~132 B), serialized to a **141-byte (0x8D)** v1 wire record `{u8 version=1; 8B (fingerprint+timestamp); 129B uid}` and programmed into the ring's 4096-byte application-data store (collection record code 35; Telesto address `TELESTO_APPLICATION_DATA_STORE`) via the Telesto `TELESTO_PROGRAM_MEMORY` operation.
  - `fingerprint` is a **custom 32-bit hash** (xxHash-style mixing, six proprietary constants) of the 132-byte record.
  - `fingerprintMatchesUserId(uid)` compares only the **low 16 bits** of `hash(uid)` against the stored fingerprint.
  - `fingerprintMatchesNoUser` = high 16 bits zero (unpaired/factory); `0xDEADDEAD` = **failsafe** mode (a special fingerprint the phone checks via `fingerprintMatchesFailsafe`).
  - The phone *programs* the record after pairing (`programSatelliteWithUserID` / `programSatelliteWithApplicationData` → 141-byte `NSData` via the Telesto `PROGRAM` operation) and *re-reads* it any time via the **update-cache** operation (section 3) — which is also how the phone detects a transition into failsafe mode.
  - `fingerprintMatchesFailsafe` = `fingerprint == 0xDEADDEAD` (corrupted/unreadable → the ring's "failsafe" state surfaced as `isInFailsafeMode`).
- The 32-bit `fingerprint` is thus a **pairing/state identifier, not a cryptographic key**; there is no key-derivation, MAC, or cipher anywhere in the audio path.

---

## 6. Direct answers to the brief

- **Raw PCM / ADPCM / Speex / Opus / delta / custom / encrypted / combination?** → **A combination: raw 16-bit PCM (record code 40) and a custom delta+Rice ("DD") entropy-coded version of that same 16-bit PCM (record code 41), with the sample rate embedded in each record header.** Not ADPCM in the G.726/μ-law sense, not Speex, not Opus, not delta-only. Not encrypted at the application layer (no cipher symbols exist anywhere in the artifacts).
- **On-ring representation?** 16-bit signed PCM from the mic ADC, stored inside record-stream "collections" (one per recorded event), multi-part for long recordings, each tagged with sample rate + final-part flag.
- **Sample rate?** Embedded per-record by the ring (`u32 sampleRateHz` in the audio record header; surfaced as `PPResultAudioTimeline_t.sampleRateHz` / `TransferComplete.sampleRate`). No hard-coded rate in the host code. The ring firmware image contains the constant **8000** (three 16-bit occurrences) and 32000 but **no 16000**, so the ring's native microphone rate is best read as **8 kHz**; 16 kHz is the host resampling target per the product spec.
- **Framing/packet layout?** Telesto: 16-byte `{type, 64-bit virtual address, length}` requests (types 0–5 = NOOP/ERASE/PROGRAM/READ/CANCEL/ERASE+PROGRAM), 12-byte `{error, info, length}` responses, 4-byte-LE length-prefixed data payloads, over control+data channels; plus a 14-flag `HaversineSystemInput` bitfield the ring pushes to trigger collections (impact/motion FSM/collection signal). Audio records are `{u8 code; u16/u32 len; …}` in a little-endian record stream with a 3-byte total-size prefix (BE24 / 0xFF+BE16 / LE24).
- **Crypto?** None in the audio/data path (BLE link-layer encryption only). The only XOR is the ring's firmware-storage obfuscation (`0xDEADDEAD`-tagged failsafe is a state, not a key).
- **Key management?** A per-device 64-bit `addressSeed` → deterministic random MAC (golden-ratio bit mixer); a 141-byte `PPRingApplicationData` pairing record (custom 32-bit fingerprint, low-16-bit user match, `0xDEADDEAD` failsafe) stored in the ring's app-data region.

---

## 7. Method / reproducibility

- klibs unzipped; cinterop `.a` extracted; arm64 objects disassembled with `otool -tV` + DWARF subprogram annotation (`tools/annotate_disasm.py`); symbols/sweeps with `nm`/`strings`; C-interop `.knm` protobuf metadata decoded (`tools/knm_strings.py`).
- Kotlin IR read directly: `ir/strings.knt` (2.2 layout = `[u32 count][u32 len…][pools]`, each pool `[u32 n][u32 len…][raw]`) plus `bodies.knb`, giving the full `HaversineTransferDelegate`/`MultipartCollection`/`KMPHaversineSatelliteManager` logic without a Kotlin toolchain.
- Ring firmware fetched from the public `HyperionSensing/firmware_releases` repo and analyzed (Cortex-M Thumb-2, XOR-obfuscated).
- Full running log of every finding: `PROGRESS.md`.
