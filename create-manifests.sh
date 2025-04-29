#!/bin/bash

# Set your image version
VERSION="1.0.0"

# Optional flag to push the manifest
PUSH_MANIFEST=false

# Parse optional flags
while [ "$#" -gt 0 ]; do
    case "$1" in
        --push) PUSH_MANIFEST=true ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Architectures to include in the manifest
ARCHITECTURES=("amd64" "arm64" "ppc64le" "s390x")

# Loop through all Dockerfiles in src/
find src/ -type f -name Dockerfile | while IFS= read -r dockerfile; do
    DIR=$(dirname "$dockerfile")

    # Special case for cartservice
    if [[ "$DIR" == *"/cartservice/src" ]]; then
        COMPONENT_NAME="cartservice"
    else
        COMPONENT_NAME=$(basename "$DIR" | tr '[:upper:]' '[:lower:]')
    fi

    MANIFEST_TAG="quay.io/mmondics/boutique-${COMPONENT_NAME}:${VERSION}-test"

    echo "🔧 Creating manifest for ${MANIFEST_TAG}"
    podman manifest create "$MANIFEST_TAG"

    for ARCH in "${ARCHITECTURES[@]}"; do
        IMAGE_TAG="quay.io/mmondics/boutique-${COMPONENT_NAME}:${VERSION}-${ARCH}-test"

        if skopeo inspect --raw "docker://${IMAGE_TAG}" > /dev/null 2>&1; then
            echo "➕ Adding $IMAGE_TAG to manifest"
            podman manifest add "$MANIFEST_TAG" "docker://${IMAGE_TAG}"
        else
            echo "⚠️  Skipping $IMAGE_TAG (not found in remote registry)"
        fi
    done

    if $PUSH_MANIFEST; then
        echo "📤 Pushing manifest $MANIFEST_TAG"
        podman manifest push --all "$MANIFEST_TAG" "docker://${MANIFEST_TAG}"
    else
        echo "✅ Manifest $MANIFEST_TAG created (not pushed)"
    fi

    echo ""
done
