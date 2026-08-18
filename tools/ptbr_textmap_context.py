#!/usr/bin/env python3
"""Find full Genshin TextMap CHS/PT phrase pairs containing unresolved OCR fragments."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STRICT=ROOT/'reports'/'ptbr-strict-ocr.json'
OUT=ROOT/'reports'/'ptbr-textmap-context.json'
BASE='https://raw.githubusercontent.com/MTAlexKen/Genshin-resources/master/TextMap/'


def download(name:str)->dict[str,str]:
    req=urllib.request.Request(BASE+name,headers={'User-Agent':'BetterGI-PTBR-Context/1.0'})
    with urllib.request.urlopen(req,timeout=120) as r:
        return json.loads(r.read().decode('utf-8-sig'))


def main():
    strict=json.loads(STRICT.read_text(encoding='utf-8'))
    literals=list(strict.get('literal_frequency',{}).keys())
    chs=download('TextMapCHS.json'); pt=download('TextMapPT.json')
    result={}
    for literal in literals:
        rows=[]
        for h,zh in chs.items():
            if literal not in zh: continue
            pv=pt.get(h)
            if not isinstance(pv,str) or not pv.strip(): continue
            rows.append({'hash':h,'zh':zh,'pt':pv})
            if len(rows)>=20: break
        result[literal]=rows
    payload={
        'source':'MTAlexKen/Genshin-resources exact shared TextMap hash; CHS phrase contains unresolved literal',
        'literal_count':len(literals),
        'with_context_count':sum(1 for rows in result.values() if rows),
        'contexts':result,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'literal_count':payload['literal_count'],'with_context_count':payload['with_context_count']},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
