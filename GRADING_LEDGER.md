# Haversine benchmark: atomic scoring ledger

Date: 2026-08-21

Rubric: `GRADING_RUBRIC.md`

Score notation:

- `1` = full credit
- `.5` = partial credit
- `0` = absent/unsupported
- `-1` = explicit contradiction or invented incompatible fact

Each subsection is floored at zero after its raw atom sum. The complete
criterion text and objective pass/fail conditions are in
`GRADING_RUBRIC.md`.

Abbreviations:

- **Luna**: `gpt-5.6-luna-xhigh`
- **Q2.4T**: `qwen3.8-2.4t-openrouter`
- **GLM**: `glm-5.3-openrouter-max`
- **Q27B**: `qwen3.8-27b-local-4bit`

## 1. Results

| Rank | Submission | Technical /70 | Rigor /18 | Reporting /12 | Penalty | Base /100 | Novelty /5 | Adjusted /105 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Luna | 59.5 | 16.5 | 11.5 | 0 | **87.5** | +5 | **92.5** |
| 2 | Q2.4T | 53.0 | 13.5 | 8.5 | 0 | **75.0** | +1 | **76.0** |
| 3 | GLM | 50.0 | 11.0 | 10.0 | 0 | **71.0** | 0 | **71.0** |
| 4 | Q27B | 7.0 | 5.5 | 3.5 | -6 | **10.0** | 0 | **10.0** |

## 2. T — Technical reconstruction

### T1. End-to-end recording representation

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| T1.01 | 1 | -1 | -1 | -1 |
| T1.02 | 1 | 1 | 1 | 1 |
| T1.03 | 1 | 1 | 1 | 1 |
| T1.04 | 1 | 1 | -1 | -1 |
| T1.05 | 1 | 1 | 1 | 1 |
| T1.06 | 1 | 1 | 1 | .5 |
| T1.07 | 1 | 1 | 1 | 1 |
| T1.08 | 1 | 1 | 1 | 1 |
| T1.09 | 1 | 1 | 1 | -1 |
| T1.10 | 1 | 1 | 1 | 1 |
| T1.11 | 1 | 1 | 1 | 1 |
| T1.12 | 1 | 1 | 1 | 1 |
| T1.13 | 1 | 1 | .5 | 0 |
| T1.14 | 1 | 1 | 1 | .5 |
| **Raw / final** | **14 / 14** | **12 / 12** | **9.5 / 9.5** | **6 / 6** |

### T2. Codec reconstruction

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| T2.01 | 1 | 1 | 1 | .5 |
| T2.02 | 1 | 1 | 1 | .5 |
| T2.03 | 1 | 1 | 1 | -1 |
| T2.04 | 1 | 1 | 1 | -1 |
| T2.05 | 1 | 1 | 1 | 0 |
| T2.06 | 1 | 1 | 1 | 0 |
| T2.07 | 1 | -1 | 1 | 0 |
| T2.08 | 1 | 1 | 1 | 0 |
| T2.09 | 1 | 1 | 1 | 0 |
| T2.10 | 1 | 1 | 1 | 0 |
| T2.11 | 1 | 1 | 1 | 0 |
| T2.12 | 1 | 1 | 1 | .5 |
| T2.13 | 1 | 1 | 1 | -1 |
| T2.14 | 1 | 1 | 1 | 0 |
| T2.15 | 1 | .5 | 1 | -1 |
| T2.16 | 1 | .5 | .5 | 0 |
| T2.17 | 0 | .5 | 0 | 0 |
| T2.18 | 1 | 1 | 1 | .5 |
| **Raw / final** | **17 / 17** | **14.5 / 14.5** | **16.5 / 16.5** | **-2 / 0** |

