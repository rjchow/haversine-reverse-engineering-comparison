# Haversine benchmark: atomic grading rubric

Status: final

Date: 2026-08-21

Ground-truth corpus: `gpt-5.6-sol-ultra/`

Maximum base score: 100 points

Maximum verified-novelty bonus: 5 points

## 1. Purpose

This is the point-by-point version of the grading rubric. It contains exactly
100 nominal one-point checkpoints arranged hierarchically:

| Hierarchy | Checkpoints | Points |
|---|---:|---:|
| T. Technical reconstruction | 70 | 70 |
| R. Reverse-engineering rigor | 18 | 18 |
| P. Reporting and implementation utility | 12 | 12 |
| **Total** | **100** | **100** |

The associated candidate scores are recorded in `GRADING_LEDGER.md`.

## 2. Atomic scoring rule

Every checkpoint has a nominal value of one point:

- `+1`: the submission states the required result explicitly and correctly;
- `+0.5`: the core result is correct, but one material qualifier or required
  detail is missing;
- `0`: absent, too vague, or unsupported;
- `-1`: the submission explicitly contradicts the required result or invents
  a mutually incompatible field, value, or behavior.

Rules:

1. A correct statement elsewhere does not erase an explicit contradiction.
   Internally contradictory treatment normally receives `0` or `-1`, depending
   on whether the contradiction is material to implementation.
2. A checkpoint is scored once across all retained authored files.
3. Each named subsection (`T1`, `T2`, ..., `P5`) is floored at zero and capped
   at its listed point count after its atomic scores are summed.
4. Evidence-specific checkpoints require a traceable artifact and at least one
   symbol/function, object, offset, disassembly excerpt, IR location, or
   executable test.
5. A bare string/class-name hit earns at most `+0.5` on an evidence checkpoint.
6. Additional penalties, applied after the 100-point base sum:
   - `-2` for fabricated or materially mismatched evidence;
   - `-3` for an unsafe unsupported destructive instruction.
7. Final base scores are bounded to `0..100`.

## 3. T — Technical reconstruction: 70 points

### T1. End-to-end recording representation: 14 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| T1.01 | Mark microphone capture, raw physical-flash representation, and transparent firmware/hardware flash encryption as unknown from the client artifacts. | Assert that PCM/DD-Rice collection bytes are proven to be the raw physical-flash bytes, or that physical flash encryption is definitively absent. |
| T1.02 | Identify the client-visible object as an indexed, directly parseable Haversine collection exposed through the ring's Telesto virtual address space. | Describe the served object as an opaque codec file or unrelated stream. |
| T1.03 | State that Haversine buffers one complete collection object before PPCommon parsing. | State that PPCommon decodes each BLE notification independently. |
| T1.04 | Separate arbitrary GATT fragments from Telesto, collection, TLV, and codec boundaries; state that notifications have no per-notification Haversine header. | Add a four-byte Haversine/Telesto length prefix to every incoming notification or call notifications codec frames. |
| T1.05 | Identify record `0x50` as uncompressed mono signed PCM16 little-endian with an explicit sample rate. | Assign `0x50` to another codec or metadata role. |
| T1.06 | Identify record `0x51` as custom DD-Rice second-difference compressed audio. | Assign compressed audio exclusively to another type or standard codec. |
| T1.07 | State that both `0x50` and `0x51` are supported and that the normal production choice is unknown without a capture. | Claim that the inspected client proves which type shipping firmware normally emits. |
| T1.08 | State that each audio record carries `sampleRateHz` as a little-endian `uint32`. | Derive the rate solely from the app's resampler target. |
| T1.09 | State that the numeric production source rate is unknown without a captured collection or firmware-side proof. | Assert 8, 16, 24, or another kHz value as proven from the app target or synthetic tests. |
| T1.10 | State that Haversine passes the record rate unchanged to `TransferComplete` and does not resample during collection decoding. | Put the 16 kHz resampling step inside PPCommon/Haversine decoding. |
| T1.11 | Identify native output as 16-bit sample words copied to a Kotlin `ShortArray` and interpreted as signed PCM at the app boundary. | Claim 8-bit, float, or compressed app-facing samples. |
| T1.12 | Identify one operational audio channel: one decoder channel/sample stream, no channel-count/interleave field, app consumes mono. | Claim stereo/interleaving without evidence. |
| T1.13 | Explain that a logical recording may span multiple indexed complete collections, each audio TLV decodes independently, and Haversine concatenates decoded PCM. | Concatenate compressed bitstreams across parts or claim all parts use one current collection index. |
| T1.14 | Preserve the app boundary: DC-bias removal, resampling from the supplied rate to 16 kHz, and little-endian mono PCM16 serialization happen after `TransferComplete`. | Use the post-transfer 16 kHz output as proof of ring capture format. |

