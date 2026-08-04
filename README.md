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
├── app.py           # Main FastHTML application with all routes
├── models.py        # SQLAlchemy database models (Property, AccessLog)
├── requirements.txt # Python dependencies
└── README.md        # This file
```

## API Endpoints

- `GET /` — Main calculator page (optionally pass `?apn=xxxxx` to look up a property)
- `GET /api/property/<apn>` — Fetch property details as JSON
- `POST /api/export-pdf` — Generate and download PDF report
- `POST /api/log-session` — Log session duration

## Database

The app uses SQLite. Database file is created automatically in the current directory as `properties.db`.

### Tables

- **properties** — Property data with mortgage and valuation info
- **access_logs** — Track calculator usage by APN

## Notes

- All HTML generation is in the `calculator_page()` function in `app.py`
- JavaScript calculations remain client-side (no changes needed — complex enough to warrant keeping it)
- PDF export uses ReportLab (same as Flask version)
- Database models use SQLAlchemy ORM directly (no Flask-SQLAlchemy wrapper)

## Differences from Flask Version

1. **No `templates/` directory** — All HTML is generated in Python
2. **Session management** — Manual session creation/closing instead of Flask-SQLAlchemy's app context
3. **File responses** — Use `FileResponse` instead of Flask's `send_file`
4. **Request handling** — `request.args` and `request.json` work the same, but imported from `fasthtml.common`

## Testing

To test with sample data, you'll need to populate the `properties` table first. Use a tool like DB Browser for SQLite or add a data loading script.
