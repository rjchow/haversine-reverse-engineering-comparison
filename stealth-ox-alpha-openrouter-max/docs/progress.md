# Haversine RE Progress Log

Task: reverse-engineer haversine-iosarm64-03202f5.klib and haversine-iossimulatorarm64-03202f5.klib
Goal: determine recording format from Pebble Index ring, codec, framing, crypto/key management.
Full brief: brief.md (in this dir).

## Status: ANALYSIS COMPLETE — writing REPORT.md

## Plan (phases from brief)
- [x] Phase 0: setup, download artifacts
- [x] Phase 1: unpack klibs, inventory members
- [x] Phase 2: symbols & strings inventory
- [x] Phase 3: locate TransferComplete creation, trace call chain backward
- [x] Phase 4: identify audio codec (DDRice codec fully reconstructed)
- [x] Phase 5: framing reconstruction (collection TLV + Telesto transport)
- [x] Phase 6: crypto analysis (NO app-layer crypto found)
- [x] Phase 7: persistent state analysis (no secrets stored)
- [x] Phase 8: device vs simulator comparison (identical logic)
- [x] Final: write report (REPORT.md)

## Status: COMPLETE. REPORT.md written. PROGRESS.md retained as evidence log.

## Key facts from brief (anchors)
- App receives TransferStatus.TransferComplete with ShortArray samples + sampleRate
- App then: DC removal -> resample -> 16k -> LE PCM16 mono
- Haversine BLE service 607B5C9B-3700-4E94-F44A-2DF900BCB0C3, char DAAD3D52-237C-90A7-B54B-8854A134D801
- Pairing: write single byte 0x00 with response
- Artifacts at repo1.maven.org io.github.coredevices.haversine

## Findings

### Architecture (KNOWN, Phase 1-2)
- .klib = zip with Kotlin/Native serialized IR (ir/bodies.knb etc.) + linkdata. NOT plain LLVM bitcode files; custom container.
- Haversine Kotlin lib is THIN GLUE over two native C interop libs (see manifest `depends=`):
  - `io.github.coredevices.haversine:haversine-cinterop-haversineSatelliteLibrary` (BLE satellite manager, Telesto structs)
  - `io.github.coredevices.haversine:haversine-cinterop-PPCommon` (PPCollection, PPAudioTimeline, PPRingUser, PPRingApplicationData)
- Actual audio decode happens in C: `PPCollection_createFromBinaryData(data) -> PPCollection` then `PPCollection_createAudioTimeline -> PPResultAudioTimeline_t` (UShort samples + sampleRateHz + isMultiPart + isFinalPart + collectionStartIndex), memcpy'd to Kotlin ShortArray.
- Other deps: ktor-client (firmware update download from GitHub), kotlinx-serialization-json, kermit logging, atomicfu, kotlinx-io.

### Key classes (from strings.knt)
- HaversineTransferDelegate: consumes transfer events (WillTransfer(range, satellite), DidFinish(data, index), DidFail(error)), maintains lastSuccessfulCollectionIndex StateFlow, currentCollection: MultipartCollection.
- MultipartCollection: startIndex, buffer (kotlinx-io Buffer), indices Set, _sampleRate UInt, releaseTimestamp, isContiguous, isMultiPart, isFinalPart, finalSequence. addPart(index, sequence, timestamp, timeline: PPAudioTimeline) writes samples via writeShortLe; flushBuffer reads readShortLe -> ShortArray. Error msgs: 'Part with index already added', 'Sample rate mismatch', 'Multipart collection is not contiguous. startIndex=, indices=', 'Buffer size must be even to read 16-bit samples'.
- TransferStatus variants: TransferStarted, TransferTypeDetermined(isAudio, buttonSequence, collectionStartIndex, collectionIndex, final, advertisementReceivedTimestamp, lifetimeCollectionCount), TransferInProgress(currentCollectionIndex), TransferComplete(collectionStartCount, samples, sampleRate, buttonReleaseTimestamp, transferCompleteTimestamp, isContiguous), TransferFailed(exception), IrrecoverableDataDetected(collection).
- removeDCBias(data: ShortArray) exists in Kotlin.
- PPCollection fields: index, data, unixTime, audioTimeline, buttonPressSequence, lifetimeCollectionCount. Uses PPCollection_createFromBinaryData / _unixTime / _buttonPressSequence / _createAudioTimeline / _freeAudioTimeline / _free.
- PPAudioTimeline(wrap PPResultAudioTimeline_t): sampleRateHz UInt, sampleCount ULong, isMultiPart, isFinalPart, collectionStartIndex, samples ShortArray (memcpy from UShortVarOf).
- Firmware update URL: https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json (org = HyperionSensing).
- Programming/pairing: KMPHaversineSatelliteManager.programSatelliteWithApplicationData -> PPRingUser_t (uid from userId string) + PPRingApplicationData_t serialize -> programWithApplicationData. PPRingApplicationData has fingerprintMatchesFailsafe / fingerprintMatchesUserId. NO crypto/key material seen in Kotlin layer so far.
- No AES/encrypt/decrypt/key/nonce strings seen in Kotlin IR strings so far.

