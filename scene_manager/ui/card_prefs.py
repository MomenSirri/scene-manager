"""Per-user look of each module card (config.json "card_ui"): column span, height, colour, title.

Keyed by module key, so a card keeps its size and colour on every setup.
"""
from .. import config

COLORS = ["#ff453a", "#ff9f0a", "#30d158", "#2ad4c4", "#64d2ff", "#0a84ff", "#5e5ce6", "#bf5af2", "#8e8e93"]


def get(key):
    return dict((config.load().get("card_ui") or {}).get(key) or {})


def update(key, **kw):
    cfg = config.load()
    ui = dict(cfg.get("card_ui") or {})
    entry = dict(ui.get(key) or {})
    for k, v in kw.items():
        if v is None:
            entry.pop(k, None)
        else:
            entry[k] = v
    ui[key] = entry
    cfg["card_ui"] = ui
    config.save(cfg)
