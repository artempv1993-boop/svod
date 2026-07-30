import fs from 'node:fs';
const ENV = 'C:/Users/proninav/Documents/svod-opros/.bitrix.env';
const env = {};
for (const raw of fs.readFileSync(ENV, 'utf8').split(/\r?\n/)) { const l = raw.trim(); if (!l || l.startsWith('#')) continue; const i = l.indexOf('='); if (i > 0) env[l.slice(0, i).trim()] = l.slice(i + 1).trim(); }
const W = env.BITRIX_WEBHOOK.replace(/\/?$/, '/');
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function call(m, p = {}) { const r = await fetch(W + m, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) }); const d = await r.json(); if (d.error) throw new Error(d.error); return d; }
async function pageAll(m, p = {}) { const o = []; for (let s = 0; ; ) { const j = await call(m, { ...p, start: s }); o.push(...(j.result || [])); if (j.next == null) break; s = j.next; await sleep(300); } return o; }
const deps = await pageAll('department.get');
const byId = {}; deps.forEach(d => byId[String(d.ID)] = { id: String(d.ID), name: d.NAME, parent: d.PARENT ? String(d.PARENT) : null });
const LINE = deps.filter(d => /товаровед|обособленн/i.test(d.NAME)).map(d => String(d.ID));
const inLine = id => { let c = byId[String(id)]; for (let i = 0; c && i < 20; i++) { if (LINE.includes(c.id)) return true; c = c.parent ? byId[c.parent] : null; } return false; };
// Очистка поля ФИО из Битрикса. В штатке имя бывает «грязным»: эмодзи, номер ОП, дата приёма,
// название точки, роль — иногда БЕЗ пробела (Эльвина✅). Сначала снимаем номера/даты, затем всё
// не-кириллическое (эмодзи/цифры/латиница отклеиваются от слова), потом токен-фильтром убираем
// роли и названия ОП. \b с кириллицей в JS не работает — поэтому фильтруем по токенам, не regex.
const ROLE_PREFIX = ['товаровед', 'кассир', 'старш', 'младш', 'ведущ', 'стаж', 'оценщик', 'скупщик', 'продавец', 'специалист', 'эксперт', 'ревизор', 'отпуск'];
const POINT = new Set(['новостройка', 'нагаево', 'булгаково', 'уфа', 'чишмы', 'нефтекамск', 'сипайлово', 'спортивная', 'первомайская']);
const nlow = w => w.toLowerCase().replace(/ё/g, 'е');
const isRolePoint = w => { const l = nlow(w); return POINT.has(l) || ROLE_PREFIX.some(p => l.startsWith(p)) || l.length < 2; };
const clean = s => String(s || '')
  .replace(/ОП[-\s]?\d+/gi, ' ').replace(/КМ[-\s]?\d+/gi, ' ')
  .replace(/с\s*\d{1,2}[.,]\d{1,2}[.,]\d{2,4}/gi, ' ')       // «с 1.06.2022»
  .replace(/[^А-Яа-яЁё\- ]/g, ' ')                            // не-кириллица (эмодзи/цифры/латиница)
  .split(/\s+/).filter(w => w && !isRolePoint(w)).join(' ').trim();
