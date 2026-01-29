---
description: Test search queries against the backend API to see how documents are retrieved
---

## User Input

```text
$ARGUMENTS
```

## Outline

Test what happens when a search query is sent across all documents. Uses the `/api/search` endpoint which runs queries through ColPali embeddings and Vespa's hybrid search (BM25 + semantic).

1. **Setup logging**:
   ```bash
   mkdir -p /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs
   : > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/search-test.log
   ```

2. **Parse arguments**:
   - If no arguments provided, prompt user for a query
   - Arguments format: `<query>` or `<query> --ranking <hybrid|bm25|colpali>`
   - Default ranking: `hybrid`

   Examples:
   - `/search-test what is lsd 400?` - Search with hybrid ranking
   - `/search-test safety regulations --ranking bm25` - BM25 text-only search
   - `/search-test architectural drawings --ranking colpali` - ColPali visual search only

3. **Check backend is running**:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://localhost:7860/api/health 2>/dev/null || echo "NOT_RUNNING"
   ```

   If backend is not running (non-200 response or connection refused):
   - Inform user: "Backend not running. Start it with `/server` first."
   - Stop execution

4. **Execute search query**:
   Parse the query and ranking from arguments, then call the API:
   ```bash
   curl -s -X POST http://localhost:7860/api/search \
     -H "Content-Type: application/json" \
     -d '{"query": "<QUERY>", "ranking": "<RANKING>"}' \
     > /home/nirav60614/projects/colpali-vespa-visual-retrieval/logs/search-test.log 2>&1
   ```

5. **Read and parse results**:
   - Use the Read tool to read `logs/search-test.log`
   - Parse the JSON response

6. **Present results summary**:
   Report:
   - **Query**: The search query sent
   - **Ranking method**: hybrid/bm25/colpali
   - **Duration**: Search time in ms
   - **Total results**: Number of documents found
   - **Top results** (up to 5):
     - Document title
     - Page number
     - Relevance score
     - Snippet preview (first 200 chars)

7. **On error**:
   - If JSON parse error: Show raw response
   - If "error" key in response: Show error message
   - If no results: Note that no documents matched the query
   - If connection error: Suggest checking if backend and Vespa are running

## Notes

- The backend must be running (`python main.py` or `/server`)
- Vespa must be running (`docker-compose up -d`)
- First search after startup may be slow due to model loading
- Ranking options:
  - `hybrid` (default): Combines BM25 text matching + ColPali visual embeddings
  - `bm25`: Text-only search using BM25 scoring
  - `colpali`: Visual-only search using ColPali embeddings
