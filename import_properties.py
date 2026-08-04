#!/usr/bin/env python3
"""Load or refresh property data in properties.db from a cleaned MLS spreadsheet.

Reads an .xlsx file with 'Property ID', 'Sale Price', 'Sale Date', and
'Current Value' columns and upserts each row into the `properties` table:
new Property IDs are inserted, existing ones are updated in place. Run this
locally, then commit + push properties.db to deploy the refresh to Railway.

Usage:
    python import_properties.py /path/to/scrapedData_20260730_multifamily.xlsx
    python import_properties.py data.xlsx --sheet "MLS Data" --dry-run
"""

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

from models import Property, get_session, init_db

MAX_ROWS = 4000
REQUIRED_COLUMNS = ("Property ID", "Sale Price", "Sale Date", "Current Value")


def parse_currency(value: object) -> int | None:
    """Convert a currency cell ("$730,000", 730000.0, etc.) to an int.

    Args:
        value: Raw cell value, which may be a string, number, or None.

    Returns:
        The parsed dollar amount as an int, or None if it can't be parsed.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        cleaned = re.sub(r"[^\d.-]", "", str(value))
        return int(float(cleaned)) if cleaned else None
    except ValueError:
        return None


def parse_sale_date(value: object) -> date | None:
    """Convert a date cell ("07/23/2024", a datetime, etc.) to a date.

    Args:
        value: Raw cell value, which may be a string, datetime, date, or None.

    Returns:
        The parsed date, or None if it can't be parsed.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%m/%d/%Y").date()
    except ValueError:
        print(f"  Warning: could not parse Sale Date {value!r}", file=sys.stderr)
        return None


def read_rows(xlsx_path: Path, sheet_name: str | None) -> list[dict]:
    """Read and validate the source spreadsheet into plain dict rows.

    Args:
        xlsx_path: Path to the source .xlsx file.
        sheet_name: Sheet to read, or None to use the active sheet.

    Returns:
        One dict per data row, keyed by the required column names.

    Raises:
        SystemExit: If a required column is missing from the sheet.
    """
    workbook = openpyxl.load_workbook(xlsx_path, data_only=True)
    sheet = workbook[sheet_name] if sheet_name else workbook.active

    header = [cell.value for cell in sheet[1]]
    missing = [col for col in REQUIRED_COLUMNS if col not in header]
    if missing:
        sys.exit(f"Error: sheet '{sheet.title}' is missing required column(s): {missing}")

    col_index = {name: header.index(name) for name in REQUIRED_COLUMNS}
    rows = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        rows.append({name: row[idx] for name, idx in col_index.items()})
    return rows


def upsert_properties(rows: list[dict], dry_run: bool) -> tuple[int, int, int]:
    """Insert new properties and update existing ones from parsed rows.

    Args:
        rows: Parsed spreadsheet rows (raw cell values, not yet type-converted).
        dry_run: If True, parse and report but don't write to the database.

    Returns:
        A (inserted, updated, skipped) count tuple.
    """
    session = get_session()
    inserted = updated = skipped = 0
    try:
        for row in rows:
            property_id = str(row["Property ID"]).strip() if row["Property ID"] else ""
            if not property_id:
                skipped += 1
                continue

            sale_price = parse_currency(row["Sale Price"])
            sale_date = parse_sale_date(row["Sale Date"])
            current_value = parse_currency(row["Current Value"])

            existing = session.query(Property).filter_by(property_id=property_id).first()
            if existing:
                existing.sale_price = sale_price
                existing.sale_date = sale_date
                existing.current_home_value = current_value
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                session.add(Property(
                    property_id=property_id,
                    sale_price=sale_price,
                    sale_date=sale_date,
                    current_home_value=current_value,
                ))
                inserted += 1

        if dry_run:
            session.rollback()
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return inserted, updated, skipped


def main() -> None:
    """Parse arguments, run the import, and print a summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx_path", type=Path, help="Path to the cleaned MLS .xlsx file")
    parser.add_argument("--sheet", default=None, help="Sheet name (default: active sheet)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing")
    args = parser.parse_args()

    if not args.xlsx_path.exists():
        sys.exit(f"Error: file not found: {args.xlsx_path}")

    init_db()
    rows = read_rows(args.xlsx_path, args.sheet)
    print(f"Read {len(rows)} row(s) from {args.xlsx_path.name}")

    inserted, updated, skipped = upsert_properties(rows, args.dry_run)

    session = get_session()
    try:
        total = session.query(Property).count()
    finally:
        session.close()

    mode = " (dry run, nothing written)" if args.dry_run else ""
    print(f"Inserted: {inserted}  Updated: {updated}  Skipped (no Property ID): {skipped}{mode}")
    print(f"Total properties in database: {total}")
    if total > MAX_ROWS:
        print(f"  Warning: exceeds the expected max of {MAX_ROWS} rows.", file=sys.stderr)


if __name__ == "__main__":
    main()
