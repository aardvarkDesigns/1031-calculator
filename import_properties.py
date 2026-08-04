#!/usr/bin/env python3
"""Load or refresh property data in properties.db from a cleaned MLS spreadsheet.

Reads an .xlsx file with 'Property ID', 'Sale Price', 'Sale Date', and
'Current Value' columns and upserts each row into the `properties` table:
new Property IDs are inserted, existing ones are updated in place. Run this
locally, then commit + push properties.db to deploy the refresh to Railway.

If the sheet also has 'Address', 'Property City', and/or 'Prop Zip' columns,
those are imported too (property_address / city / zip_code) and shown at
the top of the calculator page. They're optional -- a sheet without them
still imports fine, just without an address to display.

By default, rows removed from the spreadsheet are left alone in the database.
Pass --sync to also delete any property whose Property ID is no longer in
the spreadsheet -- use this when properties have been intentionally dropped
from the mailing list (e.g. bad data, bulk-sale price outliers) and should
stop being reachable via the calculator.

Pass --estimate-mortgage to fill in first_mortgage_amt / mortgage_rate /
mortgage_date for any property missing them, using estimate_mortgage() below.
This never overwrites real mortgage data that's already in the database --
it only fills fields that are currently NULL. These are rough estimates
based on typical financing assumptions, not actual loan data -- see
estimate_mortgage()'s docstring for the caveats.

Usage:
    python import_properties.py /path/to/scrapedData_20260730_multifamily.xlsx
    python import_properties.py data.xlsx --sheet "MLS Data" --dry-run
    python import_properties.py data.xlsx --sync
    python import_properties.py data.xlsx --estimate-mortgage
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

# Read in when present but not required -- older/other source spreadsheets
# may not have these columns, and the calculator works fine without them.
OPTIONAL_COLUMNS = ("Address", "Property City", "Prop Zip")

# Assumed loan-to-value ratio when the actual down payment is unknown. 75%
# LTV (25% down) is a common baseline for investment-property financing.
DEFAULT_LTV = 0.75

# Average annual 30-year fixed mortgage rate by year, used as a stand-in for
# the actual rate on a property's original loan when only the purchase
# (sale) date is known. Investment-property loans typically price somewhat
# above this residential benchmark, often by 0.5-0.75 points, so treat
# estimates built from this table as a floor rather than the true rate.
# Source: Bankrate historical mortgage rates
# (https://www.bankrate.com/mortgages/historical-mortgage-rates/), Freddie
# Mac PMMS data for years prior to 1982, Bankrate aggregation from 1982 on.
# Retrieved 2026-08-04.
RATE_BY_YEAR = {
    2026: 6.28, 2025: 6.66, 2024: 6.90, 2023: 7.00, 2022: 5.53, 2021: 3.15,
    2020: 3.38, 2019: 4.13, 2018: 4.70, 2017: 4.14, 2016: 3.79, 2015: 3.99,
    2014: 4.31, 2013: 4.16, 2012: 3.88, 2011: 4.65, 2010: 4.86, 2009: 5.38,
    2008: 6.23, 2007: 6.40, 2006: 6.47, 2005: 5.93, 2004: 5.88, 2003: 5.89,
    2002: 6.57, 2001: 7.01, 2000: 8.08, 1999: 7.46, 1998: 6.91, 1997: 7.57,
    1996: 7.76, 1995: 7.86, 1994: 8.28, 1993: 7.17, 1992: 8.27, 1991: 9.09,
    1990: 9.97, 1989: 10.25, 1988: 10.38, 1987: 10.40, 1986: 10.39,
    1985: 12.43, 1984: 13.88, 1983: 13.24, 1982: 16.06, 1981: 16.64,
    1980: 13.74, 1979: 11.20, 1978: 9.64, 1977: 8.85, 1976: 8.87, 1975: 9.05,
    1974: 9.19, 1973: 8.04, 1972: 7.38,
}


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


def estimate_mortgage(
    sale_price: int | None,
    sale_date: date | None,
    ltv: float = DEFAULT_LTV,
) -> tuple[int, float, date] | None:
    """Estimate original loan amount, rate, and origination date for a property.

    This fills the gap when only a purchase price and purchase date are
    known -- no original loan amount, rate, or term. It assumes the property
    was financed at `ltv` loan-to-value on the sale date, at that year's
    average 30-year fixed rate (see RATE_BY_YEAR), amortized over 30 years
    (the default term `calculate_mortgage_payoff()` in app.py already uses).

    These are estimates, not real mortgage data. The loan-to-value
    assumption is the largest source of error -- actual down payments on
    investment property vary well beyond a fixed 25%. Use this to get a
    directionally reasonable Mortgage Pay Off, not a number to rely on for
    an actual 1031 exchange transaction.

    Args:
        sale_price: The property's purchase (sale) price, or None.
        sale_date: The property's purchase (sale) date, or None.
        ltv: Assumed loan-to-value ratio, e.g. 0.75 for 75% LTV / 25% down.

    Returns:
        A (mortgage_amount, mortgage_rate, mortgage_date) tuple, or None if
        sale_price or sale_date is missing so no estimate can be made.
    """
    if sale_price is None or sale_date is None:
        return None

    mortgage_amount = int(sale_price * ltv)

    earliest_year = min(RATE_BY_YEAR)
    latest_year = max(RATE_BY_YEAR)
    lookup_year = min(max(sale_date.year, earliest_year), latest_year)
    mortgage_rate = RATE_BY_YEAR[lookup_year]

    return mortgage_amount, mortgage_rate, sale_date


def parse_optional_str(value: object) -> str | None:
    """Convert an optional text/number cell to a stripped string, or None.

    Args:
        value: Raw cell value, which may be a string, number, or None.

    Returns:
        The stripped string, or None if the cell is empty. Whole-number
        floats (e.g. a zip code read as 89119.0) are rendered without the
        trailing ".0".
    """
    if value is None or value == "":
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_rows(xlsx_path: Path, sheet_name: str | None) -> list[dict]:
    """Read and validate the source spreadsheet into plain dict rows.

    Args:
        xlsx_path: Path to the source .xlsx file.
        sheet_name: Sheet to read, or None to use the active sheet.

    Returns:
        One dict per data row, keyed by the required column names plus
        whichever OPTIONAL_COLUMNS are present in the sheet.

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
    col_index.update({name: header.index(name) for name in OPTIONAL_COLUMNS if name in header})

    rows = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        rows.append({name: row[idx] for name, idx in col_index.items()})
    return rows


