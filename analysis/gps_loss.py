#!/usr/bin/env python3
"""
PX4 SITL ucus logu analizi: GPS kaybinda EKF2 davranisi ve kaskad kontrol.

Kullanim (pyulog + matplotlib olan px4-dev container'inda):
    python3 gps_loss.py <log.ulg> [cikti_klasoru]

Uretilen grafikler:
    gps_loss_overview.png  - GPS kaybi: tahmin vs gercek konum, hata, irtifa, motorlar
    hover_cascade.png      - Hover sirasinda attitude ve rate dongusu: setpoint vs olcum
"""
import sys
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyulog import ULog

# --- Renkler (rol bazli, sabit sira) ---
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
EST = "#2a78d6"     # EKF2 tahmini / setpoint
TRUE = "#eb6834"    # gercek deger (groundtruth) / olcum
MOTORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
EVENT = "#8a8984"

TOPICS = [
    "vehicle_local_position",
    "vehicle_local_position_groundtruth",
    "vehicle_status",
    "sensor_gps",
    "estimator_status_flags",
    "actuator_motors",
    "vehicle_attitude",
    "vehicle_attitude_setpoint",
    "vehicle_rates_setpoint",
    "vehicle_angular_velocity",
]

NAV_NAMES = {2: "Position", 4: "Hold", 12: "Descend", 17: "Takeoff", 18: "Land"}


def load(path):
    ulog = ULog(path, TOPICS)
    t0 = ulog.start_timestamp
    data = {}
    for d in ulog.data_list:
        if d.multi_id != 0:
            continue
        data[d.name] = d.data
        # uint64 cikarma negatif olunca tasiyor; isaretli int64'te cikarip sonra saniyeye cevir
        data[d.name]["t"] = (d.data["timestamp"].astype(np.int64) - np.int64(t0)) / 1e6
    return data


def quat_to_roll(q0, q1, q2, q3):
    return np.degrees(np.arctan2(2 * (q0 * q1 + q2 * q3), 1 - 2 * (q1 ** 2 + q2 ** 2)))


def find_events(d):
    ev = {}
    # GPS kaybi: EKF2'nin GNSS konum fuzyonunu biraktigi son an (True -> False).
    # Not: logger disarm'da kapandigi icin GPS'in geri geldigi an logda olmayabilir.
    fl = d["estimator_status_flags"]
    gnss = fl["cs_gnss_pos"].astype(int)
    drops = np.where(np.diff(gnss) == -1)[0]
    if len(drops):
        ev["gps_lost"] = fl["t"][drops[-1] + 1]
        # EKF2 fuzyonu birakmadan once GPS mesajinin son gelis ani
        tg = d["sensor_gps"]["t"]
        before = tg[tg <= ev["gps_lost"]]
        if len(before):
            ev["last_gps_msg"] = before[-1]

    st = d["vehicle_status"]
    nav, arm, ts = st["nav_state"], st["arming_state"], st["t"]
    armed = np.where(arm == 2)[0]
    if len(armed):
        ev["armed"] = ts[armed[0]]
        ev["disarmed"] = ts[armed[-1]]
    if "last_gps_msg" in ev:
        # Son GPS mesajindan sonraki ilk mod degisikligi = commander'in failsafe karari
        ref = ev["last_gps_msg"]
        after = np.where((ts > ref) & (nav != nav[np.searchsorted(ts, ref) - 1]))[0]
        if len(after):
            ev["failsafe"] = ts[after[0]]
            ev["failsafe_nav"] = int(nav[after[0]])
    return ev


def style(ax, ylabel):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=TEXT_2, labelsize=9)
    ax.set_ylabel(ylabel, color=TEXT_2, fontsize=9)


def mark_events(ax, ev, label=False):
    items = [("last_gps_msg", "Son GPS"), ("failsafe", "Descend"), ("gps_lost", "EKF2 GPS'i birakti"),
             ("disarmed", "Disarm")]
    for key, text in items:
        if key in ev:
            ax.axvline(ev[key], color=EVENT, linewidth=1, linestyle="--")
            if label:
                ax.text(ev[key], 1.02, " " + text, transform=ax.get_xaxis_transform(),
                        color=TEXT_2, fontsize=8, rotation=0, va="bottom")


