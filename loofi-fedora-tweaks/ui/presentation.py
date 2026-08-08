"""Small presentation-only text helpers for Qt labels and mnemonic controls."""

from __future__ import annotations


def visible_label(text: object) -> str:
    """Return plain visible copy without leaking identifier separators."""
    return " ".join(str(text or "").replace("_", " ").split())


def button_label(text: object) -> str:
    """Return literal button copy with Qt mnemonic markers escaped."""
    return visible_label(text).replace("&", "&&")
