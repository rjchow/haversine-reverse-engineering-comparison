# Haversine Reverse-Engineering Progress

Last updated: 2026-08-20

This is the durable investigation log for `brief.md`. It records verified facts,
working hypotheses, failed approaches, generated artifacts, and outstanding work.
Major conclusions must eventually be backed by a reproducible command, archive
member, symbol/function, offset, metadata entry, or recovered pseudocode.

## Status legend

- `[x]` complete
- `[~]` in progress
- `[ ]` pending
- `[!]` blocked or failed approach (with reason and fallback)

## Current objective

Determine the Index 01 recording representation and the complete path from ring
storage/transfer through Haversine decoding to `TransferComplete.samples`, while
separately establishing framing/integrity behavior and whether any persistent
application-layer recording cryptography exists.

Completed follow-up objective: reconstruct how the Pebble app discovers,
downloads, and installs Index ring firmware; identify the firmware
container/validation and SUOTA transport; and acquire the publicly available
exact firmware image without bypassing authentication or access controls.

## Work plan

- [x] Acquire both Maven Central `.klib` artifacts and record hashes.
- [x] Unpack and inventory every member in both artifacts and their native
  cinterop dependencies.
- [x] Compare manifests, metadata, symbols, strings, Kotlin IR, and native
  objects. The two main KLIB IR dumps are byte-identical.
- [x] Locate `TransferStatus.TransferComplete` and trace `samples` backward.
- [x] Identify codec/sample rate/sample width/channels/frame size/byte order.
  The self-describing format is fully recovered; an actual recording is still
  needed only to observe which dynamic sample-rate/config values shipping
  firmware chooses.
- [x] Reconstruct protocol layers, incremental transfer, integrity, ACK/retry,
  native modular-index mechanics/Kotlin bridge caveat, and the absence of an
  application delete/ack command.
- [x] Trace registration, persistent state, key management, and crypto call paths.
- [x] Cross-check all important findings between device and simulator builds.
- [x] Produce and independently review the final evidence-cited technical report.
- [x] Trace app-side ring firmware version discovery and download.
- [x] Reconstruct the Haversine/SUOTA firmware transfer and validation path.
- [x] Locate, preserve, hash, and validate the current public firmware image
  and all 18 Core Ring revisions reachable from the production branch.

## Activity log

### 2026-08-20

- Started the Index firmware-update follow-up in parallel across the public app,
  exact KLIB/native SUOTA implementation, and public artifact/endpoints.
- Scope boundary: public unauthenticated acquisition is allowed; bypassing
  credentials, authorization, or access controls is not.
- Completed the firmware-update follow-up. Haversine `03202f5` performs an
  unauthenticated HTTPS GET of
  `https://raw.githubusercontent.com/HyperionSensing/firmware_releases/core_ring/haversine_update.json`.
  The JSON `image` field is the complete firmware payload in Base64; there is
  no second binary URL or stable app-created firmware file.
- The manager prefetches the manifest at construction, caches the decoded
  candidate in memory for three hours (in addition to Ktor `HttpCache`), and
  automatically considers it when a ring advertises. The shipping eligibility
  gates are RSSI at least -85 dBm, an exact manifest/ring hardware match, and a
  strictly newer manifest firmware version.
- Recovered the complete native update state machine. It uses normal
  Haversine/Telesto rather than the standard Renesas SUOTA GATT service:
  READ platform versions at `0x40030006`; system input 7; ERASE stationary
  data at `0x40000002`; ERASE then PROGRAM the exact decoded bytes at
  `0x40060000`; system input 12/PANIC to reset; reconnect; and READ final
  platform versions. The production Android wrapper passes `force=false` and
  `skipVerification=false`.
- The native client does not parse the image header or perform a hash,
  signature, CRC, or readback check. Its post-reset verification compares the
  reported firmware major/minor with the manifest. Any additional acceptance
  or boot validation is ring-side and remains invisible in the client
  artifacts.
- Acquired public Core Ring 3.75 for hardware 11.0 from immutable upstream
  commit `e8c7e2352460eeb87f7b905e12e7808abd2c5cce`. Preserved the exact
  39,203-byte manifest and its decoded 29,288-byte image at
  `artifacts/firmware/`.
