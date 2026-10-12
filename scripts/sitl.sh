#!/usr/bin/env bash
# PX4 SITL "Build & Run" - CubeIDE'deki Build + Run dugmelerinin karsiligi.
#
# Kullanim:
#   ./sitl.sh              -> derle + SIH quadcopter ile calistir
#   ./sitl.sh build        -> sadece derle (calistirma)
#   ./sitl.sh <hedef>      -> baska bir model, ornek: ./sitl.sh sihsim_airplane
#
# Kod: ~/px4/PX4-Autopilot (VS Code'da duzenlenir)
# Derleyici: px4io/px4-dev container'i (Ubuntu 26.04'te yerel kurulum desteklenmiyor)

set -e

SRC="$HOME/px4/PX4-Autopilot"
IMAGE="px4io/px4-dev:v1.16.0-rc1-258-g0369abd556"
TARGET="${1:-sihsim_quadx}"
JOBS=2   # VM'de 4 GB RAM var, daha fazla paralel derleme bellegi tasirir

if [ "$TARGET" = "build" ]; then
    TARGET=""
fi

# Calisan eski bir PX4 varsa durdur (kartin gucunu kesip yeniden vermek gibi)
if docker ps -q -f name='^px4dev$' | grep -q .; then
    echo ">> Calisan PX4 durduruluyor..."
    docker stop px4dev > /dev/null
fi

mkdir -p "$HOME/.ccache"

echo ">> make px4_sitl $TARGET (j=$JOBS)"
exec docker run -it --rm \
    --network host \
    --name px4dev \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -e CCACHE_DIR="$HOME/.ccache" \
    -v "$HOME/.ccache:$HOME/.ccache" \
    -v "$SRC:$SRC" \
    -w "$SRC" \
    "$IMAGE" \
    bash -c "make px4_sitl $TARGET j=$JOBS"
