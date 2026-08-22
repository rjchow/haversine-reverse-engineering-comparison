# Haversine reverse-engineering benchmark grading

Date: 2026-08-22
Ground truth: `gpt-5.6-sol-ultra/`
Submissions graded:

- `gpt-5.6-luna-xhigh/`
- `qwen3.8-2.4t-openrouter/`
- `glm-5.3-openrouter-max/`
- `stealth-ox-alpha-openrouter-max/`
- `qwen3.8-27b-local-4bit/`
- `qwen3.8-27b-local-4bit-verification-2/` — **the second run of local
  qwen 3.8 27b 4 bit for verification**

## 1. Scope and ground-truth precedence

This grading covers every retained authored artifact in each submission
directory, not only the main report. The comparison's runtime, cost, and token
metadata do not affect the technical-quality score.

Per the grading instruction, the Sol Ultra result is treated as ground truth.
Where its chronological progress notes and completed findings differ, source
precedence is:

1. `gpt-5.6-sol-ultra/docs/reverse_engineering_report.md`
2. `gpt-5.6-sol-ultra/docs/report_coverage_checklist.md`
3. the completed focused Sol Ultra reports
4. Sol Ultra progress notes

The original `PROMPT.md` determines relevance. Findings outside the prompt
receive novelty credit only when they materially improve pairing, transport,
recording recovery, or independent-client safety.

## 2. Scoring method

The approved base rubric is worth 100 points:

| Area | Weight |
|---|---:|
| Technical reconstruction | 70 |
| Reverse-engineering rigor | 18 |
| Reporting and implementation utility | 12 |

Each weighted leaf was decomposed into factual atoms. Atom scoring:

- `+1`: correct, explicit, and adequately supported where evidence is required;
- `+0.5`: correct core result with one required qualifier or detail missing;
- `0`: absent, too vague, or unsupported;
- `-1`: explicitly contradicts the assumed ground truth or invents a field,
  constant, or behavior.

Each subsection is floored at zero and capped at its weight. Repeated claims
score once. Evidence credit requires a traceable artifact plus a
symbol/function, offset, disassembly excerpt, or reproducible test.

Additional approved penalties:

- `-2` per fabricated or materially mismatched evidence claim;
- `-3` per unsafe unsupported destructive instruction.

No submission received the destructive-instruction penalty: several discuss
erase operations incorrectly or incompletely, but they also warn that live
validation is required.

Verified novelty is reported separately, up to `+5`, so a late-discovered
criterion does not reduce another submission's base score.

The objective scoring materials are:

- [`GRADING_RUBRIC.md`](GRADING_RUBRIC.md): the complete 100-checkpoint
  hierarchy, expected result, and deduction trigger for every checkpoint;
- [`GRADING_LEDGER.md`](GRADING_LEDGER.md): all 100 checkpoint scores for all
  six submissions, subsection floors, penalties, novelty awards, and
  non-full-credit rationales.

The totals below are calculated from that ledger.

## 3. Results

| Rank | Submission | Technical /70 | Rigor /18 | Reporting /12 | Penalty | Base /100 | Novelty /5 | Adjusted /105 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | GPT-5.6 Luna xhigh | 59.5 | 16.5 | 11.5 | 0 | **87.5** | **+5** | **92.5** |
| 2 | Qwen 3.8 2.4T OpenRouter | 53.0 | 13.5 | 8.5 | 0 | **75.0** | **+1** | **76.0** |
| 3 | GLM 5.3 OpenRouter max | 50.0 | 11.0 | 10.0 | 0 | **71.0** | 0 | **71.0** |
| 4 | Stealth Ox Alpha OpenRouter max | 25.0 | 10.0 | 4.0 | -6 | **33.0** | **+1** | **34.0** |
| 5 | the second run of local qwen 3.8 27b 4 bit for verification | 9.0 | 7.5 | 1.5 | -8 | **10.0** | **+1** | **11.0** |
| 6 | Qwen 3.8 27B local 4-bit | 7.0 | 5.5 | 3.5 | -6 | **10.0** | 0 | **10.0** |

The verified-novelty point breaks a base-score tie between the two local
Qwen 27B runs.

## 4. Technical reconstruction breakdown

| Technical area | Weight | Luna | Qwen 2.4T | GLM 5.3 | Ox Alpha | Qwen 27B | Qwen 27B V2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| End-to-end representation | 14 | 14.0 | 12.0 | 9.5 | 8.0 | 6.0 | 4.5 |
| Codec reconstruction | 18 | 17.0 | 14.5 | 16.5 | 7.0 | 0 | 0 |
| Protocol and framing | 15 | 10.5 | 11.0 | 10.5 | 4.0 | 0 | 0 |
| Transfer, multipart, integrity | 9 | 7.5 | 7.5 | 6.5 | 0.5 | 0 | 2.0 |
| Crypto, registration, persistence | 14 | 10.5 | 8.0 | 7.0 | 5.5 | 1.0 | 2.5 |
| **Total** | **70** | **59.5** | **53.0** | **50.0** | **25.0** | **7.0** | **9.0** |

