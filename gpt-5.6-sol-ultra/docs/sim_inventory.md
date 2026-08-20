# iOS Simulator ARM64 Acquisition, Protocol, and Audio Inventory

Last updated: 2026-08-20 (Asia/Singapore)

This report records the complete Apple Silicon iOS Simulator ARM64
investigation assigned from `brief.md`. It covers artifact acquisition,
archive contents, the collection-to-`TransferComplete` path, audio encoding,
Telesto framing, BLE adaptation, integrity, cryptography, and persistent
per-ring state.

## Executive answer

The transmitted recording is a **complete Haversine collection object**
containing one of two audio records:

- record `0x50` (`80`): uncompressed 16-bit PCM, with a 32-bit little-endian
  sample rate followed by native/little-endian 16-bit sample words;
- record `0x51` (`81`): a custom bit-packed, second-order delta codec
  implemented by `DDRiceCompression`, with an explicit bit count and explicit
  32-bit little-endian sample rate.

The compressed form is not Opus, Speex, IMA ADPCM, or another imported
third-party audio codec. Its decoder entropy-codes second differences and
reconstructs samples with two modulo-16-bit integrations. The implementation
calls it `DDRice`, although its concrete unary/signed-small-value encoding plus
raw escape should not be replaced by a generic “Rice codec” label.

Haversine does not decrypt the collection before parsing or audio decoding.
There is no key, nonce, authentication tag, crypto API, or persistent secret in
the recording path. The registration/application-data facility stores a
plaintext user identifier, timestamp, and noncryptographic fingerprint, not a
shared secret. Normal BLE security may still protect the radio link, but that
is outside this application-layer conclusion.

The ring's firmware-internal at-rest representation is not directly visible in
these client binaries. The collection returned by the ring is already directly
parseable as record `0x50` or `0x51`, so the **Haversine payload on the wire** is
proven. It is plausible that the same collection blob is the stored object
because it is read by collection index from a storage-like Telesto virtual
address, but the client alone cannot prove that firmware does not transform or
encrypt it internally before serving the read.

## Completion status

- [x] Download and verify the exact simulator KLIB.
- [x] Resolve, verify, and extract both cinterop dependencies.
- [x] Split the universal native archives into ARM64 and x86_64 slices.
- [x] Extract and inventory every object, symbol table, string table, DWARF
  record, build-version record, and relevant disassembly.
- [x] Recover and dump the serialized Kotlin/Native IR.
- [x] Trace `TransferComplete.samples` back through native collection parsing.
- [x] Reconstruct the collection envelope and audio-record layouts.
- [x] Reconstruct the custom compressed-audio decoder.
- [x] Trace Telesto request/response/data handling and the CoreBluetooth
  adapter.
- [x] Audit checksums, acknowledgements, retries, and other integrity features.
- [x] Audit the recording path and persistent state for application crypto.
- [x] Test the registration/shared-secret hypothesis.

The remaining unknowns at the end of this report require firmware or a captured
collection rather than more client-binary unpacking.

## Acquisition and verification

Main artifact URL:

`https://repo1.maven.org/maven2/io/github/coredevices/haversine/haversine-iossimulatorarm64/03202f5/haversine-iossimulatorarm64-03202f5.klib`

Downloaded main artifact:

`artifacts/haversine-iossimulatorarm64-03202f5.klib`

| Property | Value |
| --- | --- |
| Size | 135,476 bytes |
| Container | ZIP |
| SHA-256 | `9ba0534f81762d59c2e73b24f053933836fe10cbdf7497d578f8e950f53e46a7` |
| Published SHA-1 | `2b4b20e3b1d57b21a423445ba63458edaa0b51b0` |
| ZIP validation | `unzip -t`: no errors |

The SHA-256 exactly matches Maven's published checksum. The POM and Gradle
module metadata were also retained. The selected
`iosSimulatorArm64ApiElements-published` variant names two cinterop artifacts:

