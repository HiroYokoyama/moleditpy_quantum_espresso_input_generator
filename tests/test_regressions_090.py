"""Regressions fixed in 0.9.0; each test fails on 0.8.3."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qe_input_generator import cell_model as cm  # noqa: E402
from qe_input_generator import writer  # noqa: E402
from qe_input_generator.main_dialog import QeInputDialog  # noqa: E402
from qe_input_generator.structure_panel import SOURCE_CIF  # noqa: E402

from shared_fixtures import CUBIC_CIF, _FakeMol  # noqa: E402


def test_vc_md_uses_beeman():
    """pw.x stops at once when a vc-md run asks for verlet."""
    assert "'beeman'" in writer.build_ions({"calculation": "vc-md"})


def test_md_keeps_verlet():
    assert "'verlet'" in writer.build_ions({"calculation": "md"})


def test_bands_run_warns_about_the_k_path():
    cell = cm.parse_cif(CUBIC_CIF)
    assert any("crystal_b" in m for m in writer.validate(cell, {"calculation": "bands"}))


class _ChargedAtom:
    def __init__(self, symbol, charge):
        self.symbol, self.charge = symbol, charge

    def GetSymbol(self):
        return self.symbol

    def HasProp(self, name):
        return False

    def GetFormalCharge(self):
        return self.charge

    def GetNumRadicalElectrons(self):
        return 0


class _Ammonium(_FakeMol):
    def __init__(self):
        super().__init__(
            ["N", "H", "H", "H", "H"],
            [[0, 0, 0], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0]],
        )
        self._atoms = [_ChargedAtom("N", 1)] + [_ChargedAtom("H", 0)] * 4


@pytest.fixture
def dialog(qapp, tmp_path):
    cif = tmp_path / "bulk.cif"
    cif.write_text(CUBIC_CIF, encoding="utf-8")
    mol = _Ammonium()
    dlg = QeInputDialog(persistent_settings=writer.default_settings(), get_molecule=lambda: mol)
    dlg.auto_charge_check.setChecked(True)
    yield dlg, str(cif)
    dlg.deleteLater()


def test_auto_charge_reads_the_boxed_molecule(dialog):
    dlg, _ = dialog
    dlg.update_preview()
    assert dlg.charge_spin.value() == pytest.approx(1.0)


def test_auto_charge_ignores_the_molecule_for_a_cif(dialog):
    """The open molecule's charge does not belong to a crystal read from a CIF."""
    dlg, path = dialog
    dlg.charge_spin.setValue(0.0)
    dlg.structure_panel.source_combo.setCurrentText(SOURCE_CIF)
    dlg.structure_panel.cif_edit.setText(path)
    dlg.update_preview()
    assert dlg.charge_spin.value() == pytest.approx(0.0)
    assert "tot_charge" not in dlg.preview.toPlainText()
