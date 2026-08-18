#!/usr/bin/env python3
"""Apply only exact TextMap-resolved PT-BR mappings to high-confidence JS OCR code.

Safe transformations:
- `ocrText.includes("中文")` -> `genshin.textContainsLiteral(...)`;
- positive equality on OCR-like expressions -> `genshin.textEqualsLiteral(...)`;
- direct findText/findTextAndClick/chooseTalkOption first arguments use
  `genshin.getTextLiteral` when the TextMap mapping is unique;
- BetterGI typings are extended for the literal API.

Internal `settings.*` comparisons and unresolved TextMap literals are untouched.
"""
from __future__ import annotations

import codecs
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports'/'ptbr-textmap-resolved.json'
DTS=ROOT/'bettergi.d.ts'
SCRIPTS=ROOT/'repo'/'js'


def read(path:Path):
    raw=path.read_bytes(); return raw.decode('utf-8-sig'),raw,raw.startswith(codecs.BOM_UTF8)


def write_like(path:Path,text:str,raw:bytes,bom:bool):
    nl='\r\n' if b'\r\n' in raw else '\n'
    data=text.replace('\r\n','\n').replace('\r','\n').replace('\n',nl).encode('utf-8')
    path.write_bytes((codecs.BOM_UTF8 if bom else b'')+data)


def patch_dts(text:str)->str:
    if 'getTextLiteral(canonicalZhHans: string)' not in text:
        marker='  /** Resolve all accepted OCR variants for a semantic game-text key. */\n  getTexts(key: string): string[];\n'
        block='''  /** Resolve an exact TextMap-backed canonical Chinese game literal. */
  getTextLiteral(canonicalZhHans: string): string;
  /** Resolve every accepted TextMap-backed variant. */
  getTextLiterals(canonicalZhHans: string): string[];
  /** Check whether OCR text contains a localized TextMap literal. */
  textContainsLiteral(actualText: string, canonicalZhHans: string): boolean;
  /** Check whether OCR text equals a localized TextMap literal. */
  textEqualsLiteral(actualText: string, canonicalZhHans: string): boolean;
'''
        if marker not in text: raise RuntimeError('getTexts marker not found in bettergi.d.ts')
        text=text.replace(marker,marker+block,1)
    if 'GetTextLiteral: typeof genshin.getTextLiteral;' not in text:
        marker='  GetTexts: typeof genshin.getTexts;\n'
        block='''  GetTextLiteral: typeof genshin.getTextLiteral;
  GetTextLiterals: typeof genshin.getTextLiterals;
  TextContainsLiteral: typeof genshin.textContainsLiteral;
  TextEqualsLiteral: typeof genshin.textEqualsLiteral;
'''
        if marker not in text: raise RuntimeError('GetTexts alias marker not found')
        text=text.replace(marker,marker+block,1)
    return text


def split_comment(line:str):
    q=None; esc=False
    for i in range(len(line)-1):
        c=line[i]
        if q:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c==q: q=None
            continue
        if c in "'\"`": q=c; continue
        if c=='/' and line[i+1]=='/': return line[:i],line[i:]
    return line,''


def apply_line(code:str, unique:set[str], resolved:set[str]):
    if 'settings.' in code or 'genshin.textContainsLiteral' in code or 'genshin.textEqualsLiteral' in code:
        return code
    for literal in sorted(resolved,key=len,reverse=True):
        esc=re.escape(literal)
        # OCR/property-chain contains checks; no function calls are duplicated.
        chain=r'[A-Za-z_$][\w$?.\[\]]*'
        patt=re.compile(rf'(?P<expr>{chain})\.includes\((?P<q>[\'\"]){esc}(?P=q)\)')
        def repl(m):
            expr=m.group('expr'); lit=json.dumps(literal,ensure_ascii=False)
            return f'(genshin.textContainsLiteral ? genshin.textContainsLiteral({expr}, {lit}) : {expr}.includes({lit}))'
        code=patt.sub(repl,code)

        # Positive direct equality against OCR/result-like property chains.
        patt_eq=re.compile(rf'(?P<expr>{chain})\s*(?P<op>===|==)\s*(?P<q>[\'\"]){esc}(?P=q)')
        def repl_eq(m):
            expr=m.group('expr'); op=m.group('op'); lit=json.dumps(literal,ensure_ascii=False)
            lower=expr.lower()
            if not any(token in lower for token in ('text','ocr','result','res','find','recogn','detect')):
                return m.group(0)
            return f'(genshin.textEqualsLiteral ? genshin.textEqualsLiteral({expr}, {lit}) : {expr} {op} {lit})'
        code=patt_eq.sub(repl_eq,code)

        if literal in unique:
            lit=json.dumps(literal,ensure_ascii=False)
            localized=f'(genshin.getTextLiteral ? genshin.getTextLiteral({lit}) : {lit})'
            patt_call=re.compile(rf'\b(?P<fn>findText|findTextAndClick|chooseTalkOption)\(\s*(?P<q>[\'\"]){esc}(?P=q)')
            code=patt_call.sub(lambda m:f'{m.group("fn")}({localized}',code)
    return code


def main():
    data=json.loads(REPORT.read_text(encoding='utf-8'))
    unique=set(data['unique']); resolved=unique|set(data['variants'])
    changed=[]

    dts,raw,bom=read(DTS); new=patch_dts(dts)
    if new!=dts: write_like(DTS,new,raw,bom); changed.append('bettergi.d.ts')

    for path in sorted(SCRIPTS.rglob('*.js')):
        try: text,raw,bom=read(path)
        except UnicodeDecodeError: continue
        lines=[]
        for line in text.splitlines(keepends=True):
            code,comment=split_comment(line)
            lines.append(apply_line(code,unique,resolved)+comment)
        new=''.join(lines)
        if new!=text:
            write_like(path,new,raw,bom); changed.append(path.relative_to(ROOT).as_posix())
    print(json.dumps({'resolved_literals':len(resolved),'changed_files':len(changed),'files':changed},ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
