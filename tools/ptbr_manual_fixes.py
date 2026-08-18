#!/usr/bin/env python3
"""Targeted, idempotent PT-BR fixes where language-independent logic is safer than translation."""
from __future__ import annotations

import codecs
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEYLINE = ROOT / "repo" / "js" / "AutoLeyLineOutcrop" / "utils" / "attemptReward.js"
CRYSTALFLY = ROOT / "repo" / "js" / "CrystalflyTrap" / "main.js"
MULTI_PATHING = ROOT / "repo" / "js" / "AutoPathingLoader-MultiUser" / "main.js"


def read(path: Path):
    raw = path.read_bytes()
    return raw.decode("utf-8-sig"), raw, raw.startswith(codecs.BOM_UTF8)


def write_like(path: Path, text: str, raw: bytes, bom: bool):
    newline = "\r\n" if b"\r\n" in raw else "\n"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    data = normalized.replace("\n", newline).encode("utf-8")
    path.write_bytes((codecs.BOM_UTF8 if bom else b"") + data)


def patch_leyline(text: str) -> str:
    text = text.replace(
        'const match = texts[i].text.match(/2倍产出次数[:：]?(\\d+)/);',
        'const match = texts[i].text.match(/(\\d+)/);'
    )
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
    text = text.replace(
        't.text.includes((genshin.getTextLiteral ? genshin.getTextLiteral("原石") : "原石")) && t.text.includes("3次")',
        't.text.includes((genshin.getTextLiteral ? genshin.getTextLiteral("原石") : "原石")) && t.text.includes("3")'
    )
    text = text.replace(
        'if (text === "使用") {',
        'if (genshin.textEqualsLiteral ? genshin.textEqualsLiteral(text, "使用") : text === "使用") {'
    )

    for subject in ("t.text", "text"):
        text = re.sub(
            rf'\({re.escape(subject)}\.includes\("20"\)\s*\|\|\s*\(genshin\.textContainsLiteral \? genshin\.textContainsLiteral\({re.escape(subject)}, "20个"\) : {re.escape(subject)}\.includes\("20个"\)\)\)',
            f'{subject}.includes("20")', text
        )
        text = re.sub(
            rf'\({re.escape(subject)}\.includes\("40"\)\s*\|\|\s*\(genshin\.textContainsLiteral \? genshin\.textContainsLiteral\({re.escape(subject)}, "40个"\) : {re.escape(subject)}\.includes\("40个"\)\)\)',
            f'{subject}.includes("40")', text
        )
    return text


def patch_crystalfly(text: str) -> str:
    old_tab = '''            let backpackTitle = captureGameRegion();
            let resList = backpackTitle.findMulti(RecognitionObject.ocr(130, 0, 200, 50));
            backpackTitle.dispose();
            for (let i = 0; i < resList.count; i++) {
                let res = resList[i];
                if (!res.text.includes("小道")) {
                    log.info("点击小道具栏");
                    click(1060, 40);
                    await sleep(1000);
                }
            }'''
    new_tab = '''            // Open the gadget tab directly; this avoids a language-specific backpack title OCR check.
            log.info("点击小道具栏");
            click(1060, 40);
            await sleep(1000);'''
    text = text.replace(old_tab, new_tab)

    guard = re.compile(r'(?m)^\s*if \([^\n]*"晶蝶"[^\n]*"诱捕"[^\n]*"装置"[^\n]*\) \{$')
    replacement = '''                const isCrystalfly = genshin.textContainsLiteral ? genshin.textContainsLiteral(res.text, "晶蝶") : res.text.includes("晶蝶");
                const isDevice = genshin.textContainsLiteral ? genshin.textContainsLiteral(res.text, "装置") : res.text.includes("装置");
                if (!isCrystalfly || !isDevice) {'''
    text = guard.sub(replacement, text)
    return text


def patch_multi_pathing(text: str) -> str:
    # These are protocol messages exchanged by script instances through party chat.
    # Stable ASCII tokens are language-independent and OCR-friendly under both Latin
    # and Chinese Paddle models. Exact string replacements update both sender/receiver.
    protocol = {
        '"校验完成"': '"BGI_VERIFY_OK"',
        '"校验失败"': '"BGI_VERIFY_FAIL"',
        '"路线启动"': '"BGI_ROUTE_START"',
        '"全部路线结束"': '"BGI_ROUTES_DONE"',
    }
    for old, new in protocol.items():
        text = text.replace(old, new)
    return text


def main() -> int:
    changed = []
    for path, patcher in (
        (LEYLINE, patch_leyline),
        (CRYSTALFLY, patch_crystalfly),
        (MULTI_PATHING, patch_multi_pathing),
    ):
        text, raw, bom = read(path)
        updated = patcher(text)
        if updated != text:
            write_like(path, updated, raw, bom)
            changed.append(path.relative_to(ROOT).as_posix())
    print(f"Targeted PT-BR fixes changed {len(changed)} files: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
