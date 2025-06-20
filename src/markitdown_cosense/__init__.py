"""markitdown-cosense: A markitdown plugin for converting Scrapbox to Markdown."""

from ._plugin import TagHandling, __plugin_interface_version__, register_converters

__version__ = "0.1.0"
__all__ = [
    "register_converters",
    "TagHandling",
    "__plugin_interface_version__",
    "__version__",
]
