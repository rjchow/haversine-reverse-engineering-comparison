# Reverse-engineering progress

## Artifacts and tooling
- Downloaded the requested device and simulator KLIBs into `artifacts/`.
- Extracted both under `extracted/`; they are Kotlin/Native 2.2.20 KLIBs with serialized IR, no LLVM bitcode/native objects in the top-level library.
- Downloaded Kotlin/Native 2.2.20 macOS toolchain under `artifacts/kotlin-native-prebuilt-macos-aarch64-2.2.20/`; `klib dump-ir` successfully recovered readable IR.
- Downloaded the two cinterop KLIBs published alongside each artifact. They contain `libPPCommon_static.a` and `libHaversineSatelliteLibrary.a`.
- Extracted/disassembled relevant ARM64 objects under `work-obj/` and `work-hsl/`.

## Strong findings so far
1. `HaversineTransferDelegate.handleDidFinish` in `work-ir.txt` parses the received complete `ByteArray` with `PPCollection(index, data)`. It emits `TransferTypeDetermined`, then `TransferInProgress`, then either `processSinglePartAudio` or `processMultiPartAudio`.
2. `MultipartCollection.addPart` appends `PPAudioTimeline.samples` using `kotlinx.io.writeShortLe`; `flushBuffer` reads with `readShortLe` into `ShortArray`. `emitCompleteTransfer` constructs `TransferStatus.TransferComplete` with that buffer and the timeline sample rate. Thus app-bound output is signed 16-bit little-endian mono samples.
3. The cinterop `PPResultAudioTimeline_t` is explicitly:
   - `uint32 collectionStartIndex`
   - `uint32 sampleRateHz`
   - `size_t sampleCount`
   - `uint16_t *samples`
   - `char isMultiPart`
   - `char isFinalPart`
   The Kotlin wrapper copies `sampleCount` unsigned 16-bit samples from native memory.
4. `PPCollection_createAudioTimeline` in `work-obj/PPCollection.o` has two branches:
   - uncompressed audio record: copies payload bytes, halves the byte count, and interprets them as 16-bit samples;
   - compressed audio record: invokes `DDRiceDecompressionDecoder_init`, `DDRiceDecompressionChannel_init`, loops `DDRiceDecompressionChannel_decodeDiff`, then `nextWord`, and returns reconstructed 16-bit samples. This is custom “DDRice” compression, not ADPCM/Speex/Opus.
5. `DDRiceCompression.o` exports the custom encoder/decoder. It uses bit-level Rice-like coding with a 4-bit parameter in the audio header, variable bit reads, differential reconstruction, and adaptive per-channel stats. No known codec library calls are present.
6. Device PPCommon archive has no AES/ChaCha/SHA/HMAC/CRC/encryption symbols or strings. HSL archive likewise has no application crypto symbols/imports. Crypto search has not found an app-layer recording cipher.
7. HSL `HaversineTransferCollectionsOperation` C source/debug strings and ARM64 code show transfer phases `READ_STORED_INDEXES`, `READ_COLLECTIONS`, `READ_ADVERTISING_DATA`, `FINISHED`. It reads:
   - stored indexes at virtual address `0x40030005`, type 3/read, length 4;
   - each collection at `0x40020000 | collectionIndex`, type 3/read, offset 0, length 0 (infer length from prefix);
   - current advertising data at `0x4003000e`, type 3/read, length 10.
   Collection chunks accumulate into a per-collection buffer (max `0xA0000` / 655,360 bytes in HSL) and are delivered as one `NSData`/`ByteArray` to the Kotlin delegate.