### CODEC FULLY RECONSTRUCTED (Phase 4) - from libPPCommon_static.a DDRiceCompression.o (iosarm64)
'DDRice' = custom Rice/unary-coded SECOND-ORDER DELTA codec with error feedback:

Audio blob v1 layout (pointed to by collection struct; parsed in PPCollection_createAudioTimeline @0x3b4):
| Off | Size | Meaning |
|----:|----:|---------|
| 0 | 4 | byteLength (u32 LE) |
| 4 | 1 | config byte: low nibble k (LSBs dropped), high nibble maxPrefix (escape threshold) |
| 5 | 4 | compressedBitCount (u32 LE); validated: byteLength*8 - 72 >= compressedBitCount |
| 9 | 4 | sampleRateHz (u32 LE) |
| 13 (0xd) | ... | bitstream, MSB-first within bytes |

Codebook (signed 2nd difference d2, folded to 16-k bits):
- '1' -> d2=0 (1 bit)
- '0'*n '1' s -> d2 = +(n+1) if s=0, -(n+1) if s=1 (n+2 bits), n < maxPrefix
- maxPrefix zeros (escape) -> raw (16-k)-bit folded value

Decoder state/channel (per collection): sum1, sum2 (u16). Per word: sum2 += d2; sum1 += sum2; output_sample = (sum1 << k) & 0xFFFF (u16 LE).
Encoder: residual feedback: acc = wrap16(sum2 + sample + 2^(k-1)); qv = acc >> k; d2 = qv - 2*qv_prev + qv_prev2; Rice-encode d2; sum2 += sample - (qv<<k).
So ring stores audio quantized to (16-k) significant bits, 2nd-order delta, Rice coded. LOSSY (k LSBs discarded).

PPCollection_createAudioTimeline has TWO paths:
- v1/legacy path (ptr at collection+0x109+0): Rice blob above -> decoded u16 samples; sampleRate from header.
- v2 path (ptr at collection+0x109+0x10 non-NULL): struct {u32 @+2 = sampleRateHz, u8 @+6 = isMultiPart, u8 @+7 = isFinalPart}; audio blob at +0: u32 len; memcpy samples from blob+8, count len-4; sampleCount = (len-4)/2. Samples appear to be raw PCM16 already (need blob layout from deserializer to confirm 8-byte prefix).
- Result struct PPResultAudioTimeline_t: sampleCount, samples*, sampleRateHz, isMultiPart, isFinalPart, collectionStartIndex.

Collection struct size 0x1158 (4440) bytes. Field at +0x109 holds ptr to audio-related sub-struct.

