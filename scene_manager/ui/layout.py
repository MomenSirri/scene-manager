"""Card layout tokens (spacing, alignment, sizes) and the live Layout popover.

Every gap in a module card comes from here. A density preset gives the base values; the user can
override any single token from the Layout popover (saved in ~/.scene_manager/config.json).
"""
from PySide6 import QtCore, QtWidgets

from .. import config

PRESETS = {
    "compact": dict(card_pad=10, header_pad=6, header_gap=6, row_gap=4, col_gap=6, card_gap=8,
                    label_width=92, field_height=22, field_radius=5, card_radius=10, icon_size=16,
                    card_min_width=260),
    "regular": dict(card_pad=12, header_pad=10, header_gap=8, row_gap=6, col_gap=8, card_gap=12,
                    label_width=112, field_height=24, field_radius=6, card_radius=14, icon_size=18,
                    card_min_width=300),
    "comfortable": dict(card_pad=16, header_pad=12, header_gap=10, row_gap=10, col_gap=12, card_gap=16,
                        label_width=132, field_height=28, field_radius=7, card_radius=16, icon_size=20,
                        card_min_width=340),
}
CHOICES = {  # non-numeric tokens
    "label_align": ["left", "right"],   # text alignment inside the label column
    "label_pos": ["side", "above"],     # label beside the field, or above it
    "columns": ["auto", "1", "2", "3"],  # cards per row
    "show_dots": ["yes", "no"],         # status dots in front of each row
}
CHOICE_DEFAULTS = {"label_align": "left", "label_pos": "side", "columns": "auto", "show_dots": "yes"}
# (token, label, min, max) for the popover sliders
SLIDERS = [
    ("card_pad", "Card padding", 4, 32),
    ("header_pad", "Header height", 2, 24),
    ("header_gap", "Header spacing", 2, 20),
    ("row_gap", "Row spacing", 0, 24),
    ("col_gap", "Column spacing", 2, 24),
    ("label_width", "Label width", 50, 220),
    ("field_height", "Field height", 18, 40),
    ("card_gap", "Gap between cards", 0, 40),
    ("card_min_width", "Card width", 220, 520),
    ("card_radius", "Card corners", 0, 24),
    ("field_radius", "Field corners", 0, 14),
    ("icon_size", "Icon size", 12, 28),
]
DEFAULT_DENSITY = "regular"


def current():
    """Resolved tokens: preset + the user's overrides."""
    cfg = config.load()
    density = cfg.get("card_density", DEFAULT_DENSITY)
    t = dict(PRESETS.get(density, PRESETS[DEFAULT_DENSITY]))
    t.update(CHOICE_DEFAULTS)
    t.update({k: v for k, v in (cfg.get("card_layout") or {}).items() if k in t})
    t["density"] = density
    return t


def save(density=None, overrides=None, reset=False):
    cfg = config.load()
    if density is not None:
        cfg["card_density"] = density
    if reset:
        cfg["card_layout"] = {}
    if overrides:
        cfg.setdefault("card_layout", {}).update(overrides)
    config.save(cfg)


class LayoutPopover(QtWidgets.QFrame):
    """Floating panel with density presets and one slider per token. Changes apply live."""

    def __init__(self, on_change, parent=None):
        super().__init__(parent, QtCore.Qt.Popup)
        self.setObjectName("SMPopover")
        self.on_change = on_change
        self._timer = QtCore.QTimer(self, singleShot=True, interval=60, timeout=self.on_change)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)
        title = QtWidgets.QLabel("Card layout")
        title.setObjectName("SMTitle")
        outer.addWidget(title)

        seg = QtWidgets.QHBoxLayout()
        seg.setSpacing(4)
        self.density_group = QtWidgets.QButtonGroup(self)
        for key in PRESETS:
            b = QtWidgets.QPushButton(key.capitalize())
            b.setObjectName("SMChip")
            b.setCheckable(True)
            b.setProperty("density", key)
            self.density_group.addButton(b)
            seg.addWidget(b)
        self.density_group.buttonClicked.connect(self._on_density)
        outer.addLayout(seg)

        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
        self.sliders = {}
        for key, label, lo, hi in SLIDERS:
            row = QtWidgets.QHBoxLayout()
            s = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            s.setRange(lo, hi)
            s.setMinimumWidth(150)
            v = QtWidgets.QLabel()
            v.setObjectName("SMMuted")
            v.setFixedWidth(34)
            v.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            s.valueChanged.connect(lambda val, k=key, lbl=v: self._on_slider(k, val, lbl))
            row.addWidget(s, 1)
            row.addWidget(v)
            form.addRow(label, row)
            self.sliders[key] = (s, v)
        self.choices = {}
        names = {"label_align": "Label alignment", "label_pos": "Label position",
                 "columns": "Cards per row", "show_dots": "Status dots"}
        for key, opts in CHOICES.items():
            c = QtWidgets.QComboBox()
            c.addItems(opts)
            c.activated.connect(lambda _i, k=key, cb=c: self._on_choice(k, cb.currentText()))
            form.addRow(names[key], c)
            self.choices[key] = c
        outer.addLayout(form)
        reset = QtWidgets.QPushButton("Reset to preset")
        reset.setObjectName("SMButton")
        reset.clicked.connect(self._on_reset)
        outer.addWidget(reset, 0, QtCore.Qt.AlignRight)
        self.load()

    POPOVER_QSS = """
    #SMPopover QComboBox { background: #232325; border: 1px solid #38383a; border-radius: 6px; padding: 3px 8px;
        color: #f5f5f7; min-height: 18px; }
    #SMPopover QComboBox:focus { border: 1px solid #0a84ff; }
    #SMPopover QComboBox::drop-down { border: none; width: 16px; }
    #SMPopover QComboBox QAbstractItemView { background: #2c2c2e; color: #f5f5f7; border: 1px solid #38383a;
        selection-background-color: #0a84ff; }
    #SMPopover QLabel { color: #f5f5f7; }
    """

    def load(self):
        t = current()
        for b in self.density_group.buttons():
            b.setChecked(b.property("density") == t["density"])
        for key, (s, v) in self.sliders.items():
            s.blockSignals(True)
            s.setValue(int(t[key]))
            s.blockSignals(False)
            v.setText("%d px" % t[key] if key != "card_min_width" else "%d" % t[key])
        for key, c in self.choices.items():
            c.setCurrentText(str(t[key]))

    def _on_density(self, b):
        save(density=b.property("density"), reset=True)
        self.load()
        self.on_change()

    def _on_slider(self, key, val, lbl):
        lbl.setText("%d px" % val if key != "card_min_width" else "%d" % val)
        save(overrides={key: val})
        self._timer.start()

    def _on_choice(self, key, val):
        save(overrides={key: val})
        self.on_change()

    def _on_reset(self):
        save(reset=True)
        self.load()
        self.on_change()
