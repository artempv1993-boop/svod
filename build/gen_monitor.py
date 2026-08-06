# -*- coding: utf-8 -*-
"""Построение RAW (как у Adelina) из справочника СКС + валидной проходки survey-bot."""
import json, re, sys
from pathlib import Path
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\proninav\Documents\survey-bot")
DIR = json.load(open(BASE / "storage/directory/current.json", encoding="utf-8"))
OUT = BASE / "storage/output"
TEST = {"Пронин", "Абдуллин", "Данилова", "Чусовитина"}   # тест-команда
RAW_MODE = True   # True = как у Adelina (ВСЕ сессии, вкл. тест и пустые); False = по новому (валидные, без теста)

# ---------- дерево управлений ----------
deps = DIR["departments"];  deps = list(deps.values()) if isinstance(deps, dict) else deps
depmap = {d["bitrix_id"]: d for d in deps}
def uo(dep_id):
    d = depmap.get(dep_id)
    if not d: return ("—", "—")
    parts = [p.strip() for p in d["path"].split("/")]
    u = parts[1] if len(parts) >= 2 else d["name"]
    return (u, d["name"])

# ---------- парсер frontmatter ----------
def fm(t):
    d = {}
    if t.lstrip().startswith("---"):
        L = t.splitlines(); i1 = next((i for i in range(1, len(L)) if L[i].strip() == "---"), 0)
        for l in L[1:i1]:
            if l.strip() and not l.lstrip().startswith("#"):
                m = re.match(r"^([^:\s][^:]*):\s?(.*)$", l)
                if m: d[m.group(1).strip()] = m.group(2).strip().strip('"')
    return d
def I(v):
    try: return int(float(v))
    except: return 0

# ---------- валидная проходка по survey-bot ----------
# passage[bitrix_id] = {"s1":n,"s2":n,"s3":n,"last":iso, "info":(f,path,pos)}
passage = defaultdict(lambda: {"s1":0,"s2":0,"s3":0,"last":"","f":"","path":"","d":""})
def note(pid, key, valid, d, name, path, pos):
    p = passage[pid]
    if RAW_MODE or valid: p[key]+=1
    ca = d.get("created_at") or d.get("date") or ""
    if ca > p["last"]: p["last"]=ca
    if not p["f"]: p["f"]=name; p["path"]=path; p["d"]=pos

for f in (OUT/"process_survey").rglob("*.md"):
    t=f.read_text(encoding="utf-8",errors="replace"); d=fm(t)
    pid=I(d.get("owner_bitrix_id"))
    undef="не определ" in (d.get("id","")+d.get("process","")).lower()
    valid=(not undef) and (len(re.findall(r"\*\*BR-\d",t))>=1 or "🟢" in t)
    owner=d.get("owner","")
    note(pid,"s1",valid,d,owner.split(",")[0], d.get("owner_department_path",""), (owner.split(",")[1].strip() if "," in owner else ""))
for f in (OUT/"gap_survey").rglob("*.md"):
    t=f.read_text(encoding="utf-8",errors="replace"); d=fm(t)
    pid=I(d.get("respondent_bitrix_id"))
    valid=(I(d.get("questions_closed"))+I(d.get("questions_closed_soft"))+I(d.get("questions_partial")))>=1
    resp=d.get("respondent","")
    note(pid,"s2",valid,d,resp.split(",")[0], d.get("op",""), (resp.split(",")[1].strip() if "," in resp else ""))
for f in (OUT/"workday_photo").rglob("*.md"):
    t=f.read_text(encoding="utf-8",errors="replace"); d=fm(t)
    pid=I(d.get("owner_bitrix_id"))
    acts=len(re.findall(r"\bACT-\d",t)); full=float(d.get("полнота","0") or 0)
    valid= acts>=1 and full>=0.3
    note(pid,"s3",valid,d,d.get("сотрудник",""), d.get("подразделение_путь",""), d.get("должность",""))

# ---------- роль товаровед/скупщик ----------
def is_tovar(pos, o):
    s=(pos+" "+o).lower()
    return any(k in s for k in ("товаровед","скупщик","продавец"))

