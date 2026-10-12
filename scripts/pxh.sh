#!/usr/bin/env bash
# Calisan PX4'e (sitl.sh ile acilan) disaridan pxh komutu gonderir.
# pxh> konsoluna yazmakla ayni, ama normal terminalden ve yapistirma sorunu olmadan.
#
# Ornekler:
#   ./pxh.sh listener vehicle_attitude
#   ./pxh.sh uorb top -1
#   ./pxh.sh commander takeoff
#   ./pxh.sh failure gps off

set -e

if [ $# -eq 0 ]; then
    echo "Kullanim: $0 <komut> [argumanlar]   (ornek: $0 listener vehicle_status)"
    exit 1
fi

ROOTFS="$HOME/px4/PX4-Autopilot/build/px4_sitl_default/rootfs"
CMD="$1"
shift

# Her pxh komutu bin/ altinda px4-<komut> adli bir istemci olarak bulunur;
# istemci, calisan px4 surecine baglanip komutu onun icinde calistirir.
exec docker exec -w "$ROOTFS" px4dev "../bin/px4-$CMD" "$@"
