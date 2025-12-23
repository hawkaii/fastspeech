# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │   cURL   │  │  Python  │  │   Web    │  │  Mobile  │      │
│  │          │  │  Client  │  │   App    │  │   App    │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │             │             │             │              │
│       └─────────────┴─────────────┴─────────────┘              │
│                            │                                    │
│                            │ HTTP/HTTPS                         │
└────────────────────────────┼────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Load Balancer (GCP)                          │
│                   - Health Checks                               │
│                   - SSL Termination                             │
│                   - Request Routing                             │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Flask API Server                             │
│                   (Gunicorn + Gevent)                           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  REST Endpoints:                                         │  │
│  │  - POST /synthesize  → Generate speech from text        │  │
│  │  - GET  /healthz     → Health check                     │  │
│  │  - GET  /languages   → List available models            │  │
│  │  - POST /preload     → Preload models into memory       │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                             ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            TTS Engine (tts_engine.py)                    │  │
│  │  - Model Cache Management                                │  │
│  │  - Device Selection (GPU/CPU)                            │  │
│  │  - Text Chunking & Processing                            │  │
│  │  - Alpha/Silence Tag Parsing                             │  │
│  └──┬───────────────────────┬───────────────────────────────┘  │
│     │                       │                                   │
└─────┼───────────────────────┼───────────────────────────────────┘
      │                       │
      ▼                       ▼
┌──────────────────┐   ┌──────────────────┐
│  Model Store     │   │ Text Processor   │
│                  │   │                  │
│ - GCS Download   │   │ - Language Det.  │
│ - Local Caching  │   │ - Normalization  │
│ - Thread Safety  │   │ - Phonification  │
└────┬─────────────┘   └──────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Model Layer (GPU/CPU)                        │
│                                                                 │
│  ┌────────────────────┐         ┌──────────────────────┐       │
│  │  FastSpeech2 Model │         │  HiFi-GAN Vocoder   │       │
│  │                    │         │                      │       │
│  │ Text → Phonemes    │  mel    │  Mel → Audio        │       │
│  │ Phonemes → Mel     ├────────>│                      │       │
│  │ (ESPnet)           │         │  (Neural Vocoder)    │       │
│  └────────────────────┘         └──────────────────────┘       │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Cached Models (in memory):                             │  │
│  │  - hindi:male     → (FS2, Vocoder, Preprocessor)        │  │
│  │  - bengali:female → (FS2, Vocoder, Preprocessor)        │  │
│  │  - tamil:male     → (FS2, Vocoder, Preprocessor)        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                             ▲
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                    Storage Layer                                │
│                                                                 │
│  ┌─────────────────────┐      ┌──────────────────────────┐     │
│  │  Google Cloud       │      │  Local Disk              │     │
│  │  Storage (GCS)      │      │  /models                 │     │
│  │                     │      │                          │     │
│  │  - Model Files      │─────>│  - Cached Models         │     │
│  │  - Vocoder Files    │      │  - Stats Files           │     │
│  │  - Config Files     │      │  - Config Files          │     │
│  └─────────────────────┘      └──────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## Request Flow

### 1. Synthesis Request

```
Client Request
    │
    ├─> POST /synthesize
    │   {
    │     "text": "नमस्ते",
    │     "language": "hindi",
    │     "gender": "male",
    │     "alpha": 1.0
    │   }
    │
    ▼
Flask API (api/app.py)
    │
    ├─> Validate request
    ├─> Extract parameters
    │
    ▼
TTS Engine (src/tts_engine.py)
    │
    ├─> Check model cache
    │   │
    │   ├─> If NOT cached:
    │   │   │
    │   │   ├─> Model Store → Check local disk
    │   │   │                 │
    │   │   │                 ├─> If NOT local:
    │   │   │                 │   Download from GCS
    │   │   │                 │
    │   │   │                 └─> Load into memory
    │   │   │
    │   │   └─> Cache model
    │   │
    │   └─> Return cached model
    │
    ├─> Parse text for <alpha>/<sil> tags
    ├─> Split into chunks
    │
    ▼
Text Processor
    │
    ├─> Clean text
    ├─> Normalize numbers
    ├─> Convert to phonemes
    │
    ▼
FastSpeech2 Model
    │
    ├─> Text → Phoneme embedding
    ├─> Duration prediction
    ├─> Pitch/energy prediction
    ├─> Mel-spectrogram generation
    │
    ▼
HiFi-GAN Vocoder
    │
    ├─> Mel → Raw audio waveform
    │
    ▼
TTS Engine
    │
    ├─> Concatenate audio chunks
    ├─> Add silence if <sil> tags
    │
    ▼
Flask API
    │
    ├─> Convert to WAV format
    ├─> Return audio/wav response
    │
    ▼
Client receives audio file
```

## Component Interactions

### Model Loading Flow

