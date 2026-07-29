import json, io, sys, re, os, datetime
sys.stdout.reconfigure(encoding='utf-8')
SC = os.path.dirname(os.path.abspath(__file__))                      # svod-site/build
DATA = r'C:\Users\proninav\Documents\svod-opros\data-1a.json'       # выход коллектора svod-1a.mjs
SNAPSHOT = datetime.datetime.fromtimestamp(os.path.getmtime(DATA)).strftime('%d.%m.%Y')
d = json.load(io.open(DATA, encoding='utf-8'))
roster = json.load(io.open(os.path.join(SC, 'roster.json'), encoding='utf-8'))
deps = {x['dep']: x for x in d['departments']}
# NB: правка Щербаковой больше не нужна — в переоформленных файлах владелец указан как
# «Варуха Татьяна Викторовна» (текущая фамилия), движок относит её документы в ОУиМ верно.

def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^а-я ]', ' ', str(s).lower().replace('ё', 'е'))).strip()

# индексы справочника
full = {}; lf = {}
for r in roster:
    if r['nfio']:
        full.setdefault(r['nfio'], []).append(r)
        p = r['nfio'].split(' ')
        if len(p) >= 2:
            lf.setdefault(p[0] + ' ' + p[1], []).append(r)

def match(name):
    q = norm(name); parts = q.split(' ')
    for key in (full.get(q), lf.get(parts[0] + ' ' + parts[1]) if len(parts) >= 2 else None,
                lf.get(parts[1] + ' ' + parts[0]) if len(parts) >= 2 else None):
        if key:
            uniq = {r['id']: r for r in key}.values()
            uniq = list(uniq)
            if len(uniq) == 1:
                return uniq[0], 'ok'
            return uniq, 'amb'
    return None, 'no'

# --- распределение бота ---
TOV = 'Товароведы'
bot_to_dep = {}       # dept -> {'named': {fio:n}, 'unnamed': n, 'opinfo': {fio: 'ОП-..'}}
review = []
for p in d['bot']['people']:
    name, n = p['name'], p['n']
    toks = [w for w in norm(name).split(' ') if len(w) > 1]
    placeholder = 'не назван' in name.lower() or 'фио не' in name.lower()
    m, st = match(name)
    if placeholder:
        tgt, disp, op, kind = TOV, None, None, 'unnamed'
    elif st == 'ok' and not m['line']:
        tgt, disp, op, kind = m['dept'], m['fio'], m['op'], 'named-office'   # Пронин, Миньязов…
    elif st == 'ok' and m['line']:
        tgt, disp, op, kind = TOV, m['fio'], m['op'], 'named-tov'
    elif st == 'amb':
        tgt, disp, op, kind = TOV, name, None, 'named-amb'
    elif len(toks) >= 2:
        tgt, disp, op, kind = TOV, name, None, 'named-noroster'
    else:
        tgt, disp, op, kind = TOV, None, None, 'unnamed'
    b = bot_to_dep.setdefault(tgt, {'named': {}, 'unnamed': 0, 'op': {}})
    if disp:
        b['named'][disp] = b['named'].get(disp, 0) + n
        if op: b['op'][disp] = 'ОП-' + op
    else:
        b['unnamed'] += n
    review.append((name, n, tgt, disp or '— (ФИО не определено)', 'ОП-' + op if op else '', kind))

# --- схлопнуть бот-названных между собой по «фамилия+имя» (одна анкета — короткое имя,
#     другая — полное; это один человек) ---
def key2(f):
    p = norm(f).split(' ')
    return ' '.join(p[:2])

for b in bot_to_dep.values():
    merged = {}   # key2 -> [best_name, count, op]
    for f, n in b['named'].items():
        k = key2(f)
        if k in merged:
            merged[k][1] += n
            if len(f) > len(merged[k][0]): merged[k][0] = f
            merged[k][2] = merged[k][2] or b['op'].get(f)
        else:
            merged[k] = [f, n, b['op'].get(f)]
    b['named'] = {v[0]: v[1] for v in merged.values()}
    b['op'] = {v[0]: v[2] for v in merged.values() if v[2]}

# --- слить бот в отделы (дедупликация по ФИО: чат + бот = один человек) ---