### 4.1 GPT-5.6 Luna xhigh

Main report:
`gpt-5.6-luna-xhigh/docs/reverse_engineering_report.md`

Supplementary protocol report:
`gpt-5.6-luna-xhigh/docs/telesto_protocol.md`

#### What it got right

- Correctly recovered both audio forms, the compressed record layout, MSB-first
  bit order, bounded-unary/raw escape, signed mapping, two wrapping
  integrations, and final shift. Its decoder pseudocode has the correct
  leading-bit polarity: `1` encodes a zero second difference.
- Correctly treated the source sample rate as a dynamic record field and the
  shipping value as unknown. The public-firmware discussion remained an
  explicitly qualified inference.
- Preserved the essential physical-storage boundary: Haversine receives a
  plaintext logical collection, while transparent flash encryption remains
  unknown.
- Recovered the complete-object transfer boundary, Telesto request/response,
  collection virtual addresses, multipart handling, and the
  `TransferComplete` output path.
- Gave strong key-management and persistence evidence: registration is a
  plaintext UID/fingerprint/timestamp record, decoding is keyless, and cached
  state contains no recording key.
- The supplementary Telesto report is substantially more useful than a
  section-presence answer: it documents controller state, cancellation,
  virtual addresses, system input, and operation inventory.

#### Principal deductions

1. **Missed one accepted collection-envelope form.**  
   Main-report lines 163-175 document only the `u24be` and
   `ff + u16le` forms. The accepted `u32le totalLength` form selected when byte
   3 is zero is absent.

2. **Overstated native parser safety.**  
   The same section says PPCommon validates declared record lengths and bounds.
   Sol Ultra establishes that the native parser can read short headers without
   prechecking and can accept a final TLV overshoot.

3. **Wrong stored-range wording in the supplementary report.**  
   `telesto_protocol.md:472` calls the range inclusive. Ground truth is the
   modulo-`2^16` half-open interval `[start, end)`.

4. **Overstated BLE encryption.**  
   Main-report line 248 says BLE link encryption/bonding is `yes/OS-level`.
   The correct answer is platform-controlled and unknown for a particular
   session without firmware permissions or an HCI/SMP trace.

5. **No executable decoder/native-vector validation.**  
   The pseudocode is strong, but no runnable decoder, malformed-input suite, or
   exact-native test vectors were delivered.

6. **Registration byte serialization was not reconstructed to Sol's level.**  
   The struct and size are correct, but the exact version-1 offsets, 145-byte
   length-prefixed program object, operation `5`, and fingerprint algorithm
   were not all reported.

### 4.2 Qwen 3.8 2.4T OpenRouter

Main report:
`qwen3.8-2.4t-openrouter/docs/reverse_engineering_report.md`

Worklog:
`qwen3.8-2.4t-openrouter/docs/worklog.md`

#### What it got right

- Acquired the main and companion cinterop KLIBs and used their native objects,
  metadata, IR, DWARF/disassembly, and exact object offsets.
- Correctly recovered audio record layouts, configuration nibbles, bit count,
  sample rate, MSB-first ordering, two integrations, output shift, and PCM
  representation.
- Correctly reconstructed the 13-byte request, 12-byte response, collection
  addresses, three accepted outer-envelope families, transfer phases, and
  whole-collection buffering.
- Correctly found no shared secret, no decoder dependency on registration
  state, and no key in ordinary cached state.
- Its report is exceptionally traceable: most major claims identify an object,
  function, offset, or IR line.

#### Principal deductions

1. **The decoder pseudocode reverses the bit-code polarity.**  
   Lines 87-103 say a first bit of `0` means a zero residual and a first bit of
   `1` enters the unary code. The shipped codec does the reverse:
   first bit `1` means zero; first bit `0` begins bounded unary/escape decoding.
   This makes the supplied decoder algorithm wire-incompatible despite the
   otherwise-correct record and predictor reconstruction.

2. **“Lossless” is overclaimed.**  
   The executive answer says both forms decode losslessly to the same PCM.
   Later text correctly notes that nonzero low-nibble shifts quantize the
   output. The executive claim is therefore internally inconsistent.

3. **Physical flash encryption is answered too strongly.**  
   Lines 28 and 183 answer storage-at-rest encryption as `no`. The supported
   result is: no Haversine-managed cipher, but transparent physical-flash
   encryption remains unknown.

