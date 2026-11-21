"""Harness drivers. Adding a harness means adding a driver here and a table in models.toml."""

from factory.drivers.base import Driver, HarnessError, Reply
from factory.drivers.claude import ClaudeDriver
from factory.drivers.codex import CodexDriver

DRIVERS: dict[str, Driver] = {
    ClaudeDriver.name: ClaudeDriver(),
    CodexDriver.name: CodexDriver(),
}

__all__ = ["DRIVERS", "Driver", "HarnessError", "Reply"]