- Independently verified that the saved image exactly equals the manifest's
  Base64 decode. Image SHA-256 is
  `993ec97e0db831e3f35d5c53ed8809a6dbe2db08879637f981cdda0e2c4ba090`;
  manifest SHA-256 is
  `6e078a03ac84eff086825218038451c8fccbbe52ccd104930835221b916a0b91`.
- Parsed the exact 64-byte Dialog/Renesas single-image header: signature
  `70 51`, valid flag `aa`, 29,224-byte executable, stored CRC-32
  `0x1e3551dd`, and security flags `0x00`. CRC recomputation over the executable
  matches exactly. Under the documented header format, `0x00` declares the
  image neither signed nor encrypted.
- Preserved 18 reachable historical Core Ring manifest/image pairs under
  `artifacts/firmware/history/`; every saved image passes header-size and
  CRC-32 validation. `artifacts/firmware/SHA256SUMS` records their hashes.
- Read `brief.md` completely.
- Confirmed the workspace initially contained only `brief.md`; no prior artifacts,
  source tree, or progress notes were present.
- Created `artifacts/`, `extracted/`, `analysis/`, `scripts/`, and `report/`.
- Tool preflight found Apple `file`, `strings`, `nm`, `otool`, and `objdump`.
  LLVM command-line tools, Ghidra, and rizin/radare2 were not initially on `PATH`;
  alternate installed toolchains and package contents still need inspection.
- Downloaded the exact iOS ARM64 KLIB (135,410 bytes, SHA-256
  `4f14675b857cff246dbc8ad607c3003972cc04506823e5ab40a42055eb7ec576`)
  and exact simulator ARM64 KLIB (135,476 bytes; full hash is being recorded in
  the simulator inventory).
- Both main KLIBs are ZIP archives containing serialized Kotlin IR/linkdata.
  They do **not** contain the native implementation directly: their manifests
  name Maven-published `cinterop-PPCommon` and
  `cinterop-haversineSatelliteLibrary` companion KLIBs.
- Downloaded/extracted the companion native KLIBs. The simulator PPCommon
  archive contains universal `libPPCommon_static.a`; its objects include
  `PPCollection.o` and `DDRiceCompression.o`. The device companion contains the
  corresponding ARM64 Mach-O objects. DWARF/source-path/type data is present and
  is now a priority source of labels and layouts.
- Downloaded the same release's Android debug AAR as a cross-platform
  illumination artifact. It contains unobfuscated JVM classes for the common
  Kotlin wrapper and x86/x86_64/ARM native versions of the same PPCommon and
  Haversine libraries. Decompiled 131 JVM classes with CFR into
  `analysis/decompiled_android_debug/`.
- Recovered the high-level audio boundary:
  `collectionTransferDidFinish(ByteArray, index)` constructs `PPCollection`;
  its native path is `PPCollection_createFromBinaryData` then
  `PPCollection_createAudioTimeline`; `PPAudioTimeline` copies the native
  `uint16_t *samples` result into a Kotlin `ShortArray` using little-endian
  conversion; multipart parts are concatenated as little-endian PCM16 samples;
  `TransferComplete` receives that `ShortArray` and the native timeline's sample
  rate.
- Native symbol/metadata inventory found distinct record identifiers
  `UNCOMPRESSED_16BIT_AUDIO` and `COMPRESSED_16BIT_AUDIO`. It also found
  `DDRiceDecompressionDecoder_{init,readBit,readBits}` and
  `DDRiceDecompressionChannel_{init,decodeDiff,nextWord,prevWord}`, imported by
  `PPCollection_createAudioTimeline`.
- Important caution: these names strongly identify a differential Rice-family
  compression path, but the exact bitstream, parameters, framing, and actual
  runtime branch remain under disassembly. No final codec claim is recorded yet.
- Installed the official Ghidra 12.1.3 distribution, verified its published
  checksum, built its macOS ARM64 native decompiler component, and exported
  targeted native pseudocode from the Android x86_64 libraries and simulator
  objects. Swift analyzer exceptions were nonfatal; Apple DWARF, symbols,
  relocations, and cross-architecture instruction traces remain authoritative.
- Used the exact Kotlin/Native 2.2.20 `klib` utility to recover 8,689 lines of
  readable IR from each main KLIB. The device and simulator IR dumps have the
  identical SHA-256
  `0217f3549e3c5d54b79c2b8092a687f4cd22106d6f029b4ba62e66722ab8f300`.