4. **`TelestoResponse.info` is assigned an unsupported meaning.**  
   Line 142 offers `transferEndIndex` as an example. The reviewed collection
   path does not establish the semantic meaning of `info`; the transfer result's
   end index is separate state.

5. **Several transport details are overgeneralized or wrong.**  
   The report treats outgoing writes as universally write-with-response and
   interprets acknowledgements too broadly. Exact iOS bulk transfer normally
   uses `.withoutResponse`, with a `.withResponse` write potentially inserted
   for pacing.

6. **The first envelope is described imprecisely.**  
   It is a four-byte `u32le totalLength` whose high byte is zero, not merely a
   three-byte legacy LE24 field.

7. **No executable decoder or native test vectors were delivered.**

### 4.3 GLM 5.3 OpenRouter max

Main report:
`glm-5.3-openrouter-max/docs/reverse_engineering_report.md`

Retained disassembly:
`glm-5.3-openrouter-max/evidence/disasm/`

#### What it got right

- The codec reconstruction is excellent. It correctly identifies the two
  record types and reconstructs the exact leading-bit polarity,
  bounded-unary/escape code, sign mapping, modulo window, two integrators,
  final shift, bit-count termination, and MSB-first order.
- It documents all three accepted outer collection envelopes correctly.
- It supplies concrete, retained disassembly excerpts for the parser, codec,
  Telesto controller, and transfer operation.
- It correctly identifies the dynamic sample-rate field, output PCM form, lack
  of application-layer recording encryption, and absence of a registration
  secret.

#### Principal deductions

1. **It did not recover the published iOS companion native archives.**  
   The run relies principally on Android AAR/debug native libraries and an
   assertion that shared source paths make them representative. This is useful
   corroboration but weaker than direct device/simulator PPCommon and satellite
   archive recovery.

2. **Incoming collection framing is conflated with an outgoing helper.**  
   Lines 58 and 198-200 attach `TelestoLengthPrefixedData`/four-byte framing and
   20-byte writes to the recording receive path. The ring's collection data
   bytes are streamed directly and bounded by `TelestoResponse.length`; GATT
   notification boundaries have no extra Haversine header.

3. **The Telesto response is left unnecessarily unresolved.**  
   Lines 337 and 367 say the 12-byte field layout remains unknown. Ground truth
   directly establishes `{u32le error, u32le info, u32le length}`.

4. **Operation and range semantics are incomplete.**  
   Operation type `5` is omitted; the implementation's roughly-`0x200` guard is
   presented as a 512-slot ring rather than a client assertion; end-exclusive
   range and resume distinctions are not fully reported.

5. **Physical at-rest encryption is overclaimed.**  
   Lines 37-39 and 239 say “no evidence—almost certainly no.” Haversine proves
   only that the logical object returned through Telesto is plaintext and
   self-contained. Firmware/hardware flash encryption remains unknown.

6. **Registration serialization remains incomplete and partly misordered.**  
   The report knows the size and non-secret fields but explicitly leaves the
   exact split unresolved and does not recover the 145-byte length-prefixed
   operation-5 program object.

7. **No executable decoder or exact-native test suite was delivered.**

### 4.4 Stealth Ox Alpha OpenRouter max

Main report:
`stealth-ox-alpha-openrouter-max/docs/reverse_engineering_report.md`

Progress log:
`stealth-ox-alpha-openrouter-max/docs/progress.md`

#### What it got right

- It acquired the exact device and simulator KLIBs plus both published
  companion cinterop archives and correctly recognized the top-level KLIBs as
  thin Kotlin/Native glue over the retained native implementations.
- It recovered most of the DD-Rice mathematics correctly: MSB-first bit order,
  the leading-one zero code, bounded unary and raw escape, sign mapping, two
  wrapping integrations, output shift, and nonzero-shift quantization.
- It correctly preserved the dynamic sample-rate boundary, complete-collection
  transfer model, mono 16-bit app output, multipart concatenation concept, and
  post-`TransferComplete` DC removal/resampling.
- It recovered all three accepted outer collection envelopes and supplied a
  strong symbol/offset evidence index and end-to-end call chain.
- It correctly found no Haversine recording cipher or registration-derived
  decoder secret, retained physical at-rest encryption as unknown in its crypto
  table, and grounded the negative conclusion in both a positive decode path
  and targeted primitive/import scans.

#### Principal deductions

1. **The five audio-adjacent TLV IDs are shifted into an incompatible legacy
   map.**
   The report assigns compressed audio to `0x53`, uncompressed audio to `0x54`,
   and multipart metadata to `0x51`. The target library uses `0x50`
   uncompressed audio, `0x51` compressed audio, `0x52` multipart metadata,
   `0x53` button sequence, and `0x54` lifetime collection count.

