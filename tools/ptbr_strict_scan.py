#!/usr/bin/env python3
"""High-confidence scan for Chinese literals that directly affect OCR/UI matching."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "repo" / "js"
REPORT = ROOT / "reports" / "ptbr-strict-ocr.json"

STRING = re.compile(r"(?P<q>['\"])(?P<v>[^'\"\r\n]*[\u3400-\u4dbf\u4e00-\u9fff][^'\"\r\n]*)(?P=q)")
DIRECT_CALL = re.compile(r"(?:findText(?:AndClick)?|OcrMatch|chooseTalkOption|ChooseTalkOption)\s*\([^;\r\n]*$", re.I)
OCR_METHOD = re.compile(r"(?:\.text|ocr|recogn|result|res|find|detected|detector|ocrText|recognizedText)[\w.$?]*\s*\.\s*(?:includes|contains|indexOf|startsWith|endsWith)\s*\([^\r\n]*$", re.I)
OCR_COMPARE = re.compile(r"(?:\.text|ocr|recogn|result|res|find|detected)[\w.$?]*\s*(?:===|==|!==|!=)\s*$", re.I)
GENERATED_FALLBACK = re.compile(r"\(genshin\.getText\s*\?\s*genshin\.getText\([^\r\n)]*\)\s*:\s*$", re.I)


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


def scan(path:Path):
    try: text=path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError: return []
    comments=comment_mask(text); findings=[]
    for m in STRING.finditer(text):
        if inside(m.start(),comments): continue
        ls=text.rfind('\n',0,m.start())+1; le=text.find('\n',m.end()); le=len(text) if le<0 else le
        prefix=text[ls:m.start()]; suffix=text[m.end():le]; line=text[ls:le]
        if 'settings.' in line or GENERATED_FALLBACK.search(prefix[-220:]): continue
        direct=bool(DIRECT_CALL.search(prefix[-350:]))
        method=bool(OCR_METHOD.search(prefix[-350:]))
        compare=bool(OCR_COMPARE.search(prefix[-350:])) or bool(re.match(r"\s*(?:===|==|!==|!=)",suffix) and re.search(r"(?:\.text|ocr|recogn|result|res|find|detected)",prefix,re.I))
        if not (direct or method or compare): continue
        findings.append({'path':path.relative_to(ROOT).as_posix(),'line':text.count('\n',0,m.start())+1,'literal':m.group('v'),'source':line.strip()[:500]})
    return findings


def main():
    findings=[]
    for p in sorted(SCRIPTS.rglob('*.js')): findings.extend(scan(p))
    freq=Counter(f['literal'] for f in findings); files=Counter(f['path'] for f in findings)
    data={'strict_functional_cjk_count':len(findings),'literal_frequency':dict(freq.most_common()),'file_frequency':dict(files.most_common()),'findings':findings}
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'strict_functional_cjk_count':len(findings),'top_literals':freq.most_common(40),'top_files':files.most_common(30)},ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
