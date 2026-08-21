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
6. Launch Pi in a named `tmux` session with:

   ```text
   --provider <provider> --model <exact-slug> --thinking <requested-level>
   --session-dir <workspace-local-dir> --no-extensions --no-skills
   --no-context-files
   ```

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
2. a progress/work log;
3. compact evidence files or scripts when they substantiate a major claim.

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

Copy only authored deliverables into a normalized candidate directory. Exclude
downloaded binaries, firmware payloads, full extracted archives, toolchains,
third-party checkouts, and raw session transcripts.

Before publishing, verify:

- no local absolute paths, user identifiers, geographic/locale metadata, or
  credential-like strings remain;
- no symlinks are present;
- Markdown has no whitespace errors;
- evidence links and referenced files resolve;
- the source workspace is retained separately until curation is accepted.

Rewrite only the necessary text to sanitize it; do not alter technical claims
or fabricate missing evidence during curation.

## 6. Session accounting

Record only the original-research time windows. Exclude setup chatter,
interrupted experiments that did not contribute research, and later related
follow-ups.

For each retained window, collect where the session system provides it:

- first and last assistant-activity timestamps and elapsed duration;
- assistant-message and tool-call counts;
- provider cost or user-reported subscription consumption;
- total tokens, with new-input, output, and cache-read breakdowns;
- effective model, reasoning setting, and worker count.

When a session contains multiple windows, sum only those windows. For a
multi-agent run, take each participating agent's cumulative counter at the
original-run cutoff and sum those counters; do not include later worker turns.
State accounting differences between session systems rather than implying that
their token counters have identical billing semantics.

## 7. Verification and grading

Use the committed grading corpus and do not grade from memory or a chat
summary:

- [`GRADING_RUBRIC.md`](GRADING_RUBRIC.md) defines 100 atomic base checkpoints:
  technical reconstruction (70), reverse-engineering rigor (18), and reporting
  and implementation utility (12).
- Grade every retained authored file for a candidate as one submission.
- Apply `+1`, `+0.5`, `0`, and `-1` exactly as defined by the rubric. Floor and
  cap each subsection, then apply documented post-base penalties.
- Award up to five verified novelty points only for a correctly evidenced
  finding that is outside the rubric and not already credited elsewhere.
- Record every atomic score in `GRADING_LEDGER.md`, including citations and
  rationale for partial credit, contradictions, penalties, and novelty.
- Write `GRADING_REPORT.md` with the scope/ground-truth policy, results table,
  candidate-by-candidate assessment, decisive comparison matrix, and
  efficiency context.

Technical scores measure the retained result, not price, time, or harness
power. Cost, tokens, duration, and harness differences are reported separately
as efficiency and comparability context.

## 8. Publication checklist

Before making the repository public, confirm that:

- the candidate directory, README row, run metadata, grading ledger, and
  grading report agree on the same run identity;
- all curation and privacy checks pass;
- the comparison notes disclose material harness advantages or worker use;
- the repository is clean, committed, and pushed;
- visibility is set deliberately after review.

This sequence makes a new run reproducible and auditable without relying on
the conversational context in which it was launched.
