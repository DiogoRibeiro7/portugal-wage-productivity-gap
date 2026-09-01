"""Portugal wage-productivity gap analysis package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("portugal-wage-productivity-gap")
except PackageNotFoundError:  # pragma: no cover - source-tree execution
    __version__ = "0.3.0"

__all__ = ["__version__"]
