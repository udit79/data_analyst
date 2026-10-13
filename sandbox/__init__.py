"""Managed Deep Agents hosted sandbox declaration."""

from managed_deepagents import define_sandbox

sandbox = define_sandbox(idle_ttl_seconds=600, default_timeout=600)
