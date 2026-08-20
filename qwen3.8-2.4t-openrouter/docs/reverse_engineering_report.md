# Haversine / Pebble Index 01 — Reverse-Engineering Report

Artifacts analyzed (all `io.github.coredevices.haversine` version `03202f5`, Maven Central):

| Artifact | Contents | Extracted to |
|---|---|---|
| `haversine-iosarm64-03202f5.klib` | Kotlin Multiplatform library (IR + linkdata) | `artifacts/` |
| `haversine-iossimulatorarm64-03202f5.klib` | Identical IR/linkdata (verified byte-identical after unpack) | `artifacts/` |
| `haversine-iosarm64-03202f5-cinterop-PPCommon.klib` | `libPPCommon_static.a` — C library, full symbols | `extract/ppcommon_a/` |
| `haversine-iosarm64-03202f5-cinterop-haversineSatelliteLibrary.klib` | `libHaversineSatelliteLibrary.a` — Swift/C BLE stack | `extract/satlib_a/` |

Tools: Kotlin/Native 2.2.20 `klib dump-abi / dump-ir / dump-metadata` (`tools/haversine_abi.txt`, `tools/haversine_ir.txt`, `tools/ppcommon_meta.txt`, `tools/satlib_meta.txt`), objdump disassembly of every relevant object.

Evidence labels used below: **confirmed** (directly observed in code/metadata), **inferred** (multiple supporting observations), **speculation** (plausible, not established).

---

## 1. Executive answer

**What does the Index store?** The ring records "collections" — self-contained TLV blobs written to flash in a circular index space (`TELESTO_COLLECTION_BASE = 0x40020000 | collectionIndex`, u16 indices, range advertised via `TelestoStoredCollectionIndexes {u16 rangeStart, u16 rangeEnd}`). A collection bundles whatever the ring captured in one recording episode: motion/sensor records (gyro/accel calibration, VSR samples, stationary data, swing setup — it is a golf-swing analyzer ring), button-press sequences, a lifetime counter, and **audio** (record types 9/80 = uncompressed, 81 = compressed). Audio is stored inside the collection blob **either as raw PCM16 little-endian with an embedded sample rate, or as a custom lossless delta-delta + Golomb-Rice bitstream** — both decoded losslessly to the same PCM.

**What does it transmit?** Collections are transferred as complete objects (not incremental frames) over a custom request/response protocol ("Telesto") layered on three GATT characteristics of service `607B5C9B-3700-4E94-F44A-2DF900BCB0C3`: a 13-byte `TelestoRequest {u8 type; u32le address; u32le offset; u32le length}` written to the ctrl characteristic `C0EF558A-2058-FABF-A140-8D5ACDE50B39`, a 12-byte `TelestoResponse {u32le error; u32le info; u32le length}` notified back on it, and bulk payload bytes carried by the data characteristic `DAAD3D52-237C-90A7-B54B-8854A134D801`. A third characteristic `1D1F4039-23F5-33B2-C24E-704351F20585` carries phone→ring "system input" events (streaming enter/exit, force-collection-write, etc.).

**What does Haversine receive?** Per collection: a `ByteArray` blob (≤ 0xa0000 bytes enforced). It parses the collection envelope and TLV records in C (`PPCollection_createFromBinaryData` / `GSParseRecordsInRawData`), extracts the audio record, decompresses the Rice bitstream if present (`DDRiceDecompression*`), and produces `PPAudioTimeline {collectionStartIndex, isFinalPart, isMultiPart, sampleCount, sampleRateHz, samples: ShortArray}`. Large recordings arrive as multiple consecutive collections linked by a `collectionMultiPartInfo` record (type 82); Kotlin reassembles them in `MultipartCollection`, checking index sequence/contiguity.

**What does Haversine output to the app?** `TransferStatus.TransferComplete(satellite, collectionStartCount: Long, buttonSequence: String?, collectionIndex: Int, samples: ShortArray, sampleRate: Long, buttonReleaseTimestamp: Instant?, transferCompleteTimestamp: Instant, isContiguous: Boolean)` on a `SharedFlow`. `samples` is **mono PCM16 little-endian at the ring's native sample rate** (embedded in the collection, passed through verbatim — resampling and DC-bias removal are application-side steps; `removeDCBias(ShortArray)` ships in Haversine but is not called internally).