2. **The compressed and uncompressed wire layouts are consequently wrong.**
   The actual compressed payload begins immediately with config, followed by
   `u32le compressedBitCount`, `u32le sampleRateHz`, and the bitstream at
   payload offset 9. The report inserts a fictitious two-byte reserved field
   and begins the stream at 11. Both audio TLVs use a 32-bit payload length;
   `0x54` is not a long-form PCM record.

3. **Telesto control and data framing are materially conflated.**
   A request is a packed 13-byte control write and the response is a packed
   12-byte control notification. Data bytes are accumulated directly according
   to `response.length`. The report instead describes a 12-byte request, a
   24-byte request struct, a 12-byte Data-channel header, and per-chunk
   application acknowledgements.

4. **Enumeration cannot be implemented from the supplied protocol section.**
   The report leaves the stored-range and advertising addresses numerically
   unresolved, omits half-open modulo-range semantics, and does not recover the
   exact response fields or operation table.

5. **Registration serialization is misread.**
   The logical fields are `u32 fingerprint`, `u32 timestamp`, and `uid[129]`;
   serialized version 1 is 141 bytes and becomes a 145-byte length-prefixed
   operation-5 object. The report instead gives `{u32 version, u64 timestamp,
   uid[129]}`, omits the fingerprint from that claimed layout, and does not
   recover the program address/frame. It also presents the isolated `00` write
   as a proven bond trigger although its exact wire purpose remains unknown.

6. **Integrity and confidence claims are too strong.**
   It treats pacing state as per-chunk acknowledgement, states that record
   lengths exactly protect the container despite native bounds gaps, declares
   BLE encryption active for the reviewed session, and describes the logical
   collection as byte-identical flash storage.

7. **No runnable decoder, exact wire vector, or native regression harness was
   delivered.**
   The core entropy algorithm is useful, but the surrounding record parser is
   wire-incompatible and was not independently tested.

#### Additional penalty: `-6`

Three materially mismatched evidence uses received `-2` each:

1. `PPParsing`/`PPCollection` evidence was presented as proof of the shifted
   `0x51`/`0x53`/`0x54` record map and fictitious audio headers;
2. `TelestoController`/`TelestoOperation` evidence was presented as proof of a
   Data-channel header and per-chunk acknowledgements rather than the packed
   control request/response;
3. `PPRingApplicationData` and app pairing evidence was presented as proof of
   an incompatible registration layout and a definite bond-trigger meaning.

No destructive-instruction penalty was applied because the report explicitly
requires firmware-side observation before any erase operation.

### 4.5 Qwen 3.8 27B local 4-bit

Main report:
`qwen3.8-27b-local-4bit/docs/reverse_engineering_report.md`

#### What it got right

- Found the broad result: collections can contain uncompressed PCM or custom
  DD-Rice audio, Haversine emits `ShortArray`, application recording encryption
  is absent, and registration does not create a recording secret.
- Recovered several important classes, functions, UUIDs, and the high-level
  path to `TransferComplete`.
- Supplied all ten requested report sections and a useful evidence table.

#### Principal technical failures

1. **It mistakes the app's 16 kHz output target for the ring source rate.**
   This is one of the prompt's explicitly forbidden reasoning errors.

2. **It misidentifies type `0x52` as compressed audio.**
   `0x52` is multipart metadata; compressed audio is `0x51`.

3. **The compressed record and codec are not reconstructed.**
   The claimed 13-byte decoder header is fictitious, the supplied loop has only
   one integration, the bounded-unary/escape code is absent, and the report
   incorrectly says the algorithm is Xiph Speex `dd_rice.c`.

4. **It conflates protocol layers.**
   It puts a four-byte length prefix on every incoming GATT notification,
   gives a 10-byte/`hasData` command instead of the 13-byte Telesto request,
   and never recovers the 12-byte response fields.

5. **Several virtual addresses are wrong.**
   Stored collection indexes are at `0x40030005`, not `0x40020005`; collection
   addresses use bitwise OR with the `uint16` index, not an unknown byte stride.

6. **The collection envelope/TLV model is wrong.**
   The report treats the outer length as a per-record header, mixes endian
   descriptions, invents a type-4 audio header, and does not recover the three
   accepted envelope forms.

7. **Registration data is materially misidentified.**
   It conflates `PPFingerprintFromRawSensorData` with the UID fingerprint and
   claims the 141-byte record contains a 16-bit user hash plus a 128-bit sensor
   fingerprint. The actual serialized fields are a 32-bit UID fingerprint,
   32-bit Unix timestamp, and 129-byte UID, preceded by version `1`.

