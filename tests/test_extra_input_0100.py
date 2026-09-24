"""Free-form keywords for every namelist and extra cards, added in 0.10.0."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qe_input_generator import cell_model as cm  # noqa: E402
from qe_input_generator import writer  # noqa: E402
from qe_input_generator.main_dialog import QeInputDialog  # noqa: E402

from shared_fixtures import CUBIC_CIF  # noqa: E402


@pytest.fixture
def cell():
    return cm.parse_cif(CUBIC_CIF)


def _block(text, name):
    body = text.split(f"&{name}\n")[1].split("\n/")[0]
    return {line.split("=")[0].strip(): line.split("=", 1)[1].strip() for line in body.splitlines()}


def test_keywords_reach_every_namelist(cell):
    extras = {
        "CONTROL": "max_seconds = 86000",
        "SYSTEM": "nbnd = 40",
        "ELECTRONS": "mixing_mode = 'local-TF'",
        "IONS": "upscale = 100",
        "CELL": "cell_dofree = 'ibrav'",
    }
    text = writer.build_input(cell, {"calculation": "vc-relax", "extra_namelists": extras})
    assert _block(text, "CONTROL")["max_seconds"] == "86000"
    assert _block(text, "SYSTEM")["nbnd"] == "40"
    assert _block(text, "ELECTRONS")["mixing_mode"] == "'local-TF'"
    assert _block(text, "IONS")["upscale"] == "100"
    assert _block(text, "CELL")["cell_dofree"] == "'ibrav'"


def test_a_user_keyword_replaces_the_generated_one(cell):
    """pw.x rejects a keyword given twice; the user's value wins in place."""
    text = writer.build_input(cell, {"extra_namelists": {"ELECTRONS": "Conv_Thr = 1d-10"}})
    body = text.split("&ELECTRONS\n")[1].split("\n/")[0]
    assert body.lower().count("conv_thr") == 1
    assert _block(text, "ELECTRONS")["conv_thr"] == "1d-10"


def test_indexed_keywords_match_regardless_of_spacing(cell):
    settings = {
        "nspin": True,
        "extra_namelists": {"SYSTEM": "starting_magnetization( 1 ) = 0.8\nHubbard_U(1) = 4.0"},
    }
    entries = _block(writer.build_input(cell, settings), "SYSTEM")
    assert entries["starting_magnetization(1)"] == "0.8"
    assert entries["Hubbard_U(1)"] == "4.0"


def test_parser_handles_commas_comments_and_quotes():
    pairs, errors = writer.parse_keywords(
        "&SYSTEM\nnbnd = 40, ecutfock = 100 ! hybrid\ntitle = 'a, b ! c'\ncelldm(1) = 1.0, 2.0\n/"
    )
    assert pairs == [
        ("nbnd", "40"),
        ("ecutfock", "100"),
        ("title", "'a, b ! c'"),
        ("celldm(1)", "1.0, 2.0"),
    ]
    assert errors == []


def test_unreadable_lines_are_reported_and_left_out(cell):
    settings = {"extra_namelists": {"SYSTEM": "nbnd 40\nx = 'open"}}
    assert "nbnd 40" not in writer.build_input(cell, settings)
    messages = writer.validate(cell, settings)
    assert sum("Additional &SYSTEM" in message for message in messages) == 2


def test_ions_keywords_for_scf_are_flagged_not_written(cell):
    settings = {"extra_namelists": {"IONS": "upscale = 100"}}
    assert "&IONS" not in writer.build_input(cell, settings)
    assert any("&IONS" in message for message in writer.validate(cell, settings))


def test_the_old_system_field_still_works(cell):
    assert _block(writer.build_input(cell, {"extra_system": "nbnd = 40"}), "SYSTEM")["nbnd"] == "40"


def test_extra_cards_are_appended(cell):
    cards = "HUBBARD ortho-atomic\n  U Na-3s 1.0\n"
    text = writer.build_input(cell, {"extra_cards": cards})
    assert text.index("HUBBARD ortho-atomic") > text.index("K_POINTS")
    assert "  U Na-3s 1.0" in text


def test_a_user_k_path_replaces_the_mesh_and_silences_the_bands_warning(cell):
    path = "K_POINTS crystal_b\n  2\n  0.0 0.0 0.0 20\n  0.5 0.0 0.0 1"
    settings = {"calculation": "bands", "extra_cards": path}
    text = writer.build_input(cell, settings)
    assert text.count("K_POINTS") == 1
    assert "K_POINTS crystal_b" in text and "K_POINTS automatic" not in text
    assert not any("crystal_b" in message for message in writer.validate(cell, settings))


def test_card_problems_are_flagged(cell):
    settings = {"extra_cards": "U Fe-3d 4.0\nHUBBARD atomic\nHUBBARD atomic\nATOMIC_SPECIES\n  X 1 X.UPF"}
    messages = " ".join(writer.validate(cell, settings))
    assert "belongs to no card" in messages
    assert "HUBBARD is given more than once" in messages
    assert "ATOMIC_SPECIES card replaces" in messages


def test_without_extras_the_output_is_unchanged(cell):
    base = writer.build_input(cell)
    assert writer.build_input(cell, {"extra_namelists": {}, "extra_cards": ""}) == base


@pytest.fixture
def dialog(qapp):
    dlg = QeInputDialog(persistent_settings=writer.default_settings())
    yield dlg
    dlg.deleteLater()


def test_dialog_round_trips_every_editor(dialog):
    dialog.extra_edits["ELECTRONS"].setPlainText("mixing_ndim = 12")
    dialog.extra_cards_edit.setPlainText("HUBBARD atomic\n  U Na-3s 1.0")
    settings = dialog.read_settings()
    assert settings["extra_namelists"] == {"ELECTRONS": "mixing_ndim = 12"}
    assert settings["extra_cards"].startswith("HUBBARD")
    assert settings["extra_system"] == ""


def test_dialog_moves_old_system_extras_into_the_system_editor(dialog):
    dialog.apply_settings({**writer.default_settings(), "extra_system": "nbnd = 40"})
    assert dialog.extra_edits["SYSTEM"].toPlainText() == "nbnd = 40"
    settings = dialog.read_settings()
    assert settings["extra_namelists"]["SYSTEM"] == "nbnd = 40"
    assert _block(writer.build_input(cm.parse_cif(CUBIC_CIF), settings), "SYSTEM")["nbnd"] == "40"
