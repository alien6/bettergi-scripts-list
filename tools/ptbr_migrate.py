#!/usr/bin/env python3
"""Migrate BetterGI scripts away from fixed Simplified-Chinese game UI literals.

The migration is intentionally conservative:
- only exact, known game-UI literals are rewritten;
- JSON files and arbitrary prose are never modified;
- object-property keys are left untouched;
- generated BetterGI typings are patched idempotently;
- remaining OCR-sensitive CJK literals are reported for follow-up.

Run with --apply to modify files. Without --apply it only reports what would change.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = ROOT / "repo" / "js"
DTS_PATH = ROOT / "bettergi.d.ts"
REPORT_PATH = ROOT / "reports" / "ptbr-hardcoded-ocr.json"

# Exact Chinese literals with stable semantic meaning in the game UI.
# Keys must match BetterGenshinImpact.Core.Localization.GameTextKey.
SEMANTIC_LITERALS = {
    "确认": "confirm",
    "确定": "ok",
    "取消": "cancel",
    "退出秘境": "exit_domain",
    "退出挑战": "exit_challenge",
    "地脉异常": "ley_line_disorder",
    "物品过期": "item_expired",
    "领取奖励": "claim_reward",
    "传送": "teleport",
    "挑战达成": "challenge_completed",
    "跳过": "skip",
    "匹配挑战": "matching_challenge",
    "快速编队": "rapid_formation",
    "点击任意位置关闭": "click_anywhere_to_close",
}

# A CJK literal close to one of these tokens is probably functional game text,
# not a log/comment. The report intentionally errs on the side of visibility.
OCR_SENSITIVE_TOKENS = (
    "findText",
    "findTextAndClick",
    "findMulti",
    "OcrMatch",
    "RecognitionObject.Ocr",
    ".includes(",
    ".contains(",
    "chooseTalkOption",
    "ChooseTalkOption",
    ".text",
)

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
STRING_RE = re.compile(r"(?P<quote>['\"])(?P<value>[^'\"\r\n]*[\u3400-\u4dbf\u4e00-\u9fff][^'\"\r\n]*)(?P=quote)")


def localized_expression(literal: str, key: str) -> str:
    # Keep old BetterGI compatibility for Chinese clients while allowing the
    # new semantic API to localize on pt-BR/en/ja/etc.
    escaped = json.dumps(literal, ensure_ascii=False)
    semantic = json.dumps(key)
    return f"(genshin.getText ? genshin.getText({semantic}) : {escaped})"


def migrate_js_text(text: str) -> tuple[str, Counter[str]]:
    replacements: Counter[str] = Counter()

    def replace(match: re.Match[str]) -> str:
        literal = match.group("value")
        key = SEMANTIC_LITERALS.get(literal)
        if key is None:
            return match.group(0)

        # Do not rewrite object keys such as { "确认": handler }.
        tail = text[match.end():]
        if re.match(r"\s*:", tail):
            return match.group(0)

        replacements[key] += 1
        return localized_expression(literal, key)

    return STRING_RE.sub(replace, text), replacements


def patch_dts(text: str) -> tuple[str, bool]:
    if "readonly gameCulture: string;" in text and "findTextKeyAndClick(key: string" in text:
        return text, False

    property_marker = "  /** 系统 DPI 缩放比例 */\n  readonly screenDpiScale: number;\n"
    api_block = """  /** Current Genshin client culture configured in BetterGI. */
  readonly gameCulture: string;
  /** Resolve a semantic game-text key for the current client culture. */
  getText(key: string): string;
  /** Resolve all accepted OCR variants for a semantic game-text key. */
  getTexts(key: string): string[];
  /** Find the exact OCR result matching a semantic key inside an existing image region. */
  findTextKey(key: string, region: ImageRegion): Region;
  /** Find the exact OCR result matching a semantic key inside a capture rectangle. */
  findTextKey(key: string, x: number, y: number, width: number, height: number): Region;
  /** Return whether a semantic key is visible inside an existing image region. */
  hasTextKey(key: string, region: ImageRegion): boolean;
  /** Return whether a semantic key is visible inside a capture rectangle. */
  hasTextKey(key: string, x: number, y: number, width: number, height: number): boolean;
  /** Return the actual OCR text matched by a semantic key, or an empty string. */
  findTextKeyText(key: string, region: ImageRegion): string;
  /** Return the actual OCR text matched by a semantic key in a capture rectangle, or an empty string. */
  findTextKeyText(key: string, x: number, y: number, width: number, height: number): string;
  /** Find and click the exact OCR result matching a semantic key. */
  findTextKeyAndClick(key: string, region: ImageRegion): boolean;
  /** Find and click the exact OCR result matching a semantic key in a capture rectangle. */
  findTextKeyAndClick(key: string, x: number, y: number, width: number, height: number): boolean;