def upsert_properties(
    rows: list[dict],
    dry_run: bool,
    estimate_mortgage_flag: bool = False,
) -> tuple[int, int, int, int]:
    """Insert new properties and update existing ones from parsed rows.

    Args:
        rows: Parsed spreadsheet rows (raw cell values, not yet type-converted).
        dry_run: If True, parse and report but don't write to the database.
        estimate_mortgage_flag: If True, fill first_mortgage_amt / mortgage_rate /
            mortgage_date for any property that doesn't already have them, via
            estimate_mortgage(). Never overwrites existing (real) mortgage data.

    Returns:
        An (inserted, updated, skipped, estimated) count tuple.
    """
    session = get_session()
    inserted = updated = skipped = estimated = 0
    try:
        for row in rows:
            property_id = str(row["Property ID"]).strip() if row["Property ID"] else ""
            if not property_id:
                skipped += 1
                continue

            sale_price = parse_currency(row["Sale Price"])
            sale_date = parse_sale_date(row["Sale Date"])
            current_value = parse_currency(row["Current Value"])
            property_address = parse_optional_str(row.get("Address"))
            city = parse_optional_str(row.get("Property City"))
            zip_code = parse_optional_str(row.get("Prop Zip"))

            existing = session.query(Property).filter_by(property_id=property_id).first()
            if existing:
                existing.sale_price = sale_price
                existing.sale_date = sale_date
                existing.current_home_value = current_value
                existing.property_address = property_address
                existing.city = city
                existing.zip_code = zip_code
                existing.updated_at = datetime.utcnow()
                target = existing
                updated += 1
            else:
                target = Property(
                    property_id=property_id,
                    sale_price=sale_price,
                    sale_date=sale_date,
                    current_home_value=current_value,
                    property_address=property_address,
                    city=city,
                    zip_code=zip_code,
                )
                session.add(target)
                inserted += 1

            if estimate_mortgage_flag and target.first_mortgage_amt is None:
                estimate = estimate_mortgage(sale_price, sale_date)
                if estimate is not None:
                    target.first_mortgage_amt, target.mortgage_rate, target.mortgage_date = estimate
                    estimated += 1

        if dry_run:
            session.rollback()
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return inserted, updated, skipped, estimated


def sync_delete(current_ids: set[str], dry_run: bool) -> int:
    """Delete properties whose Property ID is no longer in the spreadsheet.

    Args:
        current_ids: Property IDs present in the current spreadsheet.
        dry_run: If True, count matches but don't delete.

    Returns:
        The number of properties removed (or that would be removed).
    """
    session = get_session()
    try:
        stale = session.query(Property).filter(~Property.property_id.in_(current_ids)).all()
        removed_ids = [p.property_id for p in stale]
        for prop in stale:
            session.delete(prop)

        if dry_run:
            session.rollback()
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if removed_ids:
        print(f"  Removed: {', '.join(removed_ids)}")
    return len(removed_ids)


def main() -> None:
    """Parse arguments, run the import, and print a summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx_path", type=Path, help="Path to the cleaned MLS .xlsx file")
    parser.add_argument("--sheet", default=None, help="Sheet name (default: active sheet)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing")
    parser.add_argument("--sync", action="store_true",
                         help="Also delete properties no longer in the spreadsheet")
    parser.add_argument("--estimate-mortgage", action="store_true",
                         help="Fill missing mortgage fields with rough estimates "
                              "(see estimate_mortgage() docstring for assumptions)")
    args = parser.parse_args()

    if not args.xlsx_path.exists():
        sys.exit(f"Error: file not found: {args.xlsx_path}")

    init_db()
    rows = read_rows(args.xlsx_path, args.sheet)
    print(f"Read {len(rows)} row(s) from {args.xlsx_path.name}")

    inserted, updated, skipped, estimated = upsert_properties(
        rows, args.dry_run, args.estimate_mortgage
    )

    removed = 0
    if args.sync:
        current_ids = {str(row["Property ID"]).strip() for row in rows if row["Property ID"]}
        removed = sync_delete(current_ids, args.dry_run)

    session = get_session()
    try:
        total = session.query(Property).count()
    finally:
        session.close()

    mode = " (dry run, nothing written)" if args.dry_run else ""
    print(f"Inserted: {inserted}  Updated: {updated}  Skipped (no Property ID): {skipped}  Removed: {removed}{mode}")
    if args.estimate_mortgage:
        print(f"Estimated mortgage fields for: {estimated} propert{'y' if estimated == 1 else 'ies'}")
    print(f"Total properties in database: {total}")
    if total > MAX_ROWS:
        print(f"  Warning: exceeds the expected max of {MAX_ROWS} rows.", file=sys.stderr)


if __name__ == "__main__":
    main()
