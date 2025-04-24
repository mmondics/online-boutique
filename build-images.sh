#!/bin/bash

# Image version
VERSION="1.0.0"

# Optional flag to enable image push
PUSH_IMAGES=false

# Parse optional arguments
while [ "$#" -gt 0 ]; do
    case $1 in
        --push) PUSH_IMAGES=true ;;
        *) echo "Unknown option: $1" && exit 1 ;;
    esac
    shift
done

# Only prompt for login if pushing is enabled
if $PUSH_IMAGES; then
    podman login quay.io
fi

# Get system architecture and convert it to container-arch
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)   ARCH="amd64" ;;
    aarch64)  ARCH="arm64" ;;
    ppc64le)  ARCH="ppc64le" ;;
    s390x)    ARCH="s390x" ;;
    *)        echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

# Temp file to hold results
RESULTS_FILE=$(mktemp)

# Find and loop over all Dockerfiles
find src/ -type f -name Dockerfile | while IFS= read -r dockerfile; do
    DIR=$(dirname "$dockerfile")
    COMPONENT_NAME=$(basename "$DIR" | tr '[:upper:]' '[:lower:]')
    IMAGE_TAG="quay.io/mmondics/boutique-${COMPONENT_NAME}:${VERSION}-${ARCH}-test"

    echo "Building image for $COMPONENT_NAME from $DIR..."
    if podman build -t "$IMAGE_TAG" "$DIR"; then
        echo "✅ Build succeeded for $COMPONENT_NAME"
        if $PUSH_IMAGES; then
            if podman push "$IMAGE_TAG"; then
                echo "📦 Push succeeded for $COMPONENT_NAME"
                echo "$COMPONENT_NAME: ✅ Build & Push Succeeded" >> "$RESULTS_FILE"
            else
                echo "⚠️ Push failed for $COMPONENT_NAME"
                echo "$COMPONENT_NAME: ✅ Build, ❌ Push Failed" >> "$RESULTS_FILE"
            fi
        else
            echo "$COMPONENT_NAME: ✅ Build Only (Push Skipped)" >> "$RESULTS_FILE"
        fi
    else
        echo "❌ Build failed for $COMPONENT_NAME"
        echo "$COMPONENT_NAME: ❌ Build Failed" >> "$RESULTS_FILE"
    fi
done

# Print summary
echo ""
echo "================== Build Summary =================="
cat "$RESULTS_FILE"
echo "==================================================="

# Cleanup
rm -f "$RESULTS_FILE"

