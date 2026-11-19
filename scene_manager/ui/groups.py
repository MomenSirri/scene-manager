"""Module groups shown in the left bar and the Add module palette, named as in Scene Manager 3.

This is a UI grouping only: modules keep their own `category` (used by other code). A module listed in
MEMBERS goes to that group; any other module falls back by category, so new modules need no edit here.
"""
GROUPS = [
    # key, label, rail icon, tint
    ("view", "View", "camera", "#0a84ff"),
    ("light", "Light and sky", "light", "#ff9f0a"),
    ("scene", "Scene", "scene", "#bf5af2"),
    ("render", "Render", "rendersettings", "#ff453a"),
    ("custom", "Custom", "script", "#30d158"),
    ("notes", "Notes", "note", "#2ad4c4"),
]
MEMBERS = {
    "view": ["camera", "output", "time"],
    "light": ["sun", "dome", "environment", "env_override", "lights", "atmosphere"],
    "scene": ["layers", "objects", "xref_scenes", "viewport_bg"],
    "render": ["output_builder", "render_elements", "render_preset", "renderer", "render_override",
               "render_vray", "render_corona", "render_arnold", "post", "lightmix"],
    "custom": ["custom_props"],
    "notes": ["notes", "todo"],
}
BY_CATEGORY = {"camera": "view", "light": "light", "env": "light", "scene": "scene",
               "render": "render", "script": "custom"}
_member_of = {k: g for g, keys in MEMBERS.items() for k in keys}
LABEL = {k: l for k, l, _i, _t in GROUPS}
ICON = {k: i for k, _l, i, _t in GROUPS}
TINT = {k: t for k, _l, _i, t in GROUPS}


def group_of(module):
    return _member_of.get(module.key) or BY_CATEGORY.get(getattr(module, "category", ""), "custom")


def modules_in(group, modules):
    return [m for m in modules if group_of(m) == group]