const norm = s => String(s || '').toLowerCase().replace(/ё/g, 'е').replace(/[^а-я ]/g, ' ').replace(/\s+/g, ' ').trim();
const users = await pageAll('user.get', { FILTER: { ACTIVE: 'Y' } });
let out = users.map(u => {
  const raw = [u.LAST_NAME, u.NAME, u.SECOND_NAME].filter(Boolean).join(' ');
  const op = (/ОП[-\s]?(\d+)/i.exec(raw) || [])[1] || null;
  const dep = (u.UF_DEPARTMENT || []).map(String);
  const toks = clean(raw).split(' ').filter(w => /^[А-ЯЁ][а-яё-]{1,}$/.test(w)).slice(0, 3);
  return { id: String(u.ID), fio: toks.join(' '), nfio: norm(toks.join(' ')), op, pos: u.WORK_POSITION || '',
    dept: dep.map(d => byId[d]?.name).filter(Boolean)[0] || '—', line: dep.some(inLine) || !!op };
});
// Дедупликация одного человека, встречающегося в штатке несколько раз (разный порядок
// Фамилия/Имя, разные отделы). Признак «тот же человек» — общая пара токенов (фамилия+имя):
// {насертдинова, эльвина} есть и в «Насертдинова Эльвина», и в «Эльвина Насертдинова Разилевна».
const parent = out.map((_, i) => i);
const find = i => { while (parent[i] !== i) i = parent[i] = parent[parent[i]]; return i; };
const union = (a, b) => { parent[find(a)] = find(b); };
// Ключ — отсортированные ПЕРВЫЕ ДВА токена (фамилия+имя). Порядок Фам/Имя в штатке разный,
// сортировка его нормализует. Только фамилия+имя, а не любая пара: иначе тёзки по имени+отчеству
// с разными фамилиями (Чернова Ирина Борисовна / Сиухина Ирина Борисовна) слились бы ошибочно.
const pairIdx = {};
out.forEach((r, i) => {
  const t = r.nfio.split(' ').filter(Boolean);
  if (t.length < 2) return;                          // одно слово — не дедуплицируем
  const k = [t[0], t[1]].sort().join('|');
  if (pairIdx[k] != null) union(i, pairIdx[k]); else pairIdx[k] = i;
});
const groups = {};
out.forEach((r, i) => (groups[find(i)] = groups[find(i)] || []).push(r));
// лучший вариант ФИО: с настоящим отчеством (-вна/-вич/-ич) в 3-м токене, затем с ОП, затем линейный.
const hasPatronymic = r => { const t = r.nfio.split(' '); return t.length >= 3 && /(вна|вич|ична|ыч)$/.test(t[2]) ? 1 : 0; };
const better = (a, b) => (hasPatronymic(b) - hasPatronymic(a)) || (b.nfio.split(' ').length - a.nfio.split(' ').length) || (Number(!!b.op) - Number(!!a.op)) || (Number(!!b.line) - Number(!!a.line));
const dedup = Object.values(groups).map(g => {
  const best = [...g].sort(better)[0];
  return { ...best, aliases: [...new Set(g.map(r => r.nfio))], ids: g.map(r => r.id),
    op: g.map(r => r.op).find(Boolean) || null, line: g.some(r => r.line),
    dept: (g.find(r => r.dept !== '—') || best).dept, pos: g.map(r => r.pos).find(Boolean) || '' };
});
const dupCount = out.length - dedup.length;
out = dedup;
fs.writeFileSync(new URL('./roster.json', import.meta.url), JSON.stringify(out), 'utf8');

// карта «отдел → управление» (верхний уровень оргструктуры) — строится динамически,
// поэтому новые отделы подхватываются сами.
const ROOT = deps.find(d => !d.PARENT) ? String(deps.find(d => !d.PARENT).ID) : '1';
function topUpr(id) { let c = byId[String(id)], prev = c; for (let i = 0; c && i < 20; i++) { if (c.parent === ROOT || c.parent == null) return c.id === ROOT ? prev.name : c.name; prev = c; c = byId[c.parent]; } return byId[String(id)]?.name; }
const dept2upr = {};
for (const d of deps) dept2upr[d.NAME] = topUpr(d.ID);
fs.writeFileSync(new URL('./dept2upr.json', import.meta.url), JSON.stringify(dept2upr), 'utf8');
console.log('dept2upr.json:', Object.keys(dept2upr).length, 'отделов сопоставлено управлениям');
console.log('roster.json:', out.length, 'человек (после дедупликации, свёрнуто дублей', dupCount + '),',
  'линейных', out.filter(x => x.line).length, ', с ОП', out.filter(x => x.op).length);
