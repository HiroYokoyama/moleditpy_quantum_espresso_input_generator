"""Quantum ESPRESSO input generator dialog."""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import PLUGIN_NAME, PLUGIN_VERSION
from . import writer
from .structure_panel import StructurePanel, dropped_cif_path


class QeInputDialog(QDialog):
    def __init__(
        self,
        parent=None,
        persistent_settings=None,
        get_molecule=None,
        mark_modified=None,
        get_cif_viewer=None,
        context=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"{PLUGIN_NAME} v{PLUGIN_VERSION}")
        self.resize(940, 720)

        self.persistent_settings = persistent_settings if persistent_settings is not None else {}
        self.mark_modified = mark_modified
        self.context = context
        self.setAcceptDrops(True)
        self._updating = False
        self._cell = None
        self._get_molecule = get_molecule
        self._pseudo_files = {}

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.structure_panel = StructurePanel(
            get_molecule=get_molecule, get_cif_viewer=get_cif_viewer, context=context
        )
        structure_tab = QWidget()
        structure_layout = QVBoxLayout(structure_tab)
        structure_layout.addWidget(self.structure_panel)
        structure_layout.addWidget(self._build_positions_box())
        structure_layout.addStretch(1)
        self.tabs.addTab(structure_tab, "Structure")

        self.tabs.addTab(self._build_control_tab(), "Control")
        self.tabs.addTab(self._build_system_tab(), "System")
        self.tabs.addTab(self._build_kpoints_tab(), "K-points")

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Courier New", 9))
        self.tabs.addTab(self.preview, "Preview")

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setTextFormat(Qt.TextFormat.RichText)
        self.warning_label.setStyleSheet("QLabel { color: #b36b00; }")
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton("Save Input...", QDialogButtonBox.ButtonRole.AcceptRole)
        self.copy_button = buttons.addButton("Copy", QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self.save_button.clicked.connect(self.save_input)
        self.copy_button.clicked.connect(self.copy_preview)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self.apply_settings(self.persistent_settings)
        self.structure_panel.changed.connect(self.update_preview)
        self.update_preview()

    # -- tabs -------------------------------------------------------------

    def _build_positions_box(self) -> QGroupBox:
        box = QGroupBox("Coordinates")
        form = QFormLayout(box)
        self.units_combo = QComboBox()
        self.units_combo.addItems(writer.POSITION_UNITS)
        form.addRow("ATOMIC_POSITIONS:", self.units_combo)
        self.units_combo.currentTextChanged.connect(self.update_preview)
        return box

    def _build_control_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)

        box = QGroupBox("&CONTROL")
        form = QFormLayout(box)
        self.calc_combo = QComboBox()
        self.calc_combo.addItems(writer.CALCULATIONS)
        form.addRow("calculation:", self.calc_combo)
        self.title_edit = QLineEdit()
        form.addRow("title:", self.title_edit)
        self.prefix_edit = QLineEdit()
        form.addRow("prefix:", self.prefix_edit)
        self.outdir_edit = QLineEdit()
        form.addRow("outdir:", self.outdir_edit)
        self.pseudo_dir_edit = QLineEdit()
        form.addRow("pseudo_dir:", self.pseudo_dir_edit)
        self.pseudo_pattern_combo = QComboBox()
        self.pseudo_pattern_combo.setEditable(True)
        self.pseudo_pattern_combo.addItems(writer.PSEUDO_PATTERNS)
        form.addRow("UPF pattern:", self.pseudo_pattern_combo)
        hint = QLabel("{El} = Si, {el} = si, {EL} = SI")
        form.addRow("", hint)

        search_row = QWidget()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.pseudo_search_edit = QLineEdit()
        self.pseudo_search_edit.setPlaceholderText("Folder holding your .UPF files")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_pseudo_folder)
        scan_button = QPushButton("Scan")
        scan_button.clicked.connect(self.scan_pseudo_folder)
        self.copy_button_pseudo = QPushButton("Copy into pseudo_dir")
        self.copy_button_pseudo.clicked.connect(self.copy_pseudos)
        search_layout.addWidget(self.pseudo_search_edit, 1)
        search_layout.addWidget(browse_button)
        search_layout.addWidget(scan_button)
        search_layout.addWidget(self.copy_button_pseudo)
        form.addRow("UPF folder:", search_row)

        self.pseudo_status_label = QLabel("Not scanned - the pattern above is used.")
        self.pseudo_status_label.setWordWrap(True)
        form.addRow("", self.pseudo_status_label)
        self.tprnfor_check = QCheckBox("tprnfor (print forces)")
        self.tstress_check = QCheckBox("tstress (print stress)")
        form.addRow("", self.tprnfor_check)
        form.addRow("", self.tstress_check)
        outer.addWidget(box)

        relax_box = QGroupBox("Relaxation / dynamics")
        relax_form = QFormLayout(relax_box)
        self.nstep_spin = QSpinBox()
        self.nstep_spin.setRange(1, 100000)
        relax_form.addRow("nstep:", self.nstep_spin)
        self.etot_edit = QLineEdit()
        relax_form.addRow("etot_conv_thr:", self.etot_edit)
        self.forc_edit = QLineEdit()
        relax_form.addRow("forc_conv_thr:", self.forc_edit)
        self.press_spin = QDoubleSpinBox()
        self.press_spin.setRange(-100000.0, 100000.0)
        self.press_spin.setSuffix(" kbar")
        relax_form.addRow("press (vc):", self.press_spin)
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 10000.0)
        self.temp_spin.setSuffix(" K")
        relax_form.addRow("tempw (md):", self.temp_spin)
        self.dt_spin = QDoubleSpinBox()
        self.dt_spin.setRange(0.1, 1000.0)
        self.dt_spin.setSuffix(" Ry a.u.")
        relax_form.addRow("dt (md):", self.dt_spin)
        outer.addWidget(relax_box)
        outer.addStretch(1)

        for widget in (self.calc_combo, self.pseudo_pattern_combo):
            widget.currentTextChanged.connect(self.update_preview)
        for widget in (
            self.title_edit,
            self.prefix_edit,
            self.outdir_edit,
            self.pseudo_dir_edit,
            self.etot_edit,
            self.forc_edit,
        ):
            widget.textChanged.connect(self.update_preview)
        for widget in (self.tprnfor_check, self.tstress_check):
            widget.toggled.connect(self.update_preview)
        for widget in (self.press_spin, self.temp_spin, self.dt_spin):
            widget.valueChanged.connect(self.update_preview)
        self.nstep_spin.valueChanged.connect(self.update_preview)
        return tab

    def _build_system_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)

        box = QGroupBox("&SYSTEM")
        form = QFormLayout(box)
        self.functional_combo = QComboBox()
        self.functional_combo.addItems(writer.FUNCTIONALS)
        form.addRow("input_dft:", self.functional_combo)
        self.ecutwfc_spin = QDoubleSpinBox()
        self.ecutwfc_spin.setRange(5.0, 500.0)
        self.ecutwfc_spin.setSuffix(" Ry")
        form.addRow("ecutwfc:", self.ecutwfc_spin)
        self.ecutrho_auto_check = QCheckBox("ecutrho = 8 x ecutwfc")
        form.addRow("", self.ecutrho_auto_check)
        self.ecutrho_spin = QDoubleSpinBox()
        self.ecutrho_spin.setRange(20.0, 4000.0)
        self.ecutrho_spin.setSuffix(" Ry")
        form.addRow("ecutrho:", self.ecutrho_spin)
        self.occupations_combo = QComboBox()
        self.occupations_combo.addItems(writer.OCCUPATIONS)
        form.addRow("occupations:", self.occupations_combo)
        self.smearing_combo = QComboBox()
        self.smearing_combo.addItems(writer.SMEARING)
        form.addRow("smearing:", self.smearing_combo)
        self.degauss_spin = QDoubleSpinBox()
        self.degauss_spin.setRange(0.0001, 1.0)
        self.degauss_spin.setDecimals(4)
        self.degauss_spin.setSingleStep(0.005)
        self.degauss_spin.setSuffix(" Ry")
        form.addRow("degauss:", self.degauss_spin)
        self.nspin_check = QCheckBox("nspin = 2 (spin polarised)")
        form.addRow("", self.nspin_check)
        self.magnetization_spin = QDoubleSpinBox()
        self.magnetization_spin.setRange(-1.0, 1.0)
        self.magnetization_spin.setSingleStep(0.1)
        form.addRow("starting_magnetization:", self.magnetization_spin)
        self.vdw_combo = QComboBox()
        self.vdw_combo.addItems(writer.VDW_OPTIONS)
        form.addRow("vdw_corr:", self.vdw_combo)
        self.isolated_combo = QComboBox()
        self.isolated_combo.addItems(writer.ASSUME_ISOLATED)
        self.isolated_combo.setToolTip(
            "Removes the interaction between periodic images: makov-payne or "
            "martyna-tuckerman for a molecule, 2D or esm for a slab."
        )
        form.addRow("assume_isolated:", self.isolated_combo)
        self.nbnd_spin = QSpinBox()
        self.nbnd_spin.setRange(0, 100000)
        self.nbnd_spin.setSpecialValueText("auto")
        form.addRow("nbnd:", self.nbnd_spin)
        self.charge_spin = QDoubleSpinBox()
        self.charge_spin.setRange(-20.0, 20.0)
        self.charge_spin.setSingleStep(1.0)
        self.charge_spin.setDecimals(2)
        form.addRow("tot_charge:", self.charge_spin)
        self.auto_charge_check = QCheckBox("Read the charge from the molecule")
        form.addRow("", self.auto_charge_check)
        outer.addWidget(box)

        elec_box = QGroupBox("&ELECTRONS")
        elec_form = QFormLayout(elec_box)
        self.conv_thr_edit = QLineEdit()
        elec_form.addRow("conv_thr:", self.conv_thr_edit)
        self.mixing_spin = QDoubleSpinBox()
        self.mixing_spin.setRange(0.01, 1.0)
        self.mixing_spin.setSingleStep(0.05)
        elec_form.addRow("mixing_beta:", self.mixing_spin)
        self.maxstep_spin = QSpinBox()
        self.maxstep_spin.setRange(1, 10000)
        elec_form.addRow("electron_maxstep:", self.maxstep_spin)
        self.diag_combo = QComboBox()
        self.diag_combo.addItems(writer.DIAGONALIZATION)
        elec_form.addRow("diagonalization:", self.diag_combo)
        outer.addWidget(elec_box)

        extra_box = QGroupBox("Additional &SYSTEM keywords")
        extra_layout = QVBoxLayout(extra_box)
        self.extra_edit = QPlainTextEdit()
        self.extra_edit.setPlaceholderText("nbnd = 40\nassume_isolated = 'makov-payne'")
        self.extra_edit.setMaximumHeight(110)
        extra_layout.addWidget(self.extra_edit)
        outer.addWidget(extra_box)
        outer.addStretch(1)

        for widget in (
            self.functional_combo,
            self.occupations_combo,
            self.smearing_combo,
            self.vdw_combo,
            self.isolated_combo,
            self.diag_combo,
        ):
            widget.currentTextChanged.connect(self.update_preview)
        for widget in (
            self.ecutwfc_spin,
            self.ecutrho_spin,
            self.degauss_spin,
            self.magnetization_spin,
            self.mixing_spin,
            self.charge_spin,
        ):
            widget.valueChanged.connect(self.update_preview)
        self.nbnd_spin.valueChanged.connect(self.update_preview)
        self.auto_charge_check.toggled.connect(self.update_preview)
        self.maxstep_spin.valueChanged.connect(self.update_preview)
        for widget in (self.ecutrho_auto_check, self.nspin_check):
            widget.toggled.connect(self.update_preview)
        self.conv_thr_edit.textChanged.connect(self.update_preview)
        self.extra_edit.textChanged.connect(self.update_preview)
        return tab

    def _build_kpoints_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        box = QGroupBox("K_POINTS")
        form = QFormLayout(box)
        self.kmode_combo = QComboBox()
        self.kmode_combo.addItems(writer.KPOINT_MODES)
        form.addRow("Mode:", self.kmode_combo)

        mesh_widget = QWidget()
        grid = QGridLayout(mesh_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        self.kmesh_spins = []
        self.kshift_checks = []
        for column, axis in enumerate("123"):
            spin = QSpinBox()
            spin.setRange(1, 200)
            grid.addWidget(QLabel(f"n{axis}:"), 0, column * 2)
            grid.addWidget(spin, 0, column * 2 + 1)
            self.kmesh_spins.append(spin)
            check = QCheckBox(f"shift {axis}")
            grid.addWidget(check, 1, column * 2, 1, 2)
            self.kshift_checks.append(check)
        form.addRow("Mesh / shift:", mesh_widget)

        self.kspacing_spin = QDoubleSpinBox()
        self.kspacing_spin.setRange(0.001, 1.0)
        self.kspacing_spin.setDecimals(4)
        self.kspacing_spin.setSingleStep(0.005)
        self.kspacing_spin.setSuffix(" 1/A")
        form.addRow("Automatic spacing:", self.kspacing_spin)
        self.slab_kpoint_check = QCheckBox("For a slab, force the third k-point to 1")
        self.slab_kpoint_check.setChecked(True)
        form.addRow("", self.slab_kpoint_check)
        outer.addWidget(box)

        hint = QLabel(
            "A molecule in a large box normally needs only the Gamma point; "
            "'K_POINTS gamma' also halves the cost versus a 1x1x1 mesh."
        )
        hint.setWordWrap(True)
        outer.addWidget(hint)
        outer.addStretch(1)

        self.kmode_combo.currentTextChanged.connect(self.update_preview)
        for spin in self.kmesh_spins:
            spin.valueChanged.connect(self.update_preview)
        for check in self.kshift_checks:
            check.toggled.connect(self.update_preview)
        self.kspacing_spin.valueChanged.connect(self.update_preview)
        self.slab_kpoint_check.toggled.connect(self.update_preview)
        return tab

    # -- drag and drop ----------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt naming
        """Accept a CIF dropped anywhere on the dialog, not only on the panel."""
        if dropped_cif_path(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt naming
        path = dropped_cif_path(event.mimeData())
        if not path:
            event.ignore()
            return
        self.structure_panel.load_cif_path(path)
        event.acceptProposedAction()

    # -- settings ---------------------------------------------------------

    def apply_settings(self, settings) -> None:
        settings = {**writer.default_settings(), **(settings or {})}
        self._updating = True
        try:
            self.calc_combo.setCurrentText(settings.get("calculation", "scf"))
            self.title_edit.setText(str(settings.get("title", "")))
            self.prefix_edit.setText(str(settings.get("prefix", "pwscf")))
            self.outdir_edit.setText(str(settings.get("outdir", "./out")))
            self.pseudo_dir_edit.setText(str(settings.get("pseudo_dir", "./pseudo")))
            self.pseudo_pattern_combo.setCurrentText(
                str(settings.get("pseudo_pattern", writer.PSEUDO_PATTERNS[0]))
            )
            self.tprnfor_check.setChecked(bool(settings.get("tprnfor", True)))
            self.tstress_check.setChecked(bool(settings.get("tstress", True)))
            self.nstep_spin.setValue(int(settings.get("nstep", 100)))
            self.etot_edit.setText(str(settings.get("etot_conv_thr", 1e-5)))
            self.forc_edit.setText(str(settings.get("forc_conv_thr", 1e-4)))
            self.press_spin.setValue(float(settings.get("press", 0.0)))
            self.temp_spin.setValue(float(settings.get("temperature", 300.0)))
            self.dt_spin.setValue(float(settings.get("dt", 20.0)))

            self.functional_combo.setCurrentText(settings.get("functional", writer.FUNCTIONALS[0]))
            self.ecutwfc_spin.setValue(float(settings.get("ecutwfc", 60.0)))
            self.ecutrho_auto_check.setChecked(bool(settings.get("ecutrho_auto", True)))
            self.ecutrho_spin.setValue(float(settings.get("ecutrho", 480.0)))
            self.occupations_combo.setCurrentText(settings.get("occupations", "smearing"))
            self.smearing_combo.setCurrentText(settings.get("smearing", writer.SMEARING[0]))
            self.degauss_spin.setValue(float(settings.get("degauss", 0.01)))
            self.nspin_check.setChecked(bool(settings.get("nspin")))
            self.magnetization_spin.setValue(float(settings.get("starting_magnetization", 0.5)))
            self.vdw_combo.setCurrentText(settings.get("vdw", writer.VDW_OPTIONS[0]))
            self.isolated_combo.setCurrentText(
                settings.get("assume_isolated", writer.ASSUME_ISOLATED[0])
            )
            self.conv_thr_edit.setText(str(settings.get("conv_thr", 1e-8)))
            self.mixing_spin.setValue(float(settings.get("mixing_beta", 0.7)))
            self.maxstep_spin.setValue(int(settings.get("electron_maxstep", 200)))
            self.diag_combo.setCurrentText(settings.get("diagonalization", "david"))
            self.extra_edit.setPlainText(str(settings.get("extra_system", "") or ""))

            self.kmode_combo.setCurrentText(settings.get("kpoint_mode", writer.KPOINT_MODES[1]))
            for spin, value in zip(self.kmesh_spins, settings.get("kmesh", [4, 4, 4])):
                spin.setValue(max(1, int(value)))
            for check, value in zip(self.kshift_checks, settings.get("kshift", [0, 0, 0])):
                check.setChecked(bool(value))
            self.kspacing_spin.setValue(float(settings.get("kspacing", 0.03)))
            self.slab_kpoint_check.setChecked(bool(settings.get("slab_kpoints_c1", True)))
            self.nbnd_spin.setValue(int(settings.get("nbnd", 0) or 0))
            self.charge_spin.setValue(float(settings.get("tot_charge", 0.0) or 0.0))
            self.auto_charge_check.setChecked(bool(settings.get("auto_charge", False)))
            self.pseudo_search_edit.setText(str(settings.get("pseudo_search_dir", "") or ""))
            self._pseudo_files = dict(settings.get("pseudo_files") or {})
            self.units_combo.setCurrentText(
                settings.get("position_units", writer.POSITION_UNITS[0])
            )
            self.structure_panel.apply_settings(settings)
        finally:
            self._updating = False
        self.update_preview()

    def read_settings(self) -> dict:
        settings = {
            "calculation": self.calc_combo.currentText(),
            "title": self.title_edit.text(),
            "prefix": self.prefix_edit.text(),
            "outdir": self.outdir_edit.text(),
            "pseudo_dir": self.pseudo_dir_edit.text(),
            "pseudo_pattern": self.pseudo_pattern_combo.currentText(),
            "tprnfor": self.tprnfor_check.isChecked(),
            "tstress": self.tstress_check.isChecked(),
            "nstep": self.nstep_spin.value(),
            "etot_conv_thr": _to_float(self.etot_edit.text(), 1e-5),
            "forc_conv_thr": _to_float(self.forc_edit.text(), 1e-4),
            "press": self.press_spin.value(),
            "temperature": self.temp_spin.value(),
            "dt": self.dt_spin.value(),
            "functional": self.functional_combo.currentText(),
            "ecutwfc": self.ecutwfc_spin.value(),
            "ecutrho_auto": self.ecutrho_auto_check.isChecked(),
            "ecutrho": self.ecutrho_spin.value(),
            "occupations": self.occupations_combo.currentText(),
            "smearing": self.smearing_combo.currentText(),
            "degauss": self.degauss_spin.value(),
            "nspin": self.nspin_check.isChecked(),
            "starting_magnetization": self.magnetization_spin.value(),
            "vdw": self.vdw_combo.currentText(),
            "assume_isolated": self.isolated_combo.currentText(),
            "conv_thr": _to_float(self.conv_thr_edit.text(), 1e-8),
            "mixing_beta": self.mixing_spin.value(),
            "electron_maxstep": self.maxstep_spin.value(),
            "diagonalization": self.diag_combo.currentText(),
            "extra_system": self.extra_edit.toPlainText(),
            "kpoint_mode": self.kmode_combo.currentText(),
            "kmesh": [spin.value() for spin in self.kmesh_spins],
            "kshift": [1 if check.isChecked() else 0 for check in self.kshift_checks],
            "kspacing": self.kspacing_spin.value(),
            "slab_kpoints_c1": self.slab_kpoint_check.isChecked(),
            "nbnd": self.nbnd_spin.value(),
            "tot_charge": self.charge_spin.value(),
            "auto_charge": self.auto_charge_check.isChecked(),
            "pseudo_search_dir": self.pseudo_search_edit.text(),
            "pseudo_files": dict(self._pseudo_files),
            "position_units": self.units_combo.currentText(),
        }
        settings.update(self.structure_panel.read_settings())
        return settings

    # -- preview / output -------------------------------------------------

    def update_preview(self, *_args) -> None:
        if self._updating:
            return
        self._apply_auto_charge()
        settings = self.read_settings()
        self.persistent_settings.update(settings)
        if self.mark_modified is not None:
            try:
                self.mark_modified()
            except Exception:  # pragma: no cover - host API guard
                pass

        self.ecutrho_spin.setEnabled(not self.ecutrho_auto_check.isChecked())
        self.smearing_combo.setEnabled(self.occupations_combo.currentText() == "smearing")
        self.degauss_spin.setEnabled(self.occupations_combo.currentText() == "smearing")
        self.magnetization_spin.setEnabled(self.nspin_check.isChecked())

        try:
            self._cell = self.structure_panel.build_cell()
        except (ValueError, OSError) as exc:
            self._cell = None
            self.structure_panel.refresh_summary(error=str(exc))
            self.preview.setPlainText(f"! {exc}")
            self._show_warnings([])
            self.save_button.setEnabled(False)
            return

        self.structure_panel.refresh_summary(self._cell)
        self.preview.setPlainText(writer.build_input(self._cell, settings))
        self._show_warnings(writer.validate(self._cell, settings))
        self.save_button.setEnabled(True)

    def _apply_auto_charge(self) -> None:
        if not self.auto_charge_check.isChecked() or self._get_molecule is None:
            return
        from .cell_model import molecule_charge_and_multiplicity

        try:
            charge, multiplicity = molecule_charge_and_multiplicity(self._get_molecule())
        except (ValueError, AttributeError, TypeError):
            return
        blocked = self._updating
        self._updating = True
        try:
            self.charge_spin.setValue(float(charge))
            # An open shell needs spin polarisation to be meaningful.
            if multiplicity > 1 and not self.nspin_check.isChecked():
                self.nspin_check.setChecked(True)
        finally:
            self._updating = blocked

    def _browse_pseudo_folder(self) -> None:  # pragma: no cover - file dialog
        folder = QFileDialog.getExistingDirectory(
            self, "Choose the folder holding your UPF files", self.pseudo_search_edit.text()
        )
        if folder:
            self.pseudo_search_edit.setText(folder)
            self.scan_pseudo_folder()

    def scan_pseudo_folder(self) -> None:
        from . import pseudos

        folder = self.pseudo_search_edit.text().strip()
        if self._cell is None:
            self.pseudo_status_label.setText("Load a structure first.")
            return
        elements = [element for element, _ in writer.sorted_by_species(self._cell)[1]]
        chosen, missing = pseudos.match_elements(elements, folder)
        self._pseudo_files = chosen
        if not folder:
            self.pseudo_status_label.setText("Choose a folder to scan for UPF files.")
        elif chosen:
            found = ", ".join(f"{element} -> {name}" for element, name in chosen.items())
            note = f"  |  not found: {', '.join(missing)}" if missing else ""
            self.pseudo_status_label.setText(found + note)
        else:
            self.pseudo_status_label.setText(
                f"No UPF file matched {', '.join(elements)} in that folder."
            )
        self.update_preview()

    def copy_pseudos(self) -> None:
        from . import pseudos

        if not self._pseudo_files:
            QMessageBox.information(
                self,
                "Quantum ESPRESSO Input Generator",
                "Scan a UPF folder first so there is something to copy.",
            )
            return
        source = self.pseudo_search_edit.text().strip()
        destination = self.pseudo_dir_edit.text().strip() or "./pseudo"
        try:
            copied = pseudos.copy_into(self._pseudo_files, source, destination)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Quantum ESPRESSO Input Generator", str(exc))
            return
        QMessageBox.information(
            self,
            "Quantum ESPRESSO Input Generator",
            f"Copied {len(copied)} pseudopotential file(s) into\n{os.path.abspath(destination)}",
        )

    def _show_warnings(self, messages) -> None:
        if not messages:
            self.warning_label.setVisible(False)
            self.warning_label.clear()
            return
        items = "".join(f"<li>{message}</li>" for message in messages)
        self.warning_label.setText(f"<b>Check:</b><ul>{items}</ul>")
        self.warning_label.setVisible(True)

    def copy_preview(self) -> None:
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.preview.toPlainText())

    def save_input(self) -> None:
        if self._cell is None:
            QMessageBox.warning(
                self, "Quantum ESPRESSO Input Generator", "There is no valid structure to write."
            )
            return
        settings = self.read_settings()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save pw.x input",
            writer.suggested_filename(settings),
            "Quantum ESPRESSO input (*.in);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(writer.build_input(self._cell, settings))
        except OSError as exc:
            QMessageBox.critical(
                self, "Quantum ESPRESSO Input Generator", f"Could not write the file:\n{exc}"
            )
            return
        QMessageBox.information(
            self, "Quantum ESPRESSO Input Generator", f"Wrote\n{os.path.abspath(path)}"
        )


def _to_float(text, default):
    try:
        return float(str(text).replace("d", "e").replace("D", "e"))
    except (TypeError, ValueError):
        return default
