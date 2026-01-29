# Tasks: Add ColQwen3 Model Support

> **Note**: These tasks were written for an earlier architecture. The application now uses Starlette (JSON API) + Next.js (frontend). All tasks are completed.

**Input**: Design documents from `/specs/001-colqwen3-model/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/api.md ✓, quickstart.md ✓

**Tests**: Not requested - no test tasks included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and model configuration structure

- [X] T001 Create ModelConfig dataclass and model registry in backend/models/config.py
- [X] T002 [P] Add flash-attn to requirements.txt as optional dependency with comment

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core model abstraction infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Add model loading methods to SimMapGenerator for ColQwen3 in backend/colpali.py
- [X] T004 Implement model unloading with GPU memory cleanup in backend/colpali.py
- [X] T005 Implement switch_model method in SimMapGenerator in backend/colpali.py
- [X] T006 Abstract embedding generation to support both ColPali and ColQwen3 in backend/colpali.py
- [X] T007 Add model state tracking (current_model_id, is_loading, last_error) to SimMapGenerator in backend/colpali.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Select ColQwen3 Model for Search (Priority: P1) 🎯 MVP

**Goal**: Users can select between ColPali and ColQwen3 models in the search UI and perform searches with the selected model

**Independent Test**: Select ColQwen3 from model dropdown, enter a search query, verify results are returned using ColQwen3 embeddings

### Implementation for User Story 1

- [X] T008 [P] [US1] Add model parameter to /search endpoint in main.py
- [X] T009 [P] [US1] Add model parameter to /fetch_results endpoint in main.py
- [X] T010 [US1] Update vespa_app.py query flow to pass model parameter through search pipeline in backend/vespa_app.py
- [X] T011 [US1] Trigger model swap before query processing when different model requested in main.py
- [X] T012 [US1] Add RadioGroup for model selection (colpali, colqwen3) to SearchBox component in frontend/app.py
- [X] T013 [US1] Update SearchBox form to submit model parameter in frontend/app.py
- [X] T014 [US1] Display current model indicator in search interface in frontend/app.py
- [X] T015 [US1] Add logging for model selection and model-related operations in backend/colpali.py
- [X] T016 [US1] Handle model load errors with user-facing error message display in main.py

**Checkpoint**: User Story 1 complete - users can select and search with ColQwen3

---

## Phase 4: User Story 2 - Persist Model Selection (Priority: P2)

**Goal**: User's model selection persists within their browser session across multiple searches

**Independent Test**: Select ColQwen3, perform search, perform another search, verify model selection is still ColQwen3

### Implementation for User Story 2

- [X] T017 [US2] Preserve model selection in form state after search submission in frontend/app.py
- [X] T018 [US2] Pass model value through request/response cycle (now via JSON API)
- [X] T019 [US2] Set default model selection to colpali on page load/refresh in frontend/app.py

**Checkpoint**: User Story 2 complete - model selection persists during session

---

## Phase 5: User Story 3 - View Model Information (Priority: P3)

**Goal**: Users can view descriptions of each model to understand their differences

**Independent Test**: Hover over or click model info icon, verify explanatory text is displayed

### Implementation for User Story 3

- [X] T020 [US3] Add model descriptions to UI (tooltip or info icon) in frontend/app.py
- [X] T021 [P] [US3] Add GET /model_status endpoint returning available models with descriptions in main.py
- [X] T022 [P] [US3] Add GET /switch_model endpoint for explicit model switching in main.py

**Checkpoint**: User Story 3 complete - all user stories functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and improvements

- [X] T023 Validate all ranking methods (colpali, bm25, hybrid) work with ColQwen3 model selection
- [X] T024 Verify backward compatibility - requests without model parameter default to colpali
- [X] T025 Test model swap performance (target: < 30 seconds)
- [X] T026 Run quickstart.md validation scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational phase - MVP
- **User Story 2 (Phase 4)**: Depends on User Story 1 completion (extends its functionality)
- **User Story 3 (Phase 5)**: Can start after Foundational (independent of US1/US2)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on User Story 1 (extends form state handling)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent of US1/US2

### Within Each User Story

- Backend changes (main.py, backend/) before frontend changes (frontend/)
- Core implementation before integration
- Validation and error handling last

### Parallel Opportunities

- T001 and T002 can run in parallel (Setup phase)
- T008 and T009 can run in parallel (both add model param to different endpoints)
- T021 and T022 can run in parallel (independent new endpoints)
- User Story 3 (Phase 5) can run in parallel with User Story 2 (Phase 4) if desired

---

## Parallel Example: User Story 1

```bash
# Launch endpoint modifications together:
Task: "Add model parameter to /search endpoint in main.py"
Task: "Add model parameter to /fetch_results endpoint in main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T007) - CRITICAL
3. Complete Phase 3: User Story 1 (T008-T016)
4. **STOP and VALIDATE**: Test model selection and search with ColQwen3
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test → Deploy/Demo (MVP!)
3. Add User Story 2 → Test → Deploy/Demo (session persistence)
4. Add User Story 3 → Test → Deploy/Demo (model info)
5. Each story adds value without breaking previous stories

### File Change Summary

| File | Changes |
|------|---------|
| backend/models/config.py | NEW - ModelConfig dataclass, model registry |
| backend/colpali.py | MODIFY - Add ColQwen3 loading, model swap, abstracted embeddings |
| backend/vespa_app.py | MODIFY - Pass model through query flow |
| frontend/app.py | MODIFY - Add model RadioGroup, form state, tooltips |
| main.py | MODIFY - Add model param to endpoints, new endpoints, model state |
| requirements.txt | MODIFY - Add flash-attn optional dependency |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
