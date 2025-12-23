#!/bin/bash
# GCE Startup Script for Indic TTS API
# This script installs Docker, NVIDIA drivers, and runs the TTS container

set -e

echo "Starting Indic TTS setup on GCE..."

# Update system
apt-get update
apt-get install -y curl wget git

# Install Docker
if ! command -v docker &> /dev/null; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com -o get-docker.sh
  sh get-docker.sh
  systemctl enable docker
  systemctl start docker
fi

# Install NVIDIA Container Toolkit
if ! dpkg -l | grep -q nvidia-container-toolkit; then
  echo "Installing NVIDIA Container Toolkit..."
  
  distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  
  apt-get update
  apt-get install -y nvidia-container-toolkit
  
  # Configure Docker to use NVIDIA runtime
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
fi

# Verify NVIDIA GPU
nvidia-smi

# Pull the Docker image (update with your image)
# docker pull gcr.io/YOUR_PROJECT/indic-tts:latest

# Create models directory
mkdir -p /data/models

# Set environment variables (update these!)
export GCS_BUCKET="gs://your-indic-tts-bucket"
export PRELOAD_MODELS="hindi:male,bengali:female"

# Run the container
docker run -d \
  --name indic-tts-api \
  --gpus all \
  --restart unless-stopped \
  -p 80:8080 \
  -e GCS_BUCKET="$GCS_BUCKET" \
  -e PRELOAD_MODELS="$PRELOAD_MODELS" \
  -e DEVICE=cuda \
  -e LOG_LEVEL=info \
  -v /data/models:/models \
  gcr.io/YOUR_PROJECT/indic-tts:latest

echo "Indic TTS API is starting..."
echo "Access the API at http://$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H 'Metadata-Flavor: Google')"

# Set up logging
docker logs -f indic-tts-api &
