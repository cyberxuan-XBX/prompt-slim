# prompt-slim

**Your system prompt is eating your context window. This tool shows you how much.**

## Why This Exists

You gave your local LLM a 2,000-token system prompt. Your model has an 8K context window. That's 25% gone before the user says a word.

Every turn, the system prompt is re-processed. A 2K system prompt × 30 turns = 60K tokens of compute burned on instructions your model already "knows." On a 4090 doing 40 tok/s, that's 25 seconds of your life per session, just re-reading the rules.

Nobody measures this. Nobody optimizes it. Your VRAM is full and you don't know why your model feels slow.

This tool tells you exactly where the fat is.

## Quick Start

```bash
# Clone and run (zero dependencies, Python 3.6+)
git clone https://github.com/cyberxuan-XBX/prompt-slim.git
cd prompt-slim

# Analyze any system prompt file
python3 prompt_slim.py analyze my_system_prompt.txt --context 8192

# Pipe from stdin
cat prompt.txt | python3 prompt_slim.py analyze --context 32768

# Scan all your Ollama models at once
python3 prompt_slim.py scan --ollama
```

No pip install. No dependencies. Just Python.

## Commands

### `prompt-slim analyze <file>` — Measure Any System Prompt

Feed it any text file containing a system prompt. It tells you:
- Token count (estimated)
- Section-by-section breakdown with visual bars
- Context window usage percentage (with `--context N`)
- How many effective turns you get before hitting the limit

```
$ python3 prompt_slim.py analyze my_prompt.txt --context 8192

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

### `prompt-slim scan --ollama` — Scan All Ollama Models

Scans every model in your Ollama library and reports system prompt sizes:

```
$ python3 prompt_slim.py scan --ollama

╭──────────────────────┬───────────────┬─────────┬────────╮
│ Model                │ System Tokens │ Context │ % Used │
├──────────────────────┼───────────────┼─────────┼────────┤
│ my-custom-agent:7b   │          ~420 │   4,096 │  10.3% │
│ coding-assistant:13b │          ~285 │   8,192 │   3.5% │
│ aya-expanse:8b       │           ~66 │ default │      ? │
│ qwen2.5:14b          │           ~17 │ default │      - │
│ llama3:8b            │            ~0 │ default │      - │
╰──────────────────────┴───────────────┴─────────┴────────╯

  ⚠ my-custom-agent:7b uses 10% of context for system prompt!
```

### JSON Output

```bash
python3 prompt_slim.py analyze prompt.txt --json
python3 prompt_slim.py scan --ollama --json
```

Machine-readable output for pipelines, dashboards, or feeding into other tools.

## The Math That Should Scare You

| System Prompt | Context | % Eaten | Effective Turns (avg 200 tok/turn) |
|---|---|---|---|
| 500 tokens | 8K | 6% | ~37 |
| 2,000 tokens | 8K | 25% | ~30 |
| 2,000 tokens | 4K | 50% | ~10 |
| 4,000 tokens | 8K | 49% | ~20 |
| 500 tokens | 32K | 1.6% | ~157 |

Small models with small context windows get hit hardest. That 7B model you're running on 8K context? Every extra 1K in your system prompt costs you ~5 turns of conversation.

## Token Estimation

prompt-slim uses character-based heuristics (no external tokenizer needed):
- English: ~4 chars/token
- CJK (Chinese/Japanese/Korean): ~1.5 chars/token
- Mixed content: weighted average

These are estimates. For exact counts, use a proper tokenizer. But for comparison and optimization, the numbers are consistent and actionable.

## What To Do With The Results

1. **Cut the fluff** — "You are a helpful assistant" costs tokens and adds nothing most models don't already do
2. **Merge redundant rules** — 5 rules saying "be concise" in different ways? Make it 1
3. **Move examples out** — Few-shot examples in system prompts are expensive; consider moving them to user messages only when needed
4. **Match prompt to context** — A 4K-token system prompt on an 8K model is insane. Trim or upgrade
5. **Measure before and after** — Run `prompt-slim analyze` before and after trimming to verify savings

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
# Install
cd /tmp && git clone https://github.com/cyberxuan-XBX/prompt-slim.git

# Scan Ollama (if available)
python3 /tmp/prompt-slim/prompt_slim.py scan --ollama

# Analyze a specific prompt
python3 /tmp/prompt-slim/prompt_slim.py analyze /path/to/system_prompt.txt --context 8192 --json
```

The `--json` flag gives you structured output you can parse directly. Key fields:
- `total_tokens`: estimated token count
- `sections[]`: per-section breakdown
- `context_window`: the context size you specified

No dependencies to install. No virtualenv needed. Just clone and run.

## See Also

- [cc-slim](https://github.com/cyberxuan-XBX/cc-slim) — Same idea, specifically for Claude Code prefix optimization
- [skill-sanitizer](https://github.com/cyberxuan-XBX/skill-sanitizer) — Scan Claude Code skills for security threats

## License

MIT
