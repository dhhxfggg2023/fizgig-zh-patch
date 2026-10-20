"""Where is Fizgig, and where is this patch?

The patch folder may sit anywhere. It finds Fizgig in this order:

  1. the FIZGIG_ROOT environment variable
  2. a "fizgig_root.txt" file next to this script
  3. the parent of this folder (the usual case: <Fizgig>/zh_patch/)
  4. the usual install locations on this machine

A Fizgig root is a directory that has BOTH fizgig.py and src/fizgig/web/static/.
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))

MARKERS = ("fizgig.py", os.path.join("src", "fizgig", "web", "static"))


def is_fizgig_root(path):
    if not path or not os.path.isdir(path):
        return False
    return all(os.path.exists(os.path.join(path, m)) for m in MARKERS)


def candidates():
    out = []
    env = os.environ.get("FIZGIG_ROOT")
    if env:
        out.append(env)
    cfg = os.path.join(HERE, "fizgig_root.txt")
    if os.path.isfile(cfg):
        try:
            out.append(io.open(cfg, encoding="utf-8").read().strip())
        except Exception:
            pass
    out.append(os.path.dirname(HERE))
    drive = os.path.splitdrive(HERE)[0] or "C:"
    for d in ("Fizgig", "tools\\Fizgig", "Fizgig-main", "tools\\Fizgig-main"):
        out.append(os.path.join(drive + "\\", d))
    return out


def find_root():
    for c in candidates():
        if is_fizgig_root(c):
            return os.path.abspath(c)
    return None


def static_dir(root=None):
    root = root or find_root()
    if not root:
        return None
    return os.path.join(root, "src", "fizgig", "web", "static")


def remember_root(root):
    try:
        io.open(os.path.join(HERE, "fizgig_root.txt"), "w",
                encoding="utf-8").write(root)
    except Exception:
        pass
