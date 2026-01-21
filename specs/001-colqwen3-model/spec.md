# Feature Specification: Add ColQwen3 Model Support

**Feature Branch**: `001-colqwen3-model`
**Created**: 2026-01-14
**Status**: Draft
**Input**: User description: "I want to add a model. https://huggingface.co/TomoroAI/tomoro-colqwen3-embed-4b as an option for search and hybrid search"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Select ColQwen3 Model for Search (Priority: P1)

A user wants to use the newer ColQwen3 model for document search because it offers better multilingual support and improved performance on complex document layouts like charts and tables.

**Why this priority**: This is the core functionality requested. Without the ability to select the model, the feature has no value. ColQwen3 offers significant advantages including 13x smaller storage footprint and state-of-the-art multilingual document retrieval.

**Independent Test**: Can be fully tested by selecting ColQwen3 from the model dropdown, entering a search query, and verifying that search results are returned using the ColQwen3 model embeddings.

**Acceptance Scenarios**:

1. **Given** a user is on the search page, **When** they view the model selection options, **Then** they see both "ColPali" and "ColQwen3" as available model choices.
2. **Given** a user has selected "ColQwen3" as the model, **When** they enter a search query and submit, **Then** the system uses ColQwen3 embeddings to retrieve and rank results.
3. **Given** a user has selected "ColQwen3" and a ranking method (ColPali-style, BM25, or Hybrid), **When** they search, **Then** results are ranked according to the selected ranking profile using ColQwen3 embeddings where applicable.

---

### User Story 2 - Persist Model Selection (Priority: P2)

A user wants their model selection to be remembered during their session so they don't have to reselect it for each search.

**Why this priority**: Improves user experience but the core search functionality works without it. Users can still manually select each time.

**Independent Test**: Can be tested by selecting ColQwen3, performing a search, then performing another search and verifying the model selection is still ColQwen3.

**Acceptance Scenarios**:

1. **Given** a user has selected "ColQwen3" as their model, **When** they perform multiple searches in the same session, **Then** the ColQwen3 selection persists across searches.
2. **Given** a user refreshes the page, **When** the page reloads, **Then** the default model selection (ColPali) is shown.

---

### User Story 3 - View Model Information (Priority: P3)

A user wants to understand the differences between available models so they can make an informed choice about which model to use for their search needs.

**Why this priority**: Nice-to-have feature that helps users make informed decisions, but not required for core functionality.

**Independent Test**: Can be tested by hovering over or clicking a model info icon and verifying explanatory text is displayed.

**Acceptance Scenarios**:

1. **Given** a user is viewing the model selection options, **When** they hover over or click an info indicator, **Then** they see a brief description of each model's strengths (e.g., "ColQwen3: Better multilingual support, improved chart/table understanding, 13x smaller storage").

---

### Edge Cases

- What happens when the ColQwen3 model fails to load? The system should display an error message to the user (no automatic fallback required - this is for evaluation purposes).
- How does the system handle queries when switching models mid-session? The system should swap models on GPU as needed, unloading the previous model to free memory before loading the new one.
- What happens if document embeddings were indexed with ColPali but user searches with ColQwen3? The system should use appropriate cross-model compatibility handling or clearly indicate which model was used for indexing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a user interface element to select between ColPali and ColQwen3 models for search.
- **FR-002**: System MUST load the selected model's processor and weights when initializing search functionality.
- **FR-003**: System MUST generate query embeddings using the selected model when processing search requests.
- **FR-004**: System MUST support ColQwen3 with all existing ranking methods: vision-based (ColPali-style), BM25, and Hybrid.
- **FR-005**: System MUST display which model is currently selected in the search interface.
- **FR-006**: System MUST handle ColQwen3's 320-dimensional embeddings appropriately in the ranking pipeline.
- **FR-007**: System MUST support ColQwen3's maximum of 1,280 visual tokens per document page.
- **FR-008**: System MUST default to ColPali model for backward compatibility with existing indexed documents.
- **FR-009**: System MUST swap models on GPU when user changes selection, unloading the current model before loading the new one to manage memory constraints.
- **FR-010**: System MUST display a clear error message to the user if a model fails to load (no automatic fallback required).
- **FR-011**: System MUST log model selection and any model-related errors for debugging purposes.

### Key Entities

- **Model Configuration**: Represents a selectable embedding model with its name, identifier, embedding dimensions, and processing parameters.
- **Query Embedding**: The multi-vector representation of a user's search query, generated by the selected model.
- **Model Selection State**: The user's current model choice, maintained during the search session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can select between at least two embedding models (ColPali and ColQwen3) from the search interface within 2 clicks.
- **SC-002**: Search queries using ColQwen3 return results within the same time tolerance as ColPali searches (no more than 20% slower).
- **SC-003**: 100% of ranking methods (vision-based, BM25, hybrid) work correctly with ColQwen3 model selection.
- **SC-004**: Model selection persists across multiple searches within the same user session with 100% reliability.
- **SC-005**: Model swap completes within 30 seconds when user changes model selection.
- **SC-006**: Users can identify which model is currently active with a single glance at the interface.
- **SC-007**: Users receive a clear error message if model loading fails.

## Assumptions

- This feature is for evaluation purposes only; production-grade reliability features (automatic fallback, high availability) are not required.
- The ColQwen3 model (TomoroAI/tomoro-colqwen3-embed-4b) is publicly available and can be downloaded from HuggingFace.
- The server has a single GPU; only one model is loaded at a time with swapping as needed.
- Users have existing documents indexed with ColPali embeddings; initial implementation will focus on query-side model selection.
- FlashAttention 2 is available on the deployment environment for optimal ColQwen3 performance.
- The existing Vespa schema can accommodate ColQwen3's 320-dimensional embeddings or will be extended as needed.

## Out of Scope

- Re-indexing existing documents with ColQwen3 embeddings (separate feature).
- Video search functionality supported by ColQwen3 (future enhancement).
- Automatic model recommendation based on query or document characteristics.
- Support for other embedding models beyond ColPali and ColQwen3.
- Performance optimization for running multiple models simultaneously.
