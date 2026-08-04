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

- **properties** — Property data: `property_id` (county APN, primary key), `sale_price` (→ Purchase Price), `sale_date` (reference only, not used in the calculator), `current_home_value` (→ Current Value), plus mortgage/address/property-detail fields for future use.
- **access_logs** — Track calculator usage by `property_id`.

`Mortgage Pay Off` and `Cost to Sell (%)` are fixed calculator defaults ($0 and 6% respectively) — they are not pulled from the database. Mortgage Pay Off defaults to $0 by leaving `first_mortgage_amt` / `mortgage_rate` / `mortgage_date` unset for imported properties.

### Updating the database

```bash
cd ~/Dropbox/ClaudeDocs/Projects/multifamilyCampaign/fastHTML
python import_properties.py /path/to/cleaned_scrapedData.xlsx --sheet "MLS Data"
```

This upserts by Property ID (inserts new ones, updates existing ones) from a spreadsheet with `Property ID`, `Sale Price`, `Sale Date`, and `Current Value` columns. Add `--dry-run` to preview counts without writing. After running it, commit and push `properties.db` to deploy the refresh to Railway (each redeploy resets `access_logs`, since Railway's disk isn't persistent across deploys).

## Notes

- All HTML generation is in the `calculator()` function in `app.py`
- JavaScript calculations remain client-side (no changes needed — complex enough to warrant keeping it)
- PDF export uses ReportLab (same as Flask version)
- Database models use SQLAlchemy ORM directly (no Flask-SQLAlchemy wrapper)
- The session factory uses `expire_on_commit=False` — without it, logging an access (`session.commit()`) expires the `Property` object's attributes, and reading them again after `session.close()` raises `DetachedInstanceError`. This was live-crashing every successful property lookup before this fix.

## Differences from Flask Version

1. **No `templates/` directory** — All HTML is generated in Python
2. **Session management** — Manual session creation/closing instead of Flask-SQLAlchemy's app context
3. **File responses** — Use `FileResponse` instead of Flask's `send_file`
4. **Request handling** — `request.args` and `request.json` work the same, but imported from `fasthtml.common`

## Testing

Populate `properties.db` with `python import_properties.py <spreadsheet.xlsx>`, then run the app and visit `http://127.0.0.1:5000/?ID=<a property ID from the spreadsheet>`.