for dep_name, b in bot_to_dep.items():
    dep = deps.get(dep_name)
    if not dep:
        continue
    dep['docs'] += sum(b['named'].values()) + b['unnamed']
    dep['bot_unnamed'] = b['unnamed']
    bot_only = []
    for f, v in sorted(b['named'].items(), key=lambda kv: -kv[1]):
        hit = next((x for x in dep['detail'] if key2(x['fio']) == key2(f)), None)
        if hit:                    # тот же товаровед сдал и в чате, и в боте — суммируем
            hit['n'] += v
            hit['bot'] = True
            if b['op'].get(f): hit['op'] = b['op'][f]
        else:                      # только через бота
            bot_only.append([f, v, b['op'].get(f, '')])
    # у Товароведов бот-only показываем отдельными чипами; у офисных — вливаем в detail
    if dep_name == TOV:
        dep['bot_named'] = bot_only
    else:
        for f, v, op in bot_only:
            dep['detail'].append({'fio': f, 'n': v, 'bot': True})
        dep['bot_named'] = []
    dep['persons'] = len(dep['detail']) + len(dep['bot_named'])

# --- управления (динамически из оргструктуры, чтобы новые отделы подхватывались) ---
dept2upr = json.load(io.open(os.path.join(SC, 'dept2upr.json'), encoding='utf-8'))

def clean_fio(f):
    f = re.sub(r'\([^)]*\)', '', f)
    f = re.sub(r'\s+(Эвридей|Первомайская|Булгаково|Нагаево|Ухтомского)\b', '', f, flags=re.I)
    return re.sub(r'\s+', ' ', f).strip()

groups = {}   # управление -> [dep, ...]
for dep_name, dep in deps.items():
    if dep_name == 'Отдел не определён':
        continue
    upr = dept2upr.get(dep_name) or 'Прочее (нет в оргструктуре)'
    groups.setdefault(upr, []).append(dep)

upr_out = []
for name, rows in groups.items():
    dd = sum(r['docs'] for r in rows); pp = sum(r['persons'] for r in rows)
    deps_out = []
    for r in sorted(rows, key=lambda r: -r['docs']):
        is_node = (r['dep'] == name)                       # отдел = само управление → руководство
        deps_out.append({
            'name': 'руководство управления' if is_node else r['dep'],
            'ruk': is_node, 'docs': r['docs'], 'people': r['persons'], 'staff': r['staff'],
            'unresolved': r.get('unresolved', 0),
            'sub': [[clean_fio(p['fio']), p['n'], p.get('op', ''), bool(p.get('bot'))] for p in r['detail']],
            'botNamed': [[clean_fio(f), v, op] for f, v, op in r.get('bot_named', [])] if r['dep'] == TOV else [],
            'botUnnamed': r.get('bot_unnamed', 0),
        })
    upr_out.append({'name': name, 'docs': dd, 'people': pp, 'deps': deps_out})
upr_out.sort(key=lambda u: -u['docs'])
und = deps.get('Отдел не определён', {'docs': 0})
upr_out.append({'name': 'Автор / отдел не определён', 'docs': und['docs'], 'people': None, 'deps': []})

t = d['totals']
named_people = sum(u['people'] for u in upr_out if u['people']) + 1
payload = {
    'meta': {'total': t['total'], 'chat': t['chat'], 'bot': t['bot'], 'people': named_people,
             'upr': len([u for u in upr_out if u['docs'] > 0 and u['name'] != 'Автор / отдел не определён']),
             'unresAuthor': t['unresolvedAuthor'], 'unresDept': t['unresolvedDept'], 'snapshot': SNAPSHOT,
             'botNamed': sum(len(b['named']) for b in bot_to_dep.values()),
             'botUnnamed': sum(b['unnamed'] for b in bot_to_dep.values())},
    'channels': [{'name': 'Чат Битрикс24', 'docs': t['chat']}, {'name': 'Telegram-бот', 'docs': t['bot']}],
    'directions': [{'n': x['name'], 'v': x['n'], 'major': i < 3} for i, x in enumerate(d['directions'])],
    'upr': upr_out,
    'botDirs': [[x['name'], x['n']] for x in d['bot']['directions']],
}
io.open(os.path.join(SC, 'payload.json'), 'w', encoding='utf-8').write(json.dumps(payload, ensure_ascii=False))

# контроль
tot_dep = sum(u['docs'] for u in upr_out)
print('КОНТРОЛЬ: сумма по управлениям+не опр =', tot_dep, '(надо', t['total'], ')', 'OK' if tot_dep == t['total'] else 'FAIL')
print('Товароведы итог:', deps[TOV]['docs'], 'док (было 3 чат + бот)')
print('bot named:', payload['meta']['botNamed'], '| bot unnamed анкет:', payload['meta']['botUnnamed'])
print()
print('=== РАСПРЕДЕЛЕНИЕ БОТА (для проверки по ФИО и ОП) ===')
for name, n, tgt, disp, op, kind in sorted(review, key=lambda r: (r[2], -r[1])):
    print(f'  {name[:34]:<34} ×{n} → {tgt[:22]:<22} | {disp[:32]:<32} {op:<8} [{kind}]')