### T3. Protocol and framing

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| T3.01 | 1 | 1 | 1 | 1 |
| T3.02 | 1 | .5 | .5 | .5 |
| T3.03 | 1 | 1 | 1 | -1 |
| T3.04 | 1 | 1 | .5 | 0 |
| T3.05 | 1 | .5 | 0 | 0 |
| T3.06 | 1 | .5 | .5 | 0 |
| T3.07 | 1 | 1 | 1 | -1 |
| T3.08 | 1 | 1 | 1 | .5 |
| T3.09 | 1 | .5 | .5 | 0 |
| T3.10 | -1 | .5 | 0 | 0 |
| T3.11 | 0 | .5 | 1 | 0 |
| T3.12 | 1 | 1 | 1 | .5 |
| T3.13 | 1 | 1 | 1 | -1 |
| T3.14 | .5 | .5 | 1 | 0 |
| T3.15 | 0 | .5 | .5 | -1 |
| **Raw / final** | **10.5 / 10.5** | **11 / 11** | **10.5 / 10.5** | **-1.5 / 0** |

### T4. Transfer, multipart, and integrity

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| T4.01 | 1 | 1 | 1 | .5 |
| T4.02 | 1 | 1 | .5 | -1 |
| T4.03 | 1 | 1 | 1 | -1 |
| T4.04 | .5 | .5 | .5 | 0 |
| T4.05 | 1 | 1 | .5 | .5 |
| T4.06 | 0 | .5 | .5 | .5 |
| T4.07 | 1 | 1 | 1 | 1 |
| T4.08 | 1 | .5 | .5 | .5 |
| T4.09 | 1 | 1 | 1 | -1 |
| **Raw / final** | **7.5 / 7.5** | **7.5 / 7.5** | **6.5 / 6.5** | **0 / 0** |

### T5. Cryptography, registration, and persistence

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| T5.01 | -1 | 1 | -1 | -1 |
| T5.02 | 1 | 1 | 1 | 1 |
| T5.03 | 1 | 1 | 1 | 1 |
| T5.04 | 1 | -1 | -1 | -1 |
| T5.05 | 1 | 1 | 1 | 1 |
| T5.06 | 1 | 1 | 1 | 1 |
| T5.07 | 1 | .5 | .5 | -1 |
| T5.08 | .5 | 0 | 0 | -1 |
| T5.09 | .5 | .5 | .5 | 0 |
| T5.10 | 1 | 1 | 1 | 1 |
| T5.11 | .5 | 0 | .5 | -1 |
| T5.12 | 1 | 1 | .5 | .5 |
| T5.13 | 1 | .5 | 1 | .5 |
| T5.14 | 1 | .5 | 1 | 0 |
| **Raw / final** | **10.5 / 10.5** | **8 / 8** | **7 / 7** | **1 / 1** |

### Technical subtotal

| Submission | T1 | T2 | T3 | T4 | T5 | Total /70 |
|---|---:|---:|---:|---:|---:|---:|
| Luna | 14 | 17 | 10.5 | 7.5 | 10.5 | **59.5** |
| Q2.4T | 12 | 14.5 | 11 | 7.5 | 8 | **53.0** |
| GLM | 9.5 | 16.5 | 10.5 | 6.5 | 7 | **50.0** |
| Q27B | 6 | 0 | 0 | 0 | 1 | **7.0** |

## 3. R — Reverse-engineering rigor

### R1. Artifact acquisition and inventory

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| R1.01 | 1 | 1 | 1 | 1 |
| R1.02 | 1 | 1 | 1 | 1 |
| R1.03 | 1 | 1 | 0 | 0 |
| **Raw / final** | **3 / 3** | **3 / 3** | **2 / 2** | **2 / 2** |

### R2. Exact call-chain recovery

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| R2.01 | 1 | 1 | 1 | 1 |
| R2.02 | 1 | 1 | 1 | 1 |
| R2.03 | 1 | 1 | 1 | .5 |
| R2.04 | .5 | .5 | .5 | .5 |
| R2.05 | 1 | 1 | 1 | .5 |
| **Raw / final** | **4.5 / 4.5** | **4.5 / 4.5** | **4.5 / 4.5** | **3.5 / 3.5** |

### R3. Cross-artifact verification

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| R3.01 | 1 | 1 | .5 | 1 |
| R3.02 | 1 | .5 | 0 | 0 |
| R3.03 | 1 | 1 | -1 | -1 |
| **Raw / final** | **3 / 3** | **2.5 / 2.5** | **-.5 / 0** | **0 / 0** |

