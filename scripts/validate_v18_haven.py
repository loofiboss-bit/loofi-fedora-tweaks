#!/usr/bin/env python3
"""Compatibility wrapper for the version-neutral product-contract gate."""

if __package__:
    from scripts.validate_product_contract import main, validate
else:  # Direct script execution.
    from validate_product_contract import main, validate

__all__ = ["main", "validate"]


if __name__ == "__main__":
    raise SystemExit(main())
