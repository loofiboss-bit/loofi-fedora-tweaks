"""Utility package providing shared helpers."""

# Plugin management modules are imported directly to avoid eager side effects:
# External Marketplace and executable Python extensions are retired.
# Not added to __init__.py to avoid circular imports with core.plugins
