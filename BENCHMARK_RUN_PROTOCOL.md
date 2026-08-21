# Haversine benchmark-run protocol

This is the end-to-end procedure for adding a comparable Haversine
reverse-engineering run: setup, execution, curation, reporting, verification,
and grading. It complements the filesystem boundary in
[`SANDBOX_METHODOLOGY.md`](SANDBOX_METHODOLOGY.md).

## 1. Define the run

Record before launch:

- a stable, descriptive directory and run ID;
- harness/session system and version;
- provider and exact model slug;
- requested and effective reasoning setting;
- whether the run is single-agent or uses workers/subagents;
- the common-brief revision (SHA-256 of `PROMPT.md`);
- the comparison commit and grading-rubric revision that will be used;
- the common initial user message below.

All candidates receive the byte-identical `PROMPT.md` brief and this initial
message:

```text
read the brief and start work. log your progress as you go along so that we can review the progress and track the outstanding task and so that you don't lose progress when context is compacted
```

Public upstream research and installation of ordinary analysis tools are in
scope. Reading another benchmark run, its raw session history, or the
comparison repository is not.

## 2. Prepare an isolated workspace

1. Create a new workspace outside the comparison repository.
2. Copy only `PROMPT.md` into it as `brief.md`.
3. Create workspace-local temporary and Pi-session directories.
4. Use the `sandbox-exec` methodology to deny prior benchmark workspaces,
   Pi/Codex histories, and publishing credentials.
5. Run the preflight checks in `SANDBOX_METHODOLOGY.md` before starting the
   model.
6. For a Pi run, launch it in a named `tmux` session with:

   ```text
   --provider <provider> --model <exact-slug> --thinking <requested-level>
   --session-dir <workspace-local-dir> --no-extensions --no-skills
   --no-context-files
   ```

   For another harness, record and reproduce the closest equivalent isolation,
   context-discovery, extension/skill, session-storage, and worker settings.

Record the model's effective reasoning level if the harness caps or remaps the
requested level. Do not silently replace a rejected model or reasoning setting:
record the failure or start a clearly labeled replacement run.

## 3. Execution rules

- Let the agent work from the common brief and its own workspace.
- Do not provide conclusions, excerpts, or files from another candidate.
- Preserve the agent's authored progress log and final report in its workspace.
- Do not inject task-changing follow-ups. If a material follow-up is necessary,
  label its time range separately and exclude it from original-run accounting.
- A run is complete only when it has a final report addressing the brief, not
  merely a chat summary or a partial progress log.

The harness, system/developer instructions, tool availability, model provider,
and worker topology are part of the benchmark environment. Record them; do not
describe the result as a model-weights-only comparison.

## 4. Required authored deliverables

Retain, at minimum:

1. a final technical report;
2. a progress/work log.

Also retain compact evidence files or scripts when the run created them, they
materially substantiate a major claim, and they pass the publication gate.
Otherwise preserve precise source-workspace evidence coordinates and keep that
workspace available for grading verification.

The final report must cover the ten functional areas requested by the brief:

1. executive answer;
2. end-to-end data path;
3. codec analysis and implementable pseudocode where justified;
4. frame/protocol structures and byte tables;
5. cryptography analysis separated by layer;
6. key-management/registration analysis;
7. relevant functions, offsets, and call chains;
8. claim-to-evidence mapping;
9. remaining unknowns and resolving artifacts;
10. independent-client implications and safety limits.

Claims must distinguish direct evidence, inference, and unknowns. In
particular, the report must not turn app-side behavior into proof of the
physical flash representation, runtime source rate, BLE security mode, or
firmware behavior without direct evidence.

## 5. Curation and privacy gate

Copy authored deliverables into a normalized candidate directory, normally as:

```text
<run-id>/docs/reverse_engineering_report.md
<run-id>/docs/progress.md
```