| Artifact | Size | Verified SHA-256 |
| --- | ---: | --- |
| `haversine-iossimulatorarm64-03202f5-cinterop-haversineSatelliteLibrary.klib` | 2,393,854 | `98cf6bad80999aa22bc58597b43bf5400ce7e0a486481199b8a757f0f54555bf` |
| `haversine-iossimulatorarm64-03202f5-cinterop-PPCommon.klib` | 65,671 | `d6ada452614b9c178206f3ca81ed9c70499dc021b70fd21af15dd11442aa117b` |

Both cinterop checksums match the Gradle module metadata and both archives pass
`unzip -t`.

## Archive and native-code inventory

### Main KLIB

The main KLIB has 50 ZIP entries, 40 regular files, and 370,701 uncompressed
bytes. Its regular files are:

| Kind | Count |
| --- | ---: |
| Kotlin/Native link metadata (`*.knm`) | 29 |
| IR tables (`*.knt`) | 3 |
| IR declarations/debug tables (`*.knd`) | 3 |
| IR file tables (`*.knf`) | 2 |
| IR bodies (`*.knb`) | 1 |
| Manifest/module files | 2 |

The main KLIB contains serialized Kotlin IR and metadata but no native object,
static library, or resource payload. Its manifest identifies:

- ABI version `2.2.0`;
- compiler version `2.2.20`;
- metadata version `1.4.1`;
- target `ios_simulator_arm64`;
- unique name `io.github.coredevices.haversine:haversine`;
- cinterop dependencies `haversine-cinterop-haversineSatelliteLibrary` and
  `haversine-cinterop-PPCommon`.

The complete IR dump is
`analysis/toolchain_iossimulatorarm64_dump_ir.txt` (8,689 lines).

### Cinterop KLIBs

`haversineSatelliteLibrary` contains:

- four link-metadata files;
- `native/cstubs.bc`, 66,256 bytes;
- `included/libHaversineSatelliteLibrary.a`, 9,005,008 bytes, universal
  x86_64/ARM64 iOS Simulator archive.

`PPCommon` contains:

- six link-metadata files;
- `native/cstubs.bc`, 40,752 bytes;
- `included/libPPCommon_static.a`, 75,512 bytes, universal x86_64/ARM64 iOS
  Simulator archive.

The ARM64 satellite archive contains **37 Mach-O objects plus `__.SYMDEF`**.
The ARM64 PPCommon archive contains **8 Mach-O objects plus
`__.SYMDEF SORTED`**. All 37 satellite objects carry DWARF; the eight PPCommon
objects do not. LC_BUILD_VERSION identifies iOS Simulator objects, minimum iOS
15.0 for the satellite archive and 14.0 for PPCommon.

The matching x86_64 slices have the same member names and counts and were used
to cross-check difficult instructions. Thin slices and all extracted objects
are under:

- `extracted/iossimulatorarm64-native-slices/`
- `extracted/iossimulatorarm64-native-objects/`

High-value members include:

- `HaversineTransferCollectionsOperation-*.o`;
- `CBConnectedPeripheralAdaptor.o`;
- `HaversineLinkController.o`;
- `TelestoController.o`, `TelestoOperation.o`, `TelestoTypes.o`;
- `PPParsing.o`, `PPCollection.o`;
- `DDRiceCompression.o`;
- `PPRingApplicationData.o`.

## Reconstructed data path

The layers must be kept separate:

```text
CoreBluetooth notification fragments
    -> Telesto response/data accumulation
    -> one complete collection read
    -> collection envelope and record parser
    -> record 0x50 direct PCM copy
       or record 0x51 DDRice decompression
    -> uint16_t samples copied bit-for-bit to Kotlin ShortArray
    -> decoded multipart PCM concatenation, if needed
    -> TransferStatus.TransferComplete(samples, sampleRate, ...)
```

The Kotlin/native call chain is:

