# Haversine / Pebble Index recording protocol reverse-engineering

Artifacts examined:

- `artifacts/haversine-iosarm64.klib`
- `artifacts/haversine-iossimulatorarm64.klib`
- the four cinterop KLIBs published alongside them, containing `libPPCommon_static.a` and `libHaversineSatelliteLibrary.a`

The top-level KLIBs contain serialized Kotlin IR, not LLVM bitcode. The device and simulator top-level IR (`bodies.knb`, `strings.knt`, metadata) is identical; the target manifest and native cinterop archives differ. Kotlin/Native `2.2.20` `klib dump-ir` was used to recover the Kotlin implementation.

For the complete Telesto-specific protocol/state-machine documentation, see [`telesto-protocol.md`](telesto-protocol.md).

## 1. Executive answer

The Index collection is not an Opus, Speex, AAC, or ordinary IMA-ADPCM stream. The native PPCommon library contains a custom codec called **DDRice**. Its decoder is directly reachable from `PPCollection_createAudioTimeline`. The compressed audio record contains a small header, a bit count, a sample rate, and a bit-packed DDRice stream. The decoder uses a Rice-like variable-length code and a second-order differential predictor. The reconstructed values are 16-bit sample words.

A collection is transferred as a raw stored collection object. Haversine's Swift/C layer reads a collection from the Index's virtual collection memory and passes the complete `NSData` to the Kotlin `HaversineTransferDelegate`. The Kotlin layer passes that byte array to PPCommon, which parses the collection TLV records and decodes the audio. There is no Haversine recording encryption/decryption step between BLE/Telesto reception and PPCommon parsing.

Haversine then concatenates the decoded samples from one or more collection parts. It emits `TransferStatus.TransferComplete` with a `ShortArray` and the per-record `sampleRate`. The Kotlin code writes and reads those samples as little-endian 16-bit values. The application subsequently removes DC bias, resamples to 16,000 Hz, and stores raw mono PCM16.

The exact source sample rate is **carried in every audio record** (`uint32 sampleRateHz`), rather than hardcoded in the Haversine decoder. These two binaries do not contain a definitive single runtime value. The public firmware image inspected alongside them contains 8,000 and 16,000 Hz configuration values, and 16,000 Hz is the strongest practical inference for current voice recordings, but a captured collection or ring firmware/source is needed to label 16,000 Hz as binary-proven for every Index firmware version.

No application-level recording encryption was found. No AES, ChaCha20, Poly1305, HMAC, HKDF, SHA, X25519/ECDH, nonce/IV, authentication-tag, or key-storage path is present in the recording path. Haversine does persist cached satellite state in `NSUserDefaults`, but that state contains metadata, application data, fingerprints, and transfer indexes—not a recording key. Bluetooth bonding/link encryption remains separate and is the likely protection referred to as “encrypted connection.”

The precise physical **flash-at-rest** status on the Index remains `unknown` from these artifacts alone: ring firmware could theoretically decrypt flash internally before exposing a collection to Telesto. What is established is that Haversine receives a logical collection in the clear after the BLE stack and immediately parses it; there is no Haversine-side decrypt operation or application key. The public firmware image inspected did not reveal a crypto implementation, but it is not a symbolized firmware build and cannot prove a negative about all firmware storage paths.

Evidence labels used below: **known** means directly present in recovered IR/metadata/disassembly; **strong inference** means multiple binary paths agree but a firmware/capture confirmation is absent; **unknown** means the phone-side artifacts cannot answer it.

## 2. End-to-end data path

```text
microphone on Index
  -> ring collection storage
       -> collection container / TLV records
            -> compressed audio record (DDRice) or supported uncompressed audio record
  -> Telesto READ_MEMORY request for 0x40020000 | collectionIndex
  -> Haversine Telesto response header + data stream
  -> BLE Telesto control/data characteristics
  -> Haversine C/Swift transfer operation
  -> NSData for one complete collection
  -> Kotlin ByteArray in HaversineTransferDelegate.collectionTransferDidFinish
  -> PPCollection_createFromBinaryData
  -> PPCollection_createAudioTimeline
       -> raw uint16 copy, or DDRice decoder
  -> PPAudioTimeline(ShortArray, sampleRateHz, multipart flags)
  -> MultipartCollection buffer
  -> TransferStatus.TransferComplete(samples, sampleRate, ...)
  -> Pebble app DC-bias removal
  -> resample to 16,000 Hz
  -> little-endian raw mono PCM16
```

