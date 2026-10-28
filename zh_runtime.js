/* Fizgig Chinese patch - runtime translator.
 *
 * Translates the web UI at run time instead of editing Fizgig's own files:
 * every text node, title/placeholder/aria-label/alt, button label, <option>
 * label and window.confirm/alert/prompt goes through the dictionary that
 * sits above this script (window.FIZGIG_ZH). Nothing else is touched, and
 * the original English stays in data-zh-en for anything that reads it back.
 */
(function () {
  "use strict";
  var PACK = window.FIZGIG_ZH || {};
  var EXACT = PACK.exact || {};
  var SKIP = Object.create(null);
  (PACK.skip || []).forEach(function (k) { SKIP[k] = 1; });

  var MAXLEN = 600;
  var HOLE = "\u0000";

  function esc(s) { return s.replace(/[.*+?^$(){}|[\]\\]/g, "\\$&"); }

  /* A template is "Found \u0000 files in \u0000" -> "在 \u0000 里找到 \u0000 个文件".
     The pack stores holes as \u0000; we turn them into non-greedy groups. */
  var TEMPLATES = [];
  (PACK.templates || []).forEach(function (pair) {
    try {
      var en = pair[0], zh = pair[1];
      var parts = en.split("\u0000");
      var re = "^" + parts.map(esc).join("([\\s\\S]*?)") + "$";
      TEMPLATES.push({ re: new RegExp(re), zh: zh, holes: parts.length - 1,
                       first: parts[0] || "" });
    } catch (e) { /* a bad pattern must never break the page */ }
  });
  function applyTpl(t, m) {
    var out = t.zh;
    for (var k = 1; k < m.length; k++) out = out.replace(HOLE, m[k]);
    /* a plural "s" hole lands right after a Chinese character: drop it */
    return out.replace(/([\u4e00-\u9fff])s(?![A-Za-z])/g, "$1");
  }

  function lookup(plain) {
    var hit = EXACT[plain];
    if (hit !== undefined) return hit;
    if (SKIP[plain]) return null;
    if (!TEMPLATES.length || plain.length > MAXLEN) return null;
    for (var i = 0; i < TEMPLATES.length; i++) {
      var t = TEMPLATES[i];
      if (t.first && plain.indexOf(t.first) !== 0) continue;
      var m = t.re.exec(plain);
      if (m) return applyTpl(t, m);
    }
    return null;
  }

  /* The app builds some labels at draw time: "Output Directory" becomes
     "Output Directory:", a section title becomes "▶ Training Parameters".
     Try the bare string for those, and put the decoration back. */
  function lookupSmart(plain) {
    var hit = lookup(plain);
    if (hit !== null) return hit;
    var m = /^([▶▼•·‣▪\-–—*]\s+)([\s\S]+)$/.exec(plain);
    if (m) {
      var inner = lookupSmart(m[2]);
      if (inner !== null) return m[1] + inner;
    }
    if (plain.charAt(plain.length - 1) === ":") {
      var bare = lookupSmart(plain.slice(0, -1));
      if (bare !== null) return bare + "：";
    }
    return null;
  }

  /* Translate one run of text, keeping its surrounding whitespace intact. */
  function tr(s) {
    if (!s) return null;
    if (s.length > MAXLEN) return null;
    var lead = s.match(/^\s*/)[0];
    var trail = s.match(/\s*$/)[0];
    var body = s.slice(lead.length, s.length - trail.length);
    if (!body) return null;
    var zh = lookupSmart(body);
    if (zh === null || zh === undefined || zh === body) return null;
    return lead + zh + trail;
  }

  var SKIP_TAGS = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, CODE: 1, PRE: 1, SVG: 1, MATH: 1, NOSCRIPT: 1 };
  var ATTRS = ["title", "placeholder", "aria-label", "alt"];

  function kept(el) {
    for (var n = el; n && n.nodeType === 1; n = n.parentNode) {
      if (SKIP_TAGS[n.tagName]) return true;
      if (n.hasAttribute && (n.hasAttribute("data-zh-skip") || n.hasAttribute("data-zh-keep"))) return true;
      if (n.isContentEditable) return true;
    }
    return false;
  }

  function textNode(node) {
    var el = node.parentNode;
    if (!el || kept(el)) return;
    if (node.__zh === node.data) return;                 /* our own write */
    var zh = tr(node.data);
    if (zh === null) return;
    if (!el.hasAttribute("data-zh-en") && el.childNodes.length === 1) {
      el.setAttribute("data-zh-en", node.data.replace(/\s+/g, " ").trim().slice(0, 300));
    }
    var old = node.data;
    node.__zh = zh;
    node.data = zh;
    node.__zhOld = old;
  }

  function option(el) {
    /* An <option> with no value= uses its own text as the value the server
       sees. Pin that English value first, then translate only the label. */
    if (!el.hasAttribute("value")) {
      var cur = el.__zh ? (el.__zhOld || el.textContent) : el.textContent;
      el.setAttribute("value", cur.replace(/\s+/g, " ").trim());
    }
    var node = el.firstChild;
    if (node && node.nodeType === 3) textNode(node);
  }

  function element(el) {
    if (el.nodeType !== 1 || kept(el)) return;
    var tag = el.tagName;
    if (tag === "OPTION") { option(el); return; }
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i], v = el.getAttribute && el.getAttribute(a);
      if (!v) continue;
      var zh = tr(v);
      if (zh === null || el.hasAttribute("data-zh-en-" + a)) continue;
      el.setAttribute("data-zh-en-" + a, v.replace(/\s+/g, " ").trim().slice(0, 300));
      el.setAttribute(a, zh);
    }
    if (tag === "INPUT" && (el.type === "button" || el.type === "submit" || el.type === "reset")) {
      var val = el.getAttribute("value");
      if (val && !el.hasAttribute("data-zh-en-value")) {
        var z = tr(val);
        if (z !== null) {
          el.setAttribute("data-zh-en-value", val);
          el.setAttribute("value", z);
        }
      }
    }
    if (tag === "TITLE") {
      var t = tr(el.textContent);
      if (t !== null) el.textContent = t;
    }
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { textNode(root); return; }
    if (root.nodeType !== 1 && root.nodeType !== 9 && root.nodeType !== 11) return;
    if (root.nodeType === 1) element(root);
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, null, false);
    var n;
    while ((n = walker.nextNode())) {
      if (n.nodeType === 1) element(n); else textNode(n);
    }
  }

  var pending = false, queue = [];
  function flush() {
    pending = false;
    var items = queue; queue = [];
    for (var i = 0; i < items.length; i++) {
      try { walk(items[i]); } catch (e) { /* never break the app */ }
    }
  }
  function schedule(nodes) {
    for (var i = 0; i < nodes.length; i++) queue.push(nodes[i]);
    if (!pending) { pending = true; setTimeout(flush, 0); }
  }

  function start() {
    try { walk(document.body || document.documentElement); } catch (e) {}
    try {
      var html = document.documentElement;
      if (html && html.getAttribute("lang") === "en") html.setAttribute("lang", "zh-CN");
    } catch (e) {}
    try {
      var mo = new MutationObserver(function (records) {
        var add = [];
        for (var i = 0; i < records.length; i++) {
          var r = records[i];
          if (r.type === "childList") {
            for (var j = 0; j < r.addedNodes.length; j++) add.push(r.addedNodes[j]);
          } else if (r.type === "characterData") {
            add.push(r.target);
          } else if (r.type === "attributes") {
            add.push(r.target);
          }
        }
        if (add.length) schedule(add);
      });
      mo.observe(document.documentElement, { childList: true, subtree: true,
                                             characterData: true, attributes: true,
                                             attributeFilter: ATTRS.concat(["value"]) });
    } catch (e) {}
  }

  /* the app's own dialogs */
  try {
    var _alert = window.alert, _confirm = window.confirm, _prompt = window.prompt;
    window.alert = function (m) { return _alert.call(window, tr(String(m)) || m); };
    window.confirm = function (m) { return _confirm.call(window, tr(String(m)) || m); };
    window.prompt = function (m, d) { return _prompt.call(window, tr(String(m)) || m, d); };
  } catch (e) {}

  window.fizgigZhTranslate = tr;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();