### Artifacts inventory
- artifacts/haversine-{iosarm64,iossimulatorarm64}-03202f5.klib (main Kotlin)
- artifacts/haversine-{t}-03202f5-cinterop-PPCommon.klib -> contains targets/*/included/libPPCommon_static.a (C codec!) + cstubs.bc
- artifacts/haversine-{t}-03202f5-cinterop-haversineSatelliteLibrary.klib -> contains libHaversineSatelliteLibrary.a (BLE satellite mgr C lib)
- sources jar is EMPTY (manifest only). cinterop klibs NOT under own maven paths, but published as classifier-style files under haversine-iosarm64/03202f5/.
- extracted/ has all unzipped; disasm of PPCollection.o and DDRiceCompression.o done (objdump -dr).
- libPPCommon objects: DDRiceCompression.o, PPSatelliteEvents.o, PPParsing.o, PPRebootReasons.o, PPBluetoothUtils.o, PPTypes.o, PPRingApplicationData.o, PPCollection.o
- Key PPCommon symbols: PPCollection_{alloc,createFromBinaryData,free,createAudioTimeline,freeAudioTimeline,unixTime,buttonPressSequenceString,lifetimeCollectionCount,applicationDataStore,hardwareSerialNumber,platformVersions}, DDRice*, PPRingApplicationData_{serialize,deserialize,init,fingerprintMatches*}, PPSatelliteEvent_{deserializeNext,description}, GSParseRecordsInRawData

### External context
- mobileapp (coredevices) uses io.github.coredevices.haversine:haversine c11a7b6; has experimental ring module with DocumentEncryptor (app-side storage encryption, NOT transfer), RingPairing.kt, RecordingProcessor etc.
- kotlin-speex exists (coredevices/kotlin-speex) but is NOT a haversine dependency; likely unrelated to Index transfer path (verify).
- HyperionSensing/firmware_releases core_ring branch: only haversine_update.json with base64 firmware image. No source.

### COLLECTION CONTAINER FORMAT FULLY RECONSTRUCTED (Phase 5) - from GSParseRecordsInRawData + jump table
GSParseRecordsInRawData(obj=collection+1, data, len) parses 'GS raw data records':

Container variants (collection binary data):
- A1: [u8 0xFF][u16 LE len][records...]  (len = bytes after header)
- A2: [u24 BE len][records...]
- B:  [u32 LE len][records...] (top byte must be 0; len = total)

Record: [u8 type][u16 LE reclen][payload(reclen-1 bytes)] — NOTE reclen INCLUDES the type byte.
Special u24-length records (types 0x4d, 0x54): [u8 type][u24 LE len][payload(len)] (len excludes type).
Unknown type or bad length -> error 6. Trailing garbage -> error.

Record type map (from jump table __TEXT,__const of PPParsing.o, verified):
0x01 impactTimestamp, 0x02 UTC, 0x03 deviceID, 0x04 magSamples, 0x05 haccel2Cal, 0x06 VSRSamples,
0x07 gyroCal, 0x08 accelCal, 0x09 multiAccelSamples, 0x0a swingSetup, 0x0b targetLineAim,
0x0c sensorTemperatures, 0x0d gyro2Cal, 0x0e accel2Cal, 0x0f magCal, 0x10 IMUSamples,
0x13 allSensorCalibrations, 0x14 haccel1Cal, 0x21 clubSettings, 0x24 stFifoFirmwareCompressed,
0x25 stFifoCompressed, 0x26 userData, 0x27 platformVersions, 0x28 stSensorConfig,
0x2c applicationDataStore, 0x2d detector, 0x31 stationaryDataSensorConfigs, 0x32 croppedStationaryData,
0x33 latestStationaryDataVersion, 0x34 latestStationaryData, 0x38 collectionSensorConfigs,
0x4d buttonPressSequence [u24 len], 0x51 collectionMultiPartInfo, 0x52 swingTimeCorrection,
0x53 compressedAudioData [u16 len], 0x54 uncompressedAudioData [u24 len]

AUDIO RECORDS (the answer to 'what is transmitted'):
- type 0x53 compressedAudioData payload: [u16 reserved/version (=0 expected)][u8 config][u32 LE compressedBitCount][u32 LE sampleRateHz][bitstream...]
  config byte: low nibble k = # LSBs dropped (quantization), high nibble maxPrefix (Rice escape threshold)
  -> DDRice decode (see above) -> s16 LE samples, sample_i = (sum1 << k) & 0xFFFF. LOSSY.
- type 0x54 uncompressedAudioData payload: [u32 LE sampleRateHz][s16 LE PCM samples...]
- type 0x51 collectionMultiPartInfo payload: [u32 LE collectionStartIndex][u8 isMultiPart][u8 isFinalPart]

PPCollection struct: { u8 ok; GSRawDataRecords records (36 ptr fields @+9..+0x121 in PPCollection); rawdata ptr/len @0x130; ... } size 0x1158.
PPCollection_createAudioTimeline: prefers uncompressedAudioData (v2) if present, else decodes compressedAudioData (v1 Rice).
Result PPResultAudioTimeline_t: {u32 error; u32 collectionStartIndex; u32 sampleRateHz; u64 sampleCount; void* samples; u8 isMultiPart; u8 isFinalPart}

Satellite event stream (PPSatelliteEvent_deserializeNext): [u16 LE size][u8 eventCode][fixed-size payload (argumentSizeForCode, max 10 bytes copied)]

## TELESTO TRANSPORT (Phase 5 cont.) - libHaversineSatelliteLibrary.a (Swift+C)
- Swift lib 'HaversineSatelliteLibrary' (build path haversine-kmp/haversine/HaversineSatelliteLibrary, Xcode 16.1). C core: TelestoController.c, HaversineLinkController.c, HaversineTransferCollectionsOperation.c, HaversineAdvertisement.c.
- BLE service 607B5C9B-3700-4E94-F44A-2DF900BCB0C3; Telesto ctrl char + Telesto DATA char DAAD3D52-237C-90A7-B54B-8854A134D801 (CBConnectedPeripheralAdaptor send/subscribe).
- TelestoController (C): op queue. Ctrl channel: fixed 12-byte messages (buf @ctrl+0x78, count @+0x88). Data channel: 12-byte header incl. u32 total length @+0x80, then payload streamed to op callback; per-chunk flow control via pendingConfirmation ack.
- TelestoRequest (24B C struct): {u8 op; u32 address LE; u64 0; u64 0}. op=3 = TELESTO_READ_MEMORY (observed).
- TELESTO_COLLECTION_BASE = 0x40020000. Collection N read as ONE object: {op=3, addr=0x40020000|N} -> length-prefixed data -> TLV container. readLastAudioSamples uses same address scheme with latest index.
- Other names recovered: TELESTO_STORED_COLLECTION_INDEXES, COLLECTION_COUNT, LIFETIME_COLLECTION_COUNT, APPLICATION_DATA_STORE, UNIX_TIME, ERASE/PROGRAM/ERASE_AND_PROGRAM_MEMORY, CANCEL_OPERATION, CURRENT_ADVERTISING_DATA, PLATFORM_VERSIONS, SERIAL_NUMBER, SENSOR_0_*, CRASH_COREDUMP, RECENT_SATELLITE_EVENTS, VIRTUAL_ADDRESS_BASE, LENGTH_INFER_FROM_PREFIX.
- Swift API: readCollectionCount(), readCollectionData(at:), readLastAudioSamples()->([UInt16],UInt32), program(applicationData:), programCollectionCount(), programFirmware, clear/eraseApplicationData, transferSwings(to:).
- Transfer flow: read stored indexes -> per index: Telesto read 0x40020000|idx (cap ~0xA0000) -> collectionTransferDidFinish(data, index, satelliteId) -> Kotlin.

## PAIRING / KEY MGMT (Phase 6-7)
- App iOS pairing (mobileapp libindex IndexPairing.ios.kt): connect -> find service+DAAD3D52 char -> write 1 byte 0x00 with response -> disconnect. Write is a BOND TRIGGER (forces CoreBluetooth bonding); no app secret. Bonding = only crypto relationship.
- Programming: programSatelliteWithUserID(userId) -> PPRingUser_t{uid} + PPRingApplicationData_t{u32 version=1, u64 timestamp, char userId[129]} = 141 bytes -> Telesto program to TELESTO_APPLICATION_DATA_STORE.
- fingerprint = mixBits32 (custom fmix-style 32-bit hash, NOT crypto) over app data; fingerprintMatchesUserId/Failsafe/NoUser match advertisements to paired ring.
- Persistent state: CollectionIndexStorage.lastSuccessfulCollectionIndex only (app prefs). Swift caches CacheableState{advertisedData, proximity} in UserDefaults. NO keys/secrets/tokens.

## CRYPTO SCAN RESULT (Phase 6)
- Scanned all libs + bodies.knb for AES s-box/inv, SHA-256 K/IV, SHA-1/MD5 init, ChaCha sigma, CRC32 tables/poly, P-256, Poly1305, Curve25519: NO genuine hits (matches were Swift metadata/jumptable/float false positives).
- No crypto symbols; deps only CoreBluetooth/Foundation/darwin/posix. programFirmware(skipVerification:) = read-back verify, not signature crypto.
- CONCLUSION: NO application-layer encryption in the iOS transfer path. Recordings travel as-is (Rice-coded or PCM16) inside TLV collections over the BLE-encrypted link.

## Integrity mechanisms
- BLE link CRC; Telesto length prefixes + per-chunk pendingConfirmation acks + error codes; container exact-length validation (unknown type -> err 6, trailing garbage -> err); audio v1 bitCount sanity check; Kotlin 5MB truncation, empty-data and contiguity checks. NO app-layer CRC/checksum/FEC.

## Sample rate
- Data-driven: v1 audio record header u32, v2 uncompressed record u32 @payload+0. No hardcoded rate anywhere. App resamples to 16k. Ring's actual ADC rate unknown from binaries.

## Device vs simulator (Phase 8)
- Identical except native_targets. C libs same source, different arch slice.

## Evidence file map
- extracted/cinterop-PPCommon-iosarm64/default/disasm/DDRiceCompression.txt
- extracted/cinterop-PPCommon-iosarm64/disasm/{PPCollection,PPParsing,PPRingApplicationData,PPSatelliteEvents,PPTypes}.txt
- extracted/cinterop-haversineSatelliteLibrary-iosarm64/disasm/{TelestoController,TelestoOperation,ReadLastAudio,HaversineTransferCollectionsOperation-*}.txt
- extracted/iosarm64/default/ir/strings.knt
- Record-type jump table: PPParsing.o __TEXT,__const @0xb68 (84 entries, parsed)

- Download cinterop klibs from Maven (haversine-cinterop-PPCommon, haversine-cinterop-haversineSatelliteLibrary, both targets) -> contain C header defs/struct layouts.
- Look for PPCommon source on GitHub (HyperionSensing / CoreDevices orgs).
- Parse linkdata .knm for full metadata; check bodies.knb for constants.
- Verify no crypto in transfer path; check C library for codec (ADPCM etc.).

## Environment notes
- workdir: isolated benchmark workspace
- artifacts dir: artifacts/
- extracted dir: extracted/
- tools available: check with bash (llvm tools, python3, etc.)