- Recovered the collection audio TLVs and both audio layouts. Type `0x50`
  carries uncompressed PCM16; type `0x51` carries custom second-difference
  DD-Rice data. Both contain a little-endian 32-bit sample rate and produce a
  single sequence of signed 16-bit samples. There is no fixed sample count or
  fixed codec frame size in the compressed record: its explicit bit count is
  the terminator.
- Recovered the DD-Rice bitstream at instruction level. Bits are consumed
  MSB-first. The channel configuration byte's low nibble is a reconstruction
  left shift/quantization value and its high nibble is a unary cutoff. Each
  decoded value is a signed second difference, followed by two wrapping
  16-bit integrations and the configured left shift. A literal escape uses
  `16 - shift` bits. This is not IMA ADPCM, Speex, or Opus.
- Recovered native Telesto structures from simulator DWARF and disassembly.
  Requests are packed 13-byte records (`type:u8`, `address:u32le`,
  `offset:u32le`, `length:u32le`). Responses are packed 12-byte records
  (`error:u32le`, `info:u32le`, `length:u32le`). Neither contains a sequence
  number, checksum, authentication tag, or nonce.
- Traced collection enumeration and reads. Haversine first reads four bytes
  from virtual address `0x40030005` to obtain two little-endian 16-bit stored
  collection indexes, then reads each collection from
  `0x40020000 + collectionIndex`. It streams the response payload into a
  per-collection buffer (maximum `0xA0000` bytes) and passes the complete
  collection `ByteArray` to PPCommon. After a range it reads ten advertising
  bytes at `0x4003000e` to detect newly arriving collections.
- Traced Android BLE adaptation as an independent behavioral check. The
  13-byte Telesto request is written directly to the control characteristic,
  and response payload bytes arrive directly on the data characteristic.
  Android splits outgoing writes into at most 20-byte GATT writes and forwards
  arbitrary incoming notification chunks without adding a Haversine header,
  CRC, sequence number, or crypto. Telesto control/data use write type
  `WRITE_TYPE_NO_RESPONSE`; write completion is transport flow control, not an
  application acknowledgement. The system-input characteristic uses
  `WRITE_TYPE_DEFAULT` (with response).
- Located the exact BLE UUIDs:
  service `607B5C9B-3700-4E94-F44A-2DF900BCB0C3` (or assigned 16-bit service
  `FCC9`), data `DAAD3D52-237C-90A7-B54B-8854A134D801`, control
  `C0EF558A-2058-FABF-A140-8D5ACDE50B39`, and system input
  `1D1F4039-23F5-33B2-C24E-704351F20585`.
- Correlated the exact Haversine release to public mobile-app commit
  `6d6e2ebb...`. The app removes DC bias, resamples from the sample rate
  supplied by each transferred collection to 16 kHz, and serializes raw mono
  PCM16 little-endian. This proves that 16 kHz is an app output target, not the
  ring's source rate.
- Built a native validation harness against the **exact simulator ARM64
  `DDRiceCompression.o`**. After changing only its Mach-O build-platform load
  command from iOS Simulator to macOS, the shipped encoder generated test
  vectors for configs `0x30`, `0x40`, `0x51`, and `0x72`, and the shipped
  decoder reproduced all expected samples. This validates signed codewords,
  bounded-unary/raw-escape behavior, modulo-16-bit integration, and
  nonzero-shift quantization independently of Ghidra pseudocode.
- Implemented `scripts/decode_index_collection.py`, a standard-library-only
  independent collection/DD-Rice decoder that emits PCM16LE or WAV. Its
  self-test embeds all four exact-native vectors. Added envelope, multipart,
  malformed-length, and native-vector tests in
  `scripts/test_decode_index_collection.py`; all tests pass.
- Finished the exact collection envelope:
  - if byte 3 is zero, bytes 0..3 are a little-endian total buffer length and
    records start at offset 4;
  - otherwise a three-byte header declares `bufferLength - 3`: `0xff` followed
    by `u16le`, or a normal `u24be`; records start at offset 3;
  - ordinary TLVs use `u8 type + u16le length`; audio `0x50`/`0x51` use
    `u8 type + u32le length`.
- Cross-checked the iOS CoreBluetooth adapter. Telesto control and data request
  `.withoutResponse`; it fragments at
  `maximumWriteValueLength(for: .withoutResponse)`, uses up to three
  no-response writes, and may insert a `.withResponse` write for pacing when
  the characteristic supports it. The system-input path requests
  `.withResponse`. Incoming notification data is forwarded unchanged.
