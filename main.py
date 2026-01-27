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

from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.colpali import SimMapGenerator
from backend.vespa_app import VespaQueryClient
from backend.ingest import ingest_pdf, validate_pdf
from backend.project_store import ProjectStore
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
    href="https://cdnjs.cloudflare.com/ajax/libs/overlayscrollbars/2.10.0/styles/overlayscrollbars.min.css",
    type="text/css",
)
overlayscrollbars_js = Script(
    src="https://cdnjs.cloudflare.com/ajax/libs/overlayscrollbars/2.10.0/browser/overlayscrollbars.browser.es5.min.js"
)
awesomplete_link = Link(
    rel="stylesheet",
    href="https://cdnjs.cloudflare.com/ajax/libs/awesomplete/1.1.7/awesomplete.min.css",
    type="text/css",
)
awesomplete_js = Script(
    src="https://cdnjs.cloudflare.com/ajax/libs/awesomplete/1.1.7/awesomplete.min.js"
)
sselink = Script(
    src="https://cdn.jsdelivr.net/npm/htmx-ext-sse@2.2.4",
    integrity="sha384-A986SAtodyH8eg8x8irJnYUk7i9inVQqYigD6qZ9evobksGNIXfeFvDwLSHcp31N",
    crossorigin="anonymous",
)

# Get log level from environment variable, default to INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

vespa_app: Vespa = VespaQueryClient(logger=logger)
project_store = ProjectStore()
thread_pool = ThreadPoolExecutor()
# Chat LLM config (OpenRouter, OpenAI, or local Ollama — all expose OpenAI-compatible API)

def _resolve_llm_config():
    """Resolve LLM base URL and API key from environment variables."""
    explicit_base = os.getenv("LLM_BASE_URL")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if explicit_base:
        base_url = explicit_base
    elif openai_key and not openrouter_key:
        base_url = "https://api.openai.com/v1"
    else:
        base_url = "https://openrouter.ai/api/v1"

    api_key = openrouter_key or openai_key or ""
    return base_url, api_key

LLM_BASE_URL, LLM_API_KEY = _resolve_llm_config()
CHAT_MODEL = os.getenv("CHAT_MODEL", "google/gemini-2.5-flash")
CHAT_SYSTEM_PROMPT = """If the user query is a question, try your best to answer it based on the provided images.
If the user query can not be interpreted as a question, or if the answer to the query can not be inferred from the images,
answer with the exact phrase "I am sorry, I can't find enough relevant information on these pages to answer your question.".
Your response should be HTML formatted, but only simple tags, such as <b>. <p>, <i>, <br> <ul> and <li> are allowed. No HTML tables.
This means that newlines will be replaced with <br> tags, bold text will be enclosed in <b> tags, and so on.
Do NOT include backticks (`) in your response. Only simple HTML tags and text.
"""
STATIC_DIR = Path("static")
IMG_DIR = STATIC_DIR / "full_images"
SIM_MAP_DIR = STATIC_DIR / "sim_maps"
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(SIM_MAP_DIR, exist_ok=True)


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


