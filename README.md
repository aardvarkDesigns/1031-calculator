# 1031 Exchange Calculator - FastHTML Version

This is a conversion of the Flask app to FastHTML, a modern Python web framework for rapid development.

## What Changed

### Flask → FastHTML Conversion

| Aspect | Flask | FastHTML |
|--------|-------|----------|
| **App Setup** | `Flask(__name__)` | `fast_app()` |
| **Routing** | `@app.route()` | `@rt()` |
| **Templates** | Jinja2 `.html` files | Python functions |
| **HTML Generation** | `render_template()` | FastHTML components (`Html`, `Div`, etc.) |
| **Database** | SQLAlchemy with Flask-SQLAlchemy | SQLAlchemy directly |

### Key Improvements

1. **No Template Files** — HTML is generated directly in Python, making it easier to embed logic and reuse components
2. **Faster Development** — One language throughout (Python), no template syntax context switching
3. **Better Type Hints** — Python functions naturally support type hints
4. **Cleaner Routing** — `@rt()` is more concise than `@app.route()`

## Installation

```bash
cd ~/Dropbox/ClaudeDocs/Projects/multifamilyCampaign/fastHTML
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

Server runs at `http://127.0.0.1:5000`

## File Structure

```
fastHTML/
├── app.py                 # Main FastHTML application with all routes
├── models.py               # SQLAlchemy database models (Property, AccessLog)
├── import_properties.py    # Load/refresh properties.db from a cleaned MLS spreadsheet
├── requirements.txt        # Python dependencies
├── Procfile                # Railway start command
└── README.md                # This file
```

## API Endpoints

- `GET /` — Main calculator page (pass `?ID=xxxxx` to look up a property by Property ID / APN)
- `GET /api/property/<property_id>` — Fetch property details as JSON
- `POST /api/export-pdf` — Generate and download PDF report
- `POST /api/log-session` — Log session duration

## Database

The app uses SQLite. Database file is created automatically in the current directory as `properties.db`.

### Tables

- **properties** — Property data: `property_id` (county APN, primary key), `sale_price` (→ Purchase Price), `sale_date` (reference only, not used in the calculator), `current_home_value` (→ Current Value), `property_address` / `city` / `zip_code` (shown at the top of the calculator page when present), plus mortgage/property-detail fields.
- **access_logs** — Track calculator usage by `property_id`.

`Cost to Sell (%)` is a fixed calculator default (6%) — it is not pulled from the database. `Estimated Mortgage Pay Off` is computed from `first_mortgage_amt` / `mortgage_rate` / `mortgage_date` via `calculate_mortgage_payoff()` in `app.py`; it shows $0 when those fields are empty (see `--estimate-mortgage`, below, to fill them).

### Updating the database

```bash
cd ~/Dropbox/ClaudeDocs/Projects/multifamilyCampaign/fastHTML
python import_properties.py /path/to/cleaned_scrapedData.xlsx --sheet "MLS Data"
```

This upserts by Property ID (inserts new ones, updates existing ones) from a spreadsheet with `Property ID`, `Sale Price`, `Sale Date`, and `Current Value` columns. If the sheet also has `Address`, `Property City`, and/or `Prop Zip` columns, those are imported too and displayed at the top of the calculator page (e.g. "4419 Spencer ST, Las Vegas 89119") -- they're optional, so a sheet without them still imports fine. Add `--dry-run` to preview counts without writing. After running it, commit and push `properties.db` to deploy the refresh to Railway (each redeploy resets `access_logs`, since Railway's disk isn't persistent across deploys).

#### Estimating mortgage payoff data

Add `--estimate-mortgage` to also fill `first_mortgage_amt`, `mortgage_rate`, and `mortgage_date` for any property that doesn't already have them:

```bash
python import_properties.py /path/to/cleaned_scrapedData.xlsx --estimate-mortgage
```

`estimate_mortgage()` in `import_properties.py` assumes 75% loan-to-value, a 30-year term, and that year's average 30-year fixed rate (a hardcoded table sourced from Bankrate/Freddie Mac historical data) as of the purchase date. These are rough estimates, not real loan data -- the LTV assumption in particular can be off by a wide margin for any individual property. It never overwrites a property's mortgage fields if they're already set.

## Notes

- All HTML generation is in the `calculator()` function in `app.py`
- JavaScript calculations remain client-side (no changes needed — complex enough to warrant keeping it)
- PDF export uses ReportLab (same as Flask version) and mirrors everything on the page: Address, Property Information, Scenario 1 (If You Sell), and Scenario 2 (1031 Exchange + Replacement Properties). The Scenario 2 figures are recomputed server-side from the same inputs, using the same formulas as the page's `calculate()` JS function.
- Database models use SQLAlchemy ORM directly (no Flask-SQLAlchemy wrapper)
- The session factory uses `expire_on_commit=False` — without it, logging an access (`session.commit()`) expires the `Property` object's attributes, and reading them again after `session.close()` raises `DetachedInstanceError`. This was live-crashing every successful property lookup before this fix.

## Differences from Flask Version

1. **No `templates/` directory** — All HTML is generated in Python
2. **Session management** — Manual session creation/closing instead of Flask-SQLAlchemy's app context
3. **File responses** — Use `FileResponse` instead of Flask's `send_file`
4. **Request handling** — `request.args` and `request.json` work the same, but imported from `fasthtml.common`

## Testing

Populate `properties.db` with `python import_properties.py <spreadsheet.xlsx>`, then run the app and visit `http://127.0.0.1:5000/?ID=<a property ID from the spreadsheet>`.
