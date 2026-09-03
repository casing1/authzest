"""AuthZest core package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("authzest")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
