# Haversine / Pebble Index 01 Recording Transfer — Reverse-Engineering Report

**Artifacts analyzed**

| Artifact | SHA-verified source | Role |
|---|---|---|
| `haversine-iosarm64-03202f5.klib` | Maven Central | Kotlin/Native glue (Kotlin 2.2.20, serialized IR + linkdata) |
| `haversine-iossimulatorarm64-03202f5.klib` | Maven Central | Same, simulator slice (logic identical; only `native_targets` differs) |
| `haversine-iosarm64-03202f5-cinterop-PPCommon.klib` → `libPPCommon_static.a` | Maven Central (same directory as main klib) | **C library with the actual collection parser and audio decoder** |
| `haversine-iosarm64-03202f5-cinterop-haversineSatelliteLibrary.klib` → `libHaversineSatelliteLibrary.a` | Maven Central | **Swift + C library implementing the BLE "Telesto" transport** |
| `coredevices/mobileapp` (GitHub, master) | open source | App-side anchors (pairing, storage, preprocessing) |

The `.klib`s are zip archives containing Kotlin/Native serialized IR (`ir/bodies.knb`, `strings.knt`, …) and linkdata. Critically, the two cinterop klibs **embed the complete static native libraries** (`targets/<triple>/included/*.a`) with full symbols, which were disassembled (`objdump -dr`, arm64). All offsets cited below are from the `ios_arm64` slices.

---

## 1. Executive answer

**What the Index stores:** Per "collection" (a recording session), the ring stores a self-contained binary object — a length-prefixed TLV container of typed records (`GS raw data records`). The audio is one record inside it, in one of two formats: **(a)** a custom lossy codec ("DDRice": 2nd-order delta + Rice/unary entropy coding with error-feedback quantization, sample rate and codec parameters in a small header), or **(b)** plain little-endian signed 16-bit PCM with a 4-byte sample-rate prefix. The same container also carries IMU/magnetometer timelines, timestamps, button-press sequences, sensor calibrations, application data (the paired user ID), etc. — the product lineage is a swing-sensor platform ("GS" records, "Telesto" memory map), and audio was added as one more record type.

**What is transmitted:** The **entire stored collection object**, byte-for-byte, read out of the ring's memory over the "Telesto" protocol (a remote read/program/erase memory-access protocol over two BLE characteristics: a 12-byte control channel and a length-prefixed data channel with per-chunk acknowledgements). A collection is addressed as `0x40020000 | collectionIndex` and read as **one complete object** (not incremental audio frames). Multi-part recordings are multiple collections linked by a `collectionMultiPartInfo` record (`collectionStartIndex`, `isMultiPart`, `isFinalPart`) and stitched client-side.

**What Haversine receives:** The raw TLV container bytes. `PPCollection_createFromBinaryData` → `GSParseRecordsInRawData` parses it. `PPCollection_createAudioTimeline` decodes the audio record (Rice-decode or PCM copy) into **unsigned 16-bit LE samples + `sampleRateHz` + `collectionStartIndex` + `isMultiPart`/`isFinalPart`**.

**What Haversine outputs to the app:** `TransferStatus.TransferComplete(collectionStartCount, samples: ShortArray, sampleRate: UInt, buttonReleaseTimestamp, transferCompleteTimestamp, isContiguous)`. Samples are the decoded 16-bit values (little-endian throughout); the Kotlin `MultipartCollection` concatenates parts via `writeShortLe`/`readShortLe` (LE). The app then does DC-bias removal → resample to 16 kHz → LE PCM16 mono (matches the open-source app).

**Encryption:** **No.**
- At rest on the ring: **unknown** (firmware not analyzed), but nothing in the client prepares or consumes ciphertext, and the client reads collections as plain bytes with a plain length prefix.
- At the Haversine application layer in transit: **No** — definitively. Exhaustive constant/symbol scans of all four binaries found **no AES, ChaCha, SHA, HMAC, CRC, or any cryptographic primitive**, and no key material anywhere.
- The only cryptography in the system is **BLE link-layer encryption** (bonding), which is explicitly out of scope per the brief.

