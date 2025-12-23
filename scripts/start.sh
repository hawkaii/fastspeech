#!/bin/bash
# Startup script for Indic TTS API

set -e

echo "Starting Indic TTS API..."

# Set environment
export PYTHONPATH=/app:/app/hifigan:/app/src
export PYTHONUNBUFFERED=1

# Activate conda environment
source /opt/conda/etc/profile.d/conda.sh
conda activate tts-hs-hifigan

# Run any preload tasks if configured
if [ -n "$PRELOAD_MODELS" ]; then
    echo "Preloading models: $PRELOAD_MODELS"
fi

# Start gunicorn with the Flask app
exec gunicorn \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers ${WORKERS:-1} \
    --worker-class gevent \
    --timeout 300 \
    --keep-alive 5 \
    --log-level ${LOG_LEVEL:-info} \
    --access-logfile - \
    --error-logfile - \
    api.app:app
