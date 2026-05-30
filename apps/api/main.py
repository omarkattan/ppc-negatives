"""FastAPI application for the negative keyword tool.

One service serves both the JSON API and the static frontend, which keeps
deployment to a single Render web service. The app is base-path aware: set
BASE_PATH (for example /ppc-negatives) when mounting under a sub-path behind a
reverse proxy, and ROOT_PATH so generated docs URLs are correct. Optional HTTP
basic auth guards the whole app when BASIC_AUTH_USER / BASIC_AUTH_PASS are set,
because this processes client PPC data and should not sit naked on the internet.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

import sys
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))                                  # apps/api (csv_io, web)
sys.path.insert(0, str(_HERE / "services"))                     # negative_keywords
sys.path.insert(0, str(_HERE.parents[1] / "packages" / "shared"))  # ppc_shared

from negative_keywords.engine import run_engine  # noqa: E402
from negative_keywords.models import EngineConfig  # noqa: E402
from csv_io import export_negatives_csv, parse_search_terms  # noqa: E402

BASE_PATH = os.environ.get("BASE_PATH", "").rstrip("/")   # e.g. "/ppc-negatives" or ""
ROOT_PATH = os.environ.get("ROOT_PATH", BASE_PATH)
WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="PPC Negative Keyword Tool", root_path=ROOT_PATH)

# --- optional basic auth -----------------------------------------------------
_security = HTTPBasic(auto_error=False)
_USER = os.environ.get("BASIC_AUTH_USER")
_PASS = os.environ.get("BASIC_AUTH_PASS")


def require_auth(credentials: HTTPBasicCredentials | None = Depends(_security)):
    if not _USER:        # auth disabled when no user configured
        return
    if credentials is None or not (
        secrets.compare_digest(credentials.username, _USER)
        and secrets.compare_digest(credentials.password, _PASS or "")
    ):
        raise HTTPException(status_code=401, detail="Unauthorised",
                            headers={"WWW-Authenticate": "Basic"})


def _csv_list(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


@app.get("/health")
def health():
    return {"status": "ok", "base_path": BASE_PATH}


@app.get("/", response_class=HTMLResponse)
def index(_=Depends(require_auth)):
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    # Inject base href so relative asset/fetch URLs resolve under any mount point.
    base_href = (BASE_PATH + "/") if BASE_PATH else "/"
    return html.replace("__BASE_HREF__", base_href)


@app.post("/api/recommend")
async def recommend(
    file: UploadFile = File(...),
    currency: str = Form("AED"),
    target_cpa: str = Form(""),
    brand_whitelist: str = Form(""),
    positive_keywords: str = Form(""),
    competitor_terms: str = Form(""),
    _=Depends(require_auth),
):
    raw = await file.read()
    terms = parse_search_terms(raw)
    if not terms:
        raise HTTPException(status_code=422,
                            detail="No search terms parsed. Check the file has a 'Search term' column.")
    cfg = EngineConfig(
        currency=currency or "AED",
        target_cpa=float(target_cpa) if target_cpa.strip() else None,
        brand_whitelist=_csv_list(brand_whitelist),
        positive_keywords=_csv_list(positive_keywords),
        competitor_terms=_csv_list(competitor_terms),
    )
    run = run_engine("uploaded_account", terms, cfg)
    return {
        "summary": run.summary(),
        "params": run.params,
        "recommendations": [r.model_dump(mode="json") for r in run.recommendations],
    }


@app.post("/api/export", response_class=PlainTextResponse)
async def export(payload: dict, _=Depends(require_auth)):
    csv_text = export_negatives_csv(payload.get("recommendations", []))
    return PlainTextResponse(
        csv_text, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=negatives.csv"},
    )


# Serve any additional static assets relatively (kept minimal for the MVP).
if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
