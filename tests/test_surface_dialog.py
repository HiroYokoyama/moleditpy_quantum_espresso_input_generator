import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qe_input_generator.surface_dialog import SurfaceEnergyDialog  # noqa: E402

BULK_OUT = """
     number of atoms/cell      =            1
!    total energy              =     -10.00000000 Ry
     JOB DONE.
"""

SLAB_OUT = """
     number of atoms/cell      =            4
!    total energy              =     -39.00000000 Ry
     JOB DONE.
"""


@pytest.fixture
def dialog(qapp):
    dlg = SurfaceEnergyDialog(get_area=lambda: 2.0)
    yield dlg
    dlg.deleteLater()


def test_area_is_prefilled_from_the_generator(dialog):
    assert dialog.area_spin.value() == pytest.approx(2.0)


def test_area_helper_tolerates_no_generator(qapp):
    dlg = SurfaceEnergyDialog(get_area=lambda: None)
    assert dlg.area_spin.value() > 0
    dlg.deleteLater()


def test_area_helper_survives_a_raising_callback(qapp):
    def _boom():
        raise RuntimeError("gone")

    dlg = SurfaceEnergyDialog(get_area=_boom)
    assert dlg.area_spin.value() > 0
    dlg.deleteLater()


def test_read_output_fills_energy_and_atoms(dialog, tmp_path):
    path = tmp_path / "bulk.out"
    path.write_text(BULK_OUT, encoding="utf-8")
    assert dialog.read_output(str(path), dialog.bulk_edit, dialog.bulk_energy, dialog.bulk_atoms)
    assert float(dialog.bulk_energy.text()) == pytest.approx(-10.0)
    assert dialog.bulk_atoms.value() == 1
    assert dialog.bulk_edit.text() == "bulk.out"


def test_read_output_reports_an_unconverged_file(dialog, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    seen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: seen.append(a))
    path = tmp_path / "bad.out"
    path.write_text("nothing useful", encoding="utf-8")
    assert not dialog.read_output(str(path), dialog.bulk_edit, dialog.bulk_energy, dialog.bulk_atoms)
    assert seen


def test_read_output_handles_a_missing_file(dialog, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    assert not dialog.read_output(
        str(tmp_path / "nope.out"), dialog.bulk_edit, dialog.bulk_energy, dialog.bulk_atoms
    )


def test_calculate_end_to_end(dialog, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    bulk = tmp_path / "bulk.out"
    bulk.write_text(BULK_OUT, encoding="utf-8")
    slab = tmp_path / "slab.out"
    slab.write_text(SLAB_OUT, encoding="utf-8")

    dialog.read_output(str(bulk), dialog.bulk_edit, dialog.bulk_energy, dialog.bulk_atoms)
    dialog.read_output(str(slab), dialog.slab_edit, dialog.slab_energy, dialog.slab_atoms)
    dialog.calculate()

    text = dialog.result.toPlainText()
    assert "E_surf" in text
    # (-39 - 4*(-10)) Ry over 2*2 A^2 = 13.6057/4 eV/A^2
    assert "3.401423" in text


def test_calculate_needs_both_energies(dialog):
    dialog.calculate()
    assert "type the two total energies" in dialog.result.toPlainText()


def test_calculate_reports_a_bad_area(dialog):
    dialog.bulk_energy.setText("-10.0")
    dialog.slab_energy.setText("-39.0")
    dialog.area_spin.setValue(dialog.area_spin.minimum())
    dialog.bulk_atoms.setValue(1)
    dialog.slab_atoms.setValue(4)
    dialog.calculate()
    assert "E_surf" in dialog.result.toPlainText()