Preserve technical claims as authored. Normalize filenames and sanitize only
machine-local metadata. Compact evidence excerpts or scripts may be retained
when useful, but exclude downloaded binaries, firmware payloads, full extracted
archives, toolchains, third-party checkouts, and raw session transcripts.

Before publishing, verify:

- no local absolute paths, user identifiers, unnecessary machine/locale
  metadata, or credential-like strings remain;
- no symlinks are present;
- Markdown has no whitespace errors;
- repository-relative links to retained files resolve;
- source-workspace evidence coordinates that necessarily refer to excluded,
  reproducible binaries are clearly citations rather than broken repository
  links;
- the source workspace is retained separately until curation is accepted.

Rewrite only the necessary text to sanitize it; do not alter technical claims
or fabricate missing evidence during curation.

## 6. Session accounting

Record only the original-research time windows. Exclude setup chatter,
interrupted experiments that did not contribute research, and later related
follow-ups.

Read the raw session record locally for accounting, but do not publish it. For
each retained window, collect where the session system provides it:

- first and last activity timestamps in UTC and elapsed duration calculated
  from the unrounded timestamps;
- assistant-message count and actual `toolCall` record count;
- provider cost or user-reported subscription consumption;
- total tokens, with new-input, output, and cache-read breakdowns;
- effective model, reasoning setting, and worker count.

For per-response usage records, sum the recorded input, output, cache-read, and
cost fields across the included responses. Round presentation values only after
summing. Do not infer cost for a local or subscription run when the source
record does not provide one.

When a session contains multiple windows, sum only those windows. For a
multi-agent run, take each participating agent's cumulative counter at the
original-run cutoff and sum those counters; do not include later worker turns.
State accounting differences between session systems rather than implying that
their token counters have identical billing semantics.

## 7. Verification and grading

Use the frozen grading corpus and do not grade from memory or a chat summary.
The base rubric must not move after seeing a candidate merely to reward or
punish that submission. If a ground-truth correction requires a base-rubric
change, version the change and rescore every candidate.

### 7.1 Ground-truth and relevance policy

Treat `gpt-5.6-sol-ultra/` as the assumed ground-truth corpus. When its
chronological notes and completed findings differ, use this precedence:

1. `gpt-5.6-sol-ultra/docs/reverse_engineering_report.md`;
2. `gpt-5.6-sol-ultra/docs/report_coverage_checklist.md`;
3. completed focused Sol Ultra reports;
4. Sol Ultra progress notes.

Use `PROMPT.md` to decide whether a finding is relevant. Preserve unknowns
where Sol Ultra does; a candidate's confident statement does not resolve an
unknown unless it qualifies for independently verified novelty without
contradicting the assumed ground truth.

### 7.2 Atomic base score

- [`GRADING_RUBRIC.md`](GRADING_RUBRIC.md) defines 100 atomic base checkpoints:
  technical reconstruction (70), reverse-engineering rigor (18), and reporting
  and implementation utility (12).
- Grade every retained authored file for a candidate as one submission.
- Assign all 100 cells using only `+1`, `+0.5`, `0`, or `-1` as defined by the
  rubric. An explicit incompatible claim can receive `-1` even when a correct
  high-level statement appears elsewhere.
- Sum each named subsection, then floor it at zero and cap it at its stated
  weight. Sum the resulting technical, rigor, and reporting subtotals.
- Apply post-subtotal penalties once per distinct misuse: `-2` for fabricated
  or materially mismatched evidence and `-3` for an unsafe unsupported
  destructive instruction. Repeated wording of the same evidence misuse is one
  penalty event. Bound the final base score to `0..100`.
- Record every atomic score in `GRADING_LEDGER.md`, plus a rationale index that
  accounts for every non-full-credit cell, either individually or through an
  unambiguous inclusive ID range, and separate penalty tables.

### 7.3 Verified novelty

Award up to five bonus points only when a finding:

