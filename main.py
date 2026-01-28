import asyncio
import base64
import io
import json
import os
import time
import uuid
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from fastcore.parallel import threaded
from fasthtml.common import (
    Aside,
    Div,
    FileResponse,
    HighlightJS,
    Img,
    JSONResponse,
    Link,
    Main,
    P,
    RedirectResponse,
    Script,
    StreamingResponse,
    UploadFile,
    fast_app,
)
from PIL import Image
from shad4fast import ShadHead
from vespa.application import Vespa

from backend import config
from backend.llm_config import resolve_llm_config, get_chat_model, is_remote_api, build_auth_headers
from backend.colpali import SimMapGenerator
from backend.vespa_app import VespaQueryClient
from backend.ingest import ingest_pdf, validate_pdf
from backend.llm_rerank import llm_rerank_results, is_llm_rerank_enabled, get_llm_rerank_candidates
from frontend.app import (
    AboutThisDemo,
    ChatResult,
    Home,
    Search,
    SearchBox,
    SearchResult,
    SimMapButtonPoll,
    SimMapButtonReady,
    UploadPage,
    UploadSidebar,
    UploadSuccess,
    UploadError,
)
from frontend.layout import Layout
import uvicorn

highlight_js_theme_link = Link(id="highlight-theme", rel="stylesheet", href="")
highlight_js_theme = Script(src="/static/js/highlightjs-theme.js")
highlight_js = HighlightJS(
    langs=["python", "javascript", "java", "json", "xml"],
    dark="github-dark",
    light="github",
)

overlayscrollbars_link = Link(
    rel="stylesheet",
    href=config.get("app", "cdn", "overlayscrollbars_css"),
    type="text/css",
)
overlayscrollbars_js = Script(
    src=config.get("app", "cdn", "overlayscrollbars_js")
)
awesomplete_link = Link(
    rel="stylesheet",
    href=config.get("app", "cdn", "awesomplete_css"),
    type="text/css",
)
awesomplete_js = Script(
    src=config.get("app", "cdn", "awesomplete_js")
)
sselink = Script(
    src=config.get("app", "cdn", "htmx_sse_js"),
    integrity=config.get("app", "cdn", "htmx_sse_integrity"),
    crossorigin="anonymous",
)

