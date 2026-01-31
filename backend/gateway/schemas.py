"""
Pydantic schemas for the Universal Gateway API.

Defines request/response models for ingestion, query, and status endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


class SourceType(str, Enum):
    """Supported document sources."""
    PROCORE = "procore"
    GDRIVE = "gdrive"
    DROPBOX = "dropbox"
    SHAREPOINT = "sharepoint"
    S3 = "s3"
    DIRECT = "direct"  # Direct API upload


class Priority(str, Enum):
    """Ingestion priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class JobState(str, Enum):
    """Job processing states."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RankingMethod(str, Enum):
    """Search ranking methods."""
    BM25 = "bm25"
    COLPALI = "colpali"
    HYBRID = "hybrid"


# =============================================================================
# Ingestion Schemas
# =============================================================================

class SourceInfo(BaseModel):
    """Information about the document source."""
    type: SourceType = Field(..., description="Source system type")
    id: str = Field(..., description="Source-specific identifier (e.g., project ID)")
    path: Optional[str] = Field(None, description="Original path in source system")
    url: Optional[HttpUrl] = Field(None, description="Link back to source document")


class FileInfo(BaseModel):
    """File content and metadata."""
    content: Optional[str] = Field(None, description="Base64-encoded file content")
    url: Optional[HttpUrl] = Field(None, description="Pre-signed URL to fetch file from")
    filename: str = Field(..., description="Original filename")
    mime_type: str = Field("application/pdf", description="MIME type of the file")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")

    @field_validator('mime_type')
    @classmethod
    def validate_mime_type(cls, v: str) -> str:
        allowed = {
            'application/pdf',
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/tiff',
        }
        if v not in allowed:
            raise ValueError(f"Unsupported mime_type: {v}. Allowed: {allowed}")
        return v


class DocumentMetadata(BaseModel):
    """Document metadata for indexing."""
    title: Optional[str] = Field(None, description="Document title")
    description: Optional[str] = Field("", description="Document description")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")
    custom: Dict[str, Any] = Field(default_factory=dict, description="Source-specific metadata")


class IngestOptions(BaseModel):
    """Processing options for ingestion."""
    detect_regions: bool = Field(False, description="Enable region detection for large drawings")
    use_vlm_detection: bool = Field(False, description="Use VLM for semantic region labeling")
    webhook_url: Optional[HttpUrl] = Field(None, description="URL to notify on completion")
    priority: Priority = Field(Priority.NORMAL, description="Processing priority")
    replace_existing: bool = Field(True, description="Replace if document already exists")


class IngestRequest(BaseModel):
    """Universal ingestion request."""
    source: SourceInfo
    file: FileInfo
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    options: IngestOptions = Field(default_factory=IngestOptions)

    @field_validator('file')
    @classmethod
    def validate_file_has_content(cls, v: FileInfo) -> FileInfo:
        if not v.content and not v.url:
            raise ValueError("Either 'content' or 'url' must be provided")
        return v


class IngestResponse(BaseModel):
    """Response from ingestion endpoint."""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobState = Field(..., description="Current job state")
    message: str = Field("", description="Status message")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


class BatchIngestRequest(BaseModel):
    """Batch ingestion request."""
    documents: List[IngestRequest] = Field(..., min_length=1, max_length=100)
    options: IngestOptions = Field(default_factory=IngestOptions)


class BatchIngestResponse(BaseModel):
    """Response from batch ingestion."""
    batch_id: str
    jobs: List[IngestResponse]
    total: int
    queued: int


# =============================================================================
# Query Schemas
# =============================================================================

class DateRange(BaseModel):
    """Date range filter."""
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class QueryFilters(BaseModel):
    """Filters for search queries."""
    sources: Optional[List[SourceType]] = Field(None, description="Filter by source types")
    source_ids: Optional[List[str]] = Field(None, description="Filter by source IDs")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    date_range: Optional[DateRange] = Field(None, description="Filter by date range")


class QueryOptions(BaseModel):
    """Options for search queries."""
    ranking: RankingMethod = Field(RankingMethod.HYBRID, description="Ranking method")
    limit: int = Field(10, ge=1, le=100, description="Maximum results to return")
    offset: int = Field(0, ge=0, description="Pagination offset")
    include_similarity_maps: bool = Field(False, description="Include similarity map data")
    rerank: bool = Field(True, description="Apply application-level reranking")
    rerank_candidates: int = Field(20, ge=1, le=100, description="Candidates for reranking")


class QueryRequest(BaseModel):
    """Universal query request."""
    query: str = Field(..., min_length=1, description="Search query text")
    filters: QueryFilters = Field(default_factory=QueryFilters)
    options: QueryOptions = Field(default_factory=QueryOptions)


class SearchResult(BaseModel):
    """Single search result."""
    doc_id: str
    title: str
    snippet: str
    page_number: int
    relevance_score: float
    source: SourceInfo
    metadata: Dict[str, Any] = Field(default_factory=dict)
    blur_image: Optional[str] = None
    similarity_map: Optional[Dict[str, str]] = None


class QueryResponse(BaseModel):
    """Response from query endpoint."""
    query: str
    results: List[SearchResult]
    total_count: int
    processing_time_ms: float
    ranking_method: RankingMethod


# =============================================================================
# Job Status Schemas
# =============================================================================

class JobStatus(BaseModel):
    """Detailed job status."""
    job_id: str
    state: JobState
    source: SourceInfo
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Progress 0-1")
    message: str = ""
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


# =============================================================================
# Health Check Schemas
# =============================================================================

class ServiceHealth(BaseModel):
    """Health status of a single service."""
    name: str
    healthy: bool
    latency_ms: Optional[float] = None
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class HealthStatus(BaseModel):
    """Overall system health status."""
    healthy: bool
    timestamp: datetime
    services: List[ServiceHealth]
    version: str = "1.0.0"


# =============================================================================
# Source Registry Schemas
# =============================================================================

class SourceConfig(BaseModel):
    """Configuration for a connected source."""
    type: SourceType
    name: str
    api_key_id: str
    enabled: bool = True
    webhook_url: Optional[HttpUrl] = None
    rate_limit: int = Field(100, description="Requests per minute")
    settings: Dict[str, Any] = Field(default_factory=dict)


class SourceStats(BaseModel):
    """Statistics for a connected source."""
    type: SourceType
    source_id: str
    documents_indexed: int
    last_sync: Optional[datetime] = None
    queries_today: int = 0
    errors_today: int = 0
