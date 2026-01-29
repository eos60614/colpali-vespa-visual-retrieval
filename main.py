"""
Backend API server for the visual document retrieval system.

Provides JSON REST APIs for the Next.js frontend.
"""
import asyncio
import base64
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import uvicorn
from fastcore.parallel import threaded
from PIL import Image
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from starlette.routing import Route
from vespa.application import Vespa

from backend.config import get
from backend.logging_config import configure_logging, get_logger
from backend.middleware import CorrelationIdMiddleware, ErrorBoundaryMiddleware
from backend.llm_config import resolve_llm_config, get_chat_model, is_remote_api, build_auth_headers
from backend.colpali import SimMapGenerator
from backend.vespa_app import VespaQueryClient
from backend.ingest import ingest_pdf, validate_pdf
from backend.s3 import generate_presigned_url
from backend.llm_rerank import llm_rerank_results, is_llm_rerank_enabled, get_llm_rerank_candidates

# Initialize centralized logging
LOG_LEVEL = get("app", "log_level").upper()
configure_logging(log_level=LOG_LEVEL, service="vespa_app")
logger = get_logger("vespa_app")

# Global instances
vespa_app: Vespa = VespaQueryClient(logger=logger)
thread_pool = ThreadPoolExecutor()

# Chat LLM config
LLM_BASE_URL, LLM_API_KEY = resolve_llm_config()
CHAT_MODEL = get_chat_model()
CHAT_SYSTEM_PROMPT = get("llm", "chat_system_prompt")

# Paths
STATIC_DIR = Path(get("app", "static_dir"))
IMG_DIR = Path(get("app", "img_dir"))
SIM_MAP_DIR = Path(get("app", "sim_map_dir"))
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(SIM_MAP_DIR, exist_ok=True)

MAX_FILE_SIZE = get("app", "max_file_size_mb") * 1024 * 1024

# In-memory cache: query_id -> list of doc metadata dicts for chat grounding
_query_result_metadata: dict[str, list[dict]] = {}

# Sim map generator (initialized at startup)
sim_map_generator: SimMapGenerator | None = None


def generate_query_id(query: str, ranking_value: str) -> int:
    hash_input = (query + ranking_value).encode("utf-8")
    return hash(hash_input)


# =============================================================================
# Startup/shutdown handlers
# =============================================================================

async def startup():
    """Initialize the ColPali model and start Vespa keepalive task."""
    global sim_map_generator
    sim_map_generator = SimMapGenerator(logger=logger)
    asyncio.create_task(poll_vespa_keepalive())
    logger.info("Application startup complete")


async def poll_vespa_keepalive():
    """Background task to keep Vespa connection alive."""
    while True:
        await asyncio.sleep(get("app", "keepalive_interval_seconds"))
        await vespa_app.keepalive()
        logger.debug(f"Vespa keepalive: {time.time()}")


# =============================================================================
# Background tasks
# =============================================================================

@threaded
def get_and_store_sim_maps(
    query_id, query: str, q_embs, ranking, idx_to_token, doc_ids
):
    """Generate and save similarity maps to disk in background."""
    ranking_sim = ranking + "_sim"
    vespa_sim_maps = vespa_app.get_sim_maps_from_query(
        query=query,
        q_embs=q_embs,
        ranking=ranking_sim,
        idx_to_token=idx_to_token,
    )
    img_paths = [IMG_DIR / f"{doc_id}.jpg" for doc_id in doc_ids]
    max_wait = get("image", "max_wait_seconds")
    poll_sleep = get("image", "poll_sleep_seconds")
    start_time = time.time()
    while (
        not all([os.path.exists(img_path) for img_path in img_paths])
        and time.time() - start_time < max_wait
    ):
        time.sleep(poll_sleep)
    if not all([os.path.exists(img_path) for img_path in img_paths]):
        logger.warning(f"Images not ready in {max_wait} seconds for query_id: {query_id}")
        return False
    sim_map_gen = sim_map_generator.gen_similarity_maps(
        query=query,
        query_embs=q_embs,
        token_idx_map=idx_to_token,
        images=img_paths,
        vespa_sim_maps=vespa_sim_maps,
    )
    for idx, token, token_idx, blended_img_base64 in sim_map_gen:
        with open(SIM_MAP_DIR / f"{query_id}_{idx}_{token_idx}.png", "wb") as f:
            f.write(base64.b64decode(blended_img_base64))
        logger.debug(
            f"Sim map saved to disk for query_id: {query_id}, idx: {idx}, token: {token}"
        )
    return True


