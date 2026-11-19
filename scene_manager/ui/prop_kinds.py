"""Extra property kinds for module cards (M2+), so module threads never edit cards.py.

    register_kind(kind, factory, always_editable=False, wide=False)
    factory(prop, value, emit, ctx) -> QWidget with .value() returning JSON-safe data; call emit()
    after the user changes something. ctx = {"own", "effective", "scene", "item", "mgr"}.
    always_editable: the widget is usable even when the prop is not stored on the item yet
    (the first edit stores it), e.g. tables with per-row ticks.
    wide: the widget gets the full card width on its own line, under the property label.

Every ui/kinds_*.py file is imported on first use; each calls register_kind at import.
"""
import importlib
import os
import traceback

KINDS = {}
_EDITABLE = set()
_WIDE = set()
_loaded = False


def register_kind(kind, factory, always_editable=False, wide=False):
    KINDS[kind] = factory
    (_EDITABLE.add if always_editable else _EDITABLE.discard)(kind)
    (_WIDE.add if wide else _WIDE.discard)(kind)


def _load():
    global _loaded
    if _loaded:
        return
    _loaded = True
    here = os.path.dirname(__file__)
    for fn in sorted(os.listdir(here)):
        if fn.startswith("kinds_") and fn.endswith(".py"):
            try:
                importlib.import_module("%s.%s" % (__package__, fn[:-3]))
            except Exception:
                print("Scene Manager: card widgets '%s' failed to load" % fn)
                traceback.print_exc()


def kinds():
    _load()
    return KINDS


def always_editable(kind):
    _load()
    return kind in _EDITABLE


def is_wide(kind):
    _load()
    return kind in _WIDE


def create(prop, value, emit, ctx):
    return kinds()[prop.kind](prop, value, emit, ctx)