### R4. Reproducibility and validation

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| R4.01 | 1 | -1 | 1 | -1 |
| R4.02 | 1 | 1 | 1 | 0 |
| R4.03 | 1 | 1 | 1 | .5 |
| R4.04 | 0 | 0 | 0 | 0 |
| **Raw / final** | **3 / 3** | **1 / 1** | **3 / 3** | **-.5 / 0** |

### R5. Falsification and confidence calibration

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| R5.01 | 1 | 1 | .5 | .5 |
| R5.02 | 1 | 1 | 1 | .5 |
| R5.03 | 1 | .5 | 0 | -1 |
| **Raw / final** | **3 / 3** | **2.5 / 2.5** | **1.5 / 1.5** | **0 / 0** |

### Rigor subtotal

| Submission | R1 | R2 | R3 | R4 | R5 | Total /18 |
|---|---:|---:|---:|---:|---:|---:|
| Luna | 3 | 4.5 | 3 | 3 | 3 | **16.5** |
| Q2.4T | 3 | 4.5 | 2.5 | 1 | 2.5 | **13.5** |
| GLM | 2 | 4.5 | 0 | 3 | 1.5 | **11.0** |
| Q27B | 2 | 3.5 | 0 | 0 | 0 | **5.5** |

## 4. P — Reporting and implementation utility

### P1. Required output coverage

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| P1.01 | 1 | 1 | 1 | 1 |
| P1.02 | 1 | 1 | 1 | 1 |
| **Raw / final** | **2 / 2** | **2 / 2** | **2 / 2** | **2 / 2** |

### P2. Technical presentation

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| P2.01 | 1 | 1 | .5 | -1 |
| P2.02 | 1 | 1 | 1 | .5 |
| P2.03 | 1 | -1 | 1 | -1 |
| **Raw / final** | **3 / 3** | **1 / 1** | **2.5 / 2.5** | **-1.5 / 0** |

### P3. Claim-to-evidence traceability

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| P3.01 | 1 | 1 | 1 | .5 |
| P3.02 | 1 | 1 | 1 | .5 |
| P3.03 | 1 | 1 | 1 | .5 |
| **Raw / final** | **3 / 3** | **3 / 3** | **3 / 3** | **1.5 / 1.5** |

### P4. Independent-client utility and safety

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| P4.01 | 1 | .5 | .5 | 0 |
| P4.02 | 1 | 1 | .5 | -1 |
| P4.03 | 1 | 1 | 1 | -1 |
| **Raw / final** | **3 / 3** | **2.5 / 2.5** | **2 / 2** | **-2 / 0** |

### P5. Internal consistency

| ID | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| P5.01 | .5 | 0 | .5 | 0 |
| **Raw / final** | **.5 / .5** | **0 / 0** | **.5 / .5** | **0 / 0** |

### Reporting subtotal

| Submission | P1 | P2 | P3 | P4 | P5 | Total /12 |
|---|---:|---:|---:|---:|---:|---:|
| Luna | 2 | 3 | 3 | 3 | .5 | **11.5** |
| Q2.4T | 2 | 1 | 3 | 2.5 | 0 | **8.5** |
| GLM | 2 | 2.5 | 3 | 2 | .5 | **10.0** |
| Q27B | 2 | 0 | 1.5 | 0 | 0 | **3.5** |

## 5. Non-full-credit rationale index

The rubric text supplies the expected fact for every ID. This section records
why each submission received less than `1`.

### 5.1 Luna

- **T2.17:** did not distinguish encoder versus decoder config validation or
  document incomplete-final-codeword behavior.
- **T3.10:** supplementary Telesto report calls the stored range inclusive;
  ground truth is half-open.
- **T3.11/T3.14:** omitted the accepted four-byte `u32le totalLength` envelope,
  so envelope disambiguation was incomplete.
- **T3.15/T4.06:** correctly identified length fields but incorrectly said the
  native parser safely validates record bounds; duplicate/selection behavior
  and overshoot gaps were omitted.
