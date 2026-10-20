"""一键切换汉化：中文 <-> 英文。

    python toggle_zh.py            # 智能切换（当前是英文就汉化，是中文就还原）
    python toggle_zh.py on         # 强制汉化
    python toggle_zh.py off        # 强制还原英文
    python toggle_zh.py status     # 只看状态

判定「当前是不是中文」：看三个静态文件里有多少个中日韩统一表意文字。
装了汉化的话会有成千上万个；没装是 0。
"""
import io
import json
import os
import shutil
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


def read(p):
    return io.open(p, encoding="utf-8").read()


def write(p, t):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)


def cjk_count():
    n = 0
    for f in FILES:
        p = os.path.join(STATIC, f)
        if os.path.isfile(p):
            n += sum(1 for c in read(p) if "\u4e00" <= c <= "\u9fff")
    return n


def backup_dirs():
    if not os.path.isdir(BACKUP):
        return []
    return [os.path.join(BACKUP, d) for d in os.listdir(BACKUP)
            if os.path.isdir(os.path.join(BACKUP, d))]


def newest_backup():
    ds = backup_dirs()
    return max(ds, key=os.path.getmtime) if ds else None


def snapshot(tag):
    d = os.path.join(BACKUP, tag)
    os.makedirs(d, exist_ok=True)
    for f in FILES:
        p = os.path.join(d, f)
        if not os.path.isfile(p):
            shutil.copy2(os.path.join(STATIC, f), p)
    return d


def do_on():
    print("=" * 56)
    print("  安装中文界面")
    print("=" * 56)
    dict_ = patchlib.load_dictionary(DICT)
    conflicts = patchlib.load_conflicts(CONFLICTS)
    tag = time.strftime("%Y%m%d-%H%M%S")
    d = snapshot(tag)
    print("原件已备份到 zh_patch\\backup\\%s" % tag)

    before = {f: read(os.path.join(STATIC, f)) for f in FILES}
    try:
        patchlib.apply_patch(STATIC, dict_, conflicts)
    except SystemExit as e:
        print("安装失败：%s" % e)
        for f in FILES:
            write(os.path.join(STATIC, f), before[f])
        print("已回滚，界面保持原样。")
        return 1

    after = {f: read(os.path.join(STATIC, f)) for f in FILES}
    problems = []
    if os.path.isfile(NODE):
        import subprocess
        r = subprocess.run([NODE, "--check", os.path.join(STATIC, "app.js")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            problems.append("app.js 解析失败：\n" + (r.stderr or "")[:400])
    for f in ("index.html", "app.js"):
        a = patchlib.comparison_literals(before[f])
        b = patchlib.comparison_literals(after[f])
        if a != b:
            problems.append("%s 的比较用字符串变了：%r" % (f, sorted(a - b)[:5]))
    n = sum(1 for c in "".join(after.values()) if "\u4e00" <= c <= "\u9fff")
    if n < 1000:
        problems.append("只写入了 %d 个汉字，太少，已回滚。" % n)

    if problems:
        for p in problems:
            print("问题：", p)
        for f in FILES:
            write(os.path.join(STATIC, f), before[f])
        print("已回滚，界面保持原样。")
        return 1

    write(STAMP, json.dumps({"tag": tag, "backup": os.path.relpath(d, ROOT),
                             "installed_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                            ensure_ascii=False, indent=1))
    print("")
    print("  OK  中文界面已安装（%d 个汉字）" % n)
    print("")
    print("  现在请重启 Fizgig，或在浏览器里按 Ctrl+F5 强刷页面。")
    print("  想还原：再次双击「一键汉化.bat」。")
    return 0


def do_off():
    print("=" * 56)
    print("  还原英文界面")
    print("=" * 56)
    d = newest_backup()
    if not d:
        print("没有找到备份，无法自动还原。")
        return 1
    print("从 %s 恢复" % os.path.relpath(d, ROOT))
    for f in FILES:
        p = os.path.join(d, f)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(STATIC, f))
            print("  已恢复 %s" % f)
    if os.path.isfile(STAMP):
        os.remove(STAMP)
    print("")
    print("  OK  已恢复英文界面")
    print("")
    print("  你的配置、模型、LoRA、训练数据全程没有被动过。")
    print("  现在请重启 Fizgig，或在浏览器里按 Ctrl+F5 强刷页面。")
    return 0


def do_status():
    n = cjk_count()
    on = n > 1000
    print("当前界面：%s" % ("中文" if on else "英文"))
    print("中文字符数：%d" % n)
    if os.path.isfile(STAMP):
        s = json.load(io.open(STAMP, encoding="utf-8"))
        print("安装时间：%s" % s.get("installed_at"))
        print("备份位置：%s" % s.get("backup"))
    else:
        print("（没有安装记录）")
    return 0


def main():
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "toggle"
    if action == "status":
        return do_status()
    if action == "on":
        return do_on()
    if action == "off":
        return do_off()
    # toggle
    if cjk_count() > 1000:
        return do_off()
    return do_on()


if __name__ == "__main__":
    sys.exit(main() or 0)
