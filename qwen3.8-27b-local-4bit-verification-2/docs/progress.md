# Haversine klib RE — Progress Log

Run label: **the second run of local qwen 3.8 27b 4 bit for verification**

Goal: answer the brief's protocol questions (audio format, codec, framing, crypto, key management) with evidence, and produce a final technical report (`REPORT.md`).

## Status: IN PROGRESS (Phase 2/3 done — native C found in cinterop klibs)

## Environment
- file, unzip, strings, nm, otool, dwarfdump, python3 (3.12, capstone available) all OK; no llvm-*/r2/kotlin; network to Maven+GitHub allowed by sandbox

## Plan
- [x] 1. Inventory available tools
- [x] 2. Download both .klib artifacts (artifacts/)
- [x] 3. Unpack klibs: IR files (bodies.knb, irDeclarations.knd, strings.knt, types.knt, signatures.knt) + linkdata .knm + manifest (abi 2.2.0, compiler 2.2.20); deps: kotlinx-serialization-json, kermit, ktor, atomicfu, cinterop-haversineSatelliteLibrary, cinterop-PPCommon
- [x] 3b. BONUS: found & downloaded haversine-iosarm64-03202f5-cinterop-*.klib from Maven Central; they contain the actual native libs: libHaversineSatelliteLibrary.a (Swift/C: 34 .o with DWARF) + libPPCommon_static.a (8 .o, no DWARF) + cstubs.bc (LLVM bitcode)
- [x] 4. Partial: dumped cinterop knm = full C API/struct layout (see Findings below)
- [ ] 5. Locate TransferComplete creation / samples pipeline (call chain)
- [ ] 6. Identify audio codec (byte->ShortArray transformation) — prime candidate: delta+Rice (DDRiceCompression)
- [ ] 7. Reconstruct framing (Telesto protocol: length prefixes, request/response, phases)
- [ ] 8. Crypto analysis (search AES/ChaCha in binaries; check UpdateCache op, address seed)
- [ ] 9. Persistent state / key management (PPRingApplicationData fingerprint; address seed)
- [ ] 10. Compare simulator vs device binary
- [ ] 11. Write final REPORT.md

