"""Root Builder detection and the use_rootbuilder setting.

Root Builder is a complement, never a requirement: when it is absent
the installer must fall back to the normal layout rather than refuse
the archive.
"""
from __future__ import annotations


def _set_mode(organizer, mode):
    organizer._settings["PalworldInstaller"]["use_rootbuilder"] = mode


class TestRootbuilderDetected:
    def test_absent_by_default(self, make_installer):
        assert make_installer._rootbuilder_detected() is False

    def test_detects_display_name(self, make_installer, rootbuilder_enabled):
        assert make_installer._rootbuilder_detected() is True

    def test_detects_alternate_spelling(self, make_installer, mock_organizer):
        """MO2 matches on the plugin's own name(), which may not be the
        spelling the docs use."""
        mock_organizer._enabled_plugins.add("RootBuilder")
        assert make_installer._rootbuilder_detected() is True

    def test_survives_a_raising_organizer(self, make_installer, mock_organizer):
        def boom(_name):
            raise RuntimeError("plugin list unavailable")

        mock_organizer.isPluginEnabled = boom
        assert make_installer._rootbuilder_detected() is False


class TestResolveUseRootbuilder:
    def test_auto_uses_it_when_present(
        self, make_installer, rootbuilder_enabled
    ):
        assert make_installer._resolve_use_rootbuilder() is True

    def test_auto_falls_back_when_absent(self, make_installer):
        assert make_installer._resolve_use_rootbuilder() is False

    def test_never_overrides_detection(
        self, make_installer, rootbuilder_enabled
    ):
        _set_mode(rootbuilder_enabled, "never")
        assert make_installer._resolve_use_rootbuilder() is False

    def test_always_routes_even_when_undetected(
        self, make_installer, mock_organizer
    ):
        _set_mode(mock_organizer, "always")
        assert make_installer._resolve_use_rootbuilder() is True

    def test_value_is_case_and_space_insensitive(
        self, make_installer, mock_organizer
    ):
        _set_mode(mock_organizer, "  NEVER ")
        assert make_installer._resolve_use_rootbuilder() is False

    def test_unknown_value_falls_back_to_auto(
        self, make_installer, rootbuilder_enabled
    ):
        _set_mode(rootbuilder_enabled, "sometimes")
        assert make_installer._resolve_use_rootbuilder() is True

    def test_missing_setting_falls_back_to_auto(
        self, make_installer, mock_organizer
    ):
        del mock_organizer._settings["PalworldInstaller"]["use_rootbuilder"]
        assert make_installer._resolve_use_rootbuilder() is False


class TestSettingRegistered:
    def test_use_rootbuilder_is_declared(self, make_installer):
        names = [s.key for s in make_installer.settings()]
        assert "use_rootbuilder" in names

    def test_defaults_to_auto(self, make_installer):
        setting = next(
            s for s in make_installer.settings() if s.key == "use_rootbuilder"
        )
        assert setting.default == "auto"
