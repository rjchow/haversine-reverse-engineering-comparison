# Haversine reverse-engineering benchmark grading

Date: 2026-08-21  
Ground truth: `gpt-5.6-sol-ultra/`  
Submissions graded:

- `gpt-5.6-luna-xhigh/`
- `qwen3.8-2.4t-openrouter/`
- `glm-5.3-openrouter-max/`
- `qwen3.8-27b-local-4bit/`

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

## 3. Results

| Rank | Submission | Technical /70 | Rigor /18 | Reporting /12 | Penalty | Base /100 | Novelty /5 | Adjusted /105 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | GPT-5.6 Luna xhigh | 60.5 | 16.0 | 11.5 | 0 | **88.0** | **+5** | **93.0** |
| 2 | Qwen 3.8 2.4T OpenRouter | 50.0 | 13.5 | 10.5 | 0 | **74.0** | **+1** | **75.0** |
| 3 | GLM 5.3 OpenRouter max | 50.0 | 10.0 | 9.5 | 0 | **69.5** | 0 | **69.5** |
| 4 | Qwen 3.8 27B local 4-bit | 20.5 | 7.5 | 6.0 | -6 | **28.0** | 0 | **28.0** |

The ranking is unchanged by novelty credit.

## 4. Technical reconstruction breakdown

| Technical area | Weight | Luna | Qwen 2.4T | GLM 5.3 | Qwen 27B |
|---|---:|---:|---:|---:|---:|
| End-to-end representation | 14 | 14.0 | 12.0 | 10.0 | 6.5 |
| Codec reconstruction | 18 | 17.0 | 12.5 | 17.0 | 3.0 |
| Protocol and framing | 15 | 10.5 | 11.5 | 10.5 | 3.0 |
| Transfer, multipart, integrity | 9 | 8.0 | 7.0 | 6.0 | 3.5 |
| Crypto, registration, persistence | 14 | 11.0 | 7.0 | 6.5 | 4.5 |
| **Total** | **70** | **60.5** | **50.0** | **50.0** | **20.5** |

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

### 4.4 Qwen 3.8 27B local 4-bit

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

## 5. Reverse-engineering rigor breakdown

| Rigor area | Weight | Luna | Qwen 2.4T | GLM 5.3 | Qwen 27B |
|---|---:|---:|---:|---:|---:|
| Artifact acquisition/inventory | 3 | 3.0 | 3.0 | 1.5 | 2.0 |
| `TransferComplete` call chain | 5 | 4.0 | 4.0 | 3.5 | 2.5 |
| Cross-artifact verification | 3 | 3.0 | 2.5 | 1.0 | 1.5 |
| Reproducibility/executable validation | 4 | 3.0 | 1.5 | 2.5 | 1.0 |
| Falsification/confidence calibration | 3 | 3.0 | 2.5 | 1.5 | 0.5 |
| **Total** | **18** | **16.0** | **13.5** | **10.0** | **7.5** |

No non-Sol submission delivered a runnable independent decoder validated
against the exact native object. GLM retained the strongest raw disassembly
set; Luna supplied the strongest correct textual reconstruction and
cross-artifact audit; Qwen 2.4T supplied excellent evidence coordinates but an
incorrect executable algorithm; Qwen 27B's cited evidence frequently did not
support its interpretation.

## 6. Reporting and implementation-utility breakdown

| Reporting area | Weight | Luna | Qwen 2.4T | GLM 5.3 | Qwen 27B |
|---|---:|---:|---:|---:|---:|
| Required-output coverage | 2 | 2.0 | 2.0 | 2.0 | 2.0 |
| Technical presentation | 3 | 3.0 | 3.0 | 3.0 | 1.5 |
| Claim/evidence traceability | 3 | 3.0 | 3.0 | 2.5 | 2.0 |
| Independent-client utility/safety | 3 | 3.0 | 2.0 | 1.5 | 0.5 |
| Internal consistency | 1 | 0.5 | 0.5 | 0.5 | 0 |
| **Total** | **12** | **11.5** | **10.5** | **9.5** | **6.0** |

All four reports followed the requested ten-section structure. The ranking is
therefore driven by correctness, evidence, and implementability rather than
mere report completeness.

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

### 7.2 Qwen 2.4T: `+1`

Qwen 2.4T independently reports the alternate
`HaversineReadLastAudioSamplesOperation` result/path and its sample/rate/index
fields. It receives the same `+1` as Luna for finding C above.

### 7.3 GLM 5.3 and Qwen 27B: `+0`

No reported claim both:

1. added a material fact absent from Sol Ultra, and
2. survived independent verification without contradicting ground truth.

Minor details such as internal DD-Rice statistics buckets were not awarded:
they do not affect decoding, protocol compatibility, pairing, or client safety.

## 8. Decisive comparison matrix

| Ground-truth requirement | Luna | Qwen 2.4T | GLM 5.3 | Qwen 27B |
|---|---|---|---|---|
| Production sample rate remains unknown | Correct | Correct | Correct | **Wrong: 16 kHz asserted** |
| Physical flash encryption remains unknown | Correct | **Overclaimed no** | **Overclaimed no** | **Overclaimed / contradictory** |
| Both `0x50` PCM and `0x51` DD-Rice | Correct | Correct, plus unsupported legacy type | Correct | **Mislabels `0x52` as audio** |
| Implementable DD-Rice code | Correct | **Leading bit inverted** | Correct | **Not reconstructed** |
| All three outer envelopes | **Only two** | Mostly correct | Correct | **Wrong model** |
| Exact 13-byte request / 12-byte response | Correct | Mostly correct | Partial | **Wrong request; response unresolved** |
| GATT chunks are not framed audio/Telesto packets | Correct | Mostly correct | **Length-prefix conflation** | **Length-prefix conflation** |
| Registration record is non-secret | Correct | Correct but incomplete | Correct but incomplete | Conclusion correct, **layout wrong** |
| Native parser validation gaps disclosed | No | No | No | No |
| Safe delete/ack remains unknown | Correct | Correct | Correct | **Generic erase overclaimed** |
| Executable native-validated decoder | No | No | No | No |

## 9. Efficiency context

Quality scores are intentionally not adjusted for time, price, tokens, or
harness. For context only:

| Submission | Active elapsed | Cost / plan metadata | Base points per active hour |
|---|---:|---|---:|
| GLM 5.3 OpenRouter max | 23m 08s | US$3.88 | 180.3 |
| GPT-5.6 Luna xhigh | 33m 42s | 1% of GPT Pro Lite 5×, user-reported | 156.7 |
| Qwen 3.8 2.4T OpenRouter | 1h 20m 31s | US$5.98 | 55.1 |
| Qwen 3.8 27B local 4-bit | 9h 43m 54s | local inference; unmeasured | 2.9 |

This derived rate is not a controlled model-speed measurement. The runs used
different models, harnesses, caching, hardware, and accounting regimes.
Among the two directly priced OpenRouter runs:

- GLM: about 17.9 base points per recorded dollar;
- Qwen 2.4T: about 12.4 base points per recorded dollar.

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

**Qwen 27B reaches the broad headline but is technically unreliable for
implementation.** It repeatedly converts surface clues into false concrete
structures, including the sample rate, audio tags, decoder format, Telesto
request/framing, collection addresses, and registration record. Its report
would require substantial re-reverse-engineering before it could guide a
client.

