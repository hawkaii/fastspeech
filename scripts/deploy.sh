#!/bin/bash
# Build and deploy script for Indic TTS API

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required variables are set
check_env() {
    if [ -z "$PROJECT_ID" ]; then
        print_error "PROJECT_ID is not set"
        echo "Usage: export PROJECT_ID=your-gcp-project-id"
        exit 1
    fi
}

# Build Docker image
build_image() {
    print_info "Building Docker image..."
    
    IMAGE_TAG="${IMAGE_TAG:-latest}"
    IMAGE_NAME="gcr.io/$PROJECT_ID/indic-tts:$IMAGE_TAG"
    
    docker build -t "$IMAGE_NAME" .
    
    print_info "Image built: $IMAGE_NAME"
}

# Push to GCR
push_image() {
    print_info "Pushing image to Google Container Registry..."
    
    IMAGE_TAG="${IMAGE_TAG:-latest}"
    IMAGE_NAME="gcr.io/$PROJECT_ID/indic-tts:$IMAGE_TAG"
    
    # Configure Docker to use gcloud as credential helper
    gcloud auth configure-docker
    
    docker push "$IMAGE_NAME"
    
    print_info "Image pushed: $IMAGE_NAME"
}

# Build with Cloud Build
build_cloud() {
    print_info "Building with Cloud Build..."
    
    IMAGE_TAG="${IMAGE_TAG:-latest}"
    
    gcloud builds submit \
        --project=$PROJECT_ID \
        --tag gcr.io/$PROJECT_ID/indic-tts:$IMAGE_TAG \
        --timeout=30m
    
    print_info "Cloud Build complete"
}

# Test locally
test_local() {
    print_info "Testing image locally..."
    
    IMAGE_TAG="${IMAGE_TAG:-latest}"
    IMAGE_NAME="gcr.io/$PROJECT_ID/indic-tts:$IMAGE_TAG"
    
    # Check if container is already running
    if docker ps -a | grep -q indic-tts-test; then
        print_warn "Stopping existing test container..."
        docker stop indic-tts-test || true
        docker rm indic-tts-test || true
    fi
    
    # Run container
    docker run -d \
        --name indic-tts-test \
        -p 8080:8080 \
        -e DEVICE=cpu \
        -e LOG_LEVEL=info \
        "$IMAGE_NAME"
    
    # Wait for startup
    print_info "Waiting for container to start..."
    sleep 10
    
    # Test health endpoint
    if curl -f http://localhost:8080/healthz > /dev/null 2>&1; then
        print_info "Health check passed!"
    else
        print_error "Health check failed"
        docker logs indic-tts-test
        exit 1
    fi
    
    # Cleanup
    docker stop indic-tts-test
    docker rm indic-tts-test
    
    print_info "Local test passed"
}

# Deploy to GCE
deploy_gce() {
    print_info "Deploying to Google Compute Engine..."
    
    INSTANCE_NAME="${INSTANCE_NAME:-indic-tts-vm}"
    ZONE="${ZONE:-us-central1-a}"
    IMAGE_TAG="${IMAGE_TAG:-latest}"
    
    # Check if instance exists
    if gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" > /dev/null 2>&1; then
        print_warn "Instance $INSTANCE_NAME already exists. Updating container..."
        
        # SSH and update container
        gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command="
            sudo docker pull gcr.io/$PROJECT_ID/indic-tts:$IMAGE_TAG
            sudo docker stop indic-tts-api || true
            sudo docker rm indic-tts-api || true
            sudo docker run -d \
                --name indic-tts-api \
                --gpus all \
                --restart unless-stopped \
                -p 80:8080 \
                -e GCS_BUCKET=\$GCS_BUCKET \
                -e PRELOAD_MODELS=\$PRELOAD_MODELS \
                -e DEVICE=cuda \
                -v /data/models:/models \
                gcr.io/$PROJECT_ID/indic-tts:$IMAGE_TAG
        "
    else
        print_info "Creating new instance..."
        
        gcloud compute instances create "$INSTANCE_NAME" \
            --project=$PROJECT_ID \
            --zone="$ZONE" \
            --machine-type=n1-standard-4 \
            --accelerator=type=nvidia-tesla-t4,count=1 \
            --maintenance-policy=TERMINATE \
            --image-family=ubuntu-2004-lts \
            --image-project=ubuntu-os-cloud \
            --boot-disk-size=100GB \
            --scopes=cloud-platform \
            --tags=http-server \
            --metadata-from-file startup-script=scripts/gce-startup.sh
    fi
    
    # Get external IP
    EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
        --zone="$ZONE" \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    
    print_info "Deployment complete!"
    print_info "API URL: http://$EXTERNAL_IP"
}

# Show help
show_help() {
    cat << EOF
Indic TTS API Build and Deployment Script

Usage: $0 [command]

Commands:
    build         Build Docker image locally
    push          Push image to Google Container Registry
    cloud-build   Build using Cloud Build
    test          Test image locally
    deploy        Deploy to Google Compute Engine
    all           Build, push, and deploy
    help          Show this help message

Environment Variables:
    PROJECT_ID       (required) GCP project ID
    IMAGE_TAG        (optional) Docker image tag (default: latest)
    INSTANCE_NAME    (optional) GCE instance name (default: indic-tts-vm)
    ZONE            (optional) GCE zone (default: us-central1-a)
    GCS_BUCKET      (optional) GCS bucket for models
    PRELOAD_MODELS  (optional) Models to preload

Examples:
    export PROJECT_ID=my-project
    $0 build
    $0 test
    $0 deploy

    # Full deployment
    export PROJECT_ID=my-project
    export GCS_BUCKET=gs://my-models
    export PRELOAD_MODELS=hindi:male,bengali:female
    $0 all
EOF
}

# Main script
main() {
    case "${1:-}" in
        build)
            check_env
            build_image
            ;;
        push)
            check_env
            push_image
            ;;
        cloud-build)
            check_env
            build_cloud
            ;;
        test)
            check_env
            test_local
            ;;
        deploy)
            check_env
            deploy_gce
            ;;
        all)
            check_env
            build_image
            push_image
            test_local
            deploy_gce
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: ${1:-}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