- Confirmed there is no recording acknowledgement or deletion operation in the
  transfer state machine. All recording operations are Telesto READs.
  Haversine remembers successful collection indexes locally and the ring
  exposes a wrapping stored-index range. Native membership walking has a
  defensive guard at roughly 512 steps, but this is not a proven firmware
  maximum and the Kotlin `IntRange` bridge complicates end-to-end rollover.
  The common delegate advances its app-provided `CollectionIndexStorage`
  **before**
  PPCollection parsing, so corrupt-but-completely-received collection data is
  reported as irrecoverable rather than automatically reread.
- Finished the remaining collection metadata records. Type `0x52` carries
  multipart origin/index and two boolean flags; type `0x53` carries a button
  sequence/count plus packed LSB-first long/short bits; type `0x54` carries a
  32-bit lifetime collection count. These are independent TLVs inside the same
  outer collection object.
- Finished the pairing/crypto/persistence audit. Registration serializes a
  versioned 141-byte public application-data record containing a 32-bit
  non-cryptographic UID fingerprint, Unix timestamp, and 129-byte UID field.
  Telesto prepends its ordinary four-byte program length and writes it with
  operation type 5 to virtual address `0x40000000`. There is no challenge,
  response, key exchange, KDF, cipher, or secret result.
- Confirmed the observed `DAAD...` characteristic is Telesto's generic data
  channel, not a pairing/key characteristic. Android explicitly requests OS
  Bluetooth bonding before application-data programming; iOS relies on
  connection-triggered CoreBluetooth pairing. The precise BLE SMP association
  model remains firmware/OS territory, but no application recording key is
  involved.
- Audited Haversine persistence on both platforms. iOS stores JSON state under
  `HaversineSatelliteState_<UUID>` in `NSUserDefaults`; Android stores Base64
  Java-serialized state in `SharedPreferences` file
  `com.wtlp.haversinecache`, keyed by the MAC address without colons. The fields
  are identity/version/config/application data/fingerprint/last index—not a
  secret—and there is no Keychain/Keystore path in recording decode.
- The recording decoder has no ring identity, persisted-state, token, or key
  input. Consequently, a captured valid collection remains decodable after
  clearing application pairing state. Clearing the OS bond may prevent a new
  BLE connection, but cannot change the plaintext collection decoding
  algorithm.
- Completed `analysis/independent_client_spec.md`, including discovery,
  subscription, pairing/registration, Telesto operation serialization,
  modular index selection, raw staging versus processed checkpoints,
  multipart handling, strict error policy, and a read-only-first safety plan.
- Drafted and iteratively audited the full ten-section report at
  `report/haversine_reverse_engineering_report.md`. The report answers every
  brief question and preserves the three material uncertainty boundaries:
  production dynamic codec/rate values, physical flash behavior, and
  firmware-defined delete/pairing semantics.
- A brief-to-evidence coverage audit and a hostile technical proofread caught
  and corrected several edge cases:
  - the `<= 0xef` limit belongs to the shipped encoder initializer; the native
    collection decoder accepts `0xf0..0xff`;
  - decoder status `3` is also returned for EOF in the middle of a codeword,
    which native PPCollection accepts as end-of-stream;
  - control/data notifications can interleave, including data before the full
    control response;
  - excess data is capped/warned by native code, whereas oversized control
    input is an error;
  - a roughly-512-step native guard is not a proven ring range maximum;
  - the Kotlin `IntRange` bridge makes integrated `uint16` rollover behavior
    an outstanding live/synthetic test;
  - public-app `last_sync_index` is one fixed/global settings value, not
    per-ring state.
- Extended the exact-object native harness with decoder-only edge cases.
  Config `0xf0` decodes successfully and a one-bit truncated codeword returns
  native status `3`, matching ARM64/x86_64 disassembly.
- Re-ran validation after all corrections:
  `decode_index_collection.py --self-test` passes four exact-native vectors;
  `test_decode_index_collection.py` passes five tests; the rebuilt C harness
  passes four round trips plus both decoder edge cases.
- Recomputed all six exact KLIB/cinterop SHA-256 values and confirmed they
  match the acquisition ledger and report. One `shasum` retry failed because
  of an environment configuration issue; a portable invocation succeeded.
