#!/bin/bash
# Upload models to Google Cloud Storage
# Usage: ./upload_models_to_gcs.sh <local-models-dir> <gcs-bucket>

set -e

if [ $# -ne 2 ]; then
  echo "Usage: $0 <local-models-dir> <gcs-bucket>"
  echo "Example: $0 ./models gs://my-indic-tts-bucket"
  exit 1
fi

LOCAL_DIR=$1
GCS_BUCKET=$2

# Remove gs:// prefix if present
GCS_BUCKET=${GCS_BUCKET#gs://}
GCS_BUCKET="gs://${GCS_BUCKET}"

echo "Uploading models from $LOCAL_DIR to $GCS_BUCKET"
echo "================================================"

# Check if gsutil is installed
if ! command -v gsutil &> /dev/null; then
  echo "ERROR: gsutil not found. Please install Google Cloud SDK."
  exit 1
fi

# Check if local directory exists
if [ ! -d "$LOCAL_DIR" ]; then
  echo "ERROR: Local directory not found: $LOCAL_DIR"
  exit 1
fi

# Upload all model files
echo "Uploading language models..."
for lang_dir in "$LOCAL_DIR"/*; do
  if [ -d "$lang_dir" ] && [ "$(basename "$lang_dir")" != "vocoder" ]; then
    lang=$(basename "$lang_dir")
    echo "  Uploading $lang..."
    gsutil -m rsync -r "$lang_dir" "$GCS_BUCKET/$lang/"
  fi
done

# Upload vocoder files
if [ -d "$LOCAL_DIR/vocoder" ]; then
  echo "Uploading vocoders..."
  gsutil -m rsync -r "$LOCAL_DIR/vocoder" "$GCS_BUCKET/vocoder/"
fi

echo ""
echo "Upload complete!"
echo ""
echo "Verify with: gsutil ls -r $GCS_BUCKET"
