#!/usr/bin/env python3
"""Resolve strict Chinese OCR literals to Portuguese through matching TextMap hashes.

Only exact CHS value matches are considered. The same hash is then read from
TextMapPT. Ambiguous Chinese text that maps to more than one Portuguese value is
kept as variants and is never silently collapsed to an invented translation.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRICT = ROOT / "reports" / "ptbr-strict-ocr.json"
OUT = ROOT / "reports" / "ptbr-textmap-resolved.json"
BASE = "https://raw.githubusercontent.com/MTAlexKen/Genshin-resources/master/TextMap/"


def download(name: str) -> dict[str, str]:
    req = urllib.request.Request(BASE + name, headers={"User-Agent":"BetterGI-PTBR-Audit/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def main() -> int:
    strict = json.loads(STRICT.read_text(encoding="utf-8"))
    wanted = set(strict.get("literal_frequency", {}).keys())
    chs = download("TextMapCHS.json")
    pt = download("TextMapPT.json")

    candidates: dict[str, set[str]] = {literal:set() for literal in wanted}
    for hash_id, zh in chs.items():
        if zh not in candidates:
            continue
        value = pt.get(hash_id)
        if isinstance(value, str) and value.strip():
            candidates[zh].add(value.strip())

    unique={}; variants={}; unresolved=[]
    for literal in sorted(wanted):
        values=sorted(candidates[literal])
        if len(values)==1:
            unique[literal]=values[0]
        elif len(values)>1:
            variants[literal]=values
        else:
            unresolved.append(literal)

    result={
        "source": "MTAlexKen/Genshin-resources TextMapCHS.json + TextMapPT.json, exact shared hash",
        "strict_literal_count": len(wanted),
        "unique_resolved_count": len(unique),
        "variant_resolved_count": len(variants),
        "unresolved_count": len(unresolved),
        "unique": unique,
        "variants": variants,
        "unresolved": unresolved,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("strict_literal_count","unique_resolved_count","variant_resolved_count","unresolved_count")}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