- Closed the release gate. All ten required report sections are present, all
  literal evidence paths resolve, Markdown structure checks pass, the hostile
  proofreader reports no remaining release blocker, and the final coverage
  checklist is fully checked.

## Verified evidence

- `extracted/android-debug/classes.jar`,
  `coredevices/haversine/ppcommon/PPCollection.class`:
  `ByteArray` is passed to native `PPCollection_createFromBinaryData`; audio is
  obtained with `PPCollection_createAudioTimeline`.
- Same JAR, `PPAudioTimeline.class`: native result fields include
  `sampleRateHz`, `sampleCount`, `isMultiPart`, `isFinalPart`,
  `collectionStartIndex`, and `uint16` samples. The wrapper requests the sample
  buffer as bytes and reads it through a `ByteBuffer` explicitly ordered
  `LITTLE_ENDIAN` into `short[]`.
- Same JAR, `MultipartCollection.class`: decoded `short[]` parts are appended
  with `writeShortLe`; `flushBuffer()` reads `readShortLe`, and all parts must
  have the same reported sample rate. Collection-index contiguity is checked.
- `libPPCommon_static.a` / Android `libppcommon.so`: audio record constants
  include `UNCOMPRESSED_16BIT_AUDIO` and `COMPRESSED_16BIT_AUDIO`; native
  differential Rice encoder/decoder symbols are present, and the timeline
  creator references the decompressor.
- Both platform manifests/Gradle variants name PPCommon and Haversine Satellite
  companion cinterop libraries, so the native implementation is part of the
  exact published iOS dependency graph rather than an unrelated Android-only
  library.
- `PPParsing.o::_GSParseRecordsInRawData` dispatches audio codes `0x50` and
  `0x51` and treats their following lengths as 32-bit little-endian values.
  `PPCollection.o::_PPCollection_createAudioTimeline` handles both branches.
- Uncompressed audio TLV (offsets from the type byte):

  | Offset | Size | Field |
  | ---: | ---: | --- |
  | 0 | 1 | type `0x50` |
  | 1 | 4 | payload length, `u32le` |
  | 5 | 4 | sample rate Hz, `u32le` |
  | 9 | variable | signed PCM16LE samples |

  The sample count is `(payloadLength - 4) / 2`.
- Compressed audio TLV:

  | Offset | Size | Field |
  | ---: | ---: | --- |
  | 0 | 1 | type `0x51` |
  | 1 | 4 | payload length, `u32le` |
  | 5 | 1 | DD-Rice channel configuration |
  | 6 | 4 | compressed bit count, `u32le` |
  | 10 | 4 | sample rate Hz, `u32le` |
  | 14 | variable | MSB-first DD-Rice bitstream |

  Native code checks
  `compressedBitCount <= (payloadLength - 9) * 8`, initializes exactly one
  channel with zero predictor state, and decodes until the stated bit count is
  exhausted. Native status `3` also accepts a limit reached mid-codeword; the
  independent decoder deliberately rejects that malformed tail.
- DD-Rice reconstruction, with wrapping signed/unsigned 16-bit arithmetic:

  ```text
  shift = config & 0x0f
  unaryLimit = config >> 4
  firstDifference = 0
  sample = 0
  for each decoded signed secondDifference:
      firstDifference = uint16(firstDifference + secondDifference)
      sample = uint16(sample + firstDifference)
      emit int16(uint16(sample << shift))
  ```

  A one bit represents zero. A zero-led unary code represents a small signed
  nonzero difference; reaching the configured unary cutoff enters a
  `16 - shift`-bit literal escape. The encoder object independently contains
  the inverse second-difference calculation.
- `TelestoController.o` DWARF defines `TelestoRequest` as 13 packed bytes and
  `TelestoResponse` as 12 packed bytes. `TelestoController_receiveCtrlBytes`
  accumulates exactly 12 response bytes; `receiveDataBytes` streams exactly
  `response.length` payload bytes to the current operation. Oversized control
  input is an error; excess data is capped/truncated with a warning.
- `HaversineTransferCollectionsOperation-*.o` constructs READ requests for
  addresses `0x40030005`, `0x40020000 + uint16(index)`, and `0x4003000e`.
  The recording bytes are not decrypted or transformed between Telesto receipt
  and `PPCollection_createFromBinaryData`.