# Maximum file size: 250MB
MAX_FILE_SIZE = 250 * 1024 * 1024


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
        if len(tag_list) > 20:
            return UploadError("Maximum 20 tags allowed")
        # Validate individual tag length
        for tag in tag_list:
            if len(tag) > 50:
                return UploadError("Each tag must be 50 characters or less")

    # Validate title length
    if len(title) > 200:
        return UploadError("Title must be 200 characters or less")

    # Validate description length
    if len(description) > 1000:
        return UploadError("Description must be 1000 characters or less")

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

    # Get the hash of the query and ranking value
    query_id = generate_query_id(query, ranking)
    logger.info(f"Query id in /fetch_results: {query_id}, rerank: {do_rerank}")
    # Run the embedding and query against Vespa app
    start_inference = time.perf_counter()
    q_embs, idx_to_token = app.sim_map_generator.get_query_embeddings_and_token_map(
        query
    )
    end_inference = time.perf_counter()
    logger.info(
        f"Inference time for query_id: {query_id} \t {end_inference - start_inference:.2f} seconds"
    )

    start = time.perf_counter()
    # Fetch real search results from Vespa
    result = await vespa_app.get_result_from_query(
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        rerank=do_rerank,
        rerank_hits=20,  # Fetch 20 candidates for reranking
        final_hits=3,    # Return top 3 after reranking
    )
    end = time.perf_counter()
    logger.info(
        f"Search results fetched in {end - start:.2f} seconds. Vespa search time: {result['timing']['searchtime']}"
    )
    search_time = result["timing"]["searchtime"]
    # Safely get total_count with a default of 0
    total_count = result.get("root", {}).get("fields", {}).get("totalCount", 0)

    search_results = vespa_app.results_to_search_results(result, idx_to_token)

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
        await asyncio.sleep(5)
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
    # All images should be downloaded, but best to wait 5 secs
    max_wait = 5
    start_time = time.time()
    while (
        not all([os.path.exists(img_path) for img_path in img_paths])
        and time.time() - start_time < max_wait
    ):
        time.sleep(0.2)
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
    num_images = 3  # Number of images before firing chat request
    max_wait = 10  # seconds
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
            await asyncio.sleep(0.2)

    # yield message with number of images ready
    yield f"event: message\ndata: Generating response based on {len(images)} images...\n\n"
    if not images:
        yield "event: message\ndata: Failed to load images for AI chat!\n\n"
        yield "event: close\ndata: \n\n"
        return

    is_remote = "openrouter.ai" in LLM_BASE_URL or LLM_API_KEY
    if is_remote and not LLM_API_KEY:
        yield "event: message\ndata: No OPENROUTER_API_KEY configured. AI chat is unavailable.\n\n"
        yield "event: close\ndata: \n\n"
        return

    # If newlines are present in the response, the connection will be closed.
    def replace_newline_with_br(text):
        return text.replace("\n", "<br>")

    # Build image content blocks for OpenAI-compatible vision API
    content_parts = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    content_parts.append({"type": "text", "text": f"\n\n Query: {query}"})

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    response_text = ""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
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
                            await asyncio.sleep(0.1)
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


@rt("/app")
def get():
    return Layout(Main(Div(P(f"Connected to Vespa at {vespa_app.url}"), cls="p-4")))


# ── JSON API Routes ─────────────────────────────────────────────────────────


def _build_yql_filter(project_id: int = 0, categories: list = None, document_ids: list = None) -> str:
    """Build a YQL filter clause from project/category/document filters."""
    parts = []
    if project_id:
        parts.append(f"project_id = {int(project_id)}")
    if categories:
        cat_clauses = " or ".join(f'category = "{c}"' for c in categories)
        parts.append(f"({cat_clauses})")
    if document_ids:
        id_clauses = " or ".join(f'id contains "{did}"' for did in document_ids)
        parts.append(f"({id_clauses})")
    return " and ".join(parts)


@app.post("/api/search")
async def api_search(request: Request):
    """JSON search endpoint for the Next.js frontend."""
    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        return JSONResponse({"error": "query is required"}, status_code=400)

    project_id = body.get("project_id", 0)
    categories = body.get("categories", [])
    document_ids = body.get("document_ids", [])
    ranking = body.get("ranking", "hybrid")
    do_rerank = body.get("rerank", True)

    extra_yql_filter = _build_yql_filter(project_id, categories, document_ids)

    query_id = str(generate_query_id(query, ranking))

    start_inference = time.perf_counter()
    q_embs, idx_to_token = app.sim_map_generator.get_query_embeddings_and_token_map(query)
    end_inference = time.perf_counter()
    logger.info(f"API search inference: {end_inference - start_inference:.2f}s")

    start = time.perf_counter()
    result = await vespa_app.get_result_from_query(
        query=query,
        q_embs=q_embs,
        ranking=ranking,
        idx_to_token=idx_to_token,
        rerank=do_rerank,
        rerank_hits=20,
        final_hits=3,
        extra_yql_filter=extra_yql_filter,
    )
    end = time.perf_counter()
    search_time_ms = int((end - start) * 1000)

    total_count = result.get("root", {}).get("fields", {}).get("totalCount", 0)
    children = result.get("root", {}).get("children", [])

    # Build sim map tokens list (non-filtered tokens)
    sim_map_tokens = [
        token for idx, token in idx_to_token.items()
        if not SimMapGenerator.should_filter_token(token)
    ]

    results_json = []
    doc_ids_for_sim = []
    for child in children:
        fields = child.get("fields", {})
        doc_id = fields.get("id", "")
        doc_ids_for_sim.append(doc_id)
        results_json.append({
            "doc_id": doc_id,
            "title": fields.get("title", ""),
            "page_number": fields.get("page_number", 0),
            "snippet": fields.get("snippet", ""),
            "text": fields.get("text", ""),
            "blur_image_url": f"/api/images/{doc_id}/blur",
            "full_image_url": f"/api/images/{doc_id}/full",
            "relevance_score": child.get("relevance", 0),
            "category": fields.get("category", ""),
            "is_region": fields.get("is_region", False),
            "sim_map_tokens": sim_map_tokens,
        })

    # Kick off background sim map generation
    if doc_ids_for_sim:
        get_and_store_sim_maps(
            query_id=query_id,
            query=query,
            q_embs=q_embs,
            ranking=ranking,
            idx_to_token=idx_to_token,
            doc_ids=doc_ids_for_sim,
        )

    return JSONResponse({
        "query_id": query_id,
        "results": results_json,
        "total_count": total_count,
        "search_time_ms": search_time_ms,
    })


