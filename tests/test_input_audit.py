"""Regressions for the 0.11.0 input audit."""

import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from qe_input_generator import cell_model as cm, writer
from qe_input_generator.main_dialog import QeInputDialog, QFileDialog, QMessageBox
from shared_fixtures import CUBIC_CIF, _FakeMol


def test_multi_index_keywords_keep_commas():
    pairs, errors = writer.parse_keywords("starting_ns_eigenvalue(1, 2, 3) = 0.5, nbnd = 20")
    assert pairs == [("starting_ns_eigenvalue(1, 2, 3)", "0.5"), ("nbnd", "20")]
    assert not errors


@pytest.mark.parametrize("text", [
    "title = \"it's a test\"", "title = 'a \"quoted\" test'",
    "title = 'O''Brien, ! test' ! ignored '",
])
def test_other_quote_style_does_not_close_a_string(text):
    pairs, errors = writer.parse_keywords(text)
    assert len(pairs) == 1
    assert not errors


def test_invalid_line_cannot_append_to_previous_line():
    pairs, errors = writer.parse_keywords("nbnd = 20\nbad, fragment")
    assert pairs == [("nbnd", "20")]
    assert len(errors) == 2


@pytest.mark.parametrize("value", [1.234567891e-9, 0.1234567891234, 123456789.12])
def test_numeric_precision(value):
    assert float(writer._fortran(value).replace("d", "e")) == pytest.approx(value, rel=1e-14)


def test_legacy_upf_default_is_preserved():
    cell = cm.parse_cif(CUBIC_CIF)
    assert "input_dft" not in writer.build_input(cell, {"functional": "POTCAR/UPF default"})
    assert writer.FUNCTIONALS[0] == "UPF default"


def test_retired_ppcg_is_rejected():
    with pytest.raises(ValueError, match="PPCG"):
        writer.build_input(cm.parse_cif(CUBIC_CIF), {"diagonalization": "ppcg"})
    assert "rmm-paro" in writer.DIAGONALIZATION


def test_tetrahedra_require_uniform_mesh_and_honor_extra_override():
    cell = cm.parse_cif(CUBIC_CIF)
    with pytest.raises(ValueError, match="uniform"):
        writer.build_input(cell, {"kpoint_mode": "Gamma point only", "occupations": "tetrahedra"})
    text = writer.build_input(cell, {
        "kpoint_mode": "Gamma point only", "occupations": "tetrahedra",
        "extra_system": "occupations = 'fixed'",
    })
    assert "'fixed'" in text


def test_invalid_extra_input_blocks_save_then_recovers(qapp, monkeypatch):
    mol = _FakeMol(["O", "H", "H"], [[0, 0, 0], [1, 0, 0], [0, 1, 0]])
    dialog = QeInputDialog(get_molecule=lambda: mol)
    try:
        dialog.persistent_settings["extra_namelists"] = {"SYSTEM": "nbnd 20"}
        dialog.apply_settings(dialog.persistent_settings)
        assert "Invalid input" in dialog.preview.toPlainText()
        assert not dialog.save_button.isEnabled()
        picker, warning = Mock(), Mock()
        monkeypatch.setattr(QFileDialog, "getSaveFileName", picker)
        monkeypatch.setattr(QMessageBox, "warning", warning)
        dialog.save_input()
        warning.assert_called_once()
        picker.assert_not_called()
        dialog.apply_settings({"extra_namelists": {"SYSTEM": "nbnd = 20"}})
        assert dialog.save_button.isEnabled()
    finally:
        dialog.close()


@pytest.mark.parametrize("filename", ["__init__.py", "main_dialog.py", "writer.py"])
def test_main_code_imports_are_module_scope(filename):
    path = Path(__file__).resolve().parents[1] / "qe_input_generator" / filename
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert not any(isinstance(child, (ast.Import, ast.ImportFrom)) for child in ast.walk(node))