Known evidence:

- `work-ir.txt:972-1458`: `handleDidFinish`, collection parsing, type determination, single/multipart processing, and `emitCompleteTransfer`.
- `work-ir.txt:1325-1458`: `emitCompleteTransfer` calls `MultipartCollection.flushBuffer()` and constructs `TransferStatus.TransferComplete`.
- `work-ir.txt` in the `MultipartCollection` section around `work-ir.txt:3408-3747`: `addPart` uses `writeShortLe`; `flushBuffer` uses `readShortLe`.
- `external-mobileapp/experimental/src/commonMain/kotlin/coredevices/ring/service/RingSync.kt:71-78, 150-168, 297-301, 658-690`: the open application removes DC bias, resamples from `transferStatus.sampleRate` to 16,000 Hz, converts `ShortArray` to little-endian bytes, and stores `audio/raw`.

## 3. Codec analysis

### 3.1 Collection audio record forms

PPCommon exposes both `GSUncompressedAudioDataRecord_t` and `GSCompressedAudioDataRecord_t` pointers in `GSRawDataRecords_t_`. `PPCollection_createAudioTimeline` selects the uncompressed branch when `uncompressedAudioData` is present and otherwise selects `compressedAudioData`.

The simulator archive includes an x86_64 slice, preserved as `work-simx/PPCollection.o`, which makes the audio record accesses especially clear. Relative to the pointer immediately after the one-byte record tag:

### Uncompressed audio record

| Offset | Size | Meaning |
| -----: | ----: | ------- |
| 0 | 4 | `contentBytes`; content after this size field |
| 4 | 4 | `sampleRateHz` |
| 8 | `contentBytes - 4` | raw 16-bit sample bytes |

The code copies `contentBytes - 4` bytes, divides by two for `sampleCount`, and stores the sample rate from offset 4. This is a supported raw PCM-like storage form.

### Compressed audio record

| Offset | Size | Meaning |
| -----: | ----: | ------- |
| 0 | 4 | `contentBytes`; includes the 9-byte metadata area and compressed payload |
| 4 | 1 | DDRice header: high nibble `m`, low nibble `k` |
| 5 | 4 | unaligned little-endian `compressedBitCount` |
| 9 | 4 | unaligned little-endian `sampleRateHz` |
| 13 | `ceil(compressedBitCount / 8)` | MSB-first compressed bitstream |

`PPCollection_createAudioTimeline` checks:

```text
compressedBitCount <= contentBytes * 8 - 0x48
```

`0x48` is 72 bits, i.e. the 9 metadata bytes after the 4-byte size. It then initializes the decoder with the bitstream at record +13 and the exact bit count at record +5.

Evidence: `ppcollection-x86-disasm.txt`, `PPCollection_createAudioTimeline` around offsets `0x484-0x57e`, and the equivalent ARM64 `ppcollection-disasm.txt` around `0x3b4-0x5a8`.

### 3.2 DDRice bitstream

The codec object is `work-obj/DDRiceCompression.o`; the same implementation was also disassembled from the simulator x86_64 slice as `ddrice-x86-disasm.txt`.

`DDRiceDecompressionDecoder_readBit` reads byte `byteIndex`, selects bit `7 - bitOffset`, advances the bit position, and returns `0xff` at the supplied bit limit. Thus the compressed stream is MSB-first within each byte.

High-level decoder pseudocode recovered from `DDRiceDecompressionChannel_decodeDiff`:

```text
readDiff(header, bitReader):
    first = readBit()
    if first == EOF:
        return END
    if first == 1:
        return 0

    m = header >> 4
    k = header & 0x0f
    q = 0

    while q + 1 < m:
        bit = readBit()
        if bit == EOF:
            return END
        q += 1
        if bit == 0:
            continue

        signOrMapping = readBit()
        if signOrMapping == EOF:
            return END
        if signOrMapping == 0:
            return q
        return (65536 >> k) - q

    # Escape/raw branch after the unary threshold.
    return readBits(16 - k)
```

The exact encoder (`DDRiceCompressionChannel_encodeWord`) confirms this is not a library codec: it computes a residual, emits a one-bit zero-residual code or a variable unary/sign code followed by a `16-k` remainder. The encoder has no IMA step table/index table, no Speex/Opus call, no LPC/CELT/SILK code, and no third-party audio dependency.

After a diff is decoded, `DDRiceDecompressionChannel_nextWord` does:

