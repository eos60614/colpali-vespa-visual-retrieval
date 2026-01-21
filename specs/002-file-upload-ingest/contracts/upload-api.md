# API Contract: File Upload Endpoints

**Feature**: 002-file-upload-ingest
**Date**: 2026-01-14

## Overview

REST-like endpoints for the file upload and ingestion feature, following existing FastHTML patterns.

---

## Endpoints

### 1. GET /upload

**Description**: Render the file upload page with form

**Request**: None (browser navigation)

**Response**: HTML page with upload form

**Example**:
```
GET /upload HTTP/1.1
Host: localhost:7860
```

**Response**: `200 OK` with HTML containing:
- File input (PDF only)
- Title input (optional)
- Description textarea (optional)
- Tags input (optional, comma-separated)
- Submit button

---

### 2. POST /upload

**Description**: Handle file upload and trigger ingestion

**Request**:
- Content-Type: `multipart/form-data`
- Body:
  | Field | Type | Required | Description |
  |-------|------|----------|-------------|
  | pdf_file | file | Yes | PDF file (max 250MB) |
  | title | string | No | Custom document title |
  | description | string | No | Document description |
  | tags | string | No | Comma-separated tags |

**Response Scenarios**:

#### Success (200 OK)
```html
<div class="upload-success">
  <h3>Upload Successful</h3>
  <p>Document "Annual Report" has been processed.</p>
  <p>5 pages indexed and ready for search.</p>
  <a href="/search">Go to Search</a>
</div>
```

#### Validation Error (400 Bad Request)
```html
<div class="upload-error">
  <h3>Upload Failed</h3>
  <p>File exceeds 250MB size limit.</p>
  <a href="/upload">Try Again</a>
</div>
```

#### Invalid PDF (400 Bad Request)
```html
<div class="upload-error">
  <h3>Upload Failed</h3>
  <p>Invalid PDF file: document is password-protected.</p>
  <a href="/upload">Try Again</a>
</div>
```

#### Processing Error (500 Internal Server Error)
```html
<div class="upload-error">
  <h3>Processing Failed</h3>
  <p>Error generating embeddings. Please try again.</p>
  <a href="/upload">Try Again</a>
</div>
```

**Example Request**:
```
POST /upload HTTP/1.1
Host: localhost:7860
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="pdf_file"; filename="report.pdf"
Content-Type: application/pdf

[PDF binary content]
------WebKitFormBoundary
Content-Disposition: form-data; name="title"

Annual Report 2024
------WebKitFormBoundary
Content-Disposition: form-data; name="description"

Company financial performance summary
------WebKitFormBoundary
Content-Disposition: form-data; name="tags"

finance, annual, 2024
------WebKitFormBoundary--
```

---

## HTMX Integration

The upload form uses HTMX for seamless interaction:

```html
<form hx-post="/upload"
      hx-encoding="multipart/form-data"
      hx-target="#upload-result"
      hx-swap="innerHTML">
  <!-- form fields -->
</form>
<div id="upload-result"></div>
```

**Behavior**:
- Form submission handled via HTMX (no page reload)
- Response HTML replaces the `#upload-result` div
- User can upload another file without navigating away

---

## Validation Rules

| Field | Rule | Error Message |
|-------|------|---------------|
| pdf_file | Required | "Please select a PDF file" |
| pdf_file | Must be PDF | "Only PDF files are accepted" |
| pdf_file | Max 250MB | "File exceeds 250MB size limit" |
| pdf_file | Valid PDF | "Invalid PDF: {specific error}" |
| pdf_file | Not encrypted | "Password-protected PDFs are not supported" |
| title | Max 200 chars | "Title must be 200 characters or less" |
| description | Max 1000 chars | "Description must be 1000 characters or less" |
| tags | Max 20 tags | "Maximum 20 tags allowed" |
| tags (each) | Max 50 chars | "Each tag must be 50 characters or less" |

---

## Error Codes

| HTTP Status | Condition |
|-------------|-----------|
| 200 | Success |
| 400 | Validation error (file type, size, format) |
| 413 | Payload too large (file > 250MB) |
| 500 | Server error (embedding/Vespa failure) |