8. **Multipart and buffer facts are misstated.**
   The initial 100,000-sample allocation is described as a part-size cap;
   multipart parts do not all have the same current collection index.

9. **Physical flash and BLE security are overclaimed.**
   The report says transferred bytes are byte-identical to flash and BLE
   encryption is active. Both remain firmware/session-dependent boundaries.

10. **Independent-client instructions are not implementable.**
    They depend on the wrong request, response, addresses, framing, record tags,
    and decoder, and suggest generic erase is the recording-deletion mechanism
    without establishing safe semantics.

#### Additional penalty: `-6`

Three materially mismatched evidence uses received `-2` each:

1. app-side 16 kHz constants were presented as proof of the ring's native rate;
2. `DDRice*` symbol names were presented as proof of Xiph Speex provenance;
3. an unrelated raw-sensor fingerprint routine was presented as a field and
   indexing mechanism of the UID registration record.

### 4.6 the second run of local qwen 3.8 27b 4 bit for verification

Main report:
`qwen3.8-27b-local-4bit-verification-2/docs/reverse_engineering_report.md`

Progress log:
`qwen3.8-27b-local-4bit-verification-2/docs/progress.md`

Run metadata:
`qwen3.8-27b-local-4bit-verification-2/docs/run_metadata.md`

#### What it got right

- It acquired the exact device and simulator KLIBs and all four companion
  cinterop KLIBs. Independent SHA-256 checks match the frozen Sol Ultra
  artifacts.
- It correctly recognized that the top-level KLIBs contain Kotlin/Native
  IR/metadata while PPCommon and HaversineSatelliteLibrary carry the native
  parser, codec, and transfer objects.
- It found the broad keyless path from a complete collection through
  `PPCollection_createFromBinaryData`, `GSParseRecordsInRawData`,
  `PPCollection_createAudioTimeline`, multipart handling, and
  `TransferComplete(ShortArray, sampleRate, ...)`.
- It recovered the two integrations and final shift in the DD-Rice decoder,
  the leading-one zero code, the direct raw-copy branch, dynamic sample-rate
  propagation, and the lack of a Haversine recording key.
- It recovered the logical registration fields
  `{u32 fingerprint, u32 timestamp, uid[129]}` and correctly treated the
  fingerprint as an unkeyed identifier rather than a recording secret.
- It independently identified the alternate
  `HaversineReadLastAudioSamplesOperation` path into the same
  PPCollection/DD-Rice decoder. This receives the established `+1` verified
  novelty award.

#### Principal technical failures

1. **The final record map changes correct byte values into wrong decimal
   tags.**
   The progress log initially lists accepted decimal values `80..84`, which
   correspond to `0x50..0x54`, but the final report calls raw audio,
   compressed audio, and multipart metadata codes `40`, `41`, and `42`.
   PPCommon actually uses `0x50`, `0x51`, and `0x52`.

2. **The compressed header and codec are materially incompatible.**
   The report invents a stored sample count and an eight-byte predictor state.
   The actual nine-byte payload header is
   `{config, u32le compressedBitCount, u32le sampleRateHz}` followed by an
   MSB-first bitstream. It also describes ordinary adaptive Rice
   quotient/remainder coding instead of the shipped bounded-unary/signed-small
   code with literal escape, calls every configuration lossless, and mistakes
   an allocation ceiling for a wire part limit. No exact pseudocode or
   executable validation is supplied.

3. **Telesto and collection framing are misread.**
   A request is the packed 13-byte
   `{u8 type, u32le address, u32le offset, u32le length}` structure, not a
   64-bit-address request. Incoming collection Data has no four-byte
   `TelestoLengthPrefixedData` wrapper. The transfer begins from the stored
   half-open range at `0x40030005`, not a single collection count; the
   implementation cap is `0xA0000`, not `0x10000`. The `u32le totalLength`
   envelope and `ff + u16le` envelope are also reported with incompatible
   widths/endianness.

4. **Sample-rate, BLE, physical-storage, and firmware boundaries are
   overclaimed.**
   Incidental `8000`/`32000` byte occurrences do not prove an 8 kHz microphone
   rate. The source rate remains the captured record's dynamic field. The
   client also cannot prove raw physical-flash representation, transparent
   flash encryption, or the BLE security state of a particular connection.
   The public image's validated SUOTA header declares no encryption; a reboot
   reason containing `XOR` does not prove that the downloaded image is
   XOR-obfuscated.

5. **Registration serialization and persistence are incomplete or wrong.**
   Version 1 is a four-byte little-endian value, not one byte. The 141-byte
   record becomes a 145-byte length-prefixed operation-5 object sent to
   `0x40000000`. Exact UserDefaults/SharedPreferences state, OS-owned bond
   keys, cache-clearing implications, no-user semantics, and the unresolved
   one-byte `00` write are not recovered.

