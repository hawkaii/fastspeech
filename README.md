# Indic TTS API - Dockerized Text-to-Speech Service

A production-ready, GPU-accelerated REST API for Indian language text-to-speech synthesis using FastSpeech2 and HiFi-GAN models.

## Features

- **16+ Indian Languages**: Support for Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Marathi, and more
- **GPU Acceleration**: CUDA-optimized for fast inference
- **GCS Integration**: Automatic model download from Google Cloud Storage
- **Advanced Controls**: Support for speed control (`<alpha>` tags) and silence insertion (`<sil>` tags)
- **REST API**: Simple HTTP interface for easy integration
- **Docker**: Fully containerized with GPU support
- **Production Ready**: Health checks, logging, and error handling

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST /synthesize
       ▼
┌─────────────────────┐
│   Flask API Server  │
│   (Gunicorn+Gevent) │
└──────────┬──────────┘
           │
    ┌──────┴────────┐
    │               │
    ▼               ▼
┌─────────┐   ┌──────────┐
│  Model  │   │  GCS     │
│  Store  │◄──┤  Bucket  │
└────┬────┘   └──────────┘
     │
     ▼
┌──────────────────────┐
│  TTS Engine          │
│  - FastSpeech2       │
│  - HiFi-GAN Vocoder  │
│  - Text Preprocessor │
└──────────────────────┘
```

## Quick Start

### Prerequisites

- Docker with GPU support (NVIDIA Container Toolkit)
- NVIDIA GPU with CUDA 11.7 support
- Google Cloud Storage bucket with TTS models (optional for local testing)

### Build the Docker Image

```bash
docker build -t indic-tts:latest .
```

### Run the Container

#### With GPU (Recommended)

```bash
docker run --gpus all \
  -p 8080:8080 \
  -e GCS_BUCKET=gs://your-bucket-name \
  -e PRELOAD_MODELS=hindi:male,bengali:female \
  -v $(pwd)/models:/models \
  indic-tts:latest
```

#### CPU Only (Slower)

```bash
docker run \
  -p 8080:8080 \
  -e DEVICE=cpu \
  -e GCS_BUCKET=gs://your-bucket-name \
  -v $(pwd)/models:/models \
  indic-tts:latest
```

## API Usage

### Health Check

```bash
curl http://localhost:8080/healthz
```

Response:
```json
{
  "status": "healthy",
  "device": "cuda",
  "models_loaded": 2
}
```

### List Available Languages

```bash
curl http://localhost:8080/languages
```

Response:
```json
{
  "languages": {
    "hindi": ["male", "female"],
    "bengali": ["male", "female"],
    "tamil": ["male", "female"]
  },
  "count": 6
}
```

### Synthesize Speech

```bash
curl -X POST http://localhost:8080/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "नमस्ते, आप कैसे हैं?",
    "language": "hindi",
    "gender": "male",
    "alpha": 1.0
  }' \
  --output output.wav
```

#### With Speed Control

```bash
curl -X POST http://localhost:8080/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is normal speed. <alpha=1.2>This is slower.<alpha=0.8>This is faster.",
    "language": "hindi",
    "gender": "female"
  }' \
  --output output.wav
```

#### With Silence Tags

```bash
curl -X POST http://localhost:8080/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "First sentence. <sil=500ms> Second sentence after pause. <sil=2s> Third after long pause.",
    "language": "tamil",
    "gender": "male",
    "alpha": 1.0
  }' \
  --output output.wav
```

### Preload Models

```bash
curl -X POST http://localhost:8080/preload \
  -H "Content-Type: application/json" \
  -d '{
    "models": [
      {"language": "hindi", "gender": "male"},
      {"language": "bengali", "gender": "female"}
    ]
  }'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODELS_DIR` | `/models` | Local directory for model storage |
| `GCS_BUCKET` | - | GCS bucket URI (e.g., `gs://my-bucket`) |
| `DEVICE` | `cuda` | Device to use (`cuda` or `cpu`) |
| `PRELOAD_MODELS` | - | Comma-separated list of models to preload (e.g., `hindi:male,tamil:female`) |
| `PORT` | `8080` | API server port |
| `WORKERS` | `1` | Number of Gunicorn workers |
| `LOG_LEVEL` | `info` | Logging level |
| `MAX_TEXT_LENGTH` | `5000` | Maximum text length in characters |
| `CHUNK_WORDS` | `100` | Words per synthesis chunk |
| `SAMPLING_RATE` | `22050` | Audio sampling rate |

### Example .env File

```bash
GCS_BUCKET=gs://my-indic-tts-models
DEVICE=cuda
PRELOAD_MODELS=hindi:male,hindi:female,bengali:male
LOG_LEVEL=info
WORKERS=1
```

## Google Cloud Storage Setup

### Directory Structure

Your GCS bucket should follow this structure:

```
gs://your-bucket/
├── hindi/
│   ├── male/
│   │   └── model/
│   │       ├── config.yaml
│   │       ├── model.pth
│   │       ├── feats_stats.npz
│   │       ├── pitch_stats.npz
│   │       └── energy_stats.npz
│   └── female/
│       └── model/
│           └── ...
├── bengali/
│   └── ...
└── vocoder/
    ├── male/
    │   ├── aryan/
    │   │   ├── config.json
    │   │   └── generator
    │   └── hindi/
    │       ├── config.json
    │       └── generator
    └── female/
        └── aryan/
            └── ...
```

