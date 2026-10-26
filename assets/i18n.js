/* 全站语言切换：简体（原文）/ 繁體 / English。
 *
 * 页面的原文是简体中文，写在 HTML 和各个 app.js 里。这里不改业务代码，
 * 只在渲染完成后替换文本节点和少量属性（placeholder / title / aria-label / alt），
 * 再用 MutationObserver 跟上后面动态渲染出来的内容。
 *
 *  - 繁體：用 assets/i18n-hant.js 里的表（由 scripts/build_i18n_hant.py 从
 *    OpenCC s2hk 反推）逐字 + 最长词组匹配，知识点名称、题目这些内容也会转。
 *  - English：查 assets/i18n-en.js 的界面词典；查不到的中文原样保留
 *    （课程内容没有英文版，见 README 的说明）。
 */
(function (global) {
  'use strict';

  var SUPPORTED = { 'zh-Hans': 1, 'zh-Hant': 1, en: 1 };
  var ALIAS = {
    zh: 'zh-Hans', 'zh-cn': 'zh-Hans', 'zh-sg': 'zh-Hans', hans: 'zh-Hans', 'zh-hans': 'zh-Hans',
    'zh-hant': 'zh-Hant', 'zh-tw': 'zh-Hant', 'zh-hk': 'zh-Hant', 'zh-mo': 'zh-Hant', hant: 'zh-Hant',
    tw: 'zh-Hant', hk: 'zh-Hant',
    en: 'en', 'en-us': 'en', 'en-gb': 'en', 'en-au': 'en'
  };
  var STORE_KEY = 'cmt.lang';
  /* 本站面向香港，没有指定语言时直接进繁體（香港字形）。 */
  var DEFAULT_LANG = 'zh-Hant';
  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, CODE: 1, PRE: 1 };
  var ATTRS = ['placeholder', 'title', 'aria-label', 'aria-description', 'alt'];
  var CJK = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/;

  var lang = DEFAULT_LANG;
  var textOriginals = new Map();  // Text -> { src, out }
  var attrOriginals = new Map();  // Element -> { attr: { src, out } }
  var listeners = [];
  var observer = null;
  var applying = false;

  /* ---------------------------------------------------------------- 语言解析 */
  function normalize(value) {
    if (!value) return null;
    if (SUPPORTED[value]) return value;
    var key = String(value).trim().toLowerCase();
    return ALIAS[key] || null;
  }

  function readStored() {
    try { return normalize(global.localStorage.getItem(STORE_KEY)); } catch (e) { return null; }
  }

  function writeStored(value) {
    try { global.localStorage.setItem(STORE_KEY, value); } catch (e) { /* 隐私模式 */ }
  }

  /* ---------------------------------------------------------------- 简→繁 */
  var hantChars = null;
  var hantPhrases = null;
  var hantMax = 1;

  function loadHant() {
    var data = global.__I18N_HANT__;
    if (!data) return false;
    hantChars = Object.create(null);
    var packed = data.chars || '';
    for (var i = 0; i + 1 < packed.length; i += 2) hantChars[packed.charAt(i)] = packed.charAt(i + 1);
    hantPhrases = data.phrases || {};
    for (var key in hantPhrases) {
      if (key.length > hantMax) hantMax = key.length;
    }
    return true;
  }

  function toHant(text) {
    if (!hantChars && !loadHant()) return text;
    var out = '';
    var i = 0;
    while (i < text.length) {
      var hit = null;
      for (var n = Math.min(hantMax, text.length - i); n >= 2; n--) {
        var piece = text.substr(i, n);
        if (hantPhrases[piece]) { hit = hantPhrases[piece]; i += n; break; }
      }
      if (hit !== null) { out += hit; continue; }
      var ch = text.charAt(i);
      out += hantChars[ch] || ch;
      i += 1;
    }
    return out;
  }

  /* ---------------------------------------------------------------- 英译 */
  var dict = null;
  var patterns = [];

  function loadDict() {
    if (dict) return true;
    if (!global.__I18N_EN__) return false;
    dict = global.__I18N_EN__.ui || {};
    patterns = global.__I18N_EN__.patterns || [];
    return true;
  }

  function toEnglish(text, depth) {
    if (!loadDict()) return null;
    depth = depth || 0;
    var hit = dict[text];
    if (hit != null) return hit;
    // 同一句话在源码里有时用全角括号、有时用半角，两种都试一遍
    var variants = [text];
    var ascii = text.replace(/（/g, '(').replace(/）/g, ')');
    if (ascii !== text) variants.push(ascii);
    for (var v = 0; v < variants.length; v++) {
      var src = variants[v];
      for (var i = 0; i < patterns.length; i++) {
        var rule = patterns[i];
        var m = src.match(rule[0]);
        if (!m) continue;
        var repl = rule[1];
        // 函数式替换收的是整个 match 数组，m[1] 起才是捕获组
        if (typeof repl === 'function') return repl(m);
        return src.replace(rule[0], repl);
      }
    }
    // 「小满 · 一年级 · 人教版」这类用 · 拼起来的短标签：逐段翻译，
    // 认不出来的段（人名、章节名这些内容）原样留着。
    if (depth < 3 && text.indexOf(' · ') > 0) {
      var parts = text.split(' · ');
      var done = parts.map(function (part) {
        var piece = toEnglish(part.trim(), depth + 1);
        return piece == null ? part : piece;
      });
      if (done.join(' · ') !== text) return done.join(' · ');
    }
    return null;
  }

  /* ---------------------------------------------------------------- 翻译单串 */
  function translate(src) {
    if (lang === 'zh-Hans' || !src || !CJK.test(src)) return src;
    var lead = src.match(/^\s*/)[0];
    var tail = src.match(/\s*$/)[0];
    var core = src.slice(lead.length, src.length - tail.length);
    if (!core) return src;
    var out = lang === 'zh-Hant' ? toHant(core) : toEnglish(core);
    if (out == null || out === core) return src;
    return lead + out + tail;
  }

  /* ---------------------------------------------------------------- DOM 遍历 */
  function translateTextNode(node) {
    var current = node.nodeValue;
    if (!current) return;
    var rec = textOriginals.get(node);
    // 业务代码直接改写同一个节点时，以新内容为原文重新翻译
    if (rec && current !== rec.out) rec = null;
    if (rec) return;
    var out = translate(current);
    textOriginals.set(node, { src: current, out: out });
    if (out !== current) {
      applying = true;
      node.nodeValue = out;
      applying = false;
    }
  }

  function translateAttrs(el) {
    for (var i = 0; i < ATTRS.length; i++) {
      var name = ATTRS[i];
      if (!el.hasAttribute(name)) continue;
      var current = el.getAttribute(name);
      if (!current || !CJK.test(current)) continue;
      var store = attrOriginals.get(el);
      if (!store) { store = Object.create(null); attrOriginals.set(el, store); }
      var rec = store[name];
      if (rec && current !== rec.out) rec = store[name] = null;
      if (rec) continue;
      var out = translate(current);
      store[name] = { src: current, out: out };
      if (out !== current) {
        applying = true;
        el.setAttribute(name, out);
        applying = false;
      }
    }
  }

  function walk(node) {
    if (node.nodeType === 3) { translateTextNode(node); return; }
    if (node.nodeType !== 1) return;
    if (SKIP_TAGS[node.tagName]) return;
    if (node.hasAttribute('data-i18n-skip')) return;
    translateAttrs(node);
    for (var child = node.firstChild; child; child = child.nextSibling) walk(child);
  }

  function applyAll() {
    walk(document.documentElement);
    syncButtons();
  }

  function restoreAll() {
    textOriginals.forEach(function (rec, node) {
      if (node.nodeValue === rec.out) node.nodeValue = rec.src;
    });
    textOriginals.clear();
    attrOriginals.forEach(function (store, el) {
      Object.keys(store).forEach(function (name) {
        var rec = store[name];
        if (rec && el.getAttribute(name) === rec.out) el.setAttribute(name, rec.src);
      });
    });
    attrOriginals.clear();
  }

  /* ---------------------------------------------------------------- 观察动态内容 */
  function onMutations(records) {
    if (applying) return;
    for (var i = 0; i < records.length; i++) {
      var rec = records[i];
      if (rec.type === 'characterData') {
        translateTextNode(rec.target);
      } else if (rec.type === 'childList') {
        for (var j = 0; j < rec.addedNodes.length; j++) walk(rec.addedNodes[j]);
      } else if (rec.type === 'attributes') {
        translateAttrs(rec.target);
      }
    }
  }

  function startObserver() {
    if (observer || !global.MutationObserver) return;
    observer = new MutationObserver(onMutations);
    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS
    });
  }

  /* ---------------------------------------------------------------- 切换按钮 */
  /* 按钮上的 data-lang 只出现在 .lang-btn 上；<html> 用的是 data-i18n-lang。
   * 两处曾共用 data-lang，于是 closest('[data-lang]') 会一路走到 <html>，
   * 页面上任何一次点击都被当成切换语言并被 preventDefault 掉——整站按钮全部失效。 */
  var BTN = '.lang-btn[data-lang]';

  function syncButtons() {
    var buttons = document.querySelectorAll(BTN);
    for (var i = 0; i < buttons.length; i++) {
      var btn = buttons[i];
      var on = normalize(btn.getAttribute('data-lang')) === lang;
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.classList.toggle('on', on);
    }
  }

  function bindButtons() {
    document.addEventListener('click', function (event) {
      var btn = event.target && event.target.closest ? event.target.closest(BTN) : null;
      if (!btn) return;
      event.preventDefault();
      setLang(btn.getAttribute('data-lang'), { remember: true, updateUrl: true });
    });
    syncButtons();
  }

  /* ---------------------------------------------------------------- 对外接口 */
  function setLang(next, options) {
    var value = normalize(next);
    if (!value) return;
    var opts = options || {};
    var changed = value !== lang;
    lang = value;

    document.documentElement.setAttribute('lang', lang);
    document.documentElement.setAttribute('data-i18n-lang', lang);
    if (opts.remember !== false) writeStored(lang);

    if (changed) {
      restoreAll();
      if (lang !== 'zh-Hans') applyAll();
      else syncButtons();
      if (opts.updateUrl) updateUrl();
      for (var i = 0; i < listeners.length; i++) {
        try { listeners[i](lang); } catch (e) { /* 单个监听器出错不影响其他 */ }
      }
    }
  }

  function updateUrl() {
    try {
      var url = new URL(global.location.href);
      // 只在偏离默认语言时才写 ?lang=，默认的繁體保持地址栏干净
      if (lang === DEFAULT_LANG) url.searchParams.delete('lang');
      else url.searchParams.set('lang', lang);
      global.history.replaceState(null, '', url.toString());
    } catch (e) { /* 老浏览器 */ }
  }

  function boot() {
    var fromQuery = normalize(new URLSearchParams(global.location.search).get('lang'));
    lang = fromQuery || readStored() || DEFAULT_LANG;
    document.documentElement.setAttribute('lang', lang);
    document.documentElement.setAttribute('data-i18n-lang', lang);

    if (lang !== 'zh-Hans') {
      document.documentElement.classList.add('i18n-booting');
      // 数据文件没加载上时也要把内容放出来，不能一直藏着
      global.setTimeout(function () {
        document.documentElement.classList.remove('i18n-booting');
      }, 1500);
    }

    var start = function () {
      bindButtons();
      if (lang !== 'zh-Hans') applyAll();
      startObserver();
      document.documentElement.classList.remove('i18n-booting');
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
  }

  global.I18N = {
    get lang() { return lang; },
    supported: Object.keys(SUPPORTED),
    setLang: setLang,
    t: function (text) { return translate(text); },
    toHant: toHant,
    onChange: function (fn) { if (typeof fn === 'function') listeners.push(fn); },
    /** 调试用：列出当前语言下仍然是中文的可见文本（英文模式下就是没收录的串）。 */
    untranslated: function () {
      var found = [];
      var nodes = document.querySelectorAll('body *');
      for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        if (SKIP_TAGS[el.tagName] || el.hasAttribute('data-i18n-skip')) continue;
        for (var c = el.firstChild; c; c = c.nextSibling) {
          if (c.nodeType === 3 && CJK.test(c.nodeValue) && c.nodeValue.trim()) found.push(c.nodeValue.trim());
        }
      }
      return found;
    }
  };

  boot();
})(window);
