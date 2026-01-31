"""
Agent mode for multi-step reasoning over visual documents.

The agent can iteratively search, retrieve documents, and synthesize answers
using LLM function calling through the OpenAI-compatible API (OpenRouter,
OpenAI, or local Ollama).
"""

import base64
import io
import json
from pathlib import Path
from typing import AsyncGenerator

import httpx
from PIL import Image

from backend.core.config import get
from backend.core.logging_config import get_logger
from backend.connectors.llm.config import resolve_llm_config, get_chat_model, is_remote_api, build_auth_headers

logger = get_logger(__name__)

# Tool definitions for OpenAI-compatible function calling
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search the document corpus with a query. Use this to find relevant pages. You can reformulate the query to find better results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant document pages. Be specific and targeted.",
                    },
                    "ranking": {
                        "type": "string",
                        "description": "Ranking method: 'hybrid' (best overall), 'colpali' (visual), or 'bm25' (text-only).",
                        "enum": ["hybrid", "colpali", "bm25"],
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_page_text",
            "description": "Get the full text content of a previously retrieved document page by its index in the results. Use this when you need to read the text more carefully.",
            "parameters": {
                "type": "object",
                "properties": {
                    "result_index": {
                        "type": "integer",
                        "description": "The index (0-based) of the result from the most recent search to get text from.",
                    },
                },
                "required": ["result_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "provide_answer",
            "description": "Provide the final answer to the user's question after gathering enough information. Call this when you have enough context to answer. Your answer MUST cite specific document titles and page numbers for every claim using the format: (Source: [Title], Page [N]). End with a Sources section listing all referenced documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "The final answer in HTML format. MUST include citations with document title and page number for every claim. Use only simple tags: <b>, <p>, <i>, <br>, <ul>, <li>. No backticks or tables. End with a Sources section.",
                    },
                },
                "required": ["answer"],
            },
        },
    },
]

AGENT_SYSTEM_PROMPT = """You are a document retrieval agent. Your job is to answer the user's question by searching through a corpus of PDF documents. You MUST answer ONLY from the documents you find. Do NOT use outside knowledge.

TOOLS:
1. search_documents - Search for relevant pages. You can search multiple times with different queries.
2. get_page_text - Read the full text of a specific result from your most recent search.
3. provide_answer - Give your final answer when you have enough information.

STRATEGY:
- Start by searching with the user's query or a reformulated version.
- If the initial results don't fully answer the question, search again with different terms.
- Use get_page_text to read document details when you need more context.
- You can make up to 5 tool calls before providing an answer.
- Look at both the images and text of results to form your answer.

STRICT CITATION RULES:
- Every factual claim in your answer MUST cite the specific document title and page number where you found it.
- Use this citation format: <b>(Source: [Document Title], Page [N])</b>
- If you cannot find relevant information after searching, say: "I could not find enough information in the available documents to answer this question."
- NEVER fabricate information or draw on knowledge outside the retrieved documents.
- End your answer with a <b>Sources</b> section listing all documents and pages referenced.

FORMAT: Use only simple HTML tags: <b>, <p>, <i>, <br>, <ul>, <li>. No backticks or tables.
"""

MAX_AGENT_STEPS = get("agent", "max_steps")
IMG_DIR = Path(get("agent", "img_dir"))


