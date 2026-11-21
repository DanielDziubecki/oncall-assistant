"""Development factory for this repository.

The factory is the set of agents, checks and commands that help build the On-call Assistant.
It runs coding agents (Claude Code, Codex) as interchangeable workers through small drivers,
so no factory definition depends on one vendor. See docs/factory/plan.md.
"""

from importlib.metadata import version

__version__ = version("factory")
