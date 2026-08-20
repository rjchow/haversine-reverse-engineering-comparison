# Run metadata

All five agents received the same byte-identical brief, preserved in [`PROMPT.md`](PROMPT.md). Times below are UTC and cover only the original reverse-engineering effort begun from that brief; later related follow-ups are excluded.

| Deliverable directory | Session system | Model and reasoning | Original RE activity window(s) | Active elapsed | Recorded activity |
|---|---|---|---|---|---|
| `qwen3.8-27b-local-4bit/` | Pi | `qwen38-27b-optimized` (local Qwen 3.8 27B), xhigh | 2026-08-19 05:17:08–15:01:02 | 9h 43m 54s | 233 assistant message records; 229 tool calls |
| `gpt-5.6-luna-xhigh/` | Pi | `gpt-5.6-luna`, xhigh | 2026-08-19 13:13:42–13:47:24 | 33m 42s | 176 assistant message records; 175 tool calls |
| `qwen3.8-2.4t-openrouter/` | Pi | `qwen/qwen3.8-2.4t-a95b` via OpenRouter, xhigh | 2026-08-19 14:53:10–16:05:01; 23:03:49–23:12:29 | 1h 20m 31s | 131 assistant message records; 135 tool calls |
| `gpt-5.6-sol-ultra/` | Codex | `gpt-5.6-sol`, ultra | 2026-08-19 23:32:46–2026-08-20 00:25:15 | 52m 28s | Main agent plus 7 workers; 635 standard function-call records and 219 custom-tool-call records |
| `glm-5.3-openrouter-max/` | Pi | `z-ai/glm-5.3` via OpenRouter; max requested, high reported by Pi | 2026-08-20 07:35:52–07:38:25; 07:39:08–07:59:43 | 23m 08s | 116 assistant message records; 133 tool calls |
