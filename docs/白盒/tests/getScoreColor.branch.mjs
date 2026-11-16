/**
 * 评分函数 getScoreColor 的分支覆盖用例执行器
 *
 * 目的：不复制被测逻辑，直接从真实源文件
 *   NewRepo-main/frontend/src/pages/Matches.tsx
 * 中截取 getScoreColor 的函数体，去掉类型标注（Node 内置 stripTypeScriptTypes）后执行，
 * 再对照“分支覆盖用例表”逐条断言，并统计分支 / 路径覆盖。
 *
 * 运行：node --no-warnings tests/getScoreColor.branch.mjs
 * 说明：项目尚未接入 Vitest / c8，此处为轻量测试桩；
 *       分支命中根据“每个分支的返回值互不相同”这一事实推断，属于真实可观测行为。
 */

import fs from 'node:fs';
import path from 'node:path';
import { stripTypeScriptTypes } from 'node:module';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(HERE, '..', '..');
const SOURCE = path.join(WORKSPACE, 'NewRepo-main', 'frontend', 'src', 'pages', 'Matches.tsx');
const REPORT = path.join(HERE, '运行结果.txt');

// ── 1. 从源文件中截取被测函数（含花括号配平，字符串内的括号不计） ──────────
const source = fs.readFileSync(SOURCE, 'utf8');
const lines = source.split(/\r?\n/);
const start = source.indexOf('const getScoreColor');
if (start < 0) throw new Error('未在源文件中找到 getScoreColor');

const bodyStart = source.indexOf('{', source.indexOf('=>', start));
let depth = 0;
let end = bodyStart;
for (let i = bodyStart; i < source.length; i += 1) {
  const ch = source[i];
  if (ch === "'" || ch === '"' || ch === '`') {
    const quote = ch;
    i += 1;
    while (i < source.length && source[i] !== quote) {
      if (source[i] === '\\') i += 1;
      i += 1;
    }
    continue;
  }
  if (ch === '{') depth += 1;
  if (ch === '}') {
    depth -= 1;
    if (depth === 0) {
      end = i + 1;
      break;
    }
  }
}
const snippet = `${source.slice(start, end)};`;
const startLine = source.slice(0, start).split(/\r?\n/).length;

// ── 2. 去掉类型标注并取出函数 ────────────────────────────────────────────
// 优先用 Node 内置 stripTypeScriptTypes；低版本 Node 用参数正则兜底。
const js = typeof stripTypeScriptTypes === 'function'
  ? stripTypeScriptTypes(snippet, { mode: 'strip' })
  : snippet.replace(/\(\s*score\s*\?\s*:\s*number\s*\)/, '(score)');
const getScoreColor = new Function(`${js}\nreturn getScoreColor;`)();

// ── 3. 分支覆盖用例（与文档中的用例表一一对应） ──────────────────────────
const CASES = [
  { id: 'TC01', input: 95, expected: 'text-emerald-600', desc: '高匹配典型值', path: 'P2' },
  { id: 'TC02', input: 80, expected: 'text-emerald-600', desc: '阈值边界 80（等于）', path: 'P2' },
  { id: 'TC03', input: 79.9, expected: 'text-amber-500', desc: '阈值下沿 79.9', path: 'P3' },
  { id: 'TC04', input: 60, expected: 'text-amber-500', desc: '阈值边界 60（等于）', path: 'P3' },
  { id: 'TC05', input: 59.9, expected: 'text-destructive', desc: '阈值下沿 59.9', path: 'P4' },
  { id: 'TC06', input: 0, expected: 'text-destructive', desc: '合法下界 0', path: 'P4' },
  { id: 'TC07', input: undefined, expected: '', desc: '缺少分数（undefined）', path: 'P1' },
  { id: 'TC08', input: null, expected: '', desc: '缺少分数（null，类型外输入）', path: 'P1' },
  { id: 'TC09', input: -5, expected: 'text-destructive', desc: '越界负值（无防御）', path: 'P4' },
  { id: 'TC10', input: 120, expected: 'text-emerald-600', desc: '越界超 100（无防御）', path: 'P2' },
  { id: 'TC11', input: Number.NaN, expected: 'text-destructive', desc: 'NaN（比较恒为 false）', path: 'P4' },
  { id: 'TC12', input: 79.6, expected: 'text-amber-500', desc: '四舍五入显示为 80 但颜色为琥珀', path: 'P3' },
];

const RETURN_TO_BRANCH = {
  '': 'D1-T',
  'text-emerald-600': 'D2-T',
  'text-amber-500': 'D3-T',
  'text-destructive': 'D3-F',
};

const BRANCHES = [
  ['D1-T', 'score === undefined || score === null 为真 → return \'\''],
  ['D1-F', '有分数 → 继续判断'],
  ['D2-T', 'score >= 80 为真 → 绿色'],
  ['D2-F', 'score >= 80 为假 → 继续判断'],
  ['D3-T', 'score >= 60 为真 → 琥珀色'],
  ['D3-F', 'score >= 60 为假 → 红色'],
];
const OPERANDS = [
  ['L1', 'score === undefined 为真'],
  ['L2', 'score === null 为真（undefined 为假时才求值）'],
];
const PATHS = ['P1', 'P2', 'P3', 'P4'];