8. HSL metadata defines `TelestoStoredCollectionIndexes { uint16 rangeStart; uint16 rangeEnd; }`, `TelestoRequest` as packed 13 bytes (`uint8 type`, `uint32 address`, `uint32 offset`, `uint32 length`), and `TelestoResponse { uint32 error; uint32 info; uint32 length; }`.
9. HSL `TelestoController` accumulates exactly a 12-byte response header and then receives `length` data bytes. It has controller error handling and pending-confirmation/outbox state, but no visible CRC/hash/sequence field in the application protocol.
10. Registration/user data is not a secret: KLIB IR `programSatelliteWithUserID` calls `PPRingUser_init(userId)`, gets POSIX time, calls `PPRingApplicationData_init`, serializes it, and programs it as application data. PPCommon metadata defines `PPRingApplicationData_t` as `{ uint32 fingerprint; uint32 timestamp; struct { char uid[129]; } user; }`, serialized version 1. The fingerprint is a custom 32-bit mixing function over UID bytes; it is not encryption. HSL cache persists only state metadata/applicationData/fingerprint/last transfer index in `NSUserDefaults` with prefix string `HaversineSatelliteState_` plus satellite UUID.
11. Therefore current evidence strongly disproves the proposed registration-derived shared-secret design in Haversine. Pairing/bonding is BLE security; Haversine has no keychain/secret/crypto path. Physical flash-at-rest encryption entirely inside ring firmware remains unknown because the requested artifacts begin at the phone-side Haversine boundary.

## Important recovered source paths/symbols
- `work-ir.txt`: recovered Kotlin IR; source paths identify the `haversine-kmp/...` source tree.
- `work-ir.txt` around lines 972–1458: `HaversineTransferDelegate.handleDidFinish`, multipart/single-part processing, `emitCompleteTransfer`.
- `work-ir.txt` around lines 3408–3747: `MultipartCollection` implementation.
- `work-ir.txt` around lines 7750–8064: `KMPHaversineSatelliteManager.programSatelliteWithUserID`.
- `work-obj/PPCollection.o`, `ppcollection-disasm.txt`: collection parser/audio decoder.
- `work-obj/DDRiceCompression.o`, `ddrice-disasm.txt`: custom compression/decompression primitives.
- `work-obj/PPRingApplicationData.o`, `pring-disasm.txt`: registration data serialization/fingerprint.
- `work-hsl/HaversineTransferCollectionsOperation-1b03d6b35479582ddfbbfc570532354b.o`, `transferop-c-disasm.txt`, `transfer-dwarf.txt`: collection transfer phases and chunking.
- `work-hsl/TelestoController.o`, `telestoctrl-disasm.txt`: Telesto response/data framing and controller checks.
- `work-hsl/HaversineEnvironment.o`, `env-disasm.txt`: NSUserDefaults cache.

## Outstanding tasks
- Determine the actual production ring sample rate for the target firmware. The decoder reads `sampleRateHz` per record; the public firmware image contains 8000/16000 configuration values but does not map them symbolically to voice capture.
- Determine whether a particular ring firmware always selects compressed DDRice or may emit the supported uncompressed record. A live collection capture or ring firmware source would settle this; Haversine supports both.
- Finish documenting characteristic mapping/transport sequencing for an independent client. The open iOS app confirms `DAAD3D52-237C-90A7-B54B-8854A134D801` is the Telesto data characteristic and pairs by writing `00` with response; exact live notification sequencing and the C0EF/1D1F assignment should still be validated.
- Confirm safe deletion/erase semantics and retry behavior with a live ring; transfer read/framing is understood, but destructive commands should not be guessed.
- Physical flash-at-rest encryption remains unknown from phone-side artifacts; no Haversine-side key/decrypt path exists.
- `report.md` is drafted with all requested sections and evidence. Keep this file updated if any final evidence changes the report.
- Full phone-side Telesto protocol documentation written to `telesto-protocol.md`, including BLE UUID roles, wire structs, operation/error enums, virtual address map, controller/link state machines, cancellation, collection-transfer sequence, payload layouts, and independent-client rules.

## Telesto protocol status
- Phone-side Telesto framing and state machine are now documented in `telesto-protocol.md`.
- Exact characteristic roles are resolved from `CBConnectedPeripheralAdaptor.o`: Ctrl `C0EF...`, Data `DAAD...`, System Input `1D1F...`; Ctrl/Data use write-without-response, System Input uses write-with-response.
- Telesto collection buffer limit corrected: ARM64 `0xa0, lsl #12` means `0xa0000` (655,360) bytes, not `0xa000`.
- Remaining Telesto uncertainty is ring-firmware-side semantics (`info`, destructive operations, sensor/image payload rules), not the phone-side read framing. The phone-side protocol is now documented sufficiently for a read-only independent client.

