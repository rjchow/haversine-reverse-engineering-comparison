# Pebble Index 01 / Haversine recording format

Technical reverse-engineering report for Haversine release `03202f5`
Date: 2026-08-20 (Asia/Singapore)

This report is based on the exact physical-iPhone and Apple-Silicon-simulator
Maven KLIBs named in `brief.md`, their separately published native cinterop
archives, and the same-release Android library as an independent
cross-platform check. “Known” below means directly supported by recovered
Kotlin IR, native metadata, symbols, or instruction-level control flow.
“Strong inference” is stated as such. Unresolved firmware-only facts are
reported as unknown.

## 1. Executive answer

The Index transmits an indexed, variable-length **Haversine collection object**.
After BLE/CoreBluetooth has delivered its plaintext characteristic values, the
object is already directly parseable as a length-delimited TLV collection. Its
audio is represented by one of two record types:

- `0x50`: an explicit sample rate followed by mono signed PCM16 little-endian;
- `0x51`: an explicit sample rate plus a custom, one-channel, bit-packed
  second-difference codec named `DDRiceCompression` in the native objects.

The compressed representation is not IMA ADPCM, Speex, Opus, CELT, or SILK.
It entropy-codes signed second differences, then Haversine performs two
wrapping 16-bit integrations to reconstruct sample words. There is no fixed
codec frame size or encoded sample count. An exact compressed bit count ends
the stream. Both representations are supported; without a real captured
collection, these binaries do not prove which one current production firmware
normally emits.

The audio record carries its source sample rate as a little-endian `uint32`.
Haversine passes that value unchanged to `TransferComplete.sampleRate`; it is
not hardcoded and is not resampled inside Haversine. The exact numeric rate
used by a shipping recording is therefore **unknown without a capture**.
The Pebble app subsequently removes DC bias, resamples from that supplied rate
to 16 kHz, and writes raw mono PCM16LE.

BLE notifications may fragment a read arbitrarily, but those notification
boundaries are not audio frames. Telesto accumulates the declared read length,
then the transfer operation hands one complete collection to PPCommon. A long
logical recording may span multiple indexed collection objects. Haversine
decodes each object separately to PCM16 and concatenates the decoded samples.

There is **no Haversine/application-layer recording encryption**. Collection
bytes go directly from Telesto receipt to the collection parser and PCM/DD-Rice
decoder. That path has no key, nonce, IV, tag, identity, registration state, or
decrypt call. Registration writes a UID, Unix timestamp, and unkeyed 32-bit
fingerprint; it does not generate, receive, derive, or persist a shared secret.
The only evidenced persistent cryptographic relationship is OS-controlled BLE
bonding/link security.

Whether the ring transparently encrypts its **physical flash at rest** is
unknown. The client proves that the object served through the Telesto virtual
collection address is plaintext and self-contained. It cannot prove whether
ring firmware stores those identical bytes, transforms them on read, or uses
hardware/firmware-only flash encryption.

| Question | Evidence-supported result |
| --- | --- |
| Application payload | Complete length-delimited collection object |
| Audio representation | `0x50` PCM16LE or `0x51` custom DD-Rice |
| Width / channels | 16-bit reconstructed samples; one channel (strongly mono) |
| Source sample rate | Explicit per audio record; production value unknown |
| Fixed audio frame size | None |
| Application encryption in transit | No |
| Registration-derived recording secret | No |
| BLE link encryption | Platform controlled; actual session/mode unknown |
| Physical storage encryption | Unknown |
| Application CRC/MAC/FEC | None |
| Recording delete/ack command used by Haversine | None |

## 2. End-to-end data path

The recovered pipeline is:

```text
microphone
  -> [firmware capture/physical flash representation: unknown]
  -> indexed Telesto virtual collection object
       outer length envelope
       TLVs, including 0x50 PCM16LE or 0x51 DD-Rice
  -> Telesto READ at 0x40020000 | uint16(collectionIndex)
  -> arbitrary GATT notification fragments on the Telesto data characteristic
  -> [optional BLE link encryption, removed by CoreBluetooth/BluetoothGatt]
  -> TelestoResponse.length-controlled collection accumulation
  -> GSParseRecordsInRawData
  -> PPCollection_createAudioTimeline
       0x50: copy PCM16 sample bytes
       0x51: DD-Rice decode to 16-bit sample words
  -> PPAudioTimeline / Kotlin ShortArray
  -> decoded-PCM concatenation for multipart recordings
  -> TransferStatus.TransferComplete(samples, sampleRate, ...)
  -> app removes DC bias
  -> app resamples supplied sampleRate -> 16000 Hz
  -> app writes raw mono PCM16LE
```

The important layer boundaries are:

1. **GATT fragments are transport fragments.** They carry direct slices of a
   Telesto request, response, or data stream and have no additional Haversine
   chunk header.
2. **A collection is the application transfer object.** Haversine buffers it
   completely before parsing it.
3. **An audio TLV is one variable-length sample stream, not a sequence of
   fixed codec frames.**
4. **Multipart is above the codec.** Each collection part resets the DD-Rice
   predictor, decodes independently, and Haversine concatenates PCM samples.

The physical on-ring representation is the one break in this chain that a
client binary cannot expose. Reading a collection-indexed virtual address and
immediately parsing the returned blob is evidence that the served object is
storage-like. Treating it as proof of the raw flash layout would be an
unsupported leap.

## 3. Codec analysis

