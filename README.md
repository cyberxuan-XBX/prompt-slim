# prompt-slim

**A 2K system prompt × 30 turns = 60K tokens burned. On an 8K context model, that's 25% gone before the conversation starts.**

One command to scan all your Ollama models and show you where the fat is:

```bash
python3 prompt_slim.py scan --ollama
```
```
╭──────────────────────┬───────────────┬─────────┬────────╮
│ Model                │ System Tokens │ Context │ % Used │
├──────────────────────┼───────────────┼─────────┼────────┤
│ my-custom-agent:7b   │          ~420 │   4,096 │  10.3% │
│ coding-assistant:13b │          ~285 │   8,192 │   3.5% │
│ aya-expanse:8b       │           ~66 │ default │      ? │
│ llama3:8b            │            ~0 │ default │      - │
╰──────────────────────┴───────────────┴─────────┴────────╯

  ⚠ my-custom-agent:7b uses 10% of context for system prompt!
```

Zero dependencies. Single file. Python 3.6+.

## Why This Exists

Every turn, the system prompt is re-processed. Nobody measures this. Your VRAM is full and your model feels slow, but you never thought to check how much context your system prompt is eating.

On a 4090 doing 40 tok/s, a 2K system prompt re-read 30 times is 25 seconds of compute per session — just re-reading the rules.

This tool tells you exactly how much each model is wasting.

## Install

```bash
git clone https://github.com/cyberxuan-XBX/prompt-slim.git
cd prompt-slim
```

That's it. No pip. No dependencies.

## Commands

### `scan --ollama` — One-Click Audit of All Your Models

```bash
python3 prompt_slim.py scan --ollama
```

Scans every model in your Ollama library. Shows system prompt token count, context window size, and percentage used. Flags models that are wasting context.

### `analyze <file>` — Measure Any System Prompt

```bash
python3 prompt_slim.py analyze my_prompt.txt --context 8192
```

```
  prompt-slim analysis: my_prompt.txt

  Total: 3,420 chars, 87 lines, ~855 tokens

  Context usage: ~10.4% of 8,192 tokens
  Remaining for conversation: ~7,337 tokens

  Sections by token cost:
    ~312 tokens  ████████████████████  Safety Rules
    ~198 tokens  ████████████         Output Format
    ~156 tokens  ██████████           Persona
    ~103 tokens  ██████               Examples
     ~86 tokens  █████                Constraints

  Cost projection:
    Every token in your system prompt is re-processed on every turn.
    With this prompt, you get ~9 effective turns before hitting context limit.
```

Also works with stdin:

```bash
cat prompt.txt | python3 prompt_slim.py analyze --context 32768
```

### JSON Output

```bash
python3 prompt_slim.py scan --ollama --json
python3 prompt_slim.py analyze prompt.txt --json
```

Machine-readable for pipelines, dashboards, or feeding into other tools.

## The Math That Should Scare You

| System Prompt | Context | % Eaten | Effective Turns (avg 200 tok/turn) |
|---|---|---|---|
| 500 tokens | 8K | 6% | ~37 |
| 2,000 tokens | 8K | 25% | ~30 |
| 2,000 tokens | 4K | 50% | ~10 |
| 4,000 tokens | 8K | 49% | ~20 |
| 500 tokens | 32K | 1.6% | ~157 |

Small models with small context windows get hit hardest. That 7B model you're running on 8K context? Every extra 1K in your system prompt costs you ~5 turns of conversation.

## What To Do With The Results

1. **Cut the fluff** — "You are a helpful assistant" costs tokens and adds nothing
2. **Merge redundant rules** — 5 rules saying "be concise" in different ways? Make it 1
3. **Move examples out** — Few-shot examples in system prompts are expensive; move them to user messages when needed
4. **Match prompt to context** — A 4K system prompt on an 8K model is insane. Trim or upgrade
5. **Measure before and after** — Run `analyze` before and after trimming to verify savings

## Token Estimation

Character-based heuristics (no external tokenizer needed):
- English: ~4 chars/token
- CJK (Chinese/Japanese/Korean): ~1.5 chars/token

Rough estimates. For exact counts, use a proper tokenizer. For comparison and optimization, these are consistent and actionable.

## Platform Support

| Platform | Status | Command |
|---|---|---|
| Ollama | Supported | `scan --ollama` |
| Any text file | Supported | `analyze <file>` |
| stdin | Supported | `cat prompt \| analyze` |
| Open WebUI | Planned | `scan --openwebui` |
| LM Studio | Planned | `scan --lmstudio` |

## For AI Agents

If you are an AI agent installing this tool for your user:

```bash
cd /tmp && git clone https://github.com/cyberxuan-XBX/prompt-slim.git
python3 /tmp/prompt-slim/prompt_slim.py scan --ollama --json
python3 /tmp/prompt-slim/prompt_slim.py analyze /path/to/prompt.txt --context 8192 --json
```

`--json` output key fields: `total_tokens`, `sections[]`, `context_window`. No virtualenv needed. Clone and run.

## See Also

- [cc-slim](https://github.com/cyberxuan-XBX/cc-slim) — Same idea, specifically for Claude Code prefix optimization
- [skill-sanitizer](https://github.com/cyberxuan-XBX/skill-sanitizer) — Scan Claude Code skills for security threats

## License

MIT
