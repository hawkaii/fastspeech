# Google Cloud Deployment Guide

This guide covers deploying the Indic TTS API to Google Cloud Platform.

## Prerequisites

1. Google Cloud Project with billing enabled
2. `gcloud` CLI installed and authenticated
3. Docker installed locally
4. Models uploaded to Google Cloud Storage

## Step 1: Prepare GCS Bucket

### Create Bucket

```bash
# Set variables
export PROJECT_ID=your-project-id
export BUCKET_NAME=indic-tts-models
export REGION=us-central1

# Create bucket
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME/
```

### Upload Models

```bash
# Clone the original Fastspeech2_HS repository to get models
git clone https://github.com/smtiitm/Fastspeech2_HS.git
cd Fastspeech2_HS

# Install git-lfs and pull models
git lfs install
git lfs pull

# Upload to GCS
gsutil -m rsync -r hindi gs://$BUCKET_NAME/hindi/
gsutil -m rsync -r bengali gs://$BUCKET_NAME/bengali/
gsutil -m rsync -r tamil gs://$BUCKET_NAME/tamil/
gsutil -m rsync -r vocoder gs://$BUCKET_NAME/vocoder/

# Verify
gsutil ls -r gs://$BUCKET_NAME/
```

## Step 2: Build and Push Docker Image

### Enable Required APIs

```bash
gcloud services enable \
  container.googleapis.com \
  containerregistry.googleapis.com \
  compute.googleapis.com
```

### Build with Cloud Build

```bash
# Navigate to project directory
cd /path/to/indic_tts

# Build image
gcloud builds submit \
  --tag gcr.io/$PROJECT_ID/indic-tts:latest \
  --timeout=30m

# Or build locally and push
docker build -t gcr.io/$PROJECT_ID/indic-tts:latest .
docker push gcr.io/$PROJECT_ID/indic-tts:latest
```

## Step 3: Deploy to Compute Engine

### Create VM with GPU

```bash
# Create VM
gcloud compute instances create indic-tts-vm \
  --project=$PROJECT_ID \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --maintenance-policy=TERMINATE \
  --image-family=ubuntu-2004-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-standard \
  --scopes=cloud-platform \
  --tags=http-server,https-server

# Create firewall rule
gcloud compute firewall-rules create allow-http-tts \
  --allow=tcp:80 \
  --target-tags=http-server \
  --source-ranges=0.0.0.0/0 \
  --description="Allow HTTP traffic to TTS API"
```

### SSH and Setup

```bash
# SSH into VM
gcloud compute ssh indic-tts-vm --zone=us-central1-a

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU
nvidia-smi
```

### Run Container

```bash
# Create data directory
sudo mkdir -p /data/models

# Run container
sudo docker run -d \
  --name indic-tts-api \
  --gpus all \
  --restart unless-stopped \
  -p 80:8080 \
  -e GCS_BUCKET=gs://$BUCKET_NAME \
  -e PRELOAD_MODELS=hindi:male,hindi:female,bengali:male \
  -e DEVICE=cuda \
  -e LOG_LEVEL=info \
  -v /data/models:/models \
  gcr.io/$PROJECT_ID/indic-tts:latest

# Check logs
sudo docker logs -f indic-tts-api
```

### Test Deployment

```bash
# Get external IP
export EXTERNAL_IP=$(gcloud compute instances describe indic-tts-vm \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Test API
curl http://$EXTERNAL_IP/healthz

# Synthesize test
curl -X POST http://$EXTERNAL_IP/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "नमस्ते दुनिया",
    "language": "hindi",
    "gender": "male"
  }' \
  --output test.wav
```

## Step 4: Deploy to GKE (Alternative)

### Create GKE Cluster

```bash
# Create cluster with GPU nodes
gcloud container clusters create indic-tts-cluster \
  --zone us-central1-a \
  --num-nodes 1 \
  --machine-type n1-standard-4 \
  --accelerator type=nvidia-tesla-t4,count=1 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 3 \
  --scopes cloud-platform

# Get credentials
gcloud container clusters get-credentials indic-tts-cluster \
  --zone us-central1-a
```

### Install NVIDIA Device Plugin

```bash
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml
```

### Deploy Application

