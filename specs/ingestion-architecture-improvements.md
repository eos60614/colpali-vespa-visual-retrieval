# Ingestion Architecture Improvements

## Overview

This document outlines improvements to the ingestion architecture to address three key requirements:

1. **Smart page size detection and splitting**
2. **Dual text extraction (OCR + layer text)**
3. **Enhanced metadata for queryable fields**

---

## 1. Smart Page Size Detection and Splitting

### Current State
- Single threshold: 2.8M pixels triggers region detection (`ki55.toml:128`)
- Detection methods: pdf_vector, heuristic, content-aware tiling, VLM
- All pages rendered at fixed 150 DPI regardless of size

### Proposed Improvements

#### 1.1 Page Size Categories
Define standard size categories for intelligent processing:

```python
class PageSizeCategory(Enum):
    STANDARD = "standard"      # A4/Letter: < 1M pixels
    LARGE = "large"            # Tabloid/A3: 1M - 3M pixels
    OVERSIZED = "oversized"    # Architectural: 3M - 10M pixels
    MASSIVE = "massive"        # Large format: > 10M pixels
```

#### 1.2 Adaptive DPI
Adjust rendering DPI based on page size to balance quality vs. processing time:

| Category   | DPI  | Max Dimension | Rationale |
|------------|------|---------------|-----------|
| Standard   | 150  | ~1500px       | Full quality for normal docs |
| Large      | 120  | ~2000px       | Slightly reduced, still readable |
| Oversized  | 100  | ~3000px       | Focus on structure, text via OCR |
| Massive    | 72   | ~4000px       | Always split into regions |

#### 1.3 Split Strategy by Category

```python
def get_split_strategy(category: PageSizeCategory, has_vector_paths: bool) -> str:
    strategies = {
        PageSizeCategory.STANDARD: "none",
        PageSizeCategory.LARGE: "auto",  # Split if dense content
        PageSizeCategory.OVERSIZED: "pdf_vector" if has_vector_paths else "heuristic",
        PageSizeCategory.MASSIVE: "mandatory_tile",  # Always split
    }
    return strategies[category]
```

#### 1.4 Content Density Analysis
Add pre-splitting analysis to determine if splitting is beneficial:

```python
def analyze_content_density(image: Image, page_text: str) -> ContentAnalysis:
    """Analyze page to determine optimal splitting strategy."""
    return ContentAnalysis(
        text_density=len(page_text) / (width * height),
        has_tables=detect_table_structures(image),
        has_drawings=detect_drawing_elements(image),
        whitespace_ratio=calculate_whitespace(image),
        recommended_strategy=determine_strategy(...)
    )
```

---

## 2. Dual Text Extraction (OCR + Layer Text)

### Current State
- Only layer text: `page.get_text("text")` extracts embedded PDF text
- Scanned PDFs or image-based PDFs return empty text
- No fallback mechanism

### Proposed Improvements

#### 2.1 Text Extraction Pipeline

```
PDF Page
    │
    ├─► Layer Text Extraction (fast)
    │   └─► page.get_text("text")
    │
    └─► OCR Extraction (when needed)
        └─► Tesseract / PyMuPDF OCR
            │
            └─► Confidence scoring
```

#### 2.2 OCR Integration Options

**Option A: PyMuPDF Built-in OCR (Recommended)**
- Requires: `pip install pymupdf[ocr]` + Tesseract system install
- Advantage: Integrated, returns positioned text blocks
- Usage: `page.get_text("text", textpage=page.get_textpage_ocr())`

**Option B: Tesseract Direct**
- Requires: `pip install pytesseract` + Tesseract binary
- Advantage: More control over OCR parameters
- Usage: `pytesseract.image_to_string(image, lang='eng')`

**Option C: Cloud OCR (Azure/Google)**
- Requires: API credentials
- Advantage: Best accuracy for complex documents
- Usage: Async API calls with rate limiting

#### 2.3 Text Extraction Strategy

