#!/usr/bin/env python3
"""
prompt-slim: Analyze and measure your LLM system prompts.

Works with any LLM. Supports Ollama Modelfile scanning.
Zero dependencies. Python 3.6+.
"""

import argparse
import os
import sys
import re
import json
import subprocess
from pathlib import Path


__version__ = "0.1.0"

# ── Token estimation ─────────────────────────────────────────────────────────

RATIO_EN = 4.0     # ~4 English chars per token
RATIO_CJK = 1.5    # ~1.5 CJK chars per token

CJK_RE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef"
    r"\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
)


def estimate_tokens(text):
    """Estimate token count from text using char-based heuristics."""
    if not text:
        return 0
    cjk_chars = len(CJK_RE.findall(text))
    other_chars = len(text) - cjk_chars
    tokens = cjk_chars / RATIO_CJK + other_chars / RATIO_EN
    return max(1, int(round(tokens)))


def fmt(n):
    """Format number with comma separators."""
    return "{:,}".format(n)


# ── Box drawing ──────────────────────────────────────────────────────────────

def print_table(rows, headers, col_aligns=None):
    """Print a table with box-drawing characters."""
    num_cols = len(headers)
    if col_aligns is None:
        col_aligns = ["l"] + ["r"] * (num_cols - 1)

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    widths = [w + 2 for w in widths]

    def hline(left, mid, right, fill="\u2500"):
        return left + mid.join(fill * w for w in widths) + right

    def data_line(cells):
        parts = []
        for i, cell in enumerate(cells):
            s = str(cell)
            if col_aligns[i] == "r":
                parts.append(s.rjust(widths[i] - 1) + " ")
            else:
                parts.append(" " + s.ljust(widths[i] - 1))
        return "\u2502" + "\u2502".join(parts) + "\u2502"

    print(hline("\u256d", "\u252c", "\u256e"))
    print(data_line(headers))
    print(hline("\u251c", "\u253c", "\u2524"))
    for row in rows:
        print(data_line(row))
    print(hline("\u2570", "\u2534", "\u256f"))


# ── Text analysis ────────────────────────────────────────────────────────────

def analyze_text(text, label="input"):
    """Analyze a system prompt text and return metrics."""
    lines = text.split("\n")
    chars = len(text)
    tokens = estimate_tokens(text)

    # Detect sections (markdown headers or blank-line-separated blocks)
    sections = []
    current_section = {"name": "(top)", "start": 0, "lines": []}
    for i, line in enumerate(lines):
        if line.startswith("#"):
            if current_section["lines"]:
                sections.append(current_section)
            current_section = {"name": line.lstrip("#").strip(), "start": i, "lines": []}
        current_section["lines"].append(line)
    if current_section["lines"]:
        sections.append(current_section)

    # Classify sections by content
    section_data = []
    for sec in sections:
        sec_text = "\n".join(sec["lines"])
        sec_tokens = estimate_tokens(sec_text)
        section_data.append({
            "name": sec["name"][:40],
            "lines": len(sec["lines"]),
            "chars": len(sec_text),
            "tokens": sec_tokens,
        })

    return {
        "label": label,
        "total_chars": chars,
        "total_lines": len(lines),
        "total_tokens": tokens,
        "sections": section_data,
    }