**Is recording data encrypted at rest?** **No** — no evidence of any crypto. Collections parse with plain structural code (envelope sizes, TLV, Rice bitstream); no key material, cipher, or MAC appears anywhere in PPCommon, the satellite library, or the Kotlin layer. (**confirmed**, see §5).

**Is it application-layer encrypted in transit?** **No.** Same negative evidence. Transport protection is only what iOS CoreBluetooth provides at the link layer if the devices are paired (**unknown** whether the ring requires LE pairing — see §5).

**Is there a registration-derived shared secret?** **No.** Registration ("programming") writes a plaintext `PPRingApplicationData` blob (ring user record) into the ring's `TELESTO_APPLICATION_DATA_STORE` via the same Telesto PROGRAM operation. No exchange, no secret, no key derivation anywhere in the artifacts. The persistent app state cached per ring (UserDefaults) is only name/versions/serial/application-data/fingerprint/`lastTransferEndIndex` — no secrets. (**confirmed**)

---

## 2. End-to-end data path

```
microphone (ring hardware; mic front-end unknown)
  -> ring firmware: 16-bit mono samples at device-native rate (value embedded per collection,
     e.g. observed field sampleRateHz; exact rates unknown without firmware/captures)
  -> ring storage: "collection" blob in flash at virtual address 0x40020000 | index
       audio as record type 80: [u32le len][u32le sampleRateHz][int16le samples]
       or record type 81:        [u32le len][u8 riceHdr][u32le bitCount][u32le sampleRateHz][bitstream]
       (lossless delta-delta + Golomb-Rice over int16 samples, step 2^k)
  -> Telesto READ_MEMORY request (13 B) on ctrl char C0EF558A
  <- TelestoResponse (12 B; error/info/length) notified on C0EF558A
  <- collection bytes streamed ring->phone on data char DAAD3D52,
     chunked to MTU, written-with-response, per-write acks drive the controller
  -> Haversine: ByteArray -> PPCollection C parser (envelope + TLV)
  -> if type 81: DDRice decoder -> int16 deltas -> double integration -> << k -> PCM16
     if type 80/9: raw PCM16le used directly
  -> MultipartCollection: parts appended little-endian into kotlinx.io.Buffer;
     ShortArray = flushBuffer(); sequence/contiguity checked
  -> TransferComplete(samples: ShortArray, sampleRate: Long, isContiguous: Boolean, ...)
  -> Pebble app: DC-bias removal -> resample to 16000 Hz -> PCM16 LE mono (per brief; app-side)
```

Formats at each known point:

| Stage | Format |
|---|---|
| Ring flash (audio) | PCM16 LE mono (type 80) or Rice-coded deltas of PCM16 (type 81), `sampleRateHz` embedded |
| BLE payload | raw collection blob bytes (no transport header; Telesto length accounting is in request/response) |
| Haversine internal | `ShortArray` mono PCM16, native ring sample rate |
| To app | same `ShortArray` + `sampleRate: Long`; app resamples to 16 kHz |

---

## 3. Codec analysis

**Encoding: custom lossless "delta-delta + Golomb-Rice" (record type 81), or uncompressed PCM16 LE (types 9/80).** Not Speex/Opus/ADPCM — none of those symbols exist. The separately published `io.github.coredevices.speex` ("Kotlin Speex", github.com/coredevices/kotlin-speex) is **not** a dependency of Haversine 03202f5 (checked POM + klib manifest) and plays no role here. **confirmed**

Evidence: `extract/ppcommon_a/DDRiceCompression.o` contains complete encoder + decoder (`DDRiceDecompressionDecoder*`, `DDRiceDecompressionChannel*`, dual-lane bit accumulator on the encode side) and `PPCollection.s` shows type 81 routed to it.

Decoder pseudocode (reconstructed from disassembly, sufficient to implement):

