"""Read pw.x output files and derive a surface energy."""

from __future__ import annotations

import re
from typing import Optional

RY_TO_EV = 13.605693122994

_TOTAL_ENERGY = re.compile(r"^!\s+total energy\s*=\s*(-?\d+\.\d+)\s*Ry", re.M)
_FINAL_ENERGY = re.compile(r"Final energy\s*=\s*(-?\d+\.\d+)\s*Ry")
_ATOM_COUNT = re.compile(r"number of atoms/cell\s*=\s*(\d+)")


def parse_total_energy(text: str) -> float:
    """Converged total energy in Ry — the last SCF value in the file.

    pw.x marks converged energies with a leading ``!``; unconverged iterations
    are written without it and are deliberately ignored.
    """
    matches = _TOTAL_ENERGY.findall(text or "")
    if matches:
        return float(matches[-1])
    final = _FINAL_ENERGY.findall(text or "")
    if final:
        return float(final[-1])
    raise ValueError(
        "No converged total energy found. pw.x writes it as a line starting with "
        "'!' — check that the run finished."
    )


def parse_atom_count(text: str) -> int:
    match = _ATOM_COUNT.search(text or "")
    if not match:
        raise ValueError("Could not read 'number of atoms/cell' from the output.")
    return int(match.group(1))


def surface_energy(
    slab_energy_ry: float,
    slab_atoms: int,
    bulk_energy_ry: float,
    bulk_atoms: int,
    area: float,
) -> float:
    """Surface energy in eV/A^2.

    E_surf = (E_slab - N_slab * E_bulk / N_bulk) / (2 A); the factor of two is
    the slab's pair of equivalent faces.
    """
    if bulk_atoms <= 0 or slab_atoms <= 0:
        raise ValueError("Atom counts must be positive.")
    if area <= 0:
        raise ValueError("The surface area must be positive.")
    excess_ry = slab_energy_ry - slab_atoms * bulk_energy_ry / bulk_atoms
    return excess_ry * RY_TO_EV / (2.0 * area)


def surface_energy_j_per_m2(value_ev_per_a2: float) -> float:
    """Convert eV/A^2 to J/m^2 (1 eV/A^2 = 16.0218 J/m^2)."""
    return value_ev_per_a2 * 16.021766339


def describe(
    slab_energy_ry: float,
    slab_atoms: int,
    bulk_energy_ry: float,
    bulk_atoms: int,
    area: float,
) -> str:
    value = surface_energy(slab_energy_ry, slab_atoms, bulk_energy_ry, bulk_atoms, area)
    return (
        f"E_slab   = {slab_energy_ry:.8f} Ry  ({slab_atoms} atoms)\n"
        f"E_bulk   = {bulk_energy_ry:.8f} Ry  ({bulk_atoms} atoms)\n"
        f"E_bulk per atom = {bulk_energy_ry / bulk_atoms:.8f} Ry\n"
        f"Area A   = {area:.4f} A^2  (both faces counted)\n\n"
        f"E_surf   = {value:.6f} eV/A^2\n"
        f"         = {surface_energy_j_per_m2(value):.4f} J/m^2"
    )
