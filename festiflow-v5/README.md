# Festiflow — Dashboard Builder v4.3

**Festival analytics dashboard generator for Madame Loyal Festivals.**
Ingests raw DICE and Shotgun ticketing exports, merges and classifies ticket data, calculates sales metrics, and generates a self-contained HTML dashboard with year-over-year comparison.

Authors: Leo & Claude
Last updated: March 2026


## Project structure

```
festiflow-v4/
├── run.py                      Main pipeline script (3404 lines)
├── dashboard_template.html     HTML/CSS/JS template for the dashboard
├── event_config.csv            All events: metadata, days, capacities, relationships
├── csv_database/               Historical CSV exports for reuse across generations
│   ├── README.md               Database-specific documentation
│   ├── paris_xxl_2025/         Raw DICE zip + Shotgun CSVs + pre-merged reference
│   └── bordeaux_2025/          Raw DICE zip + Shotgun CSV + pre-merged reference
└── README.md                   This file
```


## Quick start

```bash
# 1. Place current + reference CSV files in data/raw/
mkdir -p data/raw
cp csv_database/paris_xxl_2025/*.zip data/raw/
cp csv_database/paris_xxl_2025/*.csv data/raw/
# + add new 2026 DICE zip and Shotgun CSV to data/raw/

# 2. Run the pipeline
python run.py

# 3. Output
# → data/output/dashboard_FINAL.html
```

The script auto-detects files by year and matches DICE + Shotgun pairs automatically.
Use `--event EVENT_ID` to force a specific event from config.


## Pipeline overview

The dashboard generation follows this sequence:

1. **File detection** — Scans `data/raw/` for DICE zips and Shotgun CSVs, matches them by year using date detection from file contents.
2. **Event config matching** — Maps Shotgun event IDs from filenames to `event_config.csv` entries. Determines current vs. comparison event.
3. **merge_into handling** — Automatically detects and appends Shotgun CSVs from child events (e.g. presale) to their parent event.
4. **DICE processing** — Extracts doorlist ZIP, reads all per-ticket-type CSVs, classifies tickets using the unified classifier.
5. **Shotgun processing** — Reads the Shotgun export, classifies from CATEGORY + DEAL TITLE, applies paid/free flag.
6. **Merge** — Combines DICE + Shotgun tickets into a single sorted dataset.
7. **Metrics calculation** — Computes KPIs: total sold, revenue, velocity, daily/weekly breakdowns, per-day attendance.
8. **Year-over-year comparison** — Filters previous year data to the same relative point in the sales cycle for fair comparison.
9. **Projection (Trajectoire model)** — Uses the reference event's historical curve to project final ticket counts and sellout dates.
10. **HTML generation** — Injects all data into the dashboard template and produces a self-contained HTML file.


## Key concepts

### Ticket classification

The unified `classify_ticket()` function handles all ticket name formats from both platforms. It extracts:
- **ticket_type**: day name (vendredi, samedi...), 2-jours, 3-jours, or single_day
- **access_level**: regular, vip, backstage, early_entry, invitation, jeu_concours, group_discount
- **attendance_days**: which festival days the ticket grants access to
- **is_paid**: 0 for invitations and contest wins, 1 for everything else

### merge_into

Some events have a separate presale phase with its own Shotgun event ID. In `event_config.csv`, these are marked with `merge_into` pointing to the parent event ID. The pipeline automatically detects matching CSVs in `data/raw/` and appends their tickets to the parent event during processing.

Example: `paris_xxl_2025_presale` (Shotgun ID 406642) has `merge_into: paris_xxl_2025`. When both CSVs are in `data/raw/`, the presale tickets are automatically included.

### compare_to

Defines the year-over-year reference event. For example, `paris_xxl_2026` has `compare_to: paris_xxl_2025`. The pipeline filters previous-year data to match the current sales timeline for fair comparison.

### Trajectoire model

The projection system uses a single reference event (defined by `compare_to`) to model the expected sales trajectory. It projects final ticket counts and estimated sellout dates based on how the reference event's curve played out.


## CSV database

The `csv_database/` folder stores historical exports so they can be reused without re-uploading each time. Each subfolder is named after the `event_id` from `event_config.csv` and contains:
- The raw DICE doorlist ZIP (as exported from the platform)
- The raw Shotgun CSV(s) (including presale CSVs if applicable)
- A pre-merged CSV for quick reference/inspection

