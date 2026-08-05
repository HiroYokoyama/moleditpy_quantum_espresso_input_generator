import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qe_input_generator import cell_model as cm  # noqa: E402
from qe_input_generator import pseudos, writer  # noqa: E402


# -- UPF discovery ---------------------------------------------------------


@pytest.mark.parametrize(
    "filename,element",
    [
        ("Si.UPF", "Si"),
        ("Si.pbe-n-kjpaw_psl.1.0.0.UPF", "Si"),
        ("si_pbe_v1.4.uspp.F.UPF", "Si"),
        ("Fe_ONCV_PBE-1.0.upf", "Fe"),
        ("C.pz-vbc.UPF", "C"),
        ("Ca.pbe-spn-kjpaw_psl.1.0.0.UPF", "Ca"),
        ("O.UPF", "O"),
    ],
)
def test_element_of(filename, element):
    assert pseudos.element_of(filename) == element


def test_element_of_rejects_junk():
    assert pseudos.element_of("1234.UPF") is None


def test_element_token_does_not_confuse_c_and_ca():
    assert pseudos.element_of("C.pbe.UPF") == "C"
    assert pseudos.element_of("Ca.pbe.UPF") == "Ca"


@pytest.fixture
def upf_folder(tmp_path):
    for name in (
        "Si.pbe-n-kjpaw_psl.1.0.0.UPF",
        "Si.UPF",
        "O.pbe-n-kjpaw_psl.1.0.0.UPF",
        "readme.txt",
        "Fe_ONCV_PBE-1.0.upf",
    ):
        (tmp_path / name).write_text("dummy", encoding="utf-8")
    return tmp_path


def test_scan_folder_groups_by_element(upf_folder):
    found = pseudos.scan_folder(str(upf_folder))
    assert set(found) == {"Si", "O", "Fe"}
    assert len(found["Si"]) == 2


def test_scan_folder_ignores_non_upf(upf_folder):
    assert "Readme" not in pseudos.scan_folder(str(upf_folder))


def test_scan_folder_handles_a_missing_directory(tmp_path):
    assert pseudos.scan_folder(str(tmp_path / "nope")) == {}
    assert pseudos.scan_folder("") == {}


def test_match_elements_prefers_the_shortest_name(upf_folder):
    chosen, missing = pseudos.match_elements(["Si"], str(upf_folder))
    assert chosen == {"Si": "Si.UPF"}
    assert missing == []


def test_match_elements_reports_missing(upf_folder):
    chosen, missing = pseudos.match_elements(["Si", "Cu"], str(upf_folder))
    assert "Si" in chosen
    assert missing == ["Cu"]


def test_match_elements_is_case_insensitive(upf_folder):
    chosen, _ = pseudos.match_elements(["si", "fe"], str(upf_folder))
    assert set(chosen) == {"Si", "Fe"}


def test_copy_into(upf_folder, tmp_path):
    destination = tmp_path / "pseudo_dir"
    chosen, _ = pseudos.match_elements(["Si", "O"], str(upf_folder))
    copied = pseudos.copy_into(chosen, str(upf_folder), str(destination))
    assert sorted(copied) == sorted(chosen.values())
    for name in chosen.values():
        assert (destination / name).exists()


def test_copy_into_creates_the_destination(upf_folder, tmp_path):
    destination = tmp_path / "a" / "b"
    chosen, _ = pseudos.match_elements(["Si"], str(upf_folder))
    pseudos.copy_into(chosen, str(upf_folder), str(destination))
    assert destination.is_dir()


def test_copy_into_skips_same_folder(upf_folder):
    chosen, _ = pseudos.match_elements(["Si"], str(upf_folder))
    assert pseudos.copy_into(chosen, str(upf_folder), str(upf_folder)) == []


def test_copy_into_rejects_a_missing_source(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        pseudos.copy_into({"Si": "Si.UPF"}, str(tmp_path / "nope"), str(tmp_path))


def test_copy_into_nothing_is_a_no_op(tmp_path):
    assert pseudos.copy_into({}, str(tmp_path), str(tmp_path)) == []


def test_resolved_filenames_win_over_the_pattern():
    cell = cm.cell_from_molecule(["Si", "O"], [[0, 0, 0], [1.6, 0, 0]], padding=4.0)
    text = writer.build_input(cell, {"pseudo_files": {"Si": "Si_found_on_disk.UPF"}})
    assert "Si_found_on_disk.UPF" in text
    assert "O.UPF" in text  # O falls back to the pattern
