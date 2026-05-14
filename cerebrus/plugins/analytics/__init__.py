"""Analytics plugin package."""

__all__ = ["AnalyticsPlugin"]


def __getattr__(name: str):
    if name == "AnalyticsPlugin":
        from cerebrus.plugins.analytics.plugin import AnalyticsPlugin

        return AnalyticsPlugin
    raise AttributeError(name)
