#!/usr/bin/env python3
"""Regression checks for language-dependent OCR/control paths migrated to PT-BR-safe logic."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "repo/js/AutoLeyLineOutcrop/utils/attemptReward.js": [
        't.text.includes("20个")',
        't.text.includes("40个")',
        'text.includes("20个")',
        'text.includes("40个")',
        't.text.includes("原粹")',
        't.text.includes("树脂")',
    ],
    "repo/js/CrystalflyTrap/main.js": [
        'res.text.includes("小道")',
        'res.text.includes("诱捕")',
    ],
    "repo/js/AutoPathingLoader-MultiUser/main.js": [
        'sendMessage(`校验完成`)',
        'includes("校验完成")',
        'includes("校验失败")',
        'sendMessage("路线启动")',
        '=== "路线启动"',
        'sendMessage("全部路线结束")',
        'includes("全部路线结束")',
    ],
}


def scan() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for relative, needles in CHECKS.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8-sig")
        for needle in needles:
            count = text.count(needle)
            if count:
                findings.append({"path": relative, "needle": needle, "count": count})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    findings = scan()
    payload = {
        "ok": not findings,
        "finding_count": sum(int(item["count"]) for item in findings),
        "findings": findings,
    }
    if args.report:
        report = args.report if args.report.is_absolute() else ROOT / args.report
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
