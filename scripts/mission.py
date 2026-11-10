#!/usr/bin/env python3
"""
PX4 SITL: MAVLink uzerinden arm, takeoff ve basit gorev (pymavlink).

QGroundControl'da dugmeye basarak yaptigimiz isin script karsiligi:
  1. Heartbeat bekle, araca baglan
  2. EKF2'nin global konumu hazir olana kadar bekle
  3. Gorevi (mission) yukle: takeoff -> 3 waypoint -> RTL
  4. Arm et, MISSION moduna gec
  5. Waypoint'lere ulasildikca yazdir, inis ve disarm'i bekle

PX4 SITL, "onboard" MAVLink kanalini UDP 14540'a gonderir. QGC 14550'yi kullanir,
yani bu script QGC acikken de calisir.

Kullanim:
    pip install pymavlink
    python3 mission.py                   # gorev
    python3 mission.py --takeoff-only --hover 30   # sadece kalk, 30 s bekle, in
    python3 mission.py --url udpin:0.0.0.0:14540 --alt 20 --size 40
"""
import argparse
import math
import sys
import time

from pymavlink import mavutil

# PX4 custom mode: main_mode=AUTO(4), sub_mode MISSION(4) / LOITER(3) / LAND(6)
PX4_MAIN_AUTO = 4
PX4_AUTO_MISSION = 4
PX4_AUTO_LAND = 6


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def wait_msg(master, mtype, timeout=10.0, cond=None):
    """Belirli tipte (ve kosulu saglayan) bir mesaj gelene kadar bekle."""
    end = time.time() + timeout
    while time.time() < end:
        m = master.recv_match(type=mtype, blocking=True, timeout=0.5)
        if m is not None and (cond is None or cond(m)):
            return m
    return None


def drain(master, seconds):
    """Belirli sure boyunca gelen mesajlari oku ve at.

    time.sleep() kullanirsak PX4'un onboard kanali (yuksek hizli) UDP tamponunu
    doldurur; sonraki COMMAND_ACK bu birikmis mesajlarin arkasinda kalir ve
    zaman asimina ugrar. Beklerken okumaya devam etmek bunu onler.
    """
    end = time.time() + seconds
    while time.time() < end:
        master.recv_match(blocking=True, timeout=0.2)


def command_long(master, cmd, *params, timeout=5.0):
    """COMMAND_LONG gonder, COMMAND_ACK bekle. Sonucu (MAV_RESULT) dondur."""
    p = list(params) + [0.0] * (7 - len(params))
    master.mav.command_long_send(master.target_system, master.target_component, cmd, 0, *p)
    ack = wait_msg(master, "COMMAND_ACK", timeout, cond=lambda m: m.command == cmd)
    if ack is None:
        raise RuntimeError(f"komut {cmd} icin ACK gelmedi")
    return ack.result


def set_px4_mode(master, main_mode, sub_mode):
    base = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
    res = command_long(master, mavutil.mavlink.MAV_CMD_DO_SET_MODE, base, main_mode, sub_mode)
    if res != mavutil.mavlink.MAV_RESULT_ACCEPTED:
        raise RuntimeError(f"mod degisikligi reddedildi (sonuc {res})")


def wait_ready(master, timeout=60.0):
    """EKF2 global konum vermeye baslayana kadar bekle (GPS fix + home)."""
    log("EKF2 global konumu bekleniyor...")
    end = time.time() + timeout
    while time.time() < end:
        m = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1.0)
        if m is not None and m.lat != 0 and m.lon != 0:
            home = wait_msg(master, "HOME_POSITION", 2.0)
            if home is not None or m is not None:
                log(f"Konum hazir: lat {m.lat / 1e7:.6f} lon {m.lon / 1e7:.6f}")
                return m
    raise RuntimeError("EKF2 global konumu zaman asimina ugradi")


def offset(lat, lon, north_m, east_m):
    """Bir noktadan kuzey/dogu metre kadar uzaktaki koordinat (kucuk mesafeler icin)."""
    r = 6378137.0
    dlat = north_m / r
    dlon = east_m / (r * math.cos(math.radians(lat)))
    return lat + math.degrees(dlat), lon + math.degrees(dlon)


def build_mission(lat0, lon0, alt, size):
    """takeoff -> kare seklinde 3 waypoint -> RTL. Irtifa home'a gore (relative).

    Konumlu ogeler GLOBAL_RELATIVE_ALT_INT frame'inde. RTL'nin konumu yok, PX4 onu
    sadece MAV_FRAME_MISSION ile kabul eder (yoksa MAV_MISSION_UNSUPPORTED_FRAME doner).
    """
    rel = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
    items = [(rel, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, lat0, lon0, alt)]
    for n, e in [(size, 0.0), (size, size), (0.0, size)]:
        lat, lon = offset(lat0, lon0, n, e)
        items.append((rel, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, lat, lon, alt))
    items.append((mavutil.mavlink.MAV_FRAME_MISSION, mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                  0.0, 0.0, 0.0))
    return items


