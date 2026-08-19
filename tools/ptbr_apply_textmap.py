#!/usr/bin/env python3
"""Apply audited PT-BR literal mappings to high-confidence JS OCR code."""
from __future__ import annotations

import codecs
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports'/'ptbr-textmap-resolved.json'
AUDITED=ROOT/'tools'/'ptbr_audited_literals.json'
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
        block='''  /** Resolve an audited canonical Chinese game literal. */
  getTextLiteral(canonicalZhHans: string): string;
  /** Resolve every accepted localized variant for a canonical game literal. */
  getTextLiterals(canonicalZhHans: string): string[];
  /** Resolve a historical Chinese string embedded in an older script. */
  getLegacyText(canonicalText: string): string;
  /** Resolve every accepted localized variant for historical script text. */
  getLegacyTexts(canonicalText: string): string[];
  /** Check whether OCR text contains a localized game literal. */
  textContainsLiteral(actualText: string, canonicalZhHans: string): boolean;
  /** Check whether OCR text equals a localized game literal. */
  textEqualsLiteral(actualText: string, canonicalZhHans: string): boolean;
  /** Check whether OCR text starts with a localized game literal. */
  textStartsWithLiteral(actualText: string, canonicalZhHans: string): boolean;
  /** Check whether OCR text ends with a localized game literal. */
  textEndsWithLiteral(actualText: string, canonicalZhHans: string): boolean;
'''
        if marker not in text: raise RuntimeError('getTexts marker not found in bettergi.d.ts')
        text=text.replace(marker,marker+block,1)
    else:
        if 'getLegacyText(canonicalText: string)' not in text:
            marker='  getTextLiterals(canonicalZhHans: string): string[];\n'
            block='''  /** Resolve a historical Chinese string embedded in an older script. */
  getLegacyText(canonicalText: string): string;
  /** Resolve every accepted localized variant for historical script text. */
  getLegacyTexts(canonicalText: string): string[];
'''
            if marker not in text: raise RuntimeError('getTextLiterals marker not found')
            text=text.replace(marker,marker+block,1)
        if 'textEndsWithLiteral(actualText: string' not in text:
            marker='  /** Check whether OCR text equals a localized TextMap literal. */\n  textEqualsLiteral(actualText: string, canonicalZhHans: string): boolean;\n'
            if marker not in text:
                marker='  textEqualsLiteral(actualText: string, canonicalZhHans: string): boolean;\n'
            block='''  /** Check whether OCR text starts with a localized game literal. */
  textStartsWithLiteral(actualText: string, canonicalZhHans: string): boolean;
  /** Check whether OCR text ends with a localized game literal. */
  textEndsWithLiteral(actualText: string, canonicalZhHans: string): boolean;
'''
            if marker not in text: raise RuntimeError('textEqualsLiteral marker not found')
            text=text.replace(marker,marker+block,1)

    if 'GetTextLiteral: typeof genshin.getTextLiteral;' not in text:
        marker='  GetTexts: typeof genshin.getTexts;\n'
        block='''  GetTextLiteral: typeof genshin.getTextLiteral;
  GetTextLiterals: typeof genshin.getTextLiterals;
  GetLegacyText: typeof genshin.getLegacyText;
  GetLegacyTexts: typeof genshin.getLegacyTexts;
  TextContainsLiteral: typeof genshin.textContainsLiteral;
  TextEqualsLiteral: typeof genshin.textEqualsLiteral;
  TextStartsWithLiteral: typeof genshin.textStartsWithLiteral;
  TextEndsWithLiteral: typeof genshin.textEndsWithLiteral;
'''
        if marker not in text: raise RuntimeError('GetTexts alias marker not found')
        text=text.replace(marker,marker+block,1)
    else:
        if 'GetLegacyText: typeof genshin.getLegacyText;' not in text:
            marker='  GetTextLiterals: typeof genshin.getTextLiterals;\n'
            block='''  GetLegacyText: typeof genshin.getLegacyText;
  GetLegacyTexts: typeof genshin.getLegacyTexts;
'''
            if marker not in text: raise RuntimeError('GetTextLiterals alias marker not found')
            text=text.replace(marker,marker+block,1)
        if 'TextEndsWithLiteral: typeof genshin.textEndsWithLiteral;' not in text:
            marker='  TextEqualsLiteral: typeof genshin.textEqualsLiteral;\n'
            block='''  TextStartsWithLiteral: typeof genshin.textStartsWithLiteral;
  TextEndsWithLiteral: typeof genshin.textEndsWithLiteral;
'''
            if marker not in text: raise RuntimeError('TextEqualsLiteral alias marker not found')
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