### 3.1 Proven audio properties

| Property | Result |
| --- | --- |
| Supported record types | `0x50` uncompressed, `0x51` compressed |
| Output sample width | 16 bits |
| App-facing type | signed Kotlin `Short` |
| Channels | one native decoder channel; no channel-count/interleave field |
| Raw byte order | little-endian |
| Compressed bit order | most-significant bit first within each byte |
| Sample rate | explicit `uint32le`, passed through unchanged |
| Sample count | derived from raw byte length or number of decoded codewords |
| Codec frame size | none |
| Predictor scope | reset to zero for each compressed audio TLV |

The mono conclusion is a strong inference rather than an explicit “channels =
1” field: `PPCollection_createAudioTimeline` initializes exactly one DD-Rice
channel at index zero, has no channel loop, and appends one output word for
each decoded difference. The uncompressed layout likewise has no channel
count or interleave metadata, and the app consumes the result as mono.

### 3.2 Uncompressed record `0x50`

Offsets are relative to the record type byte:

| Offset | Size | Meaning |
| ---: | ---: | --- |
| `0x00` | 1 | type `0x50` |
| `0x01` | 4 | payload length, `uint32le` |
| `0x05` | 4 | sample rate in Hz, `uint32le` |
| `0x09` | remaining | signed PCM16LE sample words |

For a valid record:

```text
sampleCount = (payloadLength - 4) / 2
```

The native branch allocates the output and `memcpy`s the sample bytes. It
does not decrypt, byte-swap, resample, apply gain, or run another codec.

### 3.3 Compressed record `0x51`

| Offset | Size | Meaning |
| ---: | ---: | --- |
| `0x00` | 1 | type `0x51` |
| `0x01` | 4 | payload length, `uint32le` |
| `0x05` | 1 | DD-Rice configuration byte |
| `0x06` | 4 | exact compressed bit count, `uint32le` |
| `0x0a` | 4 | sample rate in Hz, `uint32le` |
| `0x0e` | remaining | MSB-first compressed bitstream |

The nine-byte compressed payload header gives:

```text
payloadLength = 9 + compressedByteCapacity
compressedBitCount <= compressedByteCapacity * 8
```

There is no encoded sample count. Every complete codeword produces one sample,
and the declared bit limit terminates the record. The shipped decoder uses the
same “no bit” status both before a new codeword and in the middle of a
codeword; `PPCollection_createAudioTimeline` treats that status as successful
end-of-stream in either position. Thus a bit count ending mid-symbol silently
drops that incomplete final symbol. A defensive client should flag or reject
that malformed-tail case.

Let:

```text
s = config & 0x0f          // reconstruction left shift / quantization shift
L = config >> 4            // bounded-unary cutoff, 0..15
M = 1 << (16 - s)
```

The exact decoder can be expressed as:

```text
reader = MSBFirstBitReader(bitstream, compressedBitCount)
firstDifference = 0
sampleBase = 0

while reader has bits:
    first = readBit()

    if first == 1:
        encoded = 0
    else:
        zeroCount = 1
        terminator = 0

        while zeroCount < L:
            zeroCount += 1
            terminator = readBit()
            if terminator == 1:
                break

        if terminator == 0:
            # bounded-unary escape
            encoded = readBits(16 - s)
        else:
            magnitude = zeroCount - 1
            sign = readBit()              # 0 positive, 1 negative
            encoded = magnitude if sign == 0 else M - magnitude

    diff = encoded if encoded < M/2 else encoded - M

    firstDifference = uint16(firstDifference + diff)
    sampleBase = uint16(sampleBase + firstDifference)
    output.append(int16(uint16(sampleBase << s)))
```

Equivalently, for the normal `L >= 1` case:

- `1` means a zero second difference;
- `0^m 1 sign`, for `1 <= m < L`, means signed magnitude `m`;
- `0^L` followed by a `(16-s)`-bit literal is the escape.

The shipped **encoder** initializer accepts canonical configurations only
through `0xef`. The collection **decoder** does not repeat that validation and
mechanically accepts high-nibble `0xf` (`0xf0..0xff`). A compatible decoder
should therefore support `L == 15`, even though the included encoder would not
emit it.

All state arithmetic wraps modulo 16 bits. When `s == 0`, the double-delta
transform itself is reversible modulo 16 bits. A nonzero `s` reconstructs only
values aligned to `2^s`, so such a configuration may be quantized/lossy.

This is a custom second-order-delta entropy code. The object and symbols call
it `DDRiceCompression`, but its concrete bounded-unary/signed-small-value
code and literal escape are more precise than calling it a generic Rice code.
There are no IMA predictor step/index tables, nibble decoder, LPC synthesis,
Opus/Speex imports, or third-party audio decoder calls in this path.

### 3.4 Independent validation

The reconstructed decoder was checked against bitstreams emitted by the exact
simulator ARM64 `DDRiceCompression.o`, using configurations `0x30`, `0x40`,
`0x51`, and `0x72`. The native decoder reproduced the expected samples, and
the standalone Python implementation reproduces all four native vectors.
Those vectors cover signed small values, literal escapes, modulo overflow, and
nonzero reconstruction shifts. A native decoder-only edge test additionally
confirms that config `0xf0` is accepted and that a bit limit ending
mid-codeword returns status `3`.

