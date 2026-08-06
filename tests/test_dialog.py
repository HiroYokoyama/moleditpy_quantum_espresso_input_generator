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


def test_dialog_writes_assume_isolated(dialog):
    dialog.isolated_combo.setCurrentText("martyna-tuckerman")
    assert "assume_isolated = 'martyna-tuckerman'" in dialog.preview.toPlainText()
    assert dialog.persistent_settings["assume_isolated"] == "martyna-tuckerman"


def test_dialog_omits_assume_isolated_by_default(dialog):
    assert "assume_isolated" not in dialog.preview.toPlainText()


def test_the_dialog_accepts_a_dropped_cif(dialog, tmp_path):
    """The drop works anywhere on the window as well as on the panel itself."""
    from test_structure_panel import _FakeDropEvent, _FakeMime

    path = tmp_path / "dropped.cif"
    path.write_text("data_x\n", encoding="utf-8")
    assert dialog.acceptDrops()
    event = _FakeDropEvent(_FakeMime([str(path)]))
    dialog.dropEvent(event)
    assert event.accepted
    assert dialog.structure_panel.cif_edit.text() == str(path)
    assert dialog.structure_panel.source_combo.currentText() == "CIF file"


# -- drag and drop refusal --------------------------------------------------


def test_a_drag_without_a_cif_is_refused_by_the_dialog(dialog):
    from test_structure_panel import _FakeDropEvent, _FakeMime

    event = _FakeDropEvent(_FakeMime(["/tmp/notes.txt"]))
    dialog.dragEnterEvent(event)
    assert event.ignored and not event.accepted
    dialog.dropEvent(event)
    assert not event.accepted


def test_a_drag_move_follows_the_same_rule(dialog):
    from test_structure_panel import _FakeDropEvent, _FakeMime

    event = _FakeDropEvent(_FakeMime(["/tmp/x.cif"]))
    dialog.dragMoveEvent(event)
    assert event.accepted


# -- automatic charge -------------------------------------------------------


class _ChargedAtom:
    def __init__(self, charge=0, radicals=0):
        self._charge, self._radicals = charge, radicals

    def GetSymbol(self):
        return "O"

    def HasProp(self, name):
        return False

    def GetProp(self, name):
        return ""

    def GetFormalCharge(self):
        return self._charge

    def GetNumRadicalElectrons(self):
        return self._radicals


class _ChargedMol:
    def __init__(self, atoms, coords):
        self._atoms, self._coords = atoms, coords

    def GetNumAtoms(self):
        return len(self._atoms)

    def GetAtomWithIdx(self, index):
        return self._atoms[index]

    def GetConformer(self):
        from test_cell_model import _FakeConformer

        return _FakeConformer(self._coords)


def test_auto_charge_reads_the_molecule(qapp):
    """A charged molecule should not need tot_charge typed in twice."""
    mol = _ChargedMol([_ChargedAtom(charge=-1)], [[0.0, 0.0, 0.0]])
    dlg = QeInputDialog(persistent_settings=writer.default_settings(), get_molecule=lambda: mol)
    dlg.auto_charge_check.setChecked(True)
    assert dlg.charge_spin.value() == pytest.approx(-1.0)
    dlg.deleteLater()


def test_auto_charge_turns_on_spin_for_an_open_shell(qapp):
    mol = _ChargedMol([_ChargedAtom(radicals=1)], [[0.0, 0.0, 0.0]])
    dlg = QeInputDialog(persistent_settings=writer.default_settings(), get_molecule=lambda: mol)
    dlg.auto_charge_check.setChecked(True)
    assert dlg.nspin_check.isChecked()
    dlg.deleteLater()


def test_auto_charge_ignores_a_molecule_it_cannot_read(dialog):
    dialog._get_molecule = lambda: None
    dialog.auto_charge_check.setChecked(True)  # must not raise


# -- pseudopotential folder -------------------------------------------------