```text
channel.diffAccumulator += diff
channel.wordAccumulator += channel.diffAccumulator
output = (channel.wordAccumulator << k) & 0xffff
```

That is a second-order differential reconstruction, followed by a power-of-two scale. It is fair to call the data **custom Rice-like, second-order delta/differential compressed 16-bit audio**. It should not be called ADPCM: there is no IMA/ADPCM step-size/index algorithm.

### 3.3 Audio representation

- Sample width after decode: 16 bits.
- Native decoder output type: `uint16_t *`, copied bit-for-bit into Kotlin `ShortArray`.
- Signedness at the app boundary: Kotlin `Short`; the app treats the values as signed PCM samples.
- Channels: one sample array and no channel-count field; the app stores/plays it as mono. Mono is strongly supported.
- Byte order: raw samples are little-endian on the ARM64 target; Haversine explicitly uses `writeShortLe`/`readShortLe`.
- Fixed codec frame size: none found. The codec is terminated by the record's `compressedBitCount`; a collection may be split across multiple collection objects.
- Sample rate: explicit `uint32 sampleRateHz` in each audio record. Exact current firmware value is not proved by the KLIB.

## 4. Frame/protocol structure

### 4.1 Collection container

`GSParseRecordsInRawData` (`work-obj/PPParsing.o`, offset `0`) validates a 3-byte collection header:

| Offset | Size | Meaning |
| -----: | ----: | ------- |
| 0 | 3 | collection content length |
| 3 | ... | record sequence |

Two length encodings are supported:

- If byte 0 is not `0xff`, bytes 0..2 are a big-endian 24-bit value equal to `collectionSize - 3`.
- If byte 0 is `0xff`, bytes 1..2 are a little-endian 16-bit value equal to `collectionSize - 3`.

Each record starts with a one-byte tag. Most record types have a little-endian 16-bit length after the tag; the two audio record types use a 32-bit `contentBytes` field. PPCommon validates the declared lengths and collection bounds.

The collection also has a separate packed `GSCollectionMultiPartInfo_t` record:

| Offset | Size | Meaning |
| -----: | ----: | ------- |
| 0 | 2 | record size |
| 2 | 4 | `startIndex` |
| 6 | 1 | `isMultiPart` |
| 7 | 1 | `isFinalPart` |

### 4.2 Telesto memory request

`TelestoRequest` is packed and is exposed by the HSL cinterop metadata:

| Offset | Size | Meaning |
| -----: | ----: | ------- |
| 0 | 1 | operation type; `3` is `TELESTO_READ_MEMORY` |
| 1 | 4 | virtual address, little-endian |
| 5 | 4 | memory offset, little-endian |
| 9 | 4 | requested length, little-endian |

The transfer operation uses:

- stored indexes: address `0x40030005`, length 4;
- each collection: address `0x40020000 | collectionIndex`, offset 0, length 0 (`TELESTO_LENGTH_INFER_FROM_PREFIX`);
- advertising data: address `0x4003000e`, length 10.

`TelestoResponse` is 12 bytes:

| Offset | Size | Meaning |
| -----: | ----: | ------- |
| 0 | 4 | `error` |
| 4 | 4 | `info` |
| 8 | 4 | returned data `length` |

The Telesto controller waits for the complete 12-byte response, then accepts the specified data length. It does not expose an audio packet sequence number, checksum, CRC, or hash.

### 4.3 Transfer phases and chunking

`HaversineTransferCollectionsOperation-1b03d6b35479582ddfbbfc570532354b.o` has embedded source strings and DWARF names:

- `TRANSFER_OPERATION_PHASE_READ_STORED_INDEXES`
- `TRANSFER_OPERATION_PHASE_READ_COLLECTIONS`
- `TRANSFER_OPERATION_PHASE_READ_ADVERTISING_DATA`
- `TRANSFER_OPERATION_PHASE_FINISHED`

The collection phase accumulates incoming data into an operation buffer, up to `0xa0000` (655,360) bytes in the C transfer object, and calls the delegate only after the complete collection operation finishes. The callback signature is exposed in `work-hsl-meta.txt`:

```text
collectionTransferDidFinish(data: NSData,
                            collectionIndex: UInt16,
                            satelliteId: NSUUID)
```

The Kotlin bridge converts that `NSData` to a `ByteArray`. This is therefore incremental at the Telesto/BLE transport layer but delivered to Kotlin as one complete stored collection object. The audio codec itself has no independently exposed BLE packet/frame boundaries.

