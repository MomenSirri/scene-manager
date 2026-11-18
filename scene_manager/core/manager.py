"""Setup tree (folders + setups), inheritance, capture and apply.

UI, batch render and the Claude bridge all go through this class.

Inheritance: every folder and setup stores, per module, an optional `enabled` flag and only the
property values it overrides. The effective values of a setup are merged from the top folder
down to the setup; the nearest explicit `enabled` wins.
"""
import copy
import json
import time
import traceback
import uuid

from pymxs import runtime as rt

from . import nodes, registry, storage, tokens

_instance = None


def _scene_redraw(on):
    """disableSceneRedraw()/enableSceneRedraw() (MAXScript). Returns True when the call went through."""
    try:
        (rt.enableSceneRedraw if on else rt.disableSceneRedraw)()
        return True
    except Exception:
        return False


def get_manager():
    global _instance
    if _instance is None:
        _instance = SetupManager()
    return _instance


class SetupManager:
    def __init__(self):
        self._listeners = []
        self.data = storage.empty()
        self.last_apply_ms = None
        self._index = None  # {id: item}, dropped on every commit/reload
        self.reload()

    # ---- listeners -------------------------------------------------------
    def add_listener(self, fn):
        if fn not in self._listeners:
            self._listeners.append(fn)

    def remove_listener(self, fn):
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _notify(self):
        for fn in list(self._listeners):
            try:
                fn()
            except Exception:
                traceback.print_exc()

    def commit(self, notify=True):
        self._index = None
        storage.save(self.data)
        if notify:
            self._notify()

    def reload(self):
        self._index = None
        self.data = storage.load()
        self._notify()

    # ---- tree queries ------------------------------------------------------
    @property
    def items(self):
        return self.data["items"]

    @property
    def active_id(self):
        return self.data.get("active")

    def setups(self):
        return [i for i in self.items if i["type"] == "setup"]

    def children(self, parent_id):
        return [i for i in self.items if i.get("parent") == parent_id]

    def descendants(self, item_id):
        out = []
        for c in self.children(item_id):
            out.append(c)
            out.extend(self.descendants(c["id"]))
        return out

    def chain(self, item):
        """Ancestors from the top folder down to the item itself."""
        out, seen = [], set()
        while item is not None and item["id"] not in seen:
            seen.add(item["id"])
            out.insert(0, item)
            item = self.get(item.get("parent")) if item.get("parent") else None
        return out

    def path(self, item):
        return " / ".join(i["name"] for i in self.chain(item))

    def get(self, key):
        """Find by id, by name, or by path 'Folder / Setup' (case-insensitive)."""
        if key is None:
            return None
        if isinstance(key, dict):
            key = key.get("id")
        if not isinstance(key, str):
            return None
        if self._index is None:
            self._index = {i["id"]: i for i in self.items}
        hit = self._index.get(key)
        if hit is not None:
            return hit
        for i in self.items:  # added since the last commit
            if i["id"] == key:
                return i
        k = str(key).strip().lower()
        for i in self.items:
            if self.path(i).lower() == k:
                return i
        for i in self.items:
            if i["name"].lower() == k:
                return i
        return None

    def require(self, key):
        i = self.get(key)
        if i is None:
            raise KeyError("No setup or folder %r" % key)
        return i

    def unique_name(self, base, parent=None, exclude=None):
        names = {i["name"].lower() for i in self.children(parent) if i is not exclude}
        if base.lower() not in names:
            return base
        n = 2
        while ("%s %d" % (base, n)).lower() in names:
            n += 1
        return "%s %d" % (base, n)

    # ---- inheritance -------------------------------------------------------
    def module_state(self, item, key):
        """Effective state of one module: enabled, values, and where each value comes from."""
        enabled, values, source = False, {}, {}
        m = registry.get(key)
        for node in self.chain(item):
            entry = node["modules"].get(key)
            if not entry:
                continue
            if entry.get("enabled") is not None:
                enabled = bool(entry["enabled"])
            own = entry.get("values") or {}
            values = m.merge(values, own) if m is not None else dict(values, **own)  # M2: tables merge per row
            for p in own:
                source[p] = node["id"]
        return {"enabled": enabled, "values": values, "source": source}

    def effective(self, item):
        """{module_key: values} for every enabled module of the item."""
        out = {}
        for m in registry.modules():
            st = self.module_state(item, m.key)
            if st["enabled"]:
                out[m.key] = st["values"]
        return out

    def context(self, item):
        eff = self.effective(item)
        ctx = tokens.base_context()
        ctx["setup"] = item["name"]
        ctx["folder"] = self.get(item["parent"])["name"] if item.get("parent") and self.get(item["parent"]) else ""
        cam = (eff.get("camera") or {}).get("camera") or {}
        ctx["camera"] = cam.get("name", "nocam")
        out = eff.get("output") or {}
        ctx["width"] = out.get("width", ctx["width"])
        ctx["height"] = out.get("height", ctx["height"])
        for m in registry.modules():  # optional hook: modules may add tokens (e.g. Output builder)
            hook = getattr(m, "extend_context", None)
            if hook and m.key in eff:
                hook(ctx, eff[m.key])
        return ctx

    def summary(self, item, key):
        st = self.module_state(item, key)
        m = registry.get(key)
        if not st["enabled"] or m is None:
            return ""
        try:
            return m.summary(st["values"])
        except Exception:
            return "?"

    def describe(self, item):
        item = self.require(item)
        return ["%s: %s" % (m.label, self.summary(item, m.key))
                for m in registry.modules() if self.module_state(item, m.key)["enabled"]]

    # ---- create / edit ---------------------------------------------------
    def _insert(self, item, parent, after=None):
        if parent:
            p = self.require(parent)  # id, name or path
            parent = p["id"] if p["type"] == "folder" else p.get("parent")
        item["parent"] = parent or None
        item["name"] = self.unique_name(item["name"], parent, exclude=item)
        if after is not None and after in self.items:
            self.items.insert(self.items.index(after) + 1, item)
        else:
            self.items.append(item)
        return item

    def add_folder(self, name="Folder", parent=None):
        f = self._insert(storage.new_item("folder", name), parent)
        self.commit()
        return f

    def add_setup(self, name=None, parent=None, keys=None, thumbnail=None, capture=True):
        s = storage.new_item("setup", name or "Setup %d" % (len(self.setups()) + 1))
        s["thumbnail"] = thumbnail
        self._insert(s, parent)
        if capture:
            self._capture_into(s, keys or [m.key for m in registry.modules() if m.available()])
        self.data["active"] = s["id"]
        self.commit()
        return s

    def _capture_into(self, item, keys=None, only_differences=True):
        """Store scene values on the item. Values equal to what it already inherits are skipped."""
        if keys is None:
            keys = [m.key for m in registry.modules() if self.module_state(item, m.key)["enabled"]] \
                or [m.key for m in registry.modules() if m.available()]
        parent = self.get(item.get("parent"))
        for k in keys:
            m = registry.get(k)
            if m is None:
                continue
            try:
                values = m.capture()
            except Exception:
                if len(keys) == 1:
                    raise
                traceback.print_exc()  # one broken module must not stop a new setup (M2)
                print("Scene Manager: %s was not captured" % m.label)
                continue
            inherited = self.module_state(parent, k) if parent else {"enabled": False, "values": {}}
            entry = item["modules"].setdefault(k, {"enabled": None, "values": {}})
            if not inherited["enabled"]:
                entry["enabled"] = True
            for p, v in values.items():
                if only_differences and inherited["values"].get(p) == v and p not in entry["values"]:
                    continue
                prop = m.prop(p)
                if only_differences and prop is not None and prop.kind == "table" and isinstance(v, dict) \
                        and isinstance(inherited["values"].get(p), dict):
                    # M2: store only the rows that differ from what the folder already gives
                    inh = inherited["values"][p]
                    v = {r: c for r, c in v.items() if inh.get(r) != c}
                    if not v and p not in entry["values"]:
                        continue
                entry["values"][p] = v

    def capture(self, key, keys=None):
        item = self.require(key)
        self._capture_into(item, keys)
        self.commit()
        return item

    def set_values(self, key, module_key, values):
        """Override properties on an item (merge)."""
        if registry.get(module_key) is None:
            raise KeyError("Unknown module %r" % module_key)
        item = self.require(key)
        entry = item["modules"].setdefault(module_key, {"enabled": None, "values": {}})
        if not self.module_state(item, module_key)["enabled"]:
            entry["enabled"] = True
        entry["values"].update(values)
        self.commit()

    def clear_value(self, key, module_key, prop):
        item = self.require(key)
        entry = item["modules"].get(module_key)
        if entry:
            entry["values"].pop(prop, None)
            self.commit()

    def set_enabled(self, key, module_key, enabled):
        """True/False overrides the folder; None means inherit."""
        item = self.require(key)
        entry = item["modules"].setdefault(module_key, {"enabled": None, "values": {}})
        entry["enabled"] = enabled
        if enabled is None and not entry["values"]:
            item["modules"].pop(module_key, None)
        self.commit()

    def remove_module(self, key, module_key):
        self.require(key)["modules"].pop(module_key, None)
        self.commit()

    def update_item(self, key, **fields):
        """name, description, tags, color, thumbnail, notes"""
        item = self.require(key)
        if "name" in fields and fields["name"]:
            fields["name"] = self.unique_name(fields["name"].strip(), item.get("parent"), exclude=item)
        item.update({k: v for k, v in fields.items() if k in
                     ("name", "description", "tags", "color", "thumbnail", "notes")})
        self.commit()
        return item

    def duplicate(self, key):
        item = self.require(key)
        clones = {}
        for src in [item] + self.descendants(item["id"]):
            c = copy.deepcopy(src)
            c["id"] = uuid.uuid4().hex
            c["parent"] = clones.get(src.get("parent"), src.get("parent"))
            clones[src["id"]] = c["id"]
            if src is item:
                c["name"] = self.unique_name(item["name"] + " copy", item.get("parent"))
                self.items.insert(self.items.index(item) + 1, c)
                first = c
            else:
                self.items.append(c)
        self.commit()
        return first

    def delete(self, key):
        item = self.require(key)
        doomed = [item] + self.descendants(item["id"])
        for d in doomed:
            self.items.remove(d)
            if self.data.get("active") == d["id"]:
                self.data["active"] = None
        self.commit()

    def move(self, key, parent, index=None):
        """Re-parent an item. index = position among the new siblings."""
        item = self.require(key)
        if parent:
            p = self.require(parent)
            if p["type"] != "folder" or p is item or p in self.descendants(item["id"]):
                raise ValueError("Can only move into a folder that is not inside the item")
        self.items.remove(item)
        item["parent"] = parent
        item["name"] = self.unique_name(item["name"], parent, exclude=item)
        sibs = self.children(parent)
        if index is None or index >= len(sibs):
            self.items.append(item)
        else:
            self.items.insert(self.items.index(sibs[max(0, index)]), item)
        self.commit()

    def set_order(self, structure):
        """Rebuild order and parents from [(id, parent_id), ...] in display order (from the UI)."""
        by_id = {i["id"]: i for i in self.items}
        new = []
        for iid, parent in structure:
            if iid in by_id:
                by_id[iid]["parent"] = parent
                new.append(by_id.pop(iid))
        new.extend(by_id.values())
        self.data["items"] = new
        self._index = None
        self.commit()

    # ---- apply -----------------------------------------------------------
    def apply(self, key, only=None, undo=None):
        """Activate a setup (or just some modules). Returns a list of error strings.

        undo: label of one undo step for the scene changes (the panel passes it; batch render does not).
        Render settings and the environment are not undoable in 3ds Max; nodes, lights and layers are."""
        if undo:
            import pymxs
            with pymxs.undo(True, undo):
                return self._apply(key, only)
        return self._apply(key, only)

    def _apply(self, key, only=None):
        item = self.require(key)
        if item["type"] != "setup":
            raise ValueError("'%s' is a folder; activate a setup inside it" % item["name"])
        t0 = time.perf_counter()
        errors = []
        was_open = bool(rt.renderSceneDialog.isOpen())
        if was_open:
            rt.renderSceneDialog.close()  # render settings do not stick while the dialog is open
        ctx = self.context(item)
        eff = self.effective(item)
        base_all = self.baseline
        redraw_off = _scene_redraw(False)  # one viewport redraw at the end instead of one per module
        try:
            for m in registry.modules():
                if only and m.key not in only:
                    continue
                if not getattr(m, "touches_scene", True):
                    continue
                # M2 deterministic activation: props (and modules) the setup does not store come from
                # the scene baseline when one is captured, so the result does not depend on which
                # setup was active before. Without a baseline the current scene fills the gaps (M1).
                base = base_all.get(m.key)
                if m.key not in eff and base is None:
                    reset = getattr(m, "reset", None)  # optional hook: undo what earlier setups changed
                    if reset is not None and not only:
                        try:
                            reset()
                        except Exception as e:
                            traceback.print_exc()
                            errors.append("%s: %s" % (m.label, e))
                    continue
                try:
                    if base is None or any(p.key not in base for p in m.props):
                        base = m.merge(m.capture(), base)
                    values = m.merge(base, eff[m.key]) if m.key in eff else base
                    m.apply(values, ctx)
                except Exception as e:
                    traceback.print_exc()
                    errors.append("%s: %s" % (m.label, e))
        finally:
            if redraw_off:
                _scene_redraw(True)
            if was_open:
                rt.renderSceneDialog.open()
        if not only:
            self.data["active"] = item["id"]
            storage.save(self.data)
        rt.redrawViews()
        self.last_apply_ms = int((time.perf_counter() - t0) * 1000)
        self._notify()
        return errors

    def differs_from_scene(self, item, key):
        """Props whose effective value differs from the scene right now."""
        m = registry.get(key)
        st = self.module_state(item, key)
        if not st["enabled"] or m is None or not getattr(m, "touches_scene", True):
            return set()
        try:
            cur = m.capture()
        except Exception:
            return set()
        return m.differs(st["values"], cur)

    # ---- scene baseline (M2: deterministic activation) --------------------
    @property
    def baseline(self):
        """{module_key: values}: the scene state every setup starts from. Empty = off (M1 behaviour)."""
        return self.data.get("baseline") or {}

    def capture_baseline(self, keys=None):
        """Record the current scene as the baseline for the given modules (default: every scene module)."""
        base = dict(self.baseline)
        for m in registry.modules():
            if (keys and m.key not in keys) or not getattr(m, "touches_scene", True):
                continue
            try:
                v = m.capture_baseline(self)
                if v is None:  # module opts out (e.g. it would undo another module's work)
                    base.pop(m.key, None)
                else:
                    base[m.key] = v
            except Exception as e:
                traceback.print_exc()
                print("Scene Manager: baseline for %s skipped: %s" % (m.label, e))
        self.data["baseline"] = base
        self.commit()
        return sorted(base)

    def clear_baseline(self, keys=None):
        if keys:
            base = {k: v for k, v in self.baseline.items() if k not in keys}
        else:
            base = {}
        self.data["baseline"] = base
        self.commit()

    def restore_baseline(self):
        """Put the scene back to the baseline (no setup active)."""
        errors = []
        ctx = tokens.base_context()
        for m in registry.modules():
            vals = self.baseline.get(m.key)
            if vals is None or not getattr(m, "touches_scene", True):
                continue
            try:
                m.apply(m.merge(m.capture(), vals), ctx)
            except Exception as e:
                traceback.print_exc()
                errors.append("%s: %s" % (m.label, e))
        self.data["active"] = None
        storage.save(self.data)
        rt.redrawViews()
        self._notify()
        return errors

    # ---- presets (team sharing, merge/xref workaround) ---------------------
    def export_items(self, keys, path):
        """Export setups flattened (inherited values baked in) so a preset is self-contained."""
        out = []
        for k in keys:
            item = self.require(k)
            targets = [item] if item["type"] == "setup" else [i for i in self.descendants(item["id"]) if i["type"] == "setup"]
            for s in targets:
                c = {f: copy.deepcopy(s.get(f)) for f in ("name", "description", "tags", "color", "thumbnail", "notes")}
                c["folder"] = self.path(self.get(s["parent"])) if s.get("parent") else ""
                c["modules"] = {mk: {"enabled": True, "values": v} for mk, v in self.effective(s).items()}
                out.append(c)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tool": "scene_manager", "schema": storage.SCHEMA, "setups": out}, f, indent=2)
        return len(out)

    def import_items(self, path, parent=None):
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        added = []
        for s in payload.get("setups", []):
            it = storage.new_item("setup", s.get("name", "Imported"))
            for f_ in ("description", "tags", "color", "thumbnail", "notes"):
                if s.get(f_) is not None:
                    it[f_] = s[f_]
            mods = s.get("modules", {})
            if any(not isinstance(v, dict) or "values" not in v for v in mods.values()):
                mods = {k: {"enabled": True, "values": v} for k, v in mods.items()}  # v1 presets
            it["modules"] = mods
            self._insert(it, parent)
            added.append(it)
        self.commit()
        return added

    # ---- callbacks -------------------------------------------------------
    def on_node_renamed(self, old, new):
        n = nodes.rename_refs(self.items, old, new) + nodes.rename_refs(self.baseline, old, new)
        from . import repair  # M2: table rows are keyed by node name too
        n += repair.rekey_rows(self.data, old, new)
        if n:
            self.commit()
