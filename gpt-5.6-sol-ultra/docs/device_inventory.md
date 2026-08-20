# Physical iOS ARM64 artifact inventory

Status: complete for first-pass device acquisition/archive inventory
Artifact version: `03202f5`
Target: `ios_arm64`
Last updated: 2026-08-20

This is the device-specific, reproducible evidence log. It intentionally does
not make codec or cryptography conclusions from names alone.

## Activity checkpoints

- Read `brief.md` and the existing shared progress log.
- Downloaded the exact KLIB named in the brief to
  `artifacts/haversine-iosarm64-03202f5.klib`.
- Saved the successful HTTP response headers in
  `analysis/iosarm64_http_headers.txt`.
- Verified the main download as an internally consistent ZIP (`unzip -t`).
- Extracted the exact main KLIB into `extracted/iosarm64`.
- Inspected the iOS variant's Gradle module metadata. It establishes that the
  variant consists of the main KLIB plus two cinterop KLIB files:
  `haversineSatelliteLibrary` and `PPCommon`.
- Downloaded and extracted both companion cinterop KLIBs into separate,
  device-specific trees. Extracted the two bundled static archives into
  `static_objects/` subdirectories.
- Began symbol, string, bitcode-wrapper, and DWARF inventory. The most important
  lead is the concrete `PPCollection_createAudioTimeline` /
  `DDRiceDecompression*` path in PPCommon.
- Recovered the audio TLV IDs, uncompressed/compressed record layouts,
  instruction-level calls into the DD Rice decoder, bit order, and output copy
  into Kotlin `ShortArray`.
- Completed a PPCommon crypto-name/import pass and inspected its fingerprint
  code. The fingerprint is a deterministic non-keyed mixer, not evidence of
  encryption.

## Acquisition and integrity

Source:

```text
https://repo1.maven.org/maven2/io/github/coredevices/haversine/haversine-iosarm64/03202f5/haversine-iosarm64-03202f5.klib
```

Main artifact:

| Property | Value |
| --- | --- |
| Size | 135,410 bytes |
| SHA-256 | `4f14675b857cff246dbc8ad607c3003972cc04506823e5ab40a42055eb7ec576` |
| SHA-512 | `de47687d8200f4ff533b0c135fa72de76e4435f11f6fc049734cba069ae901cf497bd39474bbb362c217e6bc5448f32cfcd2a3d51c9fb80c0331b5c86354ceeb` |
| SHA-1 | `44e74fa88480eed6a0bc53c3b02ddb731248a6b6` |
| MD5 | `7f3947b7cf8dfaff904dd0ce2edf9cbe` |
| Type | ZIP archive, deflate, 50 central-directory entries |
| ZIP encryption | None |

The SHA-1 and MD5 agree with Maven's `x-checksum-sha1` and
`x-checksum-md5` response headers. The SHA-256/SHA-512 agree with the values in
`artifacts/haversine-iosarm64-03202f5.module`.

The first `shasum` attempt failed. `openssl dgst` produced the values above.

The Gradle module lists these additional files as part of the
`iosArm64ApiElements-published` variant:

| File | Size | SHA-256 |
| --- | ---: | --- |
| `haversine-iosarm64-03202f5-cinterop-PPCommon.klib` | 52,154 | `d77e25abb94f8a199dab7857cb8250d0022460e0319a843fc8805c46244d2732` |
| `haversine-iosarm64-03202f5-cinterop-haversineSatelliteLibrary.klib` | 1,269,615 | `d515f1a62ad2ed7479fa964cbeb2f63e68443d4309d83c87fed4ba8f9ab1dc21` |

Extracted native payload checks:

| Payload | Size | SHA-256 |
| --- | ---: | --- |
| `libPPCommon_static.a` | 38,776 | `83101cb5c59856f54c9f76e366ce58a324bb5f76abf17f11219efb7760fe56fb` |
| PPCommon `cstubs.bc` | 38,032 | `68c4774db60fa32c6042ecd6a53d7a0fb05363c8f26fb276ab86cf5ad67563c4` |
| `libHaversineSatelliteLibrary.a` | 4,571,936 | `3683659731383b6ca779a75b05b249bacad12bbae727ccf7a948a3369c99cdaa` |
| HaversineSatelliteLibrary `cstubs.bc` | 64,192 | `73889b6685864fc76dfc199a4ee0817e26609ed76158e8bec92a3dae111622cb` |