@app.get("/api/projects")
async def api_list_projects():
    """List all active Procore projects with per-category document counts."""
    projects = project_store.list_projects()
    return JSONResponse({"projects": projects})


@app.get("/api/projects/{project_id}")
async def api_get_project(project_id: int):
    """Get a single Procore project by ID."""
    project = project_store.get_project(project_id)
    if not project:
        return JSONResponse({"error": "project not found"}, status_code=404)
    return JSONResponse(project)


@app.get("/api/projects/{project_id}/documents")
async def api_list_documents(request: Request, project_id: int):
    """List documents for a project, optionally filtered by category or search term."""
    params = request.query_params
    category = params.get("category", "")
    search_term = params.get("search", "")
    page = int(params.get("page", "1"))
    page_size = int(params.get("page_size", "20"))

    # Build YQL for document listing (BM25-only, no embeddings needed)
    filter_parts = [f"project_id = {int(project_id)}"]
    if category:
        filter_parts.append(f'category = "{category}"')

    yql_filter = " and ".join(filter_parts)
    yql_where = f"userQuery() and {yql_filter}" if search_term else yql_filter

    async with vespa_app.app.asyncio(connections=1) as session:
        body = {
            "yql": f"select id,title,url,page_number,category,snippet,tags from pdf_page where {yql_where} | all(group(url) each(output(count())) each(max(1) each(output(summary()))))",
            "ranking": "bm25" if search_term else "unranked",
            "hits": page_size,
            "offset": (page - 1) * page_size,
            "timeout": "10s",
            "presentation.timing": True,
        }
        if search_term:
            body["query"] = search_term
        response = await session.query(body=body)

    if not response.is_successful():
        return JSONResponse({"error": "query failed"}, status_code=500)

    children = response.json.get("root", {}).get("children", [])
    total = response.json.get("root", {}).get("fields", {}).get("totalCount", 0)

    documents = []
    for child in children:
        fields = child.get("fields", {})
        documents.append({
            "doc_id": fields.get("id", ""),
            "title": fields.get("title", ""),
            "category": fields.get("category", ""),
            "page_number": fields.get("page_number", 0),
            "tags": fields.get("tags", []),
        })

    return JSONResponse({"documents": documents, "total": total})


