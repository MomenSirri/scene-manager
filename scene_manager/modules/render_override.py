"""Render settings override: every renderer property that differs from the renderer's defaults.

Fetch = compare the current renderer with a fresh instance of the same renderer class and keep the
differences. Apply = set those properties back. Covers everything the curated cards do not.
Properties owned by other modules are skipped: curated settings, output/channels (Render elements),
tone mapping (Post-production), environment overrides (Environment, M3).
"""
from ..core.module_base import Module, Prop
from ..core.registry import register
from ..render import rprops

SKIP_PREFIXES = ("output_", "environment_", "colorMap_", "colormap_", "bloomGlare_", "bg_", "vfb_")


def _owned_names():
    from . import render_settings
    names = set()
    for cls in (render_settings.VRaySettings, render_settings.CoronaSettings, render_settings.ArnoldSettings):
        for p in cls.props:
            names.update(p.names)
    return names


def scene_diff():
    r = rprops.current()
    owned = _owned_names()
    cur = rprops.snapshot(r, include=lambda n: n not in owned and not n.startswith(SKIP_PREFIXES))
    return rprops.diff(cur, rprops.defaults(r))


@register
class RenderOverrideModule(Module):
    key = "render_override"
    label = "Render overrides"
    order = 45   # before the curated cards, so a curated value set on a setup always wins
    category = "render"
    props = [
        Prop("renderer", "Fetched from", "text", tip="Renderer the overrides were fetched from; they only apply to it"),
        Prop("overrides", "Changed properties", "rdiff",
             tip="Renderer properties that differ from the defaults. Fetch from scene to refresh."),
    ]

    def available(self):
        return False   # not part of every new setup; add it with + Module, then Fetch

    def capture(self):
        return {"renderer": rprops.current_kind(), "overrides": scene_diff()}

    def merge(self, base, over):
        return rprops.merge_module(base, over, dict_props=("overrides",))

    def apply(self, values, context):
        ov = values.get("overrides") or {}
        if not ov:
            return
        kind = values.get("renderer")
        if kind and kind != rprops.current_kind():
            return   # fetched from another renderer: applies only when that renderer is current
        r = rprops.current()
        missing = [p for p, v in ov.items() if rprops.write(r, [p], v) is None]
        if missing:
            raise RuntimeError("not on this renderer: %s" % ", ".join(sorted(missing)[:8]))

    def differs(self, values, scene):
        """Orange dot only when a stored override is not what the renderer has now."""
        out = set()
        cur = scene.get("overrides") or {}
        r = rprops.current()
        for p, v in (values.get("overrides") or {}).items():
            now = cur.get(p) if p in cur else rprops.read(r, [p])
            if not rprops._same(now, v):
                out.add("overrides")
                break
        if values.get("renderer") and values.get("renderer") != scene.get("renderer"):
            out.add("renderer")
        return out

    def summary(self, values):
        n = len(values.get("overrides") or {})
        return "%d changed" % n if n else ""
