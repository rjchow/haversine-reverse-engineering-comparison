# Haversine reverse-engineering comparison

Seven independent agent runs investigated the phone-side Haversine libraries
used with the Pebble Index 01 ring. The repository preserves each run's
authored deliverables and compares the six candidates against GPT-5.6 Sol Ultra
as the assumed ground truth.

## Runs

| Directory | Model/run | Comparison role | Primary report |
|---|---|---|---|
| `gpt-5.6-sol-ultra/` | GPT-5.6 Sol, ultra reasoning | Assumed ground truth; not ranked | [Report](gpt-5.6-sol-ultra/docs/reverse_engineering_report.md) |
| `gpt-5.6-luna-xhigh/` | GPT-5.6 Luna, xhigh reasoning | Graded candidate | [Report](gpt-5.6-luna-xhigh/docs/reverse_engineering_report.md) |
| `qwen3.8-2.4t-openrouter/` | Qwen 3.8 2.4T via OpenRouter | Graded candidate | [Report](qwen3.8-2.4t-openrouter/docs/reverse_engineering_report.md) |
| `glm-5.3-openrouter-max/` | GLM 5.3 via OpenRouter, maximum reasoning requested | Graded candidate | [Report](glm-5.3-openrouter-max/docs/reverse_engineering_report.md) |
| `stealth-ox-alpha-openrouter-max/` | Stealth Ox Alpha via OpenRouter, maximum reasoning requested | Graded candidate | [Report](stealth-ox-alpha-openrouter-max/docs/reverse_engineering_report.md) |
| `qwen3.8-27b-local-4bit/` | Qwen 3.8 27B, local 4-bit quantization | Graded candidate | [Report](qwen3.8-27b-local-4bit/docs/reverse_engineering_report.md) |
| `qwen3.8-27b-local-4bit-verification-2/` | **the second run of local qwen 3.8 27b 4 bit for verification** (`qwen38-27b-optimized`, xhigh) | Graded candidate | [Report](qwen3.8-27b-local-4bit-verification-2/docs/reverse_engineering_report.md); [metadata](qwen3.8-27b-local-4bit-verification-2/docs/run_metadata.md) |

## Grading results

The frozen rubric scores technical reconstruction (70), reverse-engineering
rigor (18), and reporting utility (12), with separate penalties and up to five
verified-novelty points.

| Rank | Candidate | Technical /70 | Rigor /18 | Reporting /12 | Penalty | Base /100 | Novelty /5 | Adjusted /105 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | GPT-5.6 Luna xhigh | 59.5 | 16.5 | 11.5 | 0 | **87.5** | +5 | **92.5** |
| 2 | Qwen 3.8 2.4T OpenRouter | 53.0 | 13.5 | 8.5 | 0 | **75.0** | +1 | **76.0** |
| 3 | GLM 5.3 OpenRouter max | 50.0 | 11.0 | 10.0 | 0 | **71.0** | 0 | **71.0** |
| 4 | Stealth Ox Alpha OpenRouter max | 25.0 | 10.0 | 4.0 | -6 | **33.0** | +1 | **34.0** |
| 5 | the second run of local qwen 3.8 27b 4 bit for verification | 9.0 | 7.5 | 1.5 | -8 | **10.0** | +1 | **11.0** |
| 6 | Qwen 3.8 27B local 4-bit | 7.0 | 5.5 | 3.5 | -6 | **10.0** | 0 | **10.0** |

See the [grading report](GRADING_REPORT.md) for the comparative assessment and
the [ledger](GRADING_LEDGER.md) for all 100 atomic scores and rationales.

## Run metadata

Times cover the original reverse-engineering windows. Token
parentheses are **new input / output / cache read**. Accounting conventions are
defined in the [run protocol](BENCHMARK_RUN_PROTOCOL.md#6-session-accounting).

| Deliverable directory | Session system | Model and reasoning | Original RE activity window(s) | Active elapsed | Recorded activity | Cost / plan usage | Token total (new input / output / cache read) |
|---|---|---|---|---|---|---|---|
| `qwen3.8-27b-local-4bit/` | Pi | `qwen38-27b-optimized` (local Qwen 3.8 27B), xhigh | 2026-08-19 05:17:08–15:01:02 | 9h 43m 54s | 233 assistant message records; 229 tool calls | Not measured (local inference) | 26.19M (25.99M / 198.8K / 0) |
| `qwen3.8-27b-local-4bit-verification-2/` | Pi | **the second run of local qwen 3.8 27b 4 bit for verification**; `qwen38-27b-optimized`, xhigh | 2026-08-21 13:25:50–17:32:48; 18:09:03–20:32:31; 20:40:45–21:42:07 | 7h 31m 48s | 203 assistant message records; 207 tool calls | Not measured (local inference) | 20.31M (20.08M / 229.8K / 0) |
| `gpt-5.6-luna-xhigh/` | Pi | `gpt-5.6-luna`, xhigh | 2026-08-19 13:13:42–13:47:24 | 33m 42s | 176 assistant message records; 175 tool calls | 1% of GPT Pro Lite 5× subscription (user-reported) | 77.61M (1.31M / 80.0K / 76.22M) |
| `qwen3.8-2.4t-openrouter/` | Pi | `qwen/qwen3.8-2.4t-a95b` via OpenRouter, xhigh | 2026-08-19 14:53:10–16:05:01; 23:03:49–23:12:29 | 1h 20m 31s | 131 assistant message records; 135 tool calls | US$5.98 (recorded) | 14.93M (886.8K / 120.4K / 13.93M) |
| `gpt-5.6-sol-ultra/` | Codex | `gpt-5.6-sol`, ultra | 2026-08-19 23:32:46–2026-08-20 00:25:15 | 52m 28s | Main agent plus 7 workers; 635 standard function-call records and 219 custom-tool-call records | 13% of GPT Pro Lite 5× subscription (user-reported) | 130.90M (3.71M / 366.5K / 126.82M) |
| `glm-5.3-openrouter-max/` | Pi | `z-ai/glm-5.3` via OpenRouter; max requested, high reported by Pi | 2026-08-20 07:35:52–07:38:25; 07:39:08–07:59:43 | 23m 08s | 116 assistant message records; 133 tool calls | US$3.88 (recorded) | 12.51M (301.7K / 68.7K / 12.13M) |
| `stealth-ox-alpha-openrouter-max/` | Pi | `stealth/ox-alpha` via OpenRouter; max requested, high reported by Pi | 2026-08-21 01:27:27–01:45:54 | 18m 27s | 103 assistant message records; 107 tool calls | US$3.16 (recorded) | 10.37M (1.54M / 73.6K / 8.76M) |

## Reference documents

- [Common prompt](PROMPT.md)
- [Grading rubric](GRADING_RUBRIC.md)
- [Detailed grading report](GRADING_REPORT.md)
- [Point-by-point grading ledger](GRADING_LEDGER.md)
- [Benchmark run protocol](BENCHMARK_RUN_PROTOCOL.md)
- [Sandbox methodology](SANDBOX_METHODOLOGY.md)

Runs used different harnesses and worker topologies—most notably, Sol Ultra used
one main agent plus seven workers—so the results compare complete agent systems,
not model weights alone. Candidate technical conclusions can also conflict; use
the individual reports and detailed grading report before relying on a claim.
