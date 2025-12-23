# Multi-stage Dockerfile for Indic TTS API with GPU support
FROM nvidia/cuda:11.7.1-cudnn8-runtime-ubuntu20.04 AS base

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CONDA_DIR=/opt/conda \
    PATH=/opt/conda/bin:$PATH

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    wget \
    curl \
    ca-certificates \
    ffmpeg \
    libsndfile1 \
    libgomp1 \
    && git lfs install \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-py37_23.1.0-1-Linux-x86_64.sh -O /tmp/miniconda.sh \
    && /bin/bash /tmp/miniconda.sh -b -p /opt/conda \
    && rm /tmp/miniconda.sh \
    && /opt/conda/bin/conda clean -afy

# Set working directory
WORKDIR /app

# Copy environment file first for layer caching
COPY environment.yml .

# Create conda environment
RUN conda env create -f environment.yml && conda clean -afy

# Install PyTorch with CUDA 11.7 support in the conda environment
RUN /opt/conda/envs/tts-hs-hifigan/bin/pip install --no-cache-dir \
    torch==1.13.1+cu117 \
    torchaudio==0.13.1+cu117 \
    -f https://download.pytorch.org/whl/torch_stable.html

# Install additional dependencies for the API
RUN /opt/conda/envs/tts-hs-hifigan/bin/pip install --no-cache-dir \
    flask==2.2.2 \
    gunicorn==20.1.0 \
    gevent==22.10.2 \
    google-cloud-storage==2.10.0 \
    python-dotenv==0.21.0

# Clone HiFi-GAN repository (code only, no checkpoints)
RUN git clone https://github.com/jik876/hifi-gan.git /app/hifigan \
    && cd /app/hifigan \
    && git checkout 4d871ae9

# Clone Fastspeech2_HS repository for preprocessing code
RUN git clone https://github.com/smtiitm/Fastspeech2_HS.git /tmp/fs2 \
    && mkdir -p /app/preprocessing

# Copy necessary files from the cloned repo
COPY src/ /app/src/
COPY api/ /app/api/
COPY scripts/ /app/scripts/

# Create directories for models and cache
RUN mkdir -p /models /app/tmp /app/phone_dict

# Set Python path
ENV PYTHONPATH=/app:/app/hifigan:/app/src \
    MODELS_DIR=/models \
    DEVICE=cuda

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Use conda run to execute gunicorn in the environment
CMD ["bash", "/app/scripts/start.sh"]