```text
# payload (after the record's u32le length):
#   hdr      = u8    lo nibble = k (Rice param), hi nibble = maxQ (unary escape limit)
#   bitCount = u32le at +1      (number of valid bits in bitstream)
#   rate     = u32le at +5      (sampleRateHz)
#   bits     = bitstream at +9, read MSB-first; sanity: 8*len - 72 <= bitCount

state: base = 0 (i16 path), diff = 0 (i16)      # double integrator

for each sample:
    if readBit() == 0:
        d = 0
    else:
        q = 1
        while True:
            if q >= maxQ:                       # unary escape -> literal
                d = readBits(16 - k)            # MSB-first
                break
            if readBit() == 0:                  # '10' -> q++
                q += 1
                continue
            if readBit() == 0:                  # '110' -> +q
                d = q
            else:                               # '111' -> (2^(16-k)) - q  (negative code)
                d = (65536 >> k) - q
            break
    if d >= (32768 >> k):                       # wrap into signed range
        d -= (65536 >> k)
    diff += d                                   # first integration
    base += diff                                # second integration
    sample = (base << k) & 0xFFFF               # int16; samples are multiples of 2^k
```

Notes (**confirmed** from `decodeDiff`/`nextWord`): the code space per diff has `2^(16-k)` values; diffs are transmitted modulo that space; output samples are multiples of `2^k` (encoder quantizes by k bits and stores the remainder losslessly only if it is zero — i.e. k-bit truncation is the only lossy step and happens in the ring's encoder). Type 80/9 payload is simply `[u32le sampleRateHz][int16le samples]` after the record length (**confirmed**, `PPCollection_createAudioTimeline`).

---

## 4. Frame/protocol structure

### 4.1 GATT topology (**confirmed**)

| Item | UUID | Role |
|---|---|---|
| Service | `607B5C9B-3700-4E94-F44A-2DF900BCB0C3` | Haversine service |
| Characteristic | `C0EF558A-2058-FABF-A140-8D5ACDE50B39` | Telesto **ctrl**: 13-byte request writes; 12-byte response notifications |
| Characteristic | `DAAD3D52-237C-90A7-B54B-8854A134D801` | Telesto **data**: bulk bytes both directions; notifications |
| Characteristic | `1D1F4039-23F5-33B2-C24E-704351F20585` | System-input events (phone→ring) |

Evidence: `HaversineUUID.o` rawValue jump table maps enum cases→strings; `CBConnectedPeripheralAdaptor.o` relocations tie each string to `sendTelestoCtrlBytes` (C0EF…), `sendTelestoDataBytes` (DAAD…), `sendSystemInputBytes` (1D1F…), and `handleUpdatedNotificationState` compares against DAAD… and C0EF….

### 4.2 TelestoRequest (13 bytes, packed; written to ctrl char) (**confirmed**)

| Offset | Size | Meaning |
| -----: | ---: | -------- |
| 0 | 1 | `type`: 0=NO_OP, 1=ERASE, 2=PROGRAM, 3=READ, 4=CANCEL, 5=ERASE_AND_PROGRAM |
| 1 | 4 | `address` (u32 LE, Telesto virtual address) |
| 5 | 4 | `offset` (u32 LE) |
| 9 | 4 | `length` (u32 LE; 0 = "whole object" for collection reads) |

### 4.3 TelestoResponse (12 bytes, notified on ctrl char) (**confirmed**)

| Offset | Size | Meaning |
| -----: | ---: | -------- |
| 0 | 4 | `error` (u32 LE; 0 = TELESTO_ERROR_NONE; also BAD_REQUEST, CANCELLED_BY_REQUEST (0x41 observed on cancel), CANCELLED_BY_WRITE) |
| 4 | 4 | `info` (u32 LE; e.g. transferEndIndex when finishing a transfer operation) |
| 8 | 4 | `length` (u32 LE; number of data-channel bytes that will follow for READ) |

### 4.4 Collection read sequence (**confirmed**)

1. `READ addr=0x40030005 (STORED_COLLECTION_INDEXES), offset=0, length=4` → 4-byte data payload `{u16le rangeStart, u16le rangeEnd}`.
2. App-side delegate picks first index (resume from persisted `lastTransferEndIndex` if inside the wrap-around window; batch ≤ 512 indices asserted).
3. For each index: `READ addr=0x40020000|index, offset=0, length=0` → response.length bytes arrive on the data characteristic (≤ 0xa0000 enforced client-side), delivered as `collectionTransferDidFinish(data, index)`.
4. `READ addr=0x4003000E (CURRENT_ADVERTISING_DATA), offset=0, length=10` → 10-byte advertising snapshot; first 2 bytes stripped, remaining 8 parsed by `HaversineAdvertisementData_parseManufacturedData` into `{needsServicing, inCollectionState, isMoving, hasDebugInfo, isDark, truncatedCollectionCount: u8, cacheableStateFingerprint: u32}`; decides whether to loop back to step 1 ("checking for new collections") or finish.
5. Transfer result: `HaversineTransferCollectionsResult {u16 transferEndIndex}` (persisted by the app as resume point).

Reliability: every ctrl/data write is with-response and must be acked (`pendingConfirmation` flags cleared only from `didWriteValueForCharacteristic`); protocol violations raise `TELESTO_CONTROLLER_ERROR_UNEXPECTED_{CTRL,DATA}_{INPUT,OUTPUT}`; data reception is only legal during READ (or a CANCEL of a READ); excess bytes beyond response.length are dropped with a logged warning. There is **no per-byte CRC/FEC**; integrity = BLE link CRC + write acks + structural validation (envelope size checks, TLV lengths, record-type dispatch, app-side sequence/contiguity checks).

### 4.5 Collection blob envelope (**confirmed**, `GSParseRecordsInRawData`)

| Variant | Detection | Size field | Records start |
|---|---|---|---|
| legacy LE24 | `data[3]==0` and `LE24(data[0..2]) == totalSize` | 24-bit LE | offset 4 |
| BE24 | `data[0]!=0xFF && data[3]!=0`, `BE24(data[0..2]) == totalSize` | 24-bit BE | offset 3 |
| FF | `data[0]==0xFF` | `u16le(data[1..2]) == totalSize` | offset 3 |

Record TLV loop: `[u8 type]`; for normal types `[u16le len][len-1 payload]`; for audio types 9/80/81 `[u32le len][len payload]`. Record map (confirmed from jump table in `PPParsing.o __const`): 1=deviceID, 2=gyroCal, 3=sensorTemps, 4=VSRSamples, 5..6,15..18=calibrations, 7/33/40=compressed sensor FIFO, 8/50=croppedStationary, **9=uncompressedAudio(legacy)**, 10=lifetimeCollectionCount(legacy), 11=swingSetup, 12=clubSettings, 34=stSensorConfig, 37=platformVersions, 38=userData, 39=applicationDataStore, 41=detector, 48/49=latestStationary(+version), 51/52=stationary/collection sensorConfigs, 53=swingTimeCorrection, **80=uncompressedAudio**, **81=compressedAudio**, **82=collectionMultiPartInfo**, **83=buttonPressSequence**, **84=lifetimeCollectionCount**.

Audio-relevant record payloads:

| Type | Payload |
|---|---|
| 80 / 9 | `[u32le len][u32le sampleRateHz][int16le samples × (len-4)/2]` |
| 81 | `[u32le len][u8 riceHdr][u32le bitCount][u32le sampleRateHz][bitstream]` (offsets relative to payload start) |
| 82 | `[u16 size][u32 startIndex][u8 isMultiPart][u8 isFinalPart]` |
| 83 | `[u16 size][u32 bitmap][u32 count]` → button-sequence string |
| 84 | `[u16 size][u32 count]` |

---

## 5. Cryptography analysis

| Layer | Verdict | Why |
|---|---|---|
| BLE link encryption | **unknown** (app cannot control it) | No pairing/bonding management code in the artifacts beyond CoreBluetooth defaults; whether the ring demands LE pairing is a firmware property. Nothing in the app layer adds or removes link encryption. |
| Haversine/application-layer encryption | **no** | Exhaustive string/symbol/IR sweep of all four artifacts: zero occurrences of CCCrypt/CommonCrypto/CryptoKit/SecKey/AES-*/ChaCha*/poly1305/HMAC*/CC_SHA*/ECC primitives. The 66 superficial grep hits are Swift mangling artifacts (`AES` = `Array<UInt8>` storage symbols, `SeAE` = `Decodable` witnesses). All payload structures parse as plain integers/bitstreams; Telesto has no nonce/tag/MAC fields; the 13-byte request leaves no room for authentication. |
| Storage-at-rest encryption (on ring) | **no** (as far as observable) | Collections arrive already in their plaintext TLV/Rice form and parse with no key input; PPCommon has no crypto; if the ring encrypted flash contents it would decrypt before BLE egress, but nothing on the phone side ever touches a key, and registration stores plaintext application data. |

---

## 6. Key-management analysis

* **Is there a per-ring shared secret?** No. Nothing key-like exists in any artifact.
* **How is it created?** N/A. Registration = `programSatelliteWithUserID(userId)`: `PPRingUser_init(String?)` → `PPRingApplicationData_init(user, UInt)` → `PPRingApplicationData_serialize` (plain serialization, size computed, no cipher) → `HaversineSatellite.programWithApplicationData(NSData)` → Telesto PROGRAM to `TELESTO_APPLICATION_DATA_STORE`. (**confirmed** from Kotlin IR + PPCommon metadata)
* **Where is it stored?** N/A for secrets. The app persists a Codable `CacheableState {satelliteName, platformVersions, serialNumber, sensorConfigVersion, applicationData, advertisedFingerprint, lastTransferEndIndex, cacheUpdate}` in `UserDefaults` keyed by peripheral UUID (`UserDefaultsCache`) — used for transfer resumption and change detection, not security.
* **How is it used?** N/A.
* **Does registration exchange it?** No — one-way plaintext write to the ring.
* **Does recording decoding depend on it?** No — the Rice decoder and TLV parser take only the payload bytes.

The brief's pairing anchor ("write 0x00 to DAAD3D52 with response during pairing") is consistent with this model: DAAD3D52 is the Telesto data characteristic; a 1-byte 0x00 write is most plausibly a Telesto NO_OPERATION data-channel write or link keep-alive. **inferred** — the exact trigger is not in these artifacts (it would be in the app or in `HaversineSatelliteManager` connection flow, which we did not need to fully unwind).

---

## 7. Relevant symbols / functions

**Chain to `TransferComplete`** (Kotlin, `coredevices.haversine`, all in `tools/haversine_ir.txt`):

```
CoreBluetooth didUpdateValue (data char)
→ TelestoController_receiveDataBytes (TelestoController.o:0x628)
→ _TransferOperation_handleReceivedDataFromChild (HaversineTransferCollectionsOperation-1b03…o:0x244)
   accumulates into buffer @ self+0xa007f (≤0xa0000)
→ _TransferOperation_handleCompletionFromChild (same object:0x310), phase 1 success @0x45c
→ delegate.collectionTransferDidFinish(ctx, data, size, index)   [self+0x60]
→ IOSHaversineTransferDelegate.collectionTransferDidFinish (Kotlin)
→ PPCollection(index, ByteArray) → PPCollection_createFromBinaryData (PPCollection.o)
→ PPCollection_createAudioTimeline (PPCollection.o) → GSParseRecordsInRawData (PPParsing.o)
   → type 81 → DDRiceDecompression decoder (DDRiceCompression.o)
→ PPAudioTimeline {sampleRateHz, samples: ShortArray, isMultiPart, isFinalPart, collectionStartIndex}
→ MultipartCollection.addPart(...) appends samples LE into kotlinx.io.Buffer
   (on sequence gap: logs "Sequence mismatch. Expected …, got …", flushes partial)
→ when isFinalPart: HaversineTransferDelegate.handleDidFinish → emitCompleteTransfer
→ buf = multipart.flushBuffer() (LE ShortArray); isContiguous = multipart.isContiguous()
→ TransferComplete(satellite, startIndex.toLong(), multipart.finalSequence, indices.last(),
     buf, multipart.sampleRate.toLong(), multipart.releaseTimestamp, Clock.System.now(), isContiguous)
→ _transferStatus MutableSharedFlow.emit(...)   [IR line 1409]
```

**Key symbols and offsets:**

| Symbol | Object | Address/Note |
|---|---|---|
| `_TelestoController_init/addOperation/ctrlBytesSent/dataBytesSent/receiveCtrlBytes/receiveDataBytes/close` | TelestoController.o | full state machine; controller struct 0x98 bytes |
| `__putTelestoRequestInOutbox` | TelestoController.o | 0x854 — serializes 13-byte request (`remainingSize = 0xd`) |
| `__completeOperationIfNecessary` | TelestoController.o | 0x444 — matches response (12 B) against outstanding op; READ completes when `receivedSize >= response.length`; cancel → error 0x41 |
| `_HaversineTransferCollectionsOperation_init` | HaversineTransferCollectionsOperation-1b03…o | 0x0 |
| `__TransferOperation_startNextChild` | same | 0x130 — phase switch; const request templates @0x718 (indexes read) and @0x730 (advertising read); inline collection-read request @0x1b0–0x1cc (`0x40020000 | index`) |
| `__TransferOperation_handleReceivedDataFromChild` | same | 0x244 — per-phase bounds: 4 / 0xa0000 / 0xa bytes |
| `__TransferOperation_handleCompletionFromChild` | same | 0x310 — resume window math, batch limit 0x201, per-index didFail on error |
| `_TelestoLengthPrefixedData_create` | TelestoTypes.o | 0x0 — `[u32le total=payload+4][payload]` |
| `GSParseRecordsInRawData` | PPParsing.o | envelope + TLV parser, record-type jump table @ `__const`+3608 |
| `PPCollection_createFromBinaryData`, `PPCollection_createAudioTimeline` | PPCollection.o | collection parse + audio extraction; `PPResult_t` union |
| `DDRiceDecompression*` | DDRiceCompression.o | Rice decoder (pseudocode in §3) |
| `HaversineAdvertisementData_parseManufacturedData` | HaversineAdvertisement-*.o | 8-byte advert payload → 10-byte struct |
| `HaversineTransferDelegate.emitCompleteTransfer` | main klib IR | line ~1340–1450 — TransferComplete construction |
| `MultipartCollection.addPart / flushBuffer / isContiguous` | main klib IR | LE sample appending, sequence-mismatch flush |
| `HaversineSatellite.readCollectionDataAt / readCollectionCount / programCollectionCount / programWithApplicationData / readLastAudioSamples…` | satlib_meta.txt line 651+ | ObjC API surface of the satellite object |
| `HaversineReadLastAudioSamplesResult` | satlib_meta.txt line 2724 | `{samples*, sampleCount, sampleRateHz, collectionCount, lastCollectionIndex, collectionsRead, platformVersions}` — direct "read last audio" path that bypasses full transfer |
| `TelestoStoredCollectionIndexes` | satlib_meta.txt line 1938 | `{u16 rangeStart; u16 rangeEnd}` |

**TelestoController struct layout** (inferred from all access patterns, consistent throughout):

```
+0x00 queueHead     +0x08 ctrlSendCb      +0x10 dataSendCb     +0x18 errorHandlerCb
+0x20 context       +0x28 isClosed(u8)    +0x2c outstandingRequestType(u32)
+0x30 lastRequestType(u32)
+0x38 ctrlOutbox: {bytesPtr, remainingSize, +0x48 pending(u8), request bytes @0x49..0x55}
+0x58 dataOutbox: {bytesPtr, remainingSize, +0x68 pending(u8)}
+0x78 currentResponse[12]   +0x88 currentResponseSize   +0x90 receivedDataSize
```

---

## 8. Evidence index

| Conclusion | Evidence |
|---|---|
| Service/characteristic UUIDs and roles | `HaversineUUID.o` cstring table + jump table `lJTI0_0`@0x6c (`0f 00 03 06 09 00 03 00`); `CBConnectedPeripheralAdaptor.o` relocations at 0x5f6c/0x645c/0x68f8 (send closures), 0x9240/0x9304 (notification-state compares), 0x1160 (service in init) |
| TelestoRequest/Response layouts | `tools/satlib_meta.txt` lines 1439–1477 (`TelestoRequest`, size 13, members type@0 bitfield, address@1, offset@5, length@9) and 1656–1690 (`TelestoResponse {error,info,length}`, size 12); `__putTelestoRequestInOutbox` @0x854 (`str x1,[x8,#0x11]!`, `mov w9,#0xd`, `stp x8,x9,[x0]`) |
| Operation type values | enum string order in TelestoController.o + code: data accepted only for types 3/4 (`receiveDataBytes` @0x66c–0x6ac), data outbox armed for 2/5 (`startNextOperationIfNecessary` @0x14c–0x194), cancel type 4 (`__putCancelRequestInOutbox` `orr x1,x9,#0x4`) |
| Write-with-response + MTU chunking | string "WARNING: Writing … which does not support writeWithResponse. Writes of this size have been observed to fail."; relocations `maximumWriteValueLengthForType:`@0x545c and `writeValue:forCharacteristic:type:`@0x5aec; `pendingConfirmation` semantics in TelestoController (cleared only by `*_bytesSent`) |
| Collection transfer phases/addresses | `TransferCollections.s`: templates @0x718 `03 05 00 03 40 00 00 00 00 04 00 00 00` (READ 0x40030005, len 4) and @0x730 `03 0e 00 03 40 00 00 00 00 0a 00 00 00` (READ 0x4003000E, len 10); inline `orr w8, w8, #0x40020000` @0x1b4; phase strings "Starting TRANSFER_OPERATION_PHASE_READ_*" |
| Max collection size 0xa0000 | `handleReceivedDataFromChild` @0x2c0–0x2d8 (`cmp x9, #0xa0, lsl #12`) |
| Batch limit 512 | `handleCompletionFromChild` @0x534 (`cmp w8, #0x201; b.hs assert`) |
| Audio record formats | `PPCollection.s` (`PPCollection_createAudioTimeline`), `PPParsing.s` (TLV loop, audio types use u32 length) |
| Rice codec behavior | `DDRice.s` decodeDiff/nextWord loops (unary q-escape, literal `readBits(16-k)`, wrap at `32768>>k`, double integration, final `<< k`) |
| No crypto | sweep results: 0 matches for all crypto primitive names across main klib (IR/ABI/metadata), `extract/ppcommon_a/*.o`, `extract/satlib_a/*.o`, klib archives (worklog Session 2) |
| Persistence (resume) contents | demangled `HaversineSatelliteState.CacheableState` initializers (`cacheUpdate, advertisedName, advertisedFingerprint, lastTransferEndIndex`, …), `UserDefaultsCache` symbols; `handleCompletionFromChild` phase-0 window math using `self+0x78` |
| TransferComplete construction | `tools/haversine_ir.txt` line 1409 (`CONSTRUCTOR_CALL TransferComplete.<init>` inside `emitCompleteTransfer`), args mapped field-by-field (§7) |
| Registration path | Kotlin IR `programSatelliteWithUserID` → `PPRingUser_init`/`PPRingApplicationData_*` (ppcommon_meta.txt) → `programWithApplicationData` (satlib_meta.txt line ~660); Telesto PROGRAM to APPLICATION_DATA_STORE (address constant name in HaversineTransferCollectionsOperation.c strings) |
| System-input channel | `HaversineSystemInputController.o` strings: `INPUT_INTERRUPT`, `INPUT_FORCE_COLLECTION_WRITE`, …; `sendSystemInputBytes` → 1D1F4039 |
| Speex not involved | `speex-iosarm64-905487f-dirty.pom` (name "Kotlin Speex", scm kotlin-speex); haversine klib manifest lists no speex dependency |

---

## 9. Remaining unknowns

| Unknown | Resolving artifact |
|---|---|
| Exact microphone sample rates the ring uses (field is passed through; no constant in these artifacts) | ring firmware image, or one real captured collection |
| Meaning of the 2-byte prefix stripped from the 10-byte advertising snapshot (likely BLE AD flags/manufacturer header) | GATT capture / firmware |
| Ring-side flash layout, collection lifecycle (when collections are freed — phone-side `programCollectionCount` suggests count programming, but semantics unverified) | firmware + live capture |
| Whether the ring enforces LE pairing / bonding (link encryption) | live pairing attempt / firmware |
| Exact behavior behind the brief's "write 0x00 to DAAD3D52 during pairing" (keep-alive vs NO_OP data write vs app-specific) | app binary (`Pebble Index` IPA) or GATT capture |
| Encoder quantization choice of `k`/`maxQ` per recording (decoder accepts anything) | firmware or sample captures |
| Record types 13–32/35 exact meanings (parser rejects most; unused in audio path) | firmware |
| How the app schedules transfers from the foreground/notification lifecycle | app binary |
| Contents/semantics of `TelestoDiagnosticsResult` data segments, reboot reasons, sensor streaming | firmware; PPRebootReasons.o/PPSatelliteEvents.o strings partially enumerate codes |

---

## 10. Independent-client implications

An independent iOS client can be built from this report. Per step:

1. **Discover an Index** — UNDERSTOOD. Scan for service UUID `607B5C9B-3700-4E94-F44A-2DF900BCB0C3`; advertisements carry parseable state (the 10-byte snapshot format incl. `inCollectionState`, `truncatedCollectionCount`, `cacheableStateFingerprint` is decoded except the 2-byte prefix). Advertisement name conventions for filtering: minor unknown.
2. **Connect** — UNDERSTOOD. Standard CoreBluetooth connect; discover the service and the three characteristics; subscribe to notifications on ctrl (`C0EF558A…`) and data (`DAAD3D52…`). Whether the ring additionally requires LE bonding at OS level: unknown (test empirically).
3. **Authenticate/pair** — NO AUTHENTICATION EXISTS. Optional registration = write plaintext `PPRingApplicationData` (user record) via Telesto PROGRAM to `TELESTO_APPLICATION_DATA_STORE` — serialization format fully visible in `ppcommon_meta.txt`. The observed 0x00 write to the data characteristic during pairing is not required by the protocol itself (inferred keep-alive).
4. **Enumerate recordings** — UNDERSTOOD. Telesto READ `0x40030005` (4 bytes → `{rangeStart, rangeEnd}` u16 wrap-around indices); optionally READ `0x4003000E` for current advertising state; `TELESTO_COLLECTION_COUNT` / `LIFETIME_COLLECTION_COUNT` addresses are named and reachable. Per-collection metadata (audio vs motion, multipart info, timestamps) is only known after downloading the blob (type 82/83/84 records) — there is no server-side directory.
5. **Download one** — UNDERSTOOD. Telesto READ `0x40020000|index` with length 0; receive `response.length` bytes on the data characteristic; honor the write-ack driven flow (each write with response; do not pipeline while a confirmation is pending). Full request/response/framing/state-machine semantics are specified above.
6. **Decode to PCM** — UNDERSTOOD. Parse envelope (3 variants), TLV records, audio record 80/9 (raw PCM16 LE + rate) or 81 (Rice decoder pseudocode provided; lossless to multiples of 2^k). Multi-part reassembly = concatenate parts in index order between `startIndex` and the part marked `isFinalPart`, checking contiguity.
7. **Acknowledge/delete safely** — PARTIALLY UNDERSTOOD. The library exposes `programCollectionCount(count)` and the Telesto ERASE/PROGRAM ops; the transfer protocol's `transferEndIndex` persistence indicates the app advances a "consumed up to" watermark rather than deleting per-collection, and the ring advertises new `rangeStart` values afterwards. Exact ring-side deletion semantics (does programming the count free flash?) need a firmware read or a live experiment before an independent client mutates ring state.

**Bottom line:** everything needed for read-only capture and decoding (steps 1–2, 4–6) is specified in this report with byte-level precision; steps 3 and 7 are low-risk (no security) but should be validated against live hardware, and the ring firmware remains the single artifact that would close all remaining gaps.
