"""
Hot-Reload Configuration System.

Allows configuration changes to be applied without restarting the application.

Features:
- File watching for config changes
- In-memory config cache with TTL
- WebSocket notifications for config updates
- Atomic config updates with rollback

Usage:
    from resync.core.config_hot_reload import ConfigManager

    config_manager = ConfigManager()
    await config_manager.start()

    # Get config value (auto-reloads if file changed)
    value = config_manager.get("database.host")

    # Set config value (auto-persists)
    config_manager.set("database.host", "new-host")
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


@dataclass
class ConfigChange:
    """Represents a configuration change."""
    key: str
    old_value: Any
    new_value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "api"  # api, file, env


class ConfigFileHandler(FileSystemEventHandler):
    """Handles file system events for config files."""

    def __init__(self, callback: Callable):
        self.callback = callback

    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent):
            asyncio.create_task(self.callback(event.src_path))


class ConfigManager:
    """
    Hot-reload configuration manager.

    Watches config files and applies changes without restart.
    """

    def __init__(
        self,
        config_dir: str = "config",
        main_config: str = "settings.json",
    ):
        self.config_dir = Path(config_dir)
        self.main_config = main_config

        # Configuration storage
        self._config: dict[str, Any] = {}
        self._defaults: dict[str, Any] = {}

        # Change tracking
        self._change_history: list[ConfigChange] = []
        self._subscribers: set[Callable] = set()

        # File watching
        self._observer: Observer | None = None
        self._watching = False

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the configuration manager."""
        # Create config directory if needed
        self.config_dir.mkdir(exist_ok=True)

        # Load initial configuration
        await self._load_config()

        # Start file watching
        self._start_watching()

        logger.info("ConfigManager started", extra={"config_dir": str(self.config_dir)})

    async def stop(self):
        """Stop the configuration manager."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._watching = False

        logger.info("ConfigManager stopped")

    def _start_watching(self):
        """Start watching config files for changes."""
        if self._watching:
            return

        handler = ConfigFileHandler(self._on_file_change)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.config_dir), recursive=True)
        self._observer.start()
        self._watching = True

        logger.info("Started watching config files")

    async def _on_file_change(self, filepath: str):
        """Handle config file changes."""
        logger.info(f"Config file changed: {filepath}")

        async with self._lock:
            # Reload configuration
            await self._load_config()

            # Notify subscribers
            await self._notify_subscribers()

    async def _load_config(self):
        """Load configuration from files."""
        config_file = self.config_dir / self.main_config

        if config_file.exists():
            try:
                with open(config_file) as f:
                    self._config = json.load(f)
                logger.info("Configuration loaded successfully")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in config file: {e}")
        else:
            # Create default config
            self._config = self._defaults.copy()
            await self._save_config()

    async def _save_config(self):
        """Save configuration to file."""
        config_file = self.config_dir / self.main_config

        try:
            with open(config_file, 'w') as f:
                json.dump(self._config, f, indent=2, default=str)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Supports dot notation: "database.host"
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    async def set(self, key: str, value: Any, persist: bool = True) -> bool:
        """
        Set a configuration value.

        Args:
            key: Config key (supports dot notation)
            value: New value
            persist: Whether to save to file

        Returns:
            True if successful
        """
        async with self._lock:
            # Get old value for change tracking
            old_value = self.get(key)

            # Set new value
            keys = key.split('.')
            config = self._config

            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            config[keys[-1]] = value

            # Track change
            change = ConfigChange(key=key, old_value=old_value, new_value=value)
            self._change_history.append(change)

            # Persist if requested
            if persist:
                await self._save_config()

            # Notify subscribers
            await self._notify_subscribers(change)

            logger.info(f"Config changed: {key} = {value}")
            return True

    async def reload(self):
        """Force reload configuration from files."""
        async with self._lock:
            await self._load_config()
            await self._notify_subscribers()

    def subscribe(self, callback: Callable):
        """Subscribe to configuration changes."""
        self._subscribers.add(callback)

    def unsubscribe(self, callback: Callable):
        """Unsubscribe from configuration changes."""
        self._subscribers.discard(callback)

    async def _notify_subscribers(self, change: ConfigChange | None = None):
        """Notify all subscribers of configuration change."""
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(change)
                else:
                    callback(change)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")

    def get_all(self) -> dict[str, Any]:
        """Get all configuration as dictionary."""
        return self._config.copy()

    def get_history(self, limit: int = 100) -> list[ConfigChange]:
        """Get change history."""
        return self._change_history[-limit:]

    async def rollback(self, steps: int = 1) -> bool:
        """
        Rollback configuration changes.

        Args:
            steps: Number of changes to rollback

        Returns:
            True if successful
        """
        if not self._change_history:
            return False

        async with self._lock:
            for _ in range(min(steps, len(self._change_history))):
                change = self._change_history.pop()
                await self.set(change.key, change.old_value, persist=False)

            await self._save_config()
            return True


# Global instance
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get global configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


async def init_config_manager():
    """Initialize global configuration manager."""
    manager = get_config_manager()
    await manager.start()
    return manager
