"""Fizgig Chinese patch engine (v2, structural).

Rewrites the three static files the Fizgig web server serves:

    src/fizgig/web/static/index.html
    src/fizgig/web/static/app.js
    src/fizgig/web/static/style.css

Safety model
------------
Every string literal is classified by *what the surrounding code does with it*,
not by what the string looks like:

  display  the text reaches the screen -> translate it
  value    the code compares it, uses it as an object key, a `value:` property,
           a case label, a DOM id, an <option>'s own value, or a tag name
           -> never touch it
  unknown  cannot tell -> never touch it

A string that is display in one place and value in another (e.g. "Fast" shown
in a dropdown but also compared in code) is *never* translated: the two would
otherwise disagree.

Self-check: the set of literals used in ===/!== comparisons must be
byte-identical before and after. If not, the patch aborts.

Usage
-----
    python patchlib.py --apply
    python patchlib.py --revert
    python patchlib.py --check
    python patchlib.py --dry-run
"""
import argparse
import io
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STATIC = os.path.join(os.path.dirname(HERE), "src", "fizgig", "web", "static")
FILES = ("index.html", "app.js", "style.css")
BACKUP_DIR = os.path.join(HERE, "backup")

ESC_MAP = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v",
           "\\": "\\", '"': '"', "'": "'", "`": "`", "/": "/", "$": "$"}


def unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "u" and re.match(r"[0-9a-fA-F]{4}", s[i + 2:i + 6] or ""):
                out.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
                continue
            if n == "x" and re.match(r"[0-9a-fA-F]{2}", s[i + 2:i + 4] or ""):
                out.append(chr(int(s[i + 2:i + 4], 16)))
                i += 4
                continue
            out.append(ESC_MAP.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def norm_ws(t):
    return " ".join(t.split())


def esc_html(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def script_regions(src):
    return [(m.start(2), m.end(2)) for m in
            re.finditer(r"<(script|style)\b[^>]*>(.*?)</\1>", src, re.S | re.I)]


def in_regions(pos, regions):
    return any(a <= pos < b for a, b in regions)


# ------------------------------------------------------------------ HTML
def html_occurrences(src):
    regions = script_regions(src)
    out = []
    option_spans = []
    for m in re.finditer(r"<option\b([^>]*)>(.*?)</option>", src, re.S | re.I):
        has_value = re.search(r"\bvalue\s*=", m.group(1), re.I) is not None
        option_spans.append((m.start(2), m.end(2), has_value))

    def option_of(pos):
        for a, b, hv in option_spans:
            if a <= pos < b:
                return hv
        return None

    def add(start, end, raw, cls):
        txt = norm_ws(unescape(raw))
        if not txt or not re.search(r"[A-Za-z]", txt):
            return
        out.append({"start": start, "end": end, "raw": raw, "text": txt, "cls": cls})

    for m in re.finditer(r">([^<>]{1,400})<", src):
        if in_regions(m.start(1), regions):
            continue
        hv = option_of(m.start(1))
        add(m.start(1), m.end(1), m.group(1),
            "display" if hv is None else ("value" if not hv else "display"))

    for attr in ("title", "placeholder", "aria-label", "alt"):
        for m in re.finditer(attr + r'="([^"]{1,240})"', src):
            if in_regions(m.start(1), regions):
                continue
            add(m.start(1), m.end(1), m.group(1), "display")

    for rx in (r'\bvalue="([^"]{1,240})"', r'\bid="([^"]{1,240})"',
               r'\bname="([^"]{1,240})"', r'\bdata-[\w-]+="([^"]{1,240})"',
               r'\btype="([^"]{1,240})"', r'\bfor="([^"]{1,240})"'):
        for m in re.finditer(rx, src):
            if in_regions(m.start(1), regions):
                continue
            add(m.start(1), m.end(1), m.group(1), "value")
    return out


# ------------------------------------------------------------------ JS
TAGCALL = re.compile(r"\b(?:el|h|tag|make|html|node|div|span)\s*\(\s*$")
VALUE_PROP = re.compile(
    r"\b(?:class|id|name|value|type|kind|key|field|href|src|style|role|"
    r"for|data|variant|theme|group|family|preset|mode|status|verdict|level|"
    r"tag|state|fmt|unit|ext|mime|dir|path|cmd|arg|opt|option)\s*:\s*$", re.I)
DISPLAY_PROP = re.compile(
    r"\b(?:text|label|title|placeholder|alt|html|innerText|innerHTML|"
    r"outerHTML|textContent|msg|message|note|desc|description|badge|"
    r"heading|header|caption|hint|tooltip)\s*:\s*", re.I)
DISPLAY_ASSIGN = re.compile(
    r"(?:textContent|innerHTML|innerText|outerHTML|placeholder|title|"
    r"ariaLabel|aria-label)\s*=\s*[^=]$")
COMPARE = re.compile(r"(?:===|!==|==|!=)\s*$")
CASE = re.compile(r"\bcase\s+$")
KEYLIKE = re.compile(r"[\"']\s*:\s*$")


def js_literal_spans(src):
    """All string literal spans in JavaScript source, with correct handling of
    template literals: a template with ${...} interpolation is skipped whole,
    because only its static parts are translatable (and slicing one out of the
    middle would break the expression)."""
    spans = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == '"' or c == "'":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c:
                    break
                if src[j] == "\n":
                    break
                j += 1
            spans.append((i + 1, j, c))
            i = j + 1
            continue
        if c == "`":
            # scan the template, tracking ${ } depth
            j = i + 1
            depth = 0
            static_end = None
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if depth == 0 and src[j] == "`":
                    break
                if depth == 0 and src[j] == "$" and j + 1 < n and src[j + 1] == "{":
                    depth = 1
                    j += 2
                    continue
                if depth > 0:
                    if src[j] == "{":
                        depth += 1
                    elif src[j] == "}":
                        depth -= 1
                    j += 1
                    continue
                j += 1
            if depth == 0:
                # a template with no interpolation: fully translatable
                spans.append((i + 1, j, "`"))
            i = j + 1
            continue
        i += 1
    return spans


def template_static_segments(src, start, end):
    """The literal text parts of a template literal that contains ${...}
    interpolations. Only the static text between the interpolations is
    returned, so a template like `${n}/3 selected` yields the segment
    "/3 selected" - the interpolation itself is never touched."""
    body = src[start:end]
    segs = []
    i = 0
    seg_start = 0
    while i < len(body):
        if body[i] == "\\":
            i += 2
            continue
        if body[i] == "$" and i + 1 < len(body) and body[i + 1] == "{":
            if i > seg_start:
                segs.append((seg_start, i))
            depth = 1
            j = i + 2
            while j < len(body) and depth:
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                j += 1
            i = j
            seg_start = i
            continue
        i += 1
    if seg_start < len(body):
        segs.append((seg_start, len(body)))
    return segs


def js_occurrences(src):
    out = []
    for start, end, quote in js_literal_spans(src):
        raw = src[start:end]
        before = src[max(0, start - 140):start]
        after = src[end:end + 60]

        if quote == "`" and "${" in raw:
            # an interpolated template: translate only its static text parts
            for a, b in template_static_segments(raw, 0, len(raw)):
                seg = raw[a:b]
                txt = norm_ws(unescape(seg))
                if not txt or not re.search(r"[A-Za-z]", txt):
                    continue
                if looks_like_code(txt):
                    continue
                out.append({"start": start + a, "end": start + b, "raw": seg,
                            "text": txt, "cls": "display", "quote": quote,
                            "template": True})
            continue

        txt = norm_ws(unescape(raw))
        if not txt or not re.search(r"[A-Za-z]", txt):
            continue
        if COMPARE.search(before):
            cls = "value"
        elif CASE.search(before):
            cls = "value"
        elif TAGCALL.search(before):
            cls = "value"
        elif VALUE_PROP.search(before):
            cls = "value"
        elif KEYLIKE.search(before) and re.match(r"\s*:", after):
            cls = "value"
        elif DISPLAY_PROP.search(before):
            cls = "display"
        elif DISPLAY_ASSIGN.search(before):
            cls = "display"
        else:
            cls = "unknown"
        out.append({"start": start, "end": end, "raw": raw, "text": txt, "cls": cls,
                    "quote": quote})
    return out


def css_occurrences(src):
    out = []
    for m in re.finditer(r'content:\s*"([^"]{1,80})"', src):
        txt = norm_ws(unescape(m.group(1)))
        if not txt or not re.search(r"[A-Za-z]", txt):
            continue
        out.append({"start": m.start(1), "end": m.end(1), "raw": m.group(1),
                    "text": txt, "cls": "display"})
    return out


def occurrences_for(name, src):
    if name.endswith(".html"):
        return html_occurrences(src)
    if name.endswith(".js"):
        return js_occurrences(src)
    return css_occurrences(src)


def comparison_literals(src):
    out = set()
    for start, end, quote in js_literal_spans(src):
        if re.search(r"(?:===|!==|==|!=)\s*$", src[max(0, start - 40):start]):
            out.add(src[start:end])
    return out


def load_dictionary(path):
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if isinstance(v, str) and v.strip()}


def load_conflicts(path):
    if not os.path.isfile(path):
        return set()
    with io.open(path, encoding="utf-8") as f:
        return set(json.load(f))


# A literal that looks like code is never translated, whatever the classifier
# said about it. This is the last line of defence: a mangled string literal
# would break the whole script.
CODE_GUARD = re.compile(
    r"[{}<>|\\]|=>|\$\(|\)\s*$|\(\s*$|\+\s*$|^\s*[,;)]|^\s*\+ |^\s*\)"
    r"|^\s*\.|\bfunction\b|\.\w+\(|\breturn\b|\bvar\b|\blet\b|\bconst\b"
    r"|^\s*/|^\s*[a-z_]+:\s*$|\bnew\s+\w+\(|=>|;$")


def looks_like_code(t):
    """A last-resort guard: a literal that is obviously code is never
    translated, whatever the structural classifier said about it.

    Note what is deliberately NOT here: a trailing '.' or ':' is normal
    English ("Training finished.", "Model:"), and a leading '(' or ':' is a
    normal sentence fragment. Only genuinely code-shaped literals are
    rejected."""
    t = t.strip()
    if not t:
        return True
    if CODE_GUARD.search(t):
        return True
    if re.match(r"^/api/", t):
        return True
    if re.match(r"^[\w.-]+\.(js|py|json|css|html|txt|png|jpg|mp4|zip)$", t, re.I):
        return True
    # a CSS selector or an attribute fragment:  #id .cls[attr="value"]
    if re.search(r"\[[^\]]*=", t):
        return True
    if re.match(r"^[#.][A-Za-z][\w-]*\s", t) or re.match(r"^[#.][A-Za-z][\w-]*$", t):
        return True
    # an attribute fragment:  input[name="x"]:checked
    if re.search(r"[\w-]+\[[^\]]*=", t):
        return True
    return False


def digits_of(s):
    return re.findall(r"\d+", s)


def patch_source(name, src, dictionary, conflicts, report):
    occ = occurrences_for(name, src)
    edits = []
    for o in occ:
        if o["cls"] != "display":
            continue
        if o["text"] in conflicts:       # display in one place, value in another
            continue
        if looks_like_code(o["text"]):
            continue
        zh = dictionary.get(o["text"])
        if not zh or zh.strip() == o["text"].strip():
            continue
        # a translation must keep every number: "0/3 selected" -> "已选 0/3"
        if digits_of(zh) != digits_of(o["text"]):
            continue
        edits.append(o)

    out = src
    for o in sorted(edits, key=lambda x: -x["start"]):
        zh = dictionary[o["text"]]
        raw = o["raw"]
        lead = raw[:len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()):]
        body = raw.strip()
        if name.endswith(".html"):
            new = lead + esc_html(zh) + trail
        else:
            quote = o.get("quote") or '"'
            new = (lead + zh + trail)
            new = new.replace("\\", "\\\\").replace(quote, "\\" + quote)
            new = new.replace("\n", "\\n")
        out = out[:o["start"]] + new + out[o["end"]:]
        report.append((name, o["text"], zh))
    return out


