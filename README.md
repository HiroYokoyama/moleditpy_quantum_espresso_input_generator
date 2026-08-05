# MoleditPy Quantum ESPRESSO Input Generator

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
- **ATOMIC_SPECIES** — IUPAC masses and UPF filenames from an editable pattern
  (`{El}` / `{el}` / `{EL}` placeholders, with common library conventions preset)
- Coordinates written as `crystal` or `angstrom`, always grouped by species

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

MIT — see [LICENSE](LICENSE).
