# Run metadata

Run label: **the second run of local qwen 3.8 27b 4 bit for verification**

| Field | Value |
|---|---|
| Run ID | `qwen3.8-27b-local-4bit-verification-2` |
| Session system | Pi; version not recorded in the session |
| Provider | Local vLLM endpoint; its machine-specific session alias is omitted |
| Model | `qwen38-27b-optimized` (local Qwen 3.8 27B, 4-bit quantization) |
| Reasoning | `xhigh` requested and reported |
| Topology | Single agent; no workers or subagents |
| Extensions/context | Extensions, skills, and context-file discovery disabled |
| Common brief SHA-256 | `941cb0d94c37b5ac9373faaa431ec149e962137768db92a4c55d76420babbaf4` |
| Comparison base commit | `ab6bab36cf7ffaf786d7591ac003df5df2e9f8b7` |
| Grading rubric SHA-256 | `8b97fe53f336a75eb312de4fde003a6c554411a92cbb1bc9880fd7cffef23236` |
| Original research windows | 2026-08-21 13:25:50.775–17:32:48.201; 18:09:03.005–20:32:31.280; 20:40:45.421–21:42:07.472 |
| Active elapsed | 7h 31m 47.752s |
| Recorded activity | 203 assistant message records; 207 tool calls |
| Tokens | 20,310,644 total: 20,080,809 new input; 229,835 output; 0 cache read |
| Cost | Not measured (local inference) |

Initial user message:

```text
read the brief and start work. log your progress as you go along so that we can review the progress and track the outstanding task and so that you don't lose progress when context is compacted
```

The three windows retain the complete original research. Four zero-usage
terminated responses between the first two windows and one zero-usage aborted
response between the last two windows are excluded. The two user messages that
resumed the same task did not change its scope. Authored date labels in the
progress log were not used for accounting; raw session timestamps define the
windows. Raw session records, the machine-specific sandbox profile, downloaded
binaries, extracted archives, and host-specific paths are intentionally not
published.