def upload_mission(master, items):
    """MAVLink mission protokolu: COUNT -> (REQUEST_INT -> ITEM_INT) x N -> ACK."""
    mt = mavutil.mavlink.MAV_MISSION_TYPE_MISSION
    master.mav.mission_clear_all_send(master.target_system, master.target_component, mt)
    wait_msg(master, "MISSION_ACK", 3.0)

    master.mav.mission_count_send(master.target_system, master.target_component, len(items), mt)
    sent = set()
    while len(sent) < len(items):
        req = wait_msg(master, ["MISSION_REQUEST_INT", "MISSION_REQUEST"], 5.0)
        if req is None:
            raise RuntimeError("arac waypoint istemedi (MISSION_REQUEST zaman asimi)")
        seq = req.seq
        frame, cmd, lat, lon, alt = items[seq]
        master.mav.mission_item_int_send(
            master.target_system, master.target_component, seq, frame, cmd,
            1 if seq == 0 else 0,   # current
            1,                      # autocontinue
            0, 0, 0, float("nan"),  # param1-4 (yaw=NaN: PX4 kendisi secsin)
            int(lat * 1e7), int(lon * 1e7), alt, mt)
        sent.add(seq)

    ack = wait_msg(master, "MISSION_ACK", 5.0)
    if ack is None or ack.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
        raise RuntimeError(f"gorev kabul edilmedi: {ack}")
    log(f"Gorev yuklendi: {len(items)} oge")


def arm(master):
    res = command_long(master, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
    if res != mavutil.mavlink.MAV_RESULT_ACCEPTED:
        raise RuntimeError(f"arm reddedildi (sonuc {res}), preflight kontrollerine bakin")
    log("Arm edildi")


def wait_disarm(master, timeout):
    end = time.time() + timeout
    last_alt = None
    last_seq = None
    while time.time() < end:
        m = master.recv_match(type=["HEARTBEAT", "MISSION_ITEM_REACHED", "GLOBAL_POSITION_INT",
                                    "STATUSTEXT"], blocking=True, timeout=1.0)
        if m is None:
            continue
        t = m.get_type()
        if t == "MISSION_ITEM_REACHED":
            # PX4 ayni mesaji periyodik tekrarlar, sadece degisince yazdir
            if m.seq != last_seq:
                log(f"Gorev ogesine ulasildi: {m.seq}")
                last_seq = m.seq
        elif t == "STATUSTEXT":
            log(f"PX4: {m.text}")
        elif t == "GLOBAL_POSITION_INT":
            alt = m.relative_alt / 1000.0
            if last_alt is None or abs(alt - last_alt) > 2.0:
                log(f"Irtifa {alt:.1f} m")
                last_alt = alt
        elif t == "HEARTBEAT" and m.get_srcSystem() == master.target_system:
            if not (m.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
                log("Disarm edildi, ucus bitti")
                return True
    return False


def main():
    ap = argparse.ArgumentParser(description="PX4 SITL MAVLink gorev scripti")
    ap.add_argument("--url", default="udpin:0.0.0.0:14540", help="MAVLink baglantisi")
    ap.add_argument("--alt", type=float, default=15.0, help="ucus irtifasi, home'a gore (m)")
    ap.add_argument("--size", type=float, default=30.0, help="kare gorevin kenari (m)")
    ap.add_argument("--takeoff-only", action="store_true", help="sadece kalk, --hover s bekle, in")
    ap.add_argument("--hover", type=float, default=10.0, help="takeoff-only modunda havada bekleme (s)")
    ap.add_argument("--timeout", type=float, default=240.0, help="ucus icin zaman asimi (s)")
    args = ap.parse_args()

    log(f"Baglaniliyor: {args.url}")
    master = mavutil.mavlink_connection(args.url, source_system=245)
    hb = master.wait_heartbeat(timeout=30)
    if hb is None:
        log("Heartbeat gelmedi, PX4 calisiyor mu?")
        return 1
    log(f"Araca baglanildi: sistem {master.target_system}, bilesen {master.target_component}")

    pos = wait_ready(master)
    lat0, lon0 = pos.lat / 1e7, pos.lon / 1e7

    if args.takeoff_only:
        arm(master)
        # MAV_CMD_NAV_TAKEOFF param7 deniz seviyesine gore (AMSL) irtifadir,
        # home'a gore degil. Bu yuzden home AMSL irtifasina ekliyoruz.
        target_amsl = pos.alt / 1000.0 + args.alt
        res = command_long(master, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                           0, 0, 0, float("nan"), float("nan"), float("nan"), target_amsl)
        if res != mavutil.mavlink.MAV_RESULT_ACCEPTED:
            raise RuntimeError(f"takeoff reddedildi (sonuc {res})")
        log(f"Kalkis: {args.alt} m (AMSL {target_amsl:.1f} m)")
        m = wait_msg(master, "GLOBAL_POSITION_INT", 60.0,
                     cond=lambda m: m.relative_alt / 1000.0 > args.alt * 0.9)
        if m is None:
            raise RuntimeError("hedef irtifaya 60 s icinde ulasilamadi")
        log(f"Hedef irtifaya ulasildi ({m.relative_alt / 1000.0:.1f} m), {args.hover:.0f} s bekleniyor")
        drain(master, args.hover)
        set_px4_mode(master, PX4_MAIN_AUTO, PX4_AUTO_LAND)
        log("Inis modu")
    else:
        items = build_mission(lat0, lon0, args.alt, args.size)
        upload_mission(master, items)
        arm(master)
        set_px4_mode(master, PX4_MAIN_AUTO, PX4_AUTO_MISSION)
        log("MISSION modu, gorev basladi")

    ok = wait_disarm(master, args.timeout)
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, KeyboardInterrupt) as e:
        log(f"Durduruldu: {e}")
        sys.exit(1)
