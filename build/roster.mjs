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
const clean = s => String(s || '').replace(/[✅✔❗•]/g, ' ').replace(/ОП[-\s]?\d+/gi, ' ').replace(/\b(товаровед[\wа-яё-]*|кассир|старший|ведущий|стажер|отпуск\w*)\b/gi, ' ').replace(/\s+/g, ' ').trim();
const norm = s => String(s || '').toLowerCase().replace(/ё/g, 'е').replace(/[^а-я ]/g, ' ').replace(/\s+/g, ' ').trim();
const users = await pageAll('user.get', { FILTER: { ACTIVE: 'Y' } });
const out = users.map(u => {
  const raw = [u.LAST_NAME, u.NAME, u.SECOND_NAME].filter(Boolean).join(' ');
  const op = (/ОП[-\s]?(\d+)/i.exec(raw) || [])[1] || null;
  const dep = (u.UF_DEPARTMENT || []).map(String);
  const toks = clean(raw).split(' ').filter(w => /^[А-ЯЁ][а-яё-]{1,}$/.test(w)).slice(0, 3);
  return { id: String(u.ID), fio: toks.join(' '), nfio: norm(toks.join(' ')), op, dept: dep.map(d => byId[d]?.name).filter(Boolean)[0] || '—', line: dep.some(inLine) || !!op };
});
fs.writeFileSync(new URL('./roster.json', import.meta.url), JSON.stringify(out), 'utf8');

// карта «отдел → управление» (верхний уровень оргструктуры) — строится динамически,
// поэтому новые отделы подхватываются сами.
const ROOT = deps.find(d => !d.PARENT) ? String(deps.find(d => !d.PARENT).ID) : '1';
function topUpr(id) { let c = byId[String(id)], prev = c; for (let i = 0; c && i < 20; i++) { if (c.parent === ROOT || c.parent == null) return c.id === ROOT ? prev.name : c.name; prev = c; c = byId[c.parent]; } return byId[String(id)]?.name; }
const dept2upr = {};
for (const d of deps) dept2upr[d.NAME] = topUpr(d.ID);
fs.writeFileSync(new URL('./dept2upr.json', import.meta.url), JSON.stringify(dept2upr), 'utf8');
console.log('dept2upr.json:', Object.keys(dept2upr).length, 'отделов сопоставлено управлениям');
console.log('roster.json:', out.length, 'активных, линейных', out.filter(x => x.line).length, ', с ОП', out.filter(x => x.op).length);