## Exact main-KLIB structure

The main artifact contains 50 ZIP entries: 40 regular files and 10
directories. The extracted files are:

| Category | Members |
| --- | --- |
| Manifest | `default/manifest` |
| Kotlin IR | `default/ir/bodies.knb`, `debugInfo.knd`, `fileEntries.knf`, `files.knf`, `irDeclarations.knd`, `irInlineDeclarations.knd`, `signatures.knt`, `strings.knt`, `types.knt` |
| Kotlin linkdata module | `default/linkdata/module` |
| `coredevices.haversine` metadata | `00_haversine.knm` through `24_haversine.knm` (25 files) |
| `coredevices.haversine.ppcommon` metadata | `0_ppcommon.knm` through `3_ppcommon.knm` (4 files) |
| Target/native payload | None: `default/targets/ios_arm64/included/`, `native/`, and `default/resources/` are empty |

There is no Mach-O, object archive, native object, or ordinary LLVM bitcode in
the exact main KLIB. Its implementation payload is serialized Kotlin IR plus
metadata. Native code is supplied by the companion cinterop KLIBs.

Main manifest facts:

```text
abi_version=2.2.0
compiler_version=2.2.20
metadata_version=1.4.1
native_targets=ios_arm64
short_name=haversine
unique_name=io.github.coredevices.haversine:haversine
```

Its dependencies include Kotlin/Native platform libraries, kotlinx
serialization/coroutines/io, Ktor, Kermit, and, critically:

```text
io.github.coredevices.haversine:haversine-cinterop-haversineSatelliteLibrary
io.github.coredevices.haversine:haversine-cinterop-PPCommon
```

## Main metadata leads

These are declarations and names, not by themselves implementation proof:

- `13_haversine.knm` declares `TransferStatus.TransferComplete` fields
  `samples: ShortArray`, `sampleRate`, `buttonReleaseTimestamp`,
  `transferCompleteTimestamp`, and `isContiguous`.
- `02_haversine.knm` declares `HaversineTransferDelegate`,
  `processMultiPartAudio`, `processSinglePartAudio`, and
  `emitCompleteTransfer`.
- `10_haversine.knm` declares `MultipartCollection`, `sampleRate`,
  `PPAudioTimeline`, `flushBuffer(): ShortArray`, and documents that buffer
  size must be a multiple of 16-bit samples.
- `coredevices.haversine.ppcommon/2_ppcommon.knm` declares
  `PPAudioTimeline.wrap(PPResultAudioTimeline_t)`, `sampleRateHz: UInt`,
  `sampleCount: ULong`, `isMultiPart`, `isFinalPart`,
  `collectionStartIndex`, and `samples: ShortArray`.
- `coredevices.haversine.ppcommon/3_ppcommon.knm` declares
  `PPCollection(data: ByteArray)` and `audioTimeline: PPAudioTimeline`.

These declarations locate the app boundary but do not reveal the ring codec by
themselves.

## Companion cinterop archives

### PPCommon KLIB

Regular payload files:

- `default/manifest`
- `default/linkdata/module`
- `default/linkdata/package_PPCommon/0_PPCommon.knm` through
  `5_PPCommon.knm`
- `default/targets/ios_arm64/native/cstubs.bc` (LLVM bitcode wrapper)
- `default/targets/ios_arm64/included/libPPCommon_static.a`

The manifest declares a static Objective-C cinterop library and exposes these
particularly relevant forward declarations:

```text
GSSTFifoFirmwareCompressedRecord_t_
GSCompressedAudioDataRecord_t_
GSUncompressedAudioDataRecord_t_
GSCollectionStartCount_t_
PPCollection_s
```

`libPPCommon_static.a` contains the archive symbol table plus eight ARM64 Mach-O
objects:

