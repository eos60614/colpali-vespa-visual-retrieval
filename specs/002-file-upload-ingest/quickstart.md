# Quickstart: File Upload and Ingestion Feature

**Feature**: 002-file-upload-ingest
**Date**: 2026-01-14

## Prerequisites

1. Local Vespa running (`docker compose up -d`)
2. ColPali model downloaded (happens on first app startup)
3. Application running (`python main.py`)

## How to Use

### 1. Navigate to Upload Page

Go to `http://localhost:7860/upload` in your browser.

### 2. Select a PDF File

Click "Choose File" and select a PDF document (up to 250MB).

### 3. Add Metadata (Optional)

- **Title**: Custom name for the document (defaults to filename)
- **Description**: Brief description of the document content
- **Tags**: Comma-separated keywords for improved search (e.g., "finance, report, 2024")

### 4. Upload and Wait

Click "Upload" and wait for processing to complete. The system will:
1. Validate the PDF
2. Extract text from each page
3. Generate visual embeddings
4. Index in Vespa

### 5. Search Your Document

After successful upload, navigate to the search page and query for content from your document.

## Example

Upload a financial report with:
- **Title**: "Q4 2024 Earnings Report"
- **Description**: "Quarterly financial results and outlook"
- **Tags**: "finance, earnings, Q4, 2024"

Then search for "revenue growth 2024" to find relevant pages.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "File exceeds 250MB limit" | Use a smaller PDF or split into multiple files |
| "Password-protected PDF" | Remove password protection before uploading |
| "Invalid PDF" | Ensure file is not corrupted; try re-exporting from source |
| Processing timeout | Large PDFs may take several minutes; be patient |

## Technical Notes

- Uploaded files are processed synchronously (blocking)
- Each page becomes a separate searchable document
- All pages share the same metadata (title, description, tags)
- Documents are immediately searchable after upload completes