The runnable implementation is `scripts/decode_index_collection.py`; its
regression suite is `scripts/test_decode_index_collection.py`. It matches the
native decoder on valid streams but intentionally rejects a truncated final
codeword instead of reproducing the native silent-tail behavior. The
test-suite sample rate of 24 kHz is synthetic test data and must not be
mistaken for a production-ring observation.

### 3.5 Multipart reconstruction

Record `0x52` marks multipart membership:

| Offset | Size | Meaning |
| ---: | ---: | --- |
| `0x00` | 1 | type `0x52` |
| `0x01` | 2 | nominal payload length `6`, `uint16le` |
| `0x03` | 4 | multipart group start index, `uint32le` |
| `0x07` | 1 | `isMultiPart` (`0` false, nonzero true) |
| `0x08` | 1 | `isFinalPart` (`0` false, nonzero true) |

The `startIndex` is the common group origin, not the current part index. The
current index arrives separately from the transfer layer. Haversine requires
one sample rate across a group, writes each decoded `Short` as little-endian
to its multipart buffer, and reads it back as a `ShortArray` on completion.
It checks that received indexes form a contiguous range, but it appends samples
in arrival/processing order rather than sorting parts. A final part with gaps
can still emit audio with `isContiguous = false`.

## 4. Frame and protocol structure

### 4.1 BLE service and characteristics

| Role | UUID |
| --- | --- |
| Haversine service | `607B5C9B-3700-4E94-F44A-2DF900BCB0C3` |
| Assigned 16-bit service also recognized | `FCC9` |
| Telesto data | `DAAD3D52-237C-90A7-B54B-8854A134D801` |
| Telesto control | `C0EF558A-2058-FABF-A140-8D5ACDE50B39` |
| System input | `1D1F4039-23F5-33B2-C24E-704351F20585` |

The client subscribes to control and data notifications. A 13-byte Telesto
request is written directly to control. The 12-byte operation response arrives
on control; read payload bytes arrive on data. Incoming GATT notification
boundaries are not preserved by any higher-level Haversine header.

iOS fragments outgoing data using
`maximumWriteValueLength(for: .withoutResponse)` and may insert a
`.withResponse` write for pacing. The exact Android adapter uses 20-byte
`.withoutResponse` slices. These are adapter policies, not Telesto wire fields.

### 4.2 Telesto request

| Offset | Size | Meaning |
| ---: | ---: | --- |
| 0 | 1 | operation type |
| 1 | 4 | virtual address, `uint32le` |
| 5 | 4 | offset, `uint32le` |
| 9 | 4 | length, `uint32le` |

Operation values:

| Value | Operation |
| ---: | --- |
| 0 | no operation |
| 1 | erase |
| 2 | program |
| 3 | read |
| 4 | cancel |
| 5 | erase then program |

A cancel copies the original address, offset, and length and changes the
operation to `4`.

### 4.3 Telesto response

| Offset | Size | Meaning |
| ---: | ---: | --- |
| 0 | 4 | error, `uint32le` |
| 4 | 4 | info, `uint32le` |
| 8 | 4 | returned data length, `uint32le` |

The controller permits one outstanding operation and accumulates exactly 12
control bytes. Control and data notifications may interleave: the recovered
controller tolerates data bytes arriving before all 12 control bytes, streams
them to the active read operation, and uses the declared response length as
its completion target once known. Excess data is capped/truncated with a
warning rather than rejected; oversized control input, in contrast, is a
controller error. A defensive new client should treat either excess case as
desynchronization. A nonzero response error fails the operation. The semantic
use of `info` for collection reads was not found; Haversine does not rely on it
for audio reconstruction.

There is no request/response sequence ID, per-data-fragment header, checksum,
nonce, authentication tag, or retry counter.

### 4.4 Collection enumeration and reads

| Purpose | Telesto READ address | Request length | Returned body |
| --- | ---: | ---: | --- |
| Stored collection range | `0x40030005` | 4 | two `uint16le` indexes |
| Collection `i` | `0x40020000 \| uint16(i)` | 0 | complete collection object |
| Current advertising data | `0x4003000e` | 10 | ten advertisement bytes |

The stored range is interpreted as a modulo-`2^16`, half-open interval
`[start, end)`. Native C membership/iteration uses wrapping `uint16`
arithmetic and includes a defensive guard after roughly `0x200` steps; that
guard is not proof of a firmware wire maximum. The exact Kotlin bridge later
converts endpoints to an ordinary `IntRange` and applies a non-modular resume
calculation, so fully integrated rollover behavior is not proven by these
artifacts. An independent client should preserve modular arithmetic and may
adopt 512 as its own conservative span cap. A collection buffer is capped at
`0xA0000` (655,360) bytes.

After exhausting the selected range, Haversine rechecks the authoritative
stored range so it can discover collections completed during the download.
When no collection is ready, it reads ten bytes at `0x4003000e`, feeds bytes
4..9 to the six-byte advertisement parser, and examines flag bit 5
(`in collection`). If that bit is set, it returns to the stored-range read; if
clear, the transfer operation finishes. The static code establishes this loop,
but not a general client poll interval or maximum recording duration.

`lastTransferEndIndex` is an exclusive next index cached in the SDK. The
app-provided `CollectionIndexStorage`, by contrast, records an inclusive
“last successfully handled collection index.” These values must not be
silently interchanged in an independent implementation.

### 4.5 Outer collection envelope

`GSParseRecordsInRawData` accepts three mutually distinguishable forms:

