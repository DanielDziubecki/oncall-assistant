"""Remove ids and account usage from Pi's JSON output, so a run can be kept as a sample.

Usage: python scrub_pi_samples.py <in.jsonl> <out.jsonl>

Ids keep their prefix and length, with every other character replaced by 0. Rate-limit
numbers become 0. Everything else stays byte for byte. If the result still looks like it holds
an email address or a token, nothing is written and the exit code is 1.
"""

import json
import re
import sys
from pathlib import Path

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_PREFIXED_ID = re.compile(r"\b(msg|req|resp|toolu|call|fc)_([A-Za-z0-9]{16,})")
_USAGE_NUMBER = re.compile(r'"(utilization|resetsAt|overageResetsAt)":-?[0-9.eE+-]+')
_USAGE_REASON = re.compile(r'"overageDisabledReason":"[^"]*"')

_LEFTOVERS = {
    "email address": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "Anthropic key or token": re.compile(r"sk-ant-|oat01-"),
    "OpenAI key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "bearer token": re.compile(r"Bearer [A-Za-z0-9._~+/-]{10,}"),
    "JSON web token": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ"),
}


def _zero_id(match: re.Match[str]) -> str:
    return f"{match.group(1)}_{'0' * len(match.group(2))}"


def scrub(text: str) -> str:
    """Returns the text with ids and account usage replaced."""
    text = _UUID.sub("00000000-0000-0000-0000-000000000000", text)
    text = _PREFIXED_ID.sub(_zero_id, text)
    text = _USAGE_NUMBER.sub(lambda m: f'"{m.group(1)}":0', text)
    return _USAGE_REASON.sub('"overageDisabledReason":"sample"', text)


def leftovers(text: str) -> list[str]:
    """Names what in the text still looks like personal data or a credential."""
    return [name for name, pattern in _LEFTOVERS.items() if pattern.search(text)]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    source, target = Path(argv[0]), Path(argv[1])
    text = scrub(source.read_text(encoding="utf-8"))
    for line in text.splitlines():
        json.loads(line)
    found = leftovers(text)
    if found:
        print(f"not written, still holds: {', '.join(found)}", file=sys.stderr)
        return 1
    target.write_text(text, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
