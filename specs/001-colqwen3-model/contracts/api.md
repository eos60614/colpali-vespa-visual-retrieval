# API Contracts: Add ColQwen3 Model Support

> **Note**: This contract was written for an earlier architecture. The application now uses Starlette (JSON API) + Next.js (frontend). The search endpoint now returns JSON.

**Branch**: `001-colqwen3-model` | **Date**: 2026-01-14

## Overview

This document defines the API contract changes for adding ColQwen3 model support. The application uses Starlette with JSON APIs.

---

## Modified Endpoints

### GET /search

Main search page endpoint with model selection.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | No | `""` | Search query text |
| `ranking` | string | No | `"hybrid"` | Ranking method: `colpali`, `bm25`, `hybrid` |
| `model` | string | No | `"colpali"` | Model selection: `colpali`, `colqwen3` |

**Response**: HTML page with search interface

**Example**:
```
GET /search?query=financial+report&ranking=hybrid&model=colqwen3
```

---

### POST /api/search

JSON endpoint for fetching search results.

**Request Body**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query text |
| `ranking` | string | Yes | - | Ranking method |
| `model` | string | No | `"colpali"` | Model to use for query embeddings |

**Response**: JSON with search results

**Error Response** (model load failure):
```json
{
  "error": "Failed to load ColQwen3 model: {error_message}"
}
```

---

### GET /switch_model (New Endpoint)

Endpoint to switch the active model.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Target model: `colpali`, `colqwen3` |

**Response**:

Success (200):
```json
{
  "status": "success",
  "model": "colqwen3",
  "message": "Model switched successfully"
}
```

Error (500):
```json
{
  "status": "error",
  "model": "colqwen3",
  "message": "Failed to load model: {error_details}"
}
```

---

### GET /model_status (New Endpoint)

Endpoint to check current model status.

**Query Parameters**: None

**Response** (200):
```json
{
  "current_model": "colpali",
  "is_loading": false,
  "available_models": [
    {
      "id": "colpali",
      "name": "ColPali",
      "description": "Original ColPali model, good general performance"
    },
    {
      "id": "colqwen3",
      "name": "ColQwen3",
      "description": "Better multilingual support, improved chart/table understanding"
    }
  ]
}
```

---

## Form Data Flow

### SearchBox Component

The SearchBox form now includes model selection:

```
Form
├── Input (name="query")
├── RadioGroup (name="ranking")
│   ├── RadioGroupItem (value="colpali")
│   ├── RadioGroupItem (value="bm25")
│   └── RadioGroupItem (value="hybrid")
├── RadioGroup (name="model")  [NEW]
│   ├── RadioGroupItem (value="colpali")
│   └── RadioGroupItem (value="colqwen3")
└── Button (type="submit")

→ Submits to: POST /api/search with JSON body
```

---

## Error Codes

| Code | Scenario | User Message |
|------|----------|--------------|
| 200 | Success | - |
| 400 | Invalid model parameter | "Invalid model selection. Please choose 'colpali' or 'colqwen3'." |
| 500 | Model load failure | "Failed to load {model} model: {details}" |
| 503 | Model switching in progress | "Model is currently being loaded. Please wait." |

---

## Backward Compatibility

- All existing endpoints continue to work without the `model` parameter
- Default model is `colpali` when parameter is omitted
- Existing bookmarks/URLs without model parameter remain functional