| Member | Size (bytes) |
| --- | ---: |
| `DDRiceCompression.o` | 5,320 |
| `PPSatelliteEvents.o` | 6,336 |
| `PPParsing.o` | 5,520 |
| `PPRebootReasons.o` | 5,680 |
| `PPBluetoothUtils.o` | 800 |
| `PPTypes.o` | 2,752 |
| `PPRingApplicationData.o` | 4,216 |
| `PPCollection.o` | 4,728 |

Relevant global symbols already verified:

```text
PPCollection_createAudioTimeline
DDRiceDecompressionDecoder_init
DDRiceDecompressionDecoder_readBit
DDRiceDecompressionDecoder_readBits
DDRiceDecompressionChannel_init
DDRiceDecompressionChannel_decodeDiff
DDRiceDecompressionChannel_nextWord
DDRiceDecompressionChannel_prevWord
```

`PPCollection.o` imports the `DDRiceDecompression*` functions. Its strings
include the invariant:

```text
compressedBitCount <= compressedBytes * 8
```

The call path and record layout are established below.

#### PPCommon object and symbol counts

All eight implementation members are non-fat ARM64 Mach-O objects with an iOS
8.0 minimum version command and iOS 18.1 SDK version. The archive has 69
defined global symbols and 21 unique undefined symbols.

| Object | All symbols | Defined globals | Undefined |
| --- | ---: | ---: | ---: |
| `DDRiceCompression.o` | 31 | 17 | 1 |
| `PPBluetoothUtils.o` | 3 | 3 | 0 |
| `PPCollection.o` | 32 | 11 | 13 |
| `PPParsing.o` | 26 | 13 | 7 |
| `PPRebootReasons.o` | 63 | 1 | 0 |
| `PPRingApplicationData.o` | 30 | 15 | 7 |
| `PPSatelliteEvents.o` | 58 | 5 | 2 |
| `PPTypes.o` | 32 | 4 | 1 |

The cinterop wrapper `cstubs.bc` is an LLVM bitcode wrapper, not the codec
implementation. It defines generated Kotlin/Native bridge functions and imports
the functions in the static archive. Embedded producer/target strings report
LLVM `19.1.4` and `arm64-apple-ios12.0.0`.

#### Collection TLV dispatch

`analysis/toolchain_iosarm64_ppcommon_dump_metadata.txt`, produced with the
official Kotlin/Native 2.2.20 `klib dump-metadata`, gives the imported enum
values:

| Record code | Metadata name |
| ---: | --- |
| 80 (`0x50`) | `UNCOMPRESSED_16BIT_AUDIO` |
| 81 (`0x51`) | `COMPRESSED_16BIT_AUDIO` |
| 82 (`0x52`) | `COLLECTION_MULTI_PART_INFO` |
| 83 (`0x53`) | `BUTTON_PRESS_SEQUENCE` |
| 84 (`0x54`) | `LIFETIME_COLLECTION_COUNT` |

`PPParsing.o::_GSParseRecordsInRawData` uses a jump table at
`__TEXT,__const` address `0xb68`. Entries 80 and 81 dispatch to code offsets
`0x3c8` and `0x3d8`. Both cases read a 32-bit length at the current record
pointer, advance past four length bytes, and store the pointer in
`GSRawDataRecords_t_.uncompressedAudioData` or `.compressedAudioData`.

The cinterop metadata independently locates those pointers at offsets 264 and
272 within `GSRawDataRecords_t_`. The following audio layout therefore begins
immediately after a one-byte record code:

```text
record type: u8
payload length: u32 little-endian
payload: payloadLength bytes
```

Most non-audio collection record cases in the same parser use a 16-bit payload
length; codes 80 and 81 are among the explicit 32-bit-length cases.

#### Uncompressed 16-bit audio record

In `PPCollection.o::_PPCollection_createAudioTimeline`, instructions
`0x450..0x484` handle record code 80:

| Offset from 32-bit length field | Size | Meaning/evidence |
| ---: | ---: | --- |
| `0x00` | 4 | `payloadLength`, loaded at function offset `0x450` |
| `0x04` | 4 | `sampleRateHz`, loaded at `0x478` and returned unchanged |
| `0x08` | `payloadLength - 4` | 16-bit sample bytes, copied by `memcpy` at relocation/function offset `0x474` |