```text
IOSHaversineTransferDelegate.collectionTransferDidFinishWith(
    NSData, collectionIndex, satelliteId
)
  -> NSData to ByteArray
  -> HaversineTransferDelegate.collectionTransferDidFinish
  -> handleDidFinish
  -> PPCollection(collectionIndex, data)
  -> PPCollection_createFromBinaryData
  -> PPCollectionSimple_createAudioTimeline /
     PPCollection_createAudioTimeline
  -> PPAudioTimeline(PPResultAudioTimeline_t)
  -> memcpy(sampleCount * 2) into ShortArray
  -> processSinglePartAudio or MultipartCollection.addPart
  -> emitCompleteTransfer
  -> TransferStatus.TransferComplete
```

`PPResultAudioTimeline_t` is a 32-byte ARM64 structure:

| Offset | Field | Type |
| ---: | --- | --- |
| 0 | `collectionStartIndex` | `uint32_t` |
| 4 | `sampleRateHz` | `uint32_t` |
| 8 | `sampleCount` | `size_t` |
| 16 | `samples` | `uint16_t *` |
| 24 | `isMultiPart` | `bool` |
| 25 | `isFinalPart` | `bool` |

The Kotlin wrapper copies `sampleCount * 2` bytes. It does not perform a
post-decoder codec conversion: the native result already consists of 16-bit
sample words.

## Collection framing

`PPCollection_createFromBinaryData` copies the complete byte buffer and calls
`GSParseRecordsInRawData`. The parser supports these outer envelope forms:

| Condition/form | Header interpretation | First record |
| --- | --- | ---: |
| At least 4 bytes and byte 3 is zero | bytes 0..3 are a little-endian total length and must equal the complete buffer length | 4 |
| First byte is `0xff` | bytes 1..2 are a little-endian payload length and must equal `bufferLength - 3` | 3 |
| Otherwise | bytes 0..2 are a 24-bit big-endian payload length and must equal `bufferLength - 3` | 3 |

Normal records use:

```text
u8     recordCode
u16le  payloadLength
u8     payload[payloadLength]
```

Audio records `0x50` and `0x51` are the exception:

```text
u8     recordCode
u32le  payloadLength
u8     payload[payloadLength]
```

Relevant record codes recovered from the parser metadata and switches are:

| Decimal | Hex | Meaning |
| ---: | ---: | --- |
| 80 | `0x50` | uncompressed audio |
| 81 | `0x51` | compressed audio |
| 82 | `0x52` | multipart audio information |
| 83 | `0x53` | button sequence |
| 84 | `0x54` | lifetime count |
| 255 | `0xff` | records-transfer envelope/sentinel form |

If both uncompressed and compressed audio records are present, the
`PPCollection_createAudioTimeline` control flow prefers record `0x50`.

## Audio record `0x50`: uncompressed PCM

Layout from the beginning of the record:

| Offset | Size | Meaning |
| ---: | ---: | --- |
| 0 | 1 | record code `0x50` |
| 1 | 4 | payload length, little-endian |
| 5 | 4 | sample rate in Hz, `uint32_t` little-endian |
| 9 | `payloadLength - 4` | 16-bit sample words |

The decoder computes:

```text
sampleCount = (payloadLength - 4) / 2
```

It allocates `sampleCount * 2` bytes and directly `memcpy`s the bytes at offset
9. There is no predictor, byte swap, resampling, gain stage, or decryption.
On the supported little-endian iOS targets those bytes become signed Kotlin
`Short` values bit-for-bit, establishing PCM16 little-endian interpretation for
the transmitted raw form.

## Audio record `0x51`: custom DDRice compression

Layout from the beginning of the record:

| Offset | Size | Meaning |
| ---: | ---: | --- |
| 0 | 1 | record code `0x51` |
| 1 | 4 | payload length, little-endian |
| 5 | 1 | compression configuration byte |
| 6 | 4 | exact compressed bit count, little-endian |
| 10 | 4 | sample rate in Hz, `uint32_t` little-endian |
| 14 | remaining bytes | compressed bitstream |

`PPCollection_createAudioTimeline` (rather than the generic TLV parser)
enforces:

```text
compressedBitCount <= (payloadLength - 9) * 8
```