# Get log level from config
LOG_LEVEL = config.get("app", "log_level").upper()
# Configure logger
logger = logging.getLogger("vespa_app")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter(
        "%(levelname)s: \t %(asctime)s \t %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
logger.addHandler(handler)
logger.setLevel(getattr(logging, LOG_LEVEL))

app, rt = fast_app(
    htmlkw={"cls": "grid h-full"},
    pico=False,
    hdrs=(
        highlight_js,
        highlight_js_theme_link,
        highlight_js_theme,
        overlayscrollbars_link,
        overlayscrollbars_js,
        awesomplete_link,
        awesomplete_js,
        sselink,
        ShadHead(tw_cdn=False, theme_handle=True),
    ),
)
vespa_app: Vespa = VespaQueryClient(logger=logger)
thread_pool = ThreadPoolExecutor()
# Chat LLM config (OpenRouter, OpenAI, or local Ollama — all expose OpenAI-compatible API)
LLM_BASE_URL, LLM_API_KEY = resolve_llm_config()
CHAT_MODEL = get_chat_model()
CHAT_SYSTEM_PROMPT = """You are a document research assistant. You MUST answer the user's question using ONLY the provided document pages. Do NOT use outside knowledge.

STRICT RULES:
1. Base your answer EXCLUSIVELY on the content visible in the provided document images and text extracts. Never supplement with general knowledge.
2. ALWAYS cite your sources. For every claim, reference the specific document and page where you found it using this format: <b>(Source: [Document Title], Page [N])</b>
3. If the documents do not contain enough information to answer the question, respond with exactly: "I could not find enough information in the provided documents to answer this question."
4. If only partial information is available, answer what you can from the documents, clearly state what is not covered, and still cite every claim.
5. Each document image is labeled with its title and page number. Use these labels in your citations.

RESPONSE FORMAT:
- Use only these HTML tags: <b>, <p>, <i>, <br>, <ul>, <li>. No HTML tables.
- Do NOT include backticks (`) or markdown formatting.
- End your response with a <b>Sources</b> section listing each document and page you referenced.
"""
STATIC_DIR = Path(config.get("app", "static_dir"))
IMG_DIR = Path(config.get("app", "img_dir"))
SIM_MAP_DIR = Path(config.get("app", "sim_map_dir"))
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(SIM_MAP_DIR, exist_ok=True)

# In-memory cache: query_id -> list of doc metadata dicts for chat grounding
_query_result_metadata: dict[str, list[dict]] = {}


@app.on_event("startup")
def load_model_on_startup():
    app.sim_map_generator = SimMapGenerator(logger=logger)
    return


@app.on_event("startup")
async def keepalive():
    asyncio.create_task(poll_vespa_keepalive())
    return


def generate_query_id(query, ranking_value):
    hash_input = (query + ranking_value).encode("utf-8")
    return hash(hash_input)


@rt("/static/{filepath:path}")
def serve_static(filepath: str):
    return FileResponse(STATIC_DIR / filepath)


@rt("/")
def get(session):
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return Layout(Main(Home()), is_home=True)


@rt("/about-this-demo")
def get():
    return Layout(Main(AboutThisDemo()))


MAX_FILE_SIZE = config.get("app", "max_file_size_mb") * 1024 * 1024


@rt("/upload")
def get():
    """Render the upload page."""
    return Layout(
        Main(UploadPage(), cls="border-t"),
        Aside(
            UploadSidebar(),
            cls="border-t border-l hidden md:block",
        ),
    )


@rt("/upload")
async def post(
    pdf_file: UploadFile,
    title: str = "",
    description: str = "",
    tags: str = "",
    detect_regions: str = "",
    use_vlm: str = "",
):
    """Handle PDF file upload and ingestion."""
    # Check if file was provided
    if pdf_file is None or pdf_file.filename == "":
        logger.warning("Upload attempted without file")
        return UploadError("Please select a PDF file")

    # Read file content
    try:
        file_bytes = await pdf_file.read()
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}")
        return UploadError("Error reading uploaded file")

    # Validate file size
    if len(file_bytes) > MAX_FILE_SIZE:
        logger.warning(f"File too large: {len(file_bytes)} bytes")
        return UploadError("File exceeds 250MB size limit")

    # Validate file is a PDF
    if not pdf_file.filename.lower().endswith(".pdf"):
        return UploadError("Only PDF files are accepted")

    # Validate PDF integrity
    is_valid, validation_msg = validate_pdf(file_bytes)
    if not is_valid:
        logger.warning(f"PDF validation failed: {validation_msg}")
        return UploadError(validation_msg)

    # Parse tags
    tag_list = []
    if tags.strip():
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        # Validate tag count
        max_tags = config.get("app", "validation", "max_tags")
        if len(tag_list) > max_tags:
            return UploadError(f"Maximum {max_tags} tags allowed")
        # Validate individual tag length
        max_tag_length = config.get("app", "validation", "max_tag_length")
        for tag in tag_list:
            if len(tag) > max_tag_length:
                return UploadError(f"Each tag must be {max_tag_length} characters or less")

    # Validate title length
    max_title_length = config.get("app", "validation", "max_title_length")
    if len(title) > max_title_length:
        return UploadError(f"Title must be {max_title_length} characters or less")

    # Validate description length
    max_desc_length = config.get("app", "validation", "max_description_length")
    if len(description) > max_desc_length:
        return UploadError(f"Description must be {max_desc_length} characters or less")

    # Get the ColPali model from the app
    sim_map_gen = app.sim_map_generator
    model = sim_map_gen.model
    processor = sim_map_gen.processor
    device = sim_map_gen.device

    # Get Vespa app
    vespa = vespa_app.app

    # Process the PDF
    enable_regions = detect_regions.lower() in ("on", "true", "1", "yes")
    enable_vlm = use_vlm.lower() in ("on", "true", "1", "yes")

    try:
        success, message, pages_indexed = ingest_pdf(
            file_bytes=file_bytes,
            filename=pdf_file.filename,
            vespa_app=vespa,
            model=model,
            processor=processor,
            device=device,
            title=title if title.strip() else None,
            description=description,
            tags=tag_list,
            detect_drawing_regions=enable_regions,
            use_vlm_detection=enable_vlm,
        )
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        return UploadError(f"Error processing document: {str(e)}")

    if success:
        final_title = title.strip() if title.strip() else Path(pdf_file.filename).stem
        logger.info(f"Successfully uploaded: {final_title} ({pages_indexed} pages)")
        return UploadSuccess(title=final_title, pages_indexed=pages_indexed)
    else:
        logger.error(f"Upload failed: {message}")
        return UploadError(message)