The output sample count is `(payloadLength - 4) >> 1`. The allocation masks off
the low length bit, so valid input is assumed to have an even number of sample
bytes. There is no codec call in this branch.

All multi-byte loads are native ARM64 loads without byte swapping. On this
little-endian target, the length, sample rate, and sample words are therefore
little-endian in this record representation.

#### Compressed 16-bit audio record

Instructions `0x490..0x5a8` handle record code 81:

| Offset from 32-bit length field | Size | Meaning/evidence |
| ---: | ---: | --- |
| `0x00` | 4 | `payloadLength` |
| `0x04` | 1 | DD Rice channel configuration byte |
| `0x05` | 4 | `compressedBitCount` |
| `0x09` | 4 | `sampleRateHz` |
| `0x0d` | `payloadLength - 9` | compressed bitstream bytes |

The bound check at `0x498..0x4ac` computes
`payloadLength * 8 - 72` and checks it against the 32-bit field at `+5`.
Its assertion text is exactly:

```text
compressedBitCount <= compressedBytes * 8
```

Here the value named `compressedBytes` by the assertion is the bytes remaining
after the four-byte length, while nine of those bytes are the channel config,
bit count, and sample-rate header.

The relocation-backed call sequence is:

| Function offset | Call | Arguments established by surrounding instructions |
| ---: | --- | --- |
| `0x4c0` | `DDRiceDecompressionDecoder_init` | bitstream pointer `record + 0x0d`, `compressedBitCount`, initial bit offset 0 |
| `0x4d4` | `DDRiceDecompressionChannel_init` | config pointer `record + 0x04`, channel index 0, initial state 0 |
| `0x504` | `DDRiceDecompressionChannel_decodeDiff` | one decoded difference per loop |
| `0x514` | `DDRiceDecompressionChannel_nextWord` | reconstruct one 16-bit output word |

The loop starts with capacity for 100,000 16-bit samples (200,000 bytes) and
doubles as required. Decoder status 3 terminates the stream successfully;
another decoder status becomes `PPInvalidRawData` (error value 6). No fixed
sample count or audio frame size is stored in this record; the bit count
terminates decoding.

`DDRiceDecompressionDecoder_readBit` at `DDRiceCompression.o:0x3b8` reads
each byte from bit 7 toward bit 0, proving that the compressed stream is
MSB-first within each byte.

The shipped **encoder initializer** validates the configuration byte as no
greater than `0xef`; the collection decompression path does not repeat that
check and also mechanically accepts high-nibble `0xf`. The low nibble controls
the final left shift and the full-word escape width `16 - lowNibble`; the high
nibble is the unary/small-difference cutoff. The decoder has an escape path
that reads `16 - lowNibble` literal bits. Its `nextWord` function performs two
cumulative 16-bit additions before applying the low-nibble left shift:

```text
firstDifference = uint16(firstDifference + decodedDifference)
word = uint16(word + firstDifference)
sampleBits = uint16(word << lowNibble)
```

This is concrete evidence for the symbol-named DD Rice, double-delta-style
reconstruction. No IMA-ADPCM step/index tables or calls to Speex, Opus, or
another third-party codec appear in this path.

`PPCollection_createAudioTimeline` prefers the uncompressed record if both
record pointers are present, otherwise it decodes the compressed record. This
proves that the collection protocol and Haversine support both code 80 and code
81. It does **not**, by itself, prove which one a particular ring firmware
normally emits.

#### Output structure and Kotlin boundary

The cinterop metadata gives the exact 32-byte result:

```c
struct PPResultAudioTimeline_t {
    uint32_t collectionStartIndex; // offset 0
    uint32_t sampleRateHz;         // offset 4
    size_t sampleCount;            // offset 8
    uint16_t *samples;             // offset 16
    bool isMultiPart;              // offset 24
    bool isFinalPart;              // offset 25
};
```

