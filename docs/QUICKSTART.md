# Quick Start Guide

Get up and running with Indic TTS API in minutes.

## Option 1: Local Testing (CPU, No GPU Required)

Perfect for development and testing without GPU hardware.

### Prerequisites

- Docker installed
- Python 3.7+ (for client scripts)
- At least 4GB free disk space

### Steps

```bash
# 1. Clone and navigate to project
cd indic_tts

# 2. Build Docker image
docker build -t indic-tts:latest .

# 3. Run container (CPU mode)
docker run -d \
  --name indic-tts-api \
  -p 8080:8080 \
  -e DEVICE=cpu \
  -e LOG_LEVEL=info \
  indic-tts:latest

# 4. Wait for startup (30-60 seconds)
docker logs -f indic-tts-api

# 5. Test the API
curl http://localhost:8080/healthz

# 6. Synthesize speech (requires models - see below)
curl -X POST http://localhost:8080/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "language": "hindi",
    "gender": "male"
  }' \
  --output test.wav
```

**Note**: Without models from GCS, synthesis will fail. For local testing, you can:
- Mount local models: `-v /path/to/models:/models`
- Use GCS (requires authentication): `-e GCS_BUCKET=gs://your-bucket`

## Option 2: Google Cloud with GPU (Production)

Optimal performance with GPU acceleration.

### Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated
- Models uploaded to GCS bucket

### Steps

```bash
# 1. Set up environment
export PROJECT_ID=your-gcp-project-id
export GCS_BUCKET=gs://your-models-bucket
export PRELOAD_MODELS=hindi:male,hindi:female

# 2. Authenticate
gcloud auth login
gcloud config set project $PROJECT_ID

# 3. Build and push image
docker build -t gcr.io/$PROJECT_ID/indic-tts:latest .
gcloud auth configure-docker
docker push gcr.io/$PROJECT_ID/indic-tts:latest

# Or use Cloud Build (recommended)
gcloud builds submit --tag gcr.io/$PROJECT_ID/indic-tts:latest

# 4. Create VM with GPU
gcloud compute instances create indic-tts-vm \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --maintenance-policy=TERMINATE \
  --image-family=ubuntu-2004-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=100GB \
  --scopes=cloud-platform \
  --tags=http-server \
  --metadata=GCS_BUCKET=$GCS_BUCKET,PRELOAD_MODELS=$PRELOAD_MODELS

# 5. Create firewall rule
gcloud compute firewall-rules create allow-http-tts \
  --allow=tcp:80 \
  --target-tags=http-server \
  --source-ranges=0.0.0.0/0

# 6. SSH and setup
gcloud compute ssh indic-tts-vm --zone=us-central1-a

# Inside VM:
# Install Docker and NVIDIA toolkit (see docs/GCP_DEPLOYMENT.md)
# Then run:
sudo docker run -d \
  --name indic-tts-api \
  --gpus all \
  --restart unless-stopped \
  -p 80:8080 \
  -e GCS_BUCKET=$GCS_BUCKET \
  -e PRELOAD_MODELS=$PRELOAD_MODELS \
  -e DEVICE=cuda \
  -v /data/models:/models \
  gcr.io/$PROJECT_ID/indic-tts:latest

# 7. Get external IP and test
exit  # Exit SSH
EXTERNAL_IP=$(gcloud compute instances describe indic-tts-vm \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

curl http://$EXTERNAL_IP/healthz
```

## Option 3: Using the Deployment Script

Automated deployment with our helper script.

```bash
# 1. Set environment
export PROJECT_ID=your-gcp-project-id
export GCS_BUCKET=gs://your-models-bucket
export PRELOAD_MODELS=hindi:male,bengali:female

# 2. Run deployment script
./scripts/deploy.sh all

# This will:
# - Build Docker image
# - Push to GCR
# - Test locally
# - Deploy to GCE
```

## Preparing Models

### Download from Original Repository

```bash
# Clone Fastspeech2_HS repository
git clone https://github.com/smtiitm/Fastspeech2_HS.git
cd Fastspeech2_HS

# Install git-lfs
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.python.sh | bash
sudo apt-get install git-lfs
git lfs install

# Pull model files
git lfs fetch --all
git lfs pull
```

### Upload to GCS

```bash
# Create bucket
export BUCKET_NAME=my-indic-tts-models
gsutil mb -l us-central1 gs://$BUCKET_NAME/

# Upload models
cd Fastspeech2_HS
gsutil -m rsync -r hindi gs://$BUCKET_NAME/hindi/
gsutil -m rsync -r bengali gs://$BUCKET_NAME/bengali/
gsutil -m rsync -r tamil gs://$BUCKET_NAME/tamil/
gsutil -m rsync -r vocoder gs://$BUCKET_NAME/vocoder/

# Verify
gsutil ls -r gs://$BUCKET_NAME/
```

### Use Local Models

```bash
# Mount local models directory
docker run -d \
  --name indic-tts-api \
  -p 8080:8080 \
  -v /path/to/Fastspeech2_HS:/models \
  -e DEVICE=cpu \
  indic-tts:latest
```

## Testing the API

### Using cURL

```bash
# Health check
curl http://localhost:8080/healthz

# List languages
curl http://localhost:8080/languages

# Synthesize speech
curl -X POST http://localhost:8080/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "नमस्ते, आप कैसे हैं?",
    "language": "hindi",
    "gender": "male",
    "alpha": 1.0
  }' \
  --output output.wav

# Play the audio (macOS)
afplay output.wav

# Or (Linux)
aplay output.wav
```

### Using Python Client

```bash
# Install dependencies
pip install requests

# Health check
./scripts/tts_client.py health

# List languages
./scripts/tts_client.py languages

# Synthesize
./scripts/tts_client.py synthesize \
  "नमस्ते दुनिया" \
  --language hindi \
  --gender male \
  --output hello.wav

# With speed control
./scripts/tts_client.py synthesize \
  "<alpha=1.2>यह धीमा है।<alpha=0.8>यह तेज़ है।" \
  --language hindi \
  --gender female \
  --output varied_speed.wav
```

### Using the Test Script

```bash
# Run all tests
./scripts/test_api.sh

# Or specify API URL
export API_URL=http://your-vm-ip
./scripts/test_api.sh
```

## Common Issues

### Issue: Container exits immediately

**Solution**: Check logs for errors
```bash
docker logs indic-tts-api
```

### Issue: "Model not found" errors

**Solution**: Ensure models are available
```bash
# Check local models
docker exec indic-tts-api ls -la /models

# Or verify GCS bucket
gsutil ls gs://your-bucket/
```

### Issue: Slow synthesis on CPU

**Solution**: This is expected. CPU inference is 20-30x slower than GPU. For production, use GPU instance.

### Issue: Out of memory

**Solution**: 
- Reduce concurrent requests
- Use smaller machine type
- Don't preload too many models

## Next Steps

- Read the [full README](README.md) for detailed API documentation
- See [GCP Deployment Guide](docs/GCP_DEPLOYMENT.md) for production setup
- Check [API examples](docs/api-examples.md) for advanced usage
- Review [troubleshooting guide](docs/troubleshooting.md) for common issues

## Getting Help

- Check container logs: `docker logs indic-tts-api`
- View health status: `curl http://localhost:8080/healthz`
- Review documentation in `/docs` directory
- Open an issue on GitHub for bugs or questions