### T2. Codec reconstruction: 18 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| T2.01 | Give the `0x50` wire record as `u8 type`, `u32le payloadLength`, `u32le sampleRateHz`, then PCM bytes. | Invent an additional audio header or use a 16-bit audio length. |
| T2.02 | Give raw sample count as `(payloadLength - 4) / 2` and identify the native branch as a direct byte copy without decode/resample. | Claim a fixed 100,000-sample part size or another codec transform. |
| T2.03 | Give the `0x51` wire record as `u8 type`, `u32le payloadLength`, then a nine-byte compressed metadata header and bitstream. | Replace it with a 13-byte decoder header or assign the format to `0x52`. |
| T2.04 | Locate config at payload `+0`, `compressedBitCount:u32le` at `+1`, and `sampleRateHz:u32le` at `+5`. | Invent separate header-length fields or incompatible offsets. |
| T2.05 | Locate the bitstream at payload `+9` and state that bits are read MSB-first. | State LSB-first or start the stream after a fictitious header. |
| T2.06 | Decode config as `s = config & 0x0f`, `L = config >> 4`, with modular window `M = 1 << (16-s)`. | Swap the nibble roles without an equivalent formulation. |
| T2.07 | State that the first bit `1` encodes a zero second difference and first bit `0` enters unary/escape decoding. | Reverse the leading-bit polarity. |
| T2.08 | Recover the bounded-unary count: after the leading zero, additional zeros increase magnitude until a one terminates before cutoff `L`. | Use an unrelated ordinary Rice quotient/remainder algorithm. |
| T2.09 | Recover the sign bit after a terminated small magnitude: `0` positive, `1` mapped to `M-magnitude`. | Reverse or omit the sign mapping while claiming an exact decoder. |
| T2.10 | Recover the escape: `L` zeros followed by a raw `(16-s)`-bit modular literal. | Invent a remainder table or fixed decoder header. |
| T2.11 | Convert the modular value to signed using threshold `M/2`, subtracting `M` for the negative half. | Treat all literals as unsigned PCM deltas. |
| T2.12 | Perform the first wrapping 16-bit integration: `firstDifference += signedSecondDifference`. | Reconstruct directly from the residual without this state. |
| T2.13 | Perform the second wrapping integration and final shift: `sampleBase += firstDifference`; emit `sampleBase << s`. | Perform only one integration. |
| T2.14 | State that arithmetic wraps modulo 16 bits and predictor state begins at zero for each compressed audio TLV. | Carry predictor state across independent collection audio TLVs. |
| T2.15 | State that no encoded sample count or fixed codec frame exists; one complete codeword emits one sample until the exact bit limit. | Present the initial 100,000-sample allocation as a wire/frame cap. |
| T2.16 | Distinguish `s=0` reversible modulo-16-bit reconstruction from `s>0` quantized output aligned to `2^s`; avoid blanket losslessness. | Call every configuration lossless. |
| T2.17 | Distinguish encoder config validation (`<=0xef`) from decoder acceptance of high nibble `0xf`, and identify the native incomplete-tail behavior or explicitly leave it unresolved. | Claim the collection decoder rejects `0xf0..0xff` or gracefully authenticates truncated codewords. |
| T2.18 | Exclude IMA ADPCM, Speex, Opus, CELT, SILK, and application encryption through the reachable implementation, not dependency names alone. | Claim Speex provenance or another codec solely from a name/dependency. |

