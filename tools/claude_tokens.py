#!/usr/bin/env python3
"""Count Claude Code tokens from local session transcripts and emit a shields.io badge.

Claude Code writes one JSONL per session under ~/.claude/projects, and every
assistant message carries the usage counters the API returned. Nothing here
talks to a network: it reads what is already on this machine.

  python3 tools/claude_tokens.py            # refresh the badge JSON
  python3 tools/claude_tokens.py --print    # just show the numbers

A note on the headline figure. "Tokens" is four different things:

  output       what Claude actually generated
  input        fresh context sent up
  cache write  context stored for reuse
  cache read   that stored context read back on later turns

Cache reads dominate by two orders of magnitude - they are the same context
re-read every turn, not new work. The badge shows the total because that is
what "tokens processed" means, and the JSON carries the split so the label can
be pointed at any one of them instead.
"""
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC  = pathlib.Path.home() / ".claude/projects"
OUT  = ROOT / "claude-tokens.json"

FIELDS = {
    "output":      "output_tokens",
    "input":       "input_tokens",
    "cache_write": "cache_creation_input_tokens",
    "cache_read":  "cache_read_input_tokens",
}

def human(n):
    for lim, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= lim:
            v = n / lim
            return f"{v:.1f}{suf}" if v < 100 else f"{v:.0f}{suf}"
    return str(n)

def count():
    tot = dict.fromkeys(FIELDS, 0)
    seen, msgs, files = set(), 0, 0
    if not SRC.exists():
        return tot, msgs, files
    for f in SRC.rglob("*.jsonl"):
        files += 1
        try:
            fh = open(f, errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                m = d.get("message") or {}
                u = m.get("usage")
                if not isinstance(u, dict):
                    continue
                # A resumed session replays earlier turns into the new
                # transcript, so the same message id lands in two files.
                key = m.get("id") or d.get("uuid")
                if key:
                    if key in seen:
                        continue
                    seen.add(key)
                msgs += 1
                for name, field in FIELDS.items():
                    tot[name] += u.get(field) or 0
    return tot, msgs, files

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", dest="show")
    a = ap.parse_args()

    tot, msgs, files = count()
    grand = sum(tot.values())

    if a.show:
        for k, v in tot.items():
            print(f"  {k:12s} {v:>18,}")
        print(f"  {'total':12s} {grand:>18,}   ({msgs:,} messages in {files:,} sessions)")
        return

    OUT.write_text(json.dumps({
        "schemaVersion": 1,
        "label": "Claude tokens",
        "message": human(grand),
        "color": "D97757",
        "labelColor": "1a1a1a",
        "style": "flat",
        # Not read by shields.io - kept so the split stays visible in the repo.
        "_breakdown": tot,
        "_messages": msgs,
        "_sessions": files,
    }, indent=2) + "\n")
    print(f"{OUT.name}: {human(grand)}  ({grand:,} across {msgs:,} messages)")

main()
