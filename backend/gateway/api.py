"""
Gateway API route handlers.

Provides universal endpoints for:
- Document ingestion (POST /api/v1/ingest)
- Batch ingestion (POST /api/v1/ingest/batch)
- Job status (GET /api/v1/jobs/{job_id})
- Universal query (POST /api/v1/query)
- Health check (GET /api/v1/health)
- Source management (GET /api/v1/sources)
"""

import time
from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from backend.core.logging_config import get_logger
from backend.gateway.auth import api_key_auth, rate_limiter, APIKey
from backend.gateway.jobs import job_queue
from backend.gateway.health import health_checker
from backend.gateway.schemas import (
    IngestRequest,
    IngestResponse,
    BatchIngestRequest,
    BatchIngestResponse,
    QueryRequest,
    QueryResponse,
    SearchResult,
    SourceInfo,
    SourceType,
)
from backend.connectors.base import connector_registry

logger = get_logger(__name__)


# =============================================================================
# Authentication middleware helpers
# =============================================================================

def get_api_key_from_request(request: Request) -> Optional[str]:
    """Extract API key from request headers."""
    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Check X-API-Key header
    return request.headers.get("X-API-Key")


async def validate_request(request: Request, scope: str = "ingest") -> tuple[Optional[APIKey], Optional[JSONResponse]]:
    """
    Validate API key and rate limits.

    Returns:
        Tuple of (api_key, error_response)
        If error_response is not None, return it immediately
    """
    api_key_value = get_api_key_from_request(request)

    if not api_key_value:
        return None, JSONResponse(
            {"error": "Missing API key", "code": "UNAUTHORIZED"},
            status_code=401,
        )

    api_key = api_key_auth.validate_key(api_key_value)
    if not api_key:
        return None, JSONResponse(
            {"error": "Invalid API key", "code": "UNAUTHORIZED"},
            status_code=401,
        )

    if not api_key_auth.has_scope(api_key, scope):
        return None, JSONResponse(
            {"error": f"API key lacks '{scope}' scope", "code": "FORBIDDEN"},
            status_code=403,
        )

    # Check rate limits
    allowed, remaining, reset = rate_limiter.check_rate_limit(api_key)
    if not allowed:
        return None, JSONResponse(
            {
                "error": "Rate limit exceeded",
                "code": "RATE_LIMITED",
                "retry_after": reset,
            },
            status_code=429,
            headers={
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset),
                "Retry-After": str(reset),
            },
        )

    rate_limiter.record_request(api_key)
    return api_key, None


# =============================================================================
# Ingestion Endpoints
# =============================================================================

async def api_ingest(request: Request) -> JSONResponse:
    """
    Universal document ingestion endpoint.

    POST /api/v1/ingest

    Accepts documents from any source and queues them for processing.
    """
    # Validate authentication
    api_key, error = await validate_request(request, "ingest")
    if error:
        return error

    try:
        body = await request.json()
        ingest_request = IngestRequest.model_validate(body)
    except Exception as e:
        return JSONResponse(
            {"error": f"Invalid request body: {str(e)}", "code": "BAD_REQUEST"},
            status_code=400,
        )

    # Create job
    job = job_queue.create_job(ingest_request)

    # Return response
    response = IngestResponse(
        job_id=job.job_id,
        status=job.state,
        message="Document queued for processing",
        estimated_completion=None,  # Could estimate based on queue depth
    )

    return JSONResponse(
        response.model_dump(mode="json"),
        status_code=202,  # Accepted
        headers={"X-Job-Id": job.job_id},
    )


async def api_ingest_batch(request: Request) -> JSONResponse:
    """
    Batch document ingestion endpoint.

    POST /api/v1/ingest/batch

    Accepts multiple documents and queues them all.
    """
    api_key, error = await validate_request(request, "ingest")
    if error:
        return error

    try:
        body = await request.json()
        batch_request = BatchIngestRequest.model_validate(body)
    except Exception as e:
        return JSONResponse(
            {"error": f"Invalid request body: {str(e)}", "code": "BAD_REQUEST"},
            status_code=400,
        )

    # Create jobs for each document
    jobs = []
    for doc in batch_request.documents:
        # Apply batch options if not set per-document
        if batch_request.options.webhook_url and not doc.options.webhook_url:
            doc.options.webhook_url = batch_request.options.webhook_url
        if batch_request.options.priority and doc.options.priority == "normal":
            doc.options.priority = batch_request.options.priority

        job = job_queue.create_job(doc)
        jobs.append(IngestResponse(
            job_id=job.job_id,
            status=job.state,
            message="Queued",
        ))

    import uuid
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"

    response = BatchIngestResponse(
        batch_id=batch_id,
        jobs=jobs,
        total=len(jobs),
        queued=len(jobs),
    )

    return JSONResponse(
        response.model_dump(mode="json"),
        status_code=202,
    )


