import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qe_input_generator import writer  # noqa: E402
from qe_input_generator.main_dialog import QeInputDialog, _to_float  # noqa: E402

from test_cell_model import _FakeMol  # noqa: E402


@pytest.fixture
def dialog(qapp):
    mol = _FakeMol(["O", "H", "H"], [[0, 0, 0], [0.96, 0, 0], [-0.24, 0.93, 0]])
    dlg = QeInputDialog(persistent_settings=writer.default_settings(), get_molecule=lambda: mol)
    yield dlg
    dlg.deleteLater()


def test_dialog_builds_preview(dialog):
    text = dialog.preview.toPlainText()
    assert "&CONTROL" in text and "ATOMIC_POSITIONS" in text
    assert dialog._cell is not None
    assert dialog.save_button.isEnabled()


def test_dialog_preview_tracks_calculation(dialog):
    dialog.calc_combo.setCurrentText("vc-relax")
    text = dialog.preview.toPlainText()
    assert "'vc-relax'" in text
    assert "&CELL" in text


def test_dialog_preview_tracks_kpoints(dialog):
    dialog.kmode_combo.setCurrentText("Gamma point only")
    assert "K_POINTS gamma" in dialog.preview.toPlainText()


def test_dialog_updates_persistent_settings(dialog):
    dialog.ecutwfc_spin.setValue(75.0)
    assert dialog.persistent_settings["ecutwfc"] == 75.0


def test_dialog_marks_the_project_modified(qapp):
    seen = []
    mol = _FakeMol(["H"], [[0.0, 0.0, 0.0]])
    dlg = QeInputDialog(
        persistent_settings={}, get_molecule=lambda: mol, mark_modified=lambda: seen.append(1)
    )
    dlg.ecutwfc_spin.setValue(44.0)
    assert seen
    dlg.deleteLater()


def test_dialog_settings_roundtrip(dialog):
    settings = dialog.read_settings()
    settings.update(
        {"calculation": "relax", "ecutwfc": 45.0, "kmesh": [2, 3, 4], "occupations": "fixed"}
    )
    dialog.apply_settings(settings)
    out = dialog.read_settings()
    assert out["calculation"] == "relax"
    assert out["ecutwfc"] == 45.0
    assert out["kmesh"] == [2, 3, 4]
    assert out["occupations"] == "fixed"


def test_dialog_ecutrho_field_follows_the_auto_toggle(dialog):
    dialog.ecutrho_auto_check.setChecked(True)
    assert not dialog.ecutrho_spin.isEnabled()
    dialog.ecutrho_auto_check.setChecked(False)
    assert dialog.ecutrho_spin.isEnabled()


def test_dialog_smearing_fields_follow_occupations(dialog):
    dialog.occupations_combo.setCurrentText("fixed")
    assert not dialog.smearing_combo.isEnabled()
    assert not dialog.degauss_spin.isEnabled()
    dialog.occupations_combo.setCurrentText("smearing")
    assert dialog.smearing_combo.isEnabled()


def test_dialog_magnetization_follows_nspin(dialog):
    dialog.nspin_check.setChecked(True)
    assert dialog.magnetization_spin.isEnabled()
    assert "starting_magnetization(1)" in dialog.preview.toPlainText()


def test_dialog_custom_pseudo_pattern(dialog):
    dialog.pseudo_pattern_combo.setCurrentText("{el}.oncv.upf")
    assert "o.oncv.upf" in dialog.preview.toPlainText()


def test_dialog_reports_a_missing_molecule(qapp):
    dlg = QeInputDialog(persistent_settings={}, get_molecule=lambda: None)
    assert "No molecule" in dlg.preview.toPlainText()
    assert not dlg.save_button.isEnabled()
    dlg.deleteLater()


@pytest.mark.parametrize(
    "text,expected",
    [("1.0d-8", 1e-8), ("1e-6", 1e-6), ("0.5", 0.5), ("junk", 42.0), (None, 42.0)],
)
def test_to_float_accepts_fortran_exponents(text, expected):
    assert _to_float(text, 42.0) == expected


def test_dialog_save_writes_the_input(dialog, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    target = tmp_path / "si.scf.in"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    dialog.save_input()
    text = target.read_text(encoding="utf-8")
    assert text.startswith("&CONTROL")
    assert "\r" not in text


def test_dialog_save_is_cancellable(dialog, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    dialog.save_input()
    assert not list(tmp_path.iterdir())


def test_dialog_save_without_structure_warns(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    seen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: seen.append(a))
    dlg = QeInputDialog(persistent_settings={}, get_molecule=lambda: None)
    dlg.save_input()
    assert seen
    dlg.deleteLater()


def test_dialog_copy_preview(dialog, qapp):
    dialog.copy_preview()
    assert "&CONTROL" in qapp.clipboard().text()