@rt("/search")
def get(request, query: str = "", ranking: str = "hybrid"):
    logger.info(f"/search: Fetching results for query: {query}, ranking: {ranking}")

    # Always render the SearchBox first
    if not query:
        # Show SearchBox and a message for missing query
        return Layout(
            Main(
                Div(
                    SearchBox(query_value=query, ranking_value=ranking),
                    Div(
                        P(
                            "No query provided. Please enter a query.",
                            cls="text-center text-muted-foreground",
                        ),
                        cls="p-10",
                    ),
                    cls="grid",
                )
            )
        )
    # Generate a unique query_id based on the query and ranking value
    query_id = generate_query_id(query, ranking)
    # Show the loading message if a query is provided
    return Layout(
        Main(Search(request), data_overlayscrollbars_initialize=True, cls="border-t"),
        Aside(
            ChatResult(query_id=query_id, query=query),
            cls="border-t border-l hidden md:block",
        ),
    )  # Show SearchBox and Loading message initially


@rt("/fetch_results")
async def get(session, request, query: str, ranking: str, rerank: str = "true"):
    if "hx-request" not in request.headers:
        return RedirectResponse("/search")

    # Parse rerank parameter (default to True for better results)
    do_rerank = rerank.lower() in ("true", "1", "yes")
    do_llm_rerank = is_llm_rerank_enabled()
    final_hits = config.get("search", "final_hits")

    # Get the hash of the query and ranking value
    query_id = generate_query_id(query, ranking)
    logger.info(
        f"Query id in /fetch_results: {query_id}, rerank: {do_rerank}, llm_rerank: {do_llm_rerank}"
    )
    # Run the embedding and query against Vespa app
    start_inference = time.perf_counter()
    q_embs, idx_to_token = app.sim_map_generator.get_query_embeddings_and_token_map(
        query
    )
    end_inference = time.perf_counter()
    logger.info(
        f"Inference time for query_id: {query_id} \t {end_inference - start_inference:.2f} seconds"
    )

    # When LLM reranking is enabled, get more candidates from MaxSim so the
    # LLM has a richer set to reorder before we take the final top results.
    maxsim_final_hits = get_llm_rerank_candidates() if do_llm_rerank else final_hits

    start = time.perf_counter()
    # Fetch real search results from Vespa
    result = await vespa_app.get_result_from_query(
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        rerank=do_rerank,
        rerank_hits=config.get("search", "rerank_hits"),
        final_hits=maxsim_final_hits,  # More candidates when LLM reranking follows
    )
    end = time.perf_counter()
    logger.info(
        f"Search results fetched in {end - start:.2f} seconds. Vespa search time: {result['timing']['searchtime']}"
    )

    # Optional LLM reranking pass on MaxSim candidates
    if do_llm_rerank and result.get("root", {}).get("children"):
        start_llm = time.perf_counter()
        result["root"]["children"] = await llm_rerank_results(
            query=query,
            results=result["root"]["children"],
            top_k=final_hits,
        )
        end_llm = time.perf_counter()
        logger.info(f"LLM reranking took {end_llm - start_llm:.2f} seconds")

    search_time = result["timing"]["searchtime"]
    # Safely get total_count with a default of 0
    total_count = result.get("root", {}).get("fields", {}).get("totalCount", 0)

    search_results = vespa_app.results_to_search_results(result, idx_to_token)

    # Cache document metadata for chat grounding (title, page, snippet per result)
    _query_result_metadata[str(query_id)] = [
        {
            "doc_id": r["fields"].get("id", ""),
            "title": r["fields"].get("title", "Unknown"),
            "page_number": r["fields"].get("page_number", 0) + 1,
            "snippet": (r["fields"].get("snippet", "") or "")[:config.get("image", "truncation", "snippet_length")],
            "text": (r["fields"].get("text", "") or "")[:config.get("image", "truncation", "text_length")],
        }
        for r in search_results
    ]

    get_and_store_sim_maps(
        query_id=query_id,
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        doc_ids=[result["fields"]["id"] for result in search_results],
    )
    return SearchResult(search_results, query, query_id, search_time, total_count)


