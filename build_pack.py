# -*- coding: utf-8 -*-
"""dictionary.json + templates.json + skip.json  ->  zh_pack.js (window.FIZGIG_ZH).

install.py 会在缺文件或词表更新后自动调用它，一般不用手动运行。
"""
import io
import json
import os
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

    # a key we also skip would never be used: keep the pack honest
    dict_ = {k: v for k, v in dict_.items() if k not in skip}

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