| Selection | Header | First TLV | Required length relationship |
| --- | --- | ---: | --- |
| `inputLength >= 4` and byte 3 is zero | `uint32le totalLength` | 4 | `totalLength == inputLength` |
| otherwise, byte 0 is `ff` | `ff` + `uint16le bodyLength` | 3 | `bodyLength == inputLength - 3` |
| otherwise | `uint24be bodyLength` | 3 | `bodyLength == inputLength - 3` |

In the four-byte form, byte 3 is the zero high byte of a total length below
`0x01000000`. It is not a terminator or version. In a three-byte form, byte 3
would be the first TLV type, and type zero is invalid; this is how the parser
disambiguates the layouts.

There is no multi-byte magic, collection version, record count, terminator,
CRC, or checksum. The declared outer length ends the object.

### 4.6 Inner TLVs

Ordinary records:

```text
u8     type
u16le  payloadLength
u8     payload[payloadLength]
```

Audio records `0x50` and `0x51`:

```text
u8     type
u32le  payloadLength
u8     payload[payloadLength]
```

Relevant audio-adjacent records are:

| Type | Nominal payload | Meaning |
| ---: | --- | --- |
| `0x50` | variable | PCM16 audio |
| `0x51` | variable | DD-Rice audio |
| `0x52` | 6 bytes | multipart group/flags |
| `0x53` | 8 bytes | `uint32le sequence`, `uint32le count`; bits LSB-first, `1` long and `0` short |
| `0x54` | 4 bytes | `uint32le` lifetime collection count |

For completeness, the native type dispatch accepts `0x01..0x12`,
`0x21..0x22`, `0x24..0x29`, `0x30..0x35`, and `0x50..0x54`. It rejects
`0x00`, `0x13..0x20`, `0x2a..0x2f`, `0x36..0x4f`, and values above `0x54`.
Type `0x23` (`FULL_CLUB_SETTINGS`) is a special immediate `PPFail`, not an
ordinary accepted TLV.

Duplicate types overwrite their parser slot, so the last record of a type is
used. If both audio types are present, the timeline function prefers the last
`0x50` over `0x51`.

The audio TLVs themselves contain no current collection index, recording ID,
timestamp, sequence number, codec version, or integrity field. The current
`uint16` index is transport context from the virtual address; `0x52.startIndex`
is only the multipart group origin; `0x53` is button metadata; and `0x54` is a
device lifetime count. Other recognized non-audio collection TLVs exist, but
none participates in decoding the `0x50`/`0x51` stream.

The native collection parser verifies the outer length and recognized type but
has unsafe inner-TLV validation gaps: it reads length fields without first
proving they fit, and accepts a final cursor that overshoots the outer end.
A new client should not copy those bugs. It should bounds-check every header
and payload, enforce the minimum audio headers/even PCM byte count, and require
the final cursor to equal the declared end.

### 4.7 Incrementality, integrity, acknowledgment, and deletion

Application-layer integrity mechanisms that do exist:

- Telesto response error and expected total data length;
- exact outer collection length;
- per-record payload lengths;
- compressed bit count bounded by available bytes;
- stored collection indexes and a bounded range;
- multipart progression/contiguity and sample-rate consistency checks.

The bit-count bound proves only that the bitstream fits; it does not prove that
the declared limit ends at a complete codeword.

Mechanisms not found in Telesto, the collection, or the audio record:

- CRC or checksum;
- cryptographic hash, MAC, or authentication tag;
- FEC;
- per-chunk/audio-frame sequence number;
- per-chunk/audio-frame acknowledgment;
- application retransmission loop.

BLE Link Layer CRC, acknowledgments, retransmission, and optional encryption
remain below this protocol and are intentionally not counted here.
CoreBluetooth write confirmations and the one Telesto operation response are
flow/operation completion, not acknowledgments for audio frames.

Haversine performs only READ operations for enumeration and collection
transfer. It does not send a recording-success acknowledgment and does not
erase a collection after transfer. Progress is remembered locally. The ring
appears to manage a bounded/wrapping range, but its retention/overwrite policy
is firmware-defined.

Although generic Telesto operation type `1` is “erase,” no evidence establishes
that issuing it against `0x40020000 | index` safely deletes one recording.
Doing so would be speculative and potentially destructive. Safe delete/ack
semantics remain unknown.

One official-client edge case matters to a replacement client:
`HaversineTransferDelegate.handleDidFinish` advances
`CollectionIndexStorage` before it checks for empty data or constructs
`PPCollection`. A fully received but malformed collection can therefore be
reported as irrecoverable without automatic reread. A robust independent
client should validate, decode, and durably commit output before advancing its
own resume index.

## 5. Cryptography analysis

| Layer | Result | Evidence and limitation |
| --- | --- | --- |
| BLE link encryption | **Unknown for a particular connection; platform controlled** | Android requests OS bonding; iOS relies on CoreBluetooth connection-triggered pairing. Firmware permissions/SMP mode and a live session determine whether/how the link is encrypted. |
| Haversine application encryption in transit | **No** | Telesto payload flows directly to the plaintext collection parser and PCM/DD-Rice decoder. No key/decrypt stage or encrypted wrapper exists. |
| Haversine-managed recording encryption at rest | **No** | Haversine has no recording key, cipher, or key-dependent decoder; returned collections are self-contained plaintext. |
| Transparent firmware/hardware flash encryption | **Unknown** | It could exist below the virtual-address interface and be invisible to all client code. Firmware or raw-flash evidence is required. |

