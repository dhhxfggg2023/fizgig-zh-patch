# -*- coding: utf-8 -*-
"""一键切换汉化：中文 <-> 英文。（「一键汉化.bat」背后调用的就是它）

    python toggle_zh.py            # 智能切换（当前英文就汉化，当前中文就还原）
    python toggle_zh.py on         # 强制汉化
    python toggle_zh.py off        # 强制还原英文
    python toggle_zh.py status     # 只看状态

判定「当前是不是中文」：数三个静态文件里有多少个汉字。装了汉化会有上万个，
没装是 0。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config

ROOT = config.find_root()
if not ROOT:
    raise SystemExit(
        "找不到 Fizgig。请任选一种方式告诉本补丁 Fizgig 在哪：\n"
        "  1) 把本文件夹放进 Fizgig 根目录（推荐）：<Fizgig>\\zh_patch\\\n"
        "  2) 设环境变量 FIZGIG_ROOT 指向 Fizgig 根目录\n"
        "  3) 在本文件夹里建一个 fizgig_root.txt，内容写 Fizgig 根目录路径")

STATIC = config.static_dir(ROOT)
FILES = ("index.html", "app.js", "style.css")

import install


def cjk_count():
    n = 0
    for f in FILES:
        p = os.path.join(STATIC, f)
        if os.path.isfile(p):
            n += sum(1 for c in io.open(p, encoding="utf-8").read() if "\u4e00" <= c <= "\u9fff")
    return n


def main():
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "toggle"
    if action == "status":
        return install.do_status()
    if action == "on":
        return install.do_install()
    if action == "off":
        return install.do_uninstall()
    if cjk_count() > 2000:
        return install.do_uninstall()
    return install.do_install()


if __name__ == "__main__":
    sys.exit(main() or 0)
