import math
import json

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from ensure6g.core import (
    HOTSPOTS,
    P_TX,
    RAIL_WP,
    SEG_NAMES,
    TECH,
    TECH_KEYS,
    TSR_CAP,
    cap_loss,
    env_class,
    haversine_m,
    haversine_vec,
    interpolate_polyline,
    label_segments,
    nearest_bs_quality,
    noise_dbm,
    pathloss_db,
    per_from_snr,
    pick_bearer,
    pick_secondary,
    point_in_bbox,
    rayleigh_db,
    rician_db,
    serving_bs,
    sensor_static,
    tsr_poly,
)
from ensure6g.core import _poly_key, _tsr_key_set
from ensure6g.thermal_data import current_thermal_stats, semantic_event_from_stats


V_MAX_MS = 200 / 3.6
A_MAX = 0.6
B_MAX = 0.9
N_SENS = 22
BYTES_RAW = 24
BYTES_ALERT = 280
BYTES_SUMM = 180
RAW_HZ = {"RAW": 2.0, "HYBRID": 0.2, "SEMANTIC": 0.0}


def prepare_route(sim_minutes):
    secs = max(2, int(sim_minutes * 60))
    if st.session_state.get("route_secs") != secs:
        st.session_state.route_df = interpolate_polyline(RAIL_WP, secs)
        st.session_state.seg_labels = label_segments(secs)
        st.session_state.route_secs = secs
        for k in ["arr", "_times", "sensor_static_cache"]:
            st.session_state.pop(k, None)
    return secs, st.session_state.route_df, st.session_state.seg_labels


def auto_advance(play_rate, secs):
    if st.session_state.playing:
        rate_ms = {"0.5×": 1400, "1×": 700, "2×": 350, "4×": 175}.get(play_rate, 700)
        st_autorefresh(interval=rate_ms, key=f"tick_{secs}_{play_rate}")
        st.session_state.t_idx = min(st.session_state.t_idx + 1, secs - 1)
        if st.session_state.t_idx >= secs - 1:
            st.session_state.playing = False
    return st.session_state.t_idx


def _thermal_payload_bps(thermal, mode):
    if not thermal.get("available"):
        return 0
    payload_key = {
        "RAW": "payload_bytes",
        "HYBRID": "hybrid_payload_bytes",
        "SEMANTIC": "semantic_payload_bytes",
    }.get(mode, "semantic_payload_bytes")
    return int(thermal.get(payload_key, 0))


def _thermal_delivery_loss(base_loss, mode):
    if mode == "SEMANTIC":
        return min(0.85, base_loss * 0.35)
    if mode == "HYBRID":
        return min(0.90, base_loss * 0.75 + 0.03)
    return min(0.97, base_loss + 0.12)


def _thermal_event_delivered(loss, mode, frame_id):
    if mode == "SEMANTIC":
        return True
    factor = 31 if mode == "HYBRID" else 17
    delivery_score = ((frame_id * factor) % 100) / 100
    return delivery_score > loss


def _thermal_mode_comparison(thermal, base_loss, cap_bps):
    if not thermal.get("available"):
        return []

    event = thermal.get("semantic_event", {})
    risk = event.get("risk_label", "low")
    rows = []
    for mode, payload_key, description in [
        ("RAW", "payload_bytes", "Full P2 Pro thermal frame"),
        ("HYBRID", "hybrid_payload_bytes", "Preview-scale context plus event"),
        ("SEMANTIC", "semantic_payload_bytes", "Event meaning only"),
    ]:
        payload = int(thermal.get(payload_key, 0))
        delivery_loss = _thermal_delivery_loss(base_loss, mode)
        delivered = risk == "low" or _thermal_event_delivered(delivery_loss, mode, thermal["frame_id"])
        load_pct = 100 * payload / max(cap_bps, 1)
        transfer_ms = 1000 * payload * 8 / max(cap_bps, 1)
        rows.append(
            {
                "mode": mode,
                "description": description,
                "payload_bytes": payload,
                "payload_kb": payload / 1024,
                "delivery_loss": delivery_loss,
                "reliability_pct": 100 * (1 - delivery_loss),
                "delivered": delivered,
                "load_pct": load_pct,
                "transfer_ms": transfer_ms,
                "tms_action": delivered and event.get("recommended_action") == "issue_tsr",
            }
        )
    return rows


