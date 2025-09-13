"""
thsht: Tools for working with Touhou 15 (.sht) files.

Modules
- sht_lossless: lossless dump/build and overlay application.
- sht_extract_json: extract option positions and 88-byte records to JSON.
- parse_88_levels: parse and summarize 88-byte records by level.
"""

__all__ = [
    "sht_lossless",
    "sht_extract_json",
    "parse_88_levels",
]

__version__ = "0.1.0"