6. **The requested implementation and evidence deliverables are incomplete.**
   The report has seven sections rather than ten functional equivalents. It
   lacks the layered end-to-end pipeline, correct core wire tables, exact
   decoder pseudocode, dedicated claim/evidence map, remaining-unknowns table,
   independent-client/safe-delete guidance, exact wire examples, and a
   runnable native-validated decoder suite.

#### Additional penalty: `-8`

Four distinct materially mismatched evidence uses receive `-2` each:

1. PPParsing/PPCollection/DD-Rice evidence for the wrong tags, compressed
   header, and generic Rice model;
2. Telesto controller/operation evidence for the 64-bit request, incoming Data
   prefix, count-based enumeration, and wrong cap;
3. registration serializer/programming evidence for the one-byte version and
   unprefixed operation-2 record;
4. firmware constants/reboot text for the 8 kHz production-rate and
   XOR-obfuscation claims.

No destructive-instruction penalty applies because the report does not
prescribe collection erase as a safe deletion method.

## 5. Reverse-engineering rigor breakdown

| Rigor area | Weight | Luna | Qwen 2.4T | GLM 5.3 | Ox Alpha | Qwen 27B | Qwen 27B V2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Artifact acquisition/inventory | 3 | 3.0 | 3.0 | 2.0 | 3.0 | 2.0 | 3.0 |
| `TransferComplete` call chain | 5 | 4.5 | 4.5 | 4.5 | 4.5 | 3.5 | 3.5 |
| Cross-artifact verification | 3 | 3.0 | 2.5 | 0 | 2.5 | 0 | 1.0 |
| Reproducibility/executable validation | 4 | 3.0 | 1.0 | 3.0 | 0 | 0 | 0 |
| Falsification/confidence calibration | 3 | 3.0 | 2.5 | 1.5 | 0 | 0 | 0 |
| **Total** | **18** | **16.5** | **13.5** | **11.0** | **10.0** | **5.5** | **7.5** |

No non-Sol submission delivered a runnable independent decoder validated
against the exact native object. GLM retained the strongest raw disassembly
set; Luna supplied the strongest correct textual reconstruction and
cross-artifact audit; Qwen 2.4T supplied excellent evidence coordinates but an
incorrect executable algorithm; Ox Alpha acquired the right native artifacts
and cited them densely but repeatedly misinterpreted their wire structures.
The verification run acquired more of the right evidence than the earlier
local Qwen run but still mapped it onto incompatible codec and Telesto models;
both local Qwen runs' cited evidence frequently failed to support their final
interpretations.

## 6. Reporting and implementation-utility breakdown

| Reporting area | Weight | Luna | Qwen 2.4T | GLM 5.3 | Ox Alpha | Qwen 27B | Qwen 27B V2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Required-output coverage | 2 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 0 |
| Technical presentation | 3 | 3.0 | 1.0 | 2.5 | 0 | 0 | 0 |
| Claim/evidence traceability | 3 | 3.0 | 3.0 | 3.0 | 2.0 | 1.5 | 1.5 |
| Independent-client utility/safety | 3 | 3.0 | 2.5 | 2.0 | 0 | 0 | 0 |
| Internal consistency | 1 | 0.5 | 0 | 0.5 | 0 | 0 | 0 |
| **Total** | **12** | **11.5** | **8.5** | **10.0** | **4.0** | **3.5** | **1.5** |

The five earlier reports followed the requested ten-section structure. The
verification run did not: it omitted several required functional sections, so
its reporting score also reflects incomplete coverage rather than correctness
alone.

## 7. Verified novelty audit

Novelty was checked against the entire retained Sol Ultra corpus, not only its
main report. Each accepted claim was independently verified in the original
workspace.

### 7.1 Luna: `+5`

#### A. Firmware-dependent registration and post-pair wipe policy: `+2`

Luna reports that:

- firmware older than `3.62.0` requires UID application-data programming before
  recordings transfer;
- firmware `>=3.62.0` skips that programming;
- the newer app's successful pairing path explicitly calls
  `eraseCollections()` to wipe possible factory recordings;
- a separate read-only client does not advance the official app's local cursor,
  so the official app may later redownload the same collections.

Verification:

- `haversine_reverse2/external-mobileapp/experimental/src/commonMain/kotlin/coredevices/ring/service/RingPairing.kt:28-59`
- `haversine_reverse2/external-mobileapp/libindex/src/commonMain/kotlin/coredevices/libindex/device/IndexPairing.kt:128-148`
- the app's separate local collection-index storage and Haversine READ-only
  transfer path