@app.post("/api/projects/{project_id}/upload")
async def api_upload_document(request: Request, project_id: int):
    """Upload a PDF to a specific project via JSON API."""
    form = await request.form()
    pdf_file = form.get("pdf_file")
    if pdf_file is None:
        return JSONResponse({"error": "pdf_file is required"}, status_code=400)

    file_bytes = await pdf_file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        return JSONResponse({"error": "File exceeds 250MB size limit"}, status_code=400)
    if not pdf_file.filename.lower().endswith(".pdf"):
        return JSONResponse({"error": "Only PDF files are accepted"}, status_code=400)

    is_valid, validation_msg = validate_pdf(file_bytes)
    if not is_valid:
        return JSONResponse({"error": validation_msg}, status_code=400)

    title = form.get("title", "")
    description = form.get("description", "")
    tags_str = form.get("tags", "")
    category = form.get("category", "")
    tag_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    sim_map_gen = app.sim_map_generator
    vespa = vespa_app.app

    try:
        success, message, pages_indexed = ingest_pdf(
            file_bytes=file_bytes,
            filename=pdf_file.filename,
            vespa_app=vespa,
            model=sim_map_gen.model,
            processor=sim_map_gen.processor,
            device=sim_map_gen.device,
            title=title if title.strip() else None,
            description=description,
            tags=tag_list,
            project_id=project_id,
            category=category,
        )
    except Exception as e:
        logger.error(f"API upload error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

    if success:
        return JSONResponse({"success": True, "message": message, "pages_indexed": pages_indexed})
    else:
        return JSONResponse({"error": message}, status_code=500)


@app.get("/api/chat")
async def api_chat(query_id: str, query: str, doc_ids: str):
    """SSE chat endpoint for the Next.js frontend.
    Emits JSON events: event:token data:{"content":"...","done":false}
    """
    async def json_message_generator():
        images = []
        num_images = 3
        max_wait = 10
        start_time = time.time()
        id_list = doc_ids.split(",") if doc_ids else []

        while (
            len(images) < min(num_images, len(id_list))
            and time.time() - start_time < max_wait
        ):
            images = []
            for idx in range(min(num_images, len(id_list))):
                image_filename = IMG_DIR / f"{id_list[idx]}.jpg"
                if os.path.exists(image_filename):
                    images.append(Image.open(image_filename))
            if len(images) < min(num_images, len(id_list)):
                await asyncio.sleep(0.2)

        if not images:
            yield f'event: token\ndata: {json.dumps({"content": "Failed to load images for AI chat.", "done": True})}\n\n'
            return

        is_remote = "openrouter.ai" in LLM_BASE_URL or LLM_API_KEY
        if is_remote and not LLM_API_KEY:
            yield f'event: token\ndata: {json.dumps({"content": "No API key configured. AI chat is unavailable.", "done": True})}\n\n'
            return

        content_parts = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        content_parts.append({"type": "text", "text": f"\n\n Query: {query}"})

        headers = {"Content-Type": "application/json"}
        if LLM_API_KEY:
            headers["Authorization"] = f"Bearer {LLM_API_KEY}"

        response_text = ""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
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
                                yield f'event: token\ndata: {json.dumps({"content": response_text, "done": False})}\n\n'
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except Exception as e:
            logger.error(f"API chat streaming failed: {e}")
            yield f'event: token\ndata: {json.dumps({"content": "Error generating AI response.", "done": True})}\n\n'
            return

        yield f'event: done\ndata: {json.dumps({"content": response_text, "done": True})}\n\n'

    return StreamingResponse(json_message_generator(), media_type="text/event-stream")


@app.get("/api/images/{doc_id}/full")
async def api_full_image(doc_id: str):
    """Return full-res JPEG for a document page."""
    img_path = IMG_DIR / f"{doc_id}.jpg"
    if not os.path.exists(img_path):
        image_data = await vespa_app.get_full_image_from_vespa(doc_id)
        with open(img_path, "wb") as f:
            f.write(base64.b64decode(image_data))
    return FileResponse(str(img_path), media_type="image/jpeg")


@app.get("/api/images/{doc_id}/blur")
async def api_blur_image(doc_id: str):
    """Return blur preview JPEG for a document page."""
    # Fetch from Vespa (blur_image is stored inline)
    async with vespa_app.app.asyncio(connections=1) as session:
        response = await session.query(
            body={
                "yql": f'select blur_image from pdf_page where id contains "{doc_id}"',
                "ranking": "unranked",
                "hits": 1,
            },
        )
    if not response.is_successful():
        return JSONResponse({"error": "not found"}, status_code=404)

    children = response.json.get("root", {}).get("children", [])
    if not children:
        return JSONResponse({"error": "not found"}, status_code=404)

    blur_b64 = children[0]["fields"]["blur_image"]
    blur_bytes = base64.b64decode(blur_b64)
    return Response(content=blur_bytes, media_type="image/jpeg")


@app.get("/api/sim-maps/{query_id}/{idx}/{token_idx}")
async def api_sim_map(query_id: str, idx: int, token_idx: int):
    """Return similarity map PNG (404 if not ready yet)."""
    sim_map_path = SIM_MAP_DIR / f"{query_id}_{idx}_{token_idx}.png"
    if not os.path.exists(sim_map_path):
        return JSONResponse({"error": "not ready"}, status_code=404)
    return FileResponse(str(sim_map_path), media_type="image/png")


@app.get("/api/suggestions")
async def api_suggestions(query: str = "", project_id: int = 0):
    """Return search suggestions as JSON."""
    query = query.lower().strip()
    if query:
        suggestions = await vespa_app.get_suggestions(query)
        return JSONResponse({"suggestions": suggestions})
    return JSONResponse({"suggestions": []})


if __name__ == "__main__":
    HOT_RELOAD = os.getenv("HOT_RELOAD", "False").lower() == "true"
    logger.info(f"Starting app with hot reload: {HOT_RELOAD}")
    uvicorn.run("main:app", host="0.0.0.0", timeout_worker_healthcheck=30, port=7860)
    # serve(port=7860, reload=HOT_RELOAD)
