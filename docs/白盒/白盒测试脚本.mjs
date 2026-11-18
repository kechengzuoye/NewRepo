/**
 * 匹配分数判级函数 —— 白盒测试脚本
 *
 * 被测对象：前端「匹配分析」页面评分列里的匹配分数判级函数
 *           （frontend/src/pages/Matches.tsx 第 91–96 行）
 *
 * 测试类型：白盒测试。在真实源码的函数体上注入语句 / 判定 / 条件探针，
 *           执行用例后统计语句覆盖、判定覆盖、条件覆盖、路径覆盖，
 *           并核对圈复杂度与流程图（流程图.png）是否一致。
 *
 * 插桩只记录命中，不改变程序语义：
 *   if (条件) return X;  →  __cov.stmt('语句1'); if (__cov.dec('判定1', (条件))) { __cov.stmt('语句2'); return X; }
 *   甲 || 乙             →  __cov.op('条件1', (甲)) || __cov.op('条件2', (乙))
 *
 * 运行：node --no-warnings 白盒测试脚本.mjs
 * 退出码：任一断言失败或覆盖率未达 100% 时为 1。
 */

import fs from 'node:fs';
import path from 'node:path';
import { stripTypeScriptTypes } from 'node:module';
import { fileURLToPath } from 'node:url';

const 当前目录 = path.dirname(fileURLToPath(import.meta.url));
const 项目根目录 = path.resolve(当前目录, '..', '..');
const 源文件 = path.join(项目根目录, 'frontend', 'src', 'pages', 'Matches.tsx');
const 结果文件 = path.join(当前目录, '执行结果.txt');

// ───────────────────────── 1. 取被测源码 ─────────────────────────
const 源码 = fs.readFileSync(源文件, 'utf8');
const 函数起点 = 源码.indexOf('const getScoreColor');
if (函数起点 < 0) throw new Error('未在源文件中找到被测函数');
const 起始行号 = 源码.slice(0, 函数起点).split(/\r?\n/).length;

function 跳过字符串(代码, 位置) {
  const 引号 = 代码[位置];
  let i = 位置 + 1;
  while (i < 代码.length) {
    if (代码[i] === '\\') { i += 2; continue; }
    if (代码[i] === 引号) return i;
    i += 1;
  }
  throw new Error('字符串未闭合');
}

function 找配对括号(代码, 起点, 左括号, 右括号) {
  let 层数 = 0;
  for (let i = 起点; i < 代码.length; i += 1) {
    const 字符 = 代码[i];
    if (字符 === "'" || 字符 === '"' || 字符 === '`') { i = 跳过字符串(代码, i); continue; }
    if (字符 === 左括号) 层数 += 1;
    else if (字符 === 右括号) {
      层数 -= 1;
      if (层数 === 0) return i;
    }
  }
  throw new Error('括号不匹配');
}

const 函数体起点 = 源码.indexOf('{', 源码.indexOf('=>', 函数起点));
const 函数体终点 = 找配对括号(源码, 函数体起点, '{', '}');
const 原函数代码 = `${源码.slice(函数起点, 函数体终点 + 1)};`;
// 去掉类型标注（Node 内置能力），并收拾一下留下的空格
const 可执行代码 = stripTypeScriptTypes(原函数代码, { mode: 'strip' }).replace(
  /\(\s*score\s*\)/,
  '(score)',
);

// ───────────────────────── 2. 插桩 ─────────────────────────
const 体内起点 = 可执行代码.indexOf('{', 可执行代码.indexOf('=>'));
const 体内终点 = 找配对括号(可执行代码, 体内起点, '{', '}');
const 头部 = 可执行代码.slice(0, 体内起点 + 1);
const 尾部 = 可执行代码.slice(体内终点);
const 函数体 = 可执行代码.slice(体内起点 + 1, 体内终点);

const 语句名称 = {};
const 判定名称 = {};
const 条件名称 = {};
let 语句序号 = 0;
let 判定序号 = 0;
let 条件序号 = 0;

function 按顶层拆分或(条件) {
  const 片段 = [];
  let 层数 = 0;
  let 上次 = 0;
  for (let i = 0; i < 条件.length; i += 1) {
    const 字符 = 条件[i];
    if (字符 === "'" || 字符 === '"' || 字符 === '`') { i = 跳过字符串(条件, i); continue; }
    if ('([{'.includes(字符)) 层数 += 1;
    else if (')]}'.includes(字符)) 层数 -= 1;
    else if (层数 === 0 && 字符 === '|' && 条件[i + 1] === '|') {
      片段.push(条件.slice(上次, i));
      上次 = i + 2;
      i += 1;
    }
  }
  片段.push(条件.slice(上次));
  return 片段;
}