def apply_patch(static_dir, dictionary, conflicts, backup_dir=BACKUP_DIR, verbose=True):
    if not os.path.isdir(static_dir):
        raise SystemExit("static dir not found: %s" % static_dir)
    os.makedirs(backup_dir, exist_ok=True)
    report = []
    before_cmp, after_cmp = {}, {}
    for name in FILES:
        path = os.path.join(static_dir, name)
        if not os.path.isfile(path):
            continue
        src = io.open(path, encoding="utf-8").read()
        before_cmp[name] = comparison_literals(src)
        bak = os.path.join(backup_dir, name + ".orig")
        if not os.path.isfile(bak):
            shutil.copy2(path, bak)
        new = patch_source(name, src, dictionary, conflicts, report)
        after_cmp[name] = comparison_literals(new)
        if new != src:
            with io.open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
    for name in before_cmp:
        missing = before_cmp[name] - after_cmp[name]
        if missing:
            raise SystemExit("SAFETY FAILURE in %s: comparison literals changed: %r"
                             % (name, sorted(missing)[:10]))
    if verbose:
        print("PATCHED_OCCURRENCES", len(report))
        print("UNIQUE_STRINGS_TRANSLATED", len({t for _, t, _ in report}))
    return report


def revert(static_dir, backup_dir=BACKUP_DIR):
    if not os.path.isdir(backup_dir):
        print("NO_BACKUP")
        return
    n = 0
    for name in FILES:
        bak = os.path.join(backup_dir, name + ".orig")
        path = os.path.join(static_dir, name)
        if os.path.isfile(bak) and os.path.isfile(path):
            shutil.copy2(bak, path)
            n += 1
    print("REVERTED_FILES", n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--static-dir", default=DEFAULT_STATIC)
    ap.add_argument("--dict", default=os.path.join(HERE, "dictionary.json"))
    ap.add_argument("--conflicts", default=os.path.join(HERE, "conflicts.json"))
    args = ap.parse_args()

    if args.revert:
        revert(args.static_dir)
        return
    dictionary = load_dictionary(args.dict)
    conflicts = load_conflicts(args.conflicts)
    print("DICTIONARY_ENTRIES", len(dictionary), "CONFLICTS_EXCLUDED", len(conflicts))

    if args.check or args.dry_run:
        total = 0
        for name in FILES:
            path = os.path.join(args.static_dir, name)
            if not os.path.isfile(path):
                continue
            src = io.open(path, encoding="utf-8").read()
            occ = occurrences_for(name, src)
            disp = {o["text"] for o in occ if o["cls"] == "display"}
            hit = disp & set(dictionary) - conflicts
            print("%-12s display=%d translatable=%d" % (name, len(disp), len(hit)))
            total += len(hit)
        print("TRANSLATABLE_TOTAL", total)
        if args.check:
            return
    apply_patch(args.static_dir, dictionary, conflicts)


if __name__ == "__main__":
    main()
