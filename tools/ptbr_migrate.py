#!/usr/bin/env python3
"""Migrate BetterGI scripts away from fixed Simplified-Chinese game UI literals.

The migration is conservative: known static game UI literals are localized,
comments are ignored, existing file encoding/newline style is preserved, and a
strict functional OCR report is separated from the broader review report.
"""

from __future__ import annotations

import argparse
import codecs
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

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
STRING_RE = re.compile(r"(?P<quote>['\"])(?P<value>[^'\"\r\n]*[\u3400-\u4dbf\u4e00-\u9fff][^'\"\r\n]*)(?P=quote)")
ALREADY_LOCALIZED_PREFIX_RE = re.compile(r"genshin\.getText\([^\r\n)]*\)\s*:\s*$")
FUNCTION_CALL_RE = re.compile(
    r"(?:findText(?:AndClick)?|OcrMatch|chooseTalkOption|ChooseTalkOption|"
    r"findTextKey(?:AndClick|Text)?|hasTextKey)\s*\([^;\r\n]*$",
    re.IGNORECASE,
)
METHOD_MATCH_RE = re.compile(r"\.(?:includes|contains|indexOf|startsWith|endsWith)\s*\(\s*$", re.IGNORECASE)
COMPARE_BEFORE_RE = re.compile(r"(?:===|!==|==|!=)\s*$")
COMPARE_AFTER_RE = re.compile(r"^\s*(?:===|!==|==|!=)")
TEXT_ASSIGNMENT_RE = re.compile(
    r"(?:const|let|var)\s+[A-Za-z_$][\w$]*(?:text|keyword|label|target|ocr)[\w$]*\s*=\s*$",
    re.IGNORECASE,
)
OCR_COLLECTION_MARKERS = (
    "OneContainMatchText",
    "AllContainMatchText",
    "RegexMatchText",
    "matchTexts",
)


def read_utf8(path: Path) -> tuple[str, bytes, bool]:
    raw = path.read_bytes()
    return raw.decode("utf-8-sig"), raw, raw.startswith(codecs.BOM_UTF8)


def write_like(path: Path, text: str, original_raw: bytes, had_bom: bool) -> None:
    newline = "\r\n" if b"\r\n" in original_raw else "\n"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw = normalized.replace("\n", newline).encode("utf-8")
    if had_bom:
        raw = codecs.BOM_UTF8 + raw
    path.write_bytes(raw)


def localized_expression(literal: str, key: str) -> str:
    escaped = json.dumps(literal, ensure_ascii=False)
    semantic = json.dumps(key)
    return f"(genshin.getText ? genshin.getText({semantic}) : {escaped})"


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


def in_ranges(position: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in ranges)


def line_context(text: str, match: re.Match[str]) -> tuple[str, str, str]:
    start = text.rfind("\n", 0, match.start()) + 1
    end = text.find("\n", match.end())
    if end == -1:
        end = len(text)
    line = text[start:end]
    prefix = text[start:match.start()]
    suffix = text[match.end():end]
    return line, prefix, suffix


def is_functional_context(text: str, match: re.Match[str]) -> bool:
    line, prefix, suffix = line_context(text, match)
    compact_prefix = prefix[-300:]
    if FUNCTION_CALL_RE.search(compact_prefix):
        return True
    if METHOD_MATCH_RE.search(compact_prefix):
        return True
    if COMPARE_BEFORE_RE.search(compact_prefix) or COMPARE_AFTER_RE.search(suffix):
        return True
    if TEXT_ASSIGNMENT_RE.search(compact_prefix):
        return True
    if any(marker in line for marker in OCR_COLLECTION_MARKERS):
        return True
    return False


def collapse_nested_localization(text: str) -> str:
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
    comments = comment_ranges(text)
    replacements: Counter[str] = Counter()

    def replace(match: re.Match[str]) -> str:
        if in_ranges(match.start(), comments):
            return match.group(0)
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

        # Known game labels are migrated in OCR/comparison contexts and in
        # explicit text/keyword/target assignments. Existing generated
        # expressions from earlier broad passes are left intact and audited.
        if not is_functional_context(text, match):
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


