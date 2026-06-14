"""Client-safe top-level exports for the DATA Agent package.

Default installs must be able to import ``data_agent`` without pulling in server
runtime adapters or their optional dependencies. Server-only adapter entry points
remain under ``data_agent.adapters.llm``.
"""

from data_agent.client import Client

__all__ = ["Client"]
