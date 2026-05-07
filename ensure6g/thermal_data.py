from pathlib import Path
import json
import re

import numpy as np
import streamlit as st


THERMAL_ROOT = Path(__file__).resolve().parents[2] / "ThermalData"
P2PRO_DIR = THERMAL_ROOT / "p2pro"
P2PRO_PIC_DIR = THERMAL_ROOT / "p2proPic"
P2PRO_SOURCE = "Collected P2 Pro"
SYNTHETIC_SOURCE = "Synthetic"
SEMANTIC_BYTES_FALLBACK = 0
DEMO_EVENT_TICK = 211

_FRAME_RE = re.compile(r"(\d+)$")


def _frame_number(path):
    match = _FRAME_RE.search(path.stem)
    return int(match.group(1)) if match else -1


@st.cache_data(show_spinner=False)
def list_p2pro_frames(root_dir=None):
    frame_dir = Path(root_dir) if root_dir else P2PRO_DIR
    if not frame_dir.exists():
        return []
    return [str(path) for path in sorted(frame_dir.glob("*.npy"), key=_frame_number)]


def p2pro_data_available(root_dir=None):
    return bool(list_p2pro_frames(root_dir))


def resolve_thermal_source(source, root_dir=None):
    if source == P2PRO_SOURCE and not p2pro_data_available(root_dir):
        return SYNTHETIC_SOURCE
    return source


def p2pro_preview_path(frame_path, preview_dir=None):
    path = Path(frame_path)
    pic_dir = Path(preview_dir) if preview_dir else path.parent.parent / "p2proPic"
    preview = pic_dir / f"{path.stem}.png"
    return str(preview) if preview.exists() else None


@st.cache_data(show_spinner=False)
def thermal_frame_stats(frame_path):
    path = Path(frame_path)
    raw = np.load(path)
    temp_c = raw / 64.0 - 273.2
    hotspot_flat_idx = int(np.nanargmax(temp_c))
    hotspot_y, hotspot_x = np.unravel_index(hotspot_flat_idx, temp_c.shape)
    mean_temp = float(np.nanmean(temp_c))
    p95_temp = float(np.nanpercentile(temp_c, 95))
    p99_temp = float(np.nanpercentile(temp_c, 99))
    delta_temp = p99_temp - mean_temp

    stats = {
        "available": True,
        "source": P2PRO_SOURCE,
        "frame_path": str(path),
        "preview_path": p2pro_preview_path(path),
        "frame_id": _frame_number(path),
        "frame_name": path.name,
        "shape": tuple(int(v) for v in temp_c.shape),
        "payload_bytes": int(raw.nbytes),
        "mean_temp_c": mean_temp,
        "p95_temp_c": p95_temp,
        "p99_temp_c": p99_temp,
        "max_temp_c": float(np.nanmax(temp_c)),
        "delta_temp_c": delta_temp,
        "hotspot_x": int(hotspot_x),
        "hotspot_y": int(hotspot_y),
        "risk_label": risk_label(mean_temp, p99_temp, delta_temp),
    }
    event = semantic_event_from_stats(stats)
    stats["semantic_event"] = event
    stats["semantic_payload_bytes"] = len(json.dumps(event, separators=(",", ":")).encode("utf-8"))
    stats["hybrid_payload_bytes"] = int(stats["semantic_payload_bytes"] + stats["payload_bytes"] * 0.12)
    return stats


@st.cache_data(show_spinner=False)
def thermal_frame_celsius(frame_path):
    raw = np.load(frame_path)
    return raw / 64.0 - 273.2


def risk_label(mean_temp_c, p99_temp_c, delta_temp_c):
    if p99_temp_c >= 36 or delta_temp_c >= 5:
        return "high"
    if p99_temp_c >= 33 or delta_temp_c >= 2.5:
        return "medium"
    return "low"


def confidence_from_stats(p99_temp_c, delta_temp_c):
    thermal_strength = max(0.0, (p99_temp_c - 31.0) / 7.0)
    anomaly_strength = max(0.0, delta_temp_c / 5.0)
    return round(float(min(0.96, 0.45 + 0.35 * thermal_strength + 0.20 * anomaly_strength)), 2)


def recommended_action(risk):
    if risk == "high":
        return "issue_tsr"
    if risk == "medium":
        return "increase_monitoring"
    return "monitor"


def semantic_event_from_stats(stats, sensor_id=None):
    risk = stats["risk_label"]
    return {
        "sensor_id": sensor_id or "thermal-camera",
        "frame_id": stats["frame_id"],
        "event_type": "thermal_hotspot" if risk != "low" else "thermal_nominal",
        "mean_temp_c": round(stats["mean_temp_c"], 1),
        "p99_temp_c": round(stats["p99_temp_c"], 1),
        "delta_temp_c": round(stats["delta_temp_c"], 1),
        "risk_label": risk,
        "confidence": confidence_from_stats(stats["p99_temp_c"], stats["delta_temp_c"]),
        "recommended_action": recommended_action(risk),
    }


def current_thermal_stats(source, tick, root_dir=None):
    if source != P2PRO_SOURCE:
        return {
            "available": False,
            "source": SYNTHETIC_SOURCE,
            "requested_source": source,
            "fallback_active": source == P2PRO_SOURCE,
        }

    frames = list_p2pro_frames(root_dir)
    if not frames:
        return {
            "available": False,
            "source": P2PRO_SOURCE,
            "requested_source": source,
            "fallback_active": True,
            "error": f"No P2 Pro .npy files found in {P2PRO_DIR}",
        }

    frame_path = frames[int(tick) % len(frames)]
    stats = thermal_frame_stats(frame_path)
    stats["frame_count"] = len(frames)
    stats["sequence_pos"] = int(tick) % len(frames)
    return stats
