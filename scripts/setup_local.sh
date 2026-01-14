#!/bin/bash
# Setup script for running ColPali-Vespa Visual Retrieval locally

set -e

echo "=== ColPali-Vespa Visual Retrieval Local Setup ==="
echo

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running. Please start Docker."
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not available."
    exit 1
fi

# Change to project root
cd "$(dirname "$0")/.."

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
fi

# Start Vespa
echo
echo "=== Starting Vespa container ==="
docker-compose up -d

echo
echo "Waiting for Vespa to be ready..."
echo "(This may take 1-2 minutes on first run)"

# Wait for config server
max_attempts=60
attempt=0
while ! curl -s http://localhost:19071/state/v1/health > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "Timeout waiting for Vespa config server"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo " Config server ready!"

# Wait for application to be deployable
sleep 5

# Deploy application
echo
echo "=== Deploying Vespa application ==="

# Check if vespa CLI is available
if command -v vespa &> /dev/null; then
    vespa deploy vespa-app -t http://localhost:19071
else
    # Use curl to deploy
    echo "Vespa CLI not found, deploying via HTTP API..."

    # Create application zip
    cd vespa-app
    zip -r ../app.zip . > /dev/null
    cd ..

    # Deploy
    curl -s -X POST \
        -H "Content-Type: application/zip" \
        --data-binary @app.zip \
        http://localhost:19071/application/v2/tenant/default/prepareandactivate

    rm app.zip
fi

echo
echo "Waiting for application to be active..."
sleep 10

# Check if application is ready
max_attempts=30
attempt=0
while ! curl -s http://localhost:8080/state/v1/health 2>&1 | grep -q "UP"; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "Timeout waiting for Vespa application"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo " Application ready!"

echo
echo "=== Setup Complete ==="
echo
echo "Vespa is running at: http://localhost:8080"
echo
echo "Next steps:"
echo "1. Index some PDF data:"
echo "   python scripts/feed_data.py --sample      # Use sample data"
echo "   python scripts/feed_data.py --pdf-folder /path/to/pdfs"
echo
echo "2. Start the web application:"
echo "   python main.py"
echo
echo "3. Open http://localhost:7860 in your browser"
echo