"""

    if property_marker not in text:
        raise RuntimeError("Could not locate genshin.screenDpiScale in bettergi.d.ts")
    text = text.replace(property_marker, property_marker + api_block, 1)

    alias_marker = "  readonly ScreenDpiScale: typeof genshin.screenDpiScale;\n"
    alias_block = """  readonly GameCulture: typeof genshin.gameCulture;
  GetText: typeof genshin.getText;
  GetTexts: typeof genshin.getTexts;
  FindTextKey: typeof genshin.findTextKey;
  HasTextKey: typeof genshin.hasTextKey;
  FindTextKeyText: typeof genshin.findTextKeyText;
  FindTextKeyAndClick: typeof genshin.findTextKeyAndClick;
"""
    if alias_marker not in text:
        raise RuntimeError("Could not locate genshin ScreenDpiScale alias in bettergi.d.ts")
    text = text.replace(alias_marker, alias_marker + alias_block, 1)
    return text, True


def scan_remaining(path: Path, text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        if not any(token in line for token in OCR_SENSITIVE_TOKENS):
            continue
        if not CJK_RE.search(line):
            continue
        literals = [match.group("value") for match in STRING_RE.finditer(line)]
        cjk_literals = [literal for literal in literals if CJK_RE.search(literal)]
        if not cjk_literals:
            continue
        findings.append({
            "path": path.relative_to(ROOT).as_posix(),
            "line": index,
            "literals": cjk_literals,
            "source": line.strip()[:500],
        })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write deterministic migrations")
    parser.add_argument(
        "--fail-on-known",
        action="store_true",
        help="fail if a known semantic Chinese literal remains in OCR-sensitive code",
    )
    args = parser.parse_args()

    changed_files: list[str] = []
    replacement_counts: Counter[str] = Counter()

    js_files = sorted(SCRIPTS_ROOT.rglob("*.js")) if SCRIPTS_ROOT.exists() else []
    for path in js_files:
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        migrated, counts = migrate_js_text(original)
        replacement_counts.update(counts)
        if migrated != original:
            changed_files.append(path.relative_to(ROOT).as_posix())
            if args.apply:
                path.write_text(migrated, encoding="utf-8", newline="\n")

    if DTS_PATH.exists():
        original_dts = DTS_PATH.read_text(encoding="utf-8-sig")
        migrated_dts, changed = patch_dts(original_dts)
        if changed:
            changed_files.append(DTS_PATH.relative_to(ROOT).as_posix())
            if args.apply:
                DTS_PATH.write_text(migrated_dts, encoding="utf-8", newline="\n")

    findings: list[dict[str, object]] = []
    for path in js_files:
        try:
            current = path.read_text(encoding="utf-8") if args.apply else migrate_js_text(path.read_text(encoding="utf-8"))[0]
        except UnicodeDecodeError:
            continue
        findings.extend(scan_remaining(path, current))

    known_remaining = [
        finding
        for finding in findings
        if any(literal in SEMANTIC_LITERALS for literal in finding["literals"])
    ]

    report = {
        "semantic_replacements": dict(sorted(replacement_counts.items())),
        "files_would_change" if not args.apply else "files_changed": changed_files,
        "remaining_ocr_sensitive_cjk_count": len(findings),
        "remaining_known_semantic_count": len(known_remaining),
        "remaining": findings,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "changed_files": len(changed_files),
        "semantic_replacements": sum(replacement_counts.values()),
        "remaining_ocr_sensitive_cjk": len(findings),
        "remaining_known_semantic": len(known_remaining),
        "report": REPORT_PATH.relative_to(ROOT).as_posix(),
    }, ensure_ascii=False, indent=2))

    if args.fail_on_known and known_remaining:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