# ---------- сборка RAW по всему справочнику ----------
emps = DIR["employees"];  emps = list(emps.values()) if isinstance(emps, dict) else emps
RAW=[]; used=set()
def surname(f):
    p=(f or "").split(); return p[0] if p else ""
for e in emps:
    if not e.get("is_active"): continue
    f=e.get("full_name") or ((e.get("last_name","")+" "+e.get("first_name","")+" "+e.get("middle_name","")).strip())
    if not f or re.search(r"[✅◽]|КМ-\d|ОП-\d|тест", f): continue   # точки-аккаунты/мусор
    pid=e["bitrix_id"]; used.add(pid)
    u,o = uo(e.get("department_bitrix_id"))
    d=e.get("position_title","") or ""
    p=passage.get(pid)
    if p and (RAW_MODE or surname(f) not in TEST):
        s1,s2,s3,last = p["s1"],p["s2"],p["s3"],p["last"]
    else:
        s1=s2=s3=0; last=""
    RAW.append({"f":f,"u":u,"o":o,"d":d,"t":e.get("question_tier","T1"),
                "s1":s1,"s2":s2,"s3":s3,"vs":s1+s2+s3,"last":last,
                "tv":1 if is_tovar(d,o) else 0})

# проходка от людей, которых нет в активном справочнике (новые/точки) — добавим, чтобы не терять
for pid,p in passage.items():
    if pid in used or not (p["s1"]+p["s2"]+p["s3"]): continue
    f=p["f"] or f"id{pid}"
    if surname(f) in TEST or re.search(r"[✅]|КМ-\d|ОП-\d", f): continue
    path=p["path"]; parts=[x.strip() for x in re.split(r"[/»]", path) if x.strip()]
    u = next((x for x in parts if "правлен" in x.lower()), (parts[0] if parts else "—"))
    o = parts[-1] if parts else "—"
    RAW.append({"f":f,"u":u,"o":o,"d":p["d"],"t":"T1",
                "s1":p["s1"],"s2":p["s2"],"s3":p["s3"],"vs":p["s1"]+p["s2"]+p["s3"],
                "last":p["last"],"tv":1 if is_tovar(p["d"],o) else 0})

RAW.sort(key=lambda r: r["f"])

# ---------- статистика ----------
def stat(subset):
    tot=len(subset); passed=sum(1 for r in subset if r["vs"]>0)
    sess=sum(r["vs"] for r in subset)
    s1=sum(1 for r in subset if r["s1"]>0); s2=sum(1 for r in subset if r["s2"]>0); s3=sum(1 for r in subset if r["s3"]>0)
    ss1=sum(r["s1"] for r in subset); ss2=sum(r["s2"] for r in subset); ss3=sum(r["s3"] for r in subset)
    uni=set(r["u"] for r in subset); cov=set(r["u"] for r in subset if r["vs"]>0)
    return dict(tot=tot,passed=passed,sess=sess,s1=s1,s2=s2,s3=s3,ss1=ss1,ss2=ss2,ss3=ss3,uprav=len(uni),cov=len(cov))

emp_tab=[r for r in RAW if not r["tv"]]; tov_tab=[r for r in RAW if r["tv"]]
stats=dict(all=stat(RAW), emp=stat(emp_tab), tov=stat(tov_tab), total=len(RAW))

Path("raw.json").write_text(json.dumps(RAW,ensure_ascii=False), encoding="utf-8")
Path("stats.json").write_text(json.dumps(stats,ensure_ascii=False,indent=1), encoding="utf-8")

print(f"Всего в своде: {len(RAW)} чел (сотрудники {len(emp_tab)} + товароведы/скупщики {len(tov_tab)})")
for k,lbl in (("emp","Сотрудники"),("tov","Товароведы/скупщики"),("all","ВСЕГО")):
    s=stats[k]; print(f"  [{lbl}] прошли {s['passed']}/{s['tot']} · сессий {s['sess']} (S1={s['s1']}чел/{s['ss1']}сес S2={s['s2']}/{s['ss2']} S3={s['s3']}/{s['ss3']}) · управлений охвачено {s['cov']}/{s['uprav']}")
