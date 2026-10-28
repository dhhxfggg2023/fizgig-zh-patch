# -*- coding: utf-8 -*-
"""dictionary.json + templates.json + skip.json  ->  zh_pack.js (window.FIZGIG_ZH).

install.py 会在缺文件或词表更新后自动调用它，一般不用手动运行。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, default):
    p = os.path.join(HERE, name)
    if not os.path.isfile(p):
        return default
    return json.load(io.open(p, encoding="utf-8"))


def build(quiet=False):
    dict_ = {k: v for k, v in load("dictionary.json", {}).items()
             if isinstance(v, str) and v.strip()}
    tpl = [t for t in load("templates.json", [])
           if isinstance(t, list) and len(t) == 2
           and all(isinstance(x, str) for x in t)]
    skip = [s for s in load("skip.json", []) if isinstance(s, str)]

    # 词表里带 {占位符} 的条目（表单里写成 {n} 的那种）在界面上会被替换成实际
    # 数字，整串就对不上了：把它们自动升级成模板规则，用 \u0000 表示那个洞。
    HOLE = "\u0000"
    PH = re.compile(r"\{[^{}]{1,40}\}")
    seen = set()
    for en, zh in list(dict_.items()):
        if not PH.search(en):
            continue
        en_pat = PH.sub(HOLE, en)
        if en_pat in seen:
            continue
        holes = en_pat.count(HOLE)
        if PH.search(zh):
            zh_pat = PH.sub(HOLE, zh)
            if zh_pat.count(HOLE) != holes:
                continue            # 占位符数量对不上，宁可不翻
        elif holes == 1:
            zh_pat = zh + HOLE      # 中文没写占位符：补在末尾
        else:
            continue
        seen.add(en_pat)
        tpl.append([en_pat, zh_pat])

    # a key we also skip would never be used: keep the pack honest
    dict_ = {k: v for k, v in dict_.items() if k not in skip}

    # 界面上多段提示常常是分开画的（"Off: ..." 是标签，后面段落是另一个文本
    # 节点），而词表里存的是整段。把多行词条按段拆成独立条目补进去。
    for en, zh in list(dict_.items()):
        if "\n" not in en:
            continue
        # 先试空行分段，再试单换行分段；两种都只在段数一致时才拆
        for sep in ("\n\n", "\n"):
            en_parts = [p.strip() for p in en.split(sep) if p.strip()]
            zh_parts = [p.strip() for p in zh.split(sep) if p.strip()]
            if len(en_parts) != len(zh_parts) or len(en_parts) < 2:
                continue
            for e, z in zip(en_parts, zh_parts):
                if e not in dict_ and not PH.search(e):
                    dict_[e] = z

    pack = json.dumps({"exact": dict_, "templates": tpl, "skip": skip},
                      ensure_ascii=False, separators=(",", ":"))
    out = "window.FIZGIG_ZH = " + pack + ";\n"
    with io.open(os.path.join(HERE, "zh_pack.js"), "w", encoding="utf-8", newline="") as f:
        f.write(out)
    if not quiet:
        print("zh_pack.js: %d entries, %d templates, %d skipped, %d bytes"
              % (len(dict_), len(tpl), len(skip), len(out)))
    return len(dict_), len(tpl), len(skip)


if __name__ == "__main__":
    sys.exit(0 if build() else 1)