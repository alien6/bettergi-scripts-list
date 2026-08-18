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

SEMANTIC_LITERALS = {
    "确认": "confirm",
    "确定": "ok",
    "取消": "cancel",
    "退出秘境": "exit_domain",
    "退出挑战": "exit_challenge",
    "地脉异常": "ley_line_disorder",
    "物品过期": "item_expired",
    "领取奖励": "claim_reward",
    "全部领取": "claim_all",
    "传送": "teleport",
    "挑战达成": "challenge_completed",
    "跳过": "skip",
    "匹配挑战": "matching_challenge",
    "快速编队": "rapid_formation",
    "点击任意位置关闭": "click_anywhere_to_close",
    "原粹树脂": "original_resin",
    "开始游戏": "start_game",
    "当前拥有": "current_owned",
    "搜索": "search",
    "房间": "room",
    "圣遗物": "artifact",
    "烹饪": "cooking",
    "当前队伍": "current_party",
    "点击进入": "click_to_enter",
    "培养需求": "growth_requirements",
    "取消自动任务": "cancel_auto_task",
    "鱼饵": "bait",
    "复活": "revive",
    "自动退出": "auto_exit",
    "接触征讨之花": "touch_trounce_blossom",
    "待激活": "awaiting_activation",
    "委托完成": "commission_completed",
    "委托": "commission",
    "管理": "manage",
    "返回大厅": "return_to_lobby",
    "材料不足": "insufficient_materials",
    "自动烹饪": "auto_cook",
    "料理制作": "cooking_production",
    "队列已满": "queue_full",
}

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
ALREADY_LOCALIZED_PREFIX_RE = re.compile(r"genshin\.getText\([^\r\n)]*\)\s*:\s*$")


def localized_expression(literal: str, key: str) -> str:
    escaped = json.dumps(literal, ensure_ascii=False)
    semantic = json.dumps(key)
    return f"(genshin.getText ? genshin.getText({semantic}) : {escaped})"


def collapse_nested_localization(text: str) -> str:
    """Collapse one or more accidentally nested generated fallback expressions."""
    changed = True
    while changed:
        changed = False
        for literal, key in SEMANTIC_LITERALS.items():
            single = localized_expression(literal, key)
            nested = f"(genshin.getText ? genshin.getText({json.dumps(key)}) : {single})"
            if nested in text:
                text = text.replace(nested, single)
                changed = True
    return text


def migrate_js_text(text: str) -> tuple[str, Counter[str]]:
    text = collapse_nested_localization(text)
    replacements: Counter[str] = Counter()

    def replace(match: re.Match[str]) -> str:
        literal = match.group("value")
        key = SEMANTIC_LITERALS.get(literal)
        if key is None:
            return match.group(0)

        tail = text[match.end():]
        if re.match(r"\s*:", tail):
            return match.group(0)

        prefix = text[max(0, match.start() - 160):match.start()]
        if ALREADY_LOCALIZED_PREFIX_RE.search(prefix):
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
        if not any(token in line for token in OCR_SENSITIVE_TOKENS) or not CJK_RE.search(line):
            continue

        literals = [match.group("value") for match in STRING_RE.finditer(line)]
        cjk_literals: list[str] = []
        for literal in literals:
            if not CJK_RE.search(literal):
                continue
            key = SEMANTIC_LITERALS.get(literal)
            if key and localized_expression(literal, key) in line:
                continue
            cjk_literals.append(literal)

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
            original = path.read_text(encoding="utf-8")
            current = original if args.apply else migrate_js_text(original)[0]
        except UnicodeDecodeError:
            continue
        findings.extend(scan_remaining(path, current))

    known_remaining = [
        finding for finding in findings
        if any(literal in SEMANTIC_LITERALS for literal in finding["literals"])
    ]
    literal_frequency: Counter[str] = Counter()
    for finding in findings:
        literal_frequency.update(finding["literals"])

    report = {
        "semantic_replacements": dict(sorted(replacement_counts.items())),
        "files_would_change" if not args.apply else "files_changed": changed_files,
        "remaining_ocr_sensitive_cjk_count": len(findings),
        "remaining_known_semantic_count": len(known_remaining),
        "remaining_literal_frequency": dict(literal_frequency.most_common()),
        "remaining": findings,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "changed_files": len(changed_files),
        "semantic_replacements": sum(replacement_counts.values()),
        "remaining_ocr_sensitive_cjk": len(findings),
        "remaining_known_semantic": len(known_remaining),
        "top_remaining_literals": literal_frequency.most_common(30),
        "report": REPORT_PATH.relative_to(ROOT).as_posix(),
    }, ensure_ascii=False, indent=2))

    if args.fail_on_known and known_remaining:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