The decisive positive call trace is:

```text
Telesto read bytes
  -> HaversineTransferDelegate.handleDidFinish
  -> PPCollection(index, data)
  -> PPCollection_createFromBinaryData
  -> GSParseRecordsInRawData
  -> PPCollection_createAudioTimeline
  -> direct PCM copy or DD-Rice decoder
  -> TransferComplete
```

Inputs to this path are the collection index and bytes. Neither `PPCollection`,
`PPCollection_createAudioTimeline`, nor any DD-Rice routine accepts a ring ID,
UID, fingerprint, cached application data, key, IV, nonce, or tag.

Symbol, import, string, and call-path audits found no recording-reachable AES,
CCM/GCM, ChaCha20, Poly1305, Salsa20, CTR/CBC/XTS, HKDF, HMAC, SHA-256, ECDH,
Curve25519/X25519, P-256, `CCCrypt`, CryptoKit, `SecKey`, Keychain, Java
`Cipher`, or Android Keystore operation. A generic Apple Security-framework
link option is present elsewhere, but no relevant undefined API or call enters
the recording path. The conclusion therefore rests on the recovered complete
keyless path, not merely on negative string searches.

The observed one-byte `00` write to `DAAD...` is not evidence of a secret.
That UUID is Telesto's general data channel, not a key characteristic, and the
full Haversine registration object is 145 bytes. A one-byte access might
trigger an OS security procedure or belong to another operation; its exact
purpose needs a synchronized live trace.

## 6. Key-management analysis

### 6.1 Registration record

`programSatelliteWithUserID` takes the caller's Firebase UID and current Unix
seconds, then initializes and serializes `PPRingApplicationData_t`.

The logical in-memory fields are:

```c
uint32_t fingerprint;
uint32_t timestamp;
char     uid[129];
```

Version-1 serialization is exactly:

| Offset | Size | Meaning |
| ---: | ---: | --- |
| `0x00` | 4 | version `1`, `uint32le` |
| `0x04` | 4 | UID fingerprint, `uint32le` |
| `0x08` | 4 | Unix timestamp, `uint32le` |
| `0x0c` | 129 | NUL-terminated/zero-padded UID bytes |
|  | **141** | total |

Haversine wraps this in `TelestoLengthPrefixedData`:

```text
uint32le totalLength = 145
u8 applicationData[141]
```

It sends a 13-byte Telesto operation-`5` request (erase then program) to the
control characteristic, for application-data virtual address `0x40000000`,
offset zero, length 145. It sends the 145-byte length-prefixed body to the data
characteristic. The normal first body bytes are therefore:

```text
91 00 00 00 01 00 00 00
```

The response is the ordinary 12-byte Telesto status. No registration response
field returns a secret.

### 6.2 Fingerprint is not a key

The 32-bit fingerprint is an unkeyed fixed integer mixer applied to 33
little-endian words from a zero-padded 132-byte UID buffer. Arithmetic below
wraps at 32 bits:

```text
mix(x):
    x = x + 0x7ed55d16 + (x << 12)
    x = (x ^ 0xc761c23c) ^ (x >> 19)
    x = x + 0x165667b1 + (x << 5)
    x = (x + 0xd3a2646c) ^ (x << 9)
    x = x + 0xfd7046c5 + (x << 3)
    x = (x ^ 0xb55a4f09) ^ (x >> 16)
    return x

fingerprint(uid):
    scratch = UID bytes copied into 132 zero-initialized bytes
    return XOR(mix(u32le(scratch[i:i+4])) for i = 0,4,...,128)
```

The optimized ARM64 object fuses the third and fourth mixer stages into the
algebraically equivalent constants `0xe9f8cc1d` and `0xaccf6200`. Haversine:

- compares only its low 16 bits when matching a UID;
- treats low 16 bits `ffff` as “no user”;
- recognizes full value `deaddead` as a failsafe sentinel.

The UID is serialized beside the fingerprint. This value is an identity/cache
marker, not a secret, cryptographic hash, MAC, KDF output, or encryption key.

### 6.3 Persistent state

| Platform | Storage | State indexing | Stored content |
| --- | --- | --- | --- |
| iOS Haversine SDK | `NSUserDefaults`, key `HaversineSatelliteState_<CoreBluetooth UUID>`; JSON data | UUID suffix | name, versions, serial, sensor config, application data, fingerprint, optional last transfer end index |
| Android Haversine SDK | `SharedPreferences` file `com.wtlp.haversinecache`; Base64 Java serialization | MAC without colons | versions, serial, sensor config, application data, fingerprint, optional last transfer end index |
| Public app | fixed ordinary settings keys `ring_paired`, `last_sync_index` | not per-ring; `ring_paired` holds the selected device ID | target device and one global local resume value |

No Haversine Keychain/Keystore path stores a per-ring recording key. Other
app Keychain tokens and a debug-upload API key are unrelated and are not
reachable from pairing, transfer, or decoding.

Android also creates a Companion Device association and requests
`BluetoothDevice.createBond()`. iOS leaves any bond to CoreBluetooth. Bond
keys, if present, are owned by the phone/ring Bluetooth stacks and are not
exported to Haversine.

### 6.4 Explicit answers to the shared-secret hypothesis