/** 找到从某处开始的第一条语句的分号位置 */
function 找语句结尾(代码, 起点) {
  let 层数 = 0;
  for (let i = 起点; i < 代码.length; i += 1) {
    const 字符 = 代码[i];
    if (字符 === "'" || 字符 === '"' || 字符 === '`') { i = 跳过字符串(代码, i); continue; }
    if ('([{'.includes(字符)) 层数 += 1;
    else if (')]}'.includes(字符)) 层数 -= 1;
    else if (字符 === ';' && 层数 === 0) return i;
  }
  return 代码.length - 1;
}

function 插桩函数体(代码) {
  let 输出 = '';
  let i = 0;
  const 关键字 = /\b(if|return)\b/g;

  while (i < 代码.length) {
    关键字.lastIndex = i;
    const 匹配 = 关键字.exec(代码);
    if (!匹配) { 输出 += 代码.slice(i); break; }
    输出 += 代码.slice(i, 匹配.index);

    if (匹配[1] === 'return') {
      const 结尾 = 找语句结尾(代码, 匹配.index);
      const 语句文本 = 代码.slice(匹配.index, 结尾 + 1).trim();
      const 编号 = `语句${++语句序号}`;
      语句名称[编号] = 语句文本;
      输出 += `__cov.stmt('${编号}'); ${代码.slice(匹配.index, 结尾 + 1)}`;
      i = 结尾 + 1;
      continue;
    }

    // if (条件) 单条语句
    const 左括号 = 代码.indexOf('(', 匹配.index);
    const 右括号 = 找配对括号(代码, 左括号, '(', ')');
    const 条件 = 代码.slice(左括号 + 1, 右括号);

    let 条件代码 = 条件;
    const 操作数 = 按顶层拆分或(条件);
    if (操作数.length > 1) {
      条件代码 = 操作数
        .map((片段) => {
          const 编号 = `条件${++条件序号}`;
          const 片段代码 = 片段.trim();
          条件名称[编号] = 片段代码;
          return `__cov.op('${编号}', (${片段代码}))`;
        })
        .join(' || ');
    }

    const 判定编号 = `判定${++判定序号}`;
    判定名称[判定编号] = 条件.replace(/\s+/g, ' ').trim();

    const 语句编号 = `语句${++语句序号}`;
    语句名称[语句编号] = `如果（${判定名称[判定编号]}）`;

    let 语句起点 = 右括号 + 1;
    while (语句起点 < 代码.length && /\s/.test(代码[语句起点])) 语句起点 += 1;
    if (代码[语句起点] === '{') {
      throw new Error('遇到带花括号的 if 体，当前插桩器只支持单条语句的 if');
    }
    const 结尾 = 找语句结尾(代码, 语句起点);
    const 内层文本 = 代码.slice(语句起点, 结尾 + 1);
    if (!/^return\b/.test(内层文本.trim())) {
      throw new Error(`不支持的 if 体，请先扩展插桩器：${内层文本.trim()}`);
    }

    const 内层编号 = `语句${++语句序号}`;
    语句名称[内层编号] = 内层文本.trim();

    输出 +=
      `__cov.stmt('${语句编号}'); if (__cov.dec('${判定编号}', (${条件代码}))) ` +
      `{ __cov.stmt('${内层编号}'); ${内层文本} }`;
    i = 结尾 + 1;
  }
  return 输出;
}

const 插桩后代码 = `${头部}${插桩函数体(函数体)}${尾部}`;
const 构造器 = new Function('__cov', `${插桩后代码}\nreturn getScoreColor;`);

// ───────────────────────── 3. 探针与用例 ─────────────────────────
function 新建探针() {
  const 语句 = new Map();
  const 判定 = new Map();
  const 条件 = new Map();
  return {
    stmt(编号) { 语句.set(编号, (语句.get(编号) || 0) + 1); },
    dec(编号, 值) {
      const 格 = 判定.get(编号) || { 真: 0, 假: 0 };
      if (值) 格.真 += 1; else 格.假 += 1;
      判定.set(编号, 格);
      return 值;
    },
    op(编号, 值) {
      const 格 = 条件.get(编号) || { 真: 0, 假: 0 };
      if (值) 格.真 += 1; else 格.假 += 1;
      条件.set(编号, 格);
      return 值;
    },
    数据: { 语句, 判定, 条件 },
  };
}

