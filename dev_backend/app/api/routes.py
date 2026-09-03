"""HTTP endpoints (spec §26).

    POST /api/search
    GET  /api/jobs/{job_id}
    GET  /api/jobs
    POST /api/search/{job_id}/cancel
    GET  /api/leads
    GET  /api/leads/{lead_id}
    GET  /api/leads/{lead_id}/reviews
    GET  /api/leads/{lead_id}/analysis
    GET  /api/export/csv

    POST   /api/sessions            save a finished job (§28)
    GET    /api/sessions
    GET    /api/sessions/{id}
    PATCH  /api/sessions/{id}       rename
    DELETE /api/sessions/{id}
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app import db
from app.config import settings
from app.models import SearchRequest
from app.pipeline import LeadPipeline
from app.schemas.api import (
    JobOut,
    LeadOut,
    LeadsResponse,
    SaveSessionBody,
    SearchAccepted,
    SearchBody,
    SessionDetail,
    SessionListResponse,
    SessionSummary,
    lead_id_for,
    saved_lead_to_out,
)
from app.services import session_store
from app.services.job_store import Job, store

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def _job_out(job: Job) -> JobOut:
    r = job.request
    return JobOut(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        message=job.message,
        progress=job.progress,
        location=r.location,
        category=r.category,
        min_rating=r.min_rating,
        max_rating=r.max_rating,
        minimum_reviews=r.minimum_reviews,
        requested_leads=r.limit,
        created_at=job.created_at,
        completed_at=job.completed_at,
        lead_count=len(job.leads),
        warnings=job.warnings,
        stats=job.stats,
        has_csv=job.csv_path is not None and job.csv_path.exists(),
    )


def _require_job(job_id: str) -> Job:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job_id: {job_id}")
    return job


def _run_search(job: Job) -> None:
    """Executed on the job pool. Never called from the request thread."""
    pipeline = LeadPipeline(progress=store.progress_callback(job))
    result = pipeline.run(job.request)

    job.leads = result.leads
    job.warnings = result.warnings
    job.stats = result.stats
    job.csv_path = result.csv_path
    job.evidence_path = result.evidence_path
    job.status = result.status
    job.stage = "done"
    job.message = f"{len(result.leads)} lead(s)"


# --- Search / jobs --------------------------------------------------------- #


@router.post("/search", response_model=SearchAccepted, status_code=202)
def start_search(body: SearchBody) -> SearchAccepted:
    """§27 — returns immediately with a job_id; the client polls for status."""
    request = SearchRequest(**body.model_dump())
    job = store.create(request)
    store.submit(job, _run_search)
    log.info("queued %s: %s / %s", job.id, request.category, request.location)
    return SearchAccepted(job_id=job.id, status=job.status)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(limit: int = Query(default=25, ge=1, le=100)) -> list[JobOut]:
    return [_job_out(j) for j in store.list(limit)]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str) -> JobOut:
    return _job_out(_require_job(job_id))


@router.post("/search/{job_id}/cancel", response_model=JobOut)
def cancel_search(job_id: str) -> JobOut:
    job = _require_job(job_id)
    if job.is_terminal:
        raise HTTPException(
            status_code=409, detail=f"job already finished with status '{job.status}'"
        )
    store.request_cancel(job_id)
    return _job_out(job)


# --- Leads ----------------------------------------------------------------- #


@router.get("/leads", response_model=LeadsResponse)
def get_leads(job_id: str = Query(...)) -> LeadsResponse:
    job = _require_job(job_id)
    return LeadsResponse(
        job_id=job.id,
        status=job.status,
        count=len(job.leads),
        leads=[LeadOut.from_lead(l) for l in job.leads],
    )


def _find_lead(job_id: str, lead_id: str):
    job = _require_job(job_id)
    for lead in job.leads:
        if lead_id_for(lead.business.place_id) == lead_id:
            return lead
    raise HTTPException(status_code=404, detail=f"unknown lead_id: {lead_id}")


@router.get("/leads/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: str, job_id: str = Query(...)) -> LeadOut:
    return LeadOut.from_lead(_find_lead(job_id, lead_id))


@router.get("/leads/{lead_id}/reviews")
def get_lead_reviews(lead_id: str, job_id: str = Query(...)) -> dict:
    """Every review that reached analysis, analysed or not."""
    lead = _find_lead(job_id, lead_id)
    return {
        "lead_id": lead_id,
        "company_name": lead.business.name,
        "reviews": [
            {
                "rating": r.rating,
                "text": r.text,
                "review_date": r.review_date,
                "review_url": r.review_url,
                "source": r.source,
            }
            for r in lead.business.reviews
        ],
    }


@router.get("/leads/{lead_id}/analysis")
def get_lead_analysis(lead_id: str, job_id: str = Query(...)) -> dict:
    """§33 — fact, interpretation and recommendation kept distinct."""
    lead = _find_lead(job_id, lead_id)
    return {
        "lead_id": lead_id,
        "company_name": lead.business.name,
        "analyses": [
            {
                "fact": {
                    "review_text": a.evidence_text,
                    "review_rating": a.evidence_rating,
                    "review_date": a.evidence_date,
                    "review_url": a.evidence_url,
                },
                "interpretation": {
                    "software_related": a.software_related,
                    "pain_point": a.pain_point,
                    "pain_category": a.pain_category,
                    "severity": a.severity,
                    "customer_impact": a.customer_impact,
                    "business_impact": a.business_impact,
                    "confidence": round(a.confidence, 2),
                },
                "recommendation": {
                    "solution": a.recommended_solution,
                    "solution_type": a.solution_type,
                },
            }
            for a in lead.analyses
        ],
        "opportunity": lead.opportunity.model_dump(),
        "scores": lead.scores.model_dump(),
    }


# --- Export ---------------------------------------------------------------- #


@router.get("/export/csv")
def export_csv(job_id: str = Query(...), kind: str = Query(default="leads")) -> FileResponse:
    job = _require_job(job_id)
    path = job.evidence_path if kind == "evidence" else job.csv_path
    if path is None or not path.exists():
        raise HTTPException(
            status_code=404,
            detail="no CSV for this job yet — it may still be running or have produced no leads",
        )
    return FileResponse(path, media_type="text/csv", filename=path.name)


# --- Saved sessions (§28) -------------------------------------------------- #


def _require_db() -> None:
    if not db.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Session saving is disabled — DATABASE_URL is not configured.",
        )


@router.post("/sessions", response_model=SessionDetail, status_code=201)
def save_session(body: SaveSessionBody) -> SessionDetail:
    """Persist a finished job. Explicit — nothing is saved without this call."""
    _require_db()
    job = _require_job(body.job_id)

    if not job.is_terminal:
        raise HTTPException(
            status_code=409,
            detail=f"Job is still {job.status}. Wait for it to finish before saving.",
        )
    if not job.leads:
        raise HTTPException(
            status_code=409, detail="This search produced no leads, so there is nothing to save."
        )

    try:
        new_id = session_store.save_session(job, body.name, llm_model=settings.llm_model)
    except Exception as exc:
        log.exception("failed to save session")
        raise HTTPException(status_code=502, detail=f"Could not save to the database: {exc}")

    return _session_detail(new_id)


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SessionListResponse:
    _require_db()
    rows, total = session_store.list_sessions(limit=limit, offset=offset)
    return SessionListResponse(
        total=total,
        count=len(rows),
        sessions=[SessionSummary.model_validate(r) for r in rows],
    )


def _session_detail(session_id: int) -> SessionDetail:
    row = session_store.get_session(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown session id: {session_id}")
    return SessionDetail(
        **SessionSummary.model_validate(row).model_dump(),
        max_places=row.max_places,
        strict_filters=row.strict_filters,
        warnings=list(row.warnings or []),
        stats=dict(row.stats or {}),
        leads=[saved_lead_to_out(l) for l in row.leads],
    )


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: int) -> SessionDetail:
    _require_db()
    return _session_detail(session_id)


@router.patch("/sessions/{session_id}", response_model=SessionDetail)
def rename_session(session_id: int, body: SaveSessionBody) -> SessionDetail:
    _require_db()
    if session_store.rename_session(session_id, body.name or "") is None:
        raise HTTPException(status_code=404, detail=f"unknown session id: {session_id}")
    return _session_detail(session_id)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int) -> None:
    _require_db()
    if not session_store.delete_session(session_id):
        raise HTTPException(status_code=404, detail=f"unknown session id: {session_id}")