### T3. Protocol and framing: 15 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| T3.01 | Identify service `607B...B0C3` and the recognized `FCC9` form. | Use an unrelated service. |
| T3.02 | Identify Ctrl `C0EF...`, Data `DAAD...`, and System Input `1D1F...`, with correct roles and notification/write layering. | Put a per-notification application header on incoming Data or swap characteristic roles. |
| T3.03 | Give the packed 13-byte request: `u8 type`, then `u32le address`, `offset`, and `length` at offsets 1, 5, and 9. | Call it a 10-byte `hasData` command. |
| T3.04 | Give operations `0..5`: none, erase, program, read, cancel, erase-and-program; cancellation copies address/offset/length and changes type. | Omit/misnumber a claimed complete operation table. |
| T3.05 | Give the 12-byte response: `u32le error`, `info`, and returned-data `length` at offsets 0, 4, and 8; leave `info` semantics unknown for collection reads. | Assign `info` an unsupported transfer-index meaning or say the field layout is unavailable. |
| T3.06 | State that one operation is outstanding, Ctrl/Data may interleave, completion uses the declared length, excess Data is capped while oversized Ctrl is an error. | Require Ctrl to precede Data or merge excess-Data and excess-Ctrl behavior. |
| T3.07 | Give stored-range READ `0x40030005`, offset 0, length 4, returning two `u16le` endpoints. | Use `0x40020005` or describe an index list. |
| T3.08 | Give collection READ `0x40020000 \| uint16(index)`, offset 0, request length 0, returning a complete collection. | Use an unknown byte stride or arithmetic addition that can change high address bits. |
| T3.09 | Give current-advertising READ `0x4003000e`, length 10, and the re-enumeration loop controlled by collection-state data. | Invent a fixed poll loop unrelated to the advertising state. |
| T3.10 | Treat stored indexes as modulo-`2^16`, half-open `[start,end)`; distinguish the roughly-`0x200` implementation guard from a wire maximum and inclusive app checkpoints from exclusive next indexes. | Call the range inclusive or claim a proven 512-slot wire limit. |
| T3.11 | Give the four-byte envelope `u32le totalLength`, selected when byte 3 is zero, with first TLV at offset 4 and exact equality to input length. | Treat byte 3 as a terminator/version or omit this accepted form. |
| T3.12 | Give the three-byte `ff + u16le bodyLength` envelope, first TLV at 3, requiring `bodyLength == inputLength-3`. | Treat `0xff` as an inner record type. |
| T3.13 | Give the three-byte `u24be bodyLength` envelope and its exact length relationship. | Call this field little-endian. |
| T3.14 | Explain envelope disambiguation and that there is no multi-byte magic, version, record count, or terminator; the declared length ends the object. | Invent a version, magic, or terminator. |
| T3.15 | Give ordinary `u8+u16le` versus audio `u8+u32le` TLVs, last-duplicate/`0x50` precedence, relevant `0x52..0x54` roles, and native bounds-validation gaps. | Invent type-4 audio metadata, treat `0x52` as audio, or claim complete native bounds safety. |

### T4. Transfer, multipart, and integrity: 9 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| T4.01 | Identify complete-collection accumulation, Telesto Ctrl/Data accounting, and Haversine's `0xA0000` (655,360-byte) collection cap. | Replace the collection cap with the codec's initial sample allocation or app multipart buffer. |
| T4.02 | Separate current collection index from repeated multipart group origin; state that a logical recording spans consecutive collection objects. | Claim all parts have the same current collection index. |
| T4.03 | Give `0x52` as ordinary TLV metadata with `u32le startIndex`, `isMultiPart`, and `isFinalPart`, nominal payload length 6. | Call `0x52` compressed audio. |
| T4.04 | State sample-rate consistency, index-contiguity checking, final-part emission, arrival-order append, and that a gapped final group may emit with `isContiguous=false`. | Say the final flag proves completeness or that the implementation sorts parts. |
| T4.05 | Count Telesto error and returned-data length as operation/completeness checks, not cryptographic integrity. | Call the response a per-audio-frame authentication mechanism. |
| T4.06 | Count outer/TLV lengths, bit count, indexes, contiguity, and rate equality with their actual validation limitations. | Claim every TLV is safely bounds-checked or that bit count authenticates the stream. |
| T4.07 | Explicitly state absence of application CRC/checksum, hash/MAC/tag, FEC, transaction/per-chunk sequence, and per-chunk/frame ACK. | Attribute BLE Link Layer mechanisms to Haversine framing. |
| T4.08 | State there is no application recording-read retry loop; separate Telesto operation status and GATT pacing confirmations from recording acknowledgement. | Claim reconnect/resume is a per-chunk retransmission protocol. |
| T4.09 | State there is no official recording-consumed ACK/delete command; generic erase is insufficient, and local progress should advance only after validation/durable commit. | Prescribe generic ERASE against collection addresses as safe deletion. |