async def api_job_status(request: Request) -> JSONResponse:
    """
    Get job status.

    GET /api/v1/jobs/{job_id}
    """
    api_key, error = await validate_request(request, "query")
    if error:
        return error

    job_id = request.path_params.get("job_id")
    if not job_id:
        return JSONResponse(
            {"error": "job_id is required", "code": "BAD_REQUEST"},
            status_code=400,
        )

    job = job_queue.get_job(job_id)
    if not job:
        return JSONResponse(
            {"error": "Job not found", "code": "NOT_FOUND"},
            status_code=404,
        )

    return JSONResponse(job.to_status().model_dump(mode="json"))


async def api_cancel_job(request: Request) -> JSONResponse:
    """
    Cancel a queued job.

    DELETE /api/v1/jobs/{job_id}
    """
    api_key, error = await validate_request(request, "ingest")
    if error:
        return error

    job_id = request.path_params.get("job_id")
    if not job_id:
        return JSONResponse(
            {"error": "job_id is required", "code": "BAD_REQUEST"},
            status_code=400,
        )

    if job_queue.cancel_job(job_id):
        return JSONResponse({"status": "cancelled", "job_id": job_id})
    else:
        return JSONResponse(
            {"error": "Job cannot be cancelled (not queued)", "code": "CONFLICT"},
            status_code=409,
        )


# =============================================================================
# Query Endpoints
# =============================================================================

async def api_query(request: Request) -> JSONResponse:
    """
    Universal query endpoint.

    POST /api/v1/query

    Search across all indexed documents with filters.
    """
    api_key, error = await validate_request(request, "query")
    if error:
        return error

    try:
        body = await request.json()
        query_request = QueryRequest.model_validate(body)
    except Exception as e:
        return JSONResponse(
            {"error": f"Invalid request body: {str(e)}", "code": "BAD_REQUEST"},
            status_code=400,
        )

    start_time = time.perf_counter()

    try:
        # Import here to avoid circular imports

        # Get or create instances (these should be globals in main.py)
        import sys
        main_module = sys.modules.get("__main__")

        if not main_module or not hasattr(main_module, "vespa_app"):
            return JSONResponse(
                {"error": "Search service not initialized", "code": "SERVICE_UNAVAILABLE"},
                status_code=503,
            )

        vespa_app = main_module.vespa_app
        sim_map_generator = getattr(main_module, "sim_map_generator", None)

        if not sim_map_generator:
            return JSONResponse(
                {"error": "Model not loaded", "code": "SERVICE_UNAVAILABLE"},
                status_code=503,
            )

        # Get query embeddings
        q_embs, idx_to_token = sim_map_generator.get_query_embeddings_and_token_map(
            query_request.query
        )

        # Execute search
        ranking = query_request.options.ranking.value
        result = await vespa_app.get_result_from_query(
            query=query_request.query,
            q_embs=q_embs,
            ranking=ranking,
            idx_to_token=idx_to_token,
            rerank=query_request.options.rerank,
            rerank_hits=query_request.options.rerank_candidates,
            final_hits=query_request.options.limit,
        )

        # Transform results
        search_results = []
        children = result.get("root", {}).get("children", [])

        for child in children:
            fields = child.get("fields", {})

            # Build source info from stored metadata
            source_type = fields.get("source_type", "direct")
            source_id = fields.get("source_id", "unknown")

            search_results.append(SearchResult(
                doc_id=fields.get("id", ""),
                title=fields.get("title", ""),
                snippet=fields.get("snippet", ""),
                page_number=fields.get("page_number", 1),
                relevance_score=child.get("relevance", 0.0),
                source=SourceInfo(
                    type=SourceType(source_type) if source_type in [e.value for e in SourceType] else SourceType.DIRECT,
                    id=source_id,
                    path=fields.get("url", ""),
                ),
                metadata={
                    "tags": fields.get("tags", []),
                    "description": fields.get("description", ""),
                },
                blur_image=fields.get("blur_image"),
            ))

        processing_time = (time.perf_counter() - start_time) * 1000

        response = QueryResponse(
            query=query_request.query,
            results=search_results,
            total_count=len(search_results),
            processing_time_ms=processing_time,
            ranking_method=query_request.options.ranking,
        )

        return JSONResponse(response.model_dump(mode="json"))

    except Exception as e:
        logger.exception(f"Query error: {e}")
        return JSONResponse(
            {"error": f"Query failed: {str(e)}", "code": "INTERNAL_ERROR"},
            status_code=500,
        )