When generating a new dashboard, copy the relevant raw files from `csv_database/` into `data/raw/` alongside the current-year exports.

### Current database contents

| Event | Folder | Tickets | Files |
|-------|--------|---------|-------|
| Paris XXL 2025 | `paris_xxl_2025/` | 33,155 | DICE zip + Shotgun main + Shotgun presale + merged |
| Sonora Bordeaux 2025 | `bordeaux_2025/` | 25,424 | DICE zip + Shotgun + merged |


## Event config

`event_config.csv` defines all events with their metadata. Key fields:

| Field | Description |
|-------|-------------|
| event_id | Unique identifier (e.g. `paris_xxl_2026`) |
| shotgun_event_id | Shotgun platform ID — used for auto-matching CSV filenames |
| dice_mio_id | DICE MIO platform ID |
| compare_to | event_id of the reference event for year-over-year comparison |
| merge_into | event_id of the parent event (for presales and child events) |
| status | `active` (current events) or `archive` (past events) |
| day_number, day_name, day_date, day_capacity | Multi-row day structure per event |


## Dashboard generation workflow (with Claude)

Current workflow when generating a dashboard via Claude:

1. Upload the latest DICE zip and Shotgun CSV for the current event
2. Claude copies reference files from `csv_database/` into `data/raw/`
3. Claude adds the uploaded current-year files to `data/raw/`
4. If the event has merge_into children (presale CSVs), those are also placed in `data/raw/`
5. Claude runs `python run.py` and delivers the output HTML

Future plan: web application with upload button where the user uploads the latest exports and the backend handles everything automatically.


## Version history

### v4.3 — March 2026
- **Dual projection scenarios**: Each day card now has a toggle between two projection models:
  - *Trajectoire [year]*: Pure replay of the reference event's remaining-day sales grafted onto current totals.
  - *[year] × coef. [current year]*: Reference event curve scaled by the 14d velocity ratio between current and reference event at the same J-X position.
- **Projection cards show projected values**: Progress bar and big number now display the projected total and fill percentage (not current sold). Swaps when toggling scenarios.
- **Projection floor**: Projected totals can never be below current sold — ensures logical consistency.
- **14d velocity for coefficient**: The coefficient scenario now uses 14d velocity instead of 7d for more stable projections. The coefficient is computed from the ratio of 14d velocities (current vs reference at same J-X).
- **Charts normalized to % capacity**: Projection charts now show percentage of capacity (0–100%) on the Y-axis. Both current and reference curves are normalized to their respective capacities, enabling fair visual comparison even when capacities differ (e.g. 19,000 vs 21,500).
- **Fixed 2025 reference curve**: Pre-chart-start sales are now pre-accumulated and event-day sales included, fixing an undercount that showed 2025 at ~71% instead of the correct ~89%.
- **Auto-matcher prefers largest CSV**: When multiple Shotgun CSVs share the same year, the auto-matcher now keeps the largest file (most complete export) instead of arbitrarily picking one.
- **Chart styling**: Actual sales line thinned to 1.5px. Projection lines now use yellow (matching the actual line) instead of cyan.
- **Projection title cleaned up**: Removed (i) tooltip from Projection Finale title.
- **Updated Logique tab**: Now explains both projection scenarios with methodology details.
- **Dashboard branding**: "Festiflow: Dashboard" displayed below header. Footer updated to v1.1.
- **Card hover glow**: KPI cards glow purple-indigo on hover, matching header gradient.
- **Compact header (Option A)**: Single-line header with expandable info panel.
- **Sticky navigation bar**: Vue d'ensemble · Répartition · Suivi · Projection with smooth scroll and active highlighting.

### v4.2 — March 2026
- **Compact header (Option A)**: Replaced the bulky multi-row header with a single-line layout — event name, brand, dates, badges, and an expandable "Info" toggle for venue/capacity/platforms/comparison details.
- **Sticky navigation bar**: Added a persistent top nav with smooth-scroll links to Vue d'ensemble, Répartition, Suivi, and Projection sections. Highlights active section on scroll.
- **Unified title styles**: KPI card labels and section titles now share identical font-size (0.75em), weight (600), and letter-spacing (2px).
- **Removed "Billetterie" divider**: Redundant section divider between KPI grid and Répartition removed.
- **Gradient border on header**: Purple-to-indigo gradient wraps the compact header card (2px).
- **Card hover glow**: KPI cards now glow with a purple-indigo shadow on hover, matching the header gradient.
- **Festiflow branding**: "Festiflow: Dashboard" displayed below the header. Footer updated to "Festiflow: Dashboard v1.1".
- **Removed "vs 2025" column**: Placeholder comparison column removed from Répartition des billets table.
- **Consistent "Cumulé" labels**: Daily view changed from "Acc." to "Cumulé" to match weekly view.
- **Weekly capacity percentages**: Each week shows `X.X% · Y.Y% cumulé` below SG/DICE breakdown.
- **Bigger year headers**: Suivi section year column headers increased to 0.78em.