@threaded
def _download_images_bg(doc_ids):
    """Download full images from Vespa to disk in background."""
    for doc_id in doc_ids:
        img_path = IMG_DIR / f"{doc_id}.jpg"
        if not os.path.exists(img_path):
            try:
                image_data = asyncio.run(vespa_app.get_full_image_from_vespa(doc_id))
                with open(img_path, "wb") as f:
                    f.write(base64.b64decode(image_data))
                logger.debug(f"Background download: saved {doc_id}")
            except Exception as e:
                logger.error(f"Background image download failed for {doc_id}: {e}", exc_info=True)


# =============================================================================
# API Route Handlers
# =============================================================================

async def serve_static(request):
    """Serve static files."""
    filepath = request.path_params.get("filepath", "")
    return FileResponse(STATIC_DIR / filepath)


async def api_suggestions(request):
    """Endpoint to get suggestions as user types in the search box."""
    query = request.query_params.get("query", "").lower().strip()
    if query:
        suggestions = await vespa_app.get_suggestions(query)
        if len(suggestions) > 0:
            return JSONResponse({"suggestions": suggestions})
    return JSONResponse({"suggestions": []})


async def api_search(request):
    """JSON search endpoint for the Next.js frontend.

    Accepts JSON body: { query, ranking? }
    Returns JSON with search results including blur images and doc IDs.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    query = body.get("query", "").strip()
    ranking = body.get("ranking", "hybrid")

    if not query:
        return JSONResponse({"error": "Query is required"}, status_code=400)

    query_id = generate_query_id(query, ranking)

    # Run embedding inference
    q_embs, idx_to_token = sim_map_generator.get_query_embeddings_and_token_map(query)

    start = time.perf_counter()
    result = await vespa_app.get_result_from_query(
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        rerank=True,
        rerank_hits=get("search", "rerank_hits"),
        final_hits=get("search", "final_hits"),
    )
    duration_ms = round((time.perf_counter() - start) * 1000)

    search_results = vespa_app.results_to_search_results(result, idx_to_token)

    # Trigger background sim map + image download
    doc_ids = [r["fields"]["id"] for r in search_results]
    get_and_store_sim_maps(
        query_id=query_id,
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        doc_ids=doc_ids,
    )

    # Download full images to disk in background
    _download_images_bg(doc_ids)

    # Transform Vespa results to JSON-friendly format
    results_json = []
    for sr in search_results:
        fields = sr.get("fields", {})
        relevance = sr.get("relevance", 0)
        results_json.append({
            "id": fields.get("id", ""),
            "title": fields.get("title", ""),
            "page_number": fields.get("page_number", 0),
            "snippet": fields.get("snippet", ""),
            "text": fields.get("text", ""),
            "blur_image": fields.get("blur_image", ""),
            "relevance": relevance,
            "url": fields.get("url", ""),
            "has_original_pdf": bool(fields.get("s3_key", "")),
        })

    return JSONResponse({
        "results": results_json,
        "query": query,
        "query_id": str(query_id),
        "doc_ids": doc_ids,
        "ranking": ranking,
        "duration_ms": duration_ms,
        "total_count": result.get("root", {}).get("fields", {}).get("totalCount", 0),
    })


async def api_visual_search(request):
    """JSON endpoint for visual search results.

    Accepts JSON body: { query, ranking?, limit? }
    Returns JSON with search results including blur images, doc IDs, and token map.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    query = body.get("query", "").strip()
    ranking = body.get("ranking", "hybrid")
    limit = body.get("limit", 20)

    if not query:
        return JSONResponse({"error": "Query is required"}, status_code=400)

    query_id = generate_query_id(query, ranking)

    # Run embedding inference
    q_embs, idx_to_token = sim_map_generator.get_query_embeddings_and_token_map(query)

    start = time.perf_counter()
    result = await vespa_app.get_result_from_query(
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        rerank=True,
        rerank_hits=get("search", "rerank_hits"),
        final_hits=min(limit, get("search", "final_hits")),
    )
    duration_ms = round((time.perf_counter() - start) * 1000)

    search_results = vespa_app.results_to_search_results(result, idx_to_token)

    # Trigger background sim map + image download
    doc_ids = [r["fields"]["id"] for r in search_results]
    get_and_store_sim_maps(
        query_id=query_id,
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        doc_ids=doc_ids,
    )

    # Download full images to disk in background
    _download_images_bg(doc_ids)

    # Cache document metadata for chat grounding
    _query_result_metadata[str(query_id)] = [
        {
            "doc_id": r["fields"].get("id", ""),
            "title": r["fields"].get("title", "Unknown"),
            "page_number": r["fields"].get("page_number", 0) + 1,
            "snippet": (r["fields"].get("snippet", "") or "")[:get("image", "truncation", "snippet_length")],
            "text": (r["fields"].get("text", "") or "")[:get("image", "truncation", "text_length")],
        }
        for r in search_results
    ]

    # Build token map for similarity maps
    token_map = [
        {"token": token.replace("\u2581", ""), "token_idx": token_idx}
        for token_idx, token in idx_to_token.items()
    ]

    # Transform Vespa results to JSON-friendly format
    results_json = []
    for sr in search_results:
        fields = sr.get("fields", {})
        relevance = sr.get("relevance", 0)
        results_json.append({
            "id": fields.get("id", ""),
            "title": fields.get("title", ""),
            "page_number": fields.get("page_number", 0),
            "snippet": fields.get("snippet", ""),
            "text": fields.get("text", ""),
            "blur_image": fields.get("blur_image", ""),
            "relevance": relevance,
            "url": fields.get("url", ""),
            "has_original_pdf": bool(fields.get("s3_key", "")),
        })

    return JSONResponse({
        "results": results_json,
        "query": query,
        "query_id": str(query_id),
        "doc_ids": doc_ids,
        "ranking": ranking,
        "duration_ms": duration_ms,
        "total_count": result.get("root", {}).get("fields", {}).get("totalCount", 0),
        "token_map": token_map,
    })


