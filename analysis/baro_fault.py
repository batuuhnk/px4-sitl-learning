#!/usr/bin/env python3
"""
PX4 SITL ucus logu analizi: simule barometre hatasinda EKF2 davranisi.

Log, baro_noise_sim modulu tek barometre olarak calisirken ve ucus sirasinda
BNS_FAULT parametresi degistirilerek alinir (bkz. docs/06-modul-ve-surucu.md).

Kullanim:
    python3 baro_fault.py <log.ulg> [cikti_klasoru]

Uretilen grafik (adi log dosyasindan gelir, ornek baro_step_10m.ulg -> baro_step_10m.png):
    baro irtifasi vs gercek irtifa, EKF2 irtifa tahmini,
    baro innovation ve test ratio, reddedilen olcumler, EKF2'nin baro fault karari
Konsola: hata araliginda ve disinda baro innovation istatistikleri,
         attitude_monitor zamanlama ozeti
"""
import sys
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyulog import ULog

# --- Renkler (gps_loss.py ile ayni roller) ---
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
EST = "#2a78d6"     # EKF2 tahmini
TRUE = "#eb6834"    # gercek deger (groundtruth)
BARO = "#1baf7a"    # ham baro olcumu
EVENT = "#8a8984"
FAULT_BG = "#f6e7dc"

TOPICS = [
    "vehicle_air_data",
    "vehicle_local_position",
    "vehicle_local_position_groundtruth",
    "estimator_aid_src_baro_hgt",
    "attitude_monitor",
    "estimator_status_flags",
]

FAULT_NAMES = {0: "yok", 1: "takili", 2: "basamak", 3: "kesinti"}


