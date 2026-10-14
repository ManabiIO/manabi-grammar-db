#!/usr/bin/env python3
from __future__ import annotations
import sys
from content import ROOT, parse_markdown_sections, collect_rows
from schema_contract import check_row_schema


def main() -> int:
    try:
        check_row_schema()
        rows = collect_rows(ROOT)
    except ValueError as error:
        print(f"::error::{error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