async def api_full_image(request):
    """JSON endpoint returning full-resolution image as base64."""
    doc_id = request.query_params.get("doc_id", "")
    if not doc_id:
        return JSONResponse({"error": "doc_id is required"}, status_code=400)

    img_path = IMG_DIR / f"{doc_id}.jpg"
    if not os.path.exists(img_path):
        image_data = await vespa_app.get_full_image_from_vespa(doc_id)
        with open(img_path, "wb") as f:
            f.write(base64.b64decode(image_data))
    else:
        with open(img_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
    return JSONResponse({"image": f"data:image/jpeg;base64,{image_data}"})


async def api_sim_map(request):
    """JSON endpoint to get a similarity map image as base64.

    Returns: {"ready": true, "image": "data:image/png;base64,..."}
    Or: {"ready": false}
    """
    query_id = request.query_params.get("query_id", "")
    idx = request.query_params.get("idx", "")
    token_idx = request.query_params.get("token_idx", "")

    if not query_id or not idx or not token_idx:
        return JSONResponse({"error": "Missing required parameters"}, status_code=400)

    sim_map_path = SIM_MAP_DIR / f"{query_id}_{idx}_{token_idx}.png"
    if not os.path.exists(sim_map_path):
        logger.debug(f"Sim map not ready for query_id: {query_id}, idx: {idx}, token_idx: {token_idx}")
        return JSONResponse({"ready": False})
    else:
        with open(sim_map_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        return JSONResponse({
            "ready": True,
            "image": f"data:image/png;base64,{image_data}",
        })


async def api_upload(request):
    """JSON endpoint for PDF file upload and ingestion.

    Returns JSON: {"success": true, "title": "...", "pages_indexed": N}
    On error: {"success": false, "error": "message"}
    """
    form = await request.form()
    pdf_file = form.get("pdf_file")
    title = form.get("title", "")
    description = form.get("description", "")
    tags = form.get("tags", "")
    detect_regions = form.get("detect_regions", "")
    use_vlm = form.get("use_vlm", "")

    # Check if file was provided
    if pdf_file is None or not hasattr(pdf_file, 'filename') or pdf_file.filename == "":
        logger.warning("Upload attempted without file")
        return JSONResponse({"success": False, "error": "Please select a PDF file"}, status_code=400)

    # Read file content
    try:
        file_bytes = await pdf_file.read()
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": "Error reading uploaded file"}, status_code=500)

    # Validate file size
    if len(file_bytes) > MAX_FILE_SIZE:
        logger.warning(f"File too large: {len(file_bytes)} bytes")
        return JSONResponse({"success": False, "error": "File exceeds 250MB size limit"}, status_code=400)

    # Validate file is a PDF
    if not pdf_file.filename.lower().endswith(".pdf"):
        return JSONResponse({"success": False, "error": "Only PDF files are accepted"}, status_code=400)

    # Validate PDF integrity
    is_valid, validation_msg = validate_pdf(file_bytes)
    if not is_valid:
        logger.warning(f"PDF validation failed: {validation_msg}")
        return JSONResponse({"success": False, "error": validation_msg}, status_code=400)

    # Parse tags
    tag_list = []
    if tags and tags.strip():
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        max_tags = get("app", "validation", "max_tags")
        if len(tag_list) > max_tags:
            return JSONResponse({"success": False, "error": f"Maximum {max_tags} tags allowed"}, status_code=400)
        max_tag_length = get("app", "validation", "max_tag_length")
        for tag in tag_list:
            if len(tag) > max_tag_length:
                return JSONResponse({"success": False, "error": f"Each tag must be {max_tag_length} characters or less"}, status_code=400)

    # Validate title length
    max_title_length = get("app", "validation", "max_title_length")
    if title and len(title) > max_title_length:
        return JSONResponse({"success": False, "error": f"Title must be {max_title_length} characters or less"}, status_code=400)

    # Validate description length
    max_desc_length = get("app", "validation", "max_description_length")
    if description and len(description) > max_desc_length:
        return JSONResponse({"success": False, "error": f"Description must be {max_desc_length} characters or less"}, status_code=400)

    # Get the ColPali model
    model = sim_map_generator.model
    processor = sim_map_generator.processor
    device = sim_map_generator.device

    # Get Vespa app
    vespa = vespa_app.app

    # Process the PDF
    enable_regions = detect_regions.lower() in ("on", "true", "1", "yes") if detect_regions else False
    enable_vlm = use_vlm.lower() in ("on", "true", "1", "yes") if use_vlm else False

    try:
        success, message, pages_indexed = ingest_pdf(
            file_bytes=file_bytes,
            filename=pdf_file.filename,
            vespa_app=vespa,
            model=model,
            processor=processor,
            device=device,
            title=title.strip() if title and title.strip() else None,
            description=description if description else "",
            tags=tag_list,
            detect_drawing_regions=enable_regions,
            use_vlm_detection=enable_vlm,
        )
    except Exception as e:
        logger.error(f"Error processing PDF: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": "Error processing document. Please try again."}, status_code=500)

    if success:
        final_title = title.strip() if title and title.strip() else Path(pdf_file.filename).stem
        logger.info(f"Successfully uploaded: {final_title} ({pages_indexed} pages)")
        return JSONResponse({
            "success": True,
            "title": final_title,
            "pages_indexed": pages_indexed,
            "message": message,
        })
    else:
        logger.error(f"Upload failed: {message}")
        return JSONResponse({"success": False, "error": message}, status_code=400)


async def api_download_url(request):
    """JSON endpoint returning a presigned S3 download URL for the original PDF."""
    doc_id = request.query_params.get("doc_id", "")
    if not doc_id:
        return JSONResponse({"error": "doc_id is required"}, status_code=400)

    try:
        schema = get("vespa", "schema_name")
        connection_count = get("vespa", "connection_count")
        async with vespa_app.app.asyncio(connections=connection_count) as session:
            response = await session.query(
                body={
                    "yql": f'select s3_key from {schema} where id contains "{doc_id}"',
                    "ranking": "unranked",
                    "hits": 1,
                },
            )
            if not response.is_successful():
                return JSONResponse({"error": "Document not found"}, status_code=404)

            children = response.json.get("root", {}).get("children", [])
            if not children:
                return JSONResponse({"error": "Document not found"}, status_code=404)

            s3_key = children[0].get("fields", {}).get("s3_key", "")
            if not s3_key:
                return JSONResponse({"error": "No original PDF available for this document"}, status_code=404)
    except Exception as e:
        logger.error(f"Error querying Vespa for s3_key (doc_id={doc_id}): {e}", exc_info=True)
        return JSONResponse({"error": "Failed to look up document"}, status_code=500)

    try:
        presigned_url = generate_presigned_url(s3_key)
    except Exception as e:
        logger.error(f"Error generating presigned URL for s3_key={s3_key}: {e}", exc_info=True)
        return JSONResponse({"error": "Failed to generate download link"}, status_code=500)

    return JSONResponse({"download_url": presigned_url})


async def api_download_pdf(request):
    """Redirect to a presigned S3 URL for the original PDF."""
    doc_id = request.query_params.get("doc_id", "")
    if not doc_id:
        return JSONResponse({"error": "doc_id is required"}, status_code=400)

    try:
        schema = get("vespa", "schema_name")
        connection_count = get("vespa", "connection_count")
        async with vespa_app.app.asyncio(connections=connection_count) as session:
            response = await session.query(
                body={
                    "yql": f'select s3_key from {schema} where id contains "{doc_id}"',
                    "ranking": "unranked",
                    "hits": 1,
                },
            )
            if not response.is_successful():
                logger.error(f"Vespa query failed for doc_id={doc_id}: {response.json}")
                return JSONResponse({"error": "Document not found"}, status_code=404)

            children = response.json.get("root", {}).get("children", [])
            if not children:
                return JSONResponse({"error": "Document not found"}, status_code=404)

            s3_key = children[0].get("fields", {}).get("s3_key", "")
            if not s3_key:
                return JSONResponse({"error": "No original PDF available for this document"}, status_code=404)
    except Exception as e:
        logger.error(f"Error querying Vespa for s3_key (doc_id={doc_id}): {e}", exc_info=True)
        return JSONResponse({"error": "Failed to look up document"}, status_code=500)

    try:
        presigned_url = generate_presigned_url(s3_key)
    except Exception as e:
        logger.error(f"Error generating presigned URL for s3_key={s3_key}: {e}", exc_info=True)
        return JSONResponse({"error": "Failed to generate download link"}, status_code=500)

    return RedirectResponse(presigned_url)


# =============================================================================
# SSE Streaming Endpoints
# =============================================================================

async def message_generator(query_id: str, query: str, doc_ids: list):
    """Generator function to yield SSE messages for chat response."""
    images = []
    num_images = get("search", "num_images")
    max_wait = get("image", "max_wait_chat_seconds")
    start_time = time.time()

    while (
        len(images) < min(num_images, len(doc_ids))
        and time.time() - start_time < max_wait
    ):
        images = []
        for idx in range(min(num_images, len(doc_ids))):
            image_filename = IMG_DIR / f"{doc_ids[idx]}.jpg"
            if not os.path.exists(image_filename):
                logger.debug(f"Message generator: Full image not ready for query_id: {query_id}, idx: {idx}")
                continue
            else:
                logger.debug(f"Message generator: image ready for query_id: {query_id}, idx: {idx}")
                images.append(Image.open(image_filename))
        if len(images) < num_images:
            await asyncio.sleep(get("image", "poll_sleep_seconds"))

    yield f"event: message\ndata: Generating response based on {len(images)} images...\n\n"
    if not images:
        yield "event: message\ndata: Failed to load images for AI chat!\n\n"
        yield "event: close\ndata: \n\n"
        return

    is_remote = is_remote_api(LLM_BASE_URL) or LLM_API_KEY
    if is_remote and not LLM_API_KEY:
        yield "event: message\ndata: No API key configured. AI chat is unavailable.\n\n"
        yield "event: close\ndata: \n\n"
        return

    def replace_newline_with_br(text):
        return text.replace("\n", "<br>")

    # Build document context from cached metadata
    doc_metadata = _query_result_metadata.get(query_id, [])
    context_lines = []
    for i, meta in enumerate(doc_metadata[:len(images)]):
        context_lines.append(f"- Document {i+1}: \"{meta['title']}\" — Page {meta['page_number']}")
        if meta.get("text"):
            context_lines.append(f"  Text extract: {meta['text'][:get('image', 'truncation', 'snippet_length')]}")
    doc_context = "\n".join(context_lines) if context_lines else "No metadata available."

    content_parts = []
    for i, img in enumerate(images):
        meta_label = ""
        if i < len(doc_metadata):
            m = doc_metadata[i]
            meta_label = f"[Document {i+1}: \"{m['title']}\", Page {m['page_number']}]"
        if meta_label:
            content_parts.append({"type": "text", "text": meta_label})
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=get("image", "jpeg_quality"))
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    content_parts.append({"type": "text", "text": f"\n\nDocuments provided:\n{doc_context}\n\nQuestion: {query}"})

    headers = build_auth_headers(LLM_API_KEY)

    response_text = ""
    try:
        async with httpx.AsyncClient(timeout=get("llm", "http_timeout_seconds")) as client:
            async with client.stream(
                "POST",
                f"{LLM_BASE_URL}/chat/completions",
                headers=headers,
                json={
                    "model": CHAT_MODEL,
                    "stream": True,
                    "messages": [
                        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                        {"role": "user", "content": content_parts},
                    ],
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[len("data: "):]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            response_text += text
                            yield f"event: message\ndata: {replace_newline_with_br(response_text)}\n\n"
                            await asyncio.sleep(get("llm", "streaming_sleep_seconds"))
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except Exception as e:
        logger.error(f"Chat LLM streaming failed: {e}", exc_info=True)
        yield "event: message\ndata: Error generating AI response.\n\n"
    yield "event: close\ndata: \n\n"


async def get_message(request):
    """SSE endpoint for chat responses."""
    query_id = request.query_params.get("query_id", "")
    query = request.query_params.get("query", "")
    doc_ids = request.query_params.get("doc_ids", "").split(",")
    return StreamingResponse(
        message_generator(query_id=query_id, query=query, doc_ids=doc_ids),
        media_type="text/event-stream",
    )


async def synthesize_generator(query: str, doc_ids: list, query_id: str):
    """Generator function to yield SSE messages for synthesis response."""
    images = []
    num_images = min(len(doc_ids), get("search", "num_images"))
    max_wait = get("image", "max_wait_chat_seconds")
    start_time = time.time()

    while (
        len(images) < num_images
        and time.time() - start_time < max_wait
    ):
        images = []
        for idx in range(num_images):
            if idx >= len(doc_ids):
                break
            image_filename = IMG_DIR / f"{doc_ids[idx]}.jpg"
            if not os.path.exists(image_filename):
                logger.debug(f"Synthesize: Full image not ready for query_id: {query_id}, idx: {idx}")
                continue
            else:
                logger.debug(f"Synthesize: image ready for query_id: {query_id}, idx: {idx}")
                images.append(Image.open(image_filename))
        if len(images) < num_images:
            await asyncio.sleep(get("image", "poll_sleep_seconds"))

    yield f"event: message\ndata: Generating response based on {len(images)} images...\n\n"
    if not images:
        yield "event: message\ndata: Failed to load images for synthesis!\n\n"
        yield "event: close\ndata: \n\n"
        return

    is_remote = is_remote_api(LLM_BASE_URL) or LLM_API_KEY
    if is_remote and not LLM_API_KEY:
        yield "event: message\ndata: No API key configured. AI synthesis is unavailable.\n\n"
        yield "event: close\ndata: \n\n"
        return

    def replace_newline_with_br(text):
        return text.replace("\n", "<br>")

    doc_metadata = _query_result_metadata.get(str(query_id), [])
    context_lines = []
    for i, meta in enumerate(doc_metadata[:len(images)]):
        context_lines.append(f"- Document {i+1}: \"{meta['title']}\" — Page {meta['page_number']}")
        if meta.get("text"):
            context_lines.append(f"  Text extract: {meta['text'][:get('image', 'truncation', 'snippet_length')]}")
    doc_context = "\n".join(context_lines) if context_lines else "No metadata available."

    content_parts = []
    for i, img in enumerate(images):
        meta_label = ""
        if i < len(doc_metadata):
            m = doc_metadata[i]
            meta_label = f"[Document {i+1}: \"{m['title']}\", Page {m['page_number']}]"
        if meta_label:
            content_parts.append({"type": "text", "text": meta_label})
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=get("image", "jpeg_quality"))
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    content_parts.append({"type": "text", "text": f"\n\nDocuments provided:\n{doc_context}\n\nQuestion: {query}"})

    headers = build_auth_headers(LLM_API_KEY)

    response_text = ""
    try:
        async with httpx.AsyncClient(timeout=get("llm", "http_timeout_seconds")) as client:
            async with client.stream(
                "POST",
                f"{LLM_BASE_URL}/chat/completions",
                headers=headers,
                json={
                    "model": CHAT_MODEL,
                    "stream": True,
                    "messages": [
                        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                        {"role": "user", "content": content_parts},
                    ],
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[len("data: "):]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            response_text += text
                            yield f"event: message\ndata: {replace_newline_with_br(response_text)}\n\n"
                            await asyncio.sleep(get("llm", "streaming_sleep_seconds"))
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except Exception as e:
        logger.error(f"Synthesis LLM streaming failed: {e}", exc_info=True)
        yield "event: message\ndata: Error generating AI response.\n\n"
    yield "event: close\ndata: \n\n"


async def api_synthesize(request):
    """SSE endpoint for synthesizing an AI answer from selected documents."""
    query_id = request.query_params.get("query_id", "")
    query = request.query_params.get("query", "")
    doc_ids = request.query_params.get("doc_ids", "")
    doc_id_list = [d.strip() for d in doc_ids.split(",") if d.strip()]
    return StreamingResponse(
        synthesize_generator(query=query, doc_ids=doc_id_list, query_id=query_id),
        media_type="text/event-stream",
    )


# =============================================================================
# Application Setup
# =============================================================================

routes = [
    # Static files
    Route("/static/{filepath:path}", serve_static),

    # JSON API endpoints
    Route("/suggestions", api_suggestions),
    Route("/api/search", api_search, methods=["POST"]),
    Route("/api/visual-search", api_visual_search, methods=["POST"]),
    Route("/api/full_image", api_full_image),
    Route("/api/sim-map", api_sim_map),
    Route("/api/upload", api_upload, methods=["POST"]),
    Route("/api/download_url", api_download_url),
    Route("/download_pdf", api_download_pdf),

    # SSE streaming endpoints
    Route("/get-message", get_message),
    Route("/api/synthesize", api_synthesize),
]

middleware = [
    Middleware(CorrelationIdMiddleware),
    Middleware(ErrorBoundaryMiddleware),
]

app = Starlette(
    debug=False,
    routes=routes,
    middleware=middleware,
    on_startup=[startup],
)

# Alias for compatibility with existing uvicorn command
asgi_app = app

if __name__ == "__main__":
    HOT_RELOAD = get("app", "hot_reload")
    logger.info(f"Starting app with hot reload: {HOT_RELOAD}")
    uvicorn.run(
        "main:asgi_app",
        host=get("app", "host"),
        timeout_worker_healthcheck=get("app", "healthcheck_timeout"),
        port=get("app", "port"),
    )
