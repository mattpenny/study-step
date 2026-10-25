#!/usr/bin/env node
/* 界面文案清点 / 覆盖检查工具。
 *
 *   node scripts/i18n-scan.js                 # 清点各页面上的中文，写到 .i18n-inventory.json
 *   node scripts/i18n-scan.js --check en      # 用英文模式打开，列出还剩下的中文
 *   node scripts/i18n-scan.js --shots         # 顺便存截图到 .i18n-shots/
 *
 * 用本机 Chrome（playwright-core 不下载浏览器），站点要先用
 * `python -m http.server 8000` 起在 --base 指定的地址上。
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BASE = argValue('--base') || 'http://127.0.0.1:8000';
const CHECK = argValue('--check');
const SHOTS = process.argv.includes('--shots');
const SHOT_DIR = path.join(ROOT, '.i18n-shots');

function argValue(flag) {
  const i = process.argv.indexOf(flag);
  return i > -1 ? process.argv[i + 1] : null;
}

function loadPlaywright() {
  const candidates = [
    'playwright-core',
    'C:/Users/Ansum/.workbuddy-ai/binaries/node/pwtest/node_modules/playwright-core'
  ];
  for (const c of candidates) {
    try { return require(c); } catch (e) { /* 下一个 */ }
  }
  throw new Error('找不到 playwright-core');
}

function chromePath() {
  const candidates = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
  ];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  throw new Error('找不到本机 Chrome/Edge');
}

/* 每个要检查的页面状态。wait 是额外等待时间（毫秒）。 */
const STATES = [
  { name: 'home-math', url: '/' },
  { name: 'home-english', url: '/?subject=english' },
  { name: 'home-physics', url: '/?subject=physics' },
  { name: 'home-chinese', url: '/?subject=chinese' },
  { name: 'explore', url: '/explore/' },
  { name: 'explore-node', url: '/explore/#cnm_221', after: selectNode },
  { name: 'explore-search-empty', url: '/explore/', after: searchNothing },
  { name: 'explore-english', url: '/explore/?subject=english' },
  { name: 'diagnose-start', url: '/diagnose/' },
  { name: 'diagnose-grade', url: '/diagnose/', after: openGradeTab },
  { name: 'diagnose-question', url: '/diagnose/?target=cnm_221&demo=1&step=0' },
  { name: 'diagnose-result', url: '/diagnose/?target=cnm_221&demo=1&step=99' },
  { name: 'diagnose-screen', url: '/diagnose/?grade=' + encodeURIComponent('八上') + '&demo=1&step=99' },
  { name: 'children', url: '/children/' },
  { name: 'children-list', url: '/children/', after: addKid },
  { name: 'children-history', url: '/children/history.html' }
];

async function selectNode(page) {
  const first = await page.$('#list .topic-item');
  if (first) {
    await first.click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(700);
  }
}

async function searchNothing(page) {
  await page.waitForSelector('#q', { timeout: 8000 }).catch(() => {});
  await page.fill('#q', 'zzzz').catch(() => {});
  await page.waitForTimeout(500);
}

async function openGradeTab(page) {
  const tab = await page.$('.stage-tab:nth-child(2)');
  if (tab) {
    await tab.click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(400);
  }
}

async function addKid(page) {
  // 直接用页面自己的存储接口建一个孩子，比点表单稳定
  await page.evaluate(() => {
    const CC = window.CnmChildren;
    if (CC && !CC.list().length) CC.add({ name: '小满', grade: '一年级', textbook: '人教版' });
  });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(400);
}

const COLLECT = `(() => {
  const skip = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'CODE', 'PRE']);
  const cjk = /[\\u3400-\\u4dbf\\u4e00-\\u9fff\\uf900-\\ufaff]/;
  const attrs = ['placeholder', 'title', 'aria-label', 'alt'];
  const items = [];
  const push = (text, where, tag) => {
    const t = String(text).replace(/\\s+/g, ' ').trim();
    if (!t || !cjk.test(t)) return;
    items.push({ text: t, where, tag });
  };
  for (const el of document.querySelectorAll('body *')) {
    if (skip.has(el.tagName)) continue;
    if (el.hasAttribute('data-i18n-skip')) continue;
    const visible = el.offsetParent !== null || el.tagName === 'BODY';
    if (!visible) continue;
    for (const attr of attrs) {
      if (el.hasAttribute(attr)) push(el.getAttribute(attr), 'attr:' + attr, el.tagName.toLowerCase());
    }
    for (let c = el.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === 3) {
        const tag = el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
        push(c.nodeValue, 'text', tag);
      }
    }
  }
  if (document.title) push(document.title, 'title', 'title');
  return items;
})()`;

async function main() {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: chromePath(), headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });

  if (CHECK) {
    await context.addInitScript((lang) => {
      try { localStorage.setItem('cmt.lang', lang); } catch (e) { /* ignore */ }
    }, CHECK);
  }

  const seen = new Map();
  const perState = {};

  for (const state of STATES) {
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(BASE + state.url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);
    if (state.after) {
      try { await state.after(page); } catch (e) { errors.push('after: ' + e.message.split('\n')[0]); }
    }
    await page.waitForTimeout(300);

    const items = await page.evaluate(COLLECT);
    perState[state.name] = { count: items.length, errors };
    for (const item of items) {
      const rec = seen.get(item.text) || { text: item.text, count: 0, states: new Set(), where: item.where, tag: item.tag };
      rec.count += 1;
      rec.states.add(state.name);
      seen.set(item.text, rec);
    }
    if (SHOTS) {
      fs.mkdirSync(SHOT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(SHOT_DIR, state.name + '.png'), fullPage: true });
    }
    await page.close();
  }

  await browser.close();

  const list = Array.from(seen.values())
    .map((r) => ({ text: r.text, count: r.count, where: r.where, tag: r.tag, states: Array.from(r.states) }))
    .sort((a, b) => (b.text.length - a.text.length));

  const outPath = path.join(ROOT, CHECK ? '.i18n-remaining.json' : '.i18n-inventory.json');
  fs.writeFileSync(outPath, JSON.stringify({ base: BASE, states: perState, strings: list }, null, 1), 'utf8');

  const errs = Object.entries(perState).filter(([, v]) => v.errors.length);
  console.log(`states=${STATES.length} unique=${list.length} -> ${path.basename(outPath)}`);
  if (errs.length) {
    console.log('页面报错：');
    for (const [name, v] of errs) console.log('  ' + name + ': ' + v.errors.slice(0, 3).join(' | '));
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