`analysis/toolchain_iosarm64_dump_ir.txt` shows that
`PPAudioTimeline.ios.kt` allocates a Kotlin `ShortArray(sampleCount)` and uses
one `memcpy` of `samples.size * 2` bytes from the native `uint16_t *`.
Consequently, Haversine preserves the reconstructed 16-bit bit patterns and
reinterprets them as signed Kotlin shorts; it performs no byte swap, resample,
or codec work at this copy boundary.

The decoder initializes exactly one DD Rice channel (index 0), has no channel
loop, and appends one word per decode iteration. This device implementation is
therefore a one-channel/mono reconstruction path. The sample rate is not
hardcoded: the uncompressed branch reads it at record offset `+4`, and the
compressed branch reads it at `+9`, then the Kotlin IR propagates it unchanged
to `TransferComplete.sampleRate`.

#### DWARF and source information

Every PPCommon object reports zero bytes of DWARF data via
`dwarfdump --show-section-sizes`. There are no PPCommon DWARF compile units,
types, or line tables to recover. The objects retain function/local symbol
names, relative source strings such as `DDRiceCompression.c` and
`PPCollection.c`, assertions, and Mach-O linker optimization hints.

The `HaversineSatelliteLibrary` objects do contain DWARF (for example, 18,191
bytes in the C transfer object and 20,889 bytes in its Swift wrapper), but those
are a separate implementation archive. Their source-path/type inventory is
useful for transfer tracing and is summarized below.

#### PPCommon cryptography and fingerprint inventory

A case-insensitive pass over all PPCommon symbols, printable strings, cinterop
metadata, and undefined imports found no AES, CCM, GCM, ChaCha, Poly1305,
Salsa20, CTR, CBC, XTS, HKDF, HMAC, SHA, Curve25519, X25519, P-256, ECDH,
encrypt/decrypt, cipher, nonce, secret, checksum, or CRC implementation/API.
The 21 unique undefined imports are internal PPCommon calls and ordinary libc
functions (`malloc`, `free`, `memcpy`, string/printing, assertions, and stack
guards); there is no CommonCrypto, CryptoKit, or Security-framework import.

Names containing `fingerprint` and `mixer` are present, so they were inspected
rather than counted as crypto evidence:

- Cinterop metadata defines `PPRingApplicationData_t` as exactly
  `{ uint32_t fingerprint; uint32_t timestamp; char uid[129]; }`, size 140.
- `PPRingApplicationData_serializedSize` returns 141 bytes. The serialized
  version-1 form is a four-byte version, fingerprint/timestamp, and the 129-byte
  UID; it has no key, nonce, IV, authentication tag, or secret field.
- `PPRingApplicationData_init` calls a deterministic `_fingerprint` routine on
  the UID. Its disassembly is additions, XORs, shifts, and fixed 32-bit
  constants. `fingerprintMatchesUserId` recomputes it and compares only the low
  16 bits.
- The no-user check uses low 16 bits `0xffff`; the failsafe sentinel is
  `0xdeaddead`.
- `PPFingerprintFromRawSensorData` XOR-folds input bytes into a repeating
  16-byte buffer and packs the result. It is not a cryptographic hash.
- `PPTinyBitMixer` and `PPGenerateUniqueStaticRandomBluetoothAddress` use fixed
  multiply/byte-reversal/XOR mixing. They are not encryption routines.

The main Kotlin IR further shows `programSatelliteWithUserID` taking the caller
supplied user ID, obtaining Unix time, calling `PPRingApplicationData_init`,
serializing that 141-byte value, and passing the resulting `NSData` to
`programWithApplicationData`. No random secret or key derivation appears in
this wrapper path.

This is strong negative evidence for an application secret in PPCommon and the
visible registration-data construction path. It is not a blanket proof about
unseen ring firmware or platform BLE link encryption.

### HaversineSatelliteLibrary KLIB

Regular payload files:

- `default/manifest`
- `default/linkdata/module`
- four `package_HaversineSatelliteLibrary/*.knm` files
- `default/targets/ios_arm64/native/cstubs.bc` (LLVM bitcode wrapper)
- `default/targets/ios_arm64/included/libHaversineSatelliteLibrary.a`

The static archive contains an archive symbol table and 37 ARM64 Mach-O
objects:

