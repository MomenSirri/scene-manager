"""HDRI library: favourite folders, file scan and cached thumbnails.

Favourites are saved in ~/.scene_manager/hdri.json (per user). Point a favourite at a network
share to share a library with the team. Thumbnails are cached in ~/.scene_manager/hdri_thumbs.
A preview image next to the HDRI (same name, .jpg/.png, or name_preview/_thumb) is used first;
otherwise 3ds Max reads the HDRI and writes a small JPG (HDR values are clipped).
"""
import hashlib
import json
import os

from .. import config

EXTS = (".hdr", ".exr", ".hdri")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")   # LDR backplates / environment images
TEAM_FOLDERS = ("HDRI", "HDRIs", "HDRI Library", "Environments")  # looked for inside config presets_folder
SIDECAR_MAX_BYTES = 120 * 1024   # bigger preview images are shrunk into the thumbnail cache first
PREVIEW_SUFFIXES = ("", "_preview", "_thumb", "_thumbnail", "-preview")
LIB_FILE = config.HOME / "hdri.json"
THUMBS = config.HOME / "hdri_thumbs"
THUMB_SIZE = (256, 128)


def load():
    data = {"favourites": [], "recent": []}
    try:
        data.update(json.loads(LIB_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return data


def save(data):
    config.HOME.mkdir(parents=True, exist_ok=True)
    LIB_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def add_favourite(folder):
    data = load()
    folder = os.path.normpath(folder)
    if folder not in data["favourites"]:
        data["favourites"].append(folder)
        save(data)
    return data["favourites"]


def remove_favourite(folder):
    data = load()
    data["favourites"] = [f for f in data["favourites"] if os.path.normpath(f) != os.path.normpath(folder)]
    save(data)
    return data["favourites"]


def add_recent(path):
    data = load()
    data["recent"] = [path] + [p for p in data["recent"] if p != path][:19]
    save(data)


def scan(folder, recursive=True, search=""):
    """HDRI files in a folder (sorted by name). search filters by a substring of the file name."""
    out = []
    s = (search or "").lower()
    if not folder or not os.path.isdir(folder):
        return out
    walker = os.walk(folder) if recursive else [(folder, [], os.listdir(folder))]
    for root, _dirs, files in walker:
        for f in files:
            if f.lower().endswith(EXTS) and (not s or s in f.lower()):
                out.append(os.path.join(root, f))
    return sorted(out, key=lambda p: os.path.basename(p).lower())


def library(search=""):
    """Every HDRI in every favourite folder: [{"path", "name", "folder"}]."""
    out = []
    for fav in load()["favourites"]:
        for p in scan(fav, search=search):
            out.append({"path": p, "name": os.path.splitext(os.path.basename(p))[0], "folder": fav})
    return out


def roots():
    """Library roots the browser shows: the user's favourites and, if the team presets folder has
    an HDRI subfolder, that one too (so the team shares one library without extra setup)."""
    out = [{"path": f, "label": os.path.basename(f.rstrip("\\/")) or f, "kind": "favourite",
            "exists": os.path.isdir(f)} for f in load()["favourites"]]
    team = (config.load().get("presets_folder") or "").strip()
    if team and os.path.isdir(team):
        for name in TEAM_FOLDERS:
            p = os.path.normpath(os.path.join(team, name))
            if os.path.isdir(p) and all(os.path.normcase(r["path"]) != os.path.normcase(p) for r in out):
                out.append({"path": p, "label": "Team: " + name, "kind": "team", "exists": True})
    return out


def _is_preview_of(name, stems):
    """True if an image file is the sidecar preview of an HDRI in the same folder."""
    stem = os.path.splitext(name)[0].lower()
    for suf in PREVIEW_SUFFIXES:
        if stem.endswith(suf) and stem[:len(stem) - len(suf)] in stems:
            return True
    return False


def _has_subdirs(path):
    try:
        with os.scandir(path) as it:
            return any(e.is_dir() and not e.name.startswith(".") for e in it)
    except OSError:
        return False


def list_folder(folder, search="", images=False, limit=2000):
    """One folder for the browser: its subfolders and its assets. With search, assets come from the
    whole subtree (names matching the text). Sidecar preview images are never listed as assets."""
    exts = EXTS + (IMAGE_EXTS if images else ())
    s = (search or "").strip().lower()
    dirs, files = [], []
    if not folder or not os.path.isdir(folder):
        return {"folder": folder, "dirs": dirs, "files": files, "missing": True, "truncated": False}
    walker = os.walk(folder) if s else [(folder, None, None)]
    for root, _d, _f in walker:
        try:
            entries = list(os.scandir(root))
        except OSError:
            continue
        stems = {os.path.splitext(e.name)[0].lower() for e in entries if e.name.lower().endswith(EXTS)}
        for e in entries:
            try:
                if e.is_dir():
                    if not s and not e.name.startswith("."):
                        dirs.append({"name": e.name, "path": e.path, "has_dirs": _has_subdirs(e.path)})
                    continue
                low = e.name.lower()
                if not low.endswith(exts) or (s and s not in low):
                    continue
                if low.endswith(IMAGE_EXTS) and _is_preview_of(e.name, stems):
                    continue
                st = e.stat()
                files.append({"path": e.path, "name": os.path.splitext(e.name)[0],
                              "ext": os.path.splitext(low)[1][1:], "size": st.st_size, "mtime": int(st.st_mtime),
                              "folder": os.path.relpath(root, folder) if root != folder else ""})
            except OSError:
                continue
        if len(files) >= limit:
            break
    dirs.sort(key=lambda d: d["name"].lower())
    files.sort(key=lambda f: (f["folder"].lower(), f["name"].lower()))
    return {"folder": folder, "dirs": dirs, "files": files[:limit], "missing": False, "truncated": len(files) > limit}


def sidecar_preview(path):
    stem = os.path.splitext(path)[0]
    for suf in PREVIEW_SUFFIXES:
        for ext in (".jpg", ".jpeg", ".png"):
            p = stem + suf + ext
            if os.path.isfile(p):
                return p
    return None


def thumb_path(path):
    st = os.stat(path)
    h = hashlib.sha1(("%s|%d|%d" % (os.path.normcase(path), st.st_size, int(st.st_mtime))).encode("utf-8"))
    return str(THUMBS / (h.hexdigest()[:20] + ".jpg"))


def thumbnail(path, make=True):
    """Path of a preview image for an HDRI, or None. make=False only returns what exists already.
    Order: small sidecar preview as is; big sidecar preview shrunk once; else the HDRI itself shrunk once.
    LDR images (jpg/png) are their own source."""
    side = sidecar_preview(path)
    if side is None and path.lower().endswith(IMAGE_EXTS):
        side = path
    try:
        if side and os.path.getsize(side) <= SIDECAR_MAX_BYTES:
            return side
        tp = thumb_path(side or path)
    except OSError:
        return None
    if os.path.isfile(tp):
        return tp
    if not make:
        return None
    try:
        _render_thumb(side or path, tp)
    except Exception as e:
        print("Scene Manager: no thumbnail for %s: %s" % (path, e))
        return None
    return tp if os.path.isfile(tp) else None


def _render_thumb(src, dst):
    """Use 3ds Max's bitmap IO (reads HDR/EXR). API: openBitmap, bitmap, copy, save, close."""
    from pymxs import runtime as rt
    THUMBS.mkdir(parents=True, exist_ok=True)
    bm = rt.openBitmap(src)
    if bm is None:
        raise RuntimeError("3ds Max could not open the file")
    small = rt.bitmap(THUMB_SIZE[0], THUMB_SIZE[1], filename=dst)
    rt.copy(bm, small)
    rt.save(small)
    rt.close(small)
    rt.close(bm)
