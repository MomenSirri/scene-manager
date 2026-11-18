"""Notes: free text per setup or folder (client feedback, what to check). Never touches the scene."""
from ..core.module_base import Module, Prop
from ..core.registry import register


@register
class NotesModule(Module):
    key = "notes"
    label = "Notes"
    order = 900
    category = "scene"
    touches_scene = False
    props = [Prop("text", "Notes", "note")]

    def available(self):
        return False  # added by hand (+ Add Module), not to every new setup

    def capture(self):
        return {}

    def apply(self, values, context):
        pass

    def summary(self, values):
        t = (values.get("text") or "").strip()
        return t.splitlines()[0][:60] if t else ""
