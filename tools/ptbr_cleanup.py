#!/usr/bin/env python3
"""Clean mechanical noise introduced by early PT-BR migration passes.

- restore generated localization expressions inside JS comments;
- restore generated localization expressions used as internal script setting
  values (settings.* comparisons are not game OCR text);
- restore each changed JS file's newline style to the version on origin/main;
- restore bettergi.d.ts newline style as well.

This script is deterministic and safe to run repeatedly.
"""

from __future__ import annotations

import codecs
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN_RE = re.compile(
    r'\(genshin\.getText \? genshin\.getText\("[^"\r\n]+"\) : "(?P<literal>[^"\r\n]+)"\)'
)
SETTINGS_LINE_RE = re.compile(r"\bsettings\.[A-Za-z_$][\w$]*")


def git_show_main(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"origin/main:{path}"], cwd=ROOT)


def decode(raw: bytes) -> tuple[str, bool]:
    bom = raw.startswith(codecs.BOM_UTF8)
    return raw.decode("utf-8-sig"), bom


def encode_like(text: str, base_raw: bytes, bom: bool) -> bytes:
    newline = "\r\n" if b"\r\n" in base_raw else "\n"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw = normalized.replace("\n", newline).encode("utf-8")
    return codecs.BOM_UTF8 + raw if bom else raw


def comment_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    quote: str | None = None
    escaped = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue

        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue

        if ch == "/" and nxt == "/":
            start = i
            end = text.find("\n", i + 2)
            if end == -1:
                end = n
            ranges.append((start, end))
            i = end
            continue

        if ch == "/" and nxt == "*":
            start = i
            end_token = text.find("*/", i + 2)
            end = n if end_token == -1 else end_token + 2
            ranges.append((start, end))
            i = end
            continue

        i += 1
    return ranges


def clean_comments(text: str) -> str:
    ranges = comment_ranges(text)
    if not ranges:
        return text

    pieces: list[str] = []
    cursor = 0
    for start, end in ranges:
        pieces.append(text[cursor:start])
        comment = text[start:end]
        comment = GEN_RE.sub(lambda m: f'"{m.group("literal")}"', comment)
        pieces.append(comment)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def clean_internal_settings(text: str) -> str:
    """Undo generated localization on lines comparing internal settings values."""
    lines = text.splitlines(keepends=True)
    cleaned: list[str] = []
    for line in lines:
        if SETTINGS_LINE_RE.search(line) and GEN_RE.search(line):
            line = GEN_RE.sub(lambda m: f'"{m.group("literal")}"', line)
        cleaned.append(line)
    return "".join(cleaned)


def changed_script_paths() -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", "repo/js", "bettergi.d.ts"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    return [line.strip() for line in output.splitlines() if line.strip()]


def main() -> int:
    changed = 0
    for rel in changed_script_paths():
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            base_raw = git_show_main(rel)
        except subprocess.CalledProcessError:
            continue

        current_raw = path.read_bytes()
        current_text, current_bom = decode(current_raw)
        cleaned = current_text
        if rel.endswith(".js"):
            cleaned = clean_comments(cleaned)
            cleaned = clean_internal_settings(cleaned)
        desired = encode_like(cleaned, base_raw, current_bom)
        if desired != current_raw:
            path.write_bytes(desired)
            changed += 1
            print(f"cleaned {rel}")

    print(f"PT-BR cleanup changed {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
