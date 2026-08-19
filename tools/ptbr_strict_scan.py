#!/usr/bin/env python3
"""High-confidence scan for Chinese literals that directly affect OCR/UI matching.

The report distinguishes raw legacy strings that are safely handled by the
BetterGI runtime compatibility layer from strings that still require migration.
Only additive String search methods and chooseTalkOption are considered runtime
covered; equality comparisons and other direct OCR helpers remain blockers.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from ptbr_migrate import SEMANTIC_LITERALS

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "repo" / "js"
REPORT = ROOT / "reports" / "ptbr-strict-ocr.json"
AUDITED = ROOT / "tools" / "ptbr_audited_literals.json"
TEXTMAP = ROOT / "reports" / "ptbr-textmap-resolved.json"

CJK = r"[\u3400-\u4dbf\u4e00-\u9fff]"
STRING = re.compile(r"(?P<q>['\"])(?P<v>[^'\"\r\n]*" + CJK + r"[^'\"\r\n]*)(?P=q)")
REGEX_LITERAL = re.compile(r"/(?P<v>(?:\\.|[^/\r\n])*" + CJK + r"(?:\\.|[^/\r\n])*)/[dgimsuvy]*")
REGEX_TEXT_MATCH = re.compile(r"[A-Za-z_$][\w$?.\[\]]*\s*\.\s*(?:match|search)\s*\(\s*$", re.I)
CJK_RUN = re.compile(CJK + r"+")
DIRECT_CALL = re.compile(r"(?P<call>findText(?:AndClick)?|OcrMatch|chooseTalkOption|ChooseTalkOption|waitAndFindText|waitForOcrMatch)\s*\([^;\r\n]*$", re.I)
OCR_EXPR = r"(?:[A-Za-z_$][\w$?.\[\]]*\.text|ocr[\w$?.\[\]]*|result\d*[\w$?.\[\]]*|results[\w$?.\[\]]*|res(?:\d+)?(?:[.$?\[\]][A-Za-z0-9_$?\[\].]*)?|resList[\w$?.\[\]]*|findResult[\w$?.\[\]]*|recognitionResult[\w$?.\[\]]*|recognizedText[\w$?.\[\]]*|detectedText[\w$?.\[\]]*)"
OCR_METHOD = re.compile(OCR_EXPR + r"\s*\.\s*(?P<method>includes|contains|indexOf|startsWith|endsWith)\s*\([^\r\n]*$", re.I)
OCR_COMPARE = re.compile(OCR_EXPR + r"\s*(?:===|==|!==|!=)\s*$", re.I)
GENERATED_FALLBACK = re.compile(r"\(genshin\.getText\s*\?\s*genshin\.getText\([^\r\n)]*\)\s*:\s*$", re.I)
IGNORE_CALL_PREFIX = re.compile(r"(?:log|Log)\.(?:info|debug|warn|warning|error)\([^\r\n]*$|notification\.[A-Za-z]+\([^\r\n]*$", re.I)
RESOLVED_LITERAL_API = (
    'genshin.getTextLiteral ?',
    'genshin.getTextLiterals ?',
    'genshin.getLegacyText ?',
    'genshin.getLegacyTexts ?',
    'genshin.textContainsLiteral ?',
    'genshin.textEqualsLiteral ?',
    'genshin.textStartsWithLiteral ?',
    'genshin.textEndsWithLiteral ?',
)
RUNTIME_STRING_METHODS = {'includes', 'indexof', 'startswith', 'endswith'}

# These values are script-owned protocol/state tokens, not text read from the
# Genshin UI. Keeping them in Chinese is compatible with every game language and
# also preserves existing TeyvatScanner record files. They are excluded only for
# this exact script; the same literals elsewhere are still audited normally.
INTERNAL_STATUS_LITERALS = {
    'repo/js/TeyvatScanner/main.js': {
        '罗盘状态异常，可能在战斗中',
        '未发现宝藏或宝藏相关线索',
        '发现宝藏或宝藏相关线索',
        '存在宝藏',
    },
}


def load_runtime_covered_literals() -> set[str]:
    covered = set(SEMANTIC_LITERALS)
    if AUDITED.exists():
        data = json.loads(AUDITED.read_text(encoding='utf-8'))
        covered.update(data)
    if TEXTMAP.exists():
        data = json.loads(TEXTMAP.read_text(encoding='utf-8'))
        covered.update(data.get('unique', []))
        covered.update(data.get('variants', []))
    return covered


def comment_mask(text: str) -> list[tuple[int, int]]:
    out=[]; i=0; q=None; esc=False
    while i < len(text):
        c=text[i]; n=text[i+1] if i+1<len(text) else ''
        if q:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c==q: q=None
            i+=1; continue
        if c in "'\"`": q=c; i+=1; continue
        if c=='/' and n=='/':
            e=text.find('\n',i+2); e=len(text) if e<0 else e; out.append((i,e)); i=e; continue
        if c=='/' and n=='*':
            e=text.find('*/',i+2); e=len(text) if e<0 else e+2; out.append((i,e)); i=e; continue
        i+=1
    return out


def inside(pos:int, ranges:list[tuple[int,int]]) -> bool:
    return any(a<=pos<b for a,b in ranges)


def scan(path:Path, runtime_covered_literals:set[str]):
    try: text=path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError: return [], []
    comments=comment_mask(text); blockers=[]; covered=[]
    relative_path=path.relative_to(ROOT).as_posix()
    internal_literals=INTERNAL_STATUS_LITERALS.get(relative_path, set())
    for m in STRING.finditer(text):
        if inside(m.start(),comments): continue
        ls=text.rfind('\n',0,m.start())+1; le=text.find('\n',m.end()); le=len(text) if le<0 else le
        prefix=text[ls:m.start()]; line=text[ls:le]
        literal=m.group('v')
        if literal in internal_literals:
            continue
        if 'settings.' in line or any(marker in line for marker in RESOLVED_LITERAL_API) or GENERATED_FALLBACK.search(prefix[-220:]) or IGNORE_CALL_PREFIX.search(prefix[-260:]):
            continue

        direct_match=DIRECT_CALL.search(prefix[-450:])
        method_match=OCR_METHOD.search(prefix[-450:])
        compare=bool(OCR_COMPARE.search(prefix[-450:]))
        if not (direct_match or method_match or compare): continue

        finding={'path':relative_path,'line':text.count('\n',0,m.start())+1,'literal':literal,'source':line.strip()[:500]}
        runtime_covered=False

        # The JS shim only wraps native String search methods. String.contains is
        # deliberately excluded because it is non-standard and is not overridden.
        if method_match and method_match.group('method').lower() in RUNTIME_STRING_METHODS:
            runtime_covered = literal in runtime_covered_literals

        # chooseTalkOption is localized centrally in ChooseTalkOptionTask.
        if direct_match and direct_match.group('call').lower() == 'choosetalkoption':
            runtime_covered = literal in runtime_covered_literals

        # Equality is never hidden by the runtime shim; it remains a blocker even
        # when the literal has a known PT-BR translation.
        if compare:
            runtime_covered=False

        if runtime_covered:
            finding['coverage']='legacy-runtime'
            covered.append(finding)
        else:
            blockers.append(finding)

    # Regex literals can also encode game-language assumptions, e.g.
    # ocrText.match(/冒险等阶\s*(\d+)/). Restrict this pass to regex literals used
    # directly by match/search so ordinary math/division or unrelated patterns
    # are not promoted to high-confidence OCR blockers.
    for m in REGEX_LITERAL.finditer(text):
        if inside(m.start(), comments):
            continue
        ls=text.rfind('\n',0,m.start())+1; le=text.find('\n',m.end()); le=len(text) if le<0 else le
        prefix=text[ls:m.start()]; line=text[ls:le]
        if 'settings.' in line or not REGEX_TEXT_MATCH.search(prefix[-260:]):
            continue
        for run in CJK_RUN.findall(m.group('v')):
            blockers.append({
                'path':relative_path,
                'line':text.count('\n',0,m.start())+1,
                'literal':run,
                'source':line.strip()[:500],
                'coverage':'regex-language-dependency',
            })
    return blockers, covered


def main():
    runtime_covered_literals=load_runtime_covered_literals()
    blockers=[]; covered=[]
    for p in sorted(SCRIPTS.rglob('*.js')):
        file_blockers,file_covered=scan(p,runtime_covered_literals)
        blockers.extend(file_blockers); covered.extend(file_covered)

    freq=Counter(f['literal'] for f in blockers); files=Counter(f['path'] for f in blockers)
    covered_freq=Counter(f['literal'] for f in covered); covered_files=Counter(f['path'] for f in covered)
    data={
        'strict_functional_cjk_count':len(blockers),
        'legacy_runtime_covered_count':len(covered),
        'literal_frequency':dict(freq.most_common()),
        'file_frequency':dict(files.most_common()),
        'runtime_covered_literal_frequency':dict(covered_freq.most_common()),
        'runtime_covered_file_frequency':dict(covered_files.most_common()),
        'findings':blockers,
        'runtime_covered_findings':covered,
    }
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({
        'strict_functional_cjk_count':len(blockers),
        'legacy_runtime_covered_count':len(covered),
        'top_literals':freq.most_common(40),
        'top_files':files.most_common(30),
        'top_runtime_covered_literals':covered_freq.most_common(20),
    },ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