**Registration-derived shared secret:** **Does not exist.** "Pairing" = BLE bonding (triggered by writing one byte `0x00` to the Telesto data characteristic) plus "programming" the ring with a `PPRingApplicationData` blob (version, timestamp, 129-byte user-ID string — 141 bytes total, serialized by `PPRingApplicationData_serialize`). The only derived value is a **32-bit non-cryptographic fingerprint** (`mixBits32`, a multiply/xorshift hash) used to match advertisements to the paired user. Haversine persists only `lastSuccessfulCollectionIndex`. Deleting pairing data cannot affect the ability to decode recordings, because decoding involves no key.

---

## 2. End-to-end data path

```
microphone (Index 01)
  -> [ring storage: collection object in flash; audio record is either
        DDRice-compressed 16-bit (k LSBs dropped, 2nd-order delta) or raw s16LE PCM]
  -> [collection TLV container: [len][record 0x53/0x54 audio | 0x51 multipart info | IMU/UTC/button records ...]]
  -> [no application-layer encryption]
  -> Telesto read op {op=0x03, addr=0x40020000|collectionIndex}
  -> BLE: 12-byte ctrl msg (request) + data channel: 12-byte header (u32 LE length) + payload chunks,
     per-chunk pendingConfirmation ack            [BLE link encryption only]
  -> libHaversineSatelliteLibrary (Swift/C): reassembles object, length check,
     collectionTransferDidFinish(data, collectionIndex, satelliteId)
  -> Kotlin HaversineTransferDelegate.handleDidFinish(data, index)
  -> PPCollection(data, index) -> PPCollection_createFromBinaryData -> GSParseRecordsInRawData (TLV parse)
  -> PPCollection_createAudioTimeline
        - record 0x54 (uncompressed): samples = payload[4..], sampleRateHz = payload[0..3] (u32 LE)
        - record 0x53 (compressed):  DDRice decode -> u16 samples; sampleRateHz from record header
  -> PPAudioTimeline (sampleRateHz, sampleCount, samples, isMultiPart, isFinalPart, collectionStartIndex)
  -> MultipartCollection.addPart (writeShortLe; enforces contiguous indices, consistent sample rate)
  -> flushBuffer (readShortLe) -> ShortArray
  -> TransferStatus.TransferComplete(samples, sampleRate, collectionStartCount, timestamps, isContiguous)
  -> app: removeDCBias -> resample(sampleRate -> 16000) -> LE PCM16 mono
```

Sample rate is **data-driven** (a `u32 LE` field inside the audio record); no sample-rate constant is hardcoded anywhere in the binaries. The ring's actual ADC rate is therefore whatever the firmware wrote per recording (not determinable from these artifacts).

---

## 3. Codec analysis — "DDRice" (custom, fully reconstructed)

Evidence: `libPPCommon_static.a` → `DDRiceCompression.o` (symbols `DDRiceCompressionEncoder_*`, `DDRiceDecompressionChannel_decodeDiff/nextWord/prevWord`, `DDRiceDecompressionDecoder_readBit/readBits`), invoked from `PPCollection_createAudioTimeline` (`PPCollection.o` @0x4c0–0x514). It is **not** ADPCM, Speex, or Opus — no step tables, no LPC, no third-party codec symbols. It is a custom Rice/Golomb-coded **second-order differential** codec with quantization.

