"""Base class for setup modules.

A module declares its properties (Prop). Setups and folders store only the properties they
override; the effective value is merged from the top folder down to the setup.
"""


class Prop:
    """One editable value of a module.

    kind: camera | sunlight | int | float | bool | enum | text | path
          table  {row_key: {column: value}}; merged per row and per column (M2)
          note   multi-line text (M2)
          todo   [{"text": str, "done": bool}] (M2)
    columns: for kind "table", list of Prop describing each column of a row.
    """

    def __init__(self, key, label, kind, options=None, minimum=-1e9, maximum=1e9,
                 decimals=2, suffix="", tip="", step=1.0, columns=None):
        self.key, self.label, self.kind = key, label, kind
        self.columns = columns or []
        self.options = options or []
        self.minimum, self.maximum, self.decimals = minimum, maximum, decimals
        self.suffix, self.tip, self.step = suffix, tip, step

    labels = None     # optional {option: text shown} for kind "enum"
    kinds = ()        # renderer kinds this value belongs to; () = any. Hidden when none of them is installed.

    def option_list(self):
        """`options` as a list; it may be a callable so the list can come from the scene (installed renderers)."""
        opts = self.options
        if callable(opts):
            try:
                opts = opts()
            except Exception:
                opts = []
        return list(opts or [])

    def installed(self):
        from ..render import rprops
        return rprops.is_installed(*self.kinds)


class Module:
    key = ""          # stored in the scene, never change once released
    label = ""
    order = 100       # apply order, lower first
    category = "scene"  # camera | light | env | scene | render | script (card colour and rail group)
    props = []        # list of Prop
    column = None     # header text if the setup tree shows a column for this module
    touches_scene = True  # False for bookkeeping modules (Notes, Todo): never applied, never "differs"

    def capture(self):
        """Read every property from the scene. Returns {prop_key: value}."""
        raise NotImplementedError

    def apply(self, values, context):
        """Push values into the scene. `values` always holds every prop (missing ones filled from capture)."""
        raise NotImplementedError

    def summary(self, values):
        """Short text for the tree column and for Claude."""
        return ""

    def actions(self):
        """Extra card menu actions: list of (label, fn(values) -> values)."""
        return []

    # ---- optional hooks (M2). Defaults keep the M1 behaviour for plain props. ----
    def prop(self, key):
        for p in self.props:
            if p.key == key:
                return p
        return None

    def merge(self, base, over):
        """Values of `over` on top of `base`. Table props merge per row and per column;
        a row set to None in `over` is removed. Used for folder inheritance and on apply."""
        out = dict(base or {})
        for k, v in (over or {}).items():
            p = self.prop(k)
            if p is not None and p.kind == "table" and isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = merge_table(out[k], v)
            else:
                out[k] = v
        return out

    def differs(self, values, scene):
        """Prop keys whose stored value differs from `scene` (a capture()). Tables compare stored cells only."""
        out = set()
        for k, v in values.items():
            p = self.prop(k)
            cur = scene.get(k)
            if p is not None and p.kind == "table" and isinstance(v, dict):
                cur = cur if isinstance(cur, dict) else {}
                for row, cols in v.items():
                    if cols is None:
                        continue
                    have = cur.get(row)
                    if have is None or any(have.get(c) != x for c, x in cols.items()
                                           if c != "ref" and x is not None):
                        out.add(k)
                        break
            elif isinstance(v, dict) and isinstance(cur, dict) and "handle" in v and "name" in v:
                if v.get("name") != cur.get("name"):  # node refs: same node name = same node
                    out.add(k)
            elif cur != v:
                out.add(k)
        return out

    # def reset(self): optional. Called on activation when the setup does not use this module and
    # there is no baseline for it, so the module can undo what an earlier setup changed.

    def available(self):
        """False = left out of the default module list of a new setup (e.g. another renderer's settings).
        Explicit requests (+ Module, capture with keys) still capture it."""
        return True

    def installed(self):
        """False = this module is for a renderer that is not installed here: it is not offered in Add Module.
        A setup that already carries it (a shared preset) still shows its card."""
        return True

    def capture_baseline(self, mgr):
        """Values recorded in the scene baseline. Default: a full capture(). Return None to keep this
        module out of the baseline (then a setup that does not use it leaves that part of the scene alone)."""
        return self.capture()


def merge_table(base, over):
    out = {r: dict(c) if isinstance(c, dict) else c for r, c in (base or {}).items()}
    for row, cols in (over or {}).items():
        if cols is None:
            out.pop(row, None)
        elif isinstance(out.get(row), dict) and isinstance(cols, dict):
            out[row] = dict(out[row], **cols)
        else:
            out[row] = dict(cols) if isinstance(cols, dict) else cols
    return out
