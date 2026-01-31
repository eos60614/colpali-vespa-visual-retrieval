"""
Document ingestion processor for the job queue.

Processes ingestion jobs by:
1. Fetching file content (from base64 or URL)
2. Validating the file
3. Generating embeddings
4. Indexing in Vespa
5. Sending webhook notifications
"""

import base64
import httpx
from typing import Any, Dict

from backend.core.logging_config import get_logger
from backend.gateway.jobs import Job, JobQueue
from backend.gateway.webhooks import webhook_notifier

logger = get_logger(__name__)


async def fetch_file_content(job: Job) -> bytes:
    """
    Fetch file content from base64 or URL.

    Args:
        job: The ingestion job

    Returns:
        Raw file bytes
    """
    file_info = job.request.file

    if file_info.content:
        # Decode base64 content
        return base64.b64decode(file_info.content)

    elif file_info.url:
        # Fetch from URL
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(str(file_info.url))
            response.raise_for_status()
            return response.content

    else:
        raise ValueError("No file content or URL provided")


def process_ingestion_job(job: Job, queue: JobQueue) -> Dict[str, Any]:
    """
    Process an ingestion job synchronously (runs in thread pool).

    This is the main processor function that:
    1. Fetches file content
    2. Validates and processes the file
    3. Generates embeddings
    4. Indexes in Vespa

    Args:
        job: The ingestion job
        queue: The job queue (for progress updates)

    Returns:
        Result dictionary with indexed document IDs
    """
    import asyncio

    # Run the async parts in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(
            _process_ingestion_job_async(job, queue)
        )
        return result
    finally:
        loop.close()


async def _process_ingestion_job_async(job: Job, queue: JobQueue) -> Dict[str, Any]:
    """Async implementation of job processing."""
    import sys

    # Get global instances from main module
    main_module = sys.modules.get("__main__")
    if not main_module:
        raise RuntimeError("Main module not found")

    vespa_app = getattr(main_module, "vespa_app", None)
    sim_map_generator = getattr(main_module, "sim_map_generator", None)

    if not vespa_app or not sim_map_generator:
        raise RuntimeError("Vespa or ColPali model not initialized")

    # Step 1: Fetch file content
    queue.update_progress(job.job_id, 0.1, "Fetching file content")
    file_bytes = await fetch_file_content(job)

    # Step 2: Determine file type and process
    queue.update_progress(job.job_id, 0.2, "Processing file")

    mime_type = job.request.file.mime_type
    filename = job.request.file.filename
    metadata = job.request.metadata
    options = job.request.options
    source = job.request.source

    # Import ingestion functions
    from backend.ingestion.pdf.processor import (
        ingest_pdf,
        ingest_image,
        validate_pdf,
        validate_image,
    )

    # Get model and processor from sim_map_generator
    model = sim_map_generator.model
    processor = sim_map_generator.processor
    device = str(sim_map_generator.device)

    result = {
        "source_type": source.type.value,
        "source_id": source.id,
        "source_path": source.path,
        "filename": filename,
        "documents_indexed": 0,
        "document_ids": [],
    }

    if mime_type == "application/pdf":
        # Validate PDF
        is_valid, validation_msg = validate_pdf(file_bytes)
        if not is_valid:
            raise ValueError(f"Invalid PDF: {validation_msg}")

        queue.update_progress(job.job_id, 0.3, "Generating embeddings")

        # Ingest PDF
        success, message, pages_indexed = ingest_pdf(
            file_bytes=file_bytes,
            filename=filename,
            vespa_app=vespa_app.app,  # Get the underlying Vespa instance
            model=model,
            processor=processor,
            device=device,
            title=metadata.title,
            description=metadata.description or "",
            tags=metadata.tags,
            detect_drawing_regions=options.detect_regions,
            use_vlm_detection=options.use_vlm_detection,
        )

        if not success:
            raise RuntimeError(f"Ingestion failed: {message}")

        result["documents_indexed"] = pages_indexed
        result["message"] = message

    elif mime_type.startswith("image/"):
        # Validate image
        is_valid, validation_msg = validate_image(file_bytes)
        if not is_valid:
            raise ValueError(f"Invalid image: {validation_msg}")

        queue.update_progress(job.job_id, 0.3, "Generating embeddings")

        # Ingest image
        success, message, pages_indexed = ingest_image(
            file_bytes=file_bytes,
            filename=filename,
            vespa_app=vespa_app.app,
            model=model,
            processor=processor,
            device=device,
            title=metadata.title,
            description=metadata.description or "",
            tags=metadata.tags,
        )

        if not success:
            raise RuntimeError(f"Ingestion failed: {message}")

        result["documents_indexed"] = pages_indexed
        result["message"] = message

    else:
        raise ValueError(f"Unsupported file type: {mime_type}")

    queue.update_progress(job.job_id, 0.9, "Finalizing")

    # Send webhook notification if configured
    if job.webhook_url:
        try:
            await webhook_notifier.notify_job_completed(
                webhook_url=job.webhook_url,
                job_id=job.job_id,
                source_type=source.type,
                source_id=source.id,
                result=result,
            )
        except Exception as e:
            logger.warning(f"Webhook notification failed: {e}")

    return result


def setup_job_processor():
    """
    Set up the job processor for the queue.

    Call this during application startup.
    """
    from backend.gateway.jobs import job_queue
    job_queue.set_processor(process_ingestion_job)
    logger.info("Job processor configured")
