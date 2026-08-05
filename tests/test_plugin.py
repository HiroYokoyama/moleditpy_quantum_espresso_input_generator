import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import qe_input_generator as plugin  # noqa: E402


class FakeContext:
    def __init__(self, main_window=None):
        self.main_window = main_window
        self.export_actions = []
        self.analysis_tools = []
        self.save_handlers = []
        self.load_handlers = []
        self.reset_handlers = []
        self.windows = {}
        self.current_molecule = None
        self.modified = 0

    def add_export_action(self, label, callback):
        self.export_actions.append((label, callback))

    def add_analysis_tool(self, label, callback):
        self.analysis_tools.append((label, callback))

    def register_save_handler(self, callback):
        self.save_handlers.append(callback)

    def register_load_handler(self, callback):
        self.load_handlers.append(callback)

    def register_document_reset_handler(self, callback):
        self.reset_handlers.append(callback)

    def register_window(self, window_id, window):
        self.windows[window_id] = window

    def get_window(self, window_id):
        return self.windows.get(window_id)

    def get_main_window(self):
        return self.main_window

    def mark_project_modified(self):
        self.modified += 1


@pytest.fixture
def context():
    original = dict(plugin.current_settings)
    ctx = FakeContext()
    plugin.initialize(ctx)
    yield ctx
    plugin._context = None
    plugin._dialog_opened = False
    plugin.current_settings.clear()
    plugin.current_settings.update(original)


# -- metadata --------------------------------------------------------------


def test_plugin_metadata():
    assert plugin.PLUGIN_NAME == "Quantum ESPRESSO Input Generator"
    assert plugin.PLUGIN_VERSION == "0.2.0"
    assert plugin.PLUGIN_AUTHOR == "HiroYokoyama"
    assert plugin.PLUGIN_CATEGORY == "Export"
    assert plugin.PLUGIN_DEPENDENCIES == ["numpy"]
    assert plugin.PLUGIN_TAGS == ["DFT", "Generator"]
    assert plugin.PLUGIN_DESCRIPTION.strip()


def test_plugin_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", plugin.PLUGIN_VERSION)


def test_supported_version_range():
    assert plugin.PLUGIN_SUPPORTED_MOLEDITPY_VERSION == ">=4.0.0, <5.0.0"


def test_default_settings_shape():
    settings = plugin.get_default_settings()
    for key in ("calculation", "ecutwfc", "kpoint_mode", "pseudo_pattern", "supercell"):
        assert key in settings


# -- registration ----------------------------------------------------------


def test_initialize_registers_export_action(context):
    assert [label for label, _ in context.export_actions] == [
        "Quantum ESPRESSO Input (pw.x)..."
    ]


def test_initialize_registers_the_surface_energy_tool(context):
    assert [label for label, _ in context.analysis_tools] == ["Surface Energy (QE)..."]


def test_surface_energy_tool_opens_and_reuses_its_window(context, monkeypatch):
    import qe_input_generator.surface_dialog as surface_dialog

    opened = []

    class _Dialog:
        def __init__(self, parent=None, get_area=None):
            self.get_area = get_area
            self._visible = False
            opened.append(self)

        def show(self):
            self._visible = True

        def isVisible(self):
            return self._visible

        def raise_(self):
            pass

        def activateWindow(self):
            pass

    monkeypatch.setattr(surface_dialog, "SurfaceEnergyDialog", _Dialog)
    callback = dict(context.analysis_tools)["Surface Energy (QE)..."]
    callback()
    callback()
    assert len(opened) == 1  # the second call reuses the open window


def test_surface_energy_area_comes_from_the_open_generator(context, monkeypatch):
    import qe_input_generator.surface_dialog as surface_dialog

    captured = {}

    class _Dialog:
        def __init__(self, parent=None, get_area=None):
            captured["get_area"] = get_area

        def show(self):
            pass

        def isVisible(self):
            return False

    monkeypatch.setattr(surface_dialog, "SurfaceEnergyDialog", _Dialog)

    from qe_input_generator import cell_model as cm

    cell = cm.cell_from_molecule(["H"], [[0.0, 0.0, 0.0]], padding=2.0)
    context.windows[plugin.WINDOW_ID] = type("G", (), {"_cell": cell})()

    dict(context.analysis_tools)["Surface Energy (QE)..."]()
    assert captured["get_area"]() == pytest.approx(cm.surface_area(cell))


def test_surface_energy_area_is_none_without_a_structure(context, monkeypatch):
    import qe_input_generator.surface_dialog as surface_dialog

    captured = {}

    class _Dialog:
        def __init__(self, parent=None, get_area=None):
            captured["get_area"] = get_area

        def show(self):
            pass

        def isVisible(self):
            return False

    monkeypatch.setattr(surface_dialog, "SurfaceEnergyDialog", _Dialog)
    dict(context.analysis_tools)["Surface Energy (QE)..."]()
    assert captured["get_area"]() is None


def test_initialize_registers_persistence(context):
    assert len(context.save_handlers) == 1
    assert len(context.load_handlers) == 1
    assert len(context.reset_handlers) == 1


def test_save_handler_is_silent_until_the_dialog_opens(context):
    assert context.save_handlers[0]() == {}


def test_save_handler_emits_settings_after_use(context):
    plugin._dialog_opened = True
    plugin.current_settings["ecutwfc"] = 80.0
    assert context.save_handlers[0]()["settings"]["ecutwfc"] == 80.0


def test_load_handler_updates_settings(context):
    context.load_handlers[0]({"settings": {"ecutwfc": 45.0}})
    assert plugin.current_settings["ecutwfc"] == 45.0


def test_load_handler_ignores_junk(context):
    before = dict(plugin.current_settings)
    context.load_handlers[0](None)
    context.load_handlers[0]({})
    context.load_handlers[0]({"settings": "nope"})
    assert plugin.current_settings == before


def test_reset_handler_restores_defaults(context):
    plugin._dialog_opened = True
    plugin.current_settings["ecutwfc"] = 999.0
    context.reset_handlers[0]()
    assert plugin.current_settings["ecutwfc"] == plugin.get_default_settings()["ecutwfc"]
    assert plugin._dialog_opened is False


def test_reset_handler_leaves_an_open_dialog_alone(context):
    class _Dialog:
        def isVisible(self):
            return True

    context.windows[plugin.WINDOW_ID] = _Dialog()
    plugin.current_settings["ecutwfc"] = 999.0
    context.reset_handlers[0]()
    assert plugin.current_settings["ecutwfc"] == 999.0


def test_load_handler_pushes_into_an_open_dialog(context):
    applied = {}

    class _Dialog:
        def apply_settings(self, settings):
            applied.update(settings)

    context.windows[plugin.WINDOW_ID] = _Dialog()
    context.load_handlers[0]({"settings": {"ecutwfc": 55.0}})
    assert applied["ecutwfc"] == 55.0


def test_load_handler_survives_a_broken_dialog(context):
    class _Dialog:
        def apply_settings(self, settings):
            raise RuntimeError("wrapped C/C++ object deleted")

    context.windows[plugin.WINDOW_ID] = _Dialog()
    context.load_handlers[0]({"settings": {"ecutwfc": 55.0}})
    assert plugin.current_settings["ecutwfc"] == 55.0