def print_analysis(result, context_window=None):
    """Print analysis results."""
    print()
    print("  prompt-slim analysis: {}".format(result["label"]))
    print()
    print("  Total: {} chars, {} lines, ~{} tokens".format(
        fmt(result["total_chars"]),
        fmt(result["total_lines"]),
        fmt(result["total_tokens"]),
    ))

    if context_window:
        pct = result["total_tokens"] / context_window * 100
        remaining = context_window - result["total_tokens"]
        print()
        print("  Context usage: ~{:.1f}% of {:,} tokens".format(pct, context_window))
        print("  Remaining for conversation: ~{} tokens".format(fmt(remaining)))
        if pct > 30:
            print("  \u26a0 Your system prompt uses over 30% of context — consider trimming.")

    if result["sections"] and len(result["sections"]) > 1:
        print()
        print("  Sections by token cost:")
        sorted_secs = sorted(result["sections"], key=lambda s: s["tokens"], reverse=True)
        for i, sec in enumerate(sorted_secs[:10]):
            bar_len = max(1, int(sec["tokens"] / max(s["tokens"] for s in sorted_secs) * 20))
            bar = "\u2588" * bar_len
            print("    {:>5} tokens  {}  {}".format(
                "~" + fmt(sec["tokens"]),
                bar,
                sec["name"] if sec["name"] else "(unnamed)",
            ))

    # Cost projection
    print()
    print("  Cost projection:")
    print("    Every token in your system prompt is re-processed on every turn.")
    if context_window:
        effective_turns = context_window // max(1, result["total_tokens"])
        print("    With this prompt, you get ~{} effective turns before hitting context limit.".format(
            effective_turns))
    print()


# ── Ollama scanner ───────────────────────────────────────────────────────────

def scan_ollama():
    """Scan Ollama models for system prompts."""
    try:
        out = subprocess.check_output(
            ["ollama", "list"], stderr=subprocess.DEVNULL, timeout=10
        ).decode("utf-8", errors="replace")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("Error: Could not run 'ollama list'. Is Ollama installed and running?",
              file=sys.stderr)
        sys.exit(1)

    models = []
    for line in out.strip().split("\n")[1:]:  # skip header
        parts = line.split()
        if parts:
            models.append(parts[0])

    if not models:
        print("No Ollama models found.", file=sys.stderr)
        sys.exit(1)

    results = []
    for model in models:
        try:
            mf = subprocess.check_output(
                ["ollama", "show", model, "--modelfile"],
                stderr=subprocess.DEVNULL, timeout=10,
            ).decode("utf-8", errors="replace")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue

        system_prompt = extract_ollama_system(mf)
        num_ctx = extract_ollama_param(mf, "num_ctx")

        results.append({
            "model": model,
            "system_prompt": system_prompt,
            "system_chars": len(system_prompt),
            "system_tokens": estimate_tokens(system_prompt),
            "num_ctx": num_ctx,
        })

    return results


def extract_ollama_system(modelfile_text):
    """Extract SYSTEM prompt from Ollama Modelfile content."""
    lines = modelfile_text.split("\n")
    system_lines = []
    in_system = False
    in_multiline = False

    for line in lines:
        if line.startswith("SYSTEM "):
            rest = line[7:]
            if rest.startswith('"""'):
                # Multi-line system prompt
                content = rest[3:]
                if content.endswith('"""') and len(content) > 3:
                    system_lines.append(content[:-3])
                else:
                    system_lines.append(content)
                    in_multiline = True
            else:
                system_lines.append(rest)
        elif in_multiline:
            if line.endswith('"""'):
                system_lines.append(line[:-3])
                in_multiline = False
            else:
                system_lines.append(line)

    return "\n".join(system_lines).strip()


def extract_ollama_param(modelfile_text, param_name):
    """Extract a PARAMETER value from Ollama Modelfile."""
    for line in modelfile_text.split("\n"):
        if line.startswith("PARAMETER " + param_name):
            parts = line.split()
            if len(parts) >= 3:
                try:
                    return int(parts[2])
                except ValueError:
                    try:
                        return float(parts[2])
                    except ValueError:
                        return parts[2]
    return None