```
Request for language:gender
    │
    ▼
┌─────────────────────────────────┐
│   Is model cached in memory?    │
└────────┬───────────┬─────────────┘
         │           │
        YES          NO
         │           │
         │           ▼
         │    ┌──────────────────────────────┐
         │    │  Check local disk (/models)  │
         │    └──────┬────────────┬──────────┘
         │           │            │
         │          YES           NO
         │           │            │
         │           │            ▼
         │           │     ┌──────────────────┐
         │           │     │  Download from   │
         │           │     │  GCS bucket      │
         │           │     └────┬─────────────┘
         │           │          │
         │           ▼          ▼
         │    ┌────────────────────────────┐
         │    │  Load model into memory    │
         │    │  - FastSpeech2             │
         │    │  - HiFi-GAN                │
         │    │  - Text Preprocessor       │
         │    └─────────┬──────────────────┘
         │              │
         │              ▼
         │    ┌────────────────────────────┐
         │    │  Cache in memory           │
         │    │  Key: (language, gender)   │
         │    └─────────┬──────────────────┘
         │              │
         └──────────────┘
                 │
                 ▼
         Return model instance
```

## Deployment Architectures

### Option 1: Single GCE Instance

```
Internet
    │
    ▼
┌────────────────────────────────┐
│  GCE VM (n1-standard-4)        │
│  - NVIDIA T4 GPU               │
│  - Ubuntu 20.04                │
│  - Docker + NVIDIA toolkit     │
│                                │
│  ┌──────────────────────────┐  │
│  │  Docker Container        │  │
│  │  - Flask API             │  │
│  │  - GPU-accelerated       │  │
│  │  - Port 80 exposed       │  │
│  └──────────────────────────┘  │
│                                │
│  /data/models (Persistent)     │
└────────────────────────────────┘
         │
         ▼
    GCS Bucket
```

### Option 2: GKE Cluster

```
Internet
    │
    ▼
┌────────────────────────────────────────┐
│  Cloud Load Balancer                   │
│  - SSL Termination                     │
│  - Health Checks                       │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│  GKE Cluster                           │
│                                        │
│  ┌──────────────┐  ┌──────────────┐  │
│  │  Pod 1       │  │  Pod 2       │  │
│  │  - Container │  │  - Container │  │
│  │  - T4 GPU    │  │  - T4 GPU    │  │
│  └──────────────┘  └──────────────┘  │
│         │                 │           │
│         └────────┬────────┘           │
│                  ▼                    │
│         ┌─────────────────┐           │
│         │ Persistent Vol  │           │
│         │ /models cache   │           │
│         └─────────────────┘           │
└────────────────────────────────────────┘
             │
             ▼
        GCS Bucket
```

## Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│                                                             │
│  Flask 2.2.2          REST API framework                   │
│  Gunicorn 20.1.0      WSGI server                          │
│  Gevent 22.10.2       Async workers                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    ML/AI Layer                              │
│                                                             │
│  ESPnet 202209        Speech processing toolkit            │
│  PyTorch 1.13.1       Deep learning framework              │
│  HiFi-GAN             Neural vocoder                       │
│  FastSpeech2         Acoustic model                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                     │
│                                                             │
│  Docker               Containerization                      │
│  CUDA 11.7           GPU acceleration                      │
│  Google Cloud         Cloud platform                       │
│  Kubernetes          Orchestration (optional)              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Dependencies                             │
│                                                             │
│  NumPy, SciPy         Numerical computing                  │
│  Librosa             Audio processing                      │
│  indic_unified_parser Text preprocessing                   │
│  google-cloud-storage GCS integration                      │
└─────────────────────────────────────────────────────────────┘
```

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Network Security                         │
│                                                             │
│  - VPC with private subnets                                │
│  - Firewall rules (allow :80 from LB only)                 │
│  - Cloud Armor (DDoS protection)                           │
│  - SSL/TLS termination at load balancer                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Identity & Access                        │
│                                                             │
│  - Service Account with minimal permissions                │
│  - GCS: storage.objects.get, storage.objects.list          │
│  - No public bucket access                                 │
│  - Workload Identity (GKE)                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Application Security                     │
│                                                             │
│  - Input validation (text length, params)                  │
│  - Rate limiting (optional)                                │
│  - Container runs as non-root (configurable)               │
│  - No secrets in container image                           │
└─────────────────────────────────────────────────────────────┘
```

## Monitoring & Observability

```
┌──────────────────────────────────────────────────────────────┐
│                         Metrics                              │
│                                                              │
│  - Request count, latency, errors (Prometheus/Stackdriver)  │
│  - GPU utilization (nvidia-smi)                              │
│  - Memory usage per model                                   │
│  - Cache hit/miss ratios                                    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                          Logging                             │
│                                                              │
│  - Structured JSON logs                                     │
│  - Cloud Logging integration                                │
│  - Request/response logging                                 │
│  - Error tracking                                           │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                        Health Checks                         │
│                                                              │
│  - /healthz endpoint                                        │
│  - Load balancer health probes                              │
│  - Liveness/readiness probes (K8s)                          │
└──────────────────────────────────────────────────────────────┘
```
