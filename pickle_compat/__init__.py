import pkg_resources

from pickle_compat.compat import patch, unpatch

__version__ = pkg_resources.get_distribution("pickle-compat").version


__all__ = [
    "patch",
    "unpatch",
    "__version__",
]
