"""Quantum ESPRESSO (pw.x) Input Generator plugin for MoleditPy."""

import logging
import os

PLUGIN_NAME = "Quantum ESPRESSO Input Generator"
PLUGIN_VERSION = "0.2.0"
PLUGIN_AUTHOR = "HiroYokoyama"
PLUGIN_DESCRIPTION = (
    "Generate Quantum ESPRESSO pw.x inputs from the current molecule "
    "(in a vacuum box) or from a CIF crystal structure, with supercells, "
    "k-point meshes and pseudopotential filename patterns."
)
PLUGIN_CATEGORY = "Export"
PLUGIN_TAGS = ["DFT", "Generator"]
PLUGIN_DEPENDENCIES = ["numpy"]
PLUGIN_SUPPORTED_MOLEDITPY_VERSION = ">=4.0.0, <5.0.0"

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
WINDOW_ID = "qe_input_generator_dialog"
SURFACE_WINDOW_ID = "qe_surface_energy_dialog"

_context = None
_dialog_opened = False


def get_default_settings():
    from .writer import default_settings

    return default_settings()


current_settings = get_default_settings()


def run(mw):
    global _dialog_opened

    if _context is not None:
        mw = _context.get_main_window()

    from .main_dialog import QeInputDialog

    if _context is not None:
        existing = _context.get_window(WINDOW_ID)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

    def _get_molecule():
        try:
            if _context is not None:
                return _context.current_molecule
        except Exception as exc:  # pragma: no cover - host API guard
            logging.warning("%s: could not read the molecule: %s", PLUGIN_NAME, exc)
        return getattr(mw, "current_mol", None)

    def _mark_modified():
        if _context is not None:
            try:
                _context.mark_project_modified()
            except Exception:  # pragma: no cover - host API guard
                pass

    def _get_cif_viewer():
        from .structure_panel import find_cif_viewer_widget

        return find_cif_viewer_widget(mw)

    _dialog_opened = True
    dlg = QeInputDialog(
        parent=mw,
        persistent_settings=current_settings,
        get_molecule=_get_molecule,
        mark_modified=_mark_modified,
        get_cif_viewer=_get_cif_viewer,
    )
    if _context is not None:
        _context.register_window(WINDOW_ID, dlg)
    dlg.show()


def initialize(context):
    global _context
    _context = context

    def show_dialog():
        run(context.get_main_window())

    def show_surface_energy():
        from .surface_dialog import SurfaceEnergyDialog

        mw = context.get_main_window()
        existing = context.get_window(SURFACE_WINDOW_ID)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        def _area():
            # Reuse the slab the generator is showing, if it has one.
            generator = context.get_window(WINDOW_ID)
            cell = getattr(generator, "_cell", None) if generator is not None else None
            if cell is None:
                return None
            from .cell_model import surface_area

            return surface_area(cell)

        dlg = SurfaceEnergyDialog(parent=mw, get_area=_area)
        context.register_window(SURFACE_WINDOW_ID, dlg)
        dlg.show()

    context.add_export_action("Quantum ESPRESSO Input (pw.x)...", show_dialog)
    context.add_analysis_tool("Surface Energy (QE)...", show_surface_energy)

    def save_state():
        if not _dialog_opened:
            return {}
        return {"settings": dict(current_settings)}

    def load_state(data):
        if not isinstance(data, dict):
            return
        saved = data.get("settings")
        if isinstance(saved, dict):
            current_settings.update(saved)
            dlg = context.get_window(WINDOW_ID)
            if dlg is not None:
                try:
                    dlg.apply_settings(current_settings)
                except Exception as exc:  # pragma: no cover - host API guard
                    logging.warning("%s: could not apply loaded state: %s", PLUGIN_NAME, exc)

    def handle_reset():
        global _dialog_opened
        dlg = context.get_window(WINDOW_ID)
        if dlg is not None and dlg.isVisible():
            # Leave an open dialog alone: the user may still be editing.
            return
        current_settings.clear()
        current_settings.update(get_default_settings())
        _dialog_opened = False

    context.register_save_handler(save_state)
    context.register_load_handler(load_state)
    context.register_document_reset_handler(handle_reset)