| Question | Answer |
| --- | --- |
| Is an application secret generated during registration? | No. Only UID fingerprint and timestamp are computed. |
| Is a secret received from the ring? | No. The callback consumes ordinary success/failure. |
| Is there a public/private key exchange? | No. |
| Is a persistent Haversine key stored? | No. |
| How is a key indexed to a ring? | Not applicable; ordinary cache state is indexed by UUID/MAC. |
| Does decoding reference registration state? | No. |
| Does clearing app pairing data invalidate old captured recordings? | No; a captured collection remains independently decodable. It may prevent future device access until re-pairing. |
| Is bonding the only evidenced persistent cryptographic relationship? | Yes, within the inspected artifacts; its exact SMP/link behavior is outside Haversine. |

The registration-derived shared-secret hypothesis is therefore disproved for
Haversine `03202f5`.

## 7. Relevant symbols and functions

All native offsets below are object-relative, avoiding false precision from a
later link address.

### 7.1 `TransferComplete` chain

```text
IOSHaversineTransferDelegate
  .collectionTransferDidFinishWith(NSData, collectionIndex, satelliteId)
    -> HaversineTransferDelegate.collectionTransferDidFinish(ByteArray, ...)
    -> HaversineTransferDelegate.handleDidFinish
    -> PPCollection(index, data)
    -> PPCollection_createFromBinaryData
    -> GSParseRecordsInRawData
    -> PPCollectionSimple_createAudioTimeline (generated cinterop wrapper)
    -> PPCollection_createAudioTimeline (native implementation)
       -> memcpy (0x50)
       or DDRiceDecompressionDecoder/Channel (0x51)
    -> PPAudioTimeline(PPResultAudioTimeline_t)
       -> allocate ShortArray(sampleCount)
       -> memcpy(sampleCount * 2)
    -> processSinglePartAudio / MultipartCollection.addPart
    -> emitCompleteTransfer
    -> TransferStatus.TransferComplete(..., samples, sampleRate, ...)
```

The recovered Kotlin IR constructor at
`analysis/iossimulatorarm64-transfer-wrapper-ir-excerpt.txt:670` passes the
multipart buffer's `ShortArray` as `samples` and the timeline/group rate as
`sampleRate`.

### 7.2 PPCommon device ARM64

| Object / symbol | Offset or important region | Role |
| --- | ---: | --- |
| `PPParsing.o::_GSParseRecordsInRawData` | `0x000`; header `0x48..0xe4`, TLV loop `0x1a0..0x424` | outer envelope and TLV parser |
| `PPCollection.o::_PPCollection_createFromBinaryData` | `0x00c` | copy complete object and invoke parser |
| `PPCollection.o::_PPCollection_createAudioTimeline` | `0x3b4` | select/decode audio |
| same, uncompressed branch | `0x450..0x484` | rate/count and PCM copy |
| same, compressed branch | `0x490..0x5a8` | bit-count check and DD-Rice loop |
| `DDRiceCompression.o::_DDRiceDecompressionDecoder_readBit` | `0x3b8` | MSB-first bit reader |
| `...readBits` | `0x414` | multi-bit literal reader |
| `...Channel_decodeDiff` | `0x47c` | codeword to signed second difference |
| `...Channel_nextWord` | `0x608` | two integrations and left shift |

`PPResultAudioTimeline_t` is a 32-byte ARM64 result:

| Offset | Field |
| ---: | --- |
| 0 | `uint32 collectionStartIndex` |
| 4 | `uint32 sampleRateHz` |
| 8 | `size_t sampleCount` |
| 16 | `uint16_t *samples` |
| 24 | `bool isMultiPart` |
| 25 | `bool isFinalPart` |

### 7.3 Transfer and Telesto simulator ARM64

| Object / symbol | Offset | Role |
| --- | ---: | --- |
| `HaversineTransferCollectionsOperation-*.o::_HaversineTransferCollectionsOperation_init` | `0x000` | allocate state and `0xA0000` data area |
| `::_TransferOperation_startNextChild` | `0x130` | issue range/collection/advertisement reads |
| `::_TransferOperation_handleReceivedDataFromChild` | `0x244` | append response data with bounds |
| `::_TransferOperation_handleCompletionFromChild` | `0x310` | iterate/wrap indexes and call collection delegate |
| `TelestoController.o::_TelestoController_receiveCtrlBytes` | `0x56c` | accumulate/parse 12-byte response |
| `TelestoController.o::_TelestoController_receiveDataBytes` | `0x628` | stream declared read body |

### 7.4 Registration

| `PPRingApplicationData.o` symbol | Device ARM64 offset |
| --- | ---: |
| `_mixBits32` | `0x000` |
| `__fingerprint` | `0x064` |
| `_PPRingApplicationData_fingerprintMatchesUserId` | `0x160` |
| `_PPRingApplicationData_init` | `0x1bc` |
| `__serialize_v1` | `0x250` |
| `_PPRingApplicationData_serializedSize` | `0x38c` |
| `_PPRingApplicationData_serialize` | `0x394` |

The same semantics and layouts were independently recovered from simulator
x86_64/ARM64 objects and the Android native/JVM build.

## 8. Evidence

### 8.1 Artifact identity