Haversine's Kotlin multipart logic then treats multiple *collections* as parts of one audio recording. It requires contiguous collection indexes, detects a sequence mismatch, and flushes the current buffer when a new multipart start index arrives.

### 4.4 Integrity and reliability mechanisms

- **Length validation: known.** The collection parser checks the outer length, each record length, and bounds. The compressed audio parser checks `compressedBitCount` against the available compressed bytes.
- **Operation status: known.** Telesto responses contain `error` and `info`; Haversine maps operation/controller errors to `HaversineError` and invokes the transfer-failure callback.
- **Collection indexes: known.** Stored collection ranges and collection indexes provide ordering. Multipart assembly checks contiguous indexes and detects mismatches.
- **Audio packet sequence numbers: not found.** No sequence field is present in the audio record or `PPAudioTimeline`; codec reconstruction is driven by bit position and predictor state.
- **CRC/checksum/hash: not found.** No CRC/checksum field or verification routine is in the collection parser, DDRice decoder, or Telesto response path.
- **Acknowledgement: partially known.** Telesto is request/response and the CoreBluetooth adaptor tracks write-with-response/notification confirmation. Those are transport/operation confirmations, not an audio-record authentication tag.
- **Retransmission/FEC: not found in the recording path.** HSL has connection backoff/error handling, but no recording FEC or explicit per-audio-chunk retransmission algorithm was recovered.

## 5. Cryptography analysis

| Layer | Status | Evidence |
| --- | --- | --- |
| BLE link encryption/bonding | yes/OS-level | CoreBluetooth transport and the app's bonding flow; outside Haversine recording codec |
| Haversine application-layer recording encryption | no | no cipher calls, key/nonce/tag structures, or decrypt step in collection path |
| Physical flash-at-rest encryption on Index | unknown | Haversine sees logical collection bytes after ring/BLE processing; these artifacts contain no ring-side flash implementation or key |
| Haversine-side storage-at-rest encryption | no | Haversine parses collection bytes directly; no local recording-key path |

The top-level manifest lists networking/TLS and platform dependencies, but those are not connected to recording transfer. The static archives contain some ordinary Swift linker references (including framework metadata), but no CommonCrypto/CryptoKit/Security key/crypto API call is reachable from the recording path. The only compression/integrity-like algorithm used for audio is DDRice and the only custom hash-like routine is the registration fingerprint. The absence of a Haversine decrypt path is strong evidence against the proposed persistent shared-secret design, but it cannot by itself rule out transparent encryption/decryption implemented entirely inside ring firmware.

## 6. Key-management analysis

### Is there a per-ring shared secret?

No evidence of one. No key is generated, received from the ring, derived by ECDH, stored in Keychain, or passed to the audio decoder.

### What happens during registration/programming?

The open application confirms that the pairing behavior is firmware-version dependent (`external-mobileapp/experimental/src/commonMain/kotlin/coredevices/ring/service/RingPairing.kt` and `external-mobileapp/libindex/src/commonMain/kotlin/coredevices/libindex/device/IndexPairing.kt`):

- Android asks the OS to create a BLE bond.
- iOS's `createBond` helper connects and writes one byte `0x00` with response to `DAAD3D52-237C-90A7-B54B-8854A134D801` (the Telesto data characteristic), retrying up to three times.
- Firmware older than `3.62.0` requires the app to program application data containing the user's Firebase UID before recordings transfer. Firmware `>= 3.62.0` skips that programming step.
- After a successful Android pairing, the app erases existing collections as a policy decision; that erase is not part of audio decoding and should not be reproduced blindly by an independent client.

`work-ir.txt` around the `KMPHaversineSatelliteManager.programSatelliteWithUserID` implementation shows:

1. `PPRingUser_init(userId)`.
2. POSIX `time()` for a timestamp.
3. `PPRingApplicationData_init(user, timestamp)`.
4. `PPRingApplicationData_serializedSize` and `PPRingApplicationData_serialize`.
5. `HaversineSatellite.programWithApplicationData(applicationData, ...)`.

`work-pp-meta.txt` defines the payload as:

```c
struct PPRingApplicationData_t {
    uint32_t fingerprint;
    uint32_t timestamp;
    struct { char uid[129]; } user;
};
```

Its serialized size is `0x8d` (141) bytes. `PPRingApplicationData.o` contains the fingerprint mixer and plain serialization/deserialization; it does not contain encryption.

### What is persisted?