### Compressed audio record (type `0x53`) payload

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 2 | reserved/version (u16 LE; expected 0 — included in the parser's length arithmetic) |
| 2 | 1 | config byte: **low nibble = k** (number of LSBs dropped per sample), **high nibble = maxPrefix** (unary escape threshold) |
| 3 | 4 | `compressedBitCount` (u32 LE) |
| 7 | 4 | `sampleRateHz` (u32 LE) |
| 11 | … | bitstream, **MSB-first** within each byte |

Parser validation (`PPCollection_createAudioTimeline` @0x498): `recordLen*8 − 72 ≥ compressedBitCount`, else error 6.

### Codebook (per sample, encoding the signed 2nd difference `d2 = q[i] − 2·q[i−1] + q[i−2]` of the quantized value, folded to 16−k bits)

| Bits (MSB-first) | Decoded value |
|---|---|
| `1` | `d2 = 0` (1 bit) |
| `0`×n `1` `s`, n < maxPrefix | `d2 = +(n+1)` if s=0, `−(n+1)` if s=1 (n+2 bits) |
| `0`×maxPrefix + raw (16−k) bits | escape: folded raw value `v` (interpreted mod 2¹⁶: `v ≥ 2^(15−k)` ⇒ `v −= 2^(16−k)`) |

### Reconstruction (decoder state: two u16 accumulators `sum1`, `sum2`)

```python
# per codeword:
sum2 = (sum2 + d2) & 0xFFFF
sum1 = (sum1 + sum2) & 0xFFFF
sample_i = (sum1 << k) & 0xFFFF        # u16 LE, stored via strh
```

(Verified against the encoder in the same object: encoder keeps `qv`, `d1`, `sum2` state; computes `acc = wrap16(sum2 + sample + 2^(k−1))` — a 1-bit **error-feedback** rounding; `qv = acc >> k`; encodes `Δ²qv`; updates `sum2 += sample − (qv<<k)`. So the ring stores audio quantized to the top `16−k` bits — the codec is **lossy** — and `nextWord` inverts it exactly. A reference decoder is implementable from this section alone.)

### Uncompressed audio record (type `0x54`)

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | `sampleRateHz` (u32 LE) |
| 4 | 2·N | **signed 16-bit little-endian mono PCM samples** |

Which of the two the Index 01 firmware actually emits is firmware-dependent (both are supported client-side; `createAudioTimeline` prefers `0x54` when present).

---

## 4. Frame/protocol structure

### Layer 1 — BLE GATT
- Service `607B5C9B-3700-4E94-F44A-2DF900BCB0C3`; Telesto control characteristic and Telesto **data** characteristic `DAAD3D52-237C-90A7-B54B-8854A134D801` (names from `CBConnectedPeripheralAdaptor.sendTelestoCtrlBytes/DataBytes`, `IndexPairing.ios.kt`).
- Control channel: fixed **12-byte** messages (accumulator at `TelestoController+0x78`, count at `+0x88`; dispatch at exactly 12).
- Data channel: **12-byte header** containing u32 LE total payload length (`+0x80`) + streamed payload; flow control by explicit confirmation (`pendingConfirmation` in `Outbox`), i.e., per-chunk app→ring acks. No app-layer CRC.

### Layer 2 — Telesto operation (`TelestoRequest`, 24-byte C struct)
| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 1 | op code (observed `0x03` = `TELESTO_READ_MEMORY`; family includes `PROGRAM_MEMORY`, `ERASE_MEMORY`, `ERASE_AND_PROGRAM_MEMORY`, `CANCEL_OPERATION`, `NO_OPERATION`) |
| 1 | 4 | address (u32 LE). Collections: `0x40020000 \| collectionIndex` (`TELESTO_COLLECTION_BASE`) |
| 5 | 8 | zero (offset/length = `TELESTO_LENGTH_INFER_FROM_PREFIX`) |
| 13 | … | optional outbound payload (for program ops) |

Response data arrives length-prefixed on the data channel. Named address-space constants recovered: `TELESTO_STORED_COLLECTION_INDEXES`, `COLLECTION_COUNT`, `LIFETIME_COLLECTION_COUNT`, `APPLICATION_DATA_STORE`, `UNIX_TIME`, `PLATFORM_VERSIONS`, `SERIAL_NUMBER`, `CURRENT_ADVERTISING_DATA`, `SENSOR_0_*`, `CRASH_COREDUMP`, `RECENT_SATELLITE_EVENTS`, `ERASE/PROGRAM_MEMORY`, `CANCEL_OPERATION`, `VIRTUAL_ADDRESS_BASE`.

### Layer 3 — Collection object (TLV "GS raw data records")
Container variants (accepted by `GSParseRecordsInRawData`, `PPParsing.o`):
- `[u8 0xFF][u16 LE len][records…]` (len = bytes after header)
- `[u24 BE len][records…]`
- `[u32 LE len][records…]` (top byte must be 0)

Record: `[u8 type][u16 LE reclen][payload (reclen−1 bytes)]` — note **reclen includes the type byte**. Two long-record types (`0x4d`, `0x54`) use `[u8 type][u24 LE len][payload]`. Unknown type → error 6; record sizes must exactly consume the container.

Full type map (from the 84-entry jump table in `PPParsing.o.__TEXT,__const@0xb68`):

| Type | Record | Type | Record |
|---:|---|---:|---|
| 0x01 | impactTimestamp | 0x28 | stSensorConfig |
| 0x02 | UTC | 0x2c | applicationDataStore |
| 0x03 | deviceID | 0x2d | detector |
| 0x04 | magSamples | 0x31 | stationaryDataSensorConfigs |
| 0x05 | haccel2Calibration | 0x32 | croppedStationaryData |
| 0x06 | VSRSamples | 0x33 | latestStationaryDataVersion |
| 0x07 | gyroCalibration | 0x34 | latestStationaryData |
| 0x08 | accelCalibration | 0x38 | collectionSensorConfigs |
| 0x09 | multiAccelSamples | 0x4d | buttonPressSequence (u24 len) |
| 0x0a | swingSetup | 0x51 | collectionMultiPartInfo |
| 0x0b | targetLineAim | 0x52 | swingTimeCorrection |
| 0x0c | sensorTemperatures | **0x53** | **compressedAudioData** |
| 0x0d | gyro2Calibration | **0x54** | **uncompressedAudioData** (u24 len) |
| 0x0e | accel2Calibration | 0x0f | magCalibration |
| 0x10 | IMUSamples | 0x13 | allSensorCalibrations |
| 0x14 | haccel1Calibration | 0x21 | clubSettings |
| 0x24 | stFifoFirmwareCompressed | 0x25 | stFifoCompressed |
| 0x26 | userData | 0x27 | platformVersions |

Audio-relevant payloads:
- `0x51 collectionMultiPartInfo`: `[u32 LE collectionStartIndex][u8 isMultiPart][u8 isFinalPart]`
- `0x53 / 0x54`: see §3.

### Layer 4 — Satellite event stream (separate, for status)
`PPSatelliteEvent_deserializeNext`: `[u16 LE size][u8 eventCode][fixed-size payload (argumentSizeForCode, ≤10 bytes)]`.

---

## 5. Cryptography analysis

| Layer | Encrypted? | Basis |
|---|---|---|
| BLE link | **yes** (standard bonding) | CoreBluetooth bonding triggered by app; normal LE security |
| Haversine application layer | **no** | No crypto constants/symbols in `libPPCommon_static.a`, `libHaversineSatelliteLibrary.a` (both targets), or Kotlin IR (`bodies.knb`). Scanned: AES s-box/inv, SHA-256 K/IV, SHA-1/MD5 IVs, ChaCha sigma, CRC32 tables/polynomial, P-256 params, Poly1305 clamp, Curve25519 — zero genuine hits (all raw matches were Swift metadata/jump-table/float false positives, verified by context). Dependency list is only `CoreBluetooth/Foundation/darwin/posix`. |
| Storage at rest (ring) | **unknown** | Firmware not available; the client reads collections as plaintext objects with plaintext length prefixes, with no ciphertext handling, key input, or decrypt step client-side. |

`programFirmware(skipVerification:)` verification is read-back-style (Suota), not signature-based crypto.

---

## 6. Key-management analysis

1. **Per-ring shared secret?** No. Nothing secret is generated, exchanged, or stored.
2. **Created how?** N/A. "Programming" writes `PPRingApplicationData` = `{u32 version=1; u64 timestamp; char userId[129]}` = 141 bytes (`__serialize_v1`, `PPRingApplicationData.o`) to `TELESTO_APPLICATION_DATA_STORE`.
3. **Where stored?** On the ring only. Client persists **only** `lastSuccessfulCollectionIndex` (`CollectionIndexStorage`; app impl `PrefsCollectionIndexStorage`) and caches `HaversineSatelliteState.CacheableState{advertisedData, proximity}` in UserDefaults (`HaversineUserDefaultsCache`). No Keychain/secret usage anywhere in the binaries.
4. **How used?** The ring's advertisements carry a `cacheableStateFingerprint` (u32); `mixBits32`-based `fingerprintMatchesUserId/Failsafe/NoUser` decide whether an advertisement belongs to the paired user (`KMPHaversinePermissionsDelegate`). Identification, not encryption.
5. **Does registration exchange it?** No key exchange exists (no ECDH, no random-secret generation).
6. **Does decoding depend on it?** No — decoding is pure arithmetic (§3).
7. **Is bonding the only cryptographic relationship?** Yes.

The brief's hypothesis (registration-derived secret encrypting recordings) is **disproven** for the iOS client side: the client performs no decrypt anywhere in the path `BLE bytes → TLV parse → DDRice/PCM → ShortArray`.

---

## 7. Relevant symbols / call chain to `TransferComplete`

```
BLE notifications (Telesto data char)
 <- TelestoController_receiveDataBytes            (C, TelestoController.o @0x628)
 <- HaversineLinkController_receiveTelestoDataBytes
 <- HaversineTransferCollectionsOperation child ops (op=3 read @0x40020000|idx, TransferOperation*.o @0x1b4)
 <- HaversineSatellite.transferSwings(to:) / readCollectionData(at:) / readLastAudioSamples()
 <- [ObjC delegate] IOSHaversineTransferDelegate.collectionTransferDidFinishWith(data:collectionIndex:satelliteId:)
 <- HaversineTransferDelegate.handleDidFinish(data, index)          (Kotlin)
 <- PPCollection(data, index) -> PPCollection_createFromBinaryData  (PPCollection.o @0x0c)
      -> GSParseRecordsInRawData                                    (PPParsing.o @0x0)
 <- PPCollection_createAudioTimeline                                (PPCollection.o @0x3b4)
      -> [0x54] memcpy path (@0x448-0x48c)
      -> [0x53] DDRiceDecompressionDecoder_init / Channel_init /
                Channel_decodeDiff / Channel_nextWord                (@0x4c0-0x514)
 <- PPAudioTimeline.samples / sampleRateHz / isMultiPart / isFinalPart / collectionStartIndex
 <- MultipartCollection.addPart -> emitCompleteTransfer -> TransferStatus.TransferComplete(...)
```

Other notable symbols: `PPSatelliteEvent_deserializeNext`, `PPRingApplicationData_{serialize,deserialize,fingerprintMatches*}`, `mixBits32`, `HaversineAdvertisementData_parseManufacturedData` (6/8-byte manufacturer data: u32 + flag bytes incl. `inCollectionState`, `isMoving`, `needsServicing`, `truncatedCollectionCount`, `cacheableStateFingerprint`), `KMPHaversineSatelliteManager.programSatelliteWithApplicationData`, `removeDCBias` (Kotlin `util.kt`).

---

## 8. Evidence index

| Claim | Evidence |
|---|---|
| klib structure & deps | `*/default/manifest` (`depends=` lists both cinterop libs; ktor only for firmware-update download) |
| Codec | `DDRiceCompression.o` full disassembly (`extracted/cinterop-PPCommon-iosarm64/default/disasm/DDRiceCompression.txt`); call sites `PPCollection.o` @0x3b4–0x5a8 |
| Container/record types | `GSParseRecordsInRawData` (`PPParsing.o` @0x0) + jump table `__TEXT,__const@0xb68`; record names from `PPCommon` linkdata (`GSRawDataRecords_t`, `GSCompressedAudioDataRecord_t`, `GSUncompressedAudioDataRecord_t`, `GSCollectionMultiPartInfo_t`) |
| Audio payload layouts | `PPCollection_createAudioTimeline` field reads (@0x400–0x48c) cross-checked against cinterop struct metadata (`struct { unsigned int collectionStartIndex; unsigned int sampleRateHz; unsigned long sampleCount; void* samples; char isMultiPart; char isFinalPart; }`) |
| Telesto transport | `TelestoController.o` (12-byte ctrl, length-prefixed data, `pendingConfirmation`), `TelestoOperation.o` (24-byte request serialization), `HaversineTransferCollectionsOperation-*.o` @0x1b4 (`0x40020000\|index`, op=3), `HaversineReadLastAudioSamplesOperation.o` @0x1f8 |
| No crypto | Constant scan script over all `.a`/`bodies.knb` (negative); symbol greps; manifest dependency lists |
| Pairing write = bond trigger | `mobileapp/libindex/.../IndexPairing.ios.kt` (writes `0x00` to `DAAD3D52-…` then disconnects; `createBond`) |
| App data format | `__serialize_v1` (`PPRingApplicationData.o` @0x250, 141 bytes), `PPRingUser_init` (strlcpy 129) |
| TransferComplete fields | Kotlin `strings.knt`: `TransferCompletecollectionStartCountLongsamplesShortArraysampleRate…`; `MultipartCollection` `writeShortLe/readShortLe`, contiguity & sample-rate-mismatch checks |

---

## 9. Remaining unknowns

| Unknown | What would resolve it |
|---|---|
| Ring's actual ADC sample rate & typical k/maxPrefix values | One captured collection object (BLE snoop or a transferred recording); or ring firmware |
| Which audio record type (0x53 vs 0x54) current firmware emits | Same |
| At-rest storage format/encryption on the ring | Ring firmware (e.g., `HyperionSensing/firmware_releases` image disassembly) |
| Meaning of the u16 field at offset 0 of the compressed-audio record (reserved/version?) | A sample collection or firmware |
| Exact TELESTO op-code enum values other than read(3) | Firmware, or a GATT capture of a program/erase session |
| Advertisement byte semantics beyond the parsed fields | GATT/ADV capture |
| Whether Android build (`haversine-android`) differs | Out of scope artifact |

## 10. Independent-client implications

Already fully understood (implementable today from this report):
1. **Discover** — scan for manufacturer data matching the Haversine advertisement format (u32 fingerprint + flags; `inCollectionState` bit).
2. **Connect/pair** — connect; write `0x00` (with response) to `DAAD3D52-…` under service `607B5C9B-…` to trigger bonding; bonding is the only auth.
3. **Enumerate** — Telesto read `TELESTO_STORED_COLLECTION_INDEXES` / `COLLECTION_COUNT` (address map names known; numeric addresses for these two still need one capture).
4. **Download** — Telesto read `{op=0x03, addr=0x40020000|index}` over ctrl+data characteristics with per-chunk confirmations; reassemble via u32 length prefix.
5. **Decode** — TLV parse (§4) → record `0x54` = s16LE PCM + rate; record `0x53` = DDRice decode (§3 pseudocode) → u16 samples; stitch multi-part via `0x51` (`collectionStartIndex`, `isMultiPart`, `isFinalPart`); DC-bias removal + resample to 16 kHz client-side.
6. **Acknowledge/delete** — collection-count programming (`programCollectionCount`, `TELESTO_COLLECTION_COUNT`) and erase ops exist (`TELESTO_ERASE_MEMORY`); exact semantics need one firmware-side observation before destructive use.

Still requiring capture/firmware: numeric addresses for non-collection state, the ack cadence on the data channel in practice, and at-rest behavior.