const 用例表 = [
  { 编号: '用例01', 输入: 95, 期望: 'text-emerald-600', 说明: '高匹配典型值' },
  { 编号: '用例02', 输入: 80, 期望: 'text-emerald-600', 说明: '边界：80 分（含等号）' },
  { 编号: '用例03', 输入: 79.9, 期望: 'text-amber-500', 说明: '80 分的下沿' },
  { 编号: '用例04', 输入: 60, 期望: 'text-amber-500', 说明: '边界：60 分（含等号）' },
  { 编号: '用例05', 输入: 59.9, 期望: 'text-destructive', 说明: '60 分的下沿' },
  { 编号: '用例06', 输入: 0, 期望: 'text-destructive', 说明: '合法下界 0 分' },
  { 编号: '用例07', 输入: undefined, 期望: '', 说明: '未提供分数（空值）' },
  { 编号: '用例08', 输入: null, 期望: '', 说明: '未提供分数（空值）' },
  { 编号: '用例09', 输入: -5, 期望: 'text-destructive', 说明: '越界负值' },
  { 编号: '用例10', 输入: 120, 期望: 'text-emerald-600', 说明: '越界大于 100' },
  { 编号: '用例11', 输入: Number.NaN, 期望: 'text-destructive', 说明: '非数值' },
  { 编号: '用例12', 输入: 79.6, 期望: 'text-amber-500', 说明: '显示取整为 80 但判级为中匹配' },
];

const 显示输入 = (值) => {
  if (值 === undefined) return '未提供';
  if (值 === null) return '空值';
  if (typeof 值 === 'number') {
    if (Number.isNaN(值)) return '非数值';
    return String(值);
  }
  return String(值);
};

const 执行结果 = [];
for (const 用例 of 用例表) {
  const 探针 = 新建探针();
  const 函数 = 构造器(探针);
  let 实际;
  let 异常 = '';
  try {
    实际 = 函数(用例.输入);
  } catch (错误) {
    异常 = 错误 && 错误.message ? 错误.message : String(错误);
  }

  const 判定取值 = new Map();
  for (const [编号, 格] of 探针.数据.判定.entries()) {
    判定取值.set(编号, 格.真 > 0);
  }
  const 判定1 = 判定取值.get('判定1');
  const 判定2 = 判定取值.get('判定2');
  const 判定3 = 判定取值.get('判定3');
  let 路径 = '路径？';
  if (判定1 === true) 路径 = '路径一';
  else if (判定1 === false) 路径 = 判定2 ? '路径二' : 判定3 ? '路径三' : '路径四';

  执行结果.push({
    ...用例,
    实际,
    异常,
    通过: !异常 && Object.is(实际, 用例.期望),
    路径,
    命中语句: [...探针.数据.语句.keys()],
    判定取值,
    命中条件: [...探针.数据.条件.entries()].map(([编号, 格]) => ({
      编号,
      真: 格.真,
      假: 格.假,
    })),
  });
}

// ───────────────────────── 4. 汇总覆盖 ─────────────────────────
const 语句用例 = new Map();
const 判定用例 = new Map();
const 条件用例 = new Map();
const 路径用例 = new Map();

for (const 结果 of 执行结果) {
  if (!结果.通过) continue;
  for (const 编号 of 结果.命中语句) {
    if (!语句用例.has(编号)) 语句用例.set(编号, []);
    语句用例.get(编号).push(结果.编号);
  }
  for (const [编号, 取值] of 结果.判定取值.entries()) {
    const 键 = `${编号}${取值 ? '真' : '假'}`;
    if (!判定用例.has(键)) 判定用例.set(键, []);
    判定用例.get(键).push(结果.编号);
  }
  for (const 项 of 结果.命中条件) {
    const 键 = `${项.编号}${项.真 > 0 ? '真' : '假'}`;
    if (!条件用例.has(键)) 条件用例.set(键, []);
    条件用例.get(键).push(结果.编号);
  }
  if (!路径用例.has(结果.路径)) 路径用例.set(结果.路径, []);
  路径用例.get(结果.路径).push(结果.编号);
}

const 全部语句 = Object.keys(语句名称);
const 全部判定 = Object.keys(判定名称);
const 全部条件 = Object.keys(条件名称);
const 全部路径 = ['路径一', '路径二', '路径三', '路径四'];