| Member | Size |
| --- | ---: |
| `AsyncStreamExtensions.o` | 46,160 |
| `CBCentralManagerAdaptor.o` | 422,072 |
| `CBConnectedPeripheralAdaptor.o` | 422,752 |
| `CombineExtensions.o` | 46,344 |
| `HaversineAdvertisement-5432203426e16c710574d475c9238e28.o` | 58,736 |
| `HaversineAdvertisement-a22709b85a8f5eac99cd35f28cf0164c.o` | 8,024 |
| `HaversineDiagnosticOperation.o` | 23,384 |
| `HaversineEnvironment.o` | 535,256 |
| `HaversineError.o` | 17,320 |
| `HaversineLinkController+OperationStream.o` | 44,224 |
| `HaversineLinkController.o` | 66,008 |
| `HaversineLinkControllerAdaptor.o` | 91,136 |
| `HaversineLogging.o` | 51,264 |
| `HaversineOperation.o` | 17,712 |
| `HaversineOperationStream.o` | 162,440 |
| `HaversineReadDebugInfoOperation.o` | 25,744 |
| `HaversineReadLastAudioSamplesOperation.o` | 33,392 |
| `HaversineReadRxRSSIOperation.o` | 18,400 |
| `HaversineSatellite.o` | 787,016 |
| `HaversineSatelliteId.o` | 9,848 |
| `HaversineSatelliteLibrary_vers.o` | 2,776 |
| `HaversineSatelliteManager.o` | 411,568 |
| `HaversineSatelliteState.o` | 192,936 |
| `HaversineSensorServiceOperation.o` | 17,472 |
| `HaversineSensorStreamOperation.o` | 34,584 |
| `HaversineSuotaOperation.o` | 26,680 |
| `HaversineSwiftError.o` | 46,312 |
| `HaversineSystemInputController.o` | 15,192 |
| `HaversineTransferCollectionsOperation-1b03d6b35479582ddfbbfc570532354b.o` | 25,976 |
| `HaversineTransferCollectionsOperation-a1037ba5de9e4e5ed3d03c9adecaf742.o` | 48,336 |
| `HaversineTypeExtensions.o` | 295,592 |
| `HaversineUUID.o` | 11,504 |
| `HaversineUpdateCacheOperation.o` | 24,400 |
| `ResultExtensions.o` | 12,808 |
| `TelestoController.o` | 36,104 |
| `TelestoOperation.o` | 26,360 |
| `TelestoTypes.o` | 6,288 |

The C transfer object contains source path/type information and phase strings
for reading stored indexes, collections, and advertising data. Its recovered
names include `TELESTO_COLLECTION_BASE`, `TelestoStoredCollectionIndexes`,
`currentOperationBytesRead`, and callbacks carrying `(data, size,
collectionIndex)`. This supports incremental transfer of stored collection
objects, but is not yet a complete wire-layout reconstruction.

`dwarfdump --show-sources` identifies these particularly useful physical-build
source units:

```text
Sources/Shared/HaversineTransferCollectionsOperation.c
Sources/Shared/HaversineTransferCollectionsOperation.h
Sources/Apple/Operations/HaversineTransferCollectionsOperation.swift
Sources/Shared/TelestoController.c
Sources/Shared/TelestoController.h
Sources/Apple/Operations/TelestoOperation.swift
Sources/Shared/TelestoTypes.c
Sources/Shared/TelestoTypes.h
```

The archive's undefined-symbol and linked-module string inventory contains no
CommonCrypto, CryptoKit, Security `SecKey`/`SecItem`, AES, ChaCha, HKDF, HMAC,
SHA, X25519, ECDH, encrypt/decrypt, nonce, or secret hit. This is useful
negative inventory but does not replace tracing every transfer call.

## Ancillary publication files

`haversine-iosarm64-03202f5.module` is authoritative for the physical variant's
three KLIB files and lists these external dependencies:

| Dependency | Version |
| --- | --- |
| Kotlin stdlib | 2.2.20 |
| Ktor client core / Darwin | 3.2.1 |
| kotlinx serialization JSON | 1.9.0 |
| Kermit | 2.0.6 |
| kotlinx coroutines | 1.10.2 |
| kotlinx IO core | 0.7.0 |

