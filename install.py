"""Fizgig 汉化补丁 · 安装 / 卸载 / 检查

用法：

    python install.py            # 安装汉化
    python install.py uninstall  # 卸载汉化（完全恢复英文）
    python install.py status     # 查看当前状态
    python install.py check      # 只做体检，不改任何文件

补丁会自己找 Fizgig：先看环境变量 FIZGIG_ROOT，再看本文件夹旁边的
fizgig_root.txt，再看本文件夹的上一级（<Fizgig>/zh_patch/ 这种放法最省事），
最后看常见安装位置。找不到就按提示选一种方式告诉它。

安装做了什么
------------
  1. 把 src/fizgig/web/static/ 下的 index.html / app.js / style.css 原件
     备份到 backup/（带时间戳，卸载时原样写回）
  2. 按 dictionary.json 把「显示用的英文」替换成中文
  3. 改完后自检：app.js 必须仍能被 node 解析；所有 === 比较用到的字符串
     必须一字不差；HTML 标签必须配平。任何一项不过就自动回滚。

卸载做了什么
------------
  把 backup/ 里保存的原件原样写回去，界面立刻变回英文。
  因为改的只是这三个静态文件，卸载不会影响任何配置、模型、LoRA 或训练数据。

关于 git
--------
Fizgig 是 git 仓库，这三个文件是被跟踪的。安装后 `git status` 会显示它们被
修改 —— 这不影响使用。想让 git 忽略，用：

    git update-index --skip-worktree src/fizgig/web/static/index.html ...
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time

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
BACKUP = os.path.join(HERE, "backup")
DICT = os.path.join(HERE, "dictionary.json")
CONFLICTS = os.path.join(HERE, "conflicts.json")
STAMP = os.path.join(HERE, "installed.json")

import patchlib


def find_node():
    """node is only used to syntax-check the patched app.js. Look for it in
    the usual places instead of hard-coding anyone's home directory."""
    cands = []
    which = shutil.which("node")
    if which:
        cands.append(which)
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands.append(os.path.join(base, "nodejs", "node.exe"))
    cands.append(os.path.join(ROOT, "venv", "Scripts", "node.exe"))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


NODE = find_node()