### T5. Cryptography, registration, and persistence: 14 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| T5.01 | Answer BLE link encryption as platform-controlled and unknown for a particular session/mode without firmware permissions or an HCI/SMP trace. | State that every reviewed connection is definitely encrypted or unencrypted. |
| T5.02 | Answer Haversine/application-layer recording encryption in transit as no. | Add an application cipher/decrypt layer. |
| T5.03 | Answer Haversine-managed recording encryption at rest as no: Haversine has no recording key/cipher. | Claim a Haversine-managed recording key. |
| T5.04 | Answer transparent firmware/hardware physical-flash encryption as unknown. | Conclude physical flash is definitely plaintext from phone-side evidence. |
| T5.05 | Supply the positive keyless call trace from Telesto bytes through collection parsing and PCM/DD-Rice decoding to `TransferComplete`. | Base the conclusion only on missing strings. |
| T5.06 | Corroborate with a relevant reachability/import inventory covering symmetric ciphers, KDF/MAC/hash, public-key exchange, nonce/tag APIs, and key storage. | Treat unrelated Security/TLS/debug-upload symbols as recording crypto. |
| T5.07 | Identify logical registration fields as `uint32 fingerprint`, `uint32 timestamp`, and `char uid[129]`. | Insert a 128-bit sensor fingerprint or omit the timestamp in a claimed exact layout. |
| T5.08 | Give version-1 serialization: version at 0, fingerprint at 4, timestamp at 8, UID at 12, total 141 bytes. | Use one-byte version plus invented padding/field widths. |
| T5.09 | Give the four-byte length prefix producing 145 bytes, Telesto operation `5`, address `0x40000000`, offset 0. | Describe the isolated `00` write as this registration object. |
| T5.10 | Explicitly answer: no secret generated/received/derived, no key exchange, no secret result, no persistent recording key, and decode is independent of registration. | Claim a challenge, KDF, or per-ring decoder key. |
| T5.11 | Identify the UID fingerprint as an unkeyed 32-bit mixer, with low-16-bit matching and sentinel behavior; do not call it a key/hash/MAC. | Conflate it with `PPFingerprintFromRawSensorData` or a 128-bit device secret. |
| T5.12 | Identify iOS state as ordinary JSON/cache data in `NSUserDefaults` under `HaversineSatelliteState_<UUID>`, with no recording key. | Claim Keychain storage for a Haversine recording key. |
| T5.13 | Identify Android/app resume/cache state and distinguish OS-owned BLE bond keys from Haversine state; captured collections remain decodable after app-state clearing. | Claim cache clearing cryptographically invalidates captured audio. |
| T5.14 | State that the observed one-byte `00` Data-characteristic write is not the 145-byte registration record or a proven secret exchange; exact purpose remains unknown without a trace. | Name it as the complete registration, secret, or challenge. |

## 4. R — Reverse-engineering rigor: 18 points

### R1. Artifact acquisition and inventory: 3 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| R1.01 | Identify and acquire the exact `03202f5` device and simulator KLIB targets with artifact provenance; hashes are preferred. | Analyze a different release while claiming exact parity. |
| R1.02 | Correctly inventory the top-level KLIBs as Kotlin/Native 2.2.20 serialized IR/metadata/linkdata rather than the native codec implementation. | Claim the top-level targets contain the codec object when they do not. |
| R1.03 | Discover and inspect the separately published PPCommon and HaversineSatelliteLibrary cinterop archives/native objects. | Claim those companion artifacts are unavailable when they are published. |

### R2. Exact call-chain recovery: 5 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| R2.01 | Trace the native/Swift transfer completion callback into `IOSHaversineTransferDelegate.collectionTransferDidFinish`. | Start only at an app-facing class name with no receive path. |
| R2.02 | Trace the Kotlin delegate/event path through `handleDidFinish` to `PPCollection(index, ByteArray)`. | Put decoding in CoreBluetooth. |
| R2.03 | Trace `PPCollection_createFromBinaryData` into `GSParseRecordsInRawData`. | Reverse parser and timeline-creation order. |
| R2.04 | Include `PPCollectionSimple_createAudioTimeline` as the cinterop wrapper and native `PPCollection_createAudioTimeline` with raw/DD-Rice branches. | Invent a third-party decoder call. |
| R2.05 | Trace native result ABI/sample copy, multipart processing, `emitCompleteTransfer`, and the exact `TransferComplete` constructor arguments. | Stop at a native sample pointer without establishing the app boundary. |

### R3. Cross-artifact verification: 3 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| R3.01 | Compare device and simulator top-level IR/metadata and report their relevant parity/differences. | Generalize from one target without comparison. |
| R3.02 | Verify major native parser/codec/transport conclusions across device ARM64 and simulator ARM64/x86_64 where available. | Assert architecture parity without examining the target native archives. |
| R3.03 | Use Android/public app/source as corroboration, not as the sole proof of target-iOS native behavior. | Treat Android native code alone as conclusive proof while published iOS native objects are unexamined. |