## Report status
- Full technical report written to `report.md` with the requested sections 1–10.
- Exact compressed audio record header and DDRice reconstruction are recovered using the simulator archive's x86_64 slice; the objects are preserved under `work-simx/` and disassembly under `ppcollection-x86-disasm.txt` / `ddrice-x86-disasm.txt`.
- Remaining primary uncertainty is not the decoder: it is the actual production ring firmware's chosen sample-rate value and whether all firmware variants select compressed versus the supported uncompressed audio record. Physical flash-at-rest encryption also cannot be ruled out solely from a phone-side library; no Haversine-side decrypt/key path exists.

## Additional findings (current pass)
- `PPRingApplicationData_t` metadata and `pring-disasm.txt` prove the registration payload is plaintext version-1 data: a 32-bit fingerprint, 32-bit timestamp, and 129-byte UID. `PPRingApplicationData_serializedSize` returns `0x8d` (141 bytes); the fingerprint routine is a custom mixing function and comparison only checks its low 16 bits. No cryptographic primitive is involved.
- HSL metadata confirms `TelestoRequest` is packed 13 bytes: type at offset 0, address at 1, offset at 5, length at 9. Static transfer requests decoded from `HaversineTransferCollectionsOperation` constants are `READ_MEMORY (3)` at address `0x40030005`, length 4 (stored indexes), and `0x4003000e`, length 10 (advertising data). Collection reads use address `0x40020000 | index`, offset 0, length 0 (infer length from prefix).
- `TelestoResponse` is exactly `{uint32 error, uint32 info, uint32 length}`. `TelestoController` waits for this 12-byte response and then consumes exactly `length` data bytes. It has outbox pending-confirmation state and controller/operation error propagation, but no CRC/hash/sequence field is present in these structures.
- HSL `HaversineTransferCollectionsOperation` has C DWARF/source identifiers, including phase names, collection buffer, `currentOperationBytesRead`, `collectionIndexes`, `advertisingData`, and `TLV_HEADER_SIZE`; its max collection accumulation is `0xA0000` (655,360) bytes. Each complete collection is passed as one `NSData` to the Kotlin delegate.
- `DDRice` decoder evidence: bitstream reader is MSB-first; audio header low nibble controls a power-of-two scale (`0x10000 >> k`); the normal path reads a leading zero, a unary-like quotient, a sign/mapping bit, then `16-k` remainder bits when needed; fallback reads `16-k` bits. `nextWord` reconstructs a scaled 16-bit word by accumulating decoded differences. This is custom adaptive Rice/differential coding, not IMA ADPCM (no IMA tables/index state), Speex, Opus, or another linked codec.
- The public firmware image decoded from `artifacts/haversine_update.json` contains data values 8000 (`0x1f40`) and 16000 (`0x3e80`) in a configuration region, but this is not yet tied conclusively to the compressed audio record’s runtime sample-rate field. The parser itself reads sample rate from each collection record; no hardcoded rate was found in PPCommon.
- The exact compressed audio record header is now known via the simulator x86_64 slice: after the tag, `uint32 contentBytes`, `uint8 mk`, `uint32 compressedBitCount` at +5, `uint32 sampleRateHz` at +9, payload at +13. The size check subtracts 9 metadata bytes (`0x48` bits).
- Device and simulator top-level Haversine IR (`bodies.knb`, `strings.knt`, metadata) is byte-identical; only manifest target and archive/native cinterop artifacts differ.
- `GSParseRecordsInRawData` (`work-obj/PPParsing.o`, offset 0) reveals the collection container: the first 3 bytes are a length prefix. If byte 0 is not `0xff`, bytes 0..2 are a big-endian 24-bit value equal to `collectionSize - 3`; if byte 0 is `0xff`, bytes 1..2 are a little-endian 16-bit value equal to `collectionSize - 3`. Records then begin at offset 3. Each record has a one-byte tag followed by a length field; most tags use a little-endian 16-bit length, while two special record kinds use a 32-bit length. The parser validates lengths and bounds but has no CRC/hash.
- The special 32-bit-length branch is the audio-record branch. Cross-checking the x86_64 slice in the simulator cinterop archive (which makes the stores clearer than ARM64) reconstructs the audio records relative to the pointer after the one-byte tag:
  - uncompressed: `uint32 contentBytes` at +0, `uint32 sampleRateHz` at +4, raw `uint16` sample bytes at +8; `contentBytes = 4 + sampleBytes`;
  - compressed: `uint32 contentBytes` at +0, one compression-header byte at +4 (`high nibble m`, `low nibble k`), unaligned little-endian `uint32 compressedBitCount` at +5, unaligned little-endian `uint32 sampleRateHz` at +9, compressed bitstream at +13. The decoder asserts `compressedBitCount <= contentBytes*8 - 0x48` (0x48 = 9 header bytes after the size field), then reads exactly `compressedBitCount` bits.