```python
class TextExtractionResult:
    layer_text: str           # From PDF text layer
    ocr_text: str             # From OCR
    merged_text: str          # Combined/deduplicated
    extraction_method: str    # "layer", "ocr", "merged"
    ocr_confidence: float     # 0-1 confidence score
    layer_coverage: float     # % of page with layer text

def extract_text_dual(page, image: Image) -> TextExtractionResult:
    """Extract text using both methods and intelligently merge."""

    # 1. Try layer text first (fast)
    layer_text = sanitize_text(page.get_text("text"))
    layer_coverage = estimate_text_coverage(page)

    # 2. Decide if OCR is needed
    needs_ocr = (
        len(layer_text.strip()) < 50 or      # Very little text
        layer_coverage < 0.3 or               # Low coverage
        is_likely_scanned(page)               # Scanned document indicators
    )

    # 3. Run OCR if needed
    if needs_ocr:
        ocr_text, confidence = run_ocr(image)
    else:
        ocr_text, confidence = "", 0.0

    # 4. Merge intelligently
    merged_text = merge_text_sources(layer_text, ocr_text)

    return TextExtractionResult(
        layer_text=layer_text,
        ocr_text=ocr_text,
        merged_text=merged_text,
        extraction_method=determine_method(layer_text, ocr_text),
        ocr_confidence=confidence,
        layer_coverage=layer_coverage,
    )
```

#### 2.4 Text Merging Strategy

```python
def merge_text_sources(layer: str, ocr: str) -> str:
    """Intelligently merge layer and OCR text."""

    # If one source is empty, use the other
    if not layer.strip():
        return ocr
    if not ocr.strip():
        return layer

    # If similar length, prefer layer (more accurate positioning)
    if abs(len(layer) - len(ocr)) / max(len(layer), len(ocr)) < 0.2:
        return layer

    # If OCR found significantly more text, it's likely a scanned doc
    if len(ocr) > len(layer) * 1.5:
        return ocr

    # Otherwise, concatenate unique content
    return deduplicate_merge(layer, ocr)
```

#### 2.5 Store Both Text Sources

Update schema to store both extraction methods:

```yaml
# In pdf_page.sd
field text_layer type string {
    indexing: summary | index
    index: enable-bm25
}
field text_ocr type string {
    indexing: summary | index
    index: enable-bm25
}
field text type string {
    # Merged/primary text for search
    indexing: summary | index
    index: enable-bm25
}
field text_extraction_method type string {
    indexing: summary | attribute
}
field ocr_confidence type float {
    indexing: summary | attribute
}
```

---

## 3. Enhanced Metadata Schema

### Current State
- Basic fields: title, description, tags, page_number
- No document-level metadata (author, dates, etc.)
- No page dimension information
- No queryable custom fields

### Proposed Improvements

#### 3.1 Document Metadata Fields

```yaml
# Document-level metadata (from PDF properties)
field doc_author type string {
    indexing: summary | index
    match: text
}
field doc_created type long {
    indexing: summary | attribute
}
field doc_modified type long {
    indexing: summary | attribute
}
field doc_producer type string {
    indexing: summary | attribute
}
field doc_subject type string {
    indexing: summary | index
    match: text
}
field doc_keywords type array<string> {
    indexing: summary | index
    index: enable-bm25
}
```

#### 3.2 Page Dimension Fields

```yaml
# Page physical properties
field page_width_px type int {
    indexing: summary | attribute
}
field page_height_px type int {
    indexing: summary | attribute
}
field page_size_category type string {
    # "standard", "large", "oversized", "massive"
    indexing: summary | attribute
}
field page_orientation type string {
    # "portrait", "landscape", "square"
    indexing: summary | attribute
}
field page_dpi type int {
    indexing: summary | attribute
}
```

#### 3.3 Custom Metadata Map

```yaml
# Flexible key-value metadata for user-defined fields
field custom_metadata type map<string, string> {
    indexing: summary | attribute
}
```

#### 3.4 Processing Metadata

```yaml
# Ingestion processing details
field ingested_at type long {
    indexing: summary | attribute
}
field processing_time_ms type int {
    indexing: summary | attribute
}
field embedding_model type string {
    indexing: summary | attribute
}
field split_count type int {
    # Number of regions this page was split into
    indexing: summary | attribute
}
```