It initializes one `DDRiceDecompressionChannel`, decodes until the bit reader
returns its end-of-stream status, and grows an initial 100,000-sample output
allocation when necessary. There is no encoded sample count or fixed audio
frame count.

### Decoder reconstruction

The configuration byte has two independently used nibbles:

- low nibble: output left shift/quantization shift `s`;
- high nibble: bound for the unary/small-difference representation.

The bit reader consumes bits most-significant-bit first. At a high level,
`decodeDiff` does the following:

1. A leading `1` encodes difference `0`.
2. A leading `0` enters a bounded unary run for small magnitudes.
3. A unary terminator is followed by a sign bit for the small signed value.
4. Reaching the configured unary bound without a terminator triggers a raw
   escape of `16 - s` bits.
5. The result is sign-extended in the effective `(16 - s)`-bit domain.

For each decoded difference `diff`, `nextWord` performs:

```text
firstDelta = uint16(firstDelta + diff)
sampleBase = uint16(sampleBase + firstDelta)
sample     = uint16(sampleBase << s)
```

Both integrator states are initialized to zero. Arithmetic is deliberately
modulo 16 bits. The result is stored as `uint16_t`, then copied bit-for-bit to
Kotlin `ShortArray`, where the same bits are interpreted as signed PCM16.

This proves a custom **second-order delta plus bit-level entropy coding**
scheme. The `DDRiceCompression` symbol/source name justifies the DDRice label;
the recovered implementation is the stronger evidence. There are:

- no Opus, CELT, SILK, Speex, IMA, or generic ADPCM decoder imports;
- no LPC synthesis or codec frame structure;
- no standard ADPCM step/index tables;
- no external codec call from `PPCollection.o`.

Because `s` may be nonzero, discarded low bits may represent quantization.
Calling every possible configuration mathematically lossless would therefore
go beyond the binary evidence. With `s == 0`, the double-delta transform itself
is reversible modulo 16 bits.

## Sample format and multipart reconstruction

What the simulator binary proves:

| Property | Result |
| --- | --- |
| Decoder output width | 16 bits per sample |
| App-facing signedness | Kotlin signed `Short` |
| Raw-form byte order | little-endian/native on iOS ARM64 |
| Compressed bit order | most-significant bit first |
| Channel count | one decoder channel; no channel-count field; strongly mono |
| Sample rate | explicit `uint32_t` little-endian field in each audio record |
| Audio frame size | none; raw form is a continuous sample array, compressed form is one exact-length bitstream |

The binary does **not** hardcode a nominal 8, 16, 24, 32, 44.1, or 48 kHz rate
in this decoder path. Haversine passes the record's `sampleRateHz` through to
`TransferComplete`. Consequently, the exact rate used by a real Index
recording requires a collection capture; it cannot be responsibly inferred
from this binary alone.

Record `0x52` carries:

- `collectionStartIndex`;
- `isMultiPart`;
- `isFinalPart`.

For a multipart logical recording, Haversine:

1. decodes each complete collection to 16-bit PCM;
2. requires a consistent sample rate and expected collection progression;
3. writes each decoded sample using `writeShortLe`;
4. on the final part, reads the accumulated values using `readShortLe`;
5. emits one `TransferComplete`.

Thus multipart assembly concatenates **decoded PCM16**, not compressed
bitstreams. Timestamp/duration progression is derived from decoded sample
count and sample rate.

## Collection transfer and chunking

`HaversineTransferCollectionsOperation` executes these reads:

| Purpose | Telesto address | Length |
| --- | ---: | ---: |
| stored collection indexes | `0x40030005` | 4 |
| collection `index` | `0x40020000 \| uint16(index)` | 0 (whole virtual object) |
| current advertisement data | `0x4003000e` | 10 |

The four-byte stored-index response is two little-endian `uint16_t` values
(`start`, `end`). The operation handles sequential/wrapped collection indexes,
remembers the last transferred end index, and provides a 655,360-byte
collection buffer (`0xA0000`).