def get_results_children(result):
    search_results = (
        result["root"]["children"]
        if "root" in result and "children" in result["root"]
        else []
    )
    return search_results


async def poll_vespa_keepalive():
    while True:
        await asyncio.sleep(config.get("app", "keepalive_interval_seconds"))
        await vespa_app.keepalive()
        logger.debug(f"Vespa keepalive: {time.time()}")


@threaded
def get_and_store_sim_maps(
    query_id, query: str, q_embs, ranking, idx_to_token, doc_ids
):
    ranking_sim = ranking + "_sim"
    vespa_sim_maps = vespa_app.get_sim_maps_from_query(
        query=query,
        q_embs=q_embs,
        ranking=ranking_sim,
        idx_to_token=idx_to_token,
    )
    img_paths = [IMG_DIR / f"{doc_id}.jpg" for doc_id in doc_ids]
    max_wait = config.get("image", "max_wait_seconds")
    poll_sleep = config.get("image", "poll_sleep_seconds")
    start_time = time.time()
    while (
        not all([os.path.exists(img_path) for img_path in img_paths])
        and time.time() - start_time < max_wait
    ):
        time.sleep(poll_sleep)
    if not all([os.path.exists(img_path) for img_path in img_paths]):
        logger.warning(f"Images not ready in 5 seconds for query_id: {query_id}")
        return False
    sim_map_generator = app.sim_map_generator.gen_similarity_maps(
        query=query,
        query_embs=q_embs,
        token_idx_map=idx_to_token,
        images=img_paths,
        vespa_sim_maps=vespa_sim_maps,
    )
    for idx, token, token_idx, blended_img_base64 in sim_map_generator:
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
                logger.error(f"Background image download failed for {doc_id}: {e}")


@app.get("/get_sim_map")
async def get_sim_map(query_id: str, idx: int, token: str, token_idx: int):
    """
    Endpoint that each of the sim map button polls to get the sim map image
    when it is ready. If it is not ready, returns a SimMapButtonPoll, that
    continues to poll every 1 second.
    """
    sim_map_path = SIM_MAP_DIR / f"{query_id}_{idx}_{token_idx}.png"
    if not os.path.exists(sim_map_path):
        logger.debug(
            f"Sim map not ready for query_id: {query_id}, idx: {idx}, token: {token}"
        )
        return SimMapButtonPoll(
            query_id=query_id, idx=idx, token=token, token_idx=token_idx
        )
    else:
        return SimMapButtonReady(
            query_id=query_id,
            idx=idx,
            token=token,
            token_idx=token_idx,
            img_src=sim_map_path,
        )