def scan_functional(path: Path, text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    comments = comment_ranges(text)
    for match in STRING_RE.finditer(text):
        if in_ranges(match.start(), comments) or not is_functional_context(text, match):
            continue
        literal = match.group("value")
        key = SEMANTIC_LITERALS.get(literal)
        line, _, _ = line_context(text, match)
        if key and localized_expression(literal, key) in line:
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        findings.append({
            "path": path.relative_to(ROOT).as_posix(),
            "line": line_number,
            "literals": [literal],
            "source": line.strip()[:500],
        })
    return findings


def scan_review(path: Path, text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    comments = comment_ranges(text)
    for match in STRING_RE.finditer(text):
        if in_ranges(match.start(), comments):
            continue
        literal = match.group("value")
        line, _, _ = line_context(text, match)
        key = SEMANTIC_LITERALS.get(literal)
        if key and localized_expression(literal, key) in line:
            continue
        if not any(token in line for token in (".text", "Ocr", "OCR", "find", "Find", "include", "contain")):
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        findings.append({
            "path": path.relative_to(ROOT).as_posix(),
            "line": line_number,
            "literals": [literal],
            "source": line.strip()[:500],
        })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write deterministic migrations")
    parser.add_argument(
        "--fail-on-known",
        action="store_true",
        help="fail if a known semantic Chinese literal remains in functional OCR code",
    )
    args = parser.parse_args()

    changed_files: list[str] = []
    replacement_counts: Counter[str] = Counter()
    js_files = sorted(SCRIPTS_ROOT.rglob("*.js")) if SCRIPTS_ROOT.exists() else []

    for path in js_files:
        try:
            original, raw, bom = read_utf8(path)
        except UnicodeDecodeError:
            continue
        migrated, counts = migrate_js_text(original)
        replacement_counts.update(counts)
        if migrated != original:
            changed_files.append(path.relative_to(ROOT).as_posix())
            if args.apply:
                write_like(path, migrated, raw, bom)

    if DTS_PATH.exists():
        original_dts, raw_dts, bom_dts = read_utf8(DTS_PATH)
        migrated_dts, changed = patch_dts(original_dts)
        if changed:
            changed_files.append(DTS_PATH.relative_to(ROOT).as_posix())
            if args.apply:
                write_like(DTS_PATH, migrated_dts, raw_dts, bom_dts)

    functional: list[dict[str, object]] = []
    review: list[dict[str, object]] = []
    for path in js_files:
        try:
            current, _, _ = read_utf8(path)
            if not args.apply:
                current = migrate_js_text(current)[0]
        except UnicodeDecodeError:
            continue
        functional.extend(scan_functional(path, current))
        review.extend(scan_review(path, current))

    known_remaining = [
        finding for finding in functional
        if any(literal in SEMANTIC_LITERALS for literal in finding["literals"])
    ]
    functional_frequency: Counter[str] = Counter()
    review_frequency: Counter[str] = Counter()
    for finding in functional:
        functional_frequency.update(finding["literals"])
    for finding in review:
        review_frequency.update(finding["literals"])

    report = {
        "semantic_replacements": dict(sorted(replacement_counts.items())),
        "files_would_change" if not args.apply else "files_changed": changed_files,
        "remaining_functional_cjk_count": len(functional),
        "remaining_known_semantic_count": len(known_remaining),
        "remaining_functional_literal_frequency": dict(functional_frequency.most_common()),
        "remaining_functional": functional,
        "review_cjk_count": len(review),
        "review_literal_frequency": dict(review_frequency.most_common()),
        "review": review,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "changed_files": len(changed_files),
        "semantic_replacements": sum(replacement_counts.values()),
        "remaining_functional_cjk": len(functional),
        "remaining_known_semantic": len(known_remaining),
        "top_functional_literals": functional_frequency.most_common(40),
        "review_cjk": len(review),
        "report": REPORT_PATH.relative_to(ROOT).as_posix(),
    }, ensure_ascii=False, indent=2))

    if args.fail_on_known and known_remaining:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