def _apply_tsr_from_alert(alert, controls, t, real_keys):
    if alert["confidence"] < controls["tsr_conf"]:
        return
    poly = tsr_poly(alert["lat"], alert["lon"])
    entry = dict(
        polygon=poly,
        speed=controls["tsr_speed"],
        created_idx=t,
        critical=True,
        stop=(alert["confidence"] >= 0.92 and controls["stop_on_crit"]),
    )
    if _poly_key(poly) not in real_keys:
        st.session_state.tsr_real.append(entry)
        real_keys.add(_poly_key(poly))


def _sensor_row(t, row, qualS, capS0, seg_s, demo_issues, summer_sev, thermal=None, thermal_weight=0.0):
    base = 24 + 10 * math.sin(2 * math.pi * ((t / 60) % 1440) / 1440)
    boost, hot = 0.0, ""
    if demo_issues:
        for h in HOTSPOTS:
            d = haversine_m(row.lat, row.lon, h["lat"], h["lon"])
            if d <= h["radius_m"]:
                w = max(0.0, 1.0 - d / h["radius_m"])
                b = w * summer_sev
                if b > boost:
                    boost, hot = b, h["name"]
    thermal_boost = 0.0
    if thermal and thermal.get("available") and thermal_weight > 0:
        calibrated_mean = thermal["mean_temp_c"] + 4.0
        thermal_signal = max(0.0, thermal["p99_temp_c"] - 31.0) + thermal["delta_temp_c"] * 1.5
        thermal_boost = thermal_weight * thermal_signal
        hot = hot or f"thermal frame {thermal['frame_id']}"
        base = max(base, calibrated_mean)
    temp = base + np.random.normal(0, 0.6) + boost + thermal_boost
    strain = max(0.0, (temp - 35) * 0.8 + np.random.normal(0, 0.5))
    ballast = max(0.0, np.random.normal(0.3, 0.1) + 0.015 * boost)
    score = min(1.0, 0.01 * (temp - 30) ** 2 + 0.04 * max(0, strain - 8) + 0.2 * (boost > 6) + 0.15 * (thermal_boost > 3))
    label = "high" if score > 0.75 else ("medium" if score > 0.4 else "low")
    exc = (["temp>38"] if temp >= 38 else []) + (["strain>10"] if strain >= 10 else [])
    _, lossS = cap_loss(qualS, t)
    return dict(
        score=score,
        label=label,
        exceeded=exc,
        temp=round(temp, 1),
        strain=round(strain, 1),
        ballast=round(ballast, 2),
        qualS=qualS,
        capS=capS0,
        lossS=lossS,
        hotspot=hot,
        segment=seg_s,
    )


def _choose_modality(r):
    if r["qualS"] == "POOR" or r["capS"] < 100_000:
        return "SEMANTIC"
    if r["qualS"] == "GOOD" and r["score"] < 0.4 and r["capS"] > 400_000:
        return "RAW"
    return "HYBRID"