The 165,256-byte metadata JAR has 113 entries: 69 regular files comprising 54
KNM files, seven KLIB manifests, seven linkdata modules, and one JAR manifest.
It commonizes/duplicates metadata but has no native archive, object, or IR
bodies. The 166-byte sources JAR contains only `META-INF/MANIFEST.MF` and no
source files.

## Strongest leads and limitations

Strongest device evidence:

1. The recording is embedded in a transferred collection as either record 80
   (little-endian PCM16) or record 81 (symbol-named DD Rice compressed 16-bit
   audio).
2. The compressed record layout, bit length, sample-rate location, MSB-first
   bit order, and one-channel reconstruction loop are instruction-level facts.
3. The Kotlin wrapper makes a direct two-byte-per-sample copy into
   `ShortArray`, then concatenates multipart collections and emits
   `TransferComplete` without another decode or resample.
4. Registration application data is user ID + timestamp + deterministic
   fingerprint, not a key container, in the inspected path.

Limitations/obstacles:

- The physical artifact supports both uncompressed and compressed audio
  records. No artifact-level selector proves which record a particular ring
  firmware emits by default. A captured collection or ring firmware would
  resolve this.
- The sample rate is carried as a 32-bit record field, not hardcoded in the
  decoder. An actual record/capture is needed to establish its runtime value.
- Opaque `GSCompressedAudioDataRecord_t` and
  `GSUncompressedAudioDataRecord_t` headers were not packaged, and the sources
  JAR is empty. Their used fields were nevertheless recovered from parser and
  decoder machine code.
- PPCommon contains no DWARF. Function symbols, cinterop metadata, relocations,
  and disassembly are the available evidence.
- The POM advertises a GitHub repository, but an unauthenticated
  `git ls-remote https://github.com/coredevices/haversine-kmp.git` returns
  `Repository not found`.
- Archive-level absence of crypto APIs is strong negative evidence, not proof
  about uninspected firmware or BLE controller/link-layer security.

## Reproduction commands

```sh
LC_ALL=C openssl dgst -sha256 artifacts/haversine-iosarm64-03202f5.klib
unzip -t artifacts/haversine-iosarm64-03202f5.klib
unzip -Z -1 artifacts/haversine-iosarm64-03202f5.klib
sed -n '1,120p' extracted/iosarm64/default/manifest

ar -tv extracted/iosarm64-cinterop-PPCommon/default/targets/ios_arm64/included/libPPCommon_static.a
nm -gU extracted/iosarm64-cinterop-PPCommon/default/targets/ios_arm64/included/libPPCommon_static.a
nm -u extracted/iosarm64-cinterop-PPCommon/static_objects/PPCollection.o
strings -a -n 3 extracted/iosarm64-cinterop-PPCommon/static_objects/PPCollection.o
otool -tvV extracted/iosarm64-cinterop-PPCommon/static_objects/PPCollection.o
otool -rv extracted/iosarm64-cinterop-PPCommon/static_objects/PPCollection.o
otool -tvV extracted/iosarm64-cinterop-PPCommon/static_objects/DDRiceCompression.o
otool -tvV extracted/iosarm64-cinterop-PPCommon/static_objects/PPParsing.o
dwarfdump --show-section-sizes extracted/iosarm64-cinterop-PPCommon/static_objects/PPCollection.o

# With official Kotlin/Native 2.2.20:
klib dump-ir artifacts/haversine-iosarm64-03202f5.klib
klib dump-metadata artifacts/haversine-iosarm64-03202f5-cinterop-PPCommon.klib -print-signatures true
```

## Outstanding follow-up beyond archive inventory

- Recover a complete, independently testable DD Rice decoder from the
  disassembly and validate it against a real compressed record.
- Determine a real Index record's code (80 or 81), sample rate, configuration
  byte, compression ratio, and multipart boundaries from a capture.
- Finish the Telesto controller/link framing, ACK/retry, and integrity trace in
  the satellite archive.
- Trace the complete native `programWithApplicationData` operation to confirm
  the negative application-crypto finding through the final characteristic
  writes.
