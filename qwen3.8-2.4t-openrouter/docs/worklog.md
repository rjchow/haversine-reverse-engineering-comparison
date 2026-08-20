# Haversine Reverse-Engineering Work Log

Purpose: persistent tracking of progress so context compaction can't lose state.
Resume point: always read this file first.

## Task (from brief.md)
Reverse-engineer two Kotlin/Native `.klib` artifacts (iosarm64 + iossimulatorarm64)
of the "Haversine" library (`io.github.coredevices.haversine`, version 03202f5)
used by Pebble Index iOS app to talk to the Pebble Index 01 BLE ring.

Key questions:
1. Audio format on ring / over Haversine protocol / delivered to app
2. Codec identity (PCM/ADPCM/Speex/Opus/custom/encrypted?)
3. Sample rate pre-resample, sample width, channels, framing, byte order
4. Incremental frames vs complete object transfer
5. Integrity mechanisms (CRC, seq numbers, acks, retransmit, FEC)
6. Crypto: app-layer encryption of recordings? at-rest encryption?
7. Registration shared-secret hypothesis: test explicitly
8. Locate TransferComplete(samples, sampleRate, ...) creation path

Anchors:
- Haversine BLE service: 607B5C9B-3700-4E94-F44A-2DF900BCB0C3
- Characteristic: DAAD3D52-237C-90A7-B54B-8854A134D801 (write 0x00 with response during pairing)
- App receives TransferStatus.TransferComplete with ShortArray samples + sampleRate,
  then DC-bias removal -> resample to 16000 -> PCM16 LE mono.

## URLs
- https://repo1.maven.org/maven2/io/github/coredevices/haversine/haversine-iosarm64/03202f5/haversine-iosarm64-03202f5.klib
- https://repo1.maven.org/maven2/io/github/coredevices/haversine/haversine-iossimulatorarm64/03202f5/haversine-iossimulatorarm64-03202f5.klib

## Status phases
- [ ] Phase 0: download artifacts, set up dirs
- [ ] Phase 1: unpack klib structure, inventory members, compare archs
- [ ] Phase 2: strings/symbols inventory (codec, crypto, protocol terms)
- [ ] Phase 3: locate TransferComplete creation + call chain
- [ ] Phase 4: identify audio codec with implementation evidence
- [ ] Phase 5: reconstruct framing layers
- [ ] Phase 6: crypto analysis (only matters if in recording path)
- [ ] Phase 7: persistent state / key storage analysis
- [ ] Phase 8: simulator vs device comparison
- [ ] Final report (report.md) with 10 sections

## Progress notes
(append below, newest at bottom)

