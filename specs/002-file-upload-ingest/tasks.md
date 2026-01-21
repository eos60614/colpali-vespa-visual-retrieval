# Tasks: File Upload and Ingestion with Metadata

**Input**: Design documents from `/specs/002-file-upload-ingest/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not requested - manual testing only (per spec).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md, this is a web application with:
- Backend: `backend/`, `main.py`
- Frontend: `frontend/`
- Vespa schema: `vespa-app/schemas/`

---

## Phase 1: Setup

**Purpose**: Vespa schema updates required for metadata support

- [X] T001 Add `description` field to Vespa schema in vespa-app/schemas/pdf_page.sd
- [X] T002 Add `tags` array field with BM25 indexing to Vespa schema in vespa-app/schemas/pdf_page.sd
- [X] T003 Redeploy Vespa application to apply schema changes

---

## Phase 2: Foundational (Backend Ingestion Module)

**Purpose**: Create reusable ingestion service that both user stories depend on

**⚠️ CRITICAL**: User story implementation cannot begin until this phase is complete

- [X] T004 Create backend/ingest.py with PDF validation function (validate_pdf)
- [X] T005 Add image_to_base64 and create_blur_image functions to backend/ingest.py (extract from scripts/feed_data.py)
- [X] T006 Add float_to_binary_embedding function to backend/ingest.py (extract from scripts/feed_data.py)
- [X] T007 Add pdf_to_images function to backend/ingest.py (extract from scripts/feed_data.py)
- [X] T008 Add generate_embeddings function to backend/ingest.py (extract from scripts/feed_data.py)
- [X] T009 Add feed_document function to backend/ingest.py (extract from scripts/feed_data.py)
- [X] T010 Create ingest_pdf() main function in backend/ingest.py that orchestrates the full pipeline
- [X] T011 Add generate_doc_id() function for content-hash-based IDs in backend/ingest.py

**Checkpoint**: Backend ingestion module ready for use by upload endpoints

---

## Phase 3: User Story 1 - Upload PDF Document (Priority: P1) 🎯 MVP

**Goal**: Users can upload a PDF file and have it become searchable through visual retrieval

**Independent Test**: Upload a PDF, wait for processing, search for content from the PDF, verify pages appear in results

### Implementation for User Story 1

- [X] T012 [P] [US1] Create UploadForm() component in frontend/app.py with file input and submit button
- [X] T013 [P] [US1] Create UploadPage() component in frontend/app.py wrapping UploadForm with Layout
- [X] T014 [P] [US1] Create UploadSuccess() component in frontend/app.py for success message display
- [X] T015 [P] [US1] Create UploadError() component in frontend/app.py for error message display
- [X] T016 [US1] Add GET /upload route in main.py to render upload page
- [X] T017 [US1] Add POST /upload route in main.py to handle file upload with validation
- [X] T018 [US1] Implement file size validation (250MB max) in POST /upload handler in main.py
- [X] T019 [US1] Implement PDF validation (type check, corruption, encryption) in POST /upload handler in main.py
- [X] T020 [US1] Call ingest_pdf() from POST /upload handler to process uploaded file in main.py
- [X] T021 [US1] Return success/error response HTML from POST /upload handler in main.py
- [X] T022 [US1] Add "Upload" navigation link to frontend/layout.py header

**Checkpoint**: User Story 1 complete - users can upload PDFs and search them

---

## Phase 4: User Story 2 - Add Custom Metadata (Priority: P2)

**Goal**: Users can provide custom title, description, and tags when uploading documents

**Independent Test**: Upload a PDF with custom title and tags, verify title appears in search results, search by tag and verify document ranks higher

### Implementation for User Story 2

- [X] T023 [P] [US2] Add title input field to UploadForm() component in frontend/app.py
- [X] T024 [P] [US2] Add description textarea field to UploadForm() component in frontend/app.py
- [X] T025 [P] [US2] Add tags input field to UploadForm() component in frontend/app.py
- [X] T026 [US2] Update POST /upload route to accept title, description, tags parameters in main.py
- [X] T027 [US2] Add metadata validation (title length, description length, tag count/length) in main.py
- [X] T028 [US2] Update ingest_pdf() to accept and apply metadata parameters in backend/ingest.py
- [X] T029 [US2] Apply default title (filename) when not provided in backend/ingest.py
- [X] T030 [US2] Include description and tags fields in Vespa document feed in backend/ingest.py
- [X] T031 [US2] Update hybrid rank profile to include tags in BM25 scoring in vespa-app/schemas/pdf_page.sd

**Checkpoint**: User Story 2 complete - users can add metadata that improves search

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T032 Validate complete flow per quickstart.md (upload PDF, add metadata, search)
- [X] T033 Add error logging for upload failures in main.py
- [X] T034 Add HTMX attributes to UploadForm for seamless submit without page reload in frontend/app.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion
- **User Story 2 (Phase 4)**: Depends on Foundational phase completion (can run parallel to US1)
- **Polish (Phase 5)**: Depends on User Stories 1 and 2 being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 - No dependencies on US2
- **User Story 2 (P2)**: Can start after Phase 2 - Extends US1 components but independently testable

### Within Each User Story

- Frontend components (marked [P]) can run in parallel
- Routes depend on components being available
- Integration tasks depend on route implementation

### Parallel Opportunities

- T001 and T002 can run in parallel (different fields in same file)
- T012, T013, T014, T015 can run in parallel (different functions)
- T023, T024, T025 can run in parallel (different form fields)
- US1 and US2 can run in parallel after Phase 2 completion

---

## Parallel Example: User Story 1

```bash
# Launch all frontend components in parallel:
Task: "Create UploadForm() component in frontend/app.py"
Task: "Create UploadPage() component in frontend/app.py"
Task: "Create UploadSuccess() component in frontend/app.py"
Task: "Create UploadError() component in frontend/app.py"

# Then implement routes sequentially:
Task: "Add GET /upload route in main.py"
Task: "Add POST /upload route in main.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch all form field additions in parallel:
Task: "Add title input field to UploadForm() in frontend/app.py"
Task: "Add description textarea field to UploadForm() in frontend/app.py"
Task: "Add tags input field to UploadForm() in frontend/app.py"

# Then implement backend logic sequentially:
Task: "Update POST /upload route to accept metadata parameters"
Task: "Update ingest_pdf() to apply metadata"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (Vespa schema)
2. Complete Phase 2: Foundational (backend/ingest.py)
3. Complete Phase 3: User Story 1 (basic upload)
4. **STOP and VALIDATE**: Upload a PDF, search for its content
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Backend ready
2. Add User Story 1 → Basic upload works → MVP!
3. Add User Story 2 → Metadata support → Enhanced search
4. Polish → Production-ready

---

## Notes

- [P] tasks = different files/functions, no dependencies
- [Story] label maps task to specific user story
- No automated tests - manual testing per spec
- Vespa redeployment required after schema changes (T003)
- Existing functions in scripts/feed_data.py should be extracted, not duplicated
- HTMX handles form submission without page reload
