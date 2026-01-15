# ColPali Submittal Review System Analysis

## Current System Overview

This is a **Visual RAG (Retrieval-Augmented Generation)** system built on:
- **ColPali** (vidore/colpali-v1.2) - Vision-language model for document embeddings
- **Vespa** - Vector search with HNSW indexing + BM25 text search
- **FastHTML** - Full-stack Python web framework
- **Gemini API** - LLM for generating AI responses

---

## Strengths

### 1. **Powerful Visual Understanding**
- ColPali captures visual layout, diagrams, tables, and drawings - critical for construction documents
- Works on images directly without relying solely on OCR (handles poor-quality scans, handwriting, CAD drawings)
- MaxSim algorithm matches query tokens to document patches for fine-grained relevance

### 2. **Production-Ready Architecture**
- Binary quantized embeddings (int8) for efficient storage and fast Hamming distance search
- HNSW index enables fast approximate nearest neighbor search at scale
- Hybrid ranking (visual + text) provides flexibility
- Similarity map visualization shows which parts of a document matched the query

### 3. **Robust Ingestion Pipeline**
- Parallel PDF processing (multiprocessing for rendering, threading for indexing)
- Batch embedding generation for GPU efficiency
- Handles large document collections (6,992+ pages demonstrated)

### 4. **Good Developer Experience**
- Local Docker-based Vespa setup for development
- Clear separation of concerns (backend, frontend, scripts)
- Environment-based configuration (local, cloud, mTLS)

---

## Areas Needing Addressing

### 1. **No Document Type Differentiation**
**Current:** All PDFs are treated uniformly as `pdf_page` documents
**Needed:**
- Distinguish between submittals, specifications, and drawings
- Schema fields for document category/type
- Separate indices or filtering by document type

### 2. **No Structured Metadata Extraction**
**Current:** Only generic text extraction via PyMuPDF OCR
**Needed:**
- Parse submittal cover sheets (manufacturer, model, product type)
- Extract spec section references (e.g., "Section 09 21 16 - Gypsum Board")
- Identify material specifications, performance criteria, compliance standards
- Link submittals to relevant spec sections

### 3. **No Compatibility/Compliance Logic**
**Current:** Only similarity-based matching (finds visually/textually similar documents)
**Needed:**
- Rule-based validation (does submittal meet spec requirements?)
- Structured comparison (spec says "Type X", submittal shows "Type X" → pass)
- Multi-attribute matching (material, dimensions, fire rating, etc.)
- Compliance scoring with pass/fail/review status

### 4. **No Automated Ingestion Workflow**
**Current:** Manual `python scripts/feed_data.py` command
**Needed:**
- Watch folder or API endpoint for auto-ingestion
- Document classification on upload (is this a submittal, spec, or drawing?)
- Linking mechanism (which spec sections does this submittal relate to?)

### 5. **No Construction Domain Knowledge**
**Current:** Sample data is financial reports (Norwegian Pension Fund)
**Needed:**
- Training/fine-tuning on construction documents
- Understanding of CSI MasterFormat, spec structure, submittal conventions
- Domain-specific query understanding

### 6. **No Review Workflow**
**Current:** Just retrieval and display
**Needed:**
- Status tracking (pending, approved, rejected, revise & resubmit)
- Annotation/comments on specific areas
- Comparison view (submittal vs. spec side-by-side)
- Audit trail of decisions

---

## Recommended Approach for Submittal Compatibility System

### Phase 1: Document Classification & Metadata
1. Add document type schema field (submittal, specification, drawing)
2. Build metadata extractor for spec sections and submittal cover sheets
3. Create linking mechanism between submittals and specs

### Phase 2: Compatibility Checking
1. Define structured comparison criteria per spec type
2. Implement rule engine for pass/fail checks
3. Use ColPali similarity as one signal among many (not sole decision maker)
4. Generate compliance report with specific mismatches highlighted

### Phase 3: Workflow & UI
1. Add submittal status tracking
2. Build comparison view (submittal vs. spec)
3. Enable annotations on problem areas
4. Create auto-ingestion via API or watch folder

---

## User Requirements (Clarified)

- **Submittal Type**: Product data sheets (manufacturer cut sheets, technical specs)
- **Automation Level**: Auto pass/fail for clear cases, human review for edge cases
- **Integration**: Procore integration planned but out of scope for this feature

---

## Summary: What ColPali Does Well vs. What Needs Building

### ColPali Strengths (Leverage These)
| Capability | How It Helps |
|------------|--------------|
| Visual document understanding | Can "see" product images, diagrams, tables in submittals |
| Patch-level matching | Can locate specific areas where spec requirements appear |
| Hybrid text+visual search | Combines OCR text with visual layout understanding |
| Similarity scoring | Provides relevance confidence for matches |