def cmd_scan_ollama(args):
    """Scan all Ollama models and report system prompt sizes."""
    output_json = getattr(args, "json", False)
    results = scan_ollama()

    if output_json:
        print(json.dumps({"version": __version__, "models": results},
                         indent=2, ensure_ascii=False))
        return

    print()
    print("  prompt-slim: Ollama model scan")
    print()

    # Summary table
    table_rows = []
    for r in sorted(results, key=lambda x: x["system_tokens"], reverse=True):
        ctx_str = fmt(r["num_ctx"]) if r["num_ctx"] else "default"
        if r["system_tokens"] == 0:
            pct_str = "-"
        elif r["num_ctx"]:
            pct_str = "{:.1f}%".format(r["system_tokens"] / r["num_ctx"] * 100)
        else:
            pct_str = "?"
        # Truncate long model names
        model_name = r["model"]
        if len(model_name) > 35:
            model_name = "..." + model_name[-32:]
        table_rows.append((
            model_name,
            "~" + fmt(r["system_tokens"]),
            ctx_str,
            pct_str,
        ))

    if table_rows:
        print_table(
            table_rows,
            ["Model", "System Tokens", "Context", "% Used"],
            ["l", "r", "r", "r"],
        )

    # Warnings
    has_prompt = [r for r in results if r["system_tokens"] > 0]
    no_prompt = [r for r in results if r["system_tokens"] == 0]

    if has_prompt:
        print()
        print("  {} model(s) with system prompts.".format(len(has_prompt)))
        for r in sorted(has_prompt, key=lambda x: x["system_tokens"], reverse=True):
            if r["num_ctx"] and r["system_tokens"] / r["num_ctx"] > 0.3:
                print("  \u26a0 {} uses {:.0f}% of context for system prompt!".format(
                    r["model"],
                    r["system_tokens"] / r["num_ctx"] * 100,
                ))

    if no_prompt:
        print("  {} model(s) with no system prompt (using defaults).".format(len(no_prompt)))

    # Detail for models with prompts
    if has_prompt and not output_json:
        print()
        for r in sorted(has_prompt, key=lambda x: x["system_tokens"], reverse=True)[:5]:
            preview = r["system_prompt"][:100].replace("\n", " ")
            if len(r["system_prompt"]) > 100:
                preview += "..."
            print('  {}: "{}"'.format(r["model"], preview))

    print()


# ── Analyze command ──────────────────────────────────────────────────────────

def cmd_analyze(args):
    """Analyze a system prompt from file or stdin."""
    output_json = getattr(args, "json", False)

    if args.file == "-" or (args.file is None and not sys.stdin.isatty()):
        text = sys.stdin.read()
        label = "stdin"
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            label = args.file
        except (OSError, IOError) as e:
            print("Error: {}".format(e), file=sys.stderr)
            sys.exit(1)
    else:
        print("Usage: prompt-slim analyze <file>  or  cat prompt.txt | prompt-slim analyze",
              file=sys.stderr)
        sys.exit(1)

    if not text.strip():
        print("Error: Empty input.", file=sys.stderr)
        sys.exit(1)

    context_window = getattr(args, "context", None)
    result = analyze_text(text, label=label)

    if output_json:
        result["context_window"] = context_window
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print_analysis(result, context_window=context_window)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="prompt-slim",
        description="Analyze and measure your LLM system prompts.",
    )
    parser.add_argument("--version", action="version",
                        version="prompt-slim {}".format(__version__))

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze a system prompt file")
    analyze_parser.add_argument("file", nargs="?", default=None,
                                help="Path to system prompt file (or - for stdin)")
    analyze_parser.add_argument("--context", type=int, default=None,
                                help="Context window size (e.g. 8192, 32768)")
    analyze_parser.add_argument("--json", action="store_true",
                                help="Output as JSON")

    # scan
    scan_parser = subparsers.add_parser(
        "scan", help="Scan LLM platforms for system prompts")
    scan_parser.add_argument("--ollama", action="store_true",
                             help="Scan Ollama models")
    scan_parser.add_argument("--json", action="store_true",
                             help="Output as JSON")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "scan":
        if getattr(args, "ollama", False):
            cmd_scan_ollama(args)
        else:
            print("Specify a platform to scan. Available: --ollama", file=sys.stderr)
            print("More platforms coming soon.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
