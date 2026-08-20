# Haversine / Pebble Index 01 — Recording Format & Protocol Report

**Subject**: the two Kotlin/Native klibs `io.github.coredevices.haversine:haversine-{iosarm64,iossimulatorarm64}:03202f5`, plus the equivalent Android AAR `haversine-android-03202f5.aar` (same version), which contains the identical C protocol libraries as native `.so` files.

**Confidence legend** — **KNOWN** = directly evidenced in a binary/code artifact. **INFERENCE** = multiple consistent pieces of evidence, no single direct proof. **UNKNOWN** = not established.

---

## 1. Executive answer

**What does the Index store?**
The ring stores each voice recording as a **"collection"**: a self-describing stream of records in its flash. The audio inside a collection is **16-bit, single-channel, little-endian PCM** at the ring's native rate (**16 kHz** — KNOWN from the official app; the rate is also carried per-collection in the collection itself). The collection can carry the audio as **raw 16-bit PCM** (record type `0x50`) or as **DD-Rice compressed** 16-bit PCM (record types `0x51`/`0x52`) — a differential-Rice entropy coder derived from Speex's `dd_rice.c` (KNOWN: the decoder's exact imported functions are in the library). Other records in the same blob carry the button-press sequence, IMU/sensor data, calibrations, device ID, platform versions, the ring's hardware serial number, and the application-data store.

**What does it transmit / what does Haversine receive?**
Over GATT, the ring's flash is addressed as *virtual memory* ("Telesto" protocol): the app issues `READ_MEMORY` commands against virtual addresses (collections live at `0x40020000 + index`, application data at `0x40000000`, stored-collection-index list at `0x40020005`). The ring responds by writing the collection bytes to the **Telesto data channel** characteristic, where each GATT notification payload is a **4-byte little-endian total-length prefix followed by raw payload bytes**. The application layer performs **no encryption** of this data — the collection bytes are exactly the bytes stored on the ring (plus the 4-byte framing). **No AES/CCM/GCM/ChaCha/Poly1305/SHA/curve or key-derivation code exists in either of the two protocol libraries** (KNOWN: full symbol + .rodata scan).

**What does Haversine output to the app?**
The Kotlin layer calls `PPCollection_createFromBinaryData(bytes)` then `PPCollectionSimple_createAudioTimeline(collection)`, which parse the record stream, **decode the DD-Rice (or pass through the raw) 16-bit samples**, and return `PPResultAudioTimeline_t { sampleRateHz, sampleCount, isMultiPart, isFinalPart, collectionStartIndex, samples: uint16_t* }`. Haversine wraps this as `TransferStatus.TransferComplete { samples: ShortArray, sampleRate: UInt, collectionIndex, buttonSequence, isContiguous, ... }`. Long recordings arrive as **multipart collections** (parts ≤ 100,000 samples each, same `collectionIndex`, `isFinalPart` on the last) which Haversine concatenates.

**Is recording data encrypted at rest on the Index?**
**No evidence of application-level encryption** (UNKNOWN at the firmware level — the ring's flash controller may do its own ECC/management, but nothing in the transferred bytes or the Haversine path indicates at-rest audio encryption). The transferred collection is byte-identical to the stored collection.

**Is it application-layer encrypted in transit?**
**No** (KNOWN — no cipher in the path; see §5). The only "crypto" is the BLE link layer itself.

**Is there a registration-derived shared secret?**
**No** (KNOWN, strong). Registration ("pairing") writes a **141-byte application-data blob** to the ring's `APPLICATION_DATA_STORE` virtual address. That blob contains a **version byte (1)**, a **16-bit unkeyed hash of the user ID**, and a **128-bit "fingerprint" that is a simple XOR-fold of the ring's per-device raw sensor data** (a device identity tag, not a key). Matching functions are `fingerprintMatchesFailsafe` (unconditionally true — a fresh ring pairs with anyone), `fingerprintMatchesNoUser` (appData == -1), and `fingerprintMatchesUserId` (computes the 16-bit hash of the user string with a fixed, exposed algorithm and compares). No key is generated, exchanged, stored, or referenced by the audio decode path. **Clear statement: there is no application-level shared secret; Bluetooth bonding is the only persistent cryptographic relationship.**

---

## 2. End-to-end data path

```
[ring microphone]
  → 16-bit mono PCM @ 16 kHz (native rate; per-collection rate is recorded in the collection)
  → (for compressed collections) DD-Rice: 13-byte decoder header + Rice bitstream of the sample diffs
  → stored as one record inside a "collection" = stream of length-prefixed records (flash)
  → [over GATT, Telesto protocol]
      data channel:  [u32 LE total-length incl. 4-byte prefix][raw collection bytes]   (20-byte GATT writes; 500ms app-registration on connect)
      control channel: 12-byte status messages (op ack/progress)
      commands: 10-byte {u8 hasData, u32 address, u32 offset, u32 length}
  → Haversine (KMP) reassembles the length-prefixed stream into the full collection byte array
  → PPCollection_createFromBinaryData(bytes)            [libppcommon.so — GolfShot-derived "GS" record parser]
  → PPCollectionSimple_createAudioTimeline(collection)
      raw path:     type 0x50 payload → uint16 samples directly
      compressed:   type 0x51/0x52 → DDRiceDecompressionDecoder_init(13-byte header)
                    → DDRiceDecompressionChannel_init / decodeDiff / nextWord → uint16 samples
  → PPAudioTimeline { sampleRate, samples: ShortArray, isMultiPart, isFinalPart, collectionStartIndex, sampleCount }
  → HaversineTransferDelegate.handleDidFinish → MultipartCollection (concat parts; caps: 100k samples/part, 5 MB total)
  → TransferStatus.TransferComplete { samples, sampleRate, collectionIndex, buttonSequence, isContiguous }
  → Pebble app: DC-bias removal → resample(sampleRate → 16000) → PCM16 LE bytes → M4A (AAC, 1 ch)
```

No encryption layer exists anywhere in this chain (see §5).

---

## 3. Codec analysis

### 3.1 The two audio record types

| Record type (byte) | Meaning | Payload layout (after the record header) |
|--:|--------|------------------------------------------|
| `0x50` (80) | **UNCOMPRESSED 16-bit audio** | `[u32 len][u32 ?][16-bit LE PCM samples]` |
| `0x51` (81) | **COMPRESSED 16-bit audio** (DD-Rice) | `[u32 total][u32 bitstream-len][u32 hdr-len=13][13-byte decoder header][Rice bitstream]` |
| `0x52` (82) | compressed variant 2 | same shape (decoder dispatch is identical) |
| `4` | **audio header** | `[+0][+1][u32 sampleRateHz @+2][pad][isMultiPart u8 @+6][isFinalPart u8 @+7]` |

(Decoded from `GSParseRecordsInRawData` — the jump-table dispatch and per-type handlers; identical logic in x86_64 and arm64-v8a.)

### 3.2 The DD-Rice coder (the "compressed" variant)

The compressed path is **not** Speex proper, Opus, ADPCM, or any frame-based perceptual codec. It is **differential Rice coding of 16-bit samples** — the exact algorithm of Xiph Speex's `dd_rice.c` (the low-level Rice coder Speex ships for its legacy/standalone use). Proof: the library imports exactly these four functions (`.rela.plt`, `libppcommon.so`):

```
DDRiceDecompressionDecoder_init      (PLT 0x273e0)
DDRiceDecompressionChannel_init      (PLT 0x273f0)
DDRiceDecompressionChannel_decodeDiff(PLT 0x27400)
DDRiceDecompressionChannel_nextWord  (PLT 0x27410)
```

Decoder structure (from `PPCollectionSimple_createAudioTimeline`, x86_64 @ `0x24fa0`, 638 B):

```c
// pseudocode, compressed path
decoder = DDRiceDecompressionDecoder_init(
              hdr[0],            // u8  (Rice "k" / bit-allocation param 1)
              hdr[1],           // u8  (param 2)
              u16le(hdr+2),     // u16 (channel/word config)
              /* +9 more header bytes consumed into the decoder state */ );
ch = DDRiceDecompressionChannel_init(decoder, &chstate);
out = malloc(200000);           // 100,000 samples, realloc-doubled as needed
for (i = 0; i < count && i < 100000; i++) {
    d = DDRiceDecompressionChannel_decodeDiff(ch, &bitstream);  // signed 16-bit diff
    out[i] = out[i-1] + d;                              // differential reconstruction
    DDRiceDecompressionChannel_nextWord(ch, &bitstream);
}
```

- **Sample width**: 16-bit signed (reconstructed `uint16_t`/`int16_t` samples; Kotlin side is `ShortArray`).
- **Channels**: 1 (mono) — the decoded `PPResultAudioTimeline_t` has no channel field and the app's M4A encoder configures `mChannelsPerFrame = 1`.
- **Sample rate**: **16 kHz** (KNOWN: `RingSync.TARGET_SAMPLE_RATE = 16000`, `AudioRecorder.ios.kt: sampleRate = 16000`, `M4aEncoder`/`ButterworthHighPass` all 16k, and the official app resamples the *per-collection* `sampleRate` to 16000 — i.e., 16k is the native/default rate). The rate is **carried in the collection** (audio-header record, `u32`), not hardcoded — so an independent client should read it from the record.
- **Frame size / part size**: the decoder caps at **100,000 samples per part** (`0x186a0`); initial output buffer 200,000 bytes; realloc-doubled. Multipart collections chain parts of the same `collectionIndex` until `isFinalPart`. At 16 kHz, 100k samples = 6.25 s per part.
- **Error codes** (from the decoder): 2 = null output, 3 = no-audio flag, 6 = decode failure, 7 = no audio record, 19 (0x13) = malloc/realloc failure.

**Why DD-Rice and not Speex frames?** Speex's full codec (MDCT + QMF + band-split) is heavy; a bare Rice coder on the *sample differences* is a CPU-cheap, near-lossless-for-voice compressor suitable for a microcontroller, and it matches the observed ~2× payload reduction and the 13-byte header (Rice parameter table). A separate Core Devices module, `coredevices/kotlin-speex` (a real Speex **16 kHz wideband frame** decoder, u8-length-prefixed frames, 320-sample frames, 12.8 kbps), exists but is **not** a dependency of the haversine klib and is never referenced by it — it is a different, unused-in-this-path component.

---

## 4. Frame / protocol structure

There are **three distinct layers**; do not collapse them.

### 4.1 GATT layer (BLE, ignored per brief except UUIDs)

| Item | Value |
|------|-------|
| Service (128-bit) | `607B5C9B-3700-4E94-F44A-2DF900BCB0C3` (16-bit alias `0x0000FCC9`) |
| `telestoDataChannel` (data up) | `DAAD3D52-237C-90A7-B54B-8854A134D801` (the "pairing" characteristic) |
| `telestoCtrlChannel` (control) | `C0EF558A-2058-FABF-A140-8D5ACDE50B39` |
| `systemInputChannel` | `1D1F4039-23F5-33B2-C24E-704351F20585` |

App writes **20-byte** GATT writes (no MTU negotiation); subscribes to notifications on all three (CCCD `0x2902`); a **500 ms "app registration"** window exists on connect (the observed single `0x00` write to the system-input/registration path).

### 4.2 Telesto transport layer (over the GATT characteristics)

**Data channel** (ring → app), per notification payload:

| Offset | Size | Meaning |
|--:|--:|--------|
| 0 | 4 | **total length of this payload including these 4 bytes** (little-endian `u32`) |
| 4 | N | raw payload bytes (a slice of the collection byte stream) |

Built by `TelestoLengthPrefixedData_create` (satellite lib, @ `0xfd30`).

**Control channel** (ring → app): fixed **12-byte** messages (buffered at `ctrl+0x98`, counter at `ctrl+0x88`; processed when a full 12 bytes have arrived → `TelestoController_receiveCtrlBytes` @ `0xb310`). These carry operation progress/ack for the operation state machine. *(Exact per-field layout of the 12 bytes: UNKNOWN — only size + processing confirmed.)*

**Command payload** (app → ring), 10 bytes, built by `Java_..._TelestoOperation_init` (@ `0x9c00`) from `TelestoRequest{type,address,offset,length}`:

| Offset | Size | Meaning |
|--:|--:|--------|
| 0 | 1 | `hasData` (1 = a write/program data buffer follows) |
| 1 | 4 | virtual `address` (LE) |
| 5 | 4 | `offset` (LE) |
| 9 | 4 | `length` (LE) |

Virtual memory map (ring flash exposed over BLE):

| Address | Meaning |
|--:|--------|
| `0x40000000` | APPLICATION_DATA_STORE (141-byte blob, §6) |
| `0x40020000` | COLLECTION_BASE (first collection) |
| `0x40020005` | STORED_COLLECTION_INDEXES |
| `0x40020006` | PLATFORM_VERSIONS |

### 4.3 Collection layer (the recording object — the "collection")

A collection is a **stream of records**. Each record:

| Offset | Size | Meaning |
|--:|--:|--------|
| 0 | 3 | **record length** (incl. this header). Normally **24-bit little-endian** (`b0<<16|b1<<8|b2`). Special variants: if `b0==0xFF` → 16-bit LE length at `[1..2]`; if `b3==0` → 16-bit LE length. |
| 3 | 1 | **record type** (byte) — see table below |
| 4 | 2 | **payload length** (16-bit LE) |
| 6 | … | payload |

Record types (from the dispatch jump table in `GSParseRecordsInRawData`; a "GS"/GolfShot-derived record set — the Index 01 is a golf wearable and reuses that data protocol):

| Type | Meaning |
|--:|--------|
| `4` | **audio header**: `u32 sampleRateHz @+2`, `isMultiPart u8 @+6`, `isFinalPart u8 @+7` (16-byte record) |
| `0x50` (80) | **uncompressed 16-bit PCM audio** |
| `0x51` / `0x52` (81/82) | **DD-Rice compressed 16-bit audio** |
| others | button-press sequence, device ID, UTC time, detector data, IMU data, multi-accel, magnetometer, VSR, impact timestamp, sensor calibrations, all-serialized-calibrations, sensor configs, application-data store, user data, platform versions, target-line aim, swing setup, club settings, latest/cropped stationary data, stationary-data version, sensor temperatures, swing-time correction, hardware serial number, lifetime collection count, ST-FIFO (compressed) |

The parsed container is a **4,440-byte** (`0x1158`) `GSRawDataRecords_t` struct: typed record pointers at fixed offsets (0xf8…0x120, …), a **copy of the raw collection bytes** at `+0x130` (length at `+0x138`), and a **has-audio/valid flag at byte 0** (set to 1 only when a valid audio record is present).

---

## 5. Cryptography analysis

| Layer | Encrypted? | Evidence |
|-------|-----------|----------|
| **BLE link (CoreBluetooth / ring BT stack)** | yes (link-layer, by the OS) — *not counted per brief* | Standard BLE; the app also uses the 500 ms registration write. Not application crypto. |
| **Haversine / application layer in transit** | **NO** | See below. |
| **At rest on the ring (audio)** | **no application-level evidence** | The transferred collection is byte-identical to the stored one (the parser keeps a verbatim copy at `+0x130` and the audio decoder runs directly on it). No decrypt step exists in the path. |

**Search performed** (both `libhaversinesatellitelibrary.so` and `libppcommon.so`, all architectures, full symbol table + `.rodata` + string scan): **no** AES, AES-CCM, AES-GCM, ChaCha20, Poly1305, Salsa20, CTR/CBC/XTS, HKDF, HMAC, SHA-256, Curve25519/X25519, P-256/ECDH, key-derivation, nonce/IV-generation, or authentication-tag code. The only "crypto-adjacent" primitives are:

- **`PPFingerprintFromRawSensorData`** — a **128-bit XOR-fold** of the device's raw sensor bytes (`fingerprint[i mod 16] ^= raw[i]`); a *device identity tag*, not a key. (x86_64 @ `0x249a0`, arm64 @ `0x246c4`.)
- **`PPRingApplicationData_fingerprintMatchesUserId`** — a **fixed-algorithm 16-bit hash** of the user-ID string (4-lane 32-bit mixer with constants `0xC761C23C, 0xFDC54670, 0x7ED55D16, 0xE9F8DC1D, 0x165667B1`, then XOR-fold `((x>>16)^x^y) ^ 0x4F09`). This is *attribution* (which user the ring belongs to), not confidentiality; the algorithm and constants are fully exposed in the binary, so it is not a secret.

**Conclusion:** there is **no application-layer encryption** of recordings in transit or at rest. The only integrity/attribution is the 141-byte application-data blob (§6). No checksum/CRC is applied to the collection by Haversine (the 3-byte length header and the 4-byte Telesto length prefix are the only framing integrity; the BLE link provides transport reliability).

---

## 6. Key-management analysis

- **Per-ring shared secret?** **No.** Nothing is generated, exchanged, or stored as a key.
- **Registration/pairing flow** (the "visible" iOS write is the whole of it, plus a C-side cache update):
  1. Connect; find service `0xFCC9`; write one byte `0x00` (the app-registration write, within the 500 ms window); disconnect.
  2. Haversine then (a) reads the ring's **application data store** and **platform versions**, (b) if the ring is in **failsafe** (no user bound, `appData == -1` / `fingerprintMatchesFailsafe == true`) it is open to pairing, and (c) on first-use **programs** the ring by writing a **141-byte** `PPRingApplicationData` blob to `APPLICATION_DATA_STORE` (`0x40000000`) via a `PROGRAM_MEMORY` operation.
- **The 141-byte blob** (`PPRingApplicationData_serializedSize` == `0x8d`; layout decoded from `serialize`/`deserialize`):

  | Offset | Size | Meaning |
  |--:|--:|--------|
  | 0 | 1 | **version = 1** (deserializer rejects anything else, err 7) |
  | 1 | 3 | padding/zero |
  | 4 | 8 | field containing the **16-bit user-ID hash** (LE) + padding |
  | 12 | 129 | **null-terminated user-ID string** + padding (length checked with `__strlen_chk`, ≤ 128) |

  `deserialize` requires `len == 141` exactly (else err 3).
- **How the ring is indexed**: by the **128-bit sensor-data fingerprint** (the XOR-fold of the device's raw sensor data — a per-ring hardware-derived identity) plus the **hardware serial number** (read from the collection via `GSGetHardwareSerialNumber` / `deserializeFromCollectionData`). This is how a phone recognizes *its* ring among others and how the advertisement's `cacheableStateFingerprint` (64-bit, built from a 4-byte LE value + mapped flag bits in the manufacturer data) is used for change-detection/caching.
- **Does recording decoding reference a key?** **No.** `PPCollectionSimple_createAudioTimeline` takes only the collection pointer; there is no key parameter anywhere in the decode path.
- **Does resetting pairing invalidate old recordings?** **No.** Because there is no key, a fresh/unpaired (failsafe) ring still decodes its stored recordings; pairing only changes *attribution* (which user is recorded in the app-data blob).
- **Where is any persistent state stored?** The ring's own `APPLICATION_DATA_STORE` (flash). On the app side, Haversine keeps a `lastSuccessfulCollectionIndex` (persistence delegated to the app) and a per-UUID advertisement cache — no secrets.

**Clear statement:** *There is no application-level shared secret. Bluetooth bonding is the only persistent cryptographic relationship. Pairing is an attribution/binding operation, not a key exchange.*

---

## 7. Relevant symbols / functions

### The chain to `TransferStatus.TransferComplete(samples, sampleRate, …)`

```
GATT notification (telestoDataChannel)
  → Java  HaversineLinkController.receiveTelestoDataBytes (AAR)
  → C     TelestoController_receiveDataBytes   (libhaversinesatellitelibrary.so @ 0xb3a0)
           [reconstruct the 4-byte-length-prefixed stream → full collection bytes]
  → C     HaversineTransferCollectionsOperation (op state machine @ 0xe890)
           callback collectionTransferDidFinish(byte[] data, int index)
  → KMP   HaversineTransferDelegate.handleDidFinish(TransferEvent.DidFinish)   [Kotlin, common]
           5 MB cap, DataDecodeException / IrrecoverableDataDetected handling
  → KMP   PPCollection.createAudioTimeline()
  → cinterop  PPCollectionSimple_createAudioTimeline(PPCollection_s*)
           [libppcommon.so]
  → C     PPCollection_createFromBinaryData (x86_64 @ 0x24b60, arm64 @ 0x24828)
           = calloc(0x1158) + GSParseRecordsInRawData + raw-copy@+0x130
  → C     GSParseRecordsInRawData (x86_64 @ 0x23850, arm64 @ 0x2345c)
           [3-byte length header → record type dispatch → typed record pointers]
  → C     audio decoder (inside createAudioTimeline @ 0x24fa0):
           DDRiceDecompressionDecoder_init / DDRiceDecompressionChannel_init
           DDRiceDecompressionChannel_decodeDiff / _nextWord
  → KMP   PPAudioTimeline { sampleRate, samples: ShortArray, isMultiPart, isFinalPart,
                             collectionStartIndex, sampleCount }
  → KMP   MultipartCollection.combineWith (concat parts; 100k-sample cap)
  → KMP   TransferStatus.TransferComplete { samples, sampleRate, collectionIndex,
                                             buttonSequence, isContiguous }
```

### Other key symbols
- `PPResultAudioTimeline_t { sampleRateHz:u32, sampleCount:u64, isMultiPart:u8, isFinalPart:u8, collectionStartIndex:u32, samples:u16* }`
- `GSRawDataRecords_t` (4,440-byte container; `+0x130` raw copy; byte 0 valid-flag)
- `TelestoLengthPrefixedData_create` @ `0xfd30`; `TelestoController_receive{Data,Ctrl}Bytes` @ `0xb3a0`/`0xb310`; `TelestoOperation_init` @ `0xc460`; `HaversineLinkController_commitOperations` @ `0xc110`
- `HaversineTransferCollectionsOperation_init` @ `0xe890`; `ProgramApplicationDataOperation` (writes the 141-byte blob)
- `HaversineAudioServiceOperation_init` (96-byte enter-audio-service op)
- `HaversineAdvertisementData_parseManufacturedData` @ `0xcfd0` (64-bit cacheable-state fingerprint)
- `PPRingApplicationData_{init,serialize,serializedSize,deserialize,deserializeFromCollectionData,fingerprintMatches{UserId,NoUser,Failsafe},hasUser}`
- `PPFingerprintFromRawSensorData`; `PPGetApplicationDataFromCollectionData`; `GSGetHardwareSerialNumber`
- KMP public API: `KMPHaversineSatellite.requestTransferCollection(index, timeout)`, `requestTransfersFromCollection(start,end,timeout)`, `updateSatelliteCache`

---

## 8. Evidence

| Claim | Evidence |
|-------|----------|
| klibs are K2-IR, no native code | `iosarm64/default/ir/*.knf/knb/knd/knt` + `manifest` (abi 2.2.0, compiler 2.2.20); `klib dump-ir` succeeded; no `.a`/bitcode present. IR dumps identical for both targets (`ir_dump_iosarm64.txt` == `ir_dump_iossim.txt`, 8,689 lines). |
| Same C protocol on Android | `haversine-android-03202f5.aar` → `jni/{arm64-v8a,armeabi-v7a,x86,x86_64}/{libhaversinesatellitelibrary.so, libppcommon.so}` + `classes.jar` (130 decompiled Java files). |
| GATT UUIDs / 20-byte writes / 500 ms registration | decompiled `com.wtlp.haversinesatellitelibrary.transport.HaversineUUID`, `LinkTransport` (`maxPacketSize = 20`, `timeLeftForAppRegistration() = 500ms`, `sendDelayedDisconnectInput`), `CentralManager` (manufacturer-data = 1 entry; service filter). |
| Telesto virtual memory + op types/addresses | decompiled `TelestoOperationType`, `TelestoVirtualAddress`, `TransferCollectionsOperation`, `TelestoInputParameters`; C `HaversineLinkController_commitOperations` @ `0xc110`, `TelestoLengthPrefixedData_create` @ `0xfd30` (4-byte LE prefix), `TelestoController_receiveCtrlBytes` (12-byte buffer @ `ctrl+0x98`). |
| Collection record format (3-byte len, 24-bit LE / 0xFF / b3==0; type dispatch; 4,440-byte container; raw copy @ +0x130) | disasm of `GSParseRecordsInRawData` (x86_64 @ `0x23850`; arm64 @ `0x2345c` — identical logic: `subs x8,x2,#3; b.ge`, `ldrb w9,[x1]; cmp x9,#0xff`, `x9<<16 | x10<<8 | x10`, `strb 1,[x0]` valid-flag, `str x0,[x20,#0x130]`). |
| Audio record types 0x50 raw / 0x51/0x52 compressed / type 4 header (u32 rate @+2, multipart @+6, final @+7) | `GSParseRecordsInRawData` jump table + per-type handlers; `PPCollectionSimple_createAudioTimeline` @ `0x24fa0`. |
| **DD-Rice is the compressed codec** | imported symbols `DDRiceDecompression{Decoder_init,Channel_init,Channel_decodeDiff,Channel_nextWord}` in `libppcommon.so` `.rela.plt`; 13-byte decoder header in the compressed record; differential 16-bit reconstruction loop; 100k-sample cap (`0x186a0`), 200,000-byte initial buffer. |
| Not Speex/Opus/ADPCM | No Speex frame decoder (no MDCT/QMF/speex_bits), no Opus/CELT/SILK, no ADPCM predictor/step tables in either library. `kotlin-speex` (a real 16k wideband Speex frame codec) is **not** a dependency (klib `manifest` `depends=` list; zero references in decompiled classes or IR). |
| 16 kHz mono | official app `coredevices/mobileapp`: `RingSync.TARGET_SAMPLE_RATE=16000`, `Resampler(sampleRate,16000)`, `AudioRecorder.ios.kt: sampleRate=16000`, `M4aEncoder.mChannelsPerFrame=1`, Butterworth high-pass at 16k; rate also carried per-collection (type-4 record). |
| No application-layer crypto (in transit or at rest) | full symbol + `.rodata` + string scan of both `.so` (all arches): no AES/CCM/GCM/ChaCha/Poly1305/Salsa/CTR/CBC/XTS/HKDF/HMAC/SHA256/Curve25519/X25519/P-256/ECDH/nonce/IV/key-derivation. The transferred collection is decoded directly (no decrypt step). |
| 141-byte app-data blob, version=1, 16-bit user hash, 128-bit XOR-fingerprint | `PPRingApplicationData_serializedSize` = `0x8d` (141); `serialize` (version byte `1`, `__strlen_chk` on the string field); `deserialize` (requires len==141 else err 3); `fingerprintMatchesFailsafe` = `return 1`; `fingerprintMatchesNoUser` = `(appData==-1)`; `fingerprintMatchesUserId` (16-bit hash, constant `0x4F09`); `PPFingerprintFromRawSensorData` = XOR-fold mod 16. |
| `TransferComplete` fields | KMP IR: `TransferStatus.TransferComplete{samples:ShortArray, sampleRate:UInt, collectionIndex, buttonSequence, isContiguous}`; `HaversineTransferDelegate.handleDidFinish` (5 MB cap, `IrrecoverableDataDetected`, `MultipartCollection.combineWith`). |

---

## 9. Remaining unknowns

| Item | Status | What would resolve it |
|------|--------|-----------------------|
| **12-byte Telesto control-message field layout** | size + processing known; per-field meaning not | captured GATT traffic, or the ring firmware's control-message writer |
| **DD-Rice 13-byte header semantics beyond the first 4 bytes** (exact Rice `k` / bit-allocation table) | first 4 bytes decoded (u8,u8,u16); the remaining 9 bytes feed the decoder state | the ring firmware's matching *encoder*, or a captured compressed audio record to pin the table |
| **Ring-side recording pipeline** (mic ADC rate, whether the ring downsamples from 48k, when DD-Rice compression is applied — at record time or at write) | 16k inferred from app defaults + per-collection rate | ring firmware (Sifli/`pblprog-sifli`, `SiFli-SDK` forks) |
| **Exact per-record payload layouts** for the non-audio GS records (IMU, calibrations, stationary data, etc.) | type + rough shape known | a captured collection, or the shared PPCommon/firmware source |
| **Collection at-rest ECC/flash-management** | not in the Haversine path; may exist in the ring's flash controller | ring firmware |
| **`haversine-cinterop-PPCommon` / `-haversineSatelliteLibrary` klibs** (would contain the exact C headers and settle every struct offset) | not on Maven Central (link-time only); not recovered | publishing/upload of those cinterop klibs, or the Haversine source repo |
| **Unstripped / debug `.so`** (full symbol names for the static C helpers) | `haversine-android-debug-03202f5.jar` is empty (554 B); the `.so` in the release AAR is only partially stripped | a debug AAR with unstripped libs |

---

## 10. Independent-client implications

To build a **fully independent iOS client** (no Haversine):

| Step | Status | Notes / what's still needed |
|------|--------|------------------------------|
| 1. **Discover** an Index | **Solved** | Scan for service `607B5C9B-…-BCB0C3` (or `0xFCC9`); read the **manufacturer data** (1 entry) → 6/8-byte value → 64-bit `cacheableStateFingerprint` (4-byte LE + mapped flag bits) for change-detection. |
| 2. **Connect** | **Solved** | Standard GATT; subscribe to notifications on all three characteristics (CCCD `0x2902`); use **20-byte** writes. |
| 3. **Authenticate / pair** | **Mostly solved** | Write `0x00` (app registration) within ~500 ms of connect. To *bind a user*, write the **141-byte** app-data blob (`version=1`, 16-bit user-hash, null-terminated user string) to `APPLICATION_DATA_STORE` (`0x40000000`) via `PROGRAM_MEMORY`. **Still needed:** the exact 12-byte control-message semantics to drive the program/read handshake to completion (op ack/progress), and confirmation of the `hasData`/offset/length fields for a `PROGRAM` write. |
| 4. **Enumerate recordings** | **Solved** | Read `STORED_COLLECTION_INDEXES` (`0x40020005`) → list of collection indexes; read the advertisement's collection count for a quick path. |
| 5. **Download one** | **Mostly solved** | Issue `READ_MEMORY` at `COLLECTION_BASE (0x40020000) + index * <collection stride>` (with the 10-byte command) and reassemble the 4-byte-length-prefixed data-channel notifications into the full collection byte array. **Still needed:** the collection *stride* (bytes per index — the index→address multiplier) and the exact 12-byte control handshake. |
| 6. **Decode to PCM** | **Solved** | Parse the record stream (3-byte length header; type `0x50` raw PCM16, or `0x51`/`0x52` DD-Rice with the 13-byte header + `decodeDiff`/`nextWord` Rice decode; type `4` for the sample rate). Reconstruct by summing the Rice differences into 16-bit samples; concatenate multipart parts (≤100k samples, `isFinalPart` last). **Still needed:** the exact DD-Rice parameter table (9 header bytes) to implement the decoder from scratch — or just call Speex's `dd_rice` decoder. |
| 7. **Acknowledge / delete safely** | **Partially solved** | The ring keeps a `lastSuccessfulCollectionIndex` / stored-index list; deletion is an `ERASE_MEMORY` op. **Still needed:** the exact erase/ack semantics (control-message fields) to safely mark a collection consumed without corrupting the index list. |

**Bottom line:** the *format* of the recordings is fully characterized (16-bit mono 16 kHz PCM, raw or DD-Rice, in a length-prefixed record "collection"), and there is **no encryption to defeat**. The remaining unknowns are *transport-handshake* details (the 12-byte control messages, the index→address stride, and the exact DD-Rice parameter table) — all resolvable with **one captured GATT session** or the **ring firmware**, neither of which was in the provided artifacts.

---

*Method: klib unpacking (K2 IR via `klib dump-ir`), full decompilation of the Android AAR Java (CFR), disassembly of the x86-64 and arm64-v8a `.so` (capstone + pyelftools, with a corrected x86-64 PLT map), symbol/string/.rodata scans for crypto and codecs, and cross-reference with the public `coredevices/kotlin-speex` and `coredevices/mobileapp` repositories. All findings are logged with offsets in `work/NOTES.md`.*
