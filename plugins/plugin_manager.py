"""
plugins/plugin_manager.py
----------------------------
Discovers and loads `AshaPlugin` subclasses from the `plugins/` folder
at startup, using `importlib` — no core-code changes needed to add a
new plugin, matching the spec's plugin-architecture requirement.

Convention: any `*.py` file directly inside `plugins/` (other than
files starting with `_` or the framework files themselves) that
defines exactly one `AshaPlugin` subclass is treated as a plugin.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

from config.settings import PLUGINS_DIR
from plugins.plugin_base import AshaPlugin, PetAPI
from utils.logger import get_logger

logger = get_logger(__name__)

_FRAMEWORK_FILES = {"__init__.py", "plugin_base.py", "plugin_manager.py"}


class PluginManager:
    """Loads and owns the lifecycle of all discovered plugins."""

    def __init__(self, api: PetAPI) -> None:
        self._api = api
        self._plugins: list[AshaPlugin] = []

    def discover_and_load(self) -> list[str]:
        """Import every plugin file, instantiate and load it. Returns the
        list of successfully loaded plugin names."""
        loaded_names: list[str] = []

        if not PLUGINS_DIR.is_dir():
            return loaded_names

        for path in sorted(PLUGINS_DIR.glob("*.py")):
            if path.name in _FRAMEWORK_FILES or path.name.startswith("_"):
                continue
            try:
                plugin = self._load_plugin_file(path)
            except Exception:  # noqa: BLE001 - one bad plugin shouldn't crash Asha
                logger.exception("Failed to load plugin from %s", path)
                continue
            if plugin is None:
                continue

            try:
                plugin.on_load()
            except Exception:  # noqa: BLE001
                logger.exception("Plugin '%s' raised during on_load()", plugin.name)
                continue

            self._plugins.append(plugin)
            loaded_names.append(plugin.name)
            logger.info("Loaded plugin: %s — %s", plugin.name, plugin.description)

        return loaded_names

    def _load_plugin_file(self, path: Path) -> AshaPlugin | None:
        module_name = f"plugins.dynamic.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        plugin_classes = [
            obj
            for _, obj in inspect.getmembers(module, inspect.isclass)
            if issubclass(obj, AshaPlugin) and obj is not AshaPlugin
        ]
        if not plugin_classes:
            logger.warning("No AshaPlugin subclass found in %s — skipping.", path)
            return None
        if len(plugin_classes) > 1:
            logger.warning(
                "Multiple AshaPlugin subclasses found in %s — using the first (%s).",
                path,
                plugin_classes[0].__name__,
            )

        return plugin_classes[0](self._api)

    def unload_all(self) -> None:
        for plugin in self._plugins:
            try:
                plugin.on_unload()
            except Exception:  # noqa: BLE001
                logger.exception("Plugin '%s' raised during on_unload()", plugin.name)
        self._plugins.clear()
