#!/usr/bin/env bash
set -e

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"
src_dir="$(realpath "${this_dir}/..")"

download="${src_dir}/download"
mkdir -p "${download}"

# -----------------------------------------------------------------------------

: "${PLATFORMS=linux/amd64,linux/arm64,linux/arm/v7}"
: "${DOCKER_REGISTRY=docker.io}"

: "${LANGUAGE=en}"

DOCKERFILE="${src_dir}/Dockerfile"

if [[ -n "${PROXY}" ]]; then
    if [[ -z "${PROXY_HOST}" ]]; then
        export PROXY_HOST="$(hostname -I | awk '{print $1}')"
    fi

    : "${APT_PROXY_HOST=${PROXY_HOST}}"
    : "${APT_PROXY_PORT=3142}"
    : "${PYPI_PROXY_HOST=${PROXY_HOST}}"
    : "${PYPI_PROXY_PORT=4000}"

    export APT_PROXY_HOST
    export APT_PROXY_PORT
    export PYPI_PROXY_HOST
    export PYPI_PROXY_PORT

    echo "APT proxy: ${APT_PROXY_HOST}:${APT_PROXY_PORT}"
    echo "PyPI proxy: ${PYPI_PROXY_HOST}:${PYPI_PROXY_PORT}"

    # Use temporary file instead
    temp_dockerfile="$(mktemp -p "${src_dir}")"
    function cleanup {
        rm -f "${temp_dockerfile}"
    }

    trap cleanup EXIT

    # Run through pre-processor to replace variables
    "${src_dir}/docker/preprocess.sh" < "${DOCKERFILE}" > "${temp_dockerfile}"
    DOCKERFILE="${temp_dockerfile}"
fi

TAG_POSTFIX=''
if [[ -n "${NOAVX}" ]]; then
    # Image will use PyTorch compiled without AVX instructions.
    # This will work with older CPUs like the Celeron.
    TAG_POSTFIX='-noavx'
fi

tags=(--tag "${DOCKER_REGISTRY}/synesthesiam/mozillatts:${LANGUAGE}${TAG_POSTFIX}")

if [[ "${LANGUAGE}" -eq 'en' ]]; then
    tags+=(--tag "${DOCKER_REGISTRY}/synesthesiam/mozillatts:latest${TAG_POSTFIX}")
fi

if [[ -n "${NOBUILDX}" ]]; then
    docker build \
        "${src_dir}" \
        -f "${DOCKERFILE}" \
        --build-arg "LANGUAGE=${LANGUAGE}" \
        "${tags[@]}" \
        "$@"
else
    docker buildx build \
           "${src_dir}" \
           -f "${DOCKERFILE}" \
           "--platform=${PLATFORMS}" \
           --build-arg "LANGUAGE=${LANGUAGE}" \
           "${tags[@]}" \
           --push \
           "$@"
fi
