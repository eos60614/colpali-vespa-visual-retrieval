# Research: File Upload and Ingestion with Metadata

> **Note**: This research was conducted for an earlier architecture. The application now uses Starlette (JSON API) + Next.js (frontend). File upload now uses Starlette's UploadFile directly with Next.js form handling.

**Feature**: 002-file-upload-ingest
**Date**: 2026-01-14

## Overview

This document captures research findings for implementing file upload functionality in the ColPali-Vespa visual retrieval application.

---

## 1. File Upload Implementation

**Decision**: Use Starlette's built-in file upload handling with `UploadFile`

**Rationale**:
- Starlette natively supports multipart form uploads
- The `UploadFile` class from Starlette provides async file handling
- Consistent with existing codebase patterns
- No additional dependencies required

**Alternatives Considered**:
- Dropzone.js: Adds unnecessary JavaScript complexity
- Custom AJAX upload: Next.js handles this natively with fetch API

**Implementation Pattern**:
```python
from starlette.requests import Request

# Frontend component
def UploadForm():
    return Form(
        Input(type="file", name="pdf_file", accept=".pdf"),
        Input(type="text", name="title", placeholder="Title (optional)"),
        Input(type="text", name="description", placeholder="Description (optional)"),
        Input(type="text", name="tags", placeholder="Tags (comma-separated)"),
        Button("Upload", type="submit"),
        hx_post="/upload",
        hx_encoding="multipart/form-data"
    )

# Backend endpoint
@rt("/upload")
async def post(pdf_file: UploadFile, title: str = "", description: str = "", tags: str = ""):
    # Handle upload
    pass
```

---

## 2. File Size Validation (250MB limit)

**Decision**: Validate file size on both client-side (for UX) and server-side (for security)

**Rationale**:
- Client-side validation provides immediate feedback
- Server-side validation prevents malicious bypasses
- Starlette's `UploadFile` streams the file, allowing size checks during upload

**Implementation Pattern**:
```python
MAX_FILE_SIZE = 250 * 1024 * 1024  # 250MB in bytes

@rt("/upload")
async def post(pdf_file: UploadFile):
    # Check content-length header first (may not be reliable)
    # Read file in chunks and track size
    contents = await pdf_file.read()
    if len(contents) > MAX_FILE_SIZE:
        return error_response("File exceeds 250MB limit")
```

---

## 3. PDF Validation

**Decision**: Use PyMuPDF (fitz) to validate PDF integrity before processing

**Rationale**:
- Already a project dependency
- Can detect corrupted PDFs and password protection
- Provides immediate feedback to users

**Implementation Pattern**:
```python
import fitz

def validate_pdf(file_bytes: bytes) -> tuple[bool, str]:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if doc.is_encrypted:
            return False, "Password-protected PDFs are not supported"
        page_count = len(doc)
        doc.close()
        return True, f"Valid PDF with {page_count} pages"
    except Exception as e:
        return False, f"Invalid PDF: {str(e)}"
```

---

## 4. Reusing Existing Ingestion Pipeline

**Decision**: Extract core functions from `scripts/feed_data.py` into a reusable module

**Rationale**:
- `feed_data.py` already implements the three-phase pipeline (render → embed → feed)
- Core functions can be extracted without the CLI argument parsing
- Avoids code duplication

**Key Functions to Reuse**:
- `pdf_to_images_worker()`: Converts PDF to images + extracts text
- `generate_embeddings()`: Creates ColPali embeddings
- `feed_document()`: Sends document to Vespa
- `create_blur_image()`: Creates thumbnail
- `image_to_base64()`: Encodes images

**New Module**: `backend/ingest.py` - wraps these for single-file on-demand ingestion

---

## 5. Metadata Storage in Vespa

**Decision**: Extend existing `pdf_page` schema with new fields for user-provided metadata

**Rationale**:
- The schema already has `title`, `text`, and array fields like `questions`
- Adding `description` and `tags` follows the same pattern
- Tags can be indexed for BM25 search

**Schema Changes Required**:
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

**Note**: Schema changes require Vespa redeployment.

---

## 6. Document ID Generation

**Decision**: Use content hash for document ID to enable duplicate detection

**Rationale**:
- MD5 hash of file content provides unique identifier
- Allows detecting if same document uploaded twice
- Follows pattern of existing `{pdf_stem}_page_{num}` IDs

**Implementation Pattern**:
```python
import hashlib

def generate_doc_id(pdf_bytes: bytes, title: str) -> str:
    content_hash = hashlib.md5(pdf_bytes).hexdigest()[:12]
    safe_title = "".join(c if c.isalnum() else "_" for c in title)[:30]
    return f"{safe_title}_{content_hash}"
```

---

## 7. UI Integration

**Decision**: Add "Upload" link to main navigation and create dedicated upload page

**Rationale**:
- Consistent with existing navigation pattern (Home, About)
- Keeps upload UI separate from search interface
- Next.js fetch API allows showing progress/results without page reload

**Location**: Add route `/upload` page in Next.js (`web/src/app/upload/page.tsx`)

---

## Summary

All technical decisions align with existing codebase patterns. No external dependencies needed beyond what's already installed. The main implementation work involves:

1. Creating `backend/ingest.py` by extracting functions from `feed_data.py`
2. Adding upload endpoint and UI component
3. Updating Vespa schema with `description` and `tags` fields
4. Adding navigation link to upload page