### R4. Reproducibility and validation: 4 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| R4.01 | Supply decoder pseudocode detailed enough to implement the exact bitstream and reconstruction. | Supply wire-incompatible pseudocode while calling it exact. |
| R4.02 | Supply exact reproducible wire examples/hex requests or commands sufficient to repeat key protocol checks. | Supply only prose guesses for byte structures. |
| R4.03 | Retain or precisely cite low-level IR/disassembly/DWARF evidence for the major findings. | Cite only unlocated strings or dependency names. |
| R4.04 | Deliver and run an independent decoder/native harness plus regression tests covering exact-native vectors and malformed framing. | Claim executable validation that was not performed. |

### R5. Falsification and confidence calibration: 3 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| R5.01 | Define and consistently apply direct/known, inference, and unknown labels. | Label an inference as directly proven throughout. |
| R5.02 | Ground negative conclusions in a complete positive path plus targeted negative reachability/import searches. | Infer no encryption solely from absent strings. |
| R5.03 | Preserve major unknowns and name resolving evidence; avoid the prompt's listed reasoning mistakes. | Infer source rate from 16 kHz output, physical-flash plaintext from logical bytes, or codec solely from a dependency/name. |

## 5. P — Reporting and implementation utility: 12 points

### P1. Required output coverage: 2 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| P1.01 | Cover all ten requested report sections or exact functional equivalents. | Omit several required areas. |
| P1.02 | Give an explicit executive answer to storage, transmission, Haversine input/output, encryption layers, and shared-secret hypothesis. | Leave the primary question unanswered. |

### P2. Technical presentation: 3 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| P2.01 | Present a correctly layered end-to-end pipeline separating GATT, Telesto, collection, TLV, codec, and app stages. | Merge incompatible layers into one framing structure. |
| P2.02 | Present correct byte-offset/size/endian tables for the core records and transport structures. | Tables confidently encode invented layouts. |
| P2.03 | Present readable, exact decoder pseudocode sufficient for implementation. | Present a wire-incompatible decoder as complete. |

### P3. Claim-to-evidence traceability: 3 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| P3.01 | Tie codec claims to exact native objects/functions/offsets or executable tests. | Use a codec/dependency name as the only proof. |
| P3.02 | Tie framing/transfer claims to exact request constants, structs, controller/operation functions, or byte examples. | Provide no traceable protocol evidence. |
| P3.03 | Tie crypto/registration/persistence claims to the positive path, exact serializer/fingerprint functions, cache fields, and relevant negative searches. | Cite unrelated key-like state as recording evidence. |

### P4. Independent-client utility and safety: 3 points

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| P4.01 | Give correct discovery, connection, BLE-security, and optional registration requirements with unknowns separated. | Prescribe an invented authentication/key exchange or wrong registration frame. |
| P4.02 | Give correct enumerate, download, validate, decode, multipart, and resume steps. | Supply wrong addresses, framing, or decoder such that read-only download cannot work. |
| P4.03 | Give robust length/error/commit rules and refuse speculative remote deletion/erase. | Prescribe unverified collection ERASE as safe. |

### P5. Internal consistency: 1 point

| ID | One-point objective requirement | Explicit `-1` trigger |
|---|---|---|
| P5.01 | Executive answer, detailed body, supporting documents, and unknowns agree on all central conclusions. | Retain material contradictions such as “lossless” versus acknowledged quantization or inclusive versus exclusive range. |

## 6. Verified-novelty bonus: up to 5 points

A finding receives novelty credit only when it:

1. is absent from the entire Sol Ultra corpus;
2. is relevant to the original investigation or independent-client safety;
3. is specific and falsifiable;
4. does not contradict assumed Sol Ultra ground truth;
5. is independently verified from binaries, retained evidence, source, capture,
   or a reproducible test.

Awards:

- `+1`: useful verified detail;
- `+2`: materially improves protocol/decoder/pairing understanding;
- `+3`: closes a major unknown or enables a new client capability;
- maximum `+5` per submission.

The same independently documented finding receives the same credit in every
submission containing it. Omission of a post-hoc novel finding does not reduce
the 100-point base score.

## 7. Count audit

| Subsection | IDs | Points |
|---|---:|---:|
| T1 | 14 | 14 |
| T2 | 18 | 18 |
| T3 | 15 | 15 |
| T4 | 9 | 9 |
| T5 | 14 | 14 |
| **Technical subtotal** | **70** | **70** |
| R1 | 3 | 3 |
| R2 | 5 | 5 |
| R3 | 3 | 3 |
| R4 | 4 | 4 |
| R5 | 3 | 3 |
| **Rigor subtotal** | **18** | **18** |
| P1 | 2 | 2 |
| P2 | 3 | 3 |
| P3 | 3 | 3 |
| P4 | 3 | 3 |
| P5 | 1 | 1 |
| **Reporting subtotal** | **12** | **12** |
| **Base total** | **100** | **100** |
