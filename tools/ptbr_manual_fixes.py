#!/usr/bin/env python3
"""Targeted, idempotent PT-BR fixes where language-independent logic is safer than translation."""
from __future__ import annotations

import codecs
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEYLINE = ROOT / "repo" / "js" / "AutoLeyLineOutcrop" / "utils" / "attemptReward.js"


def read(path: Path):
    raw = path.read_bytes()
    return raw.decode("utf-8-sig"), raw, raw.startswith(codecs.BOM_UTF8)


def write_like(path: Path, text: str, raw: bytes, bom: bool):
    newline = "\r\n" if b"\r\n" in raw else "\n"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    data = normalized.replace("\n", newline).encode("utf-8")
    path.write_bytes((codecs.BOM_UTF8 if bom else b"") + data)


def replace_literal(text: str, old: str, new: str) -> str:
    return text.replace(old, new)


def patch_leyline(text: str) -> str:
    # Remaining double-reward count is the only number in the dedicated OCR ROI.
    text = text.replace(
        'const match = texts[i].text.match(/2倍产出次数[:：]?(\\d+)/);',
        'const match = texts[i].text.match(/(\\d+)/);'
    )

    # The Chinese classifier 个 is not part of PT-BR. The number plus the
    # localized full resin name is enough and is more robust in every language.
    text = text.replace(
        'if ((text.includes("20") || text.includes("20个")) && text.includes((genshin.getText ? genshin.getText("original_resin") : "原粹树脂"))) {',
        'if (text.includes("20") && text.includes((genshin.getText ? genshin.getText("original_resin") : "原粹树脂"))) {'
    )
    text = text.replace(
        'if ((text.includes("40") || text.includes("40个")) && text.includes((genshin.getText ? genshin.getText("original_resin") : "原粹树脂"))) {',
        'if (text.includes("40") && text.includes((genshin.getText ? genshin.getText("original_resin") : "原粹树脂"))) {'
    )

    old_verify = '''    return texts.some(t =>
        (t.text.includes(targetAmount.toString()) && t.text.includes("原粹")) ||
        (t.text.includes(`${targetAmount}个`) && t.text.includes("树脂"))
    );'''
    new_verify = '''    const originalResin = genshin.getText ? genshin.getText("original_resin") : "原粹树脂";
    return texts.some(t => t.text.includes(targetAmount.toString()) && t.text.includes(originalResin));'''
    text = text.replace(old_verify, new_verify)

    # Full localized names supersede the Chinese-only partial-name fallbacks.
    text = text.replace(
        'genshin.textContainsLiteral(t.text, "浓缩树脂") : t.text.includes("浓缩树脂")) || t.text.includes("浓缩"))',
        'genshin.textContainsLiteral(t.text, "浓缩树脂") : t.text.includes("浓缩树脂")))'
    )
    text = text.replace(
        'genshin.textContainsLiteral(t.text, "须臾树脂") : t.text.includes("须臾树脂")) || t.text.includes("须臾"))',
        'genshin.textContainsLiteral(t.text, "须臾树脂") : t.text.includes("须臾树脂")))'
    )
    text = text.replace(
        'genshin.textContainsLiteral(t.text, "脆弱树脂") : t.text.includes("脆弱树脂")) || t.text.includes("脆弱"))',
        'genshin.textContainsLiteral(t.text, "脆弱树脂") : t.text.includes("脆弱树脂")))'
    )

    # Primogem option needs only the visible count 3 plus the localized item name.
    text = text.replace(
        't.text.includes((genshin.getTextLiteral ? genshin.getTextLiteral("原石") : "原石")) && t.text.includes("3次")',
        't.text.includes((genshin.getTextLiteral ? genshin.getTextLiteral("原石") : "原石")) && t.text.includes("3")'
    )

    # Plain local variable equality is not recognized by the generic migration tool.
    text = text.replace(
        'if (text === "使用") {',
        'if (genshin.textEqualsLiteral ? genshin.textEqualsLiteral(text, "使用") : text === "使用") {'
    )

    # Remove classifier-only duplicates after TextMap wrappers were generated.
    text = re.sub(
        r'\(t\.text\.includes\("20"\)\s*\|\|\s*\(genshin\.textContainsLiteral \? genshin\.textContainsLiteral\(t\.text, "20个"\) : t\.text\.includes\("20个"\)\)\)',
        't.text.includes("20")', text
    )
    text = re.sub(
        r'\(t\.text\.includes\("40"\)\s*\|\|\s*\(genshin\.textContainsLiteral \? genshin\.textContainsLiteral\(t\.text, "40个"\) : t\.text\.includes\("40个"\)\)\)',
        't.text.includes("40")', text
    )
    text = re.sub(
        r'\(text\.includes\("20"\)\s*\|\|\s*\(genshin\.textContainsLiteral \? genshin\.textContainsLiteral\(text, "20个"\) : text\.includes\("20个"\)\)\)',
        'text.includes("20")', text
    )
    text = re.sub(
        r'\(text\.includes\("40"\)\s*\|\|\s*\(genshin\.textContainsLiteral \? genshin\.textContainsLiteral\(text, "40个"\) : text\.includes\("40个"\)\)\)',
        'text.includes("40")', text
    )

    return text


def main() -> int:
    changed = []
    for path, patcher in ((LEYLINE, patch_leyline),):
        text, raw, bom = read(path)
        updated = patcher(text)
        if updated != text:
            write_like(path, updated, raw, bom)
            changed.append(path.relative_to(ROOT).as_posix())
    print(f"Targeted PT-BR fixes changed {len(changed)} files: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
