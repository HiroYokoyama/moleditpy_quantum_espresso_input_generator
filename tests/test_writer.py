import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qe_input_generator import cell_model as cm  # noqa: E402
from qe_input_generator import writer  # noqa: E402


@pytest.fixture
def water_cell():
    return cm.cell_from_molecule(
        ["O", "H", "H"],
        [[0.0, 0.0, 0.0], [0.96, 0.0, 0.0], [-0.24, 0.93, 0.0]],
        padding=5.0,
        name="water",
    )


def namelist(text, name):
    match = re.search(rf"&{name}\n(.*?)\n/", text, re.S)
    assert match, f"&{name} block missing"
    entries = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition("=")
        entries[key.strip()] = value.strip()
    return entries


def card(text, name):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(name):
            body = []
            for following in lines[index + 1 :]:
                if not following.startswith("  "):
                    break
                body.append(following.strip())
            return line, body
    raise AssertionError(f"card {name} missing")


# -- &CONTROL --------------------------------------------------------------


def test_control_defaults(water_cell):
    entries = namelist(writer.build_input(water_cell), "CONTROL")
    assert entries["calculation"] == "'scf'"
    assert entries["prefix"] == "'pwscf'"
    assert entries["outdir"] == "'./out'"
    assert entries["pseudo_dir"] == "'./pseudo'"
    assert entries["tprnfor"] == ".true."
    assert "nstep" not in entries


def test_control_relax_adds_convergence(water_cell):
    entries = namelist(writer.build_input(water_cell, {"calculation": "relax"}), "CONTROL")
    assert entries["nstep"] == "100"
    assert entries["etot_conv_thr"] == "1.0000d-05"
    assert entries["forc_conv_thr"] == "1.0000d-04"


def test_control_md_adds_timestep(water_cell):
    entries = namelist(writer.build_input(water_cell, {"calculation": "md"}), "CONTROL")
    assert entries["dt"] == "20"


def test_control_title_is_flattened(water_cell):
    entries = namelist(writer.build_input(water_cell, {"title": "a\nb"}), "CONTROL")
    assert entries["title"] == "'a b'"


def test_control_flags_can_be_disabled(water_cell):
    entries = namelist(
        writer.build_input(water_cell, {"tprnfor": False, "tstress": False}), "CONTROL"
    )
    assert entries["tprnfor"] == ".false."
    assert entries["tstress"] == ".false."


# -- &SYSTEM ---------------------------------------------------------------


def test_system_counts_atoms_and_types(water_cell):
    entries = namelist(writer.build_input(water_cell), "SYSTEM")
    assert entries["ibrav"] == "0"
    assert entries["nat"] == "3"
    assert entries["ntyp"] == "2"


def test_system_ecutrho_follows_ecutwfc(water_cell):
    entries = namelist(writer.build_input(water_cell, {"ecutwfc": 50.0}), "SYSTEM")
    assert entries["ecutwfc"] == "50"
    assert entries["ecutrho"] == "400"


def test_system_ecutrho_manual(water_cell):
    entries = namelist(
        writer.build_input(water_cell, {"ecutrho_auto": False, "ecutrho": 300.0}), "SYSTEM"
    )
    assert entries["ecutrho"] == "300"


def test_system_smearing_keywords(water_cell):
    entries = namelist(writer.build_input(water_cell), "SYSTEM")
    assert entries["occupations"] == "'smearing'"
    assert entries["smearing"] == "'mv'"
    assert entries["degauss"] == "0.01"


def test_system_fixed_occupations_drop_smearing(water_cell):
    entries = namelist(writer.build_input(water_cell, {"occupations": "fixed"}), "SYSTEM")
    assert "smearing" not in entries
    assert "degauss" not in entries


def test_system_input_dft_only_when_overridden(water_cell):
    assert "input_dft" not in namelist(writer.build_input(water_cell), "SYSTEM")
    entries = namelist(writer.build_input(water_cell, {"functional": "PBEsol"}), "SYSTEM")
    assert entries["input_dft"] == "'PBEsol'"


def test_system_vdw_correction(water_cell):
    entries = namelist(writer.build_input(water_cell, {"vdw": "grimme-d3"}), "SYSTEM")
    assert entries["vdw_corr"] == "'grimme-d3'"


def test_system_spin_adds_one_magnetization_per_type(water_cell):
    entries = namelist(
        writer.build_input(water_cell, {"nspin": True, "starting_magnetization": 0.3}), "SYSTEM"
    )
    assert entries["nspin"] == "2"
    assert entries["starting_magnetization(1)"] == "0.3"
    assert entries["starting_magnetization(2)"] == "0.3"
    assert "starting_magnetization(3)" not in entries


def test_system_extra_keywords_are_appended(water_cell):
    entries = namelist(writer.build_input(water_cell, {"extra_system": "nbnd = 40"}), "SYSTEM")
    assert entries["nbnd"] == "40"


# -- &ELECTRONS / &IONS / &CELL -------------------------------------------


def test_electrons_defaults(water_cell):
    entries = namelist(writer.build_input(water_cell), "ELECTRONS")
    assert entries["conv_thr"] == "1.0000d-08"
    assert entries["mixing_beta"] == "0.7"
    assert entries["diagonalization"] == "'david'"


def test_ions_block_only_for_moving_atoms(water_cell):
    assert "&IONS" not in writer.build_input(water_cell)
    assert "&IONS" in writer.build_input(water_cell, {"calculation": "relax"})


def test_ions_uses_bfgs_for_relax(water_cell):
    entries = namelist(writer.build_input(water_cell, {"calculation": "relax"}), "IONS")
    assert entries["ion_dynamics"] == "'bfgs'"


