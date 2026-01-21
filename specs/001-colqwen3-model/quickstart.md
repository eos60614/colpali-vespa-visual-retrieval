# Quickstart: Add ColQwen3 Model Support

**Branch**: `001-colqwen3-model` | **Date**: 2026-01-14

## Prerequisites

- Python 3.11+
- CUDA-capable GPU with 8GB+ VRAM
- FlashAttention 2 (optional, for optimal ColQwen3 performance)

## Setup

### 1. Install Dependencies

```bash
# Existing dependencies should work
pip install -r requirements.txt

# Optional: Install FlashAttention 2 for ColQwen3 performance
pip install flash-attn --no-build-isolation
```

### 2. Environment Variables

No new environment variables required. Existing `.env` configuration works.

### 3. Pre-download Models (Optional)

To avoid first-use download delay:

```python
# Pre-download ColQwen3
from transformers import AutoModel, AutoProcessor
AutoModel.from_pretrained("TomoroAI/tomoro-colqwen3-embed-4b", trust_remote_code=True)
AutoProcessor.from_pretrained("TomoroAI/tomoro-colqwen3-embed-4b", trust_remote_code=True)
```

## Running the Application

```bash
python main.py
```

The application starts with ColPali loaded by default.

## Using Model Selection

### Via UI

1. Navigate to the search page
2. Select model from the "Model" radio group:
   - **ColPali**: Original model (default)
   - **ColQwen3**: Multilingual, better charts/tables
3. Enter search query
4. Select ranking method
5. Submit search

### Via URL

```
# Search with ColQwen3
http://localhost:7860/search?query=financial+report&model=colqwen3&ranking=hybrid

# Search with ColPali (default)
http://localhost:7860/search?query=financial+report&ranking=hybrid
```

## Model Switching Behavior

- First model switch triggers download (~8GB for ColQwen3)
- Model swap takes ~10-30 seconds depending on GPU
- During swap, a loading indicator is shown
- Previous model is unloaded to free GPU memory

## Verifying Model Selection

Check the UI indicator showing current model, or use the status endpoint:

```bash
curl http://localhost:7860/model_status
```

Response:
```json
{
  "current_model": "colqwen3",
  "is_loading": false
}
```

## Troubleshooting

### "FlashAttention not available" Warning

ColQwen3 works without FlashAttention but with reduced performance. To fix:

```bash
pip install flash-attn --no-build-isolation
```

Requires compatible CUDA version.

### "CUDA out of memory" Error

1. Ensure only one model is loaded
2. Try restarting the application
3. Close other GPU-using applications

### Model Download Fails

Check internet connection and HuggingFace access:

```bash
huggingface-cli whoami
```

## Development Testing

### Test Model Switching

```python
# Quick test script
import requests

# Switch to ColQwen3
r = requests.get("http://localhost:7860/switch_model?model=colqwen3")
print(r.json())

# Verify
r = requests.get("http://localhost:7860/model_status")
print(r.json())

# Run a search
r = requests.get("http://localhost:7860/search?query=test&model=colqwen3")
print(r.status_code)
```

### Test Search with Both Models

```python
# Compare results
for model in ["colpali", "colqwen3"]:
    r = requests.get(f"http://localhost:7860/fetch_results?query=chart&ranking=hybrid&model={model}")
    print(f"{model}: {r.status_code}")
```
