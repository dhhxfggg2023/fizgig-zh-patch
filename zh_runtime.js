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

  /* A multi-line hint is often drawn as one block, or split into its lines:
     try each line, then the whole thing with its newlines collapsed. */
  function lookupLines(plain) {
    if (plain.indexOf("\n") < 0) return null;
    var parts = plain.split("\n");
    var out = [];
    for (var i = 0; i < parts.length; i++) {
      var t = parts[i];
      if (!t.trim()) { out.push(t); continue; }
      var z = lookupSmart(t);
      if (z === null) return null;        /* 有一段没翻，就整段不翻，免得半中半英 */
      out.push(z);
    }
    return out.join("\n");
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
    var lines = lookupLines(plain);
    if (lines !== null) return lines;
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

  /* A paragraph with a link or <b> in the middle of it arrives as several
     text nodes ("...through its" + <a>File manager</a> + "; on your own
     server..."), so no single node ever matches the dictionary. Walk the whole
     element's text, translate the joined sentence, then write the pieces back
     in the same order. Only used when the parts do NOT translate one by one:
     that keeps normal markup (bold words, links) exactly as it was. */
  var BLOCKISH = { P: 1, DIV: 1, LI: 1, TD: 1, TH: 1, DD: 1, DT: 1, BLOCKQUOTE: 1,
                   H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1, FIGCAPTION: 1, LABEL: 1 };
  var INLINE_OK = { A: 1, B: 1, I: 1, EM: 1, STRONG: 1, CODE: 1, SPAN: 1, SMALL: 1,
                    U: 1, S: 1, BR: 1, FONT: 1, MARK: 1, SUB: 1, SUP: 1 };

  function partsOf(el, out) {
    for (var c = el.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === 3) {
        if (c.data) out.push({ node: c, text: c.data });
      } else if (c.nodeType === 1) {
        if (c.tagName === "BR") { out.push({ node: null, text: "\n" }); continue; }
        if (INLINE_OK[c.tagName] && !c.hasAttribute("data-zh-skip")) {
          var kids = [];
          partsOf(c, kids);
          for (var i = 0; i < kids.length; i++) out.push(kids[i]);
          continue;
        }
        return null;                       /* something we must not merge across */
      }
    }
    return out;
  }

  function paragraph(el) {
    if (!BLOCKISH[el.tagName] || el.hasAttribute("data-zh-skip")) return;
    var parts = partsOf(el, []);
    if (!parts || parts.length < 2) return;       /* single node: handled already */
    var hasLink = false;
    for (var c = el.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === 1 && c.tagName === "A") hasLink = true;
    }
    var joined = "", texts = [];
    for (var i = 0; i < parts.length; i++) {
      texts.push(parts[i].text);
      joined += parts[i].text;
    }
    var zh = lookupSmart(joined.replace(/\s+/g, " ").trim());
    if (zh === null) return;
    var pieces = zh.split(/\s+/);
    /* the translated sentence has to be laid back over the original pieces:
       give each original part a share of the words by its own word count. */
    var counts = texts.map(function (t) { return (t.match(/\S+/g) || []).length; });
    var total = counts.reduce(function (a, b) { return a + b; }, 0);
    if (!total) return;
    if (hasLink) {
      /* a link in the middle: keep its text, translate the text around it only */
      var out2 = [];
      for (var k = 0; k < parts.length; k++) {
        out2.push(translatePiece(texts[k]));
      }
      for (var k2 = 0; k2 < parts.length; k2++) {
        var nd = parts[k2].node;
        if (!nd) continue;
        if (!out2[k2] || out2[k2] === texts[k2]) continue;
        nd.__zh = out2[k2];
        nd.data = out2[k2];
      }
      return;
    }
    var at = 0;
    for (var m = 0; m < parts.length; m++) {
      var take = Math.round(pieces.length * (counts[m] / total));
      if (m === parts.length - 1) take = pieces.length - at;
      if (take < 0) take = 0;
      var seg = pieces.slice(at, at + take).join(" ");
      at += take;
      var lead = /^\s/.test(texts[m]) ? " " : "";
      var nd2 = parts[m].node;
      if (!nd2) continue;
      if (!seg) continue;
      var z = lead + seg;
      nd2.__zh = z;
      nd2.data = z;
    }
  }

  /* one piece on its own (used around a link) */
  function translatePiece(t) {
    var lead = t.match(/^\s*/)[0], trail = t.match(/\s*$/)[0];
    var body = t.slice(lead.length, t.length - trail.length);
    if (!body) return t;
    var z = lookupSmart(body);
    return z === null ? t : lead + z + trail;
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
    if (root.nodeType === 1) paragraph(root);
    var blocks = root.querySelectorAll ? root.querySelectorAll("p,div,li,h1,h2,h3,h4,td,th,label,figcaption,blockquote") : [];
    for (var b = 0; b < blocks.length; b++) {
      try { paragraph(blocks[b]); } catch (e) {}
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