This modular behavior is direct in the native operation. The exact Kotlin
bridge later represents endpoints with an ordinary `IntRange` and applies a
non-modular resume selection, so fully integrated behavior across
`0xffff -> 0x0000` still requires a synthetic bridge test or device capture.

CoreBluetooth/Telesto may deliver a read in many notification fragments.
Those fragments are accumulated against the response's declared length.
`collectionTransferDidFinishWith` receives the complete collection `NSData`;
only then does PPCommon parse and decode it.

Therefore:

- the BLE/Telesto transfer is physically incremental;
- an individual collection is an application-level complete stored object;
- there is no independently decoded audio frame in each BLE packet;
- a long logical recording can span several complete collections through
  record `0x52`.

## Telesto application transport

The packed Telesto request is exactly 13 bytes:

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 1 | operation type |
| 1 | 4 | address, little-endian |
| 5 | 4 | offset, little-endian |
| 9 | 4 | length, little-endian |

Operation byte values are:

| Value | Operation |
| ---: | --- |
| 0 | no operation |
| 1 | erase |
| 2 | program |
| 3 | read |
| 4 | cancel |
| 5 | erase then program |

The packed response is exactly 12 bytes:

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 4 | error, little-endian |
| 4 | 4 | info, little-endian |
| 8 | 4 | data length, little-endian |

The controller permits one outstanding operation. It accumulates exactly 12
control bytes, rejects an unexpected/oversized control response, then accepts
data only for a read (or cancellation of a read). Read notifications are
accumulated until at least `response.length` bytes have arrived; excess input
is capped and warned about. A nonzero Telesto error becomes a Haversine error.

A cancel request uses operation type `4` with the original request's
address/offset/length. There is no sequence identifier in requests or
responses and no retry loop for a failed collection read.

`TelestoLengthPrefixedData` is a separate payload helper:

```text
u32le totalSizeIncludingThisPrefix
u8    bytes[totalSize - 4]
```

It is used when constructing certain higher-level program/application-data
payloads. It is **not** an extra wrapper around every BLE notification,
Telesto request, or collection read.

## CoreBluetooth adaptation

The relevant characteristics are:

- Telesto control: `C0EF558A-2058-FABF-A140-8D5ACDE50B39`;
- Telesto data: `DAAD3D52-237C-90A7-B54B-8854A134D801`.

`CBConnectedPeripheralAdaptor` slices outgoing data at
`maximumWriteValueLength(for:)`. It normally uses CoreBluetooth
`.withoutResponse`. After three no-response packets, it uses one
`.withResponse` packet when the characteristic supports that write property,
then resets the cadence. The 13-byte control request will normally fit in one
write; long outgoing program data exercises the chunking path.

The adaptor tracks `.withResponse` writes awaiting CoreBluetooth confirmation.
A failed write becomes a transport error. A successful final confirmation
signals only that the local outbox was sent. Incoming characteristic
notifications are passed unchanged to `receiveTelestoCtrlBytes` or
`receiveTelestoDataBytes`.

This is BLE/GATT pacing and error reporting, not a Haversine per-audio-frame
acknowledgement scheme. The code contains no application retransmission of a
failed chunk. Normal BLE Link Layer acknowledgements, CRC, encryption, and
radio retransmission are deliberately outside the brief's application-layer
scope.

## Integrity mechanisms

Mechanisms present in the recovered application protocol:

- Telesto's response declares the expected total data length;
- the collection envelope length must match the complete collection;
- each record declares a payload length;
- compressed audio declares an exact bit count bounded by available bytes;
- the collection operation tracks collection indexes and the stored range;
- multipart assembly checks expected progression and consistent sample rate;
- Telesto reports an operation-level error and successful completion.

Mechanisms not present in the collection/audio/Telesto path:

- no CRC field;
- no checksum field;
- no cryptographic hash;
- no MAC or authentication tag;
- no FEC;
- no per-chunk or per-frame sequence number;
- no application-level per-chunk acknowledgement;
- no application-level retransmission loop.

The operation-level response and CoreBluetooth write confirmations should not
be misreported as audio-packet acknowledgements.

## Cryptography and the shared-secret hypothesis

### Recording path

`PPCollection_createFromBinaryData` takes only `(bytes, length, error/result)`.
`PPCollection_createAudioTimeline` consumes the parsed record directly.
`DDRiceDecompressionDecoder_init` receives only the bitstream, exact bit count,
and channel/configuration state. No function in that chain accepts or loads:

- a key;
- nonce or IV;
- authentication tag;
- device secret;
- pairing token;
- cached application data.

Symbol, string, import, and call-path audits found no AES, AES-CCM/GCM, ChaCha,
Poly1305, Salsa, CTR/CBC/XTS, HKDF, HMAC, SHA-256, Curve25519/X25519, P-256,
ECDH, `CCCrypt`, `SecKey`, or Keychain operation reached by recording transfer.
The archive carries a generic Security framework linker option, but no relevant
undefined Security API and no call from the audio/collection path. A linker
option is not evidence of recording encryption.

Conclusion: **the collection bytes delivered to Haversine are not encrypted at
the Haversine application layer.**

### Registration/application data

The logical `PPRingApplicationData_t` structure is:

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 4 | `fingerprint` |
| 4 | 4 | Unix-style timestamp |
| 8 | 129 | user UID character array |

Version-1 serialization is 141 plaintext bytes:

```text
u32le version = 1
u32le fingerprint
u32le timestamp
char  uid[129]
```

The fingerprint is generated by the local `PPTinyBitMixer`/fingerprint routine
from identity data. It is used to match advertised identity/application state.
It is not a secret, cipher key, key derivation function, or message
authentication code. `PPRingApplicationData` imports ordinary string/memory
functions, not cryptography.

The Kotlin IR exposes:

- `programSatelliteWithUserID`;
- `PPRingApplicationData_init`;
- `PPRingApplicationData_serialize`;
- generic `program(applicationData: Data)`;
- erase/clear application-data operations.

The programming flow serializes the user identity structure, length-prefixes
it for programming, writes it, and updates cached state. It performs no
challenge/response, public/private key exchange, received-secret processing,
or key derivation.

### Persistent state

`HaversineSatelliteState.CacheableState` contains:

- satellite name;
- platform versions;
- serial number;
- sensor configuration version;
- application data (`Foundation.Data`);
- advertised fingerprint (`UInt32`);
- optional last transfer end index (`UInt16`).

The iOS cache uses `NSUserDefaults` data under the prefix:

`HaversineSatelliteState_`

The suffix is the ring's Foundation UUID. The implementation uses
`dataForKey:`, `setObject:forKey:`, and removal calls. It does not use Keychain.
The cached `applicationData` is the plaintext identity/application blob above,
and recording decoding never references it.

Answers to the explicit shared-secret questions:

| Question | Evidence-supported answer |
| --- | --- |
| Secret generated during registration? | No application secret in Haversine's flow. |
| Secret received from ring? | No receive/deserialize path for one. |
| Public/private key exchange? | None. |
| Persistent application key stored? | None. |
| Key location/indexing? | Not applicable; ordinary state is indexed by ring UUID in `NSUserDefaults`. |
| Does audio decoding reference a key? | No. |
| Would clearing app state prevent decoding old transferred bytes? | Not at the Haversine decoder layer; decoding is self-contained in the collection. |
| Is Bluetooth bonding the only possible persistent cryptographic relationship? | It is the only remaining plausible layer, but CoreBluetooth hides controller/bond details and this binary does not prove whether a bond is established. |

This strongly disproves the proposed persistent Haversine shared-secret
hypothesis. It does not make a claim about opaque BLE controller bond storage
or undisclosed firmware-only at-rest behavior.

## Confidence boundaries and remaining unknowns

High confidence, directly proven by IR, ABI metadata, and ARM64/x86_64 native
control flow:

