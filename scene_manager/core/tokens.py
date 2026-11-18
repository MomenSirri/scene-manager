"""Output path tokens, e.g.  D:/renders/{scene}/{setup}_{camera}_{date}.exr"""
import datetime
import getpass
import glob
import os
import re

from pymxs import runtime as rt

TOKENS = {
    "scene": "Max file name without extension",
    "setup": "Setup name",
    "folder": "Name of the folder the setup is in",
    "camera": "Camera name of the setup",
    "renderer": "vray / corona / arnold / other",
    "width": "Render width",
    "height": "Render height",
    "date": "YYYYMMDD",
    "time": "HHMM",
    "user": "Windows user name",
    "project": "3ds Max project folder",
    "version": "Version number, next free one on disk unless the Output builder fixes it (e.g. _v{version})",
    "element": "Render element name (element file names only)",
}
# Custom tokens come from the Output builder module.


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def renderer_name():
    cls = str(rt.classOf(rt.renderers.current)).lower()
    for key in ("v_ray", "vray", "corona", "arnold"):
        if key in cls:
            return {"v_ray": "vray"}.get(key, key)
    return cls


def _clean(s):
    return "".join(c if c not in '<>:"/\\|?*' else "_" for c in str(s)).strip()


def base_context():
    now = datetime.datetime.now()
    scene = os.path.splitext(str(rt.maxFileName))[0] or "untitled"
    return {
        "scene": scene,
        "renderer": renderer_name(),
        "width": int(rt.renderWidth),
        "height": int(rt.renderHeight),
        "date": now.strftime("%Y%m%d"),
        "time": now.strftime("%H%M"),
        "user": getpass.getuser(),
        "project": str(rt.pathConfig.getCurrentProjectFolder()),
    }


def resolve(template, context):
    if not template:
        return ""
    context = dict(context)
    if "{version}" in template:
        context["version"] = version_text(template, context)
    ctx = _Safe({k: (_clean(v) if k != "project" else v) for k, v in context.items()})
    return os.path.normpath(template.format_map(ctx))


_MARK = "SMVERSIONMARK"


def version_text(template, context):
    """Fixed version from context["version"] (int > 0), else the next free number on disk."""
    pad = int(context.get("version_pad") or 3)
    v = context.get("version")
    if isinstance(v, int) and not isinstance(v, bool) and v > 0:
        return str(v).zfill(pad)
    probe = resolve(template.replace("{version}", _MARK), dict(context, version=None))
    head, _, tail = probe.partition(_MARK)
    tail_root, ext = os.path.splitext("x" + tail.replace(_MARK, "*"))
    tail_root = tail_root[1:]
    # Max appends frame numbers before the extension, so allow digits there.
    rx = re.compile(re.escape(head) + r"(\d{%d,}?)" % pad + re.escape(tail_root).replace(r"\*", ".*") + r"\d*" + re.escape(ext) + "$",
                    re.IGNORECASE)
    found = 0
    for p in glob.glob(glob.escape(head) + "*"):
        p = os.path.normpath(p)
        m = rx.match(p) or rx.match(p + ext)   # a folder named by version also counts
        if m is None and os.path.isdir(p):
            m = re.match(re.escape(head) + r"(\d+)", p)
        if m:
            found = max(found, int(m.group(1)))
    return str(found + 1).zfill(pad)