def read(path):
    return io.open(path, encoding="utf-8").read()


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def git(*args):
    try:
        r = subprocess.run(["git", "-C", ROOT] + list(args),
                           capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "(git unavailable: %s)" % e


def backup_dir_for(tag):
    return os.path.join(BACKUP, tag)


def snapshot(tag):
    """Copy the current static files into backup/<tag>/ (once per tag)."""
    d = backup_dir_for(tag)
    os.makedirs(d, exist_ok=True)
    for f in FILES:
        p = os.path.join(d, f)
        if not os.path.isfile(p):
            shutil.copy2(os.path.join(STATIC, f), p)
    return d


def newest_backup():
    if not os.path.isdir(BACKUP):
        return None
    dirs = [os.path.join(BACKUP, d) for d in os.listdir(BACKUP)
            if os.path.isdir(os.path.join(BACKUP, d))]
    if not dirs:
        return None
    return max(dirs, key=os.path.getmtime)


def do_install():
    if not os.path.isdir(STATIC):
        print("ERROR Fizgig not found at", ROOT)
        return 1
    dict_ = patchlib.load_dictionary(DICT)
    conflicts = patchlib.load_conflicts(CONFLICTS)
    print("DICTIONARY", len(dict_), "CONFLICTS", len(conflicts))

    tag = time.strftime("%Y%m%d-%H%M%S")
    d = snapshot(tag)
    print("BACKUP", os.path.relpath(d, ROOT))

    before = {f: read(os.path.join(STATIC, f)) for f in FILES}
    try:
        patchlib.apply_patch(STATIC, dict_, conflicts)
    except SystemExit as e:
        print("ERROR", e)
        for f in FILES:
            write(os.path.join(STATIC, f), before[f])
        print("ROLLED_BACK")
        return 1

    after = {f: read(os.path.join(STATIC, f)) for f in FILES}

    # --- self check on the real files ------------------------------------
    problems = []
    if os.path.isfile(NODE):
        r = subprocess.run([NODE, "--check", os.path.join(STATIC, "app.js")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            problems.append("app.js no longer parses:\n" + (r.stderr or "")[:600])
    for f in ("index.html",):
        a = patchlib.comparison_literals(before[f])
        b = patchlib.comparison_literals(after[f])
        if a != b:
            problems.append("%s: comparison literals changed: %r" % (f, sorted(a - b)[:5]))
    a = patchlib.comparison_literals(before["app.js"])
    b = patchlib.comparison_literals(after["app.js"])
    if a != b:
        problems.append("app.js: comparison literals changed: %r" % (sorted(a - b)[:5],))

    cjk = sum(len([c for c in t if "\u4e00" <= c <= "\u9fff"]) for t in after.values())
    if cjk < 1000:
        problems.append("only %d Chinese characters landed - too few" % cjk)

    if problems:
        for p in problems:
            print("PROBLEM", p)
        for f in FILES:
            write(os.path.join(STATIC, f), before[f])
        print("ROLLED_BACK")
        return 1

    write(STAMP, json.dumps({"tag": tag, "backup": os.path.relpath(d, ROOT),
                             "installed_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                            ensure_ascii=False, indent=1))
    print("OK 中文界面已安装")
    print("CJK_CHARS", cjk)
    print("GIT_STATUS:")
    print(git("status", "--porcelain", "--", "src/fizgig/web/static"))
    print("现在启动 Fizgig（或重启它）即可看到中文界面。")
    return 0


def do_uninstall():
    d = newest_backup()
    if not d:
        print("NO_BACKUP 没有找到备份，无法自动卸载。")
        return 1
    print("RESTORE_FROM", os.path.relpath(d, ROOT))
    for f in FILES:
        p = os.path.join(d, f)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(STATIC, f))
            print("RESTORED", f)
    if os.path.isfile(STAMP):
        os.remove(STAMP)
    print("OK 已恢复英文界面")
    return 0


def do_status():
    if os.path.isfile(STAMP):
        s = json.load(io.open(STAMP, encoding="utf-8"))
        print("INSTALLED", s.get("installed_at"), "backup:", s.get("backup"))
    else:
        print("NOT_INSTALLED (没有安装记录)")
    cjk = 0
    for f in FILES:
        p = os.path.join(STATIC, f)
        if os.path.isfile(p):
            cjk += len([c for c in read(p) if "\u4e00" <= c <= "\u9fff"])
    print("CJK_CHARS", cjk)
    print("GIT_STATUS:")
    print(git("status", "--porcelain", "--", "src/fizgig/web/static"))


def do_check():
    dict_ = patchlib.load_dictionary(DICT)
    conflicts = patchlib.load_conflicts(CONFLICTS)
    print("DICTIONARY", len(dict_), "CONFLICTS", len(conflicts))
    total = 0
    for f in FILES:
        p = os.path.join(STATIC, f)
        if not os.path.isfile(p):
            continue
        occ = patchlib.occurrences_for(f, read(p))
        disp = {o["text"] for o in occ if o["cls"] == "display"}
        hit = (disp & set(dict_)) - conflicts
        print("%-12s display=%-5d translatable=%d" % (f, len(disp), len(hit)))
        total += len(hit)
    print("TOTAL_TRANSLATABLE", total)
    print("备份目录:", BACKUP, "(存在)" if os.path.isdir(BACKUP) else "(还没有)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", default="install",
                    choices=["install", "uninstall", "status", "check"])
    args = ap.parse_args()
    return {"install": do_install, "uninstall": do_uninstall,
            "status": do_status, "check": do_check}[args.action]()


if __name__ == "__main__":
    sys.exit(main() or 0)