- `LinkTransport.java` sets Telesto data/control characteristics to Android
  write type `1` (`WRITE_TYPE_NO_RESPONSE`), slices outgoing buffers at 20
  bytes, and directly forwards notifications to
  `receiveTelesto{Ctrl,Data}Bytes`.
- `CBConnectedPeripheralAdaptor.o` calls
  `maximumWriteValueLengthForType:` with CoreBluetooth type 1 and writes
  Telesto data/control through type 1; its generic sender inserts an occasional
  type-0 write for pacing where supported. There is no Haversine header around
  a fragment.
- Exact recovered collection envelope:

  | Form | Declared length | First TLV |
  | --- | --- | ---: |
  | byte 3 is zero | `u32le(data[0:4]) == bufferLength` | 4 |
  | byte 0 is `0xff` | `u16le(data[1:3]) == bufferLength - 3` | 3 |
  | otherwise | `u24be(data[0:3]) == bufferLength - 3` | 3 |

  Native `GSParseRecordsInRawData` rejects an outer-length mismatch and unknown
  record codes. The independent decoder additionally performs safe per-TLV
  bounds validation that the native optimized parser assumes.
- Exact native validation outputs are retained under
  `analysis/native_validation/`; `scripts/ddrice_native_harness.c` directly
  calls the shipped encoder and decoder. `python3
  scripts/decode_index_collection.py --self-test` reports four passing
  vectors, including shifts 1 and 2.
- `HaversineTransferDelegate.handleDidFinish` exact Kotlin IR calls
  `CollectionIndexStorage.setLastSuccessfulCollectionIndex(event.index)` before
  checking for empty data or constructing `PPCollection`. A decode failure
  emits `IrrecoverableDataDetected`; no retry is requested.
- PPCommon contains no imports, reachable functions, or algorithm strings for
  AES, ChaCha, Poly1305, HKDF, HMAC, SHA, ECDH, nonces, IVs, keys, or
  ciphertext. Its `PPRingApplicationData_t` is 140 bytes:
  `fingerprint:u32`, `timestamp:u32`, and `userId[129]`; serialized version 1 is
  141 bytes. The fingerprint routine is a non-keyed 32-bit mixer, not a
  cryptographic primitive. The complete registration/persistence audit is in
  `analysis/pairing_crypto_audit.md`.

## Working hypotheses

- Strong inference: the collection bytes exposed at the ring's Telesto virtual
  collection addresses may be its stored object representation, because
  Haversine reads the whole virtual object by index and immediately parses its
  audio TLV. This is intentionally not promoted to fact: firmware could
  materialize, transform, or transparently decrypt it behind the virtual
  address.
- Verified conclusion, no longer a hypothesis: Haversine application-layer
  recording encryption and a registration-derived shared secret are absent in
  release `03202f5`. The complete positive call paths are keyless, and
  persistence contains only identifiers/metadata/application data/progress.

## Dead ends / failed approaches

- The main KLIBs contain serialized Kotlin IR/linkdata, not the native codec.
  Their manifests led to the separately published cinterop KLIBs containing
  the required native archives, so this was a routing discovery rather than a
  blocker.
- The published sources JAR is empty. Exact Kotlin/Native `klib dump-ir`,
  cinterop metadata, native objects, DWARF, and the same-release Android AAR
  supplied the missing implementation evidence.
- Ghidra's Swift analysis raised nonfatal analyzer exceptions on some Mach-O
  objects. Apple `nm`/`objdump`/`dwarfdump`, x86_64 cross-checks, recovered
  Kotlin IR, and targeted native/ELF decompilation were used instead.
- A final `shasum` invocation had an environment configuration issue; the
  same read-only verification succeeded with a portable invocation.

## Generated artifacts

- `PROGRESS.md` — this investigation log.
- `analysis/device_inventory.md` — completed device KLIB/dependency inventory.
- `analysis/sim_inventory.md` — completed simulator/protocol/audio inventory.
- `analysis/toolchain_strategy.md` — completed extraction/toolchain audit.
- `analysis/toolchain_iosarm64_dump_ir.txt` and
  `analysis/toolchain_iossimulatorarm64_dump_ir.txt` — exact recovered Kotlin IR.
- `analysis/decompiled_android_debug/` — CFR output for the cross-platform
  Android debug wrapper/library classes.
- `analysis/libppcommon_x86_64_dynsym.txt` and
  `analysis/libppcommon_x86_64_text_symbols.txt` — native symbol inventories.