- **T4.04:** documented contiguity and flushing but not arrival-order append or
  emission of a gapped final group with `isContiguous=false`.
- **T5.01:** called BLE encryption/bonding `yes/OS-level`; actual session/mode
  remains unknown.
- **T5.08/T5.09/T5.11:** recovered the registration struct and size but not all
  serialized offsets, 145-byte length-prefixed operation-5 object, or full
  fingerprint semantics.
- **R2.04:** omitted the exact `PPCollectionSimple_createAudioTimeline`
  cinterop-wrapper hop.
- **R4.04:** no runnable decoder, native harness, or regression suite.
- **P5.01:** inclusive-range and BLE-security wording conflicts with stronger
  parts of the submission.

### 5.2 Qwen 2.4T

- **T1.01/T5.04:** answered physical storage-at-rest encryption as no rather
  than unknown.
- **T2.07/R4.01/P2.03:** reversed the DD-Rice leading-bit polarity, making the
  supplied decoder wire-incompatible.
- **T2.15:** bit-count termination was understood, but fixed-frame/count and
  malformed-tail behavior were incomplete.
- **T2.16/P5.01:** executive “lossless” wording conflicts with its later,
  correct observation that nonzero shifts quantize.
- **T2.17:** partially recognized permissive decoder config but omitted the
  encoder/decoder `0xef` distinction and truncated-tail behavior.
- **T3.02/T3.06/T4.08:** overgeneralized write-with-response/ack behavior.
- **T3.05:** assigned unsupported `transferEndIndex` meaning to response
  `info`.
- **T3.09:** parsed the wrong advertising-data slice.
- **T3.10:** retained a 512-slot/wire-limit overclaim and did not fully separate
  inclusive/exclusive progress values.
- **T3.11/T3.14:** treated the four-byte total-length envelope as a legacy LE24
  field; numerically close for a zero high byte but not exact.
- **T3.15/T4.04/T4.06:** useful TLV/multipart/check coverage, but no duplicate
  precedence, parser overshoot gaps, arrival-order/final-gap behavior, or full
  actor distinction.
- **T5.07-T5.11:** established no secret but did not recover exact registration
  serialization, prefix/operation, or fingerprint algorithm.
- **T5.13/T5.14/P4.01:** incomplete Android/bond-state treatment and speculative
  keepalive/NO-OP interpretation of the `00` write.
- **R2.04:** omitted the exact cinterop simple-wrapper hop.
- **R3.02:** top-level parity was shown; native simulator/device parity was not
  completed to the same standard.
- **R4.04:** no executable decoder/native vectors/regression suite.
- **R5.03:** physical-at-rest overclaim weakened confidence calibration.

### 5.3 GLM

- **T1.01/T5.04:** treated physical-flash plaintext as nearly certain rather
  than unknown.
- **T1.04/T3.02/P2.01:** conflated incoming collection bytes with a four-byte
  length-prefix helper and Android 20-byte write policy.
- **T1.13/T4.02/T4.04:** reported basic multipart reassembly but not full group
  origin/current-index, order, gap, and finality semantics.
- **T2.16/T2.17:** did not fully state quantization/losslessness or config/tail
  edge behavior.
- **T3.04:** omitted operation type `5`.
- **T3.05:** left the response fields unresolved.
- **T3.06/T3.09/T3.10:** partial controller/advertising/range reconstruction;
  phase order and 512-slot semantics were overclaimed.
- **T3.15/T4.06:** correct core TLVs/lengths but no duplicate precedence or
  native bounds gaps.
- **T4.05/T4.08:** operation response/reconnect behavior was not cleanly
  separated from acknowledgement/retransmission terminology.
- **T5.01:** called BLE encryption active rather than session-dependent.
- **T5.07-T5.11:** registration fields, exact serialization, program wrapper,
  and fingerprint details remained incomplete.
- **T5.12:** iOS persistence was asserted by analogy rather than directly
  recovered.
- **R1.03/R3.02/R3.03:** missed the published iOS companion native archives
  and relied on Android native code as target proof; R3 therefore floors to
  zero.
