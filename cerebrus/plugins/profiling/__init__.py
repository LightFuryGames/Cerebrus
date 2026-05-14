"""Profiling plugin package."""

__all__ = ["ProfilingPlugin"]


def __getattr__(name: str):
    if name == "ProfilingPlugin":
        from cerebrus.plugins.profiling.plugin import ProfilingPlugin

        return ProfilingPlugin
    raise AttributeError(name)
