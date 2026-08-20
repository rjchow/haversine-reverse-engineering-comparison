# Haversine reverse-engineering comparison

Five independent agent runs investigated the phone-side Haversine libraries used with the Pebble Index 01 ring. This repository preserves each run's authored deliverables side by side; it is not a merged technical conclusion.

| Directory | Model/run |
|---|---|
| `qwen3.8-27b-local-4bit/` | Qwen 3.8 27B, local 4-bit quantization |
| `qwen3.8-2.4t-openrouter/` | Qwen 3.8 2.4T via OpenRouter |
| `gpt-5.6-luna-xhigh/` | GPT-5.6 Luna, xhigh reasoning |
| `gpt-5.6-sol-ultra/` | GPT-5.6 Sol, ultra reasoning |
| `glm-5.3-openrouter-max/` | GLM 5.3 via OpenRouter, maximum reasoning requested |

`PROMPT.md` is the byte-identical investigation brief supplied to all five runs. `RUN_METADATA.md` contains a sanitized comparison of the available Pi and Codex session records.

## Contents and curation

The repository includes authored reports, protocol/specification notes, progress logs, and reusable decoding/decompilation scripts. File names have been normalized for easy comparison.

It intentionally excludes downloaded binaries and firmware, extracted proprietary libraries, third-party source checkouts, toolchain distributions, and raw agent transcripts. Those materials are either reproducible from the public references in the reports or inappropriate to mirror here.

Before publication, the retained documents were checked for personal identifiers, credential-like values, and local absolute paths. Two machine-relative references were rewritten to repository-relative paths; no raw session log is included.

## Caution

These are independent reverse-engineering results. Confidence labels and conclusions differ between reports; consult the evidence and the stated limitations in the individual documents before relying on a claim or interacting with a device.
