class ProviderError(Exception):
    """An external API failed or returned something unusable."""


class NoRouteError(ProviderError):
    """The routing provider found no route between the given points."""