def compute_frame(route_df, seg_labels, secs, controls):
    t = min(max(int(st.session_state.t_idx), 0), secs - 1)
    thermal = current_thermal_stats(controls.get("thermal_source"), t)
    idx_s = t
    st.session_state.t_idx = t
    train_s_m = float(route_df.s_m.iloc[idx_s])
    st.session_state.train_s_m = train_s_m
    idx_s = min(max(int(idx_s), 0), len(route_df) - 1)
    trainA = (float(route_df.lat.iloc[idx_s]), float(route_df.lon.iloc[idx_s]))
    seg = seg_labels[idx_s]
    s_along = float(route_df.s_m.iloc[idx_s])

    bsA, dA = serving_bs(*trainA)
    envA = env_class(*trainA)
    shadow = st.session_state.shadow
    snr_table = {}
    for b in ["5G", "LTE", "3G", "GSM"]:
        if b in bsA["tech"]:
            k = TECH_KEYS[b]
            pl = pathloss_db(TECH[k]["freq"], dA, envA)
            sh = shadow.sample(s_along)
            fad = rician_db(8) if envA == "RMa" else rayleigh_db()
            snr_table[b] = P_TX - pl + sh + fad - noise_dbm(TECH[k]["bw"])

    cand, valid = pick_bearer(snr_table, bsA["tech"], st.session_state.bearer)
    if valid and cand != st.session_state.bearer:
        st.session_state.bearer_ttt += 700
        if st.session_state.bearer_ttt >= controls["TTT_MS"]:
            st.session_state.bearer_prev = st.session_state.bearer
            st.session_state.bearer = cand
            st.session_state.bearer_ttt = 0
            st.session_state.ho_gap_until = t + math.ceil(controls["HO_GAP_MS"] / 700)
    else:
        st.session_state.bearer_ttt = 0

    bearer = st.session_state.bearer
    tk = TECH_KEYS[bearer]
    snr_use = snr_table.get(bearer, -20.0)
    per1 = per_from_snr(snr_use)
    secondary = pick_secondary(bearer, snr_table, controls["dc_snr_delta"]) if controls["enable_dc"] else None
    per2 = per_from_snr(snr_table.get(secondary, -20.0)) if secondary else None
    laneA_phy = (
        1 - (1 - (1 - per1) ** controls["laneA_reps"]) * (1 - (1 - per2) ** controls["laneA_reps"])
        if secondary
        else (1 - per1) ** controls["laneA_reps"]
    )

    _, _, quality = nearest_bs_quality(*trainA)
    cap_bps, rand_loss = cap_loss(quality, t)
    in_gap = t < st.session_state.ho_gap_until

    sidx = np.linspace(0, len(route_df) - 1, N_SENS).astype(int)
    s_lats = tuple(float(route_df.lat.iloc[j]) for j in sidx)
    s_lons = tuple(float(route_df.lon.iloc[j]) for j in sidx)
    sensors_base = pd.DataFrame([{"sid": f"S{i:02d}", "lat": s_lats[i], "lon": s_lons[i]} for i in range(N_SENS)])

    ss = sensor_static(secs, s_lats, s_lons)
    if ss is None:
        ss = dict(qualS=["GOOD"] * N_SENS, capS0=[int(800000 * 1.4)] * N_SENS, seg=[SEG_NAMES[0]] * N_SENS)

    thermal_sensor_idx = (thermal.get("sequence_pos", t) * 7) % N_SENS if thermal.get("available") else -1
    rows = [
        _sensor_row(
            t,
            row,
            ss["qualS"][i],
            ss["capS0"][i],
            ss["seg"][i],
            controls["demo_issues"],
            controls["summer_sev"],
            thermal,
            max(0.0, 1.0 - abs(i - thermal_sensor_idx) / 3.0) if thermal_sensor_idx >= 0 else 0.0,
        )
        for i, row in enumerate(sensors_base.itertuples())
    ]
    sensors = pd.concat([sensors_base, pd.DataFrame(rows)], axis=1)
    if thermal.get("available"):
        sensors["thermal_driver"] = sensors.index == thermal_sensor_idx
        semantic_sensor = sensors.iloc[thermal_sensor_idx]
        thermal["semantic_event"] = semantic_event_from_stats(thermal, sensor_id=str(semantic_sensor.sid))
        thermal["semantic_payload_bytes"] = len(json.dumps(thermal["semantic_event"], separators=(",", ":")).encode("utf-8"))
        thermal["hybrid_payload_bytes"] = int(thermal["semantic_payload_bytes"] + thermal["payload_bytes"] * 0.12)
    else:
        sensors["thermal_driver"] = False
    sensors["modality"] = sensors.apply(_choose_modality, axis=1)
    sensors["raw_hz"] = sensors["modality"].map(RAW_HZ).fillna(0.0)
    sensors["raw_bps"] = sensors["raw_hz"] * BYTES_RAW * (1.0 - sensors["lossS"])
    raw_bps_delivered = int(sensors["raw_bps"].sum())

    rng_a = np.random.default_rng(42 + t)
    laneA_alerts = []
    for row in sensors.itertuples():
        if row.label in ("medium", "high") and row.exceeded:
            conf = round(0.6 + 0.4 * row.score, 2)
            if rng_a.uniform() < (1.0 - row.lossS):
                laneA_alerts.append(
                    dict(
                        sid=row.sid,
                        lat=row.lat,
                        lon=row.lon,
                        severity=row.label,
                        confidence=conf,
                        temp=row.temp,
                        strain=row.strain,
                        ballast=row.ballast,
                    )
                )

    laneB_msgs = []
    if controls["mode"] in ("SEMANTIC", "HYBRID") and sensors["modality"].isin(["SEMANTIC", "HYBRID"]).any():
        laneB_msgs.append({"bhs": int((sensors.ballast > 0.6).sum()), "alerts": len(laneA_alerts)})

    real_keys = _tsr_key_set(st.session_state.tsr_real)
    for a in laneA_alerts:
        _apply_tsr_from_alert(a, controls, t, real_keys)

    if controls["demo_issues"] and controls["always_tsr"]:
        latv = sensors["lat"].values
        lonv = sensors["lon"].values
        for h in HOTSPOTS:
            d = haversine_vec(latv, lonv, h["lat"], h["lon"])
            in_h = d <= h["radius_m"]
            if in_h.any():
                top = sensors.loc[in_h].sort_values("score", ascending=False).iloc[0]
                poly = tsr_poly(float(top.lat), float(top.lon))
                entry = dict(
                    polygon=poly,
                    speed=controls["tsr_speed"],
                    created_idx=t,
                    critical=True,
                    stop=(float(top.score) > 0.92),
                )
                if _poly_key(poly) not in real_keys:
                    st.session_state.tsr_real.append(entry)
                    real_keys.add(_poly_key(poly))

    if len(st.session_state.tsr_real) > TSR_CAP:
        st.session_state.tsr_real = st.session_state.tsr_real[-TSR_CAP:]

    thermal_bps = _thermal_payload_bps(thermal, controls["mode"])
    projected_bps = len(laneA_alerts) * BYTES_ALERT + len(laneB_msgs) * BYTES_SUMM + raw_bps_delivered + thermal_bps
    projected_load = projected_bps / max(cap_bps, 1)
    loss_down = min(0.95, rand_loss + (0.3 if in_gap else 0.0))
    loss_down = min(0.97, loss_down + max(0.0, projected_load - 1.0) * 0.12)
    thermal_delivery_loss = _thermal_delivery_loss(loss_down, controls["mode"])
    thermal_event_delivered = False
    thermal_alert = None
    if thermal.get("available") and thermal.get("semantic_event", {}).get("risk_label") in ("medium", "high"):
        thermal_event_delivered = _thermal_event_delivered(thermal_delivery_loss, controls["mode"], thermal["frame_id"])
        if thermal_event_delivered:
            event = thermal["semantic_event"]
            thermal_row = sensors.loc[sensors["thermal_driver"]].iloc[0]
            thermal_alert = dict(
                sid=event["sensor_id"],
                lat=float(thermal_row.lat),
                lon=float(thermal_row.lon),
                severity=event["risk_label"],
                confidence=float(event["confidence"]),
                temp=float(thermal_row.temp),
                strain=float(thermal_row.strain),
                ballast=float(thermal_row.ballast),
            )
            laneA_alerts.append(thermal_alert)
            laneB_msgs.append({"thermal_event": event["event_type"], "action": event["recommended_action"]})
            _apply_tsr_from_alert(thermal_alert, controls, t, real_keys)
    if thermal.get("available"):
        thermal["delivery_loss"] = thermal_delivery_loss
        thermal["delivered_to_tms"] = thermal_event_delivered
        thermal["triggered_alert"] = thermal_alert is not None
        thermal["mode_comparison"] = _thermal_mode_comparison(thermal, loss_down, cap_bps)

    laneA_bps = len(laneA_alerts) * BYTES_ALERT * (2 if (controls["enable_dc"] and secondary) else 1)
    laneB_bps = len(laneB_msgs) * BYTES_SUMM
    bps_total = laneA_bps + laneB_bps + raw_bps_delivered + thermal_bps

    tms_keys = _tsr_key_set(st.session_state.tsr_tms)
    if np.random.random() > loss_down:
        for p in st.session_state.tsr_real:
            pk = _poly_key(p["polygon"])
            if pk not in tms_keys:
                st.session_state.tsr_tms.append(p)
                tms_keys.add(pk)
    if len(st.session_state.tsr_tms) > TSR_CAP:
        st.session_state.tsr_tms = st.session_state.tsr_tms[-TSR_CAP:]

    enforce_stop = any(p.get("stop") for p in st.session_state.tsr_tms)
    crash = any(
        p["critical"] and _poly_key(p["polygon"]) not in tms_keys and point_in_bbox(trainA[0], trainA[1], p["polygon"])
        for p in st.session_state.tsr_real
    )
    tsr_here = min(
        (p["speed"] for p in st.session_state.tsr_tms if point_in_bbox(trainA[0], trainA[1], p["polygon"])),
        default=None,
    )
    v_target = 0.0 if enforce_stop else (tsr_here / 3.6 if tsr_here else V_MAX_MS)

    v_cur = st.session_state.train_v_ms
    v_new = min(v_cur + A_MAX, v_target) if v_target >= v_cur else max(v_cur - B_MAX, v_target)
    st.session_state.train_v_ms = v_new
    st.session_state.train_s_m = train_s_m
    if st.session_state.t_idx >= secs - 1:
        st.session_state.playing = False

    cap_safe = max(cap_bps, 1)
    lat_ms = TECH[tk]["base_lat"] + bps_total / 1000
    if bps_total > cap_safe:
        lat_ms *= min(4.0, 1 + 0.35 * (bps_total / cap_safe - 1))
    if in_gap:
        lat_ms += 80
    laneA_success = laneA_phy
    if in_gap and not secondary:
        laneA_success = max(0.0, laneA_success * 0.85)

    for a in laneA_alerts[:4]:
        st.session_state.alerts_feed.append(
            dict(t=t, sid=a["sid"], severity=a["severity"], conf=int(a["confidence"] * 100), temp=a["temp"], strain=a["strain"])
        )
    st.session_state.alerts_feed = st.session_state.alerts_feed[-8:]

    if "_times" not in st.session_state:
        st.session_state._times = np.full(secs, np.nan)
        st.session_state.arr = {k: np.full(secs, np.nan) for k in ["raw", "laneA", "laneB", "cap", "snr", "succ", "lat_ms", "speed"]}
    if math.isnan(st.session_state._times[t]):
        st.session_state._times[t] = t
        arr = st.session_state.arr
        arr["raw"][t] = raw_bps_delivered
        arr["laneA"][t] = laneA_bps
        arr["laneB"][t] = laneB_bps
        arr["cap"][t] = cap_bps
        arr["snr"][t] = snr_use
        arr["succ"][t] = laneA_success * 100
        arr["lat_ms"][t] = lat_ms
        arr["speed"][t] = v_new * 3.6

    return {
        "t": t,
        "seg": seg,
        "trainA": trainA,
        "quality": quality,
        "bearer": bearer,
        "secondary": secondary,
        "snr_use": snr_use,
        "cap_bps": cap_bps,
        "bps_total": bps_total,
        "lat_ms": lat_ms,
        "laneA_success": laneA_success,
        "laneA_bps": laneA_bps,
        "laneB_bps": laneB_bps,
        "raw_bps_delivered": raw_bps_delivered,
        "thermal_bps": thermal_bps,
        "enforce_stop": enforce_stop,
        "crash": crash,
        "tsr_here": tsr_here,
        "speed_kmh": v_new * 3.6,
        "sensors": sensors,
        "s_lats": s_lats,
        "s_lons": s_lons,
        "in_gap": in_gap,
        "thermal": thermal,
    }