# =============================================================================
# Health & Status Endpoints
# =============================================================================

async def api_health(request: Request) -> JSONResponse:
    """
    Health check endpoint.

    GET /api/v1/health

    Returns health status of all services.
    No authentication required for basic health checks.
    """
    # Check if detailed health is requested (requires auth)
    detailed = request.query_params.get("detailed", "false").lower() == "true"

    if detailed:
        api_key, error = await validate_request(request, "query")
        if error:
            return error

    health_status = await health_checker.check_all()

    # For basic health, just return overall status
    if not detailed:
        return JSONResponse({
            "healthy": health_status.healthy,
            "timestamp": health_status.timestamp.isoformat(),
            "version": health_status.version,
        })

    return JSONResponse(health_status.model_dump(mode="json"))


async def api_sources(request: Request) -> JSONResponse:
    """
    List connected sources.

    GET /api/v1/sources
    """
    api_key, error = await validate_request(request, "query")
    if error:
        return error

    connectors = connector_registry.get_all()
    sources = [c.get_status() for c in connectors]

    return JSONResponse({
        "sources": sources,
        "total": len(sources),
    })


async def api_source_sync(request: Request) -> JSONResponse:
    """
    Trigger sync for a source.

    POST /api/v1/sources/{source_type}/{source_id}/sync
    """
    api_key, error = await validate_request(request, "ingest")
    if error:
        return error

    source_type = request.path_params.get("source_type")
    source_id = request.path_params.get("source_id")

    try:
        st = SourceType(source_type)
    except ValueError:
        return JSONResponse(
            {"error": f"Invalid source type: {source_type}", "code": "BAD_REQUEST"},
            status_code=400,
        )

    connector = connector_registry.get(st, source_id)
    if not connector:
        return JSONResponse(
            {"error": "Source not found", "code": "NOT_FOUND"},
            status_code=404,
        )

    # Parse request body for sync options
    try:
        body = await request.json()
    except Exception:
        body = {}

    full_sync = body.get("full_sync", False)
    path = body.get("path")

    # Trigger sync (async)
    import asyncio
    asyncio.create_task(connector.sync(path=path, full_sync=full_sync))

    return JSONResponse({
        "status": "sync_started",
        "source_type": source_type,
        "source_id": source_id,
        "full_sync": full_sync,
    }, status_code=202)


# =============================================================================
# API Key Management Endpoints
# =============================================================================

async def api_create_key(request: Request) -> JSONResponse:
    """
    Create a new API key.

    POST /api/v1/keys

    Requires admin scope.
    """
    api_key, error = await validate_request(request, "admin")
    if error:
        return error

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": "Invalid JSON body", "code": "BAD_REQUEST"},
            status_code=400,
        )

    source_type = body.get("source_type")
    source_id = body.get("source_id", "default")
    name = body.get("name", "API Key")
    rate_limit = body.get("rate_limit", 100)
    scopes = body.get("scopes", ["ingest", "query"])

    try:
        st = SourceType(source_type)
    except ValueError:
        return JSONResponse(
            {"error": f"Invalid source type: {source_type}", "code": "BAD_REQUEST"},
            status_code=400,
        )

    key_id, key_value = api_key_auth.register_key(
        source_type=st,
        source_id=source_id,
        name=name,
        rate_limit=rate_limit,
        scopes=scopes,
    )

    return JSONResponse({
        "key_id": key_id,
        "key": key_value,  # Only returned once!
        "source_type": source_type,
        "source_id": source_id,
        "name": name,
        "rate_limit": rate_limit,
        "scopes": scopes,
        "message": "Save this key securely - it will not be shown again!",
    }, status_code=201)


# =============================================================================
# Route definitions
# =============================================================================

gateway_routes = [
    # Ingestion
    Route("/api/v1/ingest", api_ingest, methods=["POST"]),
    Route("/api/v1/ingest/batch", api_ingest_batch, methods=["POST"]),

    # Jobs
    Route("/api/v1/jobs/{job_id}", api_job_status, methods=["GET"]),
    Route("/api/v1/jobs/{job_id}", api_cancel_job, methods=["DELETE"]),

    # Query
    Route("/api/v1/query", api_query, methods=["POST"]),

    # Health & Status
    Route("/api/v1/health", api_health, methods=["GET"]),
    Route("/api/v1/sources", api_sources, methods=["GET"]),
    Route("/api/v1/sources/{source_type}/{source_id}/sync", api_source_sync, methods=["POST"]),

    # API Key Management
    Route("/api/v1/keys", api_create_key, methods=["POST"]),
]