| Exact artifact | SHA-256 |
| --- | --- |
| `haversine-iosarm64-03202f5.klib` | `4f14675b857cff246dbc8ad607c3003972cc04506823e5ab40a42055eb7ec576` |
| `haversine-iossimulatorarm64-03202f5.klib` | `9ba0534f81762d59c2e73b24f053933836fe10cbdf7497d578f8e950f53e46a7` |
| device `cinterop-PPCommon` | `d77e25abb94f8a199dab7857cb8250d0022460e0319a843fc8805c46244d2732` |
| simulator `cinterop-PPCommon` | `d6ada452614b9c178206f3ca81ed9c70499dc021b70fd21af15dd11442aa117b` |
| device `cinterop-haversineSatelliteLibrary` | `d515f1a62ad2ed7479fa964cbeb2f63e68443d4309d83c87fed4ba8f9ab1dc21` |
| simulator `cinterop-haversineSatelliteLibrary` | `98cf6bad80999aa22bc58597b43bf5400ce7e0a486481199b8a757f0f54555bf` |
| same-release Android debug AAR | `6d41a5d0ec410646d9a903997a1a8a73e6ef0fc281cae07216a6a230c0e76989` |

Both main KLIBs contain serialized Kotlin metadata/IR rather than the native
codec itself. Their manifests identify Kotlin/Native `2.2.20` and the
separately published PPCommon/Haversine cinterop archives. The recovered main
IR dumps are byte-identical, 8,689 lines each, with SHA-256:

`0217f3549e3c5d54b79c2b8092a687f4cd22106d6f029b4ba62e66722ab8f300`.

The device PPCommon archive supplies eight ARM64 objects. The simulator archive
contains the corresponding universal ARM64/x86_64 objects. The satellite
archives supply 37 objects per architecture, with DWARF in the transfer layer.

### 8.2 Conclusion-to-evidence map

| Conclusion | Concrete retained evidence |
| --- | --- |
| `TransferComplete` receives decoded `ShortArray` | `analysis/toolchain_iosarm64_dump_ir.txt`; `analysis/iossimulatorarm64-transfer-wrapper-ir-excerpt.txt`; `analysis/iossimulatorarm64-ppcommon-wrapper-ir-excerpt.txt` |
| Exact collection envelope/TLV grammar | device `PPParsing.o`; `analysis/iossimulatorarm64-ppparsing-arm64-disassembly.txt`; `analysis/iossimulatorarm64-ppparsing-x86_64-disassembly.txt`; `analysis/collection_framing.md` |
| `0x50` layout/direct PCM copy | device `PPCollection.o` at `0x450..0x484`; simulator counterpart; `analysis/ghidra_decompiled/libppcommon_audio.c` |
| `0x51` layout/DD-Rice path | device `PPCollection.o` at `0x490..0x5a8`; `DDRiceCompression.o`; corresponding simulator disassembly |
| Exact codec behavior | `DDRiceCompression.o` decode and encoder symbols; `scripts/ddrice_native_harness.c`; `analysis/native_validation/`; standalone exact-native vectors |
| Telesto wire structures | `analysis/iossimulatorarm64-TelestoTypes-arm64-dwarf.txt`; Telesto controller disassembly; same-release Android operation classes |
| Collection addresses/range flow | `analysis/iossimulatorarm64-transfer-c-arm64-dwarf.txt`; `analysis/iossimulatorarm64-transfer-c-arm64-disassembly.txt`; Android `TransferCollectionsOperation.java` |
| No application delete/ack/retry | complete transfer state machine and Telesto call graph in `analysis/sim_inventory.md`; native/JVM cross-check |
| No application recording crypto | keyless end-to-end call trace, PPCommon imports/symbols, `analysis/pairing_crypto_audit.md` |
| Registration is UID/fingerprint/timestamp | `PPRingApplicationData.o`; cinterop metadata; exact KLIB IR `programSatelliteWithUserID`; Android programming bridge |
| Persistence is ordinary cache state | `HaversineEnvironment.o`; Android cache classes; public app Preferences/collection-index storage |
| App resamples only after `TransferComplete` | public app commit `6d6e2ebb010006e24959f300755516b84843b936`, `RingSync.kt` |

The detailed intermediate audits are:

- `analysis/device_inventory.md`
- `analysis/sim_inventory.md`
- `analysis/toolchain_strategy.md`
- `analysis/collection_framing.md`
- `analysis/pairing_crypto_audit.md`
- `analysis/independent_client_spec.md`

### 8.3 Reproducible decoder checks

From the repository root:

```sh
python3 scripts/decode_index_collection.py --self-test
python3 scripts/test_decode_index_collection.py
```

To decode a captured complete collection:

```sh
python3 scripts/decode_index_collection.py collection.bin \
  --wav collection.wav \
  --pcm collection.pcm
```

The decoder reports the envelope form, record/codec, sample rate, sample count,
DD-Rice config/bit count, multipart data, button sequence, and lifetime count.
It intentionally validates TLV bounds more safely than the shipped native
parser.

## 9. Remaining unknowns

| Unknown | Why the client binaries cannot answer it | Artifact that would resolve it |
| --- | --- | --- |
| Production source sample rate | It is a dynamic field, not a constant in the decoder | one actual complete collection |
| Whether shipping firmware normally emits `0x50` or `0x51` and which config | Both are supported and selected by record type | one or more production collections |
| Exact physical flash representation / transparent at-rest encryption | The Telesto virtual address may transform data below the client-visible boundary | ring firmware plus flash dump, or comparison of raw flash and returned collection |
| Which outer envelope production firmware normally emits | Parser accepts all three | collection capture |
| Exact BLE SMP mode and characteristic security permissions | CoreBluetooth/BluetoothGatt abstract the controller exchange | firmware GATT metadata or HCI/over-air pairing trace |
| Exact meaning of the isolated `00` data-characteristic write | It is not the 145-byte registration record, but its surrounding operation is absent | synchronized GATT/HCI trace from that app revision |
| End-to-end behavior at the `uint16` collection-index rollover | Native C is modular, but the Kotlin bridge uses an ordinary `IntRange` and non-modular resume selection | synthetic bridge test plus a ring/capture near rollover |
| Safe remote recording acknowledgment/deletion | Haversine never performs one; generic erase is not enough evidence | firmware, vendor protocol source, or controlled on-device experiments |
| Physical retention/overwrite policy | Only the bounded/wrapping index range is visible | long-running controlled ring experiment or firmware |

