import pkg_resources

from pickle_compat.compat import patch, unpatch  # noqa: F401

__version__ = pkg_resources.get_distribution("pickle-compat").version