- **R2.04:** omitted the exact cinterop simple-wrapper hop.
- **R4.04:** no executable decoder/native vectors/regression suite.
- **R5.01/R5.03/P5.01:** confidence labels were present, but physical-at-rest
  and framing overclaims remained.
- **P4.01/P4.02:** independent-client instructions had incomplete pairing,
  response, and incoming-framing details.

### 5.4 Qwen 27B

- **T1.01/T1.09/T1.14/R5.03:** inferred physical-flash representation and
  16 kHz ring capture from phone-side output behavior.
- **T1.04/T3.02/P2.01:** put a four-byte length prefix on every incoming GATT
  notification.
- **T1.06/T2.03/T3.15/T4.03:** treated `0x52` as compressed audio instead of
  multipart metadata.
- **T1.13/T4.02:** said multipart parts share one current collection index.
- **T2.01-T2.17/R4.01/P2.03:** did not reconstruct the actual compressed record
  or decoder; invented a 13-byte header, omitted the bounded-unary code and
  second integration, and converted initial allocation into a frame cap.
  T2 floors to zero.
- **T2.18/P3.01:** claimed Xiph Speex `dd_rice.c` provenance from `DDRice*`
  symbol names without supporting source evidence.
- **T3.03/T3.07/T3.08:** supplied the wrong Telesto request model and stored
  range address, plus an unknown collection stride.
- **T3.13:** called the `u24be` envelope little-endian.
- **T3.15/P2.02:** invented type-4 audio metadata and an incompatible TLV model.
  T3 and P2 floor to zero.
- **T4.01:** confused the codec's initial sample allocation/app buffer with the
  native collection cap.
- **T4.09/P4.03:** overclaimed generic erase as recording deletion. It was not
  given the extra destructive-action penalty only because the report also said
  live semantics were still needed.
- **T5.01/T5.04:** overclaimed BLE and physical-flash encryption status.
- **T5.07/T5.08/T5.11/P3.03:** conflated a raw-sensor fingerprint routine with
  the UID registration fingerprint and invented a 128-bit field.
- **T5.14/P4.01:** treated the observed `00` write as app registration.
- **R1.03:** incorrectly said published companion cinterop KLIBs were
  unavailable.
- **R2.03-R2.05:** found the broad class/function chain but confused parser
  ordering and native ABI/multipart details.
- **R3.03:** Android native code was used as target proof without the available
  iOS native archives; R3 floors to zero.
- **R4.02-R4.04:** no correct wire example, executable decoder, native vector,
  or regression suite; R4 floors to zero.
- **R5.01/R5.02:** confidence labels and some negative searches were present,
  but repeatedly applied to unsupported conclusions; R5 floors to zero.
- **P3.01-P3.03:** reports concrete symbols/offsets, but they only partially
  support the stated conclusions.
- **P4.02/P4.03:** the client cannot work with the supplied request, address,
  framing, tag, and decoder model; P4 floors to zero.
- **P5.01:** central conclusions contradict details elsewhere.

## 6. Additional penalties

Q27B receives `-6`:

| Penalty | Points |
|---|---:|
| App-side 16 kHz constants presented as proof of the ring's source rate | -2 |
| `DDRice*` symbol names presented as proof of Xiph Speex provenance | -2 |
| Raw-sensor fingerprint routine presented as the UID registration field/index | -2 |
| **Total** | **-6** |

No submission receives the unsupported destructive-instruction penalty.

## 7. Verified novelty

| Finding | Luna | Q2.4T | GLM | Q27B |
|---|---:|---:|---:|---:|
| Firmware-dependent UID registration and post-pair collection-wipe/read-only coexistence policy | +2 | 0 | 0 | 0 |
| Structured 8 kHz/16 kHz candidates in the public firmware image, without claiming production rate | +1 | 0 | 0 | 0 |
| Direct `HaversineReadLastAudioSamplesOperation` path reaches PPCollection/DD-Rice decoder | +1 | +1 | 0 | 0 |
| Full seven-byte System Input wire structure and type map | +1 | 0 | 0 | 0 |
| **Total** | **+5** | **+1** | **0** | **0** |

Independent verification details are retained in `GRADING_REPORT.md`.