@app.get("/full_image")
async def full_image(doc_id: str):
    """
    Endpoint to get the full quality image for a given result id.
    """
    img_path = IMG_DIR / f"{doc_id}.jpg"
    if not os.path.exists(img_path):
        image_data = await vespa_app.get_full_image_from_vespa(doc_id)
        # image data is base 64 encoded string. Save it to disk as jpg.
        with open(img_path, "wb") as f:
            f.write(base64.b64decode(image_data))
        logger.debug(f"Full image saved to disk for doc_id: {doc_id}")
    else:
        with open(img_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
    return Img(
        src=f"data:image/jpeg;base64,{image_data}",
        alt="something",
        cls="result-image w-full h-full object-contain",
    )


@rt("/suggestions")
async def get_suggestions(query: str = ""):
    """Endpoint to get suggestions as user types in the search box"""
    query = query.lower().strip()

    if query:
        suggestions = await vespa_app.get_suggestions(query)
        if len(suggestions) > 0:
            return JSONResponse({"suggestions": suggestions})

    return JSONResponse({"suggestions": []})


async def message_generator(query_id: str, query: str, doc_ids: list):
    """Generator function to yield SSE messages for chat response"""
    images = []
    num_images = config.get("search", "num_images")
    max_wait = config.get("image", "max_wait_chat_seconds")
    start_time = time.time()
    # Check if full images are ready on disk
    while (
        len(images) < min(num_images, len(doc_ids))
        and time.time() - start_time < max_wait
    ):
        images = []
        for idx in range(num_images):
            image_filename = IMG_DIR / f"{doc_ids[idx]}.jpg"
            if not os.path.exists(image_filename):
                logger.debug(
                    f"Message generator: Full image not ready for query_id: {query_id}, idx: {idx}"
                )
                continue
            else:
                logger.debug(
                    f"Message generator: image ready for query_id: {query_id}, idx: {idx}"
                )
                images.append(Image.open(image_filename))
        if len(images) < num_images:
            await asyncio.sleep(config.get("image", "poll_sleep_seconds"))

    # yield message with number of images ready
    yield f"event: message\ndata: Generating response based on {len(images)} images...\n\n"
    if not images:
        yield "event: message\ndata: Failed to load images for AI chat!\n\n"
        yield "event: close\ndata: \n\n"
        return

    is_remote = is_remote_api(LLM_BASE_URL) or LLM_API_KEY
    if is_remote and not LLM_API_KEY:
        yield "event: message\ndata: No OPENROUTER_API_KEY configured. AI chat is unavailable.\n\n"
        yield "event: close\ndata: \n\n"
        return

    # If newlines are present in the response, the connection will be closed.
    def replace_newline_with_br(text):
        return text.replace("\n", "<br>")

    # Build document context from cached metadata
    doc_metadata = _query_result_metadata.get(query_id, [])
    context_lines = []
    for i, meta in enumerate(doc_metadata[:len(images)]):
        context_lines.append(
            f"- Document {i+1}: \"{meta['title']}\" — Page {meta['page_number']}"
        )
        if meta.get("text"):
            context_lines.append(f"  Text extract: {meta['text'][:config.get('image', 'truncation', 'snippet_length')]}")
    doc_context = "\n".join(context_lines) if context_lines else "No metadata available."

    # Build image content blocks for OpenAI-compatible vision API
    content_parts = []
    for i, img in enumerate(images):
        meta_label = ""
        if i < len(doc_metadata):
            m = doc_metadata[i]
            meta_label = f"[Document {i+1}: \"{m['title']}\", Page {m['page_number']}]"
        if meta_label:
            content_parts.append({"type": "text", "text": meta_label})
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=config.get("image", "jpeg_quality"))
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    content_parts.append({"type": "text", "text": f"\n\nDocuments provided:\n{doc_context}\n\nQuestion: {query}"})

    headers = build_auth_headers(LLM_API_KEY)

    response_text = ""
    try:
        async with httpx.AsyncClient(timeout=config.get("llm", "http_timeout_seconds")) as client:
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
                            await asyncio.sleep(config.get("llm", "streaming_sleep_seconds"))
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except Exception as e:
        logger.error(f"Chat LLM streaming failed: {e}")
        yield f"event: message\ndata: Error generating AI response.\n\n"
    yield "event: close\ndata: \n\n"


@app.get("/get-message")
async def get_message(query_id: str, query: str, doc_ids: str):
    return StreamingResponse(
        message_generator(query_id=query_id, query=query, doc_ids=doc_ids.split(",")),
        media_type="text/event-stream",
    )


@app.post("/api/search")
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
    q_embs, idx_to_token = app.sim_map_generator.get_query_embeddings_and_token_map(
        query
    )

    start = time.perf_counter()
    result = await vespa_app.get_result_from_query(
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        rerank=True,
        rerank_hits=config.get("search", "rerank_hits"),
        final_hits=config.get("search", "final_hits"),
    )
    duration_ms = round((time.perf_counter() - start) * 1000)

    search_results = vespa_app.results_to_search_results(result, idx_to_token)

    # Trigger background sim map + image download (same as /fetch_results)
    doc_ids = [r["fields"]["id"] for r in search_results]
    get_and_store_sim_maps(
        query_id=query_id,
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        doc_ids=doc_ids,
    )

    # Download full images to disk in background so /get-message can use them
    _download_images_bg(doc_ids)

    # Transform Vespa results to JSON-friendly format
    results_json = []
    for idx, sr in enumerate(search_results):
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