- `analysis/ghidra_decompiled/` — targeted native PPCommon, Telesto, and
  transfer-operation pseudocode exports.
- `scripts/ExportDecompiledFunctions.java` — reproducible Ghidra export helper.
- `scripts/decode_index_collection.py` — independent collection and audio
  decoder; can produce raw PCM16LE or WAV and includes exact-native self-tests.
- `scripts/ddrice_native_harness.c` and `analysis/native_validation/` — harness,
  platform-adjusted object, executable, and exact encoder/decoder validation.
- `scripts/test_decode_index_collection.py` — envelope/PCM/multipart/bounds and
  native-vector regression tests.
- `analysis/mobileapp_repo/` — blob-filtered public app history used to correlate
  the exact Haversine release and app-side behavior.
- `analysis/collection_framing.md` — byte-accurate collection envelope and TLV
  reconstruction, including validation behavior.
- `analysis/pairing_crypto_audit.md` — registration, fingerprint, persistence,
  bonding, crypto-reachability, and decoder-dependency audit.
- `analysis/independent_client_spec.md` — independent client wire/state-machine
  specification and gap audit.
- `analysis/report_coverage_checklist.md` — brief-to-evidence release checklist
  and unsupported-claim traps.
- `report/haversine_reverse_engineering_report.md` — final ten-section
  technical report.
- `analysis/firmware_update_app_flow.md` — exact public download, manifest,
  caching, eligibility, retry, and UI/event trace.
- `analysis/ring_suota_protocol.md` — byte-accurate native firmware-update
  state machine, Telesto requests, reset/reconnect logic, and validation audit.
- `analysis/firmware_acquisition.md` — immutable provenance, header/CRC/security
  analysis, and historical firmware ledger.
- `artifacts/firmware/index01-core-ring-3.75-hw11.0-manifest.json` and
  `artifacts/firmware/index01-core-ring-3.75-hw11.0.bin` — exact current public
  manifest and decoded firmware image.
- `artifacts/firmware/history/` and `artifacts/firmware/SHA256SUMS` — 18
  reachable Core Ring history snapshots and a complete checksum ledger.

## Outstanding questions

- What sample rate and DD-Rice configuration does shipping Index firmware use
  in real recordings? The format stores both values dynamically; no captured
  collection is yet available.
- Does the ring persist the exact plaintext collection representation, or does
  firmware transparently decrypt/transform storage before serving its Telesto
  virtual collection address? This cannot be settled from client binaries alone.
- Which collection envelope variant(s) shipping Index firmware emits in
  practice? All three accepted variants are understood, but no captured
  production collection is available to identify the normal emitter choice.
- What firmware-defined action, if any, safely deletes or acknowledges a
  recording? Haversine performs READs only and does not establish one. Issuing
  Telesto ERASE against a virtual collection address would be unsafe
  speculation.
- What exact BLE SMP pairing/bonding mode and permissions the ring firmware
  requires. This does not affect the recovered plaintext application protocol,
  but a fully independent client must discover it from a ring/traffic capture.
- How the current Kotlin `IntRange`/resume bridge behaves at an actual
  `0xffff -> 0x0000` collection-index rollover. Native C is modular; integrated
  behavior needs a synthetic bridge test or near-rollover capture.
- Whether reads themselves have firmware-side retention/consume effects and
  what timing should be used while advertisement flag bit 5 says a collection
  is still in progress.
- Which checks the ring bootloader performs before booting a programmed image.
  The acquired image has a valid CRC but declares itself unsigned and
  unencrypted; client artifacts cannot establish ring-side rejection,
  fail-safe slot behavior, anti-rollback behavior, or power-loss recovery.

## Immediate next actions

1. No further static-analysis work from `brief.md` or the firmware-acquisition
   follow-up remains outstanding.
2. Optional physical-device follow-up: capture one complete collection plus
   pairing traffic to observe the production sample rate, emitted audio
   type/config, envelope, and BLE SMP behavior.
3. Optional controlled firmware follow-up: capture one official app update to
   confirm the static Telesto trace and observe bootloader/status behavior.
   Do not test a modified image or mismatched hardware without a recoverable
   device and a separately established recovery procedure.
4. Keep any independent client read-only until controlled firmware/device
   tests establish retention and safe delete/ack semantics.