def overview(d, ev, out):
    t_ev = ev["last_gps_msg"]
    lo, hi = t_ev - 10, ev.get("disarmed", t_ev + 20) + 8
    hi = min(hi, d["vehicle_local_position"]["t"][-1])  # log disarm'da bitiyor

    lp, gt = d["vehicle_local_position"], d["vehicle_local_position_groundtruth"]
    m_lp = (lp["t"] > lo) & (lp["t"] < hi)
    m_gt = (gt["t"] > lo) & (gt["t"] < hi)

    fig, axes = plt.subplots(4, 1, figsize=(11, 11), sharex=True, facecolor=SURFACE)
    fig.suptitle("GPS kaybi: EKF2 tahmini gercekten nasil ayrisiyor?", color=TEXT, fontsize=14,
                 x=0.06, ha="left", y=0.985)

    # 1) Y konumu
    ax = axes[0]
    style(ax, "Y konumu [m]")
    ax.plot(lp["t"][m_lp], lp["y"][m_lp], color=EST, linewidth=2, label="EKF2 tahmini")
    ax.plot(gt["t"][m_gt], gt["y"][m_gt], color=TRUE, linewidth=2, label="Gercek (groundtruth)")
    ax.legend(loc="lower left", frameon=False, fontsize=9, labelcolor=TEXT)
    mark_events(ax, ev, label=True)

    # 2) Yatay konum hatasi
    ax = axes[1]
    style(ax, "Yatay hata [m]")
    gx = np.interp(lp["t"][m_lp], gt["t"], gt["x"])
    gy = np.interp(lp["t"][m_lp], gt["t"], gt["y"])
    err = np.hypot(lp["x"][m_lp] - gx, lp["y"][m_lp] - gy)
    ax.plot(lp["t"][m_lp], err, color=EST, linewidth=2)
    i_max = np.argmax(err)
    ax.annotate(f"max {err[i_max]:.1f} m", (lp["t"][m_lp][i_max], err[i_max]),
                xytext=(8, -4), textcoords="offset points", color=TEXT, fontsize=9)
    mark_events(ax, ev)

    # 3) Irtifa (NED'de z asagi pozitif -> yukseklik = -z)
    ax = axes[2]
    style(ax, "Yukseklik [m]")
    ax.plot(lp["t"][m_lp], -lp["z"][m_lp], color=EST, linewidth=2, label="EKF2 tahmini")
    ax.plot(gt["t"][m_gt], -gt["z"][m_gt], color=TRUE, linewidth=2, label="Gercek")
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=TEXT)
    mark_events(ax, ev)

    # 4) Motor komutlari
    ax = axes[3]
    style(ax, "Motor komutu [0-1]")
    am = d["actuator_motors"]
    m_am = (am["t"] > lo) & (am["t"] < hi)
    names = ["M1 sag on", "M2 sol arka", "M3 sol on", "M4 sag arka"]
    for i in range(4):
        ax.plot(am["t"][m_am], am[f"control[{i}]"][m_am], color=MOTORS[i], linewidth=1.2, label=names[i])
    ax.legend(loc="upper right", ncol=4, frameon=False, fontsize=8, labelcolor=TEXT)
    mark_events(ax, ev)
    ax.set_xlabel("Zaman [s] (log basindan itibaren)", color=TEXT_2, fontsize=9)
    ax.set_xlim(lo, hi)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def hover_cascade(d, ev, out):
    # GPS kaybindan 30 sn once, 3 sn'lik sakin bir hover penceresi
    t1 = ev["last_gps_msg"] - 30
    t0 = t1 - 3

    att, atsp = d["vehicle_attitude"], d["vehicle_attitude_setpoint"]
    rsp, av = d["vehicle_rates_setpoint"], d["vehicle_angular_velocity"]

    def win(x):
        return (x["t"] > t0) & (x["t"] < t1)

    fig, axes = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True, facecolor=SURFACE)
    fig.suptitle("Hover sirasinda kaskad kontrol: roll ekseni", color=TEXT, fontsize=14,
                 x=0.06, ha="left", y=0.985)

    ax = axes[0]
    style(ax, "Roll acisi [deg]")
    m = win(atsp)
    ax.step(atsp["t"][m], quat_to_roll(atsp["q_d[0]"][m], atsp["q_d[1]"][m], atsp["q_d[2]"][m], atsp["q_d[3]"][m]),
            where="post", color=EST, linewidth=2, label="Setpoint (mc_pos_control)")
    m = win(att)
    ax.plot(att["t"][m], quat_to_roll(att["q[0]"][m], att["q[1]"][m], att["q[2]"][m], att["q[3]"][m]),
            color=TRUE, linewidth=2, label="Olcum (ekf2)")
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=TEXT)
    ax.set_title("Dis dongu: attitude (125 Hz setpoint)", color=TEXT_2, fontsize=10, loc="left")

    ax = axes[1]
    style(ax, "Roll hizi [deg/s]")
    m = win(rsp)
    ax.step(rsp["t"][m], np.degrees(rsp["roll"][m]), where="post", color=EST, linewidth=2,
            label="Setpoint (mc_att_control)")
    m = win(av)
    ax.plot(av["t"][m], np.degrees(av["xyz[0]"][m]), color=TRUE, linewidth=1.5, label="Olcum (gyro)")
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=TEXT)
    ax.set_title("Ic dongu: rate (250 Hz)", color=TEXT_2, fontsize=10, loc="left")
    ax.set_xlabel("Zaman [s]", color=TEXT_2, fontsize=9)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(out_dir, exist_ok=True)

    d = load(sys.argv[1])
    ev = find_events(d)
    print("Olaylar (log zamani, s):")
    for k, v in ev.items():
        extra = f" ({NAV_NAMES.get(v, v)})" if k == "failsafe_nav" else ""
        print(f"  {k:14s} {v:8.2f}{extra}" if isinstance(v, float) else f"  {k:14s} {v}{extra}")
    if "last_gps_msg" in ev:
        print(f"  Son GPS mesaji -> EKF2 GPS'i birakti: {ev['gps_lost'] - ev['last_gps_msg']:.2f} s")
    if "last_gps_msg" in ev and "failsafe" in ev:
        print(f"  Son GPS mesaji -> failsafe:         {ev['failsafe'] - ev['last_gps_msg']:.2f} s")
    if "failsafe" in ev and "disarmed" in ev:
        print(f"  Failsafe -> disarm (inis):          {ev['disarmed'] - ev['failsafe']:.2f} s")

    overview(d, ev, os.path.join(out_dir, "gps_loss_overview.png"))
    hover_cascade(d, ev, os.path.join(out_dir, "hover_cascade.png"))
    print("Grafikler:", out_dir)


if __name__ == "__main__":
    main()