These findings materially refine pairing and independent-client safety and are
not stated in the Sol Ultra corpus.

#### B. Firmware image contains structured 8 kHz and 16 kHz candidates: `+1`

Luna carefully reports—not overclaims—that the public firmware image includes
structured configuration values `8000` and `16000`, while the connection to
the recording record's runtime field remains unresolved.

Independent binary verification found:

- `8000` (`40 1f 00 00`) at firmware offset `0x58f8`;
- `16000` (`80 3e 00 00`) at firmware offset `0x5910`;
- both occur in the same structured configuration table.

This is useful narrowing evidence absent from Sol Ultra, but it does not change
the ground-truth conclusion that the production recording rate is unknown.

#### C. Direct “read last audio” operation reaches the same decoder: `+1`

Luna identifies `HaversineReadLastAudioSamplesOperation` as an alternate
operation that reads collections and directly invokes
`PPCollection_createFromBinaryData` and `PPCollection_createAudioTimeline`.
Sol Ultra inventories the object but does not report this operational finding.

Verification:

- relocations in `haversine_reverse2/lastaudio-reloc.txt` at `0x4d8/0x4f4`
  and `0x828/0x844`;
- `HaversineReadLastAudioSamplesResult` cinterop layout in
  `haversine_reverse2/work-hsl-meta.txt`.

#### D. Full seven-byte System Input wire structure/type map: `+1`

Luna documents the fixed seven-byte System Input structure, interrupt bitfields,
and type values `0..16`. Sol Ultra names the characteristic and uses a small
subset of values in firmware update analysis, but does not reconstruct the full
wire structure or enumeration.

Verification:

- `haversine_reverse2/work-hsl-meta.txt:1870-2073`
- `haversine_reverse2/work-hsl-meta.txt:4413-4509`

This is ancillary to recording download but useful to a complete independent
phone-side protocol implementation.

### 7.2 Qwen 2.4T, Ox Alpha, and Qwen 27B verification run 2: `+1` each

Qwen 2.4T independently reports the alternate
`HaversineReadLastAudioSamplesOperation` result/path and its sample/rate/index
fields. It receives the same `+1` as Luna for finding C above.

Ox Alpha also places `readLastAudioSamples()` on the alternate collection-read
and PPCommon timeline path. Independent verification in its original
`HaversineReadLastAudioSamplesOperation.o` disassembly confirms direct
relocations to `PPCollection_createFromBinaryData` and
`PPCollection_createAudioTimeline` at `0x4d8/0x4f4` and `0x828/0x844`. It
therefore receives the same `+1`.

The second local Qwen verification run reports the same alternate operation
and direct PPCollection/timeline path. Independent checks against its exact
retained source workspace found both imports and the same four relocation
pairs at `0x4d8/0x4f4` and `0x828/0x844`. It therefore receives the same
`+1`. Its 14-flag System Input description lacks the seven-byte wire structure
and complete type map, and its firmware-rate claim overreaches the evidence;
neither receives additional novelty credit.

### 7.3 GLM 5.3 and Qwen 27B: `+0`

No reported claim both:

1. added a material fact absent from Sol Ultra, and
2. survived independent verification without contradicting ground truth.

Minor details such as internal DD-Rice statistics buckets were not awarded:
they do not affect decoding, protocol compatibility, pairing, or client safety.

### 7.4 Ox Alpha satellite-event claim: no additional credit

Ox Alpha's satellite-event parser was also checked as a possible additional
novelty because it is absent from Sol Ultra. The original-run
`PPSatelliteEvents.o` disassembly confirms a three-byte prefix followed by a
code-dependent argument, but contradicts the report's claim that the leading
`u16le` is a size: the parser never uses it for framing, and
`PPSatelliteEvent_description` converts it to time using `0.625 ms` ticks. The
parser advances by `3 + argumentSizeForCode(code)`. Because the reported field
semantics were wrong, no additional novelty point was awarded.

## 8. Decisive comparison matrix

