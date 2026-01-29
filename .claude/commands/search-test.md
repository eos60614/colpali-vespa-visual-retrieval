---
description: Test search queries against the backend API to see how documents are retrieved
---

## User Input

```text
$ARGUMENTS
```

## Outline

Test the full search + LLM synthesis pipeline. Queries go through:
1. ColPali embeddings → Vespa hybrid search (BM25 + semantic)
2. LLM synthesis via OpenRouter for a final AI-generated answer

### Step 1: Setup logging
```bash
mkdir -p /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs
: > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/search-test.log
```

### Step 2: Parse arguments
- Arguments format: `<query>` or `<query> --ranking <hybrid|bm25|colpali>` or `<query> --no-llm`
- Default ranking: `hybrid`
- Default: includes LLM synthesis (use `--no-llm` to skip)

Examples:
- `/search-test what is lsd 400?` - Full pipeline with LLM answer
- `/search-test safety regulations --ranking bm25` - BM25 search + LLM
- `/search-test drawings --no-llm` - Search only, no LLM synthesis

### Step 3: Check backend is running
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:7860/api/health 2>/dev/null || echo "NOT_RUNNING"
```

If backend is not running (non-200 or connection refused):
- Inform user: "Backend not running. Start it with `/server` first."
- Stop execution

### Step 4: Execute search query
Parse the query and ranking from arguments, then call the API:
```bash
curl -s -X POST http://localhost:7860/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "<QUERY>", "ranking": "<RANKING>"}' \
  > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/search-test.log 2>&1
```

### Step 5: Read and parse search results
- Use the Read tool to read `logs/search-test.log`
- Parse the JSON response
- Extract `query_id` and `doc_ids` for synthesis step

### Step 6: Present search results summary
Report:
- **Query**: The search query sent
- **Ranking method**: hybrid/bm25/colpali
- **Duration**: Search time in ms
- **Total results**: Number of documents found
- **Top results** (up to 3):
  - Document title
  - Page number
  - Relevance score

### Step 7: LLM Synthesis (unless --no-llm)
Wait briefly for images to be ready (search triggers background download), then call synthesis:
```bash
sleep 2
curl -s -N "http://localhost:7860/api/synthesize?query=<URL_ENCODED_QUERY>&query_id=<QUERY_ID>&doc_ids=<COMMA_SEPARATED_DOC_IDS>" \
  > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/search-synthesis.log 2>&1
```

### Step 8: Parse and display LLM answer
- Read `logs/search-synthesis.log`
- Parse SSE events (lines starting with `data:`)
- The last complete `data:` line contains the full LLM response
- Display the AI-generated answer under a **LLM Answer** heading

### Step 9: Error handling
- If search fails: Show error message, suggest checking backend/Vespa
- If no results: Note that no documents matched
- If synthesis fails: Show "LLM synthesis failed" with reason (no API key, images not ready, etc.)
- If `--no-llm` flag: Skip steps 7-8, only show search results

## Notes

- Backend must be running (`python main.py` or `/server`)
- Vespa must be running (`docker-compose up -d`)
- LLM synthesis requires `LLM_BASE_URL` and API key configured in `.env`
- First search after startup may be slow due to model loading
- Synthesis sends document images to the LLM for visual understanding
- Ranking options:
  - `hybrid` (default): BM25 text + ColPali visual embeddings
  - `bm25`: Text-only BM25 scoring
  - `colpali`: Visual-only ColPali embeddings