@app.get("/api/full_image")
async def api_full_image(doc_id: str):
    """JSON endpoint returning full-resolution image as base64."""
    img_path = IMG_DIR / f"{doc_id}.jpg"
    if not os.path.exists(img_path):
        image_data = await vespa_app.get_full_image_from_vespa(doc_id)
        with open(img_path, "wb") as f:
            f.write(base64.b64decode(image_data))
    else:
        with open(img_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
    return JSONResponse({"image": f"data:image/jpeg;base64,{image_data}"})


# ---------------------------------------------------------------------------
# Procore database API — serves real data from Vespa procore_record schema
# ---------------------------------------------------------------------------

# Map Procore source_table names to frontend DocumentCategory values
_TABLE_TO_CATEGORY = {
    "drawings": "drawing",
    "drawing_revisions": "drawing",
    "drawing_sets": "drawing",
    "drawing_areas": "drawing",
    "rfis": "rfi",
    "submittals": "submittal",
    "specification_sections": "spec",
    "specification_section_revisions": "spec",
    "change_orders": "change_order",
    "commitment_change_orders": "change_order",
    "photos": "photo",
    "daily_logs": "report",
    "timesheets": "report",
}

# Reverse map: category -> list of source tables
_CATEGORY_TO_TABLES: dict[str, list[str]] = {}
for _tbl, _cat in _TABLE_TO_CATEGORY.items():
    _CATEGORY_TO_TABLES.setdefault(_cat, []).append(_tbl)

_PROJECT_COLORS = [
    "#3b82f6", "#8b5cf6", "#10b981", "#f59e0b",
    "#ef4444", "#06b6d4", "#6366f1", "#ec4899",
]

_PROCORE_SCHEMA = config.get("vespa", "procore_record_schema")


def _parse_category_counts(result: dict) -> dict[str, dict[str, int]]:
    """Parse Vespa grouping response into {project_id: {source_table: count}}."""
    counts: dict[str, dict[str, int]] = {}
    root_children = result.get("root", {}).get("children", [])
    for child in root_children:
        if not child.get("id", "").startswith("group:root"):
            continue
        for group_list in child.get("children", []):
            for project_group in group_list.get("children", []):
                project_id = str(project_group.get("value", ""))
                if not project_id or project_id == "0":
                    continue
                table_counts: dict[str, int] = {}
                for inner_list in project_group.get("children", []):
                    for table_group in inner_list.get("children", []):
                        table_name = str(table_group.get("value", ""))
                        count = table_group.get("fields", {}).get("count()", 0)
                        table_counts[table_name] = count
                counts[project_id] = table_counts
    return counts


def _aggregate_categories(table_counts: dict[str, int]) -> list[dict]:
    """Aggregate source_table counts into frontend category counts."""
    category_counts: dict[str, int] = {}
    for table, count in table_counts.items():
        if table == "projects":
            continue
        category = _TABLE_TO_CATEGORY.get(table, "other")
        category_counts[category] = category_counts.get(category, 0) + count
    return [
        {"category": cat, "count": cnt}
        for cat, cnt in sorted(category_counts.items(), key=lambda x: -x[1])
        if cnt > 0
    ]


@app.get("/api/procore/projects")
async def api_procore_projects():
    """List Procore projects with category counts from Vespa."""
    try:
        # Run both queries concurrently
        projects_coro = vespa_app.query_vespa_raw(
            f'select * from {_PROCORE_SCHEMA} where source_table contains "projects"',
            hits=100,
        )
        counts_coro = vespa_app.query_vespa_raw(
            f"select * from {_PROCORE_SCHEMA} where true "
            f"| all(group(project_id) max(100) each(output(count()) "
            f"all(group(source_table) max(50) each(output(count())))))",
            hits=0,
        )
        projects_result, counts_result = await asyncio.gather(
            projects_coro, counts_coro
        )

        project_records = projects_result.get("root", {}).get("children", [])
        project_category_counts = _parse_category_counts(counts_result)

        projects = []
        for idx, record in enumerate(project_records):
            fields = record.get("fields", {})
            metadata = fields.get("metadata", {})
            # source_id is the project's own ID;
            # project_id may be null for project records
            project_id = str(
                fields.get("source_id")
                or metadata.get("id")
                or fields.get("project_id")
                or ""
            )
            if not project_id:
                continue

            table_counts = project_category_counts.get(project_id, {})
            categories = _aggregate_categories(table_counts)
            total_docs = sum(c["count"] for c in categories)

            name = (
                metadata.get("name")
                or metadata.get("display_name")
                or f"Project {project_id}"
            )
            description = metadata.get("address", "")
            if metadata.get("city"):
                description = (
                    f"{description}, {metadata['city']}"
                    if description
                    else metadata["city"]
                )

            projects.append(
                {
                    "id": project_id,
                    "name": name,
                    "description": description,
                    "documentCount": total_docs,
                    "lastAccessedAt": metadata.get("updated_at", ""),
                    "createdAt": metadata.get("created_at", ""),
                    "categories": categories,
                    "color": _PROJECT_COLORS[idx % len(_PROJECT_COLORS)],
                }
            )

        return JSONResponse({"projects": projects})

    except Exception as e:
        logger.error(f"Error fetching Procore projects: {e}")
        return JSONResponse({"projects": [], "error": str(e)}, status_code=500)


@app.get("/api/procore/documents")
async def api_procore_documents(
    project_id: str = "",
    category: str = "",
    search: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """List documents from Procore with optional filtering."""
    try:
        conditions = []

        if project_id:
            conditions.append(f"project_id = {int(project_id)}")

        if category:
            tables = _CATEGORY_TO_TABLES.get(category, [])
            if tables:
                table_clauses = " or ".join(
                    f'source_table contains "{t}"' for t in tables
                )
                conditions.append(f"({table_clauses})")

        # Always exclude project metadata records from document listings
        conditions.append('!(source_table contains "projects")')

        where = " and ".join(conditions) if conditions else "true"

        if search and search.strip():
            # Escape quotes in search term
            safe_search = search.replace('"', '\\"').strip()
            where = f'({where}) and content_text contains "{safe_search}"'

        yql = f"select * from {_PROCORE_SCHEMA} where {where}"
        result = await vespa_app.query_vespa_raw(yql, hits=limit, offset=offset)

        children = result.get("root", {}).get("children", [])
        total = result.get("root", {}).get("fields", {}).get("totalCount", 0)

        documents = []
        for record in children:
            fields = record.get("fields", {})
            metadata = fields.get("metadata", {})
            source_table = fields.get("source_table", "")
            cat = _TABLE_TO_CATEGORY.get(source_table, "other")

            title = (
                metadata.get("title")
                or metadata.get("name")
                or metadata.get("subject")
                or (fields.get("content_text", "") or "")[:100]
                or f"{source_table} record"
            )

            doc_number = (
                metadata.get("number")
                or metadata.get("drawing_number")
                or metadata.get("revision_number")
                or ""
            )

            # Build tags from source_table and available metadata keys
            tags = [source_table]
            if metadata.get("discipline"):
                tags.append(metadata["discipline"])

            documents.append(
                {
                    "id": fields.get("doc_id", ""),
                    "title": title,
                    "documentNumber": str(doc_number),
                    "category": cat,
                    "pageCount": int(metadata.get("page_count", 0) or 0),
                    "uploadedAt": metadata.get("created_at", ""),
                    "tags": tags,
                }
            )

        return JSONResponse({"documents": documents, "total": total})

    except Exception as e:
        logger.error(f"Error fetching Procore documents: {e}")
        return JSONResponse(
            {"documents": [], "total": 0, "error": str(e)}, status_code=500
        )


@rt("/app")
def get():
    return Layout(Main(Div(P(f"Connected to Vespa at {vespa_app.url}"), cls="p-4")))


if __name__ == "__main__":
    HOT_RELOAD = config.get("app", "hot_reload")
    logger.info(f"Starting app with hot reload: {HOT_RELOAD}")
    uvicorn.run(
        "main:app",
        host=config.get("app", "host"),
        timeout_worker_healthcheck=config.get("app", "healthcheck_timeout"),
        port=config.get("app", "port"),
    )