### Gaps to Address (Build These)
| Gap | What's Needed |
|-----|---------------|
| Document classification | Distinguish submittals from specs on upload |
| Structured extraction | Parse spec requirements and submittal attributes |
| Compliance rules | Business logic for pass/fail decisions |
| Auto-ingestion | API/watch folder for incoming documents |
| Review workflow | Status tracking, approval routing |

### Critical Insight
ColPali excels at **finding relevant documents** but doesn't inherently **validate compliance**. The system can answer "which spec pages are relevant to this submittal?" but not "does this submittal meet the spec requirements?"

For auto pass/fail, you need:
1. **Structured spec requirements** (e.g., "material must be Type X, fire rating must be 2-hour")
2. **Structured submittal attributes** (extracted or parsed from the product data)
3. **Comparison logic** (does attribute match requirement?)

ColPali can assist with #1 and #2 (finding where these values appear), but the actual comparison needs explicit logic or an LLM evaluation layer.

---

## Refined Architecture (Jan 14 Discussion)

### Assumptions (Simplified Scope)
- Project association is already known (docs tagged with project ID)
- Document type is already known (we know which is spec, which is submittal)
- **1 spec section → 1 product type** (e.g., RTU spec compared to RTU submittal)

### The "Many-to-Many" Problem (Within Document Pair)

```
RTU Spec Section (many requirements)     RTU Submittal (many attributes)
────────────────────────────────────     ──────────────────────────────
• Cooling capacity ≥ 10 tons      ←→     • Cooling: 12 tons ✓
• SEER ≥ 14                       ←→     • SEER: 15.2 ✓
• Voltage: 208/230V               ←→     • Electrical: 208/230V ✓
• Refrigerant: R-410A             ←→     • Refrigerant: R-410A ✓
• Sound ≤ 72 dB                   ←→     • Sound: 68 dB ✓
• [Requirement N...]              ←→     • [Attribute N...]
```

Challenge: Spec has N requirements, submittal has M attributes. Need to match and compare each relevant pair.

---

## Most Accurate Approach: Hybrid Pipeline

ColPali's strength with PDFs:
- Visual understanding of layouts (tables, diagrams, spec sheets)
- Doesn't rely solely on OCR which can miss formatted data
- Can locate specific regions where information appears

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: Requirement Extraction (Spec)                          │
│  ─────────────────────────────────────                          │
│  Vision LLM + ColPali similarity maps                           │
│  • Send spec pages as images to vision LLM                      │
│  • Extract structured requirements with page/location refs      │
│  • ColPali provides patch-level grounding                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: Per-Requirement Retrieval (ColPali)                    │
│  ───────────────────────────────────────────                    │
│  For each requirement:                                          │
│  • Query: "cooling capacity 10 tons minimum"                    │
│  • ColPali finds submittal pages/patches with relevant content  │
│  • Returns: top-k submittal regions + similarity scores         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: Visual Verification (Vision LLM)                       │
│  ─────────────────────────────────────────                      │
│  For each requirement + retrieved submittal region:             │
│  • Send both images to vision LLM                               │
│  • Prompt: "Does this submittal section satisfy this req?"      │
│  • Extract: value found, comparison result, confidence          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: Aggregation + Human Review Routing                     │
│  ──────────────────────────────────────────                     │
│  • Aggregate all requirement checks                             │
│  • Flag low-confidence or failed checks for human review        │
│  • Generate compliance report with visual evidence              │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Is More Accurate

| Step | Why It Helps Accuracy |
|------|----------------------|
| Vision LLM on spec images | Sees tables/formatting, not just OCR text |
| ColPali retrieval per requirement | Narrows search to relevant submittal regions (not full doc) |
| Visual verification with both images | LLM compares apples-to-apples with visual context |
| Patch-level grounding | Can show exactly WHERE in the doc the match was found |

### Key Insight

**Don't extract text → compare text.** Instead: **extract requirements → visually locate in submittal → visually verify match.**

This keeps the PDF visual fidelity throughout the pipeline.

---

## Design Philosophy: Human-Assisted, Not Human-Replaced

```
┌─────────────────────────────────────────────────────────────┐
│  CORE PRINCIPLE                                             │
│  ─────────────────                                          │
│  • System does the grunt work (finding, extracting)         │
│  • Human makes the judgment calls                           │
│  • Human always understands what happened and why           │
└─────────────────────────────────────────────────────────────┘
```

### Key Constraints

| Constraint | Implication |
|------------|-------------|
| **1 submittal ↔ 1 spec section** | No cross-section matching. System suggests section, human confirms. |
| **System suggests, human verifies** | Spec section picker with override, not auto-assignment |
| **Feedback loop required** | Human corrections improve future extractions |
| **Transparency over automation** | Human must understand the reasoning, not just see pass/fail |

### What This Means for UX

