# Haversine reverse-engineering comparison

Five independent agent runs investigated the phone-side Haversine libraries used with the Pebble Index 01 ring. This repository preserves each run's authored deliverables side by side; it is not a merged technical conclusion.

| Directory | Model/run |
|---|---|
| `qwen3.8-27b-local-4bit/` | Qwen 3.8 27B, local 4-bit quantization |
| `qwen3.8-2.4t-openrouter/` | Qwen 3.8 2.4T via OpenRouter |
| `gpt-5.6-luna-xhigh/` | GPT-5.6 Luna, xhigh reasoning |
| `gpt-5.6-sol-ultra/` | GPT-5.6 Sol, ultra reasoning |
| `glm-5.3-openrouter-max/` | GLM 5.3 via OpenRouter, maximum reasoning requested |

`PROMPT.md` is the byte-identical investigation brief supplied to all five runs.
[`SANDBOX_METHODOLOGY.md`](SANDBOX_METHODOLOGY.md) documents the isolation used
for subsequent Pi benchmark runs.

## Run metadata

Times below are UTC and cover only the original reverse-engineering effort begun from the common brief; later related follow-ups are excluded. OpenRouter costs are sums of the recorded per-response costs for those windows, rounded to cents. Subscription-plan figures are user-reported usage percentages, not dollar prices. Token parentheses are **new input / output / cache read**; reasoning output is included in output.

| Deliverable directory | Session system | Model and reasoning | Original RE activity window(s) | Active elapsed | Recorded activity | Cost / plan usage | Token total (new input / output / cache read) |
|---|---|---|---|---|---|---|---|
| `qwen3.8-27b-local-4bit/` | Pi | `qwen38-27b-optimized` (local Qwen 3.8 27B), xhigh | 2026-08-19 05:17:08–15:01:02 | 9h 43m 54s | 233 assistant message records; 229 tool calls | Not measured (local inference) | 26.19M (25.99M / 198.8K / 0) |
| `gpt-5.6-luna-xhigh/` | Pi | `gpt-5.6-luna`, xhigh | 2026-08-19 13:13:42–13:47:24 | 33m 42s | 176 assistant message records; 175 tool calls | 1% of GPT Pro Lite 5× subscription (user-reported) | 77.61M (1.31M / 80.0K / 76.22M) |
| `qwen3.8-2.4t-openrouter/` | Pi | `qwen/qwen3.8-2.4t-a95b` via OpenRouter, xhigh | 2026-08-19 14:53:10–16:05:01; 23:03:49–23:12:29 | 1h 20m 31s | 131 assistant message records; 135 tool calls | US$5.98 (recorded) | 14.93M (886.8K / 120.4K / 13.93M) |
| `gpt-5.6-sol-ultra/` | Codex | `gpt-5.6-sol`, ultra | 2026-08-19 23:32:46–2026-08-20 00:25:15 | 52m 28s | Main agent plus 7 workers; 635 standard function-call records and 219 custom-tool-call records | 13% of GPT Pro Lite 5× subscription (user-reported) | 130.90M (3.71M / 366.5K / 126.82M) |
| `glm-5.3-openrouter-max/` | Pi | `z-ai/glm-5.3` via OpenRouter; max requested, high reported by Pi | 2026-08-20 07:35:52–07:38:25; 07:39:08–07:59:43 | 23m 08s | 116 assistant message records; 133 tool calls | US$3.88 (recorded) | 12.51M (301.7K / 68.7K / 12.13M) |

## Comparability note

The Sol Ultra result is not a model-only comparison. Alongside the common investigation brief, it had the Codex harness: Codex system and developer instructions, built-in tool and task orchestration, and one main agent with seven worker agents. That execution environment gave it materially more parallel research capacity than the single-agent Pi runs.

The Pi runs likewise used Pi's own harness and instruction context. These results are therefore useful as end-to-end agent-system comparisons, but not as a controlled comparison of model weights alone.

## Contents and curation

The repository includes authored reports, protocol/specification notes, progress logs, and reusable decoding/decompilation scripts. File names have been normalized for easy comparison.

It intentionally excludes downloaded binaries and firmware, extracted proprietary libraries, third-party source checkouts, toolchain distributions, and raw agent transcripts. Those materials are either reproducible from the public references in the reports or inappropriate to mirror here.

Before publication, the retained documents were checked for personal identifiers, credential-like values, and local absolute paths. Two machine-relative references were rewritten to repository-relative paths; no raw session log is included.

## Caution

These are independent reverse-engineering results. Confidence labels and conclusions differ between reports; consult the evidence and the stated limitations in the individual documents before relying on a claim or interacting with a device.
