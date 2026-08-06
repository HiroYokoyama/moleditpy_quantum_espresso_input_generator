# MoleditPy Quantum ESPRESSO Input Generator

[![Python CI](https://github.com/HiroYokoyama/moleditpy_quantum_espresso_input_generator/actions/workflows/test.yml/badge.svg)](https://github.com/HiroYokoyama/moleditpy_quantum_espresso_input_generator/actions/workflows/test.yml)
![Test Coverage](https://img.shields.io/badge/coverage->90%25-green)
[![GitHub tag](https://img.shields.io/github/v/tag/HiroYokoyama/moleditpy_quantum_espresso_input_generator?label=version)](https://github.com/HiroYokoyama/moleditpy_quantum_espresso_input_generator/tags)
[![GitHub Downloads](https://img.shields.io/github/downloads/HiroYokoyama/moleditpy_quantum_espresso_input_generator/total)](https://github.com/HiroYokoyama/moleditpy_quantum_espresso_input_generator/releases)

A [MoleditPy](https://github.com/HiroYokoyama/python_molecular_editor) plugin that
writes **pw.x** input files from a molecule or a crystal structure, with a live
preview of the complete input before you save.

## What it does

- **Three structure sources**
  - the molecule currently open in MoleditPy, wrapped in an orthorhombic vacuum box
  - a `.cif` file loaded from disk (asymmetric unit expanded with the CIF's own
    symmetry operations)
  - the structure already open in the **CIF Viewer** plugin panel, copied across
    without re-reading the file
- **Supercells** — independent a/b/c repeats applied to any source
- **Vacuum per axis** — pad one axis only (the usual slab setup) instead of a
  uniform box
- Slabs are built by the separate [Slab Builder](https://github.com/HiroYokoyama/moleditpy_slab_builder) plugin,
  which writes a CIF this plugin reads back
- **All pw.x run types** — `scf`, `nscf`, `bands`, `relax`, `vc-relax`, `md`,
  `vc-md`, with `&IONS` and `&CELL` written only when the run type needs them
- **&SYSTEM control** — `ecutwfc` with an automatic `ecutrho = 8 x ecutwfc`,
  occupations and smearing, `nspin = 2` with per-type `starting_magnetization`,
  `input_dft` overrides, `vdw_corr` (D2 / D3 / XDM / TS), plus a free-text block
  for anything else
- **&ELECTRONS control** — `conv_thr`, `mixing_beta`, `electron_maxstep`,
  `diagonalization`
- **K_POINTS** — `gamma`, an automatic mesh with shifts, or a mesh derived from a
  target reciprocal-space spacing
- **ATOMIC_SPECIES** — IUPAC masses plus UPF filenames resolved by **scanning your
  pseudopotential folder**, with a one-click copy into `pseudo_dir`; elements with
  no file fall back to an editable filename pattern (`{El}` / `{el}` / `{EL}`)
- **nbnd, tot_charge** — including reading the charge and open-shell state straight
  from the molecule
- Coordinates written as `crystal` or `angstrom`, always grouped by species

- **Checks** — a warning strip flags the classic mistakes: a molecule sampled
  with a dense k-mesh, k-points across a slab's vacuum, too little vacuum,
  cut-offs that are too low, a relaxation with zero steps, and charged cells

## Install

Plugin Manager → install from the MoleditPy plugin registry, or drop the
`qe_input_generator` folder into your MoleditPy plugins directory.

Requires `numpy` (already a MoleditPy dependency). `pymatgen` is optional and is
used only to expand a CIF Viewer structure that holds nothing but the asymmetric
unit; reading a `.cif` file directly never needs it.

## Use

**File → Export → Quantum ESPRESSO Input (pw.x)...**

Pick a structure source on the *Structure* tab, set the run up on *Control*,
*System* and *K-points*, check the *Preview* tab, then **Save Input...**.

Pseudopotential files are not generated — set `pseudo_dir` and the UPF filename
pattern to match your own pseudopotential library.

## Shared modules

`cell_model.py`, `elements.py` and `structure_panel.py` are shared byte-for-byte
with the VASP and CP2K input generator plugins. Each carries its own
`SHARED_MODULE_NAME` / `SHARED_MODULE_VERSION`, independent of `PLUGIN_VERSION`:
change one, bump its version, copy it to the sibling plugins, and update the pin
in each `tests/test_structure_panel.py`.

The CIF reader, lattice construction and symmetry de-duplication are derived from
the [MoleditPy CIF Viewer](https://github.com/HiroYokoyama/moleditpy_cif_viewer)
plugin's parser.

## Tests

```bash
python -m pytest tests/ -v
```

## Licence

GNU General Public License v3.0 — see [LICENSE](LICENSE).
