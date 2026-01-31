"""
Universal Gateway API for document ingestion and query.

Provides a standardized interface for external sources (Procore, Google Drive,
Dropbox, SharePoint, etc.) to ingest documents and query the search index.

Components:
- schemas.py   - Pydantic models for request/response validation
- auth.py      - API key authentication and rate limiting
- jobs.py      - Async job queue with status tracking
- webhooks.py  - Callback notifications to sources
- api.py       - Route handlers for /api/v1/*
- health.py    - Unified health checks for all services
"""

from backend.gateway.schemas import (
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    JobStatus,
    HealthStatus,
    SourceType,
)
from backend.gateway.auth import APIKeyAuth, RateLimiter
from backend.gateway.jobs import JobQueue, Job
from backend.gateway.webhooks import WebhookNotifier

__all__ = [
    # Schemas
    "IngestRequest",
    "IngestResponse",
    "QueryRequest",
    "QueryResponse",
    "JobStatus",
    "HealthStatus",
    "SourceType",
    # Auth
    "APIKeyAuth",
    "RateLimiter",
    # Jobs
    "JobQueue",
    "Job",
    # Webhooks
    "WebhookNotifier",
]