- exact record `0x50` and `0x51` layouts;
- 16-bit output samples;
- explicit per-record sample rate;
- one-channel DDRice decoding;
- second-order delta reconstruction;
- whole-collection parsing before decode;
- decoded-PCM multipart concatenation;
- Telesto 13-byte request and 12-byte response;
- absence of application decryption or persistent key in the client path.

Strongly inferred from direct implementation:

- recordings are mono, because exactly one decode channel exists and no
  channel-count/interleave field exists;
- raw record `0x50` is PCM16LE, because its bytes are directly copied to the
  app's PCM16 `ShortArray` on little-endian targets.

Not determinable from these client binaries alone:

- the numeric sample rate used by a real Index recording;
- which audio form (`0x50` or `0x51`) current firmware normally chooses;
- the configuration byte observed in a real compressed recording;
- whether firmware stores the identical collection bytes in flash or
  materializes them when the virtual collection address is read;
- whether firmware independently encrypts flash at rest and decrypts before
  responding;
- CoreBluetooth's actual bond/link-encryption state for a particular ring.

A single captured `collectionTransferDidFinishWith` buffer would settle the
first three practical unknowns immediately and can be decoded using the
layouts above.

## Durable evidence index

Primary evidence retained in the workspace:

- `analysis/toolchain_iossimulatorarm64_dump_ir.txt`
- `analysis/iossimulatorarm64-transfer-wrapper-ir-excerpt.txt`
- `analysis/iossimulatorarm64-multipart-ir-excerpt.txt`
- `analysis/iossimulatorarm64-ppcommon-wrapper-ir-excerpt.txt`
- `analysis/iossimulatorarm64-ppcommon-cinterop-metadata.txt`
- `analysis/iossimulatorarm64-satellite-cinterop-metadata.txt`
- `analysis/iossimulatorarm64-ppparsing-arm64-disassembly.txt`
- `analysis/iossimulatorarm64-ppcollection-arm64-disassembly.txt`
- `analysis/iossimulatorarm64-ddrice-arm64-disassembly.txt`
- corresponding x86_64 PPParsing/PPCollection/DDRice disassemblies
- `analysis/iossimulatorarm64-transfer-c-arm64-disassembly.txt`
- `analysis/iossimulatorarm64-read-last-audio-arm64-disassembly.txt`
- `analysis/iossimulatorarm64-TelestoTypes-arm64-{dwarf,disassembly,nm}.txt`
- `analysis/iossimulatorarm64-TelestoController-arm64-{dwarf,disassembly,nm}.txt`
- `analysis/iossimulatorarm64-TelestoOperation-arm64-{dwarf,disassembly,nm}.txt`
- `analysis/iossimulatorarm64-HaversineLinkController-arm64-{dwarf,disassembly,nm}.txt`
- `analysis/iossimulatorarm64-persistence-target-strings.txt`
- `analysis/iossimulatorarm64-{satellite,ppcommon}-arm64-{ar-members,nm,strings}.txt`
- `analysis/iossimulatorarm64-native-{sizes,sha256,build-versions,debug-presence}.txt`
- `analysis/ghidra_decompiled/libppcommon_audio.c`
- `analysis/ghidra_decompiled/libppcommon_helpers.c`
- `analysis/ghidra_decompiled/libhaversine_protocol.c`
- `analysis/ghidra_decompiled/libhaversine_protocol_helpers.c`
- `analysis/ghidra_decompiled/telesto_all_internal.c`

Representative reproducibility commands:

```sh
shasum -a 256 artifacts/haversine-iossimulatorarm64-03202f5*.klib
unzip -t artifacts/haversine-iossimulatorarm64-03202f5.klib
zipinfo artifacts/haversine-iossimulatorarm64-03202f5.klib
lipo -info extracted/iossimulatorarm64-cinterop-*/default/targets/*/included/*.a
ar -t extracted/iossimulatorarm64-native-slices/*.a
nm -a extracted/iossimulatorarm64-native-slices/*.a
llvm-objdump --macho --disassemble extracted/iossimulatorarm64-native-objects/*/*.o
dwarfdump extracted/iossimulatorarm64-native-objects/satellite-arm64/*.o
```