def load(path):
    ulog = ULog(path, TOPICS)
    t0 = ulog.start_timestamp
    data = {}
    for d in ulog.data_list:
        if d.multi_id != 0:
            continue
        data[d.name] = d.data
        # uint64 cikarmasi tasmasin diye once int64'e cevir
        data[d.name]["t"] = (d.data["timestamp"].astype(np.int64) - np.int64(t0)) / 1e6

    # BNS_FAULT degisikliklerinden hata araliklarini cikar
    changes = [((t - t0) / 1e6, int(v)) for t, name, v in ulog.changed_parameters
               if name == "BNS_FAULT" and t > 0]
    intervals = []
    start, mode = None, 0
    for t, v in changes:
        if v != 0 and start is None:
            start, mode = t, v
        elif v == 0 and start is not None:
            intervals.append((start, t, mode))
            start = None
    if start is not None:
        intervals.append((start, data["vehicle_local_position"]["t"][-1], mode))
    return data, intervals


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=TEXT_2, labelsize=9)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(out_dir, exist_ok=True)

    data, intervals = load(path)
    lpos = data["vehicle_local_position"]
    gt = data["vehicle_local_position_groundtruth"]
    air = data["vehicle_air_data"]
    aid = data["estimator_aid_src_baro_hgt"]

    # Ucus araligi: yerden 1 m'den yuksek oldugu zaman (+ biraz pay)
    flying = lpos["t"][-lpos["z"] > 1.0]
    t_start, t_end = (flying[0] - 5, flying[-1] + 5) if len(flying) else (0, lpos["t"][-1])

    # Baro irtifasini ilk ucustan onceki degere gore sifirla (home'a gore irtifa)
    ground = air["t"] < (flying[0] if len(flying) else 1e9)
    baro_ref = np.median(air["baro_alt_meter"][ground]) if ground.any() else air["baro_alt_meter"][0]

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True, facecolor=SURFACE)
    fig.suptitle("Simule baro hatasi: EKF2 irtifa tahmini ve baro innovation",
                 color=TEXT, fontsize=13, x=0.06, ha="left")

    # 1) Irtifa
    ax = axes[0]
    style(ax)
    ax.plot(air["t"], air["baro_alt_meter"] - baro_ref, color=BARO, lw=1.0, label="baro irtifasi (ham)")
    ax.plot(gt["t"], -gt["z"], color=TRUE, lw=1.6, label="gercek irtifa")
    ax.plot(lpos["t"], -lpos["z"], color=EST, lw=1.6, label="EKF2 tahmini")
    ax.set_ylabel("irtifa (m)", color=TEXT_2)
    ax.legend(loc="upper right", fontsize=9, frameon=False)

    # 2) Innovation
    ax = axes[1]
    style(ax)
    sigma = np.sqrt(np.maximum(aid["innovation_variance"], 0))
    ax.fill_between(aid["t"], -3 * sigma, 3 * sigma, color=GRID, label="+-3 sigma (innovation std)")
    ax.plot(aid["t"], aid["innovation"], color=EST, lw=1.0, label="baro innovation")
    ax.set_ylabel("innovation (m)", color=TEXT_2)
    ax.legend(loc="upper right", fontsize=9, frameon=False)

    # 3) Test ratio ve fuse
    ax = axes[2]
    style(ax)
    ax.plot(aid["t"], aid["test_ratio"], color=EST, lw=1.0, label="test ratio")
    ax.axhline(1.0, color=EVENT, lw=1.0, ls="--", label="red esigi (1.0)")
    rej = aid["innovation_rejected"].astype(bool)
    ax.scatter(aid["t"][rej], aid["test_ratio"][rej], s=6, color=TRUE, label="reddedildi", zorder=3)
    ax.set_yscale("symlog", linthresh=1.0)
    ax.set_ylabel("test ratio", color=TEXT_2)
    ax.set_xlabel("zaman (s)", color=TEXT_2)
    ax.legend(loc="upper right", fontsize=9, frameon=False)

    for a in axes:
        for s, e, m in intervals:
            if e > t_start and s < t_end:
                a.axvspan(s, e, color=FAULT_BG, zorder=0)
    for s, e, m in intervals:
        if e > t_start and s < t_end:
            axes[0].text(s, axes[0].get_ylim()[1], f" hata: {FAULT_NAMES.get(m, m)}",
                         va="top", fontsize=9, color=TEXT_2)

    # EKF2'nin barometreyi hatali ilan ettigi an (cs_baro_fault 0 -> 1)
    t_fault = None
    if "estimator_status_flags" in data:
        fl = data["estimator_status_flags"]
        on = np.where(np.diff(fl["cs_baro_fault"].astype(int)) > 0)[0]
        if len(on):
            t_fault = fl["t"][on[0] + 1]
            for a in axes:
                a.axvline(t_fault, color=TRUE, lw=1.2, ls=":")
            axes[2].text(t_fault, 2.0, " EKF2: baro fault", fontsize=9, color=TRUE)

    axes[-1].set_xlim(t_start, t_end)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    stem = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(out_dir, stem + ".png")
    fig.savefig(out, dpi=130)
    print(f"Grafik: {out}")

    # --- Konsol ozeti ---
    in_fault = np.zeros(len(aid["t"]), dtype=bool)
    for s, e, m in intervals:
        in_fault |= (aid["t"] >= s) & (aid["t"] <= e + 1.0)  # +1 s: hata bittikten sonraki gecis
    airborne = (aid["t"] > t_start + 5) & (aid["t"] < t_end - 5)
    for name, mask in [("normal", airborne & ~in_fault), ("hata", airborne & in_fault)]:
        if mask.any():
            inn = aid["innovation"][mask]
            print(f"{name:7s}: innovation ort {np.mean(inn):+.2f} m, std {np.std(inn):.2f} m, "
                  f"test ratio max {np.max(aid['test_ratio'][mask]):.2f}, "
                  f"reddedilen %{100 * np.mean(aid['innovation_rejected'][mask]):.0f}")

    err = np.interp(lpos["t"], gt["t"], -gt["z"]) - (-lpos["z"])
    fly = (lpos["t"] > t_start + 5) & (lpos["t"] < t_end - 5)
    if fly.any():
        print(f"EKF2 irtifa hatasi (ucusta): max {np.max(np.abs(err[fly])):.2f} m")

    if t_fault is not None:
        first = intervals[0][0] if intervals else 0.0
        print(f"EKF2 baro fault karari: t={t_fault:.1f} s (hata basladiktan {t_fault - first:.1f} s sonra), "
              f"baro fuse durdu, flag yeniden baslatmaya kadar kalir")
    else:
        print("EKF2 baro fault karari verilmedi")

    if "attitude_monitor" in data:
        am = data["attitude_monitor"]
        dt = am["dt_us"][am["dt_us"] > 0]
        print(f"attitude_monitor: {len(am['t'])} ornek, dt ort {np.mean(dt):.0f} us, "
              f"max {np.max(dt)} us, max tilt {np.degrees(np.max(am['tilt'])):.1f} deg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