## KEY FINDINGS (so far)
- Repo (private, 404): github.com/coredevices/haversine-kmp; build path `<build-root>/haversine/HaversineSatelliteLibrary`; Sources/Shared/*.c (C), Sources/Apple/Operations/*.swift (Swift glue), Xcode 16.1, iOS SDK 18.1, clang 16, CI runner
- Protocol name: **Telesto** (TELESTO_COLLECTION_BASE/COUNT/MAX, TELESTO_APPLICATION_DATA_STORE, TELESTO_ERASE_AND_PROGRAM_MEMORY, TELESTO_CRASH_COREDUMP, TELESTO_CROPPED_STATIONARY_DATA, TELESTO_ERROR_*, TelestoLengthPrefix, TelestoStoredCollectionIndexes, TelestoController/Operation/Types)
- **Record format (PPCommon cinterop)**: every record = `unsigned short size` (LE?) + payload. Record types incl: GSUncompressedAudioDataRecord_t{data[]}, GSCompressedAudioDataRecord_t{data[]}, GSSTFifoCompressedRecord_t{dataHeader{signed char sampleTimeLSP}; fifoCompressedRecord[]}, GSSTFifoFirmwareCompressedRecord_t, GSSTSensorConfigRecord_t{configurationVersion,accelBDR,gyroBDR,magBDR}, GSRawDataRecords_t{IMUSamples,multiAccelSamples,VSRSamples,magSamples,deviceID,UTC,impactTimestamp,calibrations...,stFifoCompressed,platformVersions,userData,applicationDataStore,detector,latestStationaryData,croppedStationaryData,swingTimeCorrection,buttonPressSequence,uncompressedAudioData,compressedAudioData,collectionMultiPartInfo,lifetimeCollectionCount}, GSCollectionMultiPartInfo_t{uint startIndex; char isMultiPart; char isFinalPart}, GSButtonPressSequence_t{uint sequence; uint count}, GSLifetimeCollectionCount_t{uint count}
- **PPResultAudioTimeline_t** = {uint collectionStartIndex; uint sampleRateHz; ulong sampleCount; void* samples; char isMultiPart; char isFinalPart}  <-- feeds TransferComplete(samples, sampleRate)
- **PPCollection C API**: createFromBinaryData, createAudioTimeline, freeAudioTimeline, hardwareSerialNumber, applicationDataStore, platformVersions, unixTime, lifetimeCollectionCount, buttonPressSequenceString
- **ST FIFO parser**: PPCreateCompressedSTFIFOParser(parser,rawData,rawDataSize) + PPParseCompressedSTFIFOData(parser,outSamples,outCount) + PPFreeCompressedSTFIFOParser
- **DDRiceCompression**: Encoder{init,attachOutputBuffer,appendBits,close,compressedBitCount} + Channel{init,encodeWord} + Decoder{init,readBit,readBits,noBit} + Channel{init,decodeDiff,nextWord,prevWord}  => delta+Rice variable-length integer codec
- PPRingApplicationData: {fingerprint, userUid, hasUser}; fingerprintMatchesUserId/NoUser/Failsafe; serialize/deserialize(deserializeFromCollectionData)
- **PPGenerateUniqueStaticRandomBluetoothAddress(addressSeed)** + PPTinyBitMixer (+_mixerStage): MAC derived from per-device seed; PP_REBOOT_INVALID_ADDRESS_SEED reboot code
- Reboot reasons: PP_COMPRESSION_FAILURE (compression on ring!), PP_ADC_SAMPLE_RATE_OUTSIDE_BOUNDS (audio ADC), flash storage mgr w/ failsafe (PP_REBOOT_FLASH_*), PP_REBOOT_RESTORE_CODE_AFTER_COLLECTION_XOR, PP_REBOOT_BLE_TELESTO_OPERATION_COMPLETE_1/2
- Hardware versions: MAJOR_VERSION_1..6, MAJOR_VERSION_X, **MAJOR_VERSION_AUDIO**
- HaversineReadLastAudioSamplesOperation_init: calls f(1, 0x50c0); struct size 0x50c0+? ; sentinel 0x7fc00000 @ +0x1090
- Haversine ops (C): HaversineOperation (init/state/cancel/handle...), HaversineLinkController (init/free/state/updateTime/handleConnectionEstablished/Terminated), HaversineOperationDelegateTable, HaversineLinkTransportDelegateTable (C-side transport callback table)
- Transfer op phases (strings): PHASE_READ_COLLECTION_COUNT, PHASE_READ_LAST_COLLECTION, PHASE_READ_MULTIPART_COLLECTIONS; HAVERSINE_ERROR_*: CONFIG_ERROR, END_ENCOUNTERED, LOG_DATA_ALREADY_SAVED, MISSING_DATA, NONE, OVERFLOW_ERROR, UNEXPECTED_DATA_SIZE, UNEXPECTED_VERSION, UNKNOWN
- Knm 1 of satlib: cnames TelestoLengthPrefix, hardwareVersion_t{GSInt hardwareVersionMajor/Minor, firmwareVersionMajor/Minor}, HaversineSystemInputParameters{currentUnixTimeGetter}, HaversineLinkController_state/updateTime

## Log (session 1)
- 21:26 downloaded klibs; unpacked; manifest: abi 2.2.0, kotlin 2.2.20, deps incl cinterop-haversineSatelliteLibrary + cinterop-PPCommon, kotlinx-serialization-json, kermit, ktor, atomicfu
- 21:28 downloaded cinterop klibs from Maven -> contain libHaversineSatelliteLibrary.a (34 .o, WITH DWARF, Sources/Shared/*.c + Swift) and libPPCommon_static.a (8 .o, no DWARF) + cstubs.bc
- 21:3x dumped cinterop knm metadata = complete C API:
  * Telesto protocol = virtual-memory-address request protocol: TelestoRequest{request(dataToSend),address,length}; types TELESTO_NO/ERASE/PROGRAM/READ/ERASE_AND_PROGRAM_MEMORY, TELESTO_CANCEL; length semantics TELESTO_LENGTH_INFER_FROM_PREFIX / INDEFINITE; TelestoResponse{uint error; uint info; uint length} = 12-byte ctrl frame; TelestoLengthPrefixedData{uint length; bytes[]}
  * TelestoController: dual channels ctrl/data; ctrl frames = 12B (error,info,length); data channel delivers payload bytes; outbox of ops (ctrl/data);
  * HaversineLinkController C API: init/free/state/updateTime/handleConnectionEstablished|Terminated/addOperation/commitOperations/cancelOperation/handleTransportError/receiveTelestoCtrlBytes/receiveTelestoDataBytes/...bytesSent; transport delegate {sendTelestoCtrlBytes, sendTelestoDataBytes, sendSystemInputBytes, ctx}; op delegate {handleReceivedData, handleCompletion, ctx}
  * Operations (C): HaversineSensorStreamOperation_init(+Uncalibrated, +WithRawDataCollectionEnabled; collectedRawData; sensorConfigurations; sensorCalibrations), HaversineSensorServiceOperation_init(hwMajorVer, appDataReadSize), HaversineUpdateCacheOperation_init, **HaversineTransferCollectionsOperation_init(delegate{firstCollectionToTransferInRange, willTransferCollectionsInRange, collectionTransferDidFinish, collectionTransferDidFail, ctx}, lastTransferEndIndex)**, HaversineSuotaOperation_init(imgMajor, imgMinor, img, imgSize, force, skipVerification; shouldRetry), HaversineReadDebugInfoOperation, HaversineReadRxRSSIOperation(averaging), HaversineDiagnosticOperation(unixTimeGetter), HaversineReadLastAudioSamplesOperation
  * HaversineReadLastAudioSamplesResult = {samples*, sampleCount, sampleRateHz, collectionCount, lastCollectionIndex, collectionsRead, cacheableState{platformVersions, sensorConfigVersion, serial[6], applicationData[4096], appDataSize}, rxRSSI, txRSSI, batteryVoltage, accel1Metrics, gyro1Metrics}
  * HaversineSatellite (Swift): programFirmware/service/programWithApplicationData/eraseApplicationData/eraseDebugData/clearApplicationData; readCollectionCount/programCollectionCount; readRxRSSI/measureTxRSSI/runDiagnostics; readCollectionDataAt; programLEDSequence; readLastAudioSamples(+Diagnostics); HaversineSatelliteManager: waitUntilPoweredOn/scanForSatellites/**forgetSatelliteWithId**; state {name, platformVersions, serialNumber, sensorConfigVersion, advertisedFingerprint, hasDebugInfo, inFailSafeMode}
  * HaversineAdvertisementData_parseManufacturedData; cacheableState {needsServicing, inCollectionState, isMoving, hasDebugInfo, isDark, truncatedCollectionCount, cacheableStateFingerprint}
  * System inputs (bitfield signals): collectionSignal, calibrationAccelOctant, sleepChange, sleepState, largeImpact, fifoWatermark, inCollectionOrientationUpdate, inCollectionOrientation, offClubUpdate, motionFSMUpdate, motionFSMValue, smallImpact; INPUT_* enum incl INPUT_FORCE_COLLECTION_WRITE, INPUT_PANIC, INPUT_ENTER_DARK_STATE, INPUT_APPLICATION_DATA_UPDATED...
  * Error enums: HAVERSINE_ERROR_{NONE, UNKNOWN, CONFIG_ERROR, OVERFLOW_ERROR, MISSING_DATA, END_ENCOUNTERED, LOG_DATA_ALREADY_SAVED, UNEXPECTED_VERSION, UNEXPECTED_DATA_SIZE}; TELESTO_ERROR_{NONE, CANCELLED_BY_REQUEST, CANCELLED_BY_WRITE, BAD_REQUEST}; TRANSPORT_ERROR_* (BT); TELESTO_CONTROLLER_ERROR_{UNEXPECTED_CTRL_INPUT, UNEXPECTED_DATA_INPUT}; PPErr; HaverineError_isRecoverableByImmediateReconnection
  * Constants: TELESTO_STATIONARY_DATA_V1_DATA_SET_SIZE/_MAX_COUNT/_STARTING_OFFSET, kMaxHaversineApplicationDataSize, TELESTO_BASE; hardware_major_versions_e {1,2,3,4,5,6,X,**AUDIO**}; PPSensor LSM6DSO32 (bdr, fullScaleRange, highPerformanceMode); PPSatelliteEventCode {Boot, Connection, Disconnection, StateChange, DetectionUpdate, CollectionDetected, Interrupt, DetectionTimeout, SensorCoreReset, Coredump, Dark, Light, DisconnectWithActiveTelesto, ConnectionWatchdogFired, DebugSignal0/1/2}
  * Reboot reasons (ring firmware!): PP_REBOOT_INVALID_ADDRESS_SEED, PP_COMPRESSION_FAILURE, PP_ADC_SAMPLE_RATE_OUTSIDE_BOUNDS, PP_REBOOT_FLASH_{PROGRAM,READ,ERASE}_STORAGE_FAILURE, PP_REBOOT_FLASH_READ_SIZE_TOO_LARGE, PP_REBOOT_FLASH_{WRITE_TO,READ}_FAILSAFE, PP_REBOOT_RESTORE_CODE_AFTER_COLLECTION_XOR, PP_REBOOT_BLE_TELESTO_OPERATION_COMPLETE_1/2, BLE_TELESTO_PREVIOUS_REQUEST_PENDING, PP_REBOOT_GS_STOP_WRITE, PP_REBOOT_PANIC_REQUESTED_FROM_HOST, PP_REBOOT_UNEXPECTED_HAVERSINE_ERROR, PP_REBOOT_UNEXPECTED_SENSOR_VIBRATION_REBOOT, PP_BOOST_TOO_HIGH_FOR_FLASH_WHEN_POWERING_ON_FLASH, PP_BUTTON_HELD_FOR_OVER_MAX_TIME, PP_REBOOT_ACCEL_READING_BYTES_IN_FIFO, PP_REBOOT_ACCEL_WATCHDOG_FIRED, PP_REBOOT_STACK_OVERFLOW, PP_SDK_ASSERT_ERROR, PP_ENTERED_DARK_STATE, PP_REBOOT_WATCHDOG/HARDWARE/SOFTWARE/NMI/HARDFAULT, PP_REBOOT_WAKE_FROM_HIBERNATION, PP_REBOOT_ACCEL/MAG_RESET_ON_INIT, PP_REBOOT_TIMER_FAILED_TO_SET, PP_REBOOT_PLATFORM_RESET, PP_REBOOT_UNEXPECTED_RESET
- 21:3x decoded DDRiceCompression.o (Rice codec): encoder {u32 low24-bit buffer; u32 high24 (init 0x80000000); buf start/pos/end; u64 bitCount}; appendBits(value<=24bit, nbits) -> 48-bit accumulator, flushes whole bytes; close() flushes remainder; compressedBitCount(); channel k = firstByte&0xf (0..15), upper nibble = extra state; encodeWord: 2nd-order predictor (quotient + delta-of-delta), writes: code==0 -> single 1 bit; else 0 + (16-k)-bit payload; decoder: {u32, ptr, u32; 16x16B slots (histogram for adaptive k)}; decodeDiff: read 1 bit; 0 -> read more bits (leader counting, max 15?), build code n, clamp (n - 2^(15-k))... to [-7..7] histogram, store diff; nextWord(v): delta+=v; sum+=delta; return (sum<<k)&0xffff; prevWord inverse. So audio = 16-bit samples, delta-encoded, Rice coded (k 0..15 adaptive, stored in first byte low nibble)
- 21:4x decoded GSParseRecordsInRawData (PPParsing.o): collection binary = [3-byte total-size header: BE24 (or 0xFF+BE16), or LE24 when byte3==0; must match len-3 or len] then records: {u8 code; u16 payloadLen; payload} ; 36 record pointers stored; codes: 1..18,33,34,36..41,48..53,80..84 valid (others -> error 6); loop ends exactly at buffer end; error codes 4/6/7. Record types (36): deviceID(6B serial), UTC(u32 seconds), impactTimestamp, calibrations (accel/gyro/mag/accel2/gyro2/haccel1/haccel2), sensorTemperatures, targetLineAim, swingSetup, clubSettings, allSensorCalibrations, stFifoCompressed, stFifoFirmwareCompressed, stSensorConfig, platformVersions, userData, applicationDataStore, detector, latestStationaryData(+version), croppedStationaryData, stationaryDataSensorConfigs, collectionSensorConfigs, swingTimeCorrection, buttonPressSequence, uncompressedAudioData (32-bit inner size), compressedAudioData (32-bit inner size), collectionMultiPartInfo{u32 startIndex; u8 isMultiPart; u8 isFinalPart}, lifetimeCollectionCount(u32)
- 21:4x PPCollection struct = 0x1158 bytes: {u8 valid; ~32B header; ptr deviceID @0x21; 36 record ptrs @0x29..0x148; ...; parse-result @0x130}; createAudioTimeline: result PPResultAudioTimeline{u32 collectionStartIndex(=multiPartInfo.startIndex); u32 sampleRateHz(from audio record header); u64 sampleCount; samples*; char isMultiPart, isFinalPart}; path A (record slot22): {u32; u32 sampleRateHz; pcm16 payload @+8} copied directly (uncompressed); path B (slot23): {u32 size; u32 count@5; rice stream @+4 (k byte @+0xd)} decoded via DDRiceDecompressionChannel+Decoder into int16 samples; sanity (size*8-72 >= count)
- TODO: ST FIFO parser (PPCreateCompressedSTFIFOParser/PPParseCompressedSTFIFOData - the 'stFifoCompressed' audio with sampleTimeLSP header); sample rate constants (16k?); PPRingApplicationData (fingerprint/userUid); PPTinyBitMixer + address seed -> MAC; UpdateCache op (registration); HaversineTransferCollectionsOperation C state machine (which Telesto addresses: TELESTO_COLLECTION_BASE etc.); Kotlin IR (bodies.knb) -> TransferComplete creation; crypto search; REPORT.md

## 2026-02-09 (round 4): Kotlin layer + firmware image + transfer state machine

### Kotlin layer (main klib linkdata knm strings)
- `TransferStatus` (sealed): TransferStarted, **TransferTypeDetermined** (rollover, isAudio, buttonSequence), TransferFailed(exception), **IrrecoverableDataDetected**, TransferInProgress(willTransferRange, ranges, collectionStartIndex, collectionIndex, final, advertisementReceivedTimestamp, lifetimeCollectionCount), **TransferComplete**(collection, currentCollectionIndex, collectionStartCount, samples:ShortArray, sampleRate, buttonReleaseTimestamp, transferCompleteTimestamp, isContiguous)
- `MultipartCollection`: startIndex, buffer, finalSequence, indices(set), sampleRate(UInt), releaseTimestamp, isContiguous; `addPart(index, sequence, timeline:PPAudioTimeline)` (throws if part sample rate != existing); `flushBuffer(): ShortArray`
- `HaversineTransferDelegate` (common): collectionIndexStorage, scope, _transferStatus:MutableSharedFlow, eventChannel:Channel<TransferEvent>; callbacks firstCollectionToTransferInRange / willTransferCollectionsInRange / collectionTransferDidFinish(data:ByteArray, collectionIndex:UShort) / collectionTransferDidFail; internals: processEvents, handleWillTransfer, handleDidFail, handleDidFinish, **processMultiPartAudio, processSinglePartAudio, emitCompleteTransfer**; uses ppcommon.PPCollection directly
- `CollectionIndexStorage`: lastSuccessfulCollectionIndex (persistent transfer-resume state; setLastSuccessfulCollectionIndex)
- `removeDCBias(data: ShortArray)` in-place (util.kt)
- `KMPHaversineSatelliteManager` (iOS): pairedSatelliteIdProvider, collectionIndexStorage, hwVersion, pendingProgramming, lastRing, transferDelegate/updateDelegate/permissionsDelegate, environment; `programSatelliteWithApplicationData(satellite, NSData)`; `programSatelliteWithUserID(satelliteId, userId)`; startScanning(); satelliteFirmwareUpdateState: Channel<SatelliteStatus>; RING_UPDATE_URL = https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json
- `KMPHaversineSatelliteState`: nearby, isInCollectionState, isNearby, isInFailsafeMode, firmwareVersion, truncatedCollectionCount, serialNumber, applicationDataUserId
- PPCommon.ios.kt: fingerprintMatchesFailsafe(fingerprint:Long), fingerprintMatchesUserId(userId:String)
- KMPHaversinePermissionsDelegate: OLD_FINGERPRINT? (Companion OLD_FIRMWARE_FINGERPRINT: Long), CACHE_SUBDIRECTORY, shouldHandleAdvertisement, shouldHandleSatellite, shouldTransferCollections
- KMPHaversineDebugInfo / RingDebugInfo (serializable): timestamp, satelliteId, satelliteName, satelliteVersion, satelliteSerial, dump(coreDump:ByteArray, rebootReasons:List<KMPHaversineDebugRebootReason{code:UInt, context, description}>)

### Ring firmware (public!)
- GET RING_UPDATE_URL -> JSON: firmware 3.75, hardware 11.0, creationDate 1785874793, image (base64) = 29288 bytes
- Image saved: firmware/ring_firmware_v3.75.img (git repo: firmware/repo, single commit 2024-10-06)
- Header: 7051aa00 28720000 dd51351e "1.20" 0000ffff...(padding) — 0x00AA5170 magic?, 0x7228=len-64, 0x1E3551DD CRC?
- Strings in image: "Pebble Index XXX" @0x7240 (product name!), "0123456789ABCDEF" @0xf640, many short C-style strings; entropy 6.89 bits/byte (looks like real code, NOT encrypted — XOR'd restore-code theory unconfirmed)
- 29288 bytes ~ fits a 32K MCU code region; possibly full firmware (not delta)

### TransferCollections C state machine (HaversineTransferCollectionsOperation.c)
- Op struct: 0xA098 bytes; child@0x40, phase@0x48, callbacks@0x50/0x58/0x60/0x68, ctx@0x70, {u16 lastEndIdx@0x78, flag@0x7a, u16 current@0x7b, u16 count@0x7d}, data buffer 0x10000 @0xA000 (payload @+0x81), sentinel@0xA090
- Phase 0 = ReadCollectionCount child -> u16 count@0x7d
- Phase 1 = per-collection read loop (newest first; 16-bit index wraparound; delegate willTransferCollectionsInRange; max range 0x201=513 collections)
- Phase 2 = ReadMultiPartCollections: accumulate in buffer, then GSParseRecordsInRawData(buf+0x81, size-2)
- On success: delegate callback with lastTransferredIndex; final callback with zeroed 16B result
- Phase 1 child params: 16B vtable + u32@1 = (u16 domain 0x4002 <<16) | u16 index  <- virtual address domain!
- TelestoRequest = 4 bytes {u8 type, u24 address} + 4B data length = 8B outbox prefix
- ReadLastAudioSamples init: (1, 0x50C0=20672) big op struct; start params = 16B + 8B

## 2026-02-09 (round 5): final findings
- PPRingApplicationData_t = {u32 fingerprint; u32 timestamp; uid[129]} (~132B); _fingerprint() = custom 32-bit hash of 132B (84 x u32, xxhash-style, constants 0x7ED55D16/0xC761C23C/0xE9F8CC1D/0xACCF6200/0xFD7046C5/0xB55A4F09)
- fingerprintMatchesUserId: compare LOW 16 bits of hash(uid) vs appData->fingerprint; NoUser = high 16 bits zero; Failsafe = fingerprint == 0xDEADDEAD; hasUser() = always 1 (stub)
- _serialize_v1: 141-byte (0x8D) wire format {u8 version=1; 8B (fp+ts); 129B uid; ...} - app-data programming write (0x00 op)
- PPTinyBitMixer(x) = 5x byteswap(x*0x9E3779B9); PPGenerateUniqueStaticRandomBluetoothAddress(seed64) = 4 rounds mixer + fixed 14-bit prefix | 0x1C2C pattern + XOR feedback -> static random MAC from per-device seed
- Crypto search: NO AES/ChaCha/HMAC/SHA/CRC/encrypt symbols anywhere (C or Swift). Only "XOR" = PP_REBOOT_RESTORE_CODE_AFTER_COLLECTION_XOR reboot reason (firmware storage obfuscation)
- HaversineCacheableStateUpdate{cacheableName, advertisedName, fingerprint:UInt32, lastTransferEndIndex:UInt16} = app-side persistent cache (cache dir "haversine_download")
- KMPHaversineSatelliteManager: programSatelliteWithUserID -> PPRingUser_init + PPRingApplicationData_init + PPRingApplicationData_serialize (C) -> 141B NSData -> programWithApplicationData (0x00 write)
- requestUpdate: Ktor GET RING_UPDATE_URL -> JSON{firmwareVersionMajor/Minor, hardwareVersionMajor/Minor, image(base64)} -> HaversineFirmwareUpdate; willUpdateFirmwareFor/didUpdateFirmwareFor -> SatelliteStatus channel
- Kotlin IR (bodies.knb) decoded via strings.knt pool (2.2 format: [u32 count][len x N][pools], each pool [u32 n][len x n][strings]): HaversineTransferDelegate.processEvents (firstCollectionToTransferInRange: resume from CollectionIndexStorage.lastSuccessfulCollectionIndex; willTransfer; DidFail -> TransferFailed + setLastSuccessfulCollectionIndex; DidFinish -> PPCollection(index, data) -> audioTimeline -> processMultiPartAudio/processSinglePartAudio -> emitCompleteTransfer -> TransferComplete{samples, sampleRate, ...}); MultipartCollection.addPart (check sample rate match, writeShortLe); removeDCBias = mean removal
- TransferTypeDetermined{isAudio, buttonSequence, collectionStartIndex, collectionIndex, final, advertisementReceivedTimestamp, lifetimeCollectionCount}
- TelestoStoredCollectionIndexes = {uint16_t range; uint16_t first}
- iOS vs simulator .o: DIFF (arch-specific)
- Ring firmware (29288B, Cortex-M Thumb-2, product "Pebble Index XXX"): does NOT disassemble cleanly -> XOR-obfuscated (matches RESTORE_CODE_AFTER_COLLECTION_XOR); 8000/32000 constants appear; no 16000; no standard compression magic
- SUOTA: 8-phase C state machine; 0x1F000-0x4D000 flash region; image = 29KB (probably de-XOR'd+expanded on-ring)
- SAMPLE RATE: no hard-coded rate in Haversine/PPCommon; embedded per-record (u32 in audio record header) + in sensor configs; firmware suggests 8kHz native; brief says app resamples to 16k

## 2026-02-09 (round 6): VERIFIED record-code map (jump table extracted from PPParsing.o __const@0xb68)
GSParseRecordsInRawData(out GSRaw 288B=37 slots, data, len): 3-byte size prefix (BE24, or 0xFF+BE16, or LE24-if-b3==0); records {u8 code; u16 len; payload}; slot stores ptr at u16-len (i.e. [slot]=u16 len, payload at +2); 32-bit-len variant for codes 43/44
code->slot->field (verified vs accessors):
 7->slot0(+0x00)=deviceID (6B serial)  15->slot1(+0x08)=UTC(u32)  29->slot18(+0x90)=platformVersions  35->slot20(+0xa0)=applicationDataStore(141B)  38->slot27(+0xd8)=swingTimeCorrection
 **40->slot29(+0xe8)=RAW audio {u32 size; u32 sampleRateHz; int16 LE[]}** (createAudioTimeline path A)
 **41->slot30(+0xf0)=DD/Rice-compressed audio** (path B: {u32 size; u32 sampleCount; 9B DD header (k + 8B 2nd-order predictor state); bit-packed stream})
 **42->slot31(+0xf8)=collectionMultiPartInfo {u32 startIndex; u8 isMultiPart; u8 isFinalPart}**
 43/44->slots 33/34 = 32-bit-len audio variants; 45->slot35; 46->slot32; 47->slot36(+0x120 tail)
createAudioTimeline: path B mallocs 15680B, grows to ~0x186A0 (99984) samples max (~12.5s @8k / 6.25s @16k per part)

## 2026-02-09 (round 7): Telesto protocol nailed down
- TelestoRequest = 16-byte struct (13 meaningful): {u8 type; u32 a; u32 b; u32 c} — Swift TelestoOperation.init rebuilds exactly these 13 bytes (strb [0], stur [1..4], [5..8], [9..12])
- Type enum (C order): 0=NOOP, 1=ERASE_MEMORY, 2=PROGRAM_MEMORY, 3=READ_MEMORY, 4=CANCEL, 5=ERASE_AND_PROGRAM
- 64-bit virtual addresses: 0x4002xxxx = collection region (base 0x40020000, low16 = index); 0x40000000_03060003 + 0x40000000_03080003 = single-sector region (programmed serial / platform versions) — same pair read by both UCO and SUOTA
- UpdateCache op = 4-phase READ (applicationDataStore, programmedSerialNumber, sensorStateConfigs w/ TelestoSensorConfigsHeader{inFailSafe,hasPayload}, platformVersions) -> HaversineCacheableStateUpdate{platformVersions{16B: 4 version bytes + 12B}, serialNumber, applicationData, size}
- TelestoPlatformVersions = 16B {u8 hwMajor, u8 hwMinor, u8 fwMajor, u8 fwMinor, +12B} — matches JSON v3.75
- HaversineSystemInput = 14-bit event bitfield ring->phone: interrupt, collectionSignal, calibrationAccelOctant, sleepChange, sleepState, largeImpact, fifoWatermark, inCollectionOrientation(Update), offClubUpdate, motionFSM(Update/Value), smallImpact, reserved — collections triggered by impact/motion
- rlas phases: READ_COLLECTION_COUNT -> READ_LAST_COLLECTION -> READ_MULTIPART_COLLECTIONS -> READ_CACHED_STATE -> READ_BATTERY_VOLTAGE -> READ_RX_RSSI
- UCO/SUOTA __const 16-byte param blocks extracted (application-data block has non-enum first byte 0x19 = different layout)
- REPORT.md updated: 16-byte request, 64-bit addr map, ~40 named TelestoVirtualAddress constants, update-cache 4 phases, system-input bitfield, firmware section softened (primary/failsafe image regions)

## 2026-02-09 (final): report verified
- fingerprintMatchesFailsafe: cmp w0, 0xDEADDEAD (exact); fingerprintMatchesNoUser: (fingerprint & ~0xFFFF)==0 (high-16 zero) — verified in PPRingApplicationData.o
- Corrected stale code numbers in headline (53/51 -> 40/41) and pairing section (app-data store = record code 35, programmed via Telesto PROGRAM, not a "0x00 write")
- REPORT.md complete: headline, collection container + record table (37 slots, codes 1-47), audio record layouts (raw code 40 / DD code 41), multipart, Telesto protocol (16-byte request, 64-bit addr map, type enum 0-5, response, length-prefixed data, SystemInput bitfield), update-cache 4 phases + CacheableStateUpdate, firmware update, pairing/key management, direct answers, method
