"""
FESTIFLOW — Railway API
========================
Receives uploaded CSV/ZIP files + event_id,
runs the dashboard pipeline, pushes output HTML to GitHub Pages.
"""

import os
import csv
import shutil
import subprocess
import tempfile
import base64
from pathlib import Path
from datetime import datetime

import httpx
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent / "festiflow-v4"
CONFIG_PATH = BASE_DIR / "event_config.csv"
RUN_PY      = BASE_DIR / "run.py"

# ─── Env vars (set in Railway dashboard) ─────────────────────────────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")        # Personal Access Token
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "")         # e.g. madameloyal/festiflow
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
UPLOAD_PASSWORD = os.environ.get("UPLOAD_PASSWORD", "")  # Simple shared password

# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="Festiflow API", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # GitHub Pages origin
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_active_events() -> list[dict]:
    """Read event_config.csv and return all active, non-merge events."""
    events = {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row.get("event_id", "").strip()
            if not eid:
                continue
            status = row.get("status", "").strip()
            merge_into = row.get("merge_into", "").strip()
            if status != "active" or merge_into:
                continue
            if eid not in events:
                # output_filename can be set in event_config.csv to override
                # the default {event_id}.html (e.g. "bordeaux.html")
                output_filename = row.get("output_filename", "").strip() or f"{eid}.html"
                events[eid] = {
                    "event_id":       eid,
                    "event_name":     row.get("event_name", "").strip(),
                    "brand":          row.get("brand", "").strip(),
                    "venue":          row.get("venue", "").strip(),
                    "city":           row.get("city", "").strip(),
                    "output_filename": output_filename,
                    "days":           [],
                }
            day_date = row.get("day_date", "").strip()
            day_name = row.get("day_name", "").strip()
            if day_date:
                events[eid]["days"].append({"name": day_name, "date": day_date})

    # Build a friendly date range string per event
    result = []
    for ev in events.values():
        dates = sorted(d["date"] for d in ev["days"] if d["date"])
        if dates:
            def fmt(d):
                try:
                    dt = datetime.strptime(d, "%Y-%m-%d")
                    months = ["Jan","Fév","Mar","Avr","Mai","Jun",
                              "Jul","Aoû","Sep","Oct","Nov","Déc"]
                    return f"{dt.day} {months[dt.month-1]} {dt.year}"
                except ValueError:
                    return d
            if len(dates) == 1:
                ev["date_range"] = fmt(dates[0])
            else:
                ev["date_range"] = f"{fmt(dates[0])} – {fmt(dates[-1])}"
            ev["first_date"] = dates[0]
        else:
            ev["date_range"] = ""
            ev["first_date"] = "9999-99-99"
        result.append(ev)

    # Sort by first event date
    result.sort(key=lambda e: e["first_date"])
    return result


def github_push(event_id: str, html_content: str) -> dict:
    """Push generated HTML to GitHub Pages via the GitHub Contents API."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {"ok": False, "error": "GITHUB_TOKEN or GITHUB_REPO not configured"}

    # Use output_filename from config if available, else fallback to {event_id}.html
    ev = next((e for e in load_active_events() if e["event_id"] == event_id), None)
    filename = ev["output_filename"] if ev else f"{event_id}.html"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Check if file already exists (need its SHA to update)
    sha = None
    r = httpx.get(api_url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")

    payload = {
        "message": f"Festiflow: update {event_id} dashboard [{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC]",
        "content": base64.b64encode(html_content.encode("utf-8")).decode("utf-8"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    r = httpx.put(api_url, headers=headers, json=payload, timeout=30)
    if r.status_code in (200, 201):
        return {"ok": True, "url": f"https://{GITHUB_REPO.split('/')[0]}.github.io/{GITHUB_REPO.split('/')[1]}/{filename}"}
    else:
        return {"ok": False, "error": r.text}


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/events")
def get_events():
    """Return all active events from event_config.csv."""
    try:
        return load_active_events()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate")
async def generate(
    event_id:     str      = Form(...),
    password:     str      = Form(...),
    dice_file:    UploadFile = File(...),
    shotgun_file: UploadFile = File(...),
):
    # ── Auth ──────────────────────────────────────────────────────────────────
    if UPLOAD_PASSWORD and password != UPLOAD_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")

    # ── Validate event_id exists in config ───────────────────────────────────
    active_ids = [e["event_id"] for e in load_active_events()]
    if event_id not in active_ids:
        raise HTTPException(status_code=400, detail=f"Événement inconnu: {event_id}")

    # ── Write uploaded files to a temp raw dir ───────────────────────────────
    tmp = Path(tempfile.mkdtemp(prefix="festiflow_"))
    raw_dir  = tmp / "raw"
    raw_dir.mkdir()

    try:
        # DICE zip
        dice_path = raw_dir / dice_file.filename
        with open(dice_path, "wb") as f:
            f.write(await dice_file.read())

        # Shotgun CSV
        sg_path = raw_dir / shotgun_file.filename
        with open(sg_path, "wb") as f:
            f.write(await shotgun_file.read())

        # Copy reference CSVs (csv_database) into raw dir for comparison year
        db_dir = BASE_DIR / "csv_database"
        for event_folder in db_dir.iterdir():
            if event_folder.is_dir():
                for ref_file in event_folder.iterdir():
                    if ref_file.suffix in (".csv", ".zip"):
                        shutil.copy(ref_file, raw_dir / ref_file.name)

        # ── Run the pipeline ─────────────────────────────────────────────────
        env = os.environ.copy()
        env["FESTIFLOW_RAW_DIR"] = str(raw_dir)
        env["FESTIFLOW_OUTPUT_DIR"] = str(tmp / "output")
        (tmp / "output").mkdir()

        result = subprocess.run(
            ["python3", str(RUN_PY), "--event", event_id],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=str(BASE_DIR),
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Pipeline error:\n{result.stderr[-2000:]}"
            )

        # ── Read generated HTML ───────────────────────────────────────────────
        output_html = tmp / "output" / "dashboard_FINAL.html"
        if not output_html.exists():
            # Fallback: check default location
            output_html = BASE_DIR / "data" / "output" / "dashboard_FINAL.html"

        if not output_html.exists():
            raise HTTPException(status_code=500, detail="Dashboard HTML not found after pipeline run")

        html_content = output_html.read_text(encoding="utf-8")

        # ── Push to GitHub Pages ──────────────────────────────────────────────
        push_result = github_push(event_id, html_content)
        if not push_result["ok"]:
            raise HTTPException(status_code=500, detail=f"GitHub push failed: {push_result['error']}")

        return JSONResponse({
            "ok": True,
            "event_id": event_id,
            "dashboard_url": push_result["url"],
            "generated_at": datetime.utcnow().isoformat(),
        })

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
