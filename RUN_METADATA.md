# Run metadata

All four agents received the same byte-identical brief, preserved in [`PROMPT.md`](PROMPT.md). The Sol run also received the operating instruction to read that brief, begin work, and maintain a durable progress log. Times below are UTC and are derived from the available Pi/Codex session metadata; they are wall-clock spans, not billed runtime.

| Deliverable directory | Session system | Model and reasoning | Main run span | Recorded activity |
|---|---|---|---|---|
| `qwen3.8-27b-local-4bit/` | Pi | `qwen38-27b-optimized` (local Qwen 3.8 27B), xhigh | 2026-08-19 05:16:50 to 2026-08-20 02:34:48 (21h 17m 58s) | 239 assistant message records; 234 tool calls and matching results |
| `gpt-5.6-luna-xhigh/` | Pi | `gpt-5.6-luna`, xhigh | 2026-08-19 13:13:26 to 14:27:41 (1h 14m 15s) | 253 assistant message records; 250 tool calls and matching results |
| `qwen3.8-2.4t-openrouter/` | Pi | `qwen/qwen3.8-2.4t-a95b` via OpenRouter, xhigh | 2026-08-19 14:52:55 to 23:12:29 (8h 19m 34s) | 136 assistant message records; 136 tool calls and matching results |
| `gpt-5.6-sol-ultra/` | Codex | `gpt-5.6-sol`, ultra | 2026-08-19 23:05:35 to 2026-08-20 02:34:39 (3h 29m 04s) | Main agent plus 10 workers; 782 standard function-call records and 244 custom-tool-call records across the run |

## Interpretation notes

- The Luna task session was initialized under the local Qwen configuration and switched to Luna 22 seconds later, before substantive task activity. Its statistics cover the full task session.
- A short Luna preflight occurred in the OpenRouter folder before the Qwen 2.4T session that generated the retained deliverables. It is not presented as a fifth comparison run.
- The Sol run used concurrent workers, so its aggregate tool-record count should not be compared one-for-one with the single-agent Pi counts.
- Session identifiers, raw prompts beyond the common brief, logs, machine paths, and any authentication material have deliberately been omitted.
