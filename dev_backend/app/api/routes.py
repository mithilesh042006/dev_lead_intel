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

    POST   /api/saved-leads         save the leads the user selected (§28)
    GET    /api/saved-leads
    GET    /api/saved-leads/ids      which leads are already saved
    GET    /api/saved-leads/options  vocabularies for the manual form
    POST   /api/saved-leads/manual   add a lead by hand
    GET    /api/saved-leads/export/csv   all saved leads as CSV

    GET    /api/dashboard           pipeline rollup + worklists
    GET    /api/saved-leads/{lead_id}
    DELETE /api/saved-leads/{lead_id}

    GET    /api/saved-leads/{lead_id}/followups
    POST   /api/saved-leads/{lead_id}/followups
    DELETE /api/saved-leads/{lead_id}/followups/{followup_id}
"""
from __future__ import annotations

import logging

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app import db
from app.config import settings
from app.models import PAIN_CATEGORIES, SearchRequest
from app.pipeline import LeadPipeline
from app.schemas.api import (
    DashboardOut,
    ManualLeadBody,
    ManualLeadOptions,
    FollowUpBody,
    FollowUpOut,
    FollowUpsResponse,
    JobOut,
    LeadOut,
    LeadsResponse,
    SaveLeadsBody,
    SaveLeadsResult,
    SavedLeadOut,
    SavedLeadsResponse,
    SearchAccepted,
    SearchBody,
    lead_id_for,
    saved_lead_to_out,
)
from app.services import export_service, saved_leads_store
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
def export_csv(job_id: str = Query(...), kind: str = Query(default="leads")) -> Response:
    """Built from the job's leads in memory, not read back from `data/out`.

    The pipeline still writes those files for the CLI, but serving from disk
    would break on any host with an ephemeral filesystem.
    """
    job = _require_job(job_id)
    if not job.leads:
        raise HTTPException(
            status_code=404,
            detail="no CSV for this job yet — it may still be running or have produced no leads",
        )

    body = export_service.leads_csv(job.leads, kind)
    suffix = "_evidence" if kind == "evidence" else ""
    filename = f"leads_{job.created_at.strftime('%Y%m%d_%H%M%S')}{suffix}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Saved leads (§28) ----------------------------------------------------- #
#
# Deliberately on their own /saved-leads prefix rather than under /leads: a
# path like /leads/saved would collide with /leads/{lead_id} and only work by
# accident of registration order.


def _require_db() -> None:
    if not db.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Saving leads is disabled — DATABASE_URL is not configured.",
        )


@router.post("/saved-leads", response_model=SaveLeadsResult, status_code=201)
def save_leads(body: SaveLeadsBody) -> SaveLeadsResult:
    """Save the selected leads. Nothing is stored without this call."""
    _require_db()
    job = _require_job(body.job_id)

    if not job.is_terminal:
        raise HTTPException(
            status_code=409,
            detail=f"Job is still {job.status}. Wait for it to finish before saving.",
        )

    wanted = set(body.lead_ids)
    selected = [l for l in job.leads if lead_id_for(l.business.place_id) in wanted]
    if not selected:
        raise HTTPException(
            status_code=404, detail="None of those lead ids belong to this job."
        )

    try:
        outcome = saved_leads_store.save_leads(
            selected,
            {
                "job_id": job.id,
                "location": job.request.location,
                "category": job.request.category,
                "llm_model": settings.llm_model,
            },
        )
    except Exception as exc:
        log.exception("failed to save leads")
        raise HTTPException(status_code=502, detail=f"Could not save to the database: {exc}")

    return SaveLeadsResult(
        created=outcome.created, updated=outcome.updated, lead_ids=outcome.lead_ids
    )


@router.get("/saved-leads", response_model=SavedLeadsResponse)
def list_saved_leads(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> SavedLeadsResponse:
    _require_db()
    rows, total = saved_leads_store.list_saved(limit=limit, offset=offset)
    return SavedLeadsResponse(
        total=total, count=len(rows), leads=[saved_lead_to_out(r) for r in rows]
    )


@router.get("/saved-leads/ids", response_model=list[str])
def saved_lead_ids() -> list[str]:
    """Lets the results page show already-saved leads as ticked."""
    if not db.is_configured():
        return []  # not an error: the UI simply shows nothing as saved
    return sorted(saved_leads_store.saved_ids())


@router.get("/saved-leads/options", response_model=ManualLeadOptions)
def manual_lead_options() -> ManualLeadOptions:
    """Vocabularies for the manual-entry form, so the frontend never hardcodes
    a list that the backend then rejects."""
    return ManualLeadOptions(
        pain_categories=list(PAIN_CATEGORIES),
        severities=["high", "medium", "low"],
        priorities=["HOT", "WARM", "COLD", "LOW"],
    )


@router.post("/saved-leads/manual", response_model=SavedLeadOut, status_code=201)
def create_manual_lead(body: ManualLeadBody) -> SavedLeadOut:
    """Add a lead by hand — one the pipeline never found.

    Always creates a new row. Unlike a pipeline save, there is no place id to
    merge on, so two entries for the same business are the user's call.
    """
    _require_db()
    try:
        row = saved_leads_store.create_manual_lead(body.model_dump())
    except Exception as exc:
        log.exception("failed to create manual lead")
        raise HTTPException(status_code=502, detail=f"Could not save to the database: {exc}")
    return saved_lead_to_out(row)


@router.get("/saved-leads/export/csv")
def export_saved_leads_csv() -> Response:
    """Every saved lead, one row each, with full detail.

    Declared before /saved-leads/{lead_id} so "export" is never matched as a
    lead id. Built in memory rather than written to disk — there is nothing to
    clean up afterwards.
    """
    _require_db()
    rows, _ = saved_leads_store.list_saved(limit=5000)
    if not rows:
        raise HTTPException(status_code=404, detail="There are no saved leads to export.")

    body = export_service.saved_leads_csv(rows)
    filename = f"saved_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/saved-leads/{lead_id}", response_model=SavedLeadOut)
def get_saved_lead(lead_id: str) -> SavedLeadOut:
    """One saved lead in full. Registered after /saved-leads/ids so that
    literal path is not swallowed by this parameterised one."""
    _require_db()
    row = saved_leads_store.get_saved(lead_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} is not saved")
    return saved_lead_to_out(row)


@router.delete("/saved-leads/{lead_id}", status_code=204)
def delete_saved_lead(lead_id: str) -> None:
    _require_db()
    if not saved_leads_store.delete_saved(lead_id):
        raise HTTPException(status_code=404, detail=f"lead {lead_id} is not saved")


# --- Follow-ups ------------------------------------------------------------ #
#
# Nested under the lead they belong to, so a follow-up can never be created
# against a lead that was never saved.


@router.get("/saved-leads/{lead_id}/followups", response_model=FollowUpsResponse)
def list_followups(lead_id: str) -> FollowUpsResponse:
    _require_db()
    rows = saved_leads_store.list_followups(lead_id)
    if rows is None:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} is not saved")
    return FollowUpsResponse(
        lead_id=lead_id,
        count=len(rows),
        followups=[FollowUpOut.model_validate(r) for r in rows],
    )


@router.post(
    "/saved-leads/{lead_id}/followups", response_model=FollowUpOut, status_code=201
)
def add_followup(lead_id: str, body: FollowUpBody) -> FollowUpOut:
    _require_db()
    entry = saved_leads_store.add_followup(lead_id, body.model_dump())
    if entry is None:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} is not saved")
    return FollowUpOut.model_validate(entry)


@router.delete("/saved-leads/{lead_id}/followups/{followup_id}", status_code=204)
def delete_followup(lead_id: str, followup_id: int) -> None:
    _require_db()
    if not saved_leads_store.delete_followup(lead_id, followup_id):
        raise HTTPException(status_code=404, detail="no such follow-up on this lead")


# --- Dashboard ------------------------------------------------------------- #


@router.get("/dashboard", response_model=DashboardOut)
def dashboard() -> DashboardOut:
    """Rollup of the saved-lead pipeline, plus what needs acting on today.

    Aggregated server-side so the page does not download every lead just to
    count them.
    """
    _require_db()
    return DashboardOut(**saved_leads_store.dashboard_stats(date.today()))