These are genuine boundary unknowns, not gaps that further decompilation of
the same client archives is likely to settle.

## 10. Independent-client implications

An independent iOS client can now implement discovery, Telesto transport,
enumeration, download, parsing, DD-Rice decoding, multipart assembly, and
local resume without Haversine. Pairing details and destructive deletion still
require live-device work.

### 10.1 Implementable state machine

1. **Discover**
   - scan for service `607B...` and the recognized `FCC9` service form;
   - identify and retain the CoreBluetooth peripheral UUID.
2. **Connect and secure**
   - connect and discover the Haversine service;
   - discover Telesto control `C0EF...`, data `DAAD...`, and system input
     `1D1F...`; exact Haversine requires all three before declaring readiness,
     although only control/data carry recording protocol bytes;
   - enable notifications on control and data;
   - let CoreBluetooth trigger system pairing if a protected access requires
     it.
3. **Register, if ownership programming is required**
   - obtain the intended user UID;
   - compute the recovered unkeyed fingerprint;
   - serialize the 141-byte version-1 record;
   - prefix total length 145;
   - send Telesto erase+program (`5`) to `0x40000000`;
   - treat the ordinary Telesto error result as completion. No secret response
     is expected.
4. **Enumerate**
   - issue one READ (`3`) to `0x40030005`, offset 0, length 4;
   - parse `start:uint16le`, `end:uint16le` as `[start,end)` modulo 65536;
   - as a defensive client policy, reject an implausible span above 512;
   - combine it conservatively with the locally committed resume point.
5. **Download**
   - for each index in order, READ
     `0x40020000 | index`, offset 0, length 0;
   - independently accumulate the 12-byte control response and data stream,
     tolerating their interleaving; once the response is complete, require
     exactly its declared data length, capped at 655,360 bytes;
   - do not treat GATT chunks as audio frames;
   - after the chosen range, read `0x40030005` again; if it is empty, read
     `0x4003000e`, parse advertisement flag bit 5, and return to enumeration
     while `in collection` remains set. Keep poll timing/timeouts configurable
     because the binaries do not establish a universal interval.
6. **Validate and decode**
   - validate an accepted outer envelope;
   - safely walk inner TLVs;
   - prefer `0x50` if present, otherwise decode `0x51` with the recovered
     algorithm;
   - retain the per-record sample rate;
   - parse `0x52`/`0x53`/`0x54` as needed.
7. **Assemble**
   - for multipart data, require the repeated group start index, consistent
     rate, ordered contiguous current indexes, and a final flag;
   - concatenate decoded PCM16, not compressed bytes;
   - surface gaps instead of silently calling them complete.
8. **Commit and resume**
   - optionally save the exact raw collection as a durable staging artifact,
     without treating staging alone as processed;
   - write the decoded recording and metadata durably;
   - only after successful validation and durable commit, set the chosen local
     checkpoint explicitly—for example,
     `processedNext = (index + 1) & 0xffff`; if also storing an inclusive
     value, set `lastSuccess = index` as a separate field;
   - on transport failure, reconnect and reread from the last durable commit.
9. **Postprocess**
   - if matching the Pebble app, remove DC bias, resample from the supplied
     rate to 16 kHz, and serialize mono PCM16LE.
10. **Acknowledge/delete**
    - maintain local acknowledgment only;
    - do **not** issue Telesto erase to a collection address without new
      firmware/live-device evidence;
    - leave retention to firmware and tolerate the advertised range evolving;
      its exact overwrite/rollover policy remains unknown.

### 10.2 Reliability requirements for a new implementation

- Serialize operations because Telesto supports one outstanding operation.
- Treat a partial 12-byte response and partial data body as resumable transport
  state only within the current connection; otherwise restart the read.
- Validate every length before allocation/copy and cap collection size.
- Reject trailing/overshooting TLVs even though the native parser accepts one
  overshoot class.
- Preserve modulo-16-bit index arithmetic and distinguish inclusive from
  exclusive persisted indexes.
- Persist a collection only after its full body and audio decode succeed.
- Keep incomplete multipart groups until the expected next index/final part or
  explicitly mark them incomplete.
- Do not invent an application ACK, CRC, key exchange, or encryption layer.

### 10.3 Work still requiring a real Index

- characterize CoreBluetooth pairing prompts, bond reuse, and GATT permissions;
- capture the first production collection to record its actual sample rate,
  audio type, DD-Rice config, and envelope choice;
- determine whether registration is mandatory for transfer under each firmware
  version;
- test retention/rollover non-destructively;
- establish a documented, safe delete/ack operation, if one exists.

Until that last item is resolved, an independent client can safely download,
decode, locally acknowledge, and resume recordings, but cannot promise remote
deletion.
