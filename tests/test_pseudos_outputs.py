import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qe_input_generator import cell_model as cm  # noqa: E402
from qe_input_generator import outputs, pseudos, writer  # noqa: E402


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


# -- pw.x output parsing ---------------------------------------------------


SCF_OUTPUT = """
     Program PWSCF v.7.2 starts
     number of atoms/cell      =            2
     total energy              =     -22.60000000 Ry
     total energy              =     -22.65000000 Ry
!    total energy              =     -22.65432100 Ry
     estimated scf accuracy    <       1.0E-09 Ry
     JOB DONE.
"""


def test_parse_total_energy_takes_the_converged_value():
    assert outputs.parse_total_energy(SCF_OUTPUT) == pytest.approx(-22.654321)


def test_parse_total_energy_ignores_unconverged_lines():
    text = SCF_OUTPUT.replace("!    total energy              =     -22.65432100 Ry", "")
    with pytest.raises(ValueError, match="No converged total energy"):
        outputs.parse_total_energy(text)


def test_parse_total_energy_accepts_a_relax_final_energy():
    text = "Final energy   =     -33.12345000 Ry\n"
    assert outputs.parse_total_energy(text) == pytest.approx(-33.12345)


def test_parse_total_energy_takes_the_last_of_several():
    text = SCF_OUTPUT + "!    total energy              =     -30.00000000 Ry\n"
    assert outputs.parse_total_energy(text) == pytest.approx(-30.0)


def test_parse_atom_count():
    assert outputs.parse_atom_count(SCF_OUTPUT) == 2


def test_parse_atom_count_missing():
    with pytest.raises(ValueError, match="number of atoms"):
        outputs.parse_atom_count("nothing here")


# -- surface energy --------------------------------------------------------


def test_surface_energy_is_zero_for_an_unstrained_cut():
    """A slab made of N bulk formula units with no relaxation has E_surf = 0."""
    assert outputs.surface_energy(-40.0, 4, -10.0, 1, 10.0) == pytest.approx(0.0)


def test_surface_energy_known_value():
    # slab 1 Ry above the bulk reference, 2 A^2 of surface over two faces
    value = outputs.surface_energy(-39.0, 4, -10.0, 1, 2.0)
    assert value == pytest.approx(outputs.RY_TO_EV / 4.0)


def test_surface_energy_scales_with_area():
    small = outputs.surface_energy(-39.0, 4, -10.0, 1, 2.0)
    large = outputs.surface_energy(-39.0, 4, -10.0, 1, 4.0)
    assert small == pytest.approx(2.0 * large)


def test_surface_energy_rejects_bad_input():
    with pytest.raises(ValueError):
        outputs.surface_energy(-1.0, 0, -1.0, 1, 1.0)
    with pytest.raises(ValueError):
        outputs.surface_energy(-1.0, 1, -1.0, 0, 1.0)
    with pytest.raises(ValueError):
        outputs.surface_energy(-1.0, 1, -1.0, 1, 0.0)


def test_unit_conversion():
    assert outputs.surface_energy_j_per_m2(1.0) == pytest.approx(16.0217663, rel=1e-6)


def test_describe_reports_both_units():
    text = outputs.describe(-39.0, 4, -10.0, 1, 2.0)
    assert "eV/A^2" in text
    assert "J/m^2" in text
    assert "E_bulk per atom" in text