```
OLD: Submittal → [BLACK BOX] → Pass/Fail
NEW: Submittal → [System finds evidence] → Human sees evidence → Human decides
```

The system's job is to **accelerate human review**, not replace it.

---

## 3-Lane Requirement Triage

At Step 1 (Requirement Extraction), every requirement gets classified into one of three lanes:

### Lane 1: Auto-Checkable (Green)
Typed, unambiguous, directly comparable requirements.

**Examples:**
- Voltage/phase/frequency
- Listing requirements (UL, ETL, etc.)
- Leakage class
- Material/coating specifications
- Maximum sound levels
- Minimum efficiency ratings

**Action:** System extracts, retrieves from submittal, shows comparison to human.

### Lane 2: Needs Scoping (Yellow)
Requirements that reference drawings, schedules, or external documents.

**Trigger phrases:**
- "as scheduled"
- "as indicated"
- "per plans"
- "where shown"
- "match drawings"
- "coordinate with"

**Action:** Creates a requirement stub with `status = NEEDS_SCOPING`. Human must provide the target value or mark as N/A. No auto-checking until scoped.

### Lane 3: Informational (Gray)
Narrative, workmanship, means & methods, "provide as required."

**Examples:**
- Installation instructions
- Workmanship standards
- Coordination requirements
- "As required by code"

**Action:** Stored for reference, displayed to human, but not checked.

### Why Triage Matters

This is the **single biggest lever for accuracy**. If an ambiguous requirement gets auto-checked, you get false passes. The triage ensures:
- Only clear requirements get automated checks
- Ambiguous requirements get human input first
- Informational content doesn't clutter the review

---

## Feedback Loop Design

Human corrections flow back to improve the system over time.

### Correction Types

```
┌──────────────────────────────────────────────────────────────┐
│  WHAT HUMANS CAN CORRECT                                     │
├──────────────────────────────────────────────────────────────┤
│  1. Spec section override    → Improves section matching     │
│  2. Requirement edit         → Improves extraction prompts   │
│  3. Value correction         → Improves LLM extraction       │
│  4. Pass/Fail override       → Improves comparison logic     │
│  5. "Not applicable" flag    → Improves requirement filtering│
│  6. Lane reclassification    → Improves triage accuracy      │
└──────────────────────────────────────────────────────────────┘
```

### Feedback Flow

```
Human makes correction
        ↓
Correction stored with full context:
  - Original system output
  - Human correction
  - Document refs (spec page, submittal page)
  - Timestamp, user ID
        ↓
Periodic analysis of corrections:
  - Common extraction errors → prompt tuning
  - Common triage errors → classifier updates
  - Common section mismatches → embedding improvements
        ↓
System accuracy improves over time
```

### Design Principle

Every correction should be **low-friction** for the human:
- Single click to override pass/fail
- Inline editing for value corrections
- Dropdown for lane reclassification

The system should make it **easier to correct than to ignore**.

---

## MVP Pipeline (Revised)

### Step 0: Spec Section Matching
- System suggests which spec section applies to the submittal
- Human verifies or overrides
- **Only proceeds with confirmed spec section**

### Step 1: Requirement Extraction
- Extract requirements from the **single confirmed spec section**
- Classify each into Green/Yellow/Gray lane
- Output structured JSON with source refs

### Step 2: Per-Requirement Retrieval (Green Lane Only)
- For each AUTO_CHECK requirement:
  - Query ColPali against the submittal
  - Return top-k regions with similarity scores
  - Show human where evidence was found

### Step 3: Visual Verification
- For each requirement + candidate region:
  - Vision LLM extracts value from submittal
  - Compares against requirement
  - Returns: value found, comparison result, confidence, evidence refs

### Step 4: Human Review
- Present all findings to human with full evidence
- Human can:
  - Confirm system findings
  - Override any result
  - Scope yellow-lane requirements
  - Mark items as N/A
- All actions logged for feedback loop

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Yellow lane overload (too many NEEDS_SCOPING) | Add "suggested scoping hints" without auto-checking |
| Vendor cutsheet variability | Top-k retrieval + multi-region display to human |
| Spec language diversity | Typed taxonomy + continuous tuning from feedback |
| LLM hallucination on values | Always show source evidence; human verifies |
| Confidence threshold tuning | Start conservative; use feedback data to calibrate |

---

## Open Questions

1. **Scoper workflow:** When a requirement is NEEDS_SCOPING, what's the minimal action? Options:
   - Pick a drawing sheet
   - Pick a schedule row
   - Enter target value manually (recommended for MVP)
   - Mark as N/A

2. **Feedback cadence:** How often should corrections be analyzed and incorporated?
   - Real-time learning (complex)
   - Weekly batch analysis (simpler, recommended for MVP)

3. **Multi-model submittals:** When a cutsheet has multiple product models, how to handle?
   - Human selects which model applies
   - System attempts to match model number from spec