def test_ions_uses_verlet_for_md(water_cell):
    entries = namelist(
        writer.build_input(water_cell, {"calculation": "md", "temperature": 450.0}), "IONS"
    )
    assert entries["ion_dynamics"] == "'verlet'"
    assert entries["tempw"] == "450"


def test_cell_block_only_for_variable_cell(water_cell):
    assert "&CELL" not in writer.build_input(water_cell, {"calculation": "relax"})
    entries = namelist(
        writer.build_input(water_cell, {"calculation": "vc-relax", "press": 10.0}), "CELL"
    )
    assert entries["cell_dynamics"] == "'bfgs'"
    assert entries["press"] == "10"


def test_vc_md_uses_parrinello_rahman(water_cell):
    entries = namelist(writer.build_input(water_cell, {"calculation": "vc-md"}), "CELL")
    assert entries["cell_dynamics"] == "'pr'"


# -- cards -----------------------------------------------------------------


def test_atomic_species_lists_mass_and_pseudo(water_cell):
    _, rows = card(writer.build_input(water_cell), "ATOMIC_SPECIES")
    assert len(rows) == 2
    assert rows[0].split() == ["O", "15.9990", "O.UPF"]
    assert rows[1].split()[0] == "H"


def test_atomic_species_honours_the_pattern(water_cell):
    _, rows = card(
        writer.build_input(water_cell, {"pseudo_pattern": "{el}_pbe_v1.4.uspp.F.UPF"}),
        "ATOMIC_SPECIES",
    )
    assert rows[0].split()[2] == "o_pbe_v1.4.uspp.F.UPF"


@pytest.mark.parametrize(
    "pattern,expected",
    [
        ("{El}.UPF", "Si.UPF"),
        ("{el}.upf", "si.upf"),
        ("{EL}.UPF", "SI.UPF"),
        ("{El}.pbe-n-kjpaw_psl.1.0.0.UPF", "Si.pbe-n-kjpaw_psl.1.0.0.UPF"),
    ],
)
def test_pseudo_filename(pattern, expected):
    assert writer.pseudo_filename("si", pattern) == expected


def test_cell_parameters_match_the_lattice(water_cell):
    header, rows = card(writer.build_input(water_cell), "CELL_PARAMETERS")
    assert header.endswith("angstrom")
    for index, row in enumerate(rows):
        assert [float(v) for v in row.split()] == pytest.approx(
            list(water_cell.lattice[index]), abs=1e-9
        )


def test_atomic_positions_crystal_by_default(water_cell):
    header, rows = card(writer.build_input(water_cell), "ATOMIC_POSITIONS")
    assert header.endswith("crystal")
    assert len(rows) == 3
    assert rows[0].split()[0] == "O"
    for row in rows:
        for value in [float(v) for v in row.split()[1:]]:
            assert 0.0 <= value <= 1.0


def test_atomic_positions_angstrom(water_cell):
    header, rows = card(
        writer.build_input(water_cell, {"position_units": "angstrom"}), "ATOMIC_POSITIONS"
    )
    assert header.endswith("angstrom")
    assert [float(v) for v in rows[0].split()[1:]] == pytest.approx(
        list(water_cell.atoms[0].cart), abs=1e-9
    )


def test_atomic_positions_are_species_grouped():
    cell = cm.cell_from_molecule(
        ["H", "O", "H"], [[0, 0, 0], [1.0, 0, 0], [2.0, 0, 0]], padding=3.0
    )
    _, rows = card(writer.build_input(cell), "ATOMIC_POSITIONS")
    assert [row.split()[0] for row in rows] == ["H", "H", "O"]


def test_kpoints_gamma(water_cell):
    text = writer.build_input(water_cell, {"kpoint_mode": "Gamma point only"})
    assert "K_POINTS gamma" in text
    assert "K_POINTS automatic" not in text


def test_kpoints_automatic_mesh(water_cell):
    text = writer.build_input(
        water_cell, {"kmesh": [2, 3, 4], "kshift": [1, 0, 1]}
    )
    header, rows = card(text, "K_POINTS")
    assert header.endswith("automatic")
    assert rows[0].split() == ["2", "3", "4", "1", "0", "1"]


def test_kpoints_spacing_mode(water_cell):
    text = writer.build_input(
        water_cell, {"kpoint_mode": "Automatic (spacing)", "kspacing": 0.5}
    )
    _, rows = card(text, "K_POINTS")
    assert rows[0].split() == ["1", "1", "1", "0", "0", "0"]


# -- assembly --------------------------------------------------------------


def test_input_block_order(water_cell):
    text = writer.build_input(water_cell, {"calculation": "vc-relax"})
    order = [
        text.index(token)
        for token in (
            "&CONTROL",
            "&SYSTEM",
            "&ELECTRONS",
            "&IONS",
            "&CELL",
            "ATOMIC_SPECIES",
            "CELL_PARAMETERS",
            "ATOMIC_POSITIONS",
            "K_POINTS",
        )
    ]
    assert order == sorted(order)


def test_input_ends_with_newline(water_cell):
    assert writer.build_input(water_cell).endswith("\n")


def test_fortran_formatting():
    assert writer._fortran(True) == ".true."
    assert writer._fortran(1e-8) == "1.0000d-08"
    assert writer._fortran(0.7) == "0.7"
    assert writer._fortran(3) == "3"
    assert writer._fortran("scf") == "'scf'"


def test_suggested_filename():
    assert writer.suggested_filename({"prefix": "si", "calculation": "relax"}) == "si.relax.in"
    assert writer.suggested_filename({"prefix": ""}).startswith("pwscf")


def test_default_settings_are_independent_copies():
    first = writer.default_settings()
    first["ecutwfc"] = 1.0
    assert writer.default_settings()["ecutwfc"] == 60.0
