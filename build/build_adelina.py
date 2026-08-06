# -*- coding: utf-8 -*-
"""Подставляет мой актуальный RAW в страницу Adelina (её вёрстка/логика 1:1)."""
import json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
D = Path(__file__).parent
html = (D/"adelina.html").read_text(encoding="utf-8", errors="replace")
raw  = (D/"raw.json").read_text(encoding="utf-8")

# 1) подменить массив RAW (от 'const RAW =' до '; const SNAPSHOT')
new, n = re.subn(r"const RAW\s*=\s*\[.*?\]\s*;\s*(?=const SNAPSHOT)",
                 "const RAW = " + raw + ";\n", html, count=1, flags=re.S)
assert n == 1, "RAW не найден/не заменён"

# 2) обновить дату в SNAPSHOT в её формате «ДД.ММ.ГГГГ в ЧЧ:ММ (Екб)»
now_pretty = datetime.now(timezone(timedelta(hours=5))).strftime("%d.%m.%Y в %H:%M (Екб)")
new2, m = re.subn(r'(const SNAPSHOT\s*=\s*")[^"]*(")', r"\g<1>"+now_pretty+r"\2", new, count=1)
if m: new = new2
else: print("⚠ SNAPSHOT-строку не нашёл — дата осталась исходной")

(D/"index.html").write_text(new, encoding="utf-8")
raws = json.loads(raw)
tot = sum(r["s1"]+r["s2"]+r["s3"] for r in raws)
print(f"index.html (страница Adelina + мой RAW): {len(new)} байт · {len(raws)} чел · сессий S1={sum(r['s1'] for r in raws)} S2={sum(r['s2'] for r in raws)} S3={sum(r['s3'] for r in raws)} = {tot}")
