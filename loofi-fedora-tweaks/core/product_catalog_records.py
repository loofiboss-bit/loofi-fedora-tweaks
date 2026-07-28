"""Compatibility export for destination-owned product catalog records."""

from __future__ import annotations

from core.catalog_records.composer import compose_catalog_data

# Keep the established import surface while destination modules own the data.
CATALOG_DATA = compose_catalog_data()
