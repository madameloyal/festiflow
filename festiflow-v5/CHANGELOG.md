# Festiflow — Changelog

---

## v5.0 — 2026-03-13 · Railway/SaaS Compatibility

### New files
| File | Description |
|---|---|
| `main.py` | FastAPI app deployed on Railway. Accepts file uploads + `event_id`, runs `run.py`, pushes generated HTML to GitHub Pages via the GitHub Contents API. |
| `upload.html` | Team-facing upload page hosted on GitHub Pages. Reads active events dynamically from `GET /events` — zero hardcoding. Password protected. |
| `requirements.txt` | Python dependencies for Railway (`fastapi`, `uvicorn`, `python-multipart`, `httpx`, `pandas`, `numpy`). |
| `railway.toml` | Railway deployment config. Starts with `uvicorn main:app`. |
| `README.md` | Step-by-step deployment guide. |

### Changes to `run.py`

#### 1. Environment variable overrides for input/output dirs
```python
# Before (v4.x):
RAW_DIR    = DATA_DIR / "raw"
OUTPUT_DIR = DATA_DIR / "output"

# After (v5.0):
RAW_DIR    = Path(os.environ["FESTIFLOW_RAW_DIR"])    if "FESTIFLOW_RAW_DIR"    in os.environ else DATA_DIR / "raw"
OUTPUT_DIR = Path(os.environ["FESTIFLOW_OUTPUT_DIR"]) if "FESTIFLOW_OUTPUT_DIR" in os.environ else DATA_DIR / "output"
```
Railway injects per-request temp directories so concurrent uploads never collide. Local usage is unchanged.

#### 2. `parse_datetime_dice()` — new function
```python
def parse_datetime_dice(date_str):
    """Parse DICE datetime: '2026-01-06 19:00' -> datetime object"""
```
DICE `Purchase date` was only parsed to a date string before. Now returns a full `datetime` object, enabling the "last ticket sold" timestamp to include DICE transactions.

#### 3. `order_datetime` in DICE ticket dicts
Each DICE ticket dict now includes:
```python
'order_datetime': parse_datetime_dice(row.get('Purchase date', ''))
```

#### 4. `order_datetime` preserved through `load_ticket_data()`
Previously the field was dropped when rebuilding ticket dicts inside `load_ticket_data()`. Now parsed back from string (CSV round-trip) and carried through to the final metrics calculation.

#### 5. `save_merged_csv()` — fieldnames updated
```python
# Before: 'order_date', 'ticket_type', ...
# After:  'order_date', 'order_datetime', 'ticket_type', ...
```

#### 6. `generation_time` set at file-write time
```python
# Before: generation_time set mid-pipeline, used as DATA_TIME placeholder
# After:  placeholder replaced immediately before open(output_path, 'w')
html = html.replace('{{GENERATION_TIME_PLACEHOLDER}}', datetime.now().strftime('%H:%M'))
```
Ensures the displayed upload timestamp matches when the file was actually written.

### Changes to `dashboard_template.html`

Header timestamp line updated from:
```
Dernier billet · {{LAST_TICKET_TIME}} · Généré à {{DATA_TIME}}
```
To:
```
🎟 Dernier billet vendu · {{LAST_TICKET_TIME}} · 📤 Données uploadées · {{DATA_TIME}}
```
Two clearly labelled timestamps — last transaction vs upload time.

---

## v4.5 — 2026-03-13 · Timestamp fixes (intermediate)
- `LAST_TICKET_TIME` placeholder wired up (was showing `—`)
- `generation_time` moved later in pipeline
- Superseded by v5.0 which completes these fixes

## v4.4 — 2026-03-12 · Dual counting system
- `is_paid` flag added to ticket dicts
- Paid tickets used for revenue/sales metrics
- All tickets (incl. free) used for attendance/capacity metrics

## v4.3 — Initial stable release
- DICE + Shotgun merge pipeline
- YoY comparison at same J-X point
- Scenario projections
- Velocity analysis
