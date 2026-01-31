"""
Backend module for visual document retrieval system.

Domain Structure:
- core/        - Shared infrastructure (config, logging, middleware, cache)
- connectors/  - External service clients (Vespa, LLM, S3, PostgreSQL)
- ingestion/   - Document processing (PDF, embeddings, regions, database sync)
- query/       - Search and retrieval (ranking, agent, text processing)

Shared Utilities:
- colpali.py   - SimMapGenerator for embedding generation and similarity maps
"""
