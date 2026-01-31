# Quickstart: Codebase Reorganization

## Summary

Reorganize the backend into three clear domains:
1. **Ingestion** - Document processing, embedding generation
2. **Query** - Search, ranking, similarity maps, agent
3. **Connectors** - Vespa, LLM, S3, PostgreSQL clients

Plus a **Core** shared infrastructure layer.

## Current vs Proposed

```
# Current (flat)                    # Proposed (domain-based)
backend/                            backend/
├── config.py                       ├── core/
├── colpali.py     ←── SPLIT ──→   │   ├── config.py
├── vespa_app.py   ←── SPLIT ──→   │   ├── logging_config.py
├── ingest.py                       │   └── models/
├── rerank.py                       ├── ingestion/
├── agent.py                        │   ├── pdf/
├── llm_config.py                   │   ├── embeddings/
├── s3.py                           │   ├── regions/
└── ingestion/                      │   └── database/
                                    ├── query/
                                    │   ├── search/
                                    │   ├── ranking/
                                    │   ├── similarity/
                                    │   └── agent/
                                    └── connectors/
                                        ├── vespa/
                                        ├── llm/
                                        └── storage/
```

## Key Decisions

1. **Split `colpali.py`** - Embedding generation → ingestion, similarity maps → query
2. **Split `vespa_app.py`** - Connection → connectors, queries → query domain
3. **Keep model loading shared** in `core/models/`

## Implementation Order

1. Phase 1: Move shared utils to `core/`
2. Phase 2: Create `connectors/` with Vespa, LLM, S3 clients
3. Phase 3: Create `ingestion/` with PDF, embeddings, regions
4. Phase 4: Create `query/` with search, ranking, similarity, agent
5. Phase 5: Update `main.py` and clean up

## Risk

- Medium complexity refactor
- ~100 import updates across codebase
- Run tests after each phase

## Get Started

See [plan.md](./plan.md) for detailed implementation steps.
See [tasks.md](./tasks.md) for the full task checklist.
