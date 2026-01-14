# Local Setup Guide

This guide explains how to run ColPali-Vespa Visual Retrieval locally using open-source Vespa instead of Vespa Cloud.

## Prerequisites

- **Docker**: Docker Engine with at least 8GB RAM available
- **Python 3.10+**: With pip
- **GPU (optional)**: CUDA-capable GPU recommended for faster embedding generation

## Quick Start

### 1. Start Vespa

```bash
# Start Vespa container
docker-compose up -d

# Wait for Vespa to be ready (1-2 minutes on first run)
# You can check status with:
curl http://localhost:19071/state/v1/health
```

### 2. Deploy the Application Schema

Using the Vespa CLI:
```bash
vespa deploy vespa-app -t http://localhost:19071
```

Or via HTTP API:
```bash
cd vespa-app
zip -r ../app.zip .
cd ..
curl -X POST \
    -H "Content-Type: application/zip" \
    --data-binary @app.zip \
    http://localhost:19071/application/v2/tenant/default/prepareandactivate
rm app.zip
```

### 3. Install Dependencies

```bash
# Install base requirements
pip install -r requirements.txt

# Install local development dependencies
pip install -r requirements-local.txt

# Download spaCy model for stopword filtering
python -m spacy download en_core_web_sm
```

### 4. Configure Environment

```bash
# Create .env file
cp .env.example .env

# The default config points to local Vespa:
# VESPA_LOCAL_URL=http://localhost:8080
```

### 5. Index Some Data

```bash
# Option A: Use sample data for testing
python scripts/feed_data.py --sample

# Option B: Index your own PDFs
python scripts/feed_data.py --pdf-folder /path/to/your/pdfs
```

### 6. Start the Application

```bash
python main.py
```

Open http://localhost:7860 in your browser.

## Automated Setup

Run the setup script to automate steps 1-2:

```bash
./scripts/setup_local.sh
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Browser                             │
│                   http://localhost:7860                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastHTML Application                      │
│                        (main.py)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   ColPali    │  │   Vespa      │  │   Gemini     │       │
│  │   Embeddings │  │   Client     │  │   (optional) │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Local Vespa (Docker)                      │
│                   http://localhost:8080                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   pdf_page schema                     │   │
│  │  - Text fields (title, text, snippet)                │   │
│  │  - Image fields (blur_image, full_image)             │   │
│  │  - ColPali embeddings (int8 tensor with HNSW)        │   │
│  │  - Ranking profiles (bm25, colpali, hybrid)          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Vespa Schema

The application uses a `pdf_page` schema with:

**Document Fields:**
- `id`, `url`, `title`, `page_number`, `year`
- `text`, `snippet` - Full text and excerpts
- `blur_image`, `full_image` - Base64 encoded images
- `embedding` - ColPali binary embeddings (`tensor<int8>(patch{}, v[16])`)
- `questions`, `queries` - Generated metadata

**Ranking Profiles:**
- `bm25` - Traditional text search
- `colpali` - Visual embedding similarity (MaxSim)
- `hybrid` - Combined text + visual search

## Troubleshooting

### Vespa won't start
- Check Docker has enough memory: `docker info | grep Memory`
- Minimum 8GB recommended

### Connection refused
- Wait for Vespa to fully initialize (check `docker logs vespa`)
- Verify ports 8080 and 19071 are not in use

### Out of memory during embedding generation
- Reduce batch size in feed script
- Use CPU instead of GPU (slower but less memory)

### Application deployment fails
- Check schema syntax: `vespa validate vespa-app`
- View config server logs: `docker logs vespa | grep -i error`

## Stopping Vespa

```bash
# Stop and remove container (keeps data)
docker-compose down

# Stop and remove container + data
docker-compose down -v
```

## Resources

- [Vespa Documentation](https://docs.vespa.ai/)
- [ColPali Paper](https://arxiv.org/abs/2407.01449)
- [pyvespa Examples](https://pyvespa.readthedocs.io/)