#### 3.5 Metadata Extraction

```python
def extract_pdf_metadata(doc: fitz.Document) -> dict:
    """Extract document-level metadata from PDF."""
    metadata = doc.metadata
    return {
        "doc_author": metadata.get("author", ""),
        "doc_subject": metadata.get("subject", ""),
        "doc_keywords": parse_keywords(metadata.get("keywords", "")),
        "doc_producer": metadata.get("producer", ""),
        "doc_created": parse_pdf_date(metadata.get("creationDate")),
        "doc_modified": parse_pdf_date(metadata.get("modDate")),
    }

def extract_page_dimensions(page: fitz.Page, rendered_image: Image) -> dict:
    """Extract page dimension metadata."""
    rect = page.rect
    return {
        "page_width_px": rendered_image.width,
        "page_height_px": rendered_image.height,
        "page_width_pt": rect.width,
        "page_height_pt": rect.height,
        "page_size_category": categorize_page_size(rendered_image),
        "page_orientation": determine_orientation(rect),
    }
```

---

## 4. API Changes for Metadata Queries

### 4.1 Filter by Metadata

Add query parameters to `/api/search`:

```python
@app.route("/api/search")
async def search(request):
    # Existing params
    query = params.get("query")

    # New metadata filters
    filters = {
        "author": params.get("author"),
        "date_from": params.get("date_from"),
        "date_to": params.get("date_to"),
        "size_category": params.get("size_category"),
        "tags": params.get("tags"),
        "custom": params.get("custom_metadata"),
    }

    # Build Vespa YQL with filters
    yql = build_filtered_query(query, filters)
```

### 4.2 Metadata Aggregations

Add endpoint for metadata statistics:

```python
@app.route("/api/metadata/stats")
async def metadata_stats(request):
    """Return aggregated metadata statistics."""
    return {
        "total_documents": count,
        "by_size_category": {"standard": 100, "large": 50, ...},
        "by_author": {"John Doe": 25, ...},
        "date_range": {"min": "2020-01-01", "max": "2024-01-01"},
        "top_tags": [{"tag": "construction", "count": 50}, ...],
    }
```

---

## 5. Configuration Changes

Add to `ki55.toml`:

```toml
[ingestion.text_extraction]
enable_ocr = true
ocr_engine = "pymupdf"  # "pymupdf", "tesseract", "azure", "google"
ocr_languages = ["eng"]
ocr_confidence_threshold = 0.5
layer_text_min_coverage = 0.3
always_run_ocr = false  # Run OCR even if layer text exists

[ingestion.page_sizing]
standard_max_pixels = 1_000_000
large_max_pixels = 3_000_000
oversized_max_pixels = 10_000_000
adaptive_dpi = true
standard_dpi = 150
large_dpi = 120
oversized_dpi = 100
massive_dpi = 72

[ingestion.metadata]
extract_pdf_metadata = true
extract_page_dimensions = true
store_processing_metadata = true
```

---

## 6. Implementation Priority

### Phase 1: Page Size Detection (Low effort, High impact)
1. Add `PageSizeCategory` enum and classification
2. Implement adaptive DPI
3. Add page dimension fields to schema
4. Update ingestion to populate dimension metadata

### Phase 2: Enhanced Metadata (Medium effort, Medium impact)
1. Add PDF metadata extraction
2. Add custom_metadata map field
3. Implement metadata filter queries
4. Add metadata aggregation endpoint

### Phase 3: OCR Integration (Higher effort, High impact)
1. Add OCR dependencies (optional)
2. Implement dual text extraction
3. Add text_layer/text_ocr fields
4. Implement intelligent merging
5. Update search to use merged text

---

## 7. Migration Strategy

For existing documents:
1. New fields added with default values
2. Re-ingestion script for full metadata extraction
3. Incremental OCR processing for documents with empty text

```python
async def migrate_existing_documents():
    """Add metadata to existing documents."""
    # Query all documents missing new fields
    docs = await vespa.query("select * from pdf_page where page_width_px = 0")

    for doc in docs:
        # Re-extract metadata from stored images
        # Update document with new fields
        await vespa.update(doc.id, new_fields)
```
