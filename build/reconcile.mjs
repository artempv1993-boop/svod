import fs from 'node:fs';
import path from 'node:path';
const BOT = 'C:/Users/proninav/Documents/arm-opros-bot/results';
const KB = '\\\\nas\\doc\\KB-ARM';
const SKIP = new Set(['уат', 'domain', 'lineage', '_охват', '.git', '.obsidian']);
const norm = s => String(s || '').toLowerCase().replace(/ё/g, 'е').replace(/[^a-zа-я0-9]/g, '');

// --- анкеты бота: из .json (id, respondent, name, survey_id) + парный .md ---
const anketas = [];
for (const f of fs.readdirSync(BOT).filter(f => f.endsWith('.json'))) {
  let d; try { d = JSON.parse(fs.readFileSync(path.join(BOT, f), 'utf8')); } catch { continue; }
  if (!d.survey_id) continue;                 // оборванная сессия
  const md = f.replace(/\.json$/, '.md');
  const hasMd = fs.existsSync(path.join(BOT, md));
  const a = d.answers || {};
  const nameKey = Object.keys(a).find(k => /имя|должность|фио/i.test(k));
  anketas.push({
    file: md, slug: d.survey_id.toLowerCase(), resp: String(d.respondent_id || ''),
    name: nameKey ? String(a[nameKey]).split(',')[0].trim() : '', at: (d.created_at || '').slice(0, 10), hasMd,
  });
}
console.log(`Завершённых анкет бота (survey_id есть): ${anketas.length}`);
console.log(`  из них с .md: ${anketas.filter(a => a.hasMd).length}`);

// --- уложенные документы ---
const laid = [];
(function walk(dir) { let it; try { it = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
  for (const e of it) { if (e.isDirectory()) { if (!SKIP.has(e.name)) walk(path.join(dir, e.name)); continue; }
    if (!e.name.endsWith('.md') || e.name.includes('Резюме')) continue;
    const t = fs.readFileSync(path.join(dir, e.name), 'utf8');
    const id = (t.match(/^id:\s*(.*)$/m) || [, ''])[1].trim().replace(/^PROC-/i, '').toLowerCase();
    const owner = (t.match(/^owner:\s*(.*)$/m) || [, ''])[1].trim();
    laid.push({ slug: e.name.replace(/\.md$/, '').toLowerCase(), id, owner, nowner: norm(owner) });
  } })(KB);
console.log(`Уложено документов: ${laid.length}`);

// индекс уложенных по базовому slug (без суффикса-имени)
const laidByBase = {};
for (const l of laid) {
  const keys = new Set([l.slug, l.id].filter(Boolean));
  for (const k of keys) laidByBase[k] = (laidByBase[k] || []).push ? laidByBase[k] : (laidByBase[k] || []);
}
// матчинг каждой анкеты
const usedLaid = new Set();
let matched = 0; const notLaid = [];
// подготовим: для каждого базового slug — список уложенных (slug и slug-*)
function laidFor(slug) {
  return laid.filter(l => l.slug === slug || l.id === slug || l.slug.startsWith(slug + '-') || (l.id && l.id.startsWith(slug + '-')));
}
// сгруппируем анкеты по slug
const bySlug = {};
for (const a of anketas) (bySlug[a.slug] ??= []).push(a);

for (const [slug, group] of Object.entries(bySlug)) {
  const cands = laidFor(slug).filter(l => !usedLaid.has(l.slug));
  // сопоставляем по имени владельца, если можем; иначе просто по наличию
  for (const a of group) {
    let pick = null;
    if (a.name) {
      const an = norm(a.name);
      pick = cands.find(l => !usedLaid.has(l.slug) && l.nowner && (l.nowner.includes(an.slice(0, 8)) || an.includes(l.nowner.slice(0, 8))));
    }
    if (!pick) pick = cands.find(l => !usedLaid.has(l.slug));
    if (pick) { usedLaid.add(pick.slug); matched++; }
    else notLaid.push(a);
  }
}
const botOriginLaid = usedLaid.size;
const botLabelExact = laid.filter(l => bySlug[l.slug] || bySlug[l.id]).length;
console.log(`\n=== СВЕРКА ПО КАЖДОЙ АНКЕТЕ ===`);
console.log(`Анкет всего: ${anketas.length}`);
console.log(`  уложены (найден документ): ${matched}`);
console.log(`  НЕ уложены: ${notLaid.length}`);
console.log(`\nУложенных документов бот-происхождения: ${botOriginLaid}`);
console.log(`  из них движок метит как «бот» (точный id): ${botLabelExact}`);
console.log(`  лежат под суффиксом → метятся как «чат»: ${botOriginLaid - botLabelExact}`);

// база слуга есть в уложенных вообще?
const allLaidSlugs = laid.map(l => l.slug + ' ' + l.id).join(' ');
const byResp = {};
for (const a of notLaid) { const baseExists = allLaidSlugs.includes(a.slug.replace(/-v\d+$|-\d+$/, '')); (byResp[a.name || '— имя не указано'] ??= []).push({ slug: a.slug, at: a.at, baseExists }); }
console.log(`\n=== НЕ УЛОЖЕНО — по респондентам (${notLaid.length} анкет) ===`);
for (const [r, arr] of Object.entries(byResp).sort((a, b) => b[1].length - a[1].length))
  console.log(`  ${arr.length}× ${r}  [${arr.map(x => x.at.slice(5)).join(', ')}]`);
const absent = notLaid.filter(a => !allLaidSlugs.includes(a.slug.replace(/-v\d+$|-\d+$/, ''))).length;
console.log(`\nИз ${notLaid.length} не уложенных: базового процесса нет в KB совсем — ${absent}; частично уложенный процесс (не все анкеты) — ${notLaid.length - absent}`);
