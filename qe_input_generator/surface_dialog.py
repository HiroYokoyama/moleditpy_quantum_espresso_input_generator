"""Surface energy from a bulk and a slab pw.x output."""

from __future__ import annotations

import os

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from . import outputs


class SurfaceEnergyDialog(QDialog):
    """Loads two pw.x outputs and reports E_surf in eV/A^2 and J/m^2."""

    def __init__(self, parent=None, get_area=None):
        super().__init__(parent)
        self.setWindowTitle("Surface Energy")
        self.resize(720, 520)
        self.get_area = get_area

        layout = QVBoxLayout(self)

        self.bulk_box, self.bulk_edit, self.bulk_energy, self.bulk_atoms = self._make_group(
            "Bulk output", self.load_bulk
        )
        layout.addWidget(self.bulk_box)
        self.slab_box, self.slab_edit, self.slab_energy, self.slab_atoms = self._make_group(
            "Slab output", self.load_slab
        )
        layout.addWidget(self.slab_box)

        area_box = QGroupBox("Surface")
        area_form = QFormLayout(area_box)
        self.area_spin = QDoubleSpinBox()
        self.area_spin.setRange(0.0001, 1e6)
        self.area_spin.setDecimals(4)
        self.area_spin.setValue(1.0)
        self.area_spin.setSuffix(" A^2")
        area_form.addRow("Area (a x b):", self.area_spin)
        self.use_current_button = QPushButton("Use the slab currently in the generator")
        self.use_current_button.clicked.connect(self.use_current_area)
        area_form.addRow("", self.use_current_button)
        layout.addWidget(area_box)

        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setFont(QFont("Courier New", 9))
        layout.addWidget(self.result, 1)

        buttons = QDialogButtonBox()
        compute = buttons.addButton("Calculate", QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Close)
        compute.clicked.connect(self.calculate)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self.use_current_area()

    def _make_group(self, title, loader):
        box = QGroupBox(title)
        form = QFormLayout(box)
        row = QHBoxLayout()
        edit = QLineEdit()
        edit.setReadOnly(True)
        button = QPushButton("Load...")
        button.clicked.connect(loader)
        row.addWidget(edit, 1)
        row.addWidget(button)
        form.addRow("File:", row)
        energy = QLineEdit()
        energy.setPlaceholderText("Ry")
        form.addRow("Total energy:", energy)
        atoms = QSpinBox()
        atoms.setRange(1, 100000)
        form.addRow("Atoms:", atoms)
        return box, edit, energy, atoms

    # -- loading ----------------------------------------------------------

    def load_bulk(self) -> None:  # pragma: no cover - file dialog
        self._load_into(self.bulk_edit, self.bulk_energy, self.bulk_atoms, "bulk")

    def load_slab(self) -> None:  # pragma: no cover - file dialog
        self._load_into(self.slab_edit, self.slab_energy, self.slab_atoms, "slab")

    def _load_into(self, edit, energy_field, atom_field, label):  # pragma: no cover
        path, _ = QFileDialog.getOpenFileName(
            self, f"Open the {label} pw.x output", "", "pw.x output (*.out *.log);;All files (*)"
        )
        if not path:
            return
        self.read_output(path, edit, energy_field, atom_field)

    def read_output(self, path, edit, energy_field, atom_field) -> bool:
        """Parse one output file into the fields; returns True on success."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            energy = outputs.parse_total_energy(text)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Surface Energy", str(exc))
            return False

        edit.setText(os.path.basename(path))
        energy_field.setText(f"{energy:.10f}")
        try:
            atom_field.setValue(outputs.parse_atom_count(text))
        except ValueError:
            pass  # the count can be typed in by hand
        return True

    def use_current_area(self) -> None:
        if self.get_area is None:
            return
        try:
            area = self.get_area()
        except Exception:  # pragma: no cover - host guard
            return
        if area:
            self.area_spin.setValue(float(area))

    # -- result -----------------------------------------------------------

    def calculate(self) -> None:
        try:
            slab_energy = float(self.slab_energy.text())
            bulk_energy = float(self.bulk_energy.text())
        except (TypeError, ValueError):
            self.result.setPlainText("Load both outputs, or type the two total energies in Ry.")
            return
        try:
            text = outputs.describe(
                slab_energy,
                self.slab_atoms.value(),
                bulk_energy,
                self.bulk_atoms.value(),
                self.area_spin.value(),
            )
        except ValueError as exc:
            self.result.setPlainText(str(exc))
            return
        self.result.setPlainText(text)