class AgentSession:
    """Manages a single agent reasoning session."""

    def __init__(self, vespa_client, sim_map_generator, query: str):
        self.vespa_client = vespa_client
        self.sim_map_generator = sim_map_generator
        self.query = query
        self.current_results = []
        self.all_doc_ids = []

    async def _search(self, search_query: str, ranking: str = "hybrid") -> dict:
        """Execute a search against Vespa and return formatted results."""
        q_embs, idx_to_token = self.sim_map_generator.get_query_embeddings_and_token_map(
            search_query
        )

        result = await self.vespa_client.get_result_from_query(
            query=search_query,
            q_embs=q_embs,
            ranking=ranking,
            idx_to_token=idx_to_token,
            rerank=True,
            rerank_hits=get("search", "rerank_hits"),
            final_hits=get("search", "final_hits"),
        )

        children = result.get("root", {}).get("children", [])
        self.current_results = children

        results_summary = []
        for i, child in enumerate(children):
            fields = child.get("fields", {})
            doc_id = fields.get("id", "")
            if doc_id and doc_id not in self.all_doc_ids:
                self.all_doc_ids.append(doc_id)
            results_summary.append({
                "index": i,
                "title": fields.get("title", "Unknown"),
                "page_number": fields.get("page_number", 0) + 1,
                "relevance": child.get("relevance", 0),
                "snippet": fields.get("snippet", "")[:get("agent", "snippet_preview_length")],
                "text_preview": (fields.get("text", "") or "")[:get("agent", "text_preview_length")],
            })

        return {
            "num_results": len(children),
            "results": results_summary,
        }

    def _get_page_text(self, result_index: int) -> dict:
        """Get full text from a result by index."""
        if result_index < 0 or result_index >= len(self.current_results):
            return {"error": f"Invalid index {result_index}. Available: 0-{len(self.current_results)-1}"}

        fields = self.current_results[result_index].get("fields", {})
        return {
            "title": fields.get("title", "Unknown"),
            "page_number": fields.get("page_number", 0) + 1,
            "text": fields.get("text", "No text available"),
            "url": fields.get("url", ""),
        }

    async def _collect_images(self) -> list:
        """Collect available images for the gathered doc_ids."""
        images = []

        max_images = get("agent", "max_images")
        for doc_id in self.all_doc_ids[:max_images]:
            img_path = IMG_DIR / f"{doc_id}.jpg"
            if not img_path.exists():
                # Fetch from Vespa
                try:
                    image_data = await self.vespa_client.get_full_image_from_vespa(doc_id)
                    with open(img_path, "wb") as f:
                        f.write(base64.b64decode(image_data))
                except Exception as e:
                    logger.warning(f"Failed to fetch image for {doc_id}: {e}")
                    continue

            if img_path.exists():
                try:
                    images.append(Image.open(img_path))
                except Exception as e:
                    logger.warning(f"Failed to open image {img_path}: {e}")

        return images

    def _build_image_content_parts(self, images: list) -> list:
        """Convert PIL images to OpenAI-compatible content parts."""
        parts = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=get("agent", "jpeg_quality"))
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        return parts

    def _build_image_content_parts_with_metadata(self, images: list) -> list:
        """Convert PIL images to content parts with document metadata labels."""
        parts = []
        # Build metadata lookup from all_doc_ids and current_results
        doc_metadata = {}
        for child in self.current_results:
            fields = child.get("fields", {})
            doc_id = fields.get("id", "")
            if doc_id:
                doc_metadata[doc_id] = {
                    "title": fields.get("title", "Unknown"),
                    "page_number": fields.get("page_number", 0) + 1,
                }

        for i, img in enumerate(images):
            # Add metadata label before each image
            if i < len(self.all_doc_ids):
                doc_id = self.all_doc_ids[i]
                meta = doc_metadata.get(doc_id, {})
                title = meta.get("title", "Unknown")
                page = meta.get("page_number", "?")
                parts.append({
                    "type": "text",
                    "text": f"[Document {i+1}: \"{title}\", Page {page}]",
                })

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=get("agent", "jpeg_quality"))
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        parts.append({"type": "text", "text": f"\n\nQuestion: {self.query}"})
        return parts

    async def run(self) -> AsyncGenerator[str, None]:
        """Run the agent loop, yielding SSE events for each step."""
        yield self._sse_event("status", "Agent starting...")

        base_url, api_key = resolve_llm_config()
        chat_model = get_chat_model()

        if is_remote_api(base_url) and not api_key:
            yield self._sse_event("error", "No API key configured. Agent mode requires OPENROUTER_API_KEY or OPENAI_API_KEY.")
            yield self._sse_event("close", "")
            return

        headers = build_auth_headers(api_key)

        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"User question: {self.query}\n\nPlease search for relevant information and answer the question."},
        ]

        yield self._sse_event("thinking", f"Analyzing query: \"{self.query}\"")

        steps_taken = 0
        final_answer = None

        try:
            async with httpx.AsyncClient(timeout=get("agent", "client_timeout_seconds")) as client:
                while steps_taken < MAX_AGENT_STEPS:
                    # Call LLM with tools
                    try:
                        resp = await client.post(
                            f"{base_url}/chat/completions",
                            headers=headers,
                            json={
                                "model": chat_model,
                                "messages": messages,
                                "tools": AGENT_TOOLS,
                                "tool_choice": "auto",
                            },
                        )
                        resp.raise_for_status()
                        response_data = resp.json()
                    except Exception as e:
                        logger.error(f"Agent LLM call failed: {e}", exc_info=True)
                        yield self._sse_event("error", "Agent encountered an error. Please try again.")
                        yield self._sse_event("close", "")
                        return

                    choice = response_data["choices"][0]
                    message = choice["message"]

                    # Append assistant message to conversation
                    messages.append(message)

                    # Check if model wants to call tools
                    tool_calls = message.get("tool_calls", [])

                    if not tool_calls:
                        # Model gave a text response without tool calls
                        content = message.get("content", "")
                        if content:
                            final_answer = content.replace("\n", "<br>")
                        break

                    # Process tool calls
                    for tool_call in tool_calls:
                        fn_name = tool_call["function"]["name"]
                        try:
                            fn_args = json.loads(tool_call["function"]["arguments"])
                        except json.JSONDecodeError:
                            fn_args = {}

                        steps_taken += 1

                        if fn_name == "search_documents":
                            search_query = fn_args.get("query", self.query)
                            ranking = fn_args.get("ranking", "hybrid")
                            yield self._sse_event("tool_call", json.dumps({
                                "tool": "search_documents",
                                "query": search_query,
                                "ranking": ranking,
                                "step": steps_taken,
                            }))

                            result = await self._search(search_query, ranking)
                            tool_response = json.dumps(result)
                            yield self._sse_event("tool_result", json.dumps({
                                "tool": "search_documents",
                                "num_results": result["num_results"],
                                "step": steps_taken,
                            }))

                        elif fn_name == "get_page_text":
                            result_index = int(fn_args.get("result_index", 0))
                            yield self._sse_event("tool_call", json.dumps({
                                "tool": "get_page_text",
                                "result_index": result_index,
                                "step": steps_taken,
                            }))

                            result = self._get_page_text(result_index)
                            tool_response = json.dumps(result)
                            yield self._sse_event("tool_result", json.dumps({
                                "tool": "get_page_text",
                                "title": result.get("title", ""),
                                "step": steps_taken,
                            }))

                        elif fn_name == "provide_answer":
                            final_answer = fn_args.get("answer", "")
                            yield self._sse_event("thinking", "Composing final answer...")
                            tool_response = json.dumps({"status": "answer_accepted"})

                        else:
                            tool_response = json.dumps({"error": f"Unknown tool: {fn_name}"})

                        # Append tool result to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": tool_response,
                        })

                    if final_answer:
                        break

        except Exception as e:
            logger.error(f"Agent session failed: {e}", exc_info=True)
            yield self._sse_event("error", "Agent encountered an error. Please try again.")
            yield self._sse_event("close", "")
            return

        # If no explicit answer was provided, try to get images and generate one
        if not final_answer:
            yield self._sse_event("thinking", "Generating answer from collected context...")
            images = await self._collect_images()
            if images:
                try:
                    fb_base_url, fb_api_key = resolve_llm_config()
                    fb_model = get_chat_model()
                    fb_headers = build_auth_headers(fb_api_key)

                    image_parts = self._build_image_content_parts_with_metadata(images)

                    async with httpx.AsyncClient(timeout=get("agent", "answer_timeout_seconds")) as client:
                        resp = await client.post(
                            f"{fb_base_url}/chat/completions",
                            headers=fb_headers,
                            json={
                                "model": fb_model,
                                "messages": [
                                    {"role": "system", "content": """Answer the user's question using ONLY the provided document images. Do NOT use outside knowledge.
For every claim, cite the document and page where you found it: <b>(Source: [Title], Page [N])</b>.
If you cannot answer from these documents, say: "I could not find enough information in the provided documents to answer this question."
Use only simple HTML tags: <b>, <p>, <i>, <br>, <ul>, <li>. No backticks or tables.
End with a <b>Sources</b> section listing all referenced documents and pages."""},
                                    {"role": "user", "content": image_parts},
                                ],
                            },
                        )
                        resp.raise_for_status()
                        answer_data = resp.json()
                        content = answer_data["choices"][0]["message"].get("content", "")
                        if content:
                            final_answer = content.replace("\n", "<br>")
                except Exception as e:
                    logger.error(f"Agent answer generation failed: {e}", exc_info=True)
                    final_answer = "I encountered an error while generating the answer."
            else:
                final_answer = "I am sorry, I couldn't find enough relevant information to answer your question."

        # Stream the final answer
        final_answer = final_answer.replace("\n", "<br>")
        yield self._sse_event("answer", final_answer)
        yield self._sse_event("close", "")

    def _sse_event(self, event: str, data: str) -> str:
        """Format an SSE event."""
        return f"event: {event}\ndata: {data}\n\n"


async def run_agent(
    vespa_client,
    sim_map_generator,
    query: str,
) -> AsyncGenerator[str, None]:
    """
    Run the agent and yield SSE events.

    Events emitted:
    - status: General status updates
    - thinking: Agent reasoning steps
    - tool_call: Tool being called (JSON with tool name and args)
    - tool_result: Tool result summary (JSON)
    - answer: The final answer (HTML)
    - error: Error messages
    - close: End of stream
    """
    session = AgentSession(vespa_client, sim_map_generator, query)
    async for event in session.run():
        yield event
