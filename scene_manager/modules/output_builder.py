"""Output builder: {version} numbering and custom tokens for every path that uses tokens
(Output, render element files, V-Ray channels/raw, render preset).

{version}: 0 = next free number on disk (looks at existing files/folders), or a fixed number.
Custom tokens: any name -> text, e.g. {"client": "ACME", "phase": "DD"} makes {client} and {phase} work.
A custom token may itself use built-in tokens, e.g. {"shot": "{camera}_{width}"}.
"""
from ..core import tokens
from ..core.module_base import Module, Prop
from ..core.registry import register
from ..render import rprops


@register
class OutputBuilderModule(Module):
    key = "output_builder"
    label = "Output builder"
    order = 15     # before Output (20), so its tokens are in the context when paths resolve
    category = "camera"
    props = [
        Prop("version", "Version", "int", minimum=0, maximum=9999,
             tip="0 = next free version on disk. Use {version} in paths, e.g. D:/renders/{scene}/{setup}_v{version}.exr"),
        Prop("version_pad", "Digits", "int", minimum=1, maximum=6, tip="3 -> 007"),
        Prop("custom", "Custom tokens", "rdiff", tip="Token name -> text. Use them in paths as {name}."),
    ]

    def available(self):
        return False

    def capture(self):
        return {"version": 0, "version_pad": 3}

    def merge(self, base, over):
        return rprops.merge_module(base, over, dict_props=("custom",))

    def extend_context(self, ctx, values):
        """Called by SetupManager.context(); also from apply() for cores without that hook."""
        ctx["version"] = int(values.get("version") or 0)
        ctx["version_pad"] = int(values.get("version_pad") or 3)
        builtin = {k: v for k, v in ctx.items()}
        for name, text in (values.get("custom") or {}).items():
            name = str(name).strip().strip("{}")
            if not name or name in tokens.TOKENS:
                continue
            text = str(text)
            ctx[name] = text.format_map(tokens._Safe(builtin)) if "{" in text else text

    def apply(self, values, context):
        self.extend_context(context, values)

    def differs(self, values, scene):
        return set()

    def summary(self, values):
        v = int(values.get("version") or 0)
        bits = ["v%s" % str(v).zfill(int(values.get("version_pad") or 3)) if v else "v auto"]
        if values.get("custom"):
            bits.append("%d tokens" % len(values["custom"]))
        return ", ".join(bits)