### v4.1 — March 2026
- **Weekly capacity percentages**: Each week in the Suivi des ventes weekly view now shows `X.X% · Y.Y% cumulé` below the SG/DICE breakdown — weekly share of capacity and cumulative fill rate. Both years display percentages relative to their own total capacity.
- **Bigger year headers**: The year column headers in the Suivi section ("2025 (même jour)" / "2026 (actuel)") increased from 0.62em to 0.78em for better readability.
- **Consistent "Cumulé" label**: Daily view changed from "Acc." to "Cumulé" to match weekly view terminology.
- **Removed "vs 2025" column**: The placeholder comparison column in Répartition des billets has been removed. Table now has 4 clean columns: name, Total, %, Prix Ø.

### v4.0 — March 2026
- **CSV database system**: Added `csv_database/` folder structure for storing historical exports, organized by `event_id` from config. Stores both raw source files (DICE zip + Shotgun CSVs) and pre-merged reference CSVs.
- **merge_into pipeline support**: Added `find_merge_into_files()` function. The pipeline now automatically detects Shotgun CSVs belonging to child events (presales, etc.) and appends their tickets to the parent event during processing. Works for both current and previous year data.
- **Version alignment**: Fixed version references throughout `run.py` — header docstring and runtime banner now correctly read v4.0.
- **Database contents**: Paris XXL 2025 (33,155 tickets incl. presale) and Sonora Bordeaux 2025 (25,424 tickets).

### v3.2 (base for v4)
- Single Trajectoire model for reference events
- Standard festival profile with disclaimer for no-reference events
- Real cumulative chart data
- No dual S1/S2 toggle
- Collapsible ticket group breakdown
- Velocity and revenue charts with YoY overlay
- Dual cutoff system (cumulative vs. velocity)

### v2.0
- Initial single-script pipeline
- DICE + Shotgun merge with unified ticket classifier
- `is_paid` flag for paid/free ticket distinction
- HTML dashboard template with Chart.js visualizations


## Future features (planned)

### Cross-event comparison dropdown
Allow users to select any past event as the comparison reference, not just the hardcoded `compare_to` event. Scope:
- **Suivi weekly view**: Swap the left column to show the selected event's weekly sales, with `% cumulé` relative to that event's own capacity. Works because percentages normalize across different venue sizes.
- **Projection section**: "Trajectoire [event]" uses the selected event's remaining-day pattern. Coefficient scenario uses velocity ratio against the selected event. Charts already normalized to % capacity so this works visually.
- **Implementation**: Pre-compute data for each selectable reference event and embed as JSON in the HTML. Dropdown triggers JS swap of weekly rows and projection data. Requires CSV data for each selectable event in `csv_database/`.
- **KPI cards and daily view** stay on the default `compare_to` event (absolute comparisons).

### Early-launch projection guard
Add a minimum data threshold (e.g. 14 days of sales) before showing projections. Currently, generating a dashboard 7 days after launch will show projections based on very low/unstable velocity data without any warning.

### Web application
Upload-based UI where the user selects an event, uploads DICE zip + Shotgun CSV, and the backend generates the dashboard automatically. The `csv_database/` becomes backend storage, `event_config.csv` becomes a database table or admin panel.


## Technical notes

- **Python 3.10+** required. No external dependencies beyond the standard library.
- **Template**: `dashboard_template.html` uses Chart.js (loaded via CDN) for all visualizations.
- **Output**: Single self-contained HTML file — no server needed, opens in any browser.
- **DICE fee**: Net price calculated as gross × 0.9435 (~5.65% platform fee).
- **Shotgun price**: Uses PRIX HT (net revenue) directly from the export.
- **run.py**: 3,219 lines. Monolithic by design for portability — no module dependencies.
