"""In-process job registry (spec §27, §28 `jobs` table).

A search takes minutes, so the HTTP request cannot stay open. §24 keeps Celery
and Redis out of the MVP, so jobs run on a small thread pool here and the
frontend polls GET /api/jobs/{job_id}.

Swapping this for Celery later means replacing `submit()` — the API surface and
the frontend contract stay the same.
"""
from __future__ import annotations

import logging
import re
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models import Lead, SearchRequest

log = logging.getLogger(__name__)

MAX_CONCURRENT_JOBS = 2
MAX_JOBS_RETAINED = 100


class JobCancelled(BaseException):
    """Cooperative cancellation signal.

    Deliberately derived from BaseException, not Exception: the pipeline wraps
    each business in `except Exception` to honour §35, which would otherwise
    swallow the cancellation and let the job run to completion.
    """


# Stage -> progress floor. The analyse stage reports "i/n" so its share is
# interpolated rather than jumping.
_STAGE_PROGRESS = {
    "queued": 0,
    "search": 10,
    "filter": 25,
    "website": 35,
    "analyse": 45,
    "pitch": 85,
    "export": 95,
    "done": 100,
}
_ANALYSE_SPAN = 40  # 45 -> 85
_COUNTER_RE = re.compile(r"^(\d+)/(\d+)")


@dataclass
class Job:
    id: str
    request: SearchRequest
    status: str = "queued"
    stage: str = "queued"
    message: str = ""
    progress: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    warnings: list[str] = field(default_factory=list)
    leads: list[Lead] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    csv_path: Optional[Path] = None
    evidence_path: Optional[Path] = None
    cancel_requested: bool = False
    _future: Optional[Future] = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {"completed", "partial", "failed", "empty", "cancelled"}


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_JOBS, thread_name_prefix="lead-job"
        )

    # ------------------------------------------------------------------ #

    def create(self, request: SearchRequest) -> Job:
        job = Job(id=f"job_{uuid.uuid4().hex[:12]}", request=request)
        with self._lock:
            self._jobs[job.id] = job
            self._evict_locked()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 50) -> list[Job]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def _evict_locked(self) -> None:
        """Drop the oldest finished jobs so a long-lived server does not grow
        without bound. Running jobs are never evicted."""
        if len(self._jobs) <= MAX_JOBS_RETAINED:
            return
        finished = sorted(
            (j for j in self._jobs.values() if j.is_terminal),
            key=lambda j: j.created_at,
        )
        for job in finished[: len(self._jobs) - MAX_JOBS_RETAINED]:
            self._jobs.pop(job.id, None)

    # ------------------------------------------------------------------ #

    def submit(self, job: Job, runner) -> None:
        """`runner(job)` does the real work; exceptions are recorded on the job."""

        def _wrapped() -> None:
            job.status = "running"
            try:
                runner(job)
            except JobCancelled:
                job.status = "cancelled"
                job.stage = "cancelled"
                job.message = "cancelled by user"
                log.info("job %s cancelled", job.id)
            except Exception as exc:  # noqa: BLE001 - surfaced to the client
                log.exception("job %s failed", job.id)
                job.status = "failed"
                job.stage = "failed"
                job.message = str(exc)
                job.warnings.append(str(exc))
            finally:
                job.completed_at = datetime.now(timezone.utc)
                if job.status in {"completed", "partial"}:
                    job.progress = 100

        job._future = self._pool.submit(_wrapped)

    def request_cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.is_terminal:
            return False
        job.cancel_requested = True
        # A queued job that never started can be dropped outright.
        if job._future is not None and job._future.cancel():
            job.status = "cancelled"
            job.stage = "cancelled"
            job.completed_at = datetime.now(timezone.utc)
        return True

    # ------------------------------------------------------------------ #

    @staticmethod
    def progress_callback(job: Job):
        """Built for LeadPipeline's `progress` hook.

        Doubles as the cancellation checkpoint: the pipeline calls this between
        stages and after every business, so raising here stops the run promptly
        without needing to kill a thread.
        """

        def report(stage: str, message: str) -> None:
            if job.cancel_requested:
                raise JobCancelled(job.id)

            job.stage = stage
            job.message = message
            base = _STAGE_PROGRESS.get(stage, job.progress)

            if stage == "analyse":
                match = _COUNTER_RE.match(message)
                if match:
                    done, total = int(match.group(1)), max(int(match.group(2)), 1)
                    base += int(_ANALYSE_SPAN * done / total)

            job.progress = max(job.progress, min(base, 99))
            log.info("[%s] %s: %s", job.id, stage, message)

        return report


store = JobStore()
