# -*- coding: utf-8 -*-
"""Fizgig 汉化补丁 · 安装 / 卸载 / 状态 / 体检

只改 Fizgig 网页界面的三个静态文件：

    src/fizgig/web/static/index.html
    src/fizgig/web/static/app.js
    src/fizgig/web/static/style.css

外加在 index.html 的 </body> 前插入一段带标记的 <script>（译文表 + 运行时
翻译器），用来翻译后端发来的文字和运行时才拼出来的界面。

**只靠脚本就能汉化，也只靠脚本就能还原**：安装时把「改了哪几个字节、原文是
什么」写进 rollback.json，还原时按字节原样倒回去（带 sha256 校验），不需要
git、不需要网络、不需要手动备份。git 只是最后的兜底手段。

    python install.py            # 安装 / 重新安装（更新译文）
    python install.py uninstall  # 还原英文
    python install.py status     # 看当前状态
    python install.py check      # 只体检，不改任何文件
    python install.py block      # 打印要插入的那段 script（调试用）
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config

MARK_START = "<!-- zh_patch:start -->"
MARK_END = "<!-- zh_patch:end -->"
# the block is inserted as mark + script + end + one newline. Swallow exactly
# that newline (never the file's own whitespace) so removing it is byte-exact.
BLOCK_RE = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + "\\n?", re.S)
FILES = ("index.html", "app.js", "style.css")
PACK_JS = os.path.join(HERE, "zh_pack.js")
RUNTIME_JS = os.path.join(HERE, "zh_runtime.js")
DICT = os.path.join(HERE, "dictionary.json")
TEMPLATES = os.path.join(HERE, "templates.json")
CONFLICTS = os.path.join(HERE, "conflicts.json")
BACKUP = os.environ.get("ZH_PATCH_BACKUP") or os.path.join(HERE, "backup")
STAMP = os.path.join(HERE, "installed.json")
ROLLBACK = os.path.join(HERE, "rollback.json")

ROOT = config.find_root()
STATIC = config.static_dir(ROOT) if ROOT else None

import patchlib


def read(p):
    # newline="" keeps CRLF exactly as it is on disk: the restore must be
    # byte-for-byte identical, and git should not see a line-ending change.
    return io.open(p, encoding="utf-8", newline="").read()


def write(p, t):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def target_path():
    if not STATIC:
        raise SystemExit(
            "找不到 Fizgig。请任选一种方式告诉本补丁 Fizgig 在哪：\n"
            "  1) 把本文件夹放进 Fizgig 根目录（推荐）：<Fizgig>\\zh_patch\\\n"
            "  2) 设环境变量 FIZGIG_ROOT 指向 Fizgig 根目录\n"
            "  3) 在本文件夹里建一个 fizgig_root.txt，内容写 Fizgig 根目录路径")
    return os.path.join(STATIC, "index.html")


def strip_patch(html):
    return BLOCK_RE.sub("", html)


def ensure_pack(quiet=False):
    """编译 zh_pack.js（缺文件、或词表比它新时自动重编）。

    这样仓库里只需要词表源码，别人下载下来直接就能用，不用先手动 build。
    """
    srcs = [DICT, TEMPLATES, os.path.join(HERE, "skip.json"),
            os.path.join(HERE, "build_pack.py")]
    need = not os.path.isfile(PACK_JS)
    if not need:
        try:
            newest = max(os.path.getmtime(p) for p in srcs if os.path.isfile(p))
            need = os.path.getmtime(PACK_JS) < newest
        except OSError:
            need = True
    if not need:
        return
    import build_pack
    n, t, s = build_pack.build(quiet=True)
    if not quiet:
        print("BUILT zh_pack.js（%d 词条 / %d 模板）" % (n, t))


def build_block():
    if not os.path.isfile(PACK_JS):
        raise SystemExit("缺少 zh_pack.js —— 先运行 python build_pack.py")
    js = read(PACK_JS) + "\n" + read(RUNTIME_JS)
    js = js.replace("</", "<\\/")            # never let the HTML parser close the script
    return (MARK_START + "\n<script>\n" + js + "\n</script>\n" + MARK_END + "\n")


def inject(html, block):
    html = strip_patch(html)
    i = html.rfind("</body>")
    if i < 0:
        i = html.rfind("</html>")
    if i < 0:
        return html + "\n" + block
    return html[:i] + block + html[i:]


# ---------------------------------------------------------------- 还原
def _is_pristine(txt):
    if MARK_START in txt:
        return False
    return len([c for c in txt if "\u4e00" <= c <= "\u9fff"]) < 50


def reverse_previous():
    """Undo the recorded install from rollback.json alone. No git, no network."""
    if not os.path.isfile(ROLLBACK):
        return False
    try:
        m = json.load(io.open(ROLLBACK, encoding="utf-8"))
    except Exception:
        return False
    pristined = {}
    for f, info in (m.get("files") or {}).items():
        p = os.path.join(STATIC, f)
        if not os.path.isfile(p):
            return False
        txt = read(p)
        if sha(txt) != info.get("patched_sha256"):
            return False                     # the file changed since we patched it
        if f == "index.html":
            txt = strip_patch(txt)
        try:
            txt = patchlib.reverse_edits(txt, info.get("edits") or [])
        except SystemExit:
            return False
        if sha(txt) != info.get("pristine_sha256"):
            return False
        pristined[f] = txt
    if not pristined:
        return False
    for f, txt in pristined.items():         # only write once everything checks out
        write(os.path.join(STATIC, f), txt)
    try:
        os.remove(ROLLBACK)
    except OSError:
        pass
    return True


def git_status():
    return git("status", "--porcelain", "--", "src/fizgig/web/static")


def git(*args):
    if not ROOT:
        return ""
    try:
        r = subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True,
                           text=True, timeout=60)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "(git unavailable: %s)" % e


def git_restore_pristine():
    if not ROOT or not os.path.isdir(os.path.join(ROOT, ".git")):
        return False
    subprocess.run(["git", "-C", ROOT, "checkout", "--",
                    "src/fizgig/web/static/index.html",
                    "src/fizgig/web/static/app.js",
                    "src/fizgig/web/static/style.css"],
                   capture_output=True, text=True)
    if git_status().strip():
        return False
    try:
        return _is_pristine(read(os.path.join(STATIC, "index.html")))
    except OSError:
        return False


def newest_backup(pristine_only=True):
    if not os.path.isdir(BACKUP):
        return None
    dirs = []
    for d in os.listdir(BACKUP):
        p = os.path.join(BACKUP, d)
        idx = os.path.join(p, "index.html")
        if not (os.path.isdir(p) and os.path.isfile(idx)):
            continue
        if pristine_only:
            try:
                if not _is_pristine(read(idx)):
                    continue
            except OSError:
                continue
        dirs.append(p)
    return max(dirs, key=os.path.getmtime) if dirs else None


def restore_from_backup():
    b = newest_backup()
    if not b:
        return False
    for f in FILES:
        p = os.path.join(b, f)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(STATIC, f))
    try:
        return _is_pristine(read(os.path.join(STATIC, "index.html")))
    except OSError:
        return False


def restore_pristine():
    """Back to the English source. Returns (how, note)."""
    if reverse_previous():
        return "rollback", ""
    if git_restore_pristine():
        return "git", ""
    if restore_from_backup():
        return "backup", ""
    p = os.path.join(STATIC, "index.html")
    try:
        raw = read(p)
        if MARK_START in raw:
            write(p, strip_patch(raw))
            return "strip", ""
    except OSError:
        pass
    return "none", ""


# ---------------------------------------------------------------- 安装
def snapshot(tag, contents):
    d = os.path.join(BACKUP, tag)
    os.makedirs(d, exist_ok=True)
    for f in FILES:
        p = os.path.join(d, f)
        if not os.path.isfile(p) and f in contents:
            write(p, contents[f])
    return d


def find_node():
    cands = [shutil.which("node")]
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            cands.append(os.path.join(base, "nodejs", "node.exe"))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def load_pack():
    d = patchlib.load_dictionary(DICT)
    c = patchlib.load_conflicts(CONFLICTS)
    t = []
    if os.path.isfile(TEMPLATES):
        t = json.load(io.open(TEMPLATES, encoding="utf-8"))
    return d, c, t


def restore_from(contents):
    for f in FILES:
        if f in contents:
            write(os.path.join(STATIC, f), contents[f])


def do_install():
    target_path()
    how, note = restore_pristine()
    if how == "git":
        print("先还原英文（git checkout）")
    elif how == "backup":
        print("先还原英文（用备份 %s）" % note)
    elif how == "strip":
        print("先去掉上一次注入的 script")

    before = {f: read(os.path.join(STATIC, f)) for f in FILES if os.path.isfile(os.path.join(STATIC, f))}
    start_index = strip_patch(before.get("index.html", ""))
    if MARK_START in start_index:
        print("ERROR index.html 里有多段标记，无法安全处理。")
        return 1

    ensure_pack()
    dict_, conflicts, tpl = load_pack()
    print("DICTIONARY %d  TEMPLATES %d  CONFLICTS %d" % (len(dict_), len(tpl), len(conflicts)))

    tag = time.strftime("%Y%m%d-%H%M%S")
    d = snapshot(tag, before)
    print("BACKUP %s" % os.path.relpath(d, ROOT))

    report = []
    try:
        patchlib.apply_patch(STATIC, dict_, conflicts, backup_dir=BACKUP, verbose=False,
                             report=report)
    except SystemExit as e:
        restore_from(before)
        print("ERROR %s" % e)
        print("ROLLED_BACK 界面保持原样。")
        return 1

    # 运行时那一层：</body> 前插入一段带标记的 <script>
    patched_index = read(os.path.join(STATIC, "index.html"))
    block = build_block()
    new_index = inject(patched_index, block)
    write(os.path.join(STATIC, "index.html"), new_index)

    # --- 自检 -----------------------------------------------------------
    problems = []
    if strip_patch(new_index) != strip_patch(patched_index):
        problems.append("去掉标记后与打补丁的 index.html 不一致")
    if new_index.count(MARK_START) != 1 or new_index.count(MARK_END) != 1:
        problems.append("标记出现次数不对")
    if new_index.count("<script") != start_index.count("<script") + 1:
        problems.append("script 标签数量不对")
    for tg in ("div", "button", "span", "select", "option", "script", "body", "html"):
        a = len(re.findall(r"<" + tg + r"\b", start_index))
        b = len(re.findall(r"<" + tg + r"\b", strip_patch(new_index)))
        if a != b:
            problems.append("<%s> 数量变了：%d -> %d" % (tg, a, b))
    node = find_node()
    if node:
        r = subprocess.run([node, "--check", os.path.join(STATIC, "app.js")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            problems.append("app.js 解析失败：\n" + (r.stderr or "")[:500])
    after = {f: read(os.path.join(STATIC, f)) for f in FILES}
    cjk = sum(len([c for c in t if "\u4e00" <= c <= "\u9fff"]) for t in after.values())
    if cjk < 2000:
        problems.append("三个文件里的汉字太少（%d）" % cjk)
    if problems:
        for p in problems:
            print("PROBLEM %s" % p)
        restore_from(before)
        print("ROLLED_BACK 界面保持原样。")
        return 1

    # --- 记录「怎么倒回去」 ----------------------------------------------
    edits = {f: [] for f in FILES}
    for r in report:
        edits[r["file"]].append({"start": r["start"], "end": r["end"],
                                 "raw": r["raw"], "new": r["new"]})
    files = {}
    for f in FILES:
        files[f] = {"patched_sha256": sha(after[f]),
                    "pristine_sha256": sha(start_index if f == "index.html" else before[f]),
                    "edits": edits[f]}
    write(ROLLBACK, json.dumps({"version": 1, "tag": tag,
                                "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "files": files}, ensure_ascii=False))
    write(STAMP, json.dumps({"tag": tag, "backup": os.path.relpath(d, ROOT),
                             "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                             "entries": len(dict_), "templates": len(tpl),
                             "occurrences": len(report)}, ensure_ascii=False, indent=1))

    print("OK 中文界面已安装")
    print("PATCHED_OCCURRENCES %d  汉字 %d" % (len(report), cjk))
    print("还原方式：install.py uninstall（只靠 rollback.json 就能逐字节倒回去）")
    print("现在重启 Fizgig，或在浏览器里按 Ctrl+F5 强刷，即可看到中文界面。")
    return 0


# ---------------------------------------------------------------- 卸载
def do_uninstall():
    target_path()
    if reverse_previous():
        print("OK 已还原英文（按 rollback.json 逐字节倒回，未使用 git）")
    elif git_restore_pristine():
        print("OK 已还原英文（git checkout；rollback.json 对不上，可能手动改过）")
    elif restore_from_backup():
        print("OK 已还原英文（用备份目录里的原件）")
    else:
        p = os.path.join(STATIC, "index.html")
        raw = read(p)
        if MARK_START in raw:
            write(p, strip_patch(raw))
            print("部分还原：只去掉了注入的 script，app.js / style.css 的改动没能倒回。")
        else:
            print("NOT_INSTALLED 没有找到补丁。")
            return 1
    for f in (STAMP, ROLLBACK):
        if os.path.isfile(f):
            os.remove(f)
    return 0


def do_status():
    target_path()
    idx = read(os.path.join(STATIC, "index.html"))
    on = MARK_START in idx
    cjk = sum(len([c for c in read(os.path.join(STATIC, f)) if "\u4e00" <= c <= "\u9fff"])
              for f in FILES if os.path.isfile(os.path.join(STATIC, f)))
    print("PATCHED %s" % ("yes 中文界面已安装" if on else "no 当前是英文界面"))
    print("FIZGIG_ROOT %s" % ROOT)
    print("CJK_CHARS %d" % cjk)
    dict_, conflicts, tpl = load_pack()
    print("DICTIONARY %d  TEMPLATES %d  CONFLICTS %d" % (len(dict_), len(tpl), len(conflicts)))
    if os.path.isfile(STAMP):
        print("INSTALLED", json.load(io.open(STAMP, encoding="utf-8")))
    print("ROLLBACK_RECORD %s" % ("yes 可逐字节还原" if os.path.isfile(ROLLBACK) else "no"))
    return 0


def do_check():
    target_path()
    dict_, conflicts, tpl = load_pack()
    print("DICTIONARY %d  TEMPLATES %d  CONFLICTS %d" % (len(dict_), len(tpl), len(conflicts)))
    total = 0
    for f in FILES:
        p = os.path.join(STATIC, f)
        if not os.path.isfile(p):
            continue
        src = strip_patch(read(p)) if f == "index.html" else read(p)
        occ = patchlib.occurrences_for(f, src)
        value_texts = {o["text"] for o in occ if o["cls"] == "value"}
        disp = {o["text"] for o in occ if o["cls"] == "display"}
        hit = (disp & set(dict_)) - conflicts - value_texts
        print("%-11s display=%-5d translatable=%d" % (f, len(disp), len(hit)))
        total += len(hit)
    print("TOTAL_TRANSLATABLE %d" % total)
    return 0


def do_block():
    sys.stdout.write(build_block())
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", default="install",
                    choices=["install", "uninstall", "status", "check", "block"])
    args = ap.parse_args()
    return {"install": do_install, "uninstall": do_uninstall, "status": do_status,
            "check": do_check, "block": do_block}[args.action]()


if __name__ == "__main__":
    sys.exit(main() or 0)