```bash
# Update kubernetes-deployment.yaml with your PROJECT_ID and BUCKET_NAME
sed -i "s/YOUR_PROJECT_ID/$PROJECT_ID/g" docs/kubernetes-deployment.yaml
sed -i "s/your-indic-tts-bucket/$BUCKET_NAME/g" docs/kubernetes-deployment.yaml

# Deploy
kubectl apply -f docs/kubernetes-deployment.yaml

# Check status
kubectl get pods -n indic-tts
kubectl get svc -n indic-tts

# Get external IP
kubectl get svc indic-tts-service -n indic-tts
```

## Step 5: Set Up Monitoring (Optional)

### Cloud Logging

```bash
# View logs
gcloud logging read "resource.type=gce_instance AND resource.labels.instance_id=INSTANCE_ID" \
  --limit 50 \
  --format json

# Or for GKE
kubectl logs -f deployment/indic-tts-api -n indic-tts
```

### Cloud Monitoring

```bash
# Create uptime check
gcloud monitoring uptime-checks create http indic-tts-health \
  --resource-type=uptime-url \
  --http-check-path=/healthz \
  --host=$EXTERNAL_IP \
  --port=80
```

## Step 6: Configure Domain (Optional)

### Reserve Static IP

```bash
# Reserve IP
gcloud compute addresses create indic-tts-ip \
  --region=us-central1

# Get IP
gcloud compute addresses describe indic-tts-ip \
  --region=us-central1 \
  --format="get(address)"

# Update VM to use static IP
gcloud compute instances delete-access-config indic-tts-vm \
  --zone=us-central1-a \
  --access-config-name="External NAT"

gcloud compute instances add-access-config indic-tts-vm \
  --zone=us-central1-a \
  --access-config-name="External NAT" \
  --address=indic-tts-ip
```

### Configure DNS

1. Go to your DNS provider
2. Create an A record pointing to the static IP
3. Wait for DNS propagation

### Add HTTPS (with Cloud Load Balancer)

```bash
# Create managed SSL certificate
gcloud compute ssl-certificates create indic-tts-cert \
  --domains=tts.yourdomain.com

# Create backend service, URL map, and load balancer
# (See GCP documentation for detailed steps)
```

## Cost Estimation

### Compute Engine (T4 GPU)

- n1-standard-4 with 1x T4 GPU: ~$0.95/hour (~$684/month)
- 100GB persistent disk: ~$4/month
- Network egress: Variable based on usage

### GCS Storage

- Standard storage: $0.020/GB/month
- Models (~50GB): ~$1/month
- Network egress: Variable

### Total Estimated Cost

- ~$700-800/month for always-on GPU instance
- Cheaper with preemptible instances or autoscaling

## Optimization Tips

1. **Use Preemptible VMs**: Save up to 80% on compute costs
2. **Auto-scaling**: Scale down during low traffic
3. **Nearline Storage**: Move unused models to cheaper storage
4. **Regional Resources**: Keep all resources in same region
5. **Committed Use Discounts**: 1 or 3 year commitments for savings

## Troubleshooting

### Container won't start

```bash
# Check logs
sudo docker logs indic-tts-api

# Check GPU
nvidia-smi

# Test container locally
sudo docker run --gpus all -it --rm gcr.io/$PROJECT_ID/indic-tts:latest bash
```

### Models not downloading

```bash
# Check GCS permissions
gsutil ls gs://$BUCKET_NAME/

# Verify service account
gcloud compute instances describe indic-tts-vm \
  --zone=us-central1-a \
  --format="get(serviceAccounts)"
```

### Out of memory

```bash
# Upgrade to larger machine type
gcloud compute instances stop indic-tts-vm --zone=us-central1-a
gcloud compute instances set-machine-type indic-tts-vm \
  --machine-type=n1-standard-8 \
  --zone=us-central1-a
gcloud compute instances start indic-tts-vm --zone=us-central1-a
```

## Cleanup

```bash
# Delete VM
gcloud compute instances delete indic-tts-vm --zone=us-central1-a

# Delete GKE cluster
gcloud container clusters delete indic-tts-cluster --zone=us-central1-a

# Delete images
gcloud container images delete gcr.io/$PROJECT_ID/indic-tts:latest

# Delete bucket (careful!)
gsutil rm -r gs://$BUCKET_NAME/
```
