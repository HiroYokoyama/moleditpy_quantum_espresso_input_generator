import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qe_input_generator import cell_model as cm  # noqa: E402
from qe_input_generator import writer  # noqa: E402


@pytest.fixture
def molecule_cell():
    return cm.cell_from_molecule(
        ["O", "H", "H"],
        [[0.0, 0.0, 0.0], [0.96, 0.0, 0.0], [-0.24, 0.93, 0.0]],
        padding=6.0,
    )


@pytest.fixture
def bulk_cell():
    lengths, angles = (4.0, 4.0, 4.0), (90.0, 90.0, 90.0)
    lattice = cm.cell_vectors(lengths, angles)
    atom = cm.CellAtom("Cu1", "Cu", np.zeros(3), np.zeros(3))
    return cm.Cell("sc", lengths, angles, lattice, (atom,), source="cif")


@pytest.fixture
def slab_cell():
    """A slab as it arrives from the Slab Builder: a CIF with a vacuum layer."""
    lengths, angles = (4.0, 4.0, 20.0), (90.0, 90.0, 90.0)
    lattice = cm.cell_vectors(lengths, angles)
    atoms = tuple(
        cm.CellAtom(
            f"Cu{index + 1}",
            "Cu",
            np.array([0.0, 0.0, height / 20.0]),
            np.array([0.0, 0.0, height]),
        )
        for index, height in enumerate((0.0, 2.0, 4.0))
    )
    return cm.Cell("slab", lengths, angles, lattice, atoms, source="cif")


def joined(messages):
    return " | ".join(messages)


# -- Quantum ESPRESSO -------------------------------------------------------


def test_no_warnings_for_a_sane_bulk_run(bulk_cell):
    assert writer.validate(bulk_cell, {"kmesh": [8, 8, 8]}) == []


def test_molecule_with_a_dense_mesh_is_flagged(molecule_cell):
    assert "gamma" in joined(writer.validate(molecule_cell, {"kmesh": [4, 4, 4]}))


def test_slab_sampled_through_the_vacuum(slab_cell):
    messages = writer.validate(
        slab_cell, {"kmesh": [6, 6, 6], "slab_kpoints_c1": False}
    )
    assert "vacuum direction" in joined(messages)


def test_slab_rule_silences_the_warning(slab_cell):
    messages = writer.validate(slab_cell, {"kmesh": [6, 6, 6], "slab_kpoints_c1": True})
    assert "vacuum direction" not in joined(messages)


def test_slab_kpoint_rule_reaches_the_input(slab_cell):
    text = writer.build_input(slab_cell, {"kmesh": [6, 6, 6]})
    assert "6 6 1" in text


def test_slab_kpoint_rule_zeroes_the_third_shift(slab_cell):
    text = writer.build_input(slab_cell, {"kmesh": [6, 6, 6], "kshift": [1, 1, 1]})
    assert "6 6 1  1 1 0" in text


def test_low_ecutrho_ratio(bulk_cell):
    messages = writer.validate(
        bulk_cell, {"kmesh": [8, 8, 8], "ecutrho_auto": False, "ecutrho": 100.0, "ecutwfc": 60.0}
    )
    assert "ecutrho" in joined(messages)


def test_low_ecutwfc(bulk_cell):
    assert "ecutwfc" in joined(writer.validate(bulk_cell, {"kmesh": [8, 8, 8], "ecutwfc": 20.0}))


def test_nscf_reminds_about_the_charge_density(bulk_cell):
    messages = writer.validate(bulk_cell, {"kmesh": [8, 8, 8], "calculation": "nscf"})
    assert "previous scf" in joined(messages)


def test_vc_relax_pulay(bulk_cell):
    messages = writer.validate(
        bulk_cell, {"kmesh": [8, 8, 8], "calculation": "vc-relax", "ecutwfc": 40.0}
    )
    assert "Pulay" in joined(messages)


def test_fixed_occupations_on_a_slab(slab_cell):
    messages = writer.validate(slab_cell, {"kmesh": [6, 6, 1], "occupations": "fixed"})
    assert "Fixed occupations" in joined(messages)


def test_tetrahedra_outside_nscf(bulk_cell):
    messages = writer.validate(bulk_cell, {"kmesh": [8, 8, 8], "occupations": "tetrahedra"})
    assert "tetrahedron occupations" in joined(messages)


def test_charged_molecule_suggests_an_isolated_correction(molecule_cell):
    messages = writer.validate(
        molecule_cell, {"kpoint_mode": "Gamma point only", "tot_charge": -1.0}
    )
    assert "makov-payne" in joined(messages)


def test_missing_pseudo_is_reported(bulk_cell):
    messages = writer.validate(
        bulk_cell, {"kmesh": [8, 8, 8], "pseudo_files": {"Fe": "Fe.UPF"}}
    )
    assert "No pseudopotential file" in joined(messages)


def test_resolved_pseudo_is_quiet(bulk_cell):
    messages = writer.validate(
        bulk_cell, {"kmesh": [8, 8, 8], "pseudo_files": {"Cu": "Cu.UPF"}}
    )
    assert "No pseudopotential file" not in joined(messages)


def test_nbnd_and_charge_reach_the_input(bulk_cell):
    text = writer.build_input(bulk_cell, {"nbnd": 40, "tot_charge": -1.0})
    assert "nbnd" in text
    assert "tot_charge" in text


def test_nbnd_zero_is_omitted(bulk_cell):
    assert "nbnd" not in writer.build_input(bulk_cell, {"nbnd": 0})