1. is absent from the entire Sol Ultra corpus and the frozen base rubric;
2. materially improves relevant protocol, decoder, pairing, recovery, or
   independent-client safety knowledge;
3. is specific and falsifiable;
4. does not contradict the assumed ground truth; and
5. is independently verified from retained/original binaries, source, a
   capture, or a reproducible test—not merely from the candidate's prose.

The same independently documented finding receives the same bonus in every
candidate that found it. A later-discovered novelty does not deduct points from
earlier candidates that omitted it. Record accepted and materially plausible
but rejected novelty claims in the report, including the verification result.

### 7.4 Comparative report and efficiency

- Write `GRADING_REPORT.md` with the scope/ground-truth policy, results table,
  candidate-by-candidate assessment, decisive comparison matrix, and
  efficiency context.

Technical scores measure the retained result, not price, time, or harness
power. Cost, tokens, duration, and harness differences are reported separately
as efficiency and comparability context. Where denominators exist, calculate
base points per active hour and base points per recorded dollar; do not use
either value to change rank or quality score.

### 7.5 Mechanical validation gate

Before accepting a grade, run checks that establish:

- exactly 100 unique rubric IDs and one score cell for every candidate at each
  ID;
- every score cell is one of `1`, `.5`, `0`, or `-1`;
- every non-full-credit ID is covered individually or by an unambiguous
  inclusive ID range in that candidate's rationale index;
- every subsection raw sum and floor/cap result is reproducible;
- technical, rigor, reporting, penalty, base, novelty, adjusted score, and rank
  agree in the ledger and report;
- run duration, token, cost, and derived-efficiency arithmetic reproduce the
  README/report values;
- Markdown tables have consistent columns, links intended to resolve in the
  repository do resolve, and `git diff --check` passes.

## 8. Aggregated documents to update

After curating and grading a new candidate, update every aggregate that consumes
run-level data:

1. **`README.md`**
   - add the run to the directory/primary-report table;
   - add its complete session metadata row;
   - add its technical, rigor, reporting, penalty, base, novelty, adjusted
     score, and rank to the grading summary;
   - update run counts, navigation, comparability, curation, or caution text
     affected by the new run.
2. **`GRADING_LEDGER.md`**
   - add the candidate abbreviation and results row;
   - add one score cell for each of the 100 rubric IDs;
   - add every subsection raw/final value and category subtotal;
   - add a rationale covering every non-full-credit ID;
   - add distinct evidence/destructive penalties and verified-novelty awards.
3. **`GRADING_REPORT.md`**
   - add the candidate to scope and all results/breakdown tables;
   - add its candidate-specific strengths, deductions, and penalty explanation;
   - update novelty verification, the decisive comparison matrix, efficiency
     context, overall assessment, and rank-dependent wording.

Review these frozen or procedural documents, but do not change them merely to
fit a new candidate:

- **`GRADING_RUBRIC.md`** remains frozen for an ordinary new run. If a genuine
  ground-truth correction changes the base rubric, version it and rescore every
  candidate.
- **`PROMPT.md`** remains byte-identical across runs.
- **`BENCHMARK_RUN_PROTOCOL.md`** changes only when the actual workflow changes.
- **`SANDBOX_METHODOLOGY.md`** changes only when the isolation design changes.

The candidate's own normalized deliverables are added under `<run-id>/`; they
are inputs to the aggregates above, not aggregate documents themselves.

## 9. Publication checklist

Before making the repository public, confirm that:

- the candidate directory, README row, run metadata, grading ledger, and
  grading report agree on the same run identity;
- all curation and privacy checks pass;
- the comparison notes disclose material harness advantages or worker use;
- unrelated worktree changes are preserved and excluded from the publication
  commit;
- raw transcripts, sandbox profiles, credentials, and downloaded artifacts are
  not staged;
- the repository is clean, committed, and pushed;
- visibility is set deliberately after review.

This sequence makes a new run reproducible and auditable without relying on
the conversational context in which it was launched.
