# Haversine RE Progress Log

## Brief
Investigate two Haversine .klib artifacts (iosarm64 + iossimulatorarm64, version 03202f5) to determine:
- Recording format transmitted by Pebble Index ring
- Audio codec, sample rate, framing, integrity mechanisms
- Whether app-layer crypto / registration shared secret exists

Working dir: `haversine_reverse5`

## Status

- [x] Phase 1: Download + unpack klibs
- [x] Phase 2: Symbol/string inventory
- [x] Phase 3: Locate TransferComplete creation
- [x] Phase 4: Identify audio codec (DD-Rice: double-delta + Rice, fully reconstructed)
- [x] Phase 5: Reconstruct framing (collection TLV + Telesto protocol)
- [x] Phase 6: Crypto analysis (none in decode path; only mixBits32/_fingerprint weak hash)
- [x] Phase 7: Persistent state analysis (SharedPreferences cache; registration = non-secret user blob)
- [x] Phase 8: Compare iosarm64 vs simulator (identical Kotlin IR; Android .so = same shared C sources)
- [x] Final report -> REPORT.md

## Deliverables
- REPORT.md — full technical report (exec answer, data path, codec pseudocode, framing tables,
  crypto/key-management analysis, symbol list, evidence index, unknowns, independent-client guide)