The HSL `HaversineUserDefaultsCache` persists a `HaversineSatelliteState.CacheableState` keyed by the prefix `HaversineSatelliteState_` plus the satellite UUID. The state contains platform versions, sensor configuration version, serial number, application data, application-data size, advertised fingerprint, and last transfer end index. It does not contain a symmetric key or secret. The Kotlin app's `CollectionIndexStorage` separately stores the last successful collection index.

### Does recording decode depend on registration data?

No. `PPCollection_createAudioTimeline` takes only the collection object. Its arguments are collection bytes and output storage; no user ID, fingerprint, application data, key, or satellite identity is passed. `applicationDataUserId` only deserializes/exposes the ring's UID for pairing/permission decisions.

Removing pairing state or clearing Haversine's cache can remove the remembered ring identity and transfer index, and the visible app may deliberately erase recordings when pairing. It does not remove a Haversine decode key because no such key exists in the code path.

## 7. Relevant symbols/functions

### Kotlin IR

- `coredevices.haversine.HaversineTransferDelegate.collectionTransferDidFinish`
- `coredevices.haversine.HaversineTransferDelegate.handleDidFinish`
- `coredevices.haversine.HaversineTransferDelegate.processSinglePartAudio`
- `coredevices.haversine.HaversineTransferDelegate.processMultiPartAudio`
- `coredevices.haversine.HaversineTransferDelegate.emitCompleteTransfer`
- `coredevices.haversine.MultipartCollection.addPart`
- `coredevices.haversine.MultipartCollection.flushBuffer`
- `coredevices.haversine.TransferStatus.TransferComplete.<init>`
- `coredevices.haversine.ppcommon.PPCollection.<init>`
- `coredevices.haversine.ppcommon.PPAudioTimeline.<init>`
- `coredevices.haversine.KMPHaversineSatelliteManager.programSatelliteWithUserID`
- `coredevices.haversine.KMPHaversineSatelliteState.applicationDataUserId`

### PPCommon C/native

- `_GSParseRecordsInRawData` (`PPParsing.o`, offset `0`)
- `_PPCollection_createFromBinaryData` (`PPCollection.o`, offset `0x0c`)
- `_PPCollection_createAudioTimeline` (`PPCollection.o`, offset `0x3b4`)
- `_PPCollection_freeAudioTimeline` (`PPCollection.o`, offset `0x5ac`)
- `_DDRiceDecompressionDecoder_init`
- `_DDRiceDecompressionDecoder_readBit`
- `_DDRiceDecompressionDecoder_readBits`
- `_DDRiceDecompressionChannel_init`
- `_DDRiceDecompressionChannel_decodeDiff`
- `_DDRiceDecompressionChannel_nextWord`
- `_DDRiceCompressionChannel_encodeWord`
- `_PPRingApplicationData_init`
- `_PPRingApplicationData_serialize`
- `_PPRingApplicationData_deserialize`
- `_PPRingApplicationData_fingerprintMatchesUserId`

### HaversineSatelliteLibrary C/Swift

- `_HaversineTransferCollectionsOperation_init`
- `__TransferOperation_startNextChild`
- `__TransferOperation_handleReceivedDataFromChild`
- `__TransferOperation_handleCompletionFromChild`
- `_TelestoController_receiveCtrlBytes`
- `_TelestoController_receiveDataBytes`
- `HaversineSatellite.readCollectionData(at:)`
- `HaversineSatellite.transferSwings(to:)`
- `HaversineSatellite.readLastAudioSamples()`
- `HaversineSatellite.readLastAudioSamplesAndRunDiagnostics(measureTxRSSI:)`
- `HaversineUserDefaultsCache.fetchCachedState(for:)`
- `HaversineUserDefaultsCache.cacheState(_:for:)`

## 8. Evidence summary

| Conclusion | Concrete evidence |
| --- | --- |
| Complete collection is passed into Kotlin before decoding | `work-ir.txt`, `handleDidFinish`: `PPCollection(index, data)` |
| Audio decode is PPCommon native code | `work-obj/PPCollection.o`, `_PPCollection_createAudioTimeline` |
| Custom codec is DDRice | `work-obj/DDRiceCompression.o` symbols and strings; direct calls from `PPCollection.o` |
| Custom differential reconstruction | `ddrice-x86-disasm.txt`, `_DDRiceDecompressionChannel_nextWord` double accumulator |
| 16-bit output | `PPResultAudioTimeline_t.samples` is `uint16_t *`; Kotlin `ShortArray` copy |
| Little-endian app boundary | Kotlin IR `writeShortLe` / `readShortLe`; app `toByteArrayLe` |
| Collection transfer is read-memory, not a complete opaque encrypted blob | HSL transfer operation constants and `TelestoRequest` metadata |
| Multipart is collection-level | `GSCollectionMultiPartInfo_t`; `MultipartCollection` contiguous-index checks |
| No Haversine recording cipher | no cipher imports/symbols/calls and no key parameter in PPCollection/DDRice path |
| Registration data is not a secret | `PPRingApplicationData_t` layout and `pring-disasm.txt` plain serializer/fingerprint mixer |
| Persistent Haversine state is non-secret metadata | `HaversineUserDefaultsCache` methods and `HaversineSatelliteState.CacheableState` fields |