def test_scanning_without_a_structure_says_so(qapp):
    dlg = QeInputDialog(persistent_settings=writer.default_settings(), get_molecule=lambda: None)
    dlg.scan_pseudo_folder()
    assert "structure" in dlg.pseudo_status_label.text().lower()
    dlg.deleteLater()


def test_scanning_an_empty_path_asks_for_a_folder(dialog):
    dialog.pseudo_search_edit.setText("")
    dialog.scan_pseudo_folder()
    assert "folder" in dialog.pseudo_status_label.text().lower()


def test_scanning_a_folder_matches_the_upf_files(dialog, tmp_path):
    (tmp_path / "O.UPF").write_text("", encoding="utf-8")
    dialog.pseudo_search_edit.setText(str(tmp_path))
    dialog.scan_pseudo_folder()
    assert dialog._pseudo_files.get("O") == "O.UPF"
    assert "O -> O.UPF" in dialog.pseudo_status_label.text()
    assert "O.UPF" in dialog.preview.toPlainText()


def test_scanning_a_folder_with_nothing_useful(dialog, tmp_path):
    (tmp_path / "readme.txt").write_text("", encoding="utf-8")
    dialog.pseudo_search_edit.setText(str(tmp_path))
    dialog.scan_pseudo_folder()
    assert "No UPF file matched" in dialog.pseudo_status_label.text()


def test_copying_pseudos_puts_them_in_the_pseudo_dir(dialog, tmp_path, monkeypatch):
    source = tmp_path / "src"
    source.mkdir()
    (source / "O.UPF").write_text("data", encoding="utf-8")
    destination = tmp_path / "pseudo"
    dialog.pseudo_search_edit.setText(str(source))
    dialog.pseudo_dir_edit.setText(str(destination))
    dialog.scan_pseudo_folder()

    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    dialog.copy_pseudos()
    assert (destination / "O.UPF").is_file()


def test_copying_without_a_scan_says_to_scan_first(dialog, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    seen = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: seen.append(a))
    dialog._pseudo_files = {}
    dialog.copy_pseudos()
    assert seen


def test_copying_from_a_missing_folder_reports_the_error(dialog, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    seen = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: seen.append(a))
    dialog._pseudo_files = {"O": "O.UPF"}
    dialog.pseudo_search_edit.setText(str(tmp_path / "nowhere"))
    dialog.copy_pseudos()
    assert seen


def test_saving_to_an_unwritable_path_reports_the_error(dialog, tmp_path, monkeypatch):
    """A failed write must say so, not look like it worked."""
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    target = tmp_path / "missing" / "pw.in"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    seen = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: seen.append(a))
    dialog.save_input()
    assert seen


def test_saving_writes_the_input(dialog, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    target = tmp_path / "pw.in"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    dialog.save_input()
    assert "&CONTROL" in target.read_text(encoding="utf-8")


def test_cancelling_the_save_writes_nothing(dialog, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    dialog.save_input()  # must not raise


def test_saving_without_a_structure_warns(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    seen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: seen.append(a))
    dlg = QeInputDialog(persistent_settings=writer.default_settings(), get_molecule=lambda: None)
    dlg.save_input()
    assert seen
    dlg.deleteLater()


def test_copying_the_preview_reaches_the_clipboard(dialog, qapp):
    dialog.copy_preview()
    from PyQt6.QtWidgets import QApplication

    assert "&CONTROL" in QApplication.clipboard().text()


def test_the_box_is_drawn_as_soon_as_the_dialog_opens(qapp):
    """Opening the generator should show the cell, not an empty viewer."""
    pytest.importorskip("rdkit")
    from test_structure_panel import _RecordingContext

    mol = _FakeMol(["O", "H", "H"], [[0, 0, 0], [0.96, 0, 0], [-0.24, 0.93, 0]])
    context = _RecordingContext()
    dlg = QeInputDialog(
        persistent_settings=writer.default_settings(),
        get_molecule=lambda: mol,
        context=context,
    )
    assert context.current_molecule is not None
    assert len(context.plotter.lines) == 12
    dlg.deleteLater()