### Session 1
- Read brief.md. Created worklog. Starting downloads.
- Downloaded both klibs (zip, 135KB each). Structure: default/{manifest,ir/,linkdata/,targets/,resources}.
  NO native objects/bitcode in main klib; targets/*/native is EMPTY.
- IR (bodies.knb etc.) IDENTICAL between device+sim; linkdata IDENTICAL. => analyze once.
- Kotlin 2.2.20 build. Deps: kotlinx-serialization, ktor, kermit, atomicfu, kotlinx-io, and
  two cinterop libs: haversine-cinterop-haversineSatelliteLibrary, haversine-cinterop-PPCommon.
  => the real protocol/C code likely lives in those cinterop artifacts. TODO: download from Maven.
- strings dump revealed rich symbols:
  * TransferStatus sealed class: TransferStarted(willTransferRange,rollover),
    TransferTypeDetermined(isAudio,buttonSequence,collectionStartIndex,collectionIndex,final,
    advertisementReceivedTimestamp,lifetimeCollectionCount), TransferFailed(exception),
    IrrecoverableDataDetected(collection:MultipartCollection), TransferInProgress(currentCollectionIndex),
    TransferComplete(satellite,collectionStartCount:Long,buttonSequence:String?,sampleRate:Int,
    samples:ShortArray,buttonReleaseTimestamp:Long,transferCompleteTimestamp:Instant?,...:Instant,isContiguous:Boolean)
  * HaversineTransferDelegate: processEvents/handleWillTransfer/handleDidFinish/handleDidFail;
    native callback collectionTransferDidFinish(data:ByteArray,index,satellite);
    parses "PPCollection" (errors: "Failed to parse PPCollection at index", maxSize, 5MB truncation);
    PPAudioTimeline {isFinalPart,isMultiPart,collectionStartIndex,timestamp,unixTime};
    MultipartCollection {addPart(unixTime,...,PPAudioTimeline), flushBuffer()->ShortArray, isContiguous, indices};
    "Sequence mismatch. Expected, got. Flushing buffer." -> sequence numbers exist.
  * PPCommon cinterop API: PPCollection, PPAudioTimeline, PPRingUser_t, PPRingUser_init,
    PPRingApplicationData_t/_init/_serializedSize/_serialize.
  * Telesto: "TelestoStoredCollectionIndexes" struct used by IOSHaversineTransferDelegate.firstCollectionToTransferIn.
  * Firmware update: https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json
  * Program/pairing: programSatelliteWithUserID -> PPRingUser_init(String?) -> PPRingApplicationData_init(user, UInt) ->
    serialize -> NSData -> programWithApplicationData. No obvious crypto in this path yet.
- Source paths from the build identify the `haversine-kmp/...` repository tree.
  Group io.github.coredevices => check github.com/coredevices + HyperionSensing for public source.
- Downloading kotlin-native-prebuilt 2.2.20 (tools/kn.tar.gz) DONE (249MB). Need to extract + use `klib` tool.

### Session 1 (cont.) — MAJOR FINDINGS
- Maven also publishes (same dir as main klib): cinterop klibs + sources.jar (empty stub).
  * haversine-iosarm64-03202f5-cinterop-PPCommon.klib -> contains libPPCommon_static.a (38KB, ARM64 objects,
    FULL symbols): DDRiceCompression.o PPBluetoothUtils.o PPCollection.o PPParsing.o PPRebootReasons.o
    PPRingApplicationData.o PPSatelliteEvents.o PPTypes.o  [extracted to extract/ppcommon_a/]
  * haversine-iosarm64-03202f5-cinterop-haversineSatelliteLibrary.klib -> libHaversineSatelliteLibrary.a
    (4.5MB Swift objects: HaversineLinkController, TelestoController, TelestoOperation, TelestoTypes,
    HaversineTransferCollectionsOperation, HaversineReadLastAudioSamplesOperation, HaversineSuotaOperation,
    CBCentralManagerAdaptor etc.) [extracted to extract/satlib_a/]
  * ALSO separate Maven artifact io.github.coredevices:speex (speex-iosarm64 etc., versions 1946c84, a47881a,
    c61d18a, 905487f-dirty, e8c1491-dirty, e927b56-dirty). Haversine 03202f5 does NOT depend on it per manifest.
    TODO: inspect what speex artifact is (maybe used by newer firmware/app for mic audio?).
- Kotlin toolchain: tools/kotlin-native-prebuilt-macos-aarch64-2.2.20/bin/{klib,konanc,...}.
  klib dump-abi/dump-ir/dump-metadata WORK.
  * tools/haversine_abi.txt = full public API (dump-abi of main klib).
  * tools/ppcommon_meta.txt = full PPCommon C bindings incl. struct spellings (dump-metadata).
- Device context: it's a GOLF swing-analyzer ring (IMU/accel/gyro/mag/swing records + button + audio).
  "GS" record structs, "PP" = Pebble(?) API layer.

#### Collection blob format (from GSParseRecordsInRawData disasm, extract/ppcommon_a/PPParsing.s):
- Envelope variants (blob header):
  * v0 legacy: data[3]==0, LE24(data[0..2]) == total blob size, records start at offset 4
  * v1: data[0]!=0xff & data[3]!=0: BE24(data[0..2]) == total size, records at offset 3
  * v2: data[0]==0xff: u16LE(data[1..2]) == total size, records at offset 3
- Record TLV loop: [u8 type] then:
  * normal types: [u16LE len][len-1 data bytes] (advance = p+len+1, p=len-field pos)
  * audio types (9, 80, 81): [u32LE len][len data bytes] (advance = p+len+4)
- Record type map (from jump table @ PPParsing.o __const offset 3608):
  1=deviceID 2=gyroCalibration 3=sensorTemperatures 4=VSRSamples 5=haccel1Cal 6=allSensorCalibrations
  7=stFifoFirmwareCompressed 8=croppedStationaryData 9=uncompressedAudio(legacy) 10=lifetimeCollectionCount(legacy)
  11=swingSetup 12=clubSettings 13=VSRSamples? 14=multiAccelSamples 15=accel2Cal 16=gyro2Cal 17=haccel1Cal
  18=haccel2Cal 19-32=unknown->parse error 33=stFifoCompressed 34=stSensorConfig 35=?err 36=allSensorCal
  37=platformVersions 38=userData 39=applicationDataStore 40=stFifoFirmwareCompressed 41=detector
  48=latestStationaryData 49=latestStationaryDataVersion 50=croppedStationaryData 51=stationaryDataSensorConfigs
  52=collectionSensorConfigs 53=swingTimeCorrection
  80(0x50)=uncompressedAudioData 81(0x51)=compressedAudioData 82(0x52)=collectionMultiPartInfo
  83(0x53)=buttonPressSequence 84(0x54)=lifetimeCollectionCount
  (many types map to same slot = versioned records)

#### Audio record payloads (from PPCollection_createAudioTimeline disasm, extract/ppcommon_a/PPCollection.s):
- type 9/80 uncompressed: [u32LE len][u32LE sampleRateHz][int16 LE samples[(len-4)/2]]
- type 81 compressed:     [u32LE len][payload]; payload =
    +0 u8 riceHeader (lo nibble = k Rice param, hi nibble = maxQ unary escape limit)
    +1 u32LE compressedBitCount (unaligned)
    +5 u32LE sampleRateHz (unaligned)
    +9 bitstream (MSB-first)
  sanity check in parser: 8*len - 72 <= bitCount  (bitstream fills payload after 9-byte header)
- collectionMultiPartInfo record payload: [u16 size][u32 startIndex][u8 isMultiPart][u8 isFinalPart]
- buttonPressSequence payload: [u16 size][u32 bitmap][u32 count] (bits -> string of '1'/'2' etc.)
- lifetimeCollectionCount payload: [u16 size][u32 count]

#### Rice codec (DDRiceCompression.o — fully understood decoder):
- Bit reader DDRiceDecompressionDecoder: (data ptr, totalBits, bitOffset). readBit MSB-first; EOF -> rc=3.
- Channel state (DDRiceDecompressionChannel): header byte ptr (k, maxQ), double integrator:
  field+0x10 = 2nd-order accumulated base (i16), field+0x12 = current diff (i16); 15 histogram counters
  at +0x38 (debug/stats only); +0x28/+0x30 literal stats.
- decodeDiff(channel, decoder, &out16, count): for each sample diff d (u16 mod 65536):
    b0 = readBit
    if b0 == 0: d = 0
    else: q = 1
          loop: if q >= maxQ: LITERAL: d = readBits(16-k) (MSB first); count stats; break
                b1 = readBit; if b1 == 0: q += 1; continue
                b2 = readBit; if b2 == 0: d = +q; else d = (65536 >> k) - q; break
    then: if d >= (32768>>k): d -= (65536>>k)   [wrap to negative]
    bin = clamp(d, -7, 7)+7; counters[bin]++
    *out++ = d (raw 16-bit diff)
- nextWord(channel, d): ch.diff += d; ch.base += ch.diff; return (ch.base << k) & 0xffff
  => samples reconstructed by DOUBLE INTEGRATION of Rice-coded diffs, then << k (samples are multiples of 2^k).
- Encoder side mirrors it (appendBits dual-lane 32-bit accumulator, byte-out MSB-first).
- This is custom "delta-delta + Golomb-Rice" lossless compression of 16-bit audio, NOT a standard codec.

#### PPResult_t / API
- PPCollection_createFromBinaryData(data,size,&err) -> PPCollection_s* (0x1158 bytes: valid@0,
  GSRawDataRecords(37 ptrs)@1, dataCopy@0x130, dataSize@0x138).
- PPCollection_createAudioTimeline(coll) -> PPResult_t (union; error@0, audioTimeline@8):
  PPResultAudioTimeline_t {u32 collectionStartIndex; u32 sampleRateHz; u64 sampleCount; void* samples;
  char isMultiPart; char isFinalPart}
- Error codes seen: 2=null, 3=not parsed/invalid, 6=parse error, 7=missing record, 0x13(19)=OOM.
- Kotlin wrapper: coredevices.haversine.ppcommon.PPCollection(index, ByteArray),
  PPAudioTimeline {collectionStartIndex, isFinalPart, isMultiPart, sampleCount, sampleRateHz, samples: ShortArray}

#### Kotlin API (tools/haversine_abi.txt)
- TransferComplete(satellite, collectionStartCount:Long, buttonSequence:String?, collectionIndex:Int,
  samples:ShortArray, sampleRate:Long, buttonReleaseTimestamp:Instant?, transferCompleteTimestamp:Instant,
  isContiguous:Boolean)
- MultipartCollection(startIndex) {addPart(index,buttonSeq?,Instant?,PPAudioTimeline), flushBuffer():ShortArray,
  isContiguous(), indices:Set<Int>, finalSequence:String?, sampleRate:UInt, releaseTimestamp:Instant?}
- removeDCBias(ShortArray) exists IN haversine.
- HaversineTransferDelegate: willTransferCollectionsInRange(range, satellite), firstCollectionToTransferInRange,
  collectionTransferDidFinish(ByteArray, index, satellite), collectionTransferDidFail(...), transferStatus: SharedFlow.
- programSatelliteWithUserID(userId, ...) -> PPRingUser_init/PPRingApplicationData_init/serialize -> program.
- Firmware update via https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json

## NEXT STEPS
1. klib dump-ir main klib -> bodies of HaversineTransferDelegate/MultipartCollection (sequence logic, sampleRate flow)
2. Satellite Swift lib: nm/strings/disasm TelestoController, TelestoTypes, HaversineTransferCollectionsOperation
   -> BLE framing (GATT ops, chunking, acks, TelestoStoredCollectionIndexes)
3. Crypto sweep: strings/nm both libs + IR for AES/ChaCha/HKDF etc.; PPRingApplicationData; pairing path.
4. Check speex artifact (what it wraps, who uses it).
5. PPSatelliteEvents.o + PPRebootReasons.o strings (advertisement/event format).
6. Compare sim versions of cinterop libs (verify identical logic).
7. Write report.md.

### Session 2 — Transport layer (satellite library) + sweeps. ALL PHASES DONE.

#### Telesto protocol (TelestoController.o, C, full symbols; confirmed by cinterop metadata)
- Wire request `TelestoRequest` = 13 bytes packed align 1 (satlib_meta spelling + putTelestoRequestInOutbox writes
  remainingSize=0xd at outbox+8, request bytes at outbox+0x11):
  | off | size | field |
  | 0 | 1 | type (TelestoOperationType, 8-bit bitfield) |
  | 1 | 4 | address (u32 LE, virtual address) |
  | 5 | 4 | offset (u32 LE) |
  | 9 | 4 | length (u32 LE) |
- Wire response `TelestoResponse` = 12 bytes { u32le error; u32le info; u32le length }.
- Operation types (enum string order + code paths): 0 NO_OPERATION, 1 ERASE_MEMORY, 2 PROGRAM_MEMORY,
  3 READ_MEMORY, 4 CANCEL_OPERATION, 5 ERASE_AND_PROGRAM_MEMORY.
- Two logical channels: CTRL (13-byte request writes; 12-byte response notifications) and DATA (raw bulk bytes).
  READ: data flows ring→phone, expected bytes = response.length (checked in completeOperationIfNecessary:
  receivedDataSize[0x90] >= response[8]). PROGRAM/ERASE_AND_PROGRAM: phone→ring, dataOutbox.remainingSize =
  request.length (startNextOperationIfNecessary: x20>>8 of the 40-bit {offset,length} = u32 length).
- Each outbox has pendingConfirmation flag; processOutbox sends via callback {sendTelestoCtrlBytes,
  sendTelestoDataBytes, sendSystemInputBytes, context} and sets pending; pending is cleared ONLY by
  TelestoController_ctrlBytesSent / _dataBytesSent (called from CoreBluetooth didWriteValue) → writes are
  write-with-response and per-write-ack driven. Unexpected events → TELESTO_CONTROLLER_ERROR_UNEXPECTED_{CTRL,DATA}_{INPUT,OUTPUT} (1..4).
- CANCEL: putCancelRequestInOutbox reuses head op's address, sets type=4. Completion error on cancel = 0x41
  (TELESTO_ERROR_CANCELLED_BY_REQUEST; enum also has BAD_REQUEST, CANCELLED_BY_WRITE, NONE).
- TelestoController struct = 0x98 bytes (calloc 1,0x98 in init). Layout decoded (see report §7).
- TelestoLengthPrefixedData (TelestoTypes.c): malloc(size+4); [u32le total(=payload+4)][payload].

#### GATT wiring (CBConnectedPeripheralAdaptor.o, Swift + relocations)
- HaversineUUID enum rawValue switch (HaversineUUID.o, jumptable lJTI0_0 @0x6c = 0f 00 03 06 09 00 03 00):
  case1→607B5C9B-3700-4E94-F44A-2DF900BCB0C3 (SERVICE), case2→DAAD3D52-237C-90A7-B54B-8854A134D801,
  case3→C0EF558A-2058-FABF-A140-8D5ACDE50B39, case4→1D1F4039-23F5-33B2-C24E-704351F20585.
- Role mapping by string relocations in CBConnectedPeripheralAdaptor.o:
  * sendTelestoCtrlBytes closure (0x5e90) constructs CBUUID from C0EF558A (reloc 0x5f6c) → CTRL write char
  * sendTelestoDataBytes closure (0x63bc) constructs CBUUID from DAAD3D52 (reloc 0x645c) → DATA write char
  * sendSystemInputBytes closure (0x6858) constructs CBUUID from 1D1F4039 (reloc 0x68f8) → system-input char
  * handleUpdatedNotificationState compares char UUIDs against DAAD3D52 (0x9240) and C0EF558A (0x9304)
    → notifications on BOTH ctrl and data chars.
- init closure discovers service 607B5C9B (reloc 0x1160) and all three characteristics.
- Writes go through private helper send(bytes:to:type:) @0x4f60 which calls maximumWriteValueLengthForType:
  (reloc 0x545c) and writeValue:forCharacteristic:type: (reloc 0x5aec) — i.e. chunking to negotiated MTU.
  Log string: "WARNING: Writing <n> to BLE characterisic <uuid> which does not support writeWithResponse.
  Writes of this size have been observed to fail." → the library writes with .withResponse.
- didWrite/didUpdateValue routed via dictionary characteristicContexts[CBUUID: CharacteristicContext]
  (no hardcoded role switch in the hot path).

#### Telesto virtual address space (named constants in HaversineTransferCollectionsOperation.c strings + code immediates)
- TELESTO_VIRTUAL_ADDRESS_BASE = 0x40000000 (implied); COLLECTION_BASE = 0x40020000 | collectionIndex
  (built inline @0x1b4-0x1c4: orr w8, wIdx, #0x40020000; strb type=3; offset=0; length=0 → ring returns full
  collection, size via response.length).
- Const request template A @0x718: READ addr=0x40030005 (TELESTO_STORED_COLLECTION_INDEXES) offset=0 len=4.
- Const request template B @0x730: READ addr=0x4003000E (TELESTO_CURRENT_ADVERTISING_DATA) offset=0 len=10.
- Other addresses named: UNIX_TIME, BATTERY_VOLTAGE, PLATFORM_VERSIONS, SERIAL_NUMBER, APPLICATION_DATA_STORE,
  APPLICATION_DOMAIN, STATIONARY_DATA, SENSOR_CALIBRATIONS, SENSOR_0_FIFO/LAST_OUTPUT/CONFIGS/STREAMING,
  COLLECTION_COUNT, LIFETIME_COLLECTION_COUNT, STORED_COLLECTION_INDEXES, LED_SEQUENCE, REBOOT_TRACKING,
  CRASH_COREDUMP, PRINT_LOGS, GPIO_STATUS, LAST_RX_RSSI, LAST_PROGRAMMED_UNIX_TIME, FAILSAFE/PRIMARY_IMAGE,
  PHOTOTRANSISTOR_VOLTAGE, LSM6DSO32_FREQ_FINE, RECENT_SATELLITE_EVENTS, CURRENT_ADVERTISING_DATA.

#### Collection transfer state machine (HaversineTransferCollectionsOperation.c, decoded fully)
- self struct: +0x40 currentChild, +0x48 phase, +0x50..0x68 delegate {firstCollectionToTransferInRange,
  willTransferCollectionsInRange, collectionTransferDidFinish, collectionTransferDidFail}, +0x70 ctx,
  +0x78 lastTransferEndIndex u16, +0x7a transferredAny u8, +0x7b nextIndex u16, +0x7d rangeEnd u16,
  +0x7f advert buf(10), +0xa007f collection buf (≤0xa0000), +0xa0090 receivedSize.
- Phases: 0 READ_STORED_INDEXES (4B → rangeStart@0x7b, rangeEnd@0x7d), 1 READ_COLLECTIONS,
  2 READ_ADVERTISING_DATA, 3 FINISHED.
- Phase 0 success: resume logic with persisted lastTransferEndIndex: if within wrap-around window
  [rangeStart, rangeEnd) restart from it, else rangeStart. Then delegate.firstCollectionToTransferInRange
  ((rangeEnd<<16)|start) → chosen first index; contiguous span bounded (assert < 0x201 → max 512 collections);
  delegate.willTransferCollectionsInRange((end<<16)|first) → phase 1.
- Phase 1 success: collectionTransferDidFinish(ctx, self+0x7f, receivedSize, index); nextIndex++;
  lastTransferEndIndex=nextIndex; loop until nextIndex==rangeEnd then back to phase 0 (re-read stored indexes
  to catch new collections). Phase 1 error: collectionTransferDidFail per remaining index.
- Phase 2: read 10B advertising snapshot; parseManufacturedData(data+2, len-2) (strips 2-byte prefix);
  logs "Satellite in collection state - checking for new collections" / "not in collection state - finishing";
  then finish with HaversineTransferCollectionsResult {u16 transferEndIndex}.

#### System input channel (HaversineSystemInputController.c)
- INPUT types: INTERRUPT, PHOTODIODE_LIGHT, PHOTODIODE_DARK, APPLICATION_DATA_UPDATED, SENSOR_CONFIG_UPDATED,
  ENTER_STREAMING_STATE, EXIT_STREAMING_STATE, PRIMARY_DISCONNECTED, UPDATE_ADVERTISING, FORCE_COLLECTION_WRITE.
- Struct HaversineSystemInput { type; ... } + SystemInputInterruptParameters; written to 1D1F4039 char.

#### Phase 5 crypto sweep — NEGATIVE (documented)
- 0 hits for CCCrypt/CommonCrypto/CryptoKit/SecKey/AES-/ChaCha/poly1305/HMAC/CC_SHA/curve25519 across:
  main klib IR+ABI, PPCommon metadata+objects, satellite library objects+metadata.
- 66 superficial grep hits all false positives (Swift mangling: "AES" = Array<UInt8> storage, "SeAE" =
  Decodable witness).
- Conclusion: NO application-layer encryption/auth/MAC anywhere in the stack. Integrity = Telesto write-acks +
  response error codes + app-side collection sequence/contiguity checks only.

#### Phase 7 persistence
- HaversineSatelliteState.CacheableState (Codable) = {cacheUpdate: HaversineCacheableStateUpdate, advertisedName?,
  advertisedFingerprint: u32, lastTransferEndIndex: u16?} + fuller variant {satelliteName, platformVersions,
  serialNumber, sensorConfigVersion, applicationData, advertisedFingerprint, lastTransferEndIndex}.
- UserDefaultsCache: cacheState/fetchCachedState/clearCache keyed by peripheral UUID. → used for resume-from
  lastTransferEndIndex. NO secrets/keys stored.

#### TransferComplete construction (tools/haversine_ir.txt line 1409, fun emitCompleteTransfer)
- TransferComplete(satellite, collectionStartCount=multipart.startIndex.toLong(),
  buttonSequence=multipart.finalSequence, collectionIndex=multipart.indices.last(),
  samples=buf /* multipart.flushBuffer() ShortArray */, sampleRate=multipart.sampleRate.toLong() /* from ring
  PPAudioTimeline.sampleRateHz */, buttonReleaseTimestamp=multipart.releaseTimestamp,
  transferCompleteTimestamp=Clock.System.now(), isContiguous=multipart.isContiguous())
- Emitted only if buf.isNotEmpty(); afterwards lastAdvertisements cache entries for those indices removed.

#### speex artifact
- io.github.coredevices.speex "Kotlin Speex" (github.com/coredevices/kotlin-speex), versions 1946c84..e927b56-dirty.
  Separate product; NOT a dependency of haversine 03202f5 (checked POM + manifest). Not in the audio path of
  this Haversine version.

## Status phases (FINAL)
- [x] Phase 0..8 all done. report.md WRITTEN.

## NEXT STEPS (if continuing)
- Optional: capture live GATT traffic / obtain firmware image to nail ring-side encoder (mic source, exact
  Rice header semantics vs encoder, collection flash layout, advertising 2-byte prefix meaning, 0x00 pairing
  write behavior on DAAD3D52).
- Optional: inspect newer haversine versions on Maven for protocol changes / speex adoption.
