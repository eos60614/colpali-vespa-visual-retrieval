# Data Model: File Upload and Ingestion with Metadata

**Feature**: 002-file-upload-ingest
**Date**: 2026-01-14

## Overview

This document defines the data entities and their relationships for the file upload feature.

---

## Entities

### 1. UploadedFile (transient)

Represents a file during the upload and processing flow. Not persisted after ingestion completes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file_bytes | bytes | Yes | Raw PDF file content |
| original_filename | string | Yes | Original filename from upload |
| content_hash | string | Yes | MD5 hash of file content (first 12 chars) |
| size_bytes | int | Yes | File size in bytes |
| upload_timestamp | datetime | Yes | When the file was uploaded |

**Validation Rules**:
- `size_bytes` must be ≤ 262,144,000 (250MB)
- File must be valid PDF (not encrypted, not corrupted)

---

### 2. DocumentMetadata (user-provided)

Optional metadata provided by user during upload.

| Field | Type | Required | Default |
|-------|------|----------|---------|
| title | string | No | Original filename (without .pdf) |
| description | string | No | Empty string |
| tags | list[string] | No | Empty list |

**Validation Rules**:
- `title` max length: 200 characters
- `description` max length: 1000 characters
- `tags` max items: 20, each tag max 50 characters

---

### 3. DocumentPage (persisted in Vespa)

Represents a single page from an uploaded PDF. Stored in Vespa `pdf_page` schema.

| Field | Type | Indexed | Description |
|-------|------|---------|-------------|
| id | string | Yes | Unique identifier: `{title_slug}_{hash}_page_{num}` |
| url | string | Yes | Original filename |
| title | string | Yes (BM25) | User-provided or default from filename |
| page_number | int | Yes | 1-indexed page number |
| text | string | Yes (BM25) | OCR-extracted text from page |
| snippet | string | Yes | First 200 chars of text or default |
| description | string | Yes | User-provided description (same for all pages) |
| tags | array[string] | Yes (BM25) | User-provided tags (same for all pages) |
| blur_image | raw | No | Base64 JPEG thumbnail (100px max) |
| full_image | raw | No | Base64 JPEG full resolution |
| embedding | tensor<int8> | Yes (HNSW) | ColPali binary embeddings |
| questions | array[string] | Yes | Empty (not populated by upload) |
| queries | array[string] | Yes | Empty (not populated by upload) |

---

## Entity Relationships

```
UploadedFile (1) ──processes──> (N) DocumentPage
     │
     └── has ──> (1) DocumentMetadata
```

- One uploaded PDF file produces N document pages (one per page)
- All pages from the same upload share the same metadata (title, description, tags)
- The `UploadedFile` entity is transient and discarded after successful ingestion

---

## State Transitions

### Upload Processing Flow

```
[Upload Received]
       │
       ▼
[Validate] ──fail──> [Error Response]
       │
       │ pass
       ▼
[Render Pages]
       │
       ▼
[Generate Embeddings]
       │
       ▼
[Feed to Vespa]
       │
       ▼
[Success Response]
```

**States**:
- `received`: File uploaded, not yet validated
- `validating`: Checking file type, size, PDF integrity
- `rendering`: Converting PDF pages to images, extracting text
- `embedding`: Generating ColPali embeddings for each page
- `feeding`: Sending documents to Vespa
- `complete`: All pages indexed successfully
- `failed`: Error occurred (with error message)

---

## Vespa Schema Updates

The existing `pdf_page.sd` schema requires two new fields:

```
field description type string {
    indexing: summary | index
    match: text
}

field tags type array<string> {
    indexing: summary | index
    match: text
    index: enable-bm25
}
```

**Impact**: Requires Vespa application redeployment after schema change.

---

## ID Generation Strategy

Document IDs follow the pattern: `{title_slug}_{content_hash}_page_{page_number}`

Example: `annual_report_a1b2c3d4e5f6_page_1`

- `title_slug`: Alphanumeric version of title (max 30 chars)
- `content_hash`: First 12 characters of MD5 hash of PDF content
- `page_number`: 1-indexed page number

This allows:
- Human-readable identification
- Duplicate detection via hash
- Unique IDs even for same-titled documents
