"""Atmosphere: which 3ds Max atmospheric effects are active (VRayEnvironmentFog,
VRayAerialPerspective, Corona volume effects, Max fog, ...). Effects are matched by name."""
from pymxs import runtime as rt

from ..core.module_base import Module, Prop
from ..core.registry import register


def effects():
    out = []
    for i in range(1, int(rt.numAtmospherics) + 1):
        a = rt.getAtmospheric(i)
        if a is not None:
            out.append(a)
    return out


@register
class AtmosphereModule(Module):
    key = "atmosphere"
    label = "Atmosphere"
    order = 58
    category = "env"
    props = [Prop("effects", "Effects", "checklist", tip="Ticked = active in this setup")]

    def capture(self):
        return {"effects": {str(a.name): bool(rt.isActive(a)) for a in effects()}}

    def apply(self, values, context):
        wanted = values.get("effects") or {}
        missing = [n for n in wanted if n not in {str(a.name) for a in effects()}]
        for a in effects():
            n = str(a.name)
            if n in wanted and bool(rt.isActive(a)) != bool(wanted[n]):
                rt.setActive(a, bool(wanted[n]))
        if missing:
            raise RuntimeError("atmospheric(s) not in scene: %s" % ", ".join(missing))

    def summary(self, values):
        on = [n for n, v in (values.get("effects") or {}).items() if v]
        return ", ".join(on) if on else "none"