// ── 4. 执行用例 ──────────────────────────────────────────────────────────
const results = CASES.map((c) => {
  const actual = getScoreColor(c.input);
  const pass = Object.is(actual, c.expected);
  const branch = pass ? RETURN_TO_BRANCH[actual] : '断言失败';
  return { ...c, actual, pass, branch };
});

const hitBranches = new Set(results.filter((r) => r.pass).map((r) => r.branch));
if (hitBranches.has('D2-T') || hitBranches.has('D3-T') || hitBranches.has('D3-F')) {
  hitBranches.add('D1-F');
}
if (hitBranches.has('D3-T') || hitBranches.has('D3-F')) hitBranches.add('D2-F');

const hitOperands = new Set();
for (const r of results) {
  if (!r.pass) continue;
  if (r.input === undefined) hitOperands.add('L1');
  if (r.input === null) hitOperands.add('L2');
}

const hitPaths = new Set(results.filter((r) => r.pass).map((r) => r.path));

// ── 5. 输出报告 ──────────────────────────────────────────────────────────
const pad = (text, width) => {
  const s = String(text);
  const visual = [...s].reduce((w, ch) => w + (/[\u4e00-\u9fa5\uff00-\uffef]/.test(ch) ? 2 : 1), 0);
  return s + ' '.repeat(Math.max(0, width - visual));
};
const line = (ch = '─', n = 96) => ch.repeat(n);

const out = [];
out.push('评分函数分支覆盖用例执行结果');
out.push(line());
out.push(`被测源文件：${path.relative(WORKSPACE, SOURCE).replace(/\\/g, '/')}  第 ${startLine} 行起`);
out.push('被测函数原文：');
for (const l of snippet.trimEnd().split(/\r?\n/)) out.push(`  ${l}`);
out.push('');
out.push('【用例执行表】');
out.push(pad('用例', 7) + pad('输入', 10) + pad('期望返回', 24) + pad('实际返回', 24) + pad('结论', 6) + '覆盖分支');
out.push(line('·'));
for (const r of results) {
  const input = r.input === undefined ? 'undefined' : r.input === null ? 'null' : String(r.input);
  const shown = Object.is(r.input, Number.NaN) ? 'NaN' : input;
  out.push(
    pad(r.id, 7) +
      pad(shown, 10) +
      pad(JSON.stringify(r.expected), 24) +
      pad(JSON.stringify(r.actual), 24) +
      pad(r.pass ? '通过' : '失败', 6) +
      r.branch,
  );
}
out.push('');

out.push('【分支覆盖】');
for (const [id, desc] of BRANCHES) {
  out.push(`  ${pad(id, 6)}${hitBranches.has(id) ? '[x]' : '[ ]'}  ${desc}`);
}
out.push(`  判定分支：${hitBranches.size}/${BRANCHES.length}`);
out.push('');

out.push('【判定内部逻辑操作数（Istanbul 会单独计入 branch）】');
for (const [id, desc] of OPERANDS) {
  out.push(`  ${pad(id, 6)}${hitOperands.has(id) ? '[x]' : '[ ]'}  ${desc}`);
}
out.push(`  逻辑操作数：${hitOperands.size}/${OPERANDS.length}`);
out.push('');

out.push('【路径覆盖】');
for (const p of PATHS) out.push(`  ${p} ${hitPaths.has(p) ? '[x]' : '[ ]'}`);
out.push(`  独立路径：${hitPaths.size}/${PATHS.length}（V(G) = 4）`);
out.push('');

out.push('【建议的最小分支覆盖集合】TC02, TC04, TC05, TC07, TC08');
const minimal = results.filter((r) => ['TC02', 'TC04', 'TC05', 'TC07', 'TC08'].includes(r.id));
const minBranches = new Set(minimal.filter((r) => r.pass).map((r) => r.branch));
if (minBranches.has('D2-T')) minBranches.add('D1-F');
if (minBranches.has('D3-T') || minBranches.has('D3-F')) {
  minBranches.add('D1-F');
  minBranches.add('D2-F');
}
out.push(`  该集合命中的判定分支：${[...minBranches].sort().join(', ')}（${minBranches.size}/${BRANCHES.length}）`);
out.push('');

const failed = results.filter((r) => !r.pass);
out.push(line());
out.push(`总计：${results.length} 条用例，通过 ${results.length - failed.length} 条，失败 ${failed.length} 条。`);
out.push(
  hitBranches.size === BRANCHES.length
    ? '结论：全部判定分支均已覆盖（100%）。'
    : '结论：仍有判定分支未覆盖，需要补充用例。',
);
out.push('备注：分支命中由返回值反推——每个分支的返回值互不相同，因此可观测且唯一。');

const text = `${out.join('\n')}\n`;
fs.writeFileSync(REPORT, text, 'utf8');
process.stdout.write(text);

if (failed.length > 0) process.exitCode = 1;