- `GSCollectionMultiPartInfo_t` is exposed in PPCommon metadata as a packed 8-byte record: `uint16 size` at 0, `uint32 startIndex` at 2, `uint8 isMultiPart` at 6, `uint8 isFinalPart` at 7. These fields are separate from the audio payload and populate `PPAudioTimeline`.
- The exact compressed record layout is now recovered from the simulator’s x86_64 static archive (`work-simx/PPCollection.o`, `PPCollection_createAudioTimeline`): `contentBytes` includes the 9 bytes after the size field (`1-byte m/k header + 4-byte bit count + 4-byte sample rate`) plus compressed payload; the bit-capacity check subtracts `0x48` bits. The sample rate is therefore definitely at compressed-record offset +9, not +4.
- The x86_64 DDRice disassembly (`ddrice-x86-disasm.txt`, same logic as ARM64) resolves the decoder: first bit 1 => diff 0; first bit 0 => unary count `q` up to header `m`; a following bit selects `q` or `(65536 >> k) - q`; if the unary threshold is reached, it reads `16-k` raw bits. `nextWord` performs `d1 += diff; word += d1; output = (word << k) & 0xffff`, proving a second-order differential predictor plus Rice-like variable coding. Bits are read MSB-first (`7 - bitOffset`).
- `HaversineReadLastAudioSamplesOperation` independently calls `PPCollection_createFromBinaryData` and `PPCollection_createAudioTimeline`, then processes native `uint16` samples; this corroborates that decoding occurs on the phone after collection transfer, not in the BLE layer.

## Unreversed/partially reversed Haversine areas
- BLE characteristic assignment for C0EF/1D1F and exact live notification/write sequencing; generic Telesto controller framing is reversed.
- `HaversineSensorStreamOperation` (calibrated/uncalibrated/raw sensor streaming), sensor configuration/calibration payload semantics, and `HaversineSensorServiceOperation`.
- `HaversineSuotaOperation` firmware-update transport, retry policy, bootloader/authentication behavior, and image verification.
- Debug/core-dump reads (`HaversineReadDebugInfoOperation`, `eraseDebugData`), reboot-reason decoding, and complete diagnostics metric payloads (`HaversineDiagnosticOperation`).
- Non-audio memory operations: exact erase-collections semantics, application-data erase/clear, LED programming, collection-count programming, and cache-update behavior.
- `HaversineSystemInputOperation` event payloads/direction and its interaction with system-input notifications.
- Full advertisement/permission/state policy, connection throttling, error-recovery, and firmware-update policy.
- These areas are not required for a read-only recording downloader; the transfer/Telesto/PPCollection/DDRice path is the substantially reversed subset.
- Open-app pairing behavior is now confirmed: Android requests an OS BLE bond; iOS connects and writes one byte `00` with response to `DAAD3D52-237C-90A7-B54B-8854A134D801`, retrying three times. Firmware `<3.62.0` additionally receives plaintext user application data; `>=3.62.0` skips it. Android then erases existing collections as an app policy, not a decode requirement.
- Read-only transfer impact is now clearer from `RingSync.kt` and `PrefsCollectionIndexStorage.kt`: HSL collection transfer performs reads, while erase is a separate explicit operation. An independent app will not advance the official app's local last-successful index, so the official app may redownload/duplicate recordings later, but read-only access should not delete ring collections. Concurrent transfers can cause an official transfer failure.
