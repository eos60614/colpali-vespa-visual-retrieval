# Feature Specification: File Upload and Ingestion with Metadata

**Feature Branch**: `002-file-upload-ingest`
**Created**: 2026-01-14
**Status**: Draft
**Input**: User description: "allow user to upload file on the frontend and ingest. allow user to include meta data"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload PDF Document (Priority: P1)

A user wants to add their own PDF document to the visual retrieval system so they can search through it alongside existing documents. The user navigates to an upload area, selects a PDF file from their computer, and submits it for processing. The system ingests the document and makes it searchable.

**Why this priority**: This is the core functionality - without file upload, no other features work. Users need a way to add their own documents to make the system useful for their specific use cases.

**Independent Test**: Can be fully tested by uploading a single PDF and verifying it appears in search results. Delivers immediate value by allowing users to search their own documents.

**Acceptance Scenarios**:

1. **Given** a user is on the upload page, **When** they select a valid PDF file and click upload, **Then** the file is accepted and processing begins.
2. **Given** a PDF has been ingested, **When** the user searches for content from that PDF, **Then** relevant pages appear in search results.

---

### User Story 2 - Add Custom Metadata (Priority: P2)

A user wants to attach descriptive metadata to their uploaded document to improve organization and searchability. When uploading a file, the user can provide a custom title, description, and tags that will be associated with the document.

**Why this priority**: Metadata enhances search quality and document organization, but the system can function with auto-generated metadata from filenames.

**Independent Test**: Can be tested by uploading a document with custom metadata and verifying the metadata appears in search results.

**Acceptance Scenarios**:

1. **Given** a user is uploading a PDF, **When** they enter a custom title in the metadata form, **Then** that title is used instead of the filename in search results.
2. **Given** a user provides tags for their document, **When** they search using those tags, **Then** the document ranks higher in results.
3. **Given** a user leaves metadata fields empty, **When** the document is ingested, **Then** reasonable defaults are applied (filename as title).

---

### Edge Cases

- What happens when a user uploads a corrupted or password-protected PDF?
  - System displays an error message and does not process the file.
- What happens when a user uploads a file that exceeds 250MB?
  - System rejects the upload with a message indicating the size limit.
- What happens with PDFs containing only images (no extractable text)?
  - System processes normally using visual embeddings; document is still searchable via visual similarity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a file upload interface accessible from the frontend.
- **FR-002**: System MUST accept PDF files up to 250MB for upload and ingestion.
- **FR-003**: System MUST validate uploaded files before processing (file type, size).
- **FR-004**: System MUST allow users to specify optional metadata fields: title, description, and tags.
- **FR-005**: System MUST process uploaded PDFs through the existing ingestion pipeline (page rendering, embedding generation, indexing).
- **FR-006**: System MUST apply default metadata values when user does not provide them (filename as title).
- **FR-007**: System MUST make user-provided tags searchable.

### Key Entities

- **Uploaded Document**: Represents a file submitted by a user; contains the file binary and associated metadata.
- **Document Metadata**: User-provided information including title, description, and tags; linked to one uploaded document.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can upload a PDF and have it become searchable.
- **SC-002**: Users can find their uploaded documents using content-based queries after ingestion.
- **SC-003**: Custom metadata (title, tags) appears in search results and affects ranking.

## Assumptions

- Maximum file size limit is 250MB.
- The existing ingestion pipeline can be triggered on-demand for single documents.
- Tags will be stored as an array field similar to existing fields in the document schema.
