"""
Async job queue for document ingestion.

Provides:
- Job creation and tracking
- Async processing with status updates
- Persistence for job state (SQLite)
"""

import asyncio
import sqlite3
import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from backend.core.config import get
from backend.core.logging_config import get_logger
from backend.gateway.schemas import (
    IngestRequest,
    JobState,
    JobStatus,
    SourceInfo,
    Priority,
)

logger = get_logger(__name__)

# Job storage directory
JOBS_DIR = Path(get("app", "data_dir", fallback="data")) / "jobs"
JOBS_DB = JOBS_DIR / "jobs.db"


@dataclass
class Job:
    """Represents an ingestion job."""
    job_id: str
    source: SourceInfo
    request: IngestRequest
    state: JobState = JobState.QUEUED
    priority: Priority = Priority.NORMAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = None
    retries: int = 0
    max_retries: int = 3

    def to_status(self) -> JobStatus:
        """Convert to JobStatus response model."""
        return JobStatus(
            job_id=self.job_id,
            state=self.state,
            source=self.source,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            progress=self.progress,
            message=self.message,
            error=self.error,
            result=self.result,
        )


class JobStore:
    """
    SQLite-backed job storage.

    Persists job state for recovery after restarts.
    """

    def __init__(self, db_path: Path = JOBS_DB):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    progress REAL DEFAULT 0,
                    message TEXT DEFAULT '',
                    error TEXT,
                    result TEXT,
                    request TEXT NOT NULL,
                    webhook_url TEXT,
                    retries INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source_type, source_id)
            """)
            conn.commit()

    @contextmanager
    def _get_conn(self):
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save(self, job: Job):
        """Save or update a job."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jobs (
                    job_id, source_type, source_id, state, priority,
                    created_at, started_at, completed_at, progress,
                    message, error, result, request, webhook_url, retries
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id,
                job.source.type.value,
                job.source.id,
                job.state.value,
                job.priority.value,
                job.created_at.isoformat(),
                job.started_at.isoformat() if job.started_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
                job.progress,
                job.message,
                job.error,
                json.dumps(job.result) if job.result else None,
                job.request.model_dump_json(),
                job.webhook_url,
                job.retries,
            ))
            conn.commit()

    def get(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row:
                return self._row_to_job(row)
        return None

    def get_by_state(self, state: JobState, limit: int = 100) -> List[Job]:
        """Get jobs by state."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE state = ? ORDER BY created_at LIMIT ?",
                (state.value, limit)
            ).fetchall()
            return [self._row_to_job(row) for row in rows]

    def get_queued(self, limit: int = 10) -> List[Job]:
        """Get queued jobs ordered by priority and creation time."""
        with self._get_conn() as conn:
            # Priority order: high=0, normal=1, low=2
            rows = conn.execute("""
                SELECT * FROM jobs
                WHERE state = 'queued'
                ORDER BY
                    CASE priority
                        WHEN 'high' THEN 0
                        WHEN 'normal' THEN 1
                        WHEN 'low' THEN 2
                    END,
                    created_at
                LIMIT ?
            """, (limit,)).fetchall()
            return [self._row_to_job(row) for row in rows]

    def get_for_source(
        self,
        source_type: str,
        source_id: str,
        limit: int = 100
    ) -> List[Job]:
        """Get jobs for a specific source."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM jobs
                   WHERE source_type = ? AND source_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (source_type, source_id, limit)
            ).fetchall()
            return [self._row_to_job(row) for row in rows]

    def delete_old(self, days: int = 7):
        """Delete completed jobs older than N days."""
        with self._get_conn() as conn:
            conn.execute("""
                DELETE FROM jobs
                WHERE state IN ('completed', 'failed', 'cancelled')
                AND datetime(completed_at) < datetime('now', ?)
            """, (f'-{days} days',))
            conn.commit()

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert a database row to a Job object."""
        request = IngestRequest.model_validate_json(row['request'])
        return Job(
            job_id=row['job_id'],
            source=request.source,
            request=request,
            state=JobState(row['state']),
            priority=Priority(row['priority']),
            created_at=datetime.fromisoformat(row['created_at']),
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            progress=row['progress'],
            message=row['message'] or "",
            error=row['error'],
            result=json.loads(row['result']) if row['result'] else None,
            webhook_url=row['webhook_url'],
            retries=row['retries'],
        )


class JobQueue:
    """
    Async job queue for document ingestion.

    Manages job lifecycle:
    1. Create job (queued)
    2. Pick up job (processing)
    3. Execute processor
    4. Complete/fail job
    5. Send webhook notification
    """

    def __init__(
        self,
        processor: Optional[Callable] = None,
        max_workers: int = 4,
        poll_interval: float = 1.0,
    ):
        self.store = JobStore()
        self.processor = processor
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = False
        self._active_jobs: Dict[str, Job] = {}

    def create_job(self, request: IngestRequest) -> Job:
        """Create a new ingestion job."""
        job_id = f"ing_{uuid.uuid4().hex[:12]}"
        job = Job(
            job_id=job_id,
            source=request.source,
            request=request,
            priority=request.options.priority,
            webhook_url=str(request.options.webhook_url) if request.options.webhook_url else None,
        )
        self.store.save(job)
        logger.info(f"Created job {job_id} for {request.source.type.value}/{request.source.id}")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        # Check active jobs first
        if job_id in self._active_jobs:
            return self._active_jobs[job_id]
        return self.store.get(job_id)

    def update_progress(self, job_id: str, progress: float, message: str = ""):
        """Update job progress."""
        job = self.get_job(job_id)
        if job:
            job.progress = min(1.0, max(0.0, progress))
            job.message = message
            self.store.save(job)

    def complete_job(self, job_id: str, result: Dict[str, Any]):
        """Mark a job as completed."""
        job = self.get_job(job_id)
        if job:
            job.state = JobState.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress = 1.0
            job.result = result
            job.message = "Completed successfully"
            self.store.save(job)
            self._active_jobs.pop(job_id, None)
            logger.info(f"Job {job_id} completed")

    def fail_job(self, job_id: str, error: str, retry: bool = True):
        """Mark a job as failed."""
        job = self.get_job(job_id)
        if job:
            if retry and job.retries < job.max_retries:
                job.retries += 1
                job.state = JobState.QUEUED
                job.error = f"Retry {job.retries}/{job.max_retries}: {error}"
                logger.warning(f"Job {job_id} failed, will retry: {error}")
            else:
                job.state = JobState.FAILED
                job.completed_at = datetime.utcnow()
                job.error = error
                logger.error(f"Job {job_id} failed permanently: {error}")
            self.store.save(job)
            self._active_jobs.pop(job_id, None)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if it's still queued."""
        job = self.get_job(job_id)
        if job and job.state == JobState.QUEUED:
            job.state = JobState.CANCELLED
            job.completed_at = datetime.utcnow()
            job.message = "Cancelled by user"
            self.store.save(job)
            logger.info(f"Job {job_id} cancelled")
            return True
        return False

    async def start(self):
        """Start the job queue processor."""
        if self._running:
            return
        self._running = True
        logger.info("Job queue started")

        # Recover any jobs that were processing when we stopped
        processing = self.store.get_by_state(JobState.PROCESSING)
        for job in processing:
            job.state = JobState.QUEUED
            job.started_at = None
            self.store.save(job)
            logger.info(f"Recovered job {job.job_id} to queued state")

        # Start processing loop
        asyncio.create_task(self._process_loop())

    async def stop(self):
        """Stop the job queue processor."""
        self._running = False
        self._executor.shutdown(wait=True)
        logger.info("Job queue stopped")

    async def _process_loop(self):
        """Main processing loop."""
        while self._running:
            # Check for available capacity
            active_count = len(self._active_jobs)
            if active_count >= self.max_workers:
                await asyncio.sleep(self.poll_interval)
                continue

            # Get queued jobs
            available_slots = self.max_workers - active_count
            jobs = self.store.get_queued(limit=available_slots)

            for job in jobs:
                if not self._running:
                    break
                await self._start_job(job)

            await asyncio.sleep(self.poll_interval)

    async def _start_job(self, job: Job):
        """Start processing a job."""
        job.state = JobState.PROCESSING
        job.started_at = datetime.utcnow()
        self.store.save(job)
        self._active_jobs[job.job_id] = job

        logger.info(f"Starting job {job.job_id}")

        # Run processor in thread pool
        loop = asyncio.get_event_loop()
        try:
            if self.processor:
                await loop.run_in_executor(
                    self._executor,
                    self._run_processor,
                    job
                )
            else:
                # No processor set, just complete
                self.complete_job(job.job_id, {"status": "no_processor"})
        except Exception as e:
            self.fail_job(job.job_id, str(e))

    def _run_processor(self, job: Job):
        """Run the job processor (in thread pool)."""
        try:
            result = self.processor(job, self)
            self.complete_job(job.job_id, result)
        except Exception as e:
            logger.exception(f"Job {job.job_id} processor error")
            self.fail_job(job.job_id, str(e))

    def set_processor(self, processor: Callable):
        """Set the job processor function."""
        self.processor = processor


# Global job queue instance
job_queue = JobQueue()