const 已覆盖语句 = 全部语句.filter((编号) => 语句用例.has(编号));
const 已覆盖判定 = 全部判定
  .flatMap((编号) => [`${编号}真`, `${编号}假`])
  .filter((键) => 判定用例.has(键));
const 已覆盖条件 = 全部条件
  .flatMap((编号) => [`${编号}真`, `${编号}假`])
  .filter((键) => 条件用例.has(键));
const 已覆盖路径 = 全部路径.filter((名称) => 路径用例.has(名称));

const 失败用例 = 执行结果.filter((结果) => !结果.通过);

// 控制流图：入口 1 + 判定 3 + 返回语句 4 + 出口 1 = 9 个节点；
// 边 = 入口→判定一 1 条 + 每个判定 2 条 + 每个返回→出口 4 条 = 11 条。
const 返回语句数 = 全部语句.filter((编号) => /^return\b/.test(语句名称[编号])).length;
const 节点数 = 1 + 全部判定.length + 返回语句数 + 1;
const 边数 = 1 + 全部判定.length * 2 + 返回语句数;
const 圈复杂度 = 边数 - 节点数 + 2;

// ───────────────────────── 5. 输出 ─────────────────────────
const 对宽 = (值, 宽度) => {
  const 文本 = String(值);
  const 视觉宽 = [...文本].reduce(
    (总, 字) => 总 + (/[\u3000-\u303f\u4e00-\u9fa5\uff00-\uffef]/.test(字) ? 2 : 1),
    0,
  );
  return 文本 + ' '.repeat(Math.max(0, 宽度 - 视觉宽));
};
const 分隔线 = (符号 = '─', 长度 = 108) => 符号.repeat(长度);

const 输出 = [];
输出.push('匹配分数判级函数 —— 白盒测试执行结果');
输出.push(分隔线());
输出.push(`执行时间：${new Date().toLocaleString('zh-CN', { hour12: false })}　运行环境：Node ${process.version}`);
输出.push('');
输出.push('【被测对象】');
输出.push('  名称：匹配分数判级函数');
输出.push(`  位置：前端「匹配分析」页面的评分列，源码第 ${起始行号}–${起始行号 + 5} 行`);
输出.push('  形态：页面内的纯函数——输入一个匹配分数，返回一个表示等级的样式类名');
输出.push('  输入：0 到 100 的匹配分数；报告未完成或分析失败时没有分数');
输出.push('  输出：绿色（高匹配）、琥珀色（中匹配）、红色（低匹配）、不染色（无等级）');
输出.push('  被测内容：判级函数的全部语句、判定、条件与四条执行路径');
输出.push('  不在本次范围：分数如何产生（由 AI 分析给出）、页面实际渲染效果');
输出.push('  测试类型：白盒测试（插桩统计覆盖率，不只看输入输出）');
输出.push('');
输出.push('【被测函数原文】');
for (const 行 of 原函数代码.trimEnd().split(/\r?\n/)) 输出.push(`  ${行}`);
输出.push('');
输出.push('【插桩后的代码（探针不改变语义）】');
for (const 行 of 插桩后代码.trimEnd().split(/\r?\n/)) 输出.push(`  ${行}`);
输出.push('');

输出.push('【用例执行表】');
输出.push(对宽('用例', 8) + 对宽('输入', 10) + 对宽('期望等级', 18) + 对宽('实际等级', 18) + 对宽('路径', 8) + '结论');
输出.push(分隔线('·'));
const 等级名称 = {
  'text-emerald-600': '高匹配（绿）',
  'text-amber-500': '中匹配（琥珀）',
  'text-destructive': '低匹配（红）',
  '': '无等级（不染色）',
};
for (const 结果 of 执行结果) {
  输出.push(
    对宽(结果.编号, 8) +
      对宽(显示输入(结果.输入), 10) +
      对宽(等级名称[结果.期望] ?? '未知', 18) +
      对宽(结果.异常 ? `异常：${结果.异常}` : (等级名称[结果.实际] ?? '未知'), 18) +
      对宽(结果.路径, 8) +
      (结果.通过 ? '通过' : '失败'),
  );
}
输出.push('');

输出.push('【语句覆盖】');
输出.push(对宽('编号', 8) + 对宽('语句', 54) + 对宽('是否覆盖', 10) + '覆盖用例');
输出.push(分隔线('·'));
for (const 编号 of 全部语句) {
  const 用例们 = 语句用例.get(编号) || [];
  输出.push(对宽(编号, 8) + 对宽(语句名称[编号], 54) + 对宽(用例们.length ? '已覆盖' : '未覆盖', 10) + (用例们.join('、') || '—'));
}
输出.push(`  语句覆盖率：${已覆盖语句.length}/${全部语句.length}`);
输出.push('');

