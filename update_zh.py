# -*- coding: utf-8 -*-
"""先还原英文 -> 跑 Fizgig 官方更新 -> 再汉化回来。

为什么需要它：汉化会改动 src/fizgig/web/static/ 下的三个文件。上游更新时
git pull 一旦也要改这三个文件，就会因为「本地有改动」直接中止 —— 这也是以前
「明明更新过却还提示可以更新」的原因。所以更新的第一步必须先把它们还原。

    python update_zh.py            # 更新 + 重新汉化
    python update_zh.py --no-patch # 只更新，不重新汉化

背后调用的是 Fizgig 自带的 update_fizgig.py（它自己会挑 CUDA / ROCm、装依赖）。
"""
import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config

ROOT = config.find_root()
if not ROOT:
    raise SystemExit("找不到 Fizgig。参考 README 里「放在哪？」一节的三种办法。")

PY = os.path.join(ROOT, "venv", "Scripts", "python.exe")
if not os.path.isfile(PY):
    PY = sys.executable

import install

TORCH_PROBE = (
    "import sys\n"
    "try:\n"
    "    import torch\n"
    "except Exception:\n"
    "    sys.exit(12)\n"
    "v = getattr(torch, '__version__', '') or ''\n"
    "rocm = getattr(getattr(torch, 'version', None), 'rocm', None)\n"
    "hip = getattr(getattr(torch, 'version', None), 'hip', None)\n"
    "sys.exit(10 if (rocm or hip or '+rocm' in v.lower()) else 11)\n"
)


def git(*args):
    try:
        r = subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True,
                           text=True, timeout=60)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, "(git unavailable: %s)" % e


def torch_kind():
    """10 = ROCm, 11 = CUDA/CPU, 12 = 没有可用的 torch。"""
    fd, p = tempfile.mkstemp(suffix=".py", prefix="fizgig_torch_probe_")
    os.close(fd)
    try:
        io.open(p, "w", encoding="utf-8").write(TORCH_PROBE)
        r = subprocess.run([PY, p], capture_output=True, text=True, timeout=300)
        return r.returncode if r.returncode in (10, 11) else 12
    except Exception:
        return 12
    finally:
        try:
            os.remove(p)
        except OSError:
            pass


def hf_env():
    """this machine points HuggingFace at a mirror in user_data/hf_endpoint.bat."""
    env = dict(os.environ)
    p = os.path.join(ROOT, "user_data", "hf_endpoint.bat")
    if os.path.isfile(p):
        try:
            m = re.search(r'set\s+"?([A-Z_]+)=([^"\r\n]+)"?', io.open(p, encoding="utf-8", errors="replace").read())
            if m:
                env[m.group(1)] = m.group(2).strip()
        except OSError:
            pass
    return env


def main():
    patch_back = "--no-patch" not in sys.argv[1:]

    print("=" * 60)
    print("  第 1 步 / 3：还原英文（让 git pull 不被汉化的改动挡住）")
    print("=" * 60)
    install.do_uninstall()

    code, out = git("rev-list", "--count", "HEAD..origin/master")
    before_behind = out if code == 0 else "?"

    print()
    print("=" * 60)
    print("  第 2 步 / 3：运行 Fizgig 官方更新")
    print("=" * 60)
    kind = torch_kind()
    args = [PY, os.path.join(ROOT, "update_fizgig.py")]
    if kind == 10:
        args.append("--rocm")
        print("(检测到 ROCm 版 torch，用 --rocm)")
    elif kind == 12:
        print("(警告：这个 venv 里 torch 用不了，按官方脚本的默认逻辑继续)")
    rc = subprocess.call(args, cwd=ROOT, env=hf_env())
    if rc != 0:
        print()
        print("更新脚本以退出码 %d 结束。请看上面的输出。" % rc)
        print("（汉化尚未重新安装；修好之后重新运行本脚本，或单独运行 install.py）")
        return rc

    code, out = git("rev-list", "--count", "HEAD..origin/master")
    behind = out if code == 0 else "?"
    code, head = git("rev-parse", "--short", "HEAD")
    print()
    print("更新后：HEAD=%s，还落后 origin/master %s 个提交" % (head, behind))
    if before_behind != "?" and behind == before_behind and behind != "0":
        print("!! 还是和更新前一样落后 —— 说明这次的 git pull 又被挡住了。")
        print("   把上面的 git 输出发给我，或先手动执行：")
        print("   git -C \"%s\" status" % ROOT)

    if not patch_back:
        print()
        print("--no-patch：不重新汉化。想汉化就运行 install.py install。")
        return 0

    print()
    print("=" * 60)
    print("  第 3 步 / 3：重新汉化新界面")
    print("=" * 60)
    rc = install.do_install()
    if rc == 0:
        return 0
    print()
    print("汉化没装上（新版本的界面文字可能变了）。界面现在是英文的，功能正常。")
    print("把上面的 PROBLEM 发给我，我按新版本更新词表。")
    return rc


if __name__ == "__main__":
    sys.exit(main() or 0)
