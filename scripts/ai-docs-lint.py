#!/usr/bin/env python3
"""Enforce the AI-guide size caps (from adityaduggal/ai-coding claude-md-lint.py).

    python3 scripts/ai-docs-lint.py

Checks that AGENTS.md is at most --max-chars characters, and that each
.claude/skills/*/SKILL.md is at most --max-skill-lines lines. Exits 0 when
all caps hold and 1 when one fails. No third-party dependencies.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--max-chars", type=int, default=500)
	parser.add_argument("--max-skill-lines", type=int, default=500)
	args = parser.parse_args()

	failed = False
	agents = ROOT / "AGENTS.md"
	if agents.exists():
		chars = len(agents.read_text(encoding="utf-8"))
		ok = chars <= args.max_chars
		failed |= not ok
		print(f"ai-docs-lint: AGENTS.md {chars}/{args.max_chars} chars {'OK' if ok else 'OVER'}")

	for skill in sorted(ROOT.glob(".claude/skills/*/SKILL.md")):
		lines = sum(1 for _ in skill.open(encoding="utf-8"))
		ok = lines <= args.max_skill_lines
		failed |= not ok
		print(f"ai-docs-lint: {skill.relative_to(ROOT)} {lines}/{args.max_skill_lines} lines {'OK' if ok else 'OVER'}")

	if failed:
		print("Move content to docs/ai/ and leave a pointer instead.")
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