def apply_line(code:str, resolved:set[str]):
    if 'settings.' in code or any(x in code for x in ('genshin.textContainsLiteral','genshin.textEqualsLiteral','genshin.textStartsWithLiteral','genshin.textEndsWithLiteral')):
        return code
    chain=r'[A-Za-z_$][\w$?.\[\]]*'
    for literal in sorted(resolved,key=len,reverse=True):
        esc=re.escape(literal); lit=json.dumps(literal,ensure_ascii=False)

        for method,api in (
            ('includes','textContainsLiteral'),
            ('startsWith','textStartsWithLiteral'),
            ('endsWith','textEndsWithLiteral'),
        ):
            patt=re.compile(rf'(?P<expr>{chain})\.{method}\((?P<q>[\'\"]){esc}(?P=q)\)')
            def repl(m,method=method,api=api):
                expr=m.group('expr')
                return f'(genshin.{api} ? genshin.{api}({expr}, {lit}) : {expr}.{method}({lit}))'
            code=patt.sub(repl,code)

        patt_eq=re.compile(rf'(?P<expr>{chain})\s*(?P<op>===|==)\s*(?P<q>[\'\"]){esc}(?P=q)')
        def repl_eq(m):
            expr=m.group('expr'); op=m.group('op'); lower=expr.lower()
            if not ('.text' in lower or lower.startswith(('ocr','result','res','find','recogn','detect'))):
                return m.group(0)
            return f'(genshin.textEqualsLiteral ? genshin.textEqualsLiteral({expr}, {lit}) : {expr} {op} {lit})'
        code=patt_eq.sub(repl_eq,code)

        localized=f'(genshin.getTextLiteral ? genshin.getTextLiteral({lit}) : {lit})'
        # Match a resolved literal anywhere inside a direct OCR/helper call's
        # argument list, not only when it is the first scalar argument. This
        # covers common shapes such as findText(["点击", "继续"], ...).
        patt_call=re.compile(
            rf'(?P<prefix>\b(?:findText|findTextAndClick|chooseTalkOption|waitAndFindText|waitForOcrMatch)\([^;\r\n]*?)'
            rf'(?P<q>[\'\"]){esc}(?P=q)'
        )
        def repl_call(m):
            prefix=m.group('prefix')
            # Preserve idempotence: do not wrap the canonical fallback literal
            # inside a getTextLiteral/getLegacyText expression on a later pass.
            if re.search(r'(?:getTextLiteral|getLegacyText)\s*\(\s*$', prefix[-120:]):
                return m.group(0)
            return f'{prefix}{localized}'
        code=patt_call.sub(repl_call,code)
    return code


def main():
    data=json.loads(REPORT.read_text(encoding='utf-8'))
    audited=json.loads(AUDITED.read_text(encoding='utf-8')) if AUDITED.exists() else {}
    resolved=set(data['unique'])|set(data['variants'])|set(audited)
    changed=[]

    dts,raw,bom=read(DTS); new=patch_dts(dts)
    if new!=dts: write_like(DTS,new,raw,bom); changed.append('bettergi.d.ts')

    for path in sorted(SCRIPTS.rglob('*.js')):
        try: text,raw,bom=read(path)
        except UnicodeDecodeError: continue
        lines=[]
        for line in text.splitlines(keepends=True):
            code,comment=split_comment(line)
            lines.append(apply_line(code,resolved)+comment)
        new=''.join(lines)
        if new!=text:
            write_like(path,new,raw,bom); changed.append(path.relative_to(ROOT).as_posix())
    print(json.dumps({'resolved_literals':len(resolved),'changed_files':len(changed),'files':changed},ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