## 9. Remaining unknowns

1. A captured collection is needed to verify the exact production audio tag value and confirm whether a particular firmware build chooses compressed or uncompressed audio.
2. The KLIB carries the per-record sample-rate field but not a definitive current runtime value. A capture, firmware source, or decoded firmware configuration would settle 8/16/32 kHz for each firmware family.
3. The generic record-tag-to-struct mapping is present in the PPCommon parser's jump table but the public cinterop metadata does not expose all audio forward-declared struct names/fields. The audio record layouts above are recovered; non-audio TLV tag numbers are not fully documented here.
4. Telesto/CentralBluetooth characteristic delivery can split data arbitrarily. Exact negotiated ATT notification payload sizes and lower transport behavior should be established with a GATT capture; they are intentionally not treated as audio frames here.
5. No explicit application-level retransmission/FEC algorithm was found. Link reconnection/backoff exists in HSL, but the exact retry policy under every transport error requires a live capture or full HSL state-machine tracing.
6. Safe collection deletion semantics should be confirmed with a live ring before implementing an independent client. The HSL API exposes erase/program operations, but a client should not guess erase addresses or issue them without a tested acknowledgement sequence.

## 10. Independent-client implications

Already understood:

1. Discover service `607B5C9B-3700-4E94-F44A-2DF900BCB0C3`.
2. Discover its three characteristics. `DAAD3D52-237C-90A7-B54B-8854A134D801` is Telesto Data, `C0EF558A-2058-FABF-A140-8D5ACDE50B39` is Telesto Ctrl, and `1D1F4039-23F5-33B2-C24E-704351F20585` is System Input. The role mapping is recovered from the Apple adaptor's send paths; live sequencing should still be validated.
3. Establish the BLE bond/authorization. On iOS, reproduce the `DAAD...` write-with-response of `00`; on Android use the OS bond flow. Do not invent an application key exchange. For firmware `<3.62.0`, programming the plaintext application-data UID may also be required.
4. Subscribe to Telesto control/data notifications and implement the 13-byte packed Telesto request plus 12-byte response header.
5. Read stored indexes from `0x40030005`, select collection indexes, and read each collection from `0x40020000 | index` with inferred length.
6. Preserve each returned collection byte-for-byte. Validate the 3-byte collection prefix and record lengths.
7. Decode compressed audio using the DDRice record header and bitstream, or copy the uncompressed record's little-endian `uint16` payload.
8. Use `GSCollectionMultiPartInfo_t` to join multipart recordings by contiguous `startIndex`/collection indexes and honor `isFinalPart`.
9. Obtain the actual sample rate from the audio record, produce signed mono PCM16, and resample only if desired by the application.

Still requiring live validation:

- exact live notification ordering under every firmware/connection condition and confirmation behavior;
- BLE bond behavior on iOS and Android outside the open app's helpers;
- treatment of rollover and the stored-index range;
- retries after a dropped Telesto response;
- safe deletion/erase operation after successful preservation;
- firmware-specific compressed record/tag variants.

### Effect on the official Pebble app

A client restricted to `READ_MEMORY` collection operations should not modify ring recordings or advance the official app's local transfer cursor. The HSL transfer operation contains reads; collection deletion is a separate explicit `eraseCollections()` operation. The official app stores its last successful collection index locally (`PrefsCollectionIndexStorage`) and has no indication that another app downloaded a collection. Consequently, the official app may attempt to download the same collections again and could create duplicate/local reprocessing on its next sync, but read-only access should not delete the ring data.

Do not connect concurrently during an official transfer if avoidable: the Index may permit only one active central, and taking the connection can make the official transfer appear failed or incomplete. Its recovery path is designed to retry, but this has not been tested with an independent client. Do not call erase, program, cancel, or firmware-update operations in a recording downloader.