- disasm/*.txt — annotated disassembly dumps used as evidence
- decomp/ — Vineflower decompilation of Android classes.jar

## Progress notes

### Session 1
- Read brief.md.
- Downloaded iosarm64 + iossimulatorarm64 klibs (135KB each). Both are Kotlin IR-only klibs
  (no native objects; targets/ dirs empty of .o). Manifest lists deps incl. cinterop
  `haversine-cinterop-haversineSatelliteLibrary` and `haversine-cinterop-PPCommon` (NOT on Maven, 404).
- KEY FINDING: `haversine-android` artifact on Maven has an **AAR with classes.jar (JVM bytecode) and
  native libs**: `jni/*/libhaversinesatellitelibrary.so` and `jni/*/libppcommon.so` (arm64-v8a,
  armeabi-v7a, x86, x86_64). Also `haversine-android-debug` AAR with larger (unstripped-ish) .so files.
  sources.jar is empty.
- Downloaded + extracted both AARs to extract/android and extract/android-debug.
- libppcommon.so exported symbols reveal:
  - `DD` prefix = delta-Rice compression: DDRiceCompressionChannel_encodeWord,
    DDRiceDecompressionChannel_decodeDiff, readBit/readBits, etc.
  - record-type enums: COMPRESSED_16BIT_AUDIO, COLLECTION_MULTI_PART_INFO, BUTTON_PRESS_SEQUENCE,
    APPLICATION_DATA_STORE, CROPPED_STATIONARY_DATA, DETECTOR_DATA, CLUB_SETTINGS...
  - GS* functions (golf swing? IMU) - Pebble heritage (GSClubSettings...)
  - JNI bridge class: com.wtlp.ppcommon.PPCommonJNI
- Kotlin IR strings.knt already reveals full class structure: HaversineTransferDelegate ->
  processMultiPartAudio/processSinglePartAudio -> PPCollection.createFromBinaryData (native) ->
  PPAudioTimeline(samples: ShortArray, sampleRateHz: UInt) -> MultipartCollection buffer
  (writeShortLe/readShortLe => LE int16 PCM out) -> emitCompleteTransfer ->
  TransferStatus.TransferComplete(samples, sampleRate, buttonReleaseTimestamp,
  transferCompleteTimestamp, isContiguous, collectionStartCount).
- Decompiled classes.jar with Vineflower: **HaversineTransferDelegate fully recovered** (decomp/coredevices/haversine/).
  Call chain: `collectionTransferDidFinish(data: ByteArray, collectionIndex)` -> `PPCollection(index, data)`
  (native `PPCommon.createFromBinaryData`) -> `getAudioTimeline()` -> `PPAudioTimeline` (native, LE 16-bit PCM
  ShortArray + sampleRateHz) -> MultipartCollection buffer -> `emitCompleteTransfer` ->
  `TransferStatus.TransferComplete(samples, sampleRate, ...)`.
  Multi-part handling: GSCollectionMultiPartInfo isMultiPart/isFinalPart/collectionStartIndex;
  sequence mismatch -> flush; isContiguous check on indices.
  Other classes: TransferStatus, AndroidHaversineTransferDelegate, PPAudioTimeline, PPCommon_androidKt.

### Session 2
- Confirmed no crypto imports/strings in either native lib (nm -D undefined grep aes|sha|crypto|...: empty).
  libppcommon only has `_fingerprint(const char*)` + `mixBits32` (user-fingerprint hash, not recording crypto).
- libhaversinesatellitelibrary (transport) C API + source paths recovered via strings: sources at
  haversine/HaversineSatelliteLibrary/Sources/Shared/*.c (TelestoController.c, HaversineTransferCollectionsOperation.c, ...).
  HaversineUUID.java: service FCC9/607B5C9B..., telestoData DAAD3D52..., telestoCtrl C0EF558A..., systemInput 1D1F4039...
- Transport concepts seen in strings: ctrl/data outboxes with pendingConfirmation, TelestoLengthPrefixedData_create,
  Transfer op phases: READ_ADVERTISING_DATA -> READ_STORED_INDEXES -> READ_COLLECTIONS; "checking for new collections",
  "finishing transfer operation". SUOTA phases too.
- Both android (release) and android-debug .so have identical exported C symbols; debug build appears -O0
  (bigger offsets) -> using debug .so for disassembly. Key symbols (debug addresses):
  PPCollection_createFromBinaryData 0x2f1b0, GSParseRecordsInRawData 0x2d644, PPCollection_createAudioTimeline 0x2f964,
  PPDeserializeTimeSeries 0x2e8c0, DDRice decompression: init 0x30930, decodeDiff 0x30bcc, readBit 0x30a48, readBits 0x30b18.
- Telesto protocol reconstructed: ctrl channel = 13-byte request {type,addr le32,offset le32,len le32};
  ops ERASE=1/PROGRAM=2/READ=3/CANCEL=4; virtual addrs 0x40000000 app-data, 0x40020000|idx collections,
  0x40030005 stored indexes (4B = u16 start,end), 0x40030006 platform versions, 0x4003000E adv data (10B);
  response = 12-byte TelestoResponse on ctrl + data notifications; 20-byte write-with-response chunks;
  [u32 LE len] prefix for multi-packet data (TelestoLengthPrefixedData_create 0x19000).
  Transfer op: 640KB collection buffer; phases; index ring w/ rollover; no CRC/seq/FEC.
- PPResult_t (1384B, memset) returned by createAudioTimeline; audio timeline at +8:
  {collectionStartIndex u32, sampleRateHz u32, sampleCount u64, samples u16*, isMultiPart u8, isFinalPart u8}
  (cross-checked vs JNI getters offsets 0/4/8/0x10/0x18/0x19 and freeAudioTimeline freeing samples@0x10).
- Registration = programSatelliteWithUserID -> PPRingUser/PPRingApplicationData -> _serialize_v1:
  141-byte blob {version=1, timestamp, userId[128], fingerprint} — NON-SECRET. mixBits32 = avalanche
  finalizer; _fingerprint(uid) = iterated mixBits32 — user matching only, never a key.
- Persisted per-ring state (SharedPreferences "com.wtlp.haversinecache"): platform versions, serial,
  sensorConfigVersion, applicationData, advertisedFingerprint, lastTransferEndIndex. No secrets.
- Pairing write 0x00 to telestoData doesn't match any Haversine frame -> app/firmware-level trigger.
- PPErr strings resolved (0=Success … 6=Invalid raw data, 7=Incomplete, 19=Malloc failed).
- Wrote REPORT.md (final deliverable, 10 sections per brief).

### Session 2 (cont.) — CODEC SOLVED
- Disassembled (debug .so, -O0, very readable) and fully reconstructed:
  **GSParseRecordsInRawData** (0x2d644): collection container format:
  - Header variant A: [u32 LE total size, top byte 0] (4 bytes) — LE24(b0..2)==size && b3==0
  - Header variant B: [0xFF][u16 LE size-3] (3 bytes)
  - Header variant C: [BE24 size-3] (3 bytes)
  - Then TLV records: [type:1][len:2 LE][payload] (total 3+len); types 80/81 use [type:1][len:4 LE][payload]
  - Record type enum recovered via JNI constant getters (see report). Key ones:
    UNCOMPRESSED_16BIT_AUDIO=80, COMPRESSED_16BIT_AUDIO=81, COLLECTION_MULTI_PART_INFO=82,
    BUTTON_PRESS_SEQUENCE=83, LIFETIME_COLLECTION_COUNT=84, DEVICE_ID=1, PLATFORM_VERSIONS=37,
    APPLICATION_DATA_STORE=39. Unknown types 19-32,42-47,54-79 -> err 6; type 35 -> err 1.
  **PPCollection_createAudioTimeline** (0x2f964):
  - MULTI_PART_INFO payload = [startIndex u32][isMultiPart u8][isFinalPart u8]
  - UNCOMPRESSED_16BIT_AUDIO payload = [sampleRateHz u32][PCM16LE samples...]
  - COMPRESSED_16BIT_AUDIO payload = [cfg byte][bitCount u32][sampleRateHz u32][Rice bitstream...]
    cfg byte: high nibble = unary escape limit, low nibble = m (scale shift)
  - Decode loop: DDRiceDecompressionDecoder_init(dec, bitstream, bitCount, 0);
    DDRiceDecompressionChannel_init(ch, payload+0(cfg), 0, 0); then per sample:
    decodeDiff(ch,dec,&diff); nextWord(ch,diff) -> store u16.
  **DDRice decoder** (reconstructed pseudocode in REPORT.md):
  - Bitstream MSB-first. Code: bit 1 -> diff 0; bit 0 + (v-1 zeros) + 1 + sign bit -> ±v;
    escape: limit zeros + (16-m) raw bits. Zigzag: if diff >= 2^(15-m): diff -= 2^(16-m).
    sign bit set: v = 2^(16-m) - v before zigzag.
  - nextWord: B += diff; A += B (both u16, double integrator); sample = (A << m) & 0xFFFF (read as s16 LE).
  - Error 3 = end-of-bits (normal termination); sampleCount = actual decoded count.
- NO encryption anywhere in decode path: no crypto imports in either .so, decode is pure entropy+delta coding.
- Next: TelestoLengthPrefixedData_create + TelestoController (BLE app-layer framing/integrity),
  HaversineTransferCollectionsOperation phases, CollectionIndexStorage persistence, pairing write 0x00 meaning.