输出.push('【判定 / 分支覆盖】');
输出.push(对宽('编号', 8) + 对宽('判定条件', 40) + 对宽('取真', 34) + '取假');
输出.push(分隔线('·'));
for (const 编号 of 全部判定) {
  const 真 = 判定用例.get(`${编号}真`) || [];
  const 假 = 判定用例.get(`${编号}假`) || [];
  输出.push(
    对宽(编号, 8) +
      对宽(判定名称[编号], 40) +
      对宽(真.length ? `已覆盖（${真.join('、')}）` : '未覆盖', 34) +
      (假.length ? `已覆盖（${假.join('、')}）` : '未覆盖'),
  );
}
输出.push(`  判定分支覆盖率：${已覆盖判定.length}/${全部判定.length * 2}`);
输出.push('');

输出.push('【条件覆盖（“或”的两侧）】');
输出.push(对宽('编号', 8) + 对宽('条件表达式', 30) + 对宽('取真', 22) + '取假');
输出.push(分隔线('·'));
for (const 编号 of 全部条件) {
  const 真 = 条件用例.get(`${编号}真`) || [];
  const 假 = 条件用例.get(`${编号}假`) || [];
  输出.push(
    对宽(编号, 8) +
      对宽(条件名称[编号], 30) +
      对宽(真.length ? `已覆盖（${真.join('、')}）` : '未取真', 22) +
      (假.length ? `已覆盖（${假.join('、')}）` : '未取假'),
  );
}
输出.push(`  条件覆盖率：${已覆盖条件.length}/${全部条件.length * 2}（条件2 只在条件1 为假时求值）`);
输出.push('');

输出.push('【路径覆盖】');
输出.push(对宽('路径', 8) + 对宽('条件', 24) + 对宽('结果', 24) + '覆盖用例');
输出.push(分隔线('·'));
const 路径说明 = {
  路径一: ['分数未提供', '无等级（不染色）'],
  路径二: ['分数不低于 80 分', '高匹配（绿色）'],
  路径三: ['分数不低于 60 分', '中匹配（琥珀色）'],
  路径四: ['分数低于 60 分', '低匹配（红色）'],
};
for (const 名称 of 全部路径) {
  const 用例们 = 路径用例.get(名称) || [];
  输出.push(对宽(名称, 8) + 对宽(路径说明[名称][0], 24) + 对宽(路径说明[名称][1], 24) + (用例们.join('、') || '—'));
}
输出.push(`  路径覆盖率：${已覆盖路径.length}/${全部路径.length}`);
输出.push('');

输出.push('【圈复杂度核对】');
输出.push(`  节点数 ${节点数}，边数 ${边数}，圈复杂度 = 边数 − 节点数 + 2 = ${圈复杂度}`);
输出.push(`  判定数 ${全部判定.length}，圈复杂度 = 判定数 + 1 = ${全部判定.length + 1}`);
输出.push(`  独立路径数应等于圈复杂度：实测 ${已覆盖路径.length} 条可达路径`);
输出.push('');

输出.push(分隔线());
输出.push(`用例：${执行结果.length} 条，通过 ${执行结果.length - 失败用例.length} 条，失败 ${失败用例.length} 条。`);
输出.push(
  `覆盖：语句 ${已覆盖语句.length}/${全部语句.length}，判定分支 ${已覆盖判定.length}/${全部判定.length * 2}，` +
    `条件 ${已覆盖条件.length}/${全部条件.length * 2}，路径 ${已覆盖路径.length}/${全部路径.length}。`,
);

const 全部覆盖 =
  已覆盖语句.length === 全部语句.length &&
  已覆盖判定.length === 全部判定.length * 2 &&
  已覆盖条件.length === 全部条件.length * 2 &&
  已覆盖路径.length === 全部路径.length;
const 成功 = 失败用例.length === 0 && 全部覆盖;
输出.push(成功 ? '结论：全部用例通过，语句 / 判定 / 条件 / 路径覆盖均为 100%。' : '结论：存在失败用例或未覆盖项，见上表。');

const 报告 = `${输出.join('\n')}\n`;
fs.writeFileSync(结果文件, 报告, 'utf8');
process.stdout.write(报告);

if (!成功) process.exitCode = 1;