| Ground-truth requirement | Luna | Qwen 2.4T | GLM 5.3 | Ox Alpha | Qwen 27B | Qwen 27B V2 |
|---|---|---|---|---|---|---|
| Production sample rate remains unknown | Correct | Correct | Correct | Correct | **Wrong: 16 kHz asserted** | **Wrong: 8 kHz inferred** |
| Physical flash encryption remains unknown | Correct | **Overclaimed no** | **Overclaimed no** | Mixed: table correct, storage wording overclaimed | **Overclaimed / contradictory** | **Overclaimed / conflated with firmware XOR** |
| Both `0x50` PCM and `0x51` DD-Rice | Correct | Correct, plus unsupported legacy type | Correct | **Wrong: `0x53`/`0x54`** | **Mislabels `0x52` as audio** | **Wrong decimal `40`/`41` tags** |
| Implementable DD-Rice code | Correct | **Leading bit inverted** | Correct | **Core math correct; wire header wrong** | **Not reconstructed** | **Generic Rice model; header wrong** |
| All three outer envelopes | **Only two** | Mostly correct | Correct | Correct | **Wrong model** | **One correct; two incompatible** |
| Exact 13-byte request / 12-byte response | Correct | Mostly correct | Partial | **Wrong request/data framing** | **Wrong request; response unresolved** | **Wrong request; response correct** |
| GATT chunks are not framed audio/Telesto packets | Correct | Mostly correct | **Length-prefix conflation** | **Data-header/ACK conflation** | **Length-prefix conflation** | **Length-prefix conflation** |
| Registration record is non-secret | Correct | Correct but incomplete | Correct but incomplete | Conclusion correct, **layout wrong** | Conclusion correct, **layout wrong** | Conclusion correct, **wire/program wrong** |
| Native parser validation gaps disclosed | No | No | No | No | No | No |
| Safe delete/ack remains unknown | Correct | Correct | Correct | Correct | **Generic erase overclaimed** | Not established |
| Executable native-validated decoder | No | No | No | No | No | No |

## 9. Efficiency context

Quality scores are intentionally not adjusted for time, price, tokens, or
harness. For context only:

| Submission | Active elapsed | Cost / plan metadata | Base points per active hour |
|---|---:|---|---:|
| GLM 5.3 OpenRouter max | 23m 08s | US$3.88 | 184.2 |
| GPT-5.6 Luna xhigh | 33m 42s | 1% of GPT Pro Lite 5×, user-reported | 155.8 |
| Stealth Ox Alpha OpenRouter max | 18m 27s | US$3.16 | 107.3 |
| Qwen 3.8 2.4T OpenRouter | 1h 20m 31s | US$5.98 | 55.9 |
| the second run of local qwen 3.8 27b 4 bit for verification | 7h 31m 48s | local inference; unmeasured | 1.3 |
| Qwen 3.8 27B local 4-bit | 9h 43m 54s | local inference; unmeasured | 1.0 |

This derived rate is not a controlled model-speed measurement. The runs used
different models, harnesses, caching, hardware, and accounting regimes.
The verification run's active elapsed value sums three successful research
windows and excludes four zero-usage terminated replies plus one zero-usage
aborted reply; its full accounting is in the retained run metadata.
Among the three directly priced OpenRouter runs:

- GLM: about 18.3 base points per recorded dollar;
- Qwen 2.4T: about 12.5 base points per recorded dollar;
- Ox Alpha: about 10.4 base points per recorded dollar.

## 10. Overall assessment

**Luna is the clear strongest non-ground-truth submission.** It reconstructs
the central codec correctly, preserves the important unknown boundaries, and
adds verified app/firmware and phone-protocol findings. Its main weaknesses are
the missing third collection envelope, incorrect parser-bounds claim, and a few
transport/security overstatements.

**Qwen 2.4T is the strongest protocol-forensics report but not a usable decoder
specification.** Its evidence density and Telesto work are excellent, yet the
single most important codec branch is inverted. An implementer following its
pseudocode would fail on real compressed collections.

**GLM solves the codec accurately and efficiently but leaves too much of the
iOS-specific protocol and registration path unresolved.** Its dependence on
Android native artifacts and its incoming-framing/at-rest mistakes keep it
below Qwen 2.4T overall despite the better decoder.

**Ox Alpha found the correct native artifacts and most of the codec mathematics
very quickly, but mapped those findings onto the wrong wire structures.** Its
shifted audio/multipart record IDs, fictitious compressed header, Telesto
Data-channel header/ack model, and registration layout make its independent
client instructions unusable without substantial correction. Its acquisition,
call-chain, and evidence work nevertheless place it clearly above both local
Qwen 27B runs.

**The second run of local qwen 3.8 27b 4 bit for verification acquires the
right native evidence but still maps it onto the wrong wire protocol.** It
improves artifact acquisition, multipart coverage, and the alternate read-last
path over the first local run. Its decimal audio tags, fictitious compressed
header, generic Rice model, 64-bit Telesto request, Data prefix, source-rate
inference, and incomplete report structure nevertheless keep its base score at
10. The verified alternate-decoder path gives it an adjusted score of 11 and
fifth place.

**The first Qwen 27B run reaches the broad headline but is technically
unreliable for implementation.** It repeatedly converts surface clues into
false concrete structures, including the sample rate, audio tags, decoder
format, Telesto request/framing, collection addresses, and registration
record. Its report would require substantial re-reverse-engineering before it
could guide a client.