### Upload Models to GCS

```bash
# Install gsutil
pip install gsutil

# Upload language models
gsutil -m cp -r hindi gs://your-bucket/
gsutil -m cp -r bengali gs://your-bucket/

# Upload vocoders
gsutil -m cp -r vocoder gs://your-bucket/
```

### GCS Bucket Permissions

The service account or credentials used must have:
- `storage.objects.get`
- `storage.objects.list`

```bash
# Set environment variable for authentication
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

## Deployment to Google Cloud

### Option 1: Google Compute Engine (Recommended)

1. **Create VM with GPU**

```bash
gcloud compute instances create indic-tts-vm \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --maintenance-policy=TERMINATE \
  --image-family=ubuntu-2004-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=100GB \
  --metadata-from-file startup-script=scripts/gce-startup.sh
```

2. **SSH into VM and Install NVIDIA Drivers**

```bash
gcloud compute ssh indic-tts-vm --zone=us-central1-a

# Install NVIDIA drivers
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit docker.io
sudo systemctl restart docker
```

3. **Build and Run Container**

```bash
# Clone repository
git clone <your-repo-url>
cd indic_tts

# Build image
sudo docker build -t indic-tts:latest .

# Run container
sudo docker run -d --gpus all \
  --name indic-tts-api \
  -p 80:8080 \
  -e GCS_BUCKET=gs://your-bucket \
  -e PRELOAD_MODELS=hindi:male,bengali:female \
  --restart unless-stopped \
  indic-tts:latest
```

### Option 2: Google Kubernetes Engine (GKE)

1. **Create GKE Cluster with GPU Nodes**

```bash
gcloud container clusters create indic-tts-cluster \
  --zone us-central1-a \
  --num-nodes 1 \
  --machine-type n1-standard-4 \
  --accelerator type=nvidia-tesla-t4,count=1 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 3
```

2. **Install NVIDIA Device Plugin**

```bash
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml
```

3. **Deploy Application**

See `docs/kubernetes-deployment.yaml` for full configuration.

```bash
kubectl apply -f docs/kubernetes-deployment.yaml
```

### Option 3: Cloud Run with GPU (Preview)

```bash
gcloud run deploy indic-tts-api \
  --image gcr.io/your-project/indic-tts:latest \
  --gpu 1 \
  --gpu-type nvidia-l4 \
  --memory 8Gi \
  --cpu 4 \
  --set-env-vars GCS_BUCKET=gs://your-bucket \
  --allow-unauthenticated \
  --region us-central1
```

## Performance

### Benchmarks (NVIDIA T4 GPU)

| Language | Text Length | Synthesis Time | Real-time Factor |
|----------|-------------|----------------|------------------|
| Hindi    | 50 chars    | ~0.8s          | ~8x              |
| Bengali  | 100 chars   | ~1.5s          | ~10x             |
| Tamil    | 200 chars   | ~2.8s          | ~12x             |

### Optimization Tips

1. **Preload Frequently Used Models**: Use `PRELOAD_MODELS` to cache models in memory
2. **Use GPU**: CPU inference is 20-30x slower
3. **Batch Requests**: Send longer texts to amortize model loading overhead
4. **Persistent Storage**: Mount `/models` volume to avoid re-downloading

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs <container-id>

# Verify GPU is available
docker run --gpus all nvidia/cuda:11.7.1-base-ubuntu20.04 nvidia-smi
```

### Models Not Loading

```bash
# Check GCS access
gsutil ls gs://your-bucket/

# Verify service account permissions
gcloud projects get-iam-policy your-project-id

# Check local models directory
docker exec <container-id> ls -la /models
```

### Out of Memory

```bash
# Reduce concurrent workers
-e WORKERS=1

# Use smaller models or CPU
-e DEVICE=cpu
```

### Slow Synthesis

- Verify GPU is being used: Check logs for "Using GPU: ..."
- Reduce `CHUNK_WORDS` if processing very long texts
- Preload models to avoid loading latency

## Development

### Local Development (CPU)

```bash
# Create conda environment
conda env create -f environment.yml
conda activate tts-hs-hifigan

# Install PyTorch CPU
pip install torch==1.13.1 torchaudio==0.13.1

# Set environment
export PYTHONPATH=$(pwd):$(pwd)/hifigan:$(pwd)/src
export MODELS_DIR=./models
export DEVICE=cpu

# Run Flask app
python api/app.py
```

### Testing

```bash
# Run health check
curl http://localhost:8080/healthz

# Test synthesis
curl -X POST http://localhost:8080/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Test","language":"hindi","gender":"male"}' \
  --output test.wav
```

## License

Based on [Fastspeech2_HS](https://github.com/smtiitm/Fastspeech2_HS) - CC BY 4.0

## Credits

- Speech Technology Consortium, IIT Madras
- Bhashini, MeiTY
- Original model authors: Hema A Murthy & S Umesh

## Support

For issues and questions:
- Check logs: `docker logs <container-id>`
- Review documentation in `/docs`
- Open an issue on GitHub
