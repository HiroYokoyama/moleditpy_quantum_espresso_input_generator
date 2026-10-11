# Input audit — 0.11.0 (2026-10-12)

Reference: [official pw.x input description](https://www.quantum-espresso.org/Doc/INPUT_PW.html).

Comma-indexed namelist keywords are preserved, and a quote of the other style
inside a string no longer produces a false unclosed-quote error. A malformed
line cannot attach fragments to a previous line's value. Numeric settings retain
precision. Malformed extra keywords and stray card text block input generation;
preview and save explain the problem and recover when corrected.

The functional default is named UPF default; older POTCAR/UPF default settings
still omit input_dft. PPCG is removed because support ended in December 2024;
RMM-ParO is available. Tetrahedron occupations require an automatic uniform
mesh, with extra occupation overrides honored. Their force warning no longer
claims that every SCF use is invalid. Existing beeman/pr variable-cell dynamics
keywords and functional names remain unchanged.

Imports in the plugin entry point, dialog and writer are at module scope.
Tests exercise parser behavior, precision, legacy settings, solver/mesh checks
and Qt preview/save recovery. No pw.x executable is installed here; these are
documentation and regression checks, not engine calculations.
