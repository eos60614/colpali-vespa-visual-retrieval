"""
Agent mode for multi-step reasoning over visual documents.

The agent can iteratively search, retrieve documents, and synthesize answers
using Gemini's function calling capabilities.
"""

import asyncio
import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import AsyncGenerator

import google.generativeai as genai
from PIL import Image

logger = logging.getLogger("vespa_app")

# Tool definitions for Gemini function calling
SEARCH_TOOL = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(
            name="search_documents",
            description="Search the document corpus with a query. Use this to find relevant pages. You can reformulate the query to find better results.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "query": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="The search query to find relevant document pages. Be specific and targeted.",
                    ),
                    "ranking": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="Ranking method: 'hybrid' (best overall), 'colpali' (visual), or 'bm25' (text-only).",
                        enum=["hybrid", "colpali", "bm25"],
                    ),
                },
                required=["query"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="get_page_text",
            description="Get the full text content of a previously retrieved document page by its index in the results. Use this when you need to read the text more carefully.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "result_index": genai.protos.Schema(
                        type=genai.protos.Type.INTEGER,
                        description="The index (0-based) of the result from the most recent search to get text from.",
                    ),
                },
                required=["result_index"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="provide_answer",
            description="Provide the final answer to the user's question after gathering enough information. Call this when you have enough context to answer.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "answer": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="The final answer in HTML format. Use only simple tags: <b>, <p>, <i>, <br>, <ul>, <li>. No backticks or tables.",
                    ),
                },
                required=["answer"],
            ),
        ),
    ]
)

AGENT_SYSTEM_PROMPT = """You are a document retrieval agent. Your job is to answer the user's question by searching through a corpus of PDF documents.

You have access to tools:
1. search_documents - Search for relevant pages. You can search multiple times with different queries.
2. get_page_text - Read the full text of a result from your most recent search.
3. provide_answer - Give your final answer when you have enough information.

Strategy:
- Start by searching with the user's query or a reformulated version.
- If the initial results don't fully answer the question, search again with different terms.
- You can make up to 5 tool calls before providing an answer.
- Look at both the images and text of results to form your answer.
- If you can't find relevant information after searching, say so honestly.

Your final answer should be HTML formatted using only simple tags: <b>, <p>, <i>, <br>, <ul>, <li>.
Do NOT include backticks (`) in your response. Only simple HTML tags and text.
"""

MAX_AGENT_STEPS = 5
IMG_DIR = Path("static/full_images")


class AgentSession:
    """Manages a single agent reasoning session."""

    def __init__(self, vespa_client, sim_map_generator, query: str):
        self.vespa_client = vespa_client
        self.sim_map_generator = sim_map_generator
        self.query = query
        self.steps = []
        self.current_results = []
        self.all_doc_ids = []
        self.images_collected = []

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
            rerank_hits=20,
            final_hits=3,
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
                "snippet": fields.get("snippet", "")[:200],
                "text_preview": (fields.get("text", "") or "")[:300],
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
        max_wait = 5
        start_time = time.time()

        for doc_id in self.all_doc_ids[:5]:  # Max 5 images
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

    async def run(self) -> AsyncGenerator[str, None]:
        """Run the agent loop, yielding SSE events for each step."""
        yield self._sse_event("status", "Agent starting...")

        # Collect images in background for the initial query
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=AGENT_SYSTEM_PROMPT,
            tools=[SEARCH_TOOL],
        )

        chat = model.start_chat()

        # Initial message to the agent
        initial_prompt = f"User question: {self.query}\n\nPlease search for relevant information and answer the question."

        yield self._sse_event("thinking", f"Analyzing query: \"{self.query}\"")

        try:
            response = await chat.send_message_async(initial_prompt)
        except Exception as e:
            logger.error(f"Agent initial call failed: {e}")
            yield self._sse_event("error", f"Agent error: {str(e)}")
            yield self._sse_event("close", "")
            return

        steps_taken = 0
        final_answer = None

        while steps_taken < MAX_AGENT_STEPS:
            # Check if there are function calls
            if not response.candidates or not response.candidates[0].content.parts:
                break

            has_function_call = False
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    has_function_call = True
                    break

            if not has_function_call:
                # Model gave a text response without tool calls - use as answer
                text_parts = []
                for part in response.candidates[0].content.parts:
                    if part.text:
                        text_parts.append(part.text)
                if text_parts:
                    final_answer = "<br>".join(text_parts)
                break

            # Process all function calls in this response
            function_responses = []
            for part in response.candidates[0].content.parts:
                if not part.function_call:
                    continue

                fn_call = part.function_call
                fn_name = fn_call.name
                fn_args = dict(fn_call.args) if fn_call.args else {}

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
                    function_responses.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name="search_documents",
                                response={"result": json.dumps(result)},
                            )
                        )
                    )
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
                    function_responses.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name="get_page_text",
                                response={"result": json.dumps(result)},
                            )
                        )
                    )
                    yield self._sse_event("tool_result", json.dumps({
                        "tool": "get_page_text",
                        "title": result.get("title", ""),
                        "step": steps_taken,
                    }))

                elif fn_name == "provide_answer":
                    final_answer = fn_args.get("answer", "")
                    yield self._sse_event("thinking", "Composing final answer...")
                    break

            if final_answer:
                break

            if not function_responses:
                break

            # Send function responses back to the model
            try:
                response = await chat.send_message_async(function_responses)
            except Exception as e:
                logger.error(f"Agent follow-up call failed: {e}")
                yield self._sse_event("error", f"Agent error: {str(e)}")
                yield self._sse_event("close", "")
                return

        # If no explicit answer was provided, try to get images and generate one
        if not final_answer:
            yield self._sse_event("thinking", "Generating answer from collected context...")
            images = await self._collect_images()
            if images:
                try:
                    answer_model = genai.GenerativeModel(
                        "gemini-2.5-flash",
                        system_instruction="""Answer the user's question based on the provided images.
Use only simple HTML tags: <b>, <p>, <i>, <br>, <ul>, <li>. No backticks or tables.
If you can't answer from the images, say so honestly.""",
                    )
                    answer_response = await answer_model.generate_content_async(
                        images + [f"\n\nQuestion: {self.query}"]
                    )
                    if answer_response.text:
                        final_answer = answer_response.text.replace("\n", "<br>")
                except Exception as e:
                    logger.error(f"Agent answer generation failed: {e}")
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
