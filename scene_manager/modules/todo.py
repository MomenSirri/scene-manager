"""To do: a checklist per setup or folder. Never touches the scene.

Values: {"items": [{"text": str, "done": bool}]}. A setup's list replaces its folder's list.
"""
from ..core.module_base import Module, Prop
from ..core.registry import register


@register
class TodoModule(Module):
    key = "todo"
    label = "To do"
    order = 910
    category = "scene"
    column = "To do"
    touches_scene = False
    props = [Prop("items", "To do", "todo")]

    def available(self):
        return False  # added by hand (+ Add Module), not to every new setup

    def capture(self):
        return {}

    def apply(self, values, context):
        pass

    def summary(self, values):
        items = values.get("items") or []
        if not items:
            return ""
        return "%d/%d done" % (len([i for i in items if i.get("done")]), len(items))
