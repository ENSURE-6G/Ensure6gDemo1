import streamlit as st

from ensure6g.core import ShadowingTrack
from ensure6g.theme import PAL
from ensure6g.thermal_data import (
    DEMO_EVENT_TICK,
    P2PRO_DIR,
    P2PRO_SOURCE,
    SYNTHETIC_SOURCE,
    p2pro_data_available,
    resolve_thermal_source,
)


PRESET_VALUES = {
    "Baseline": dict(scenario="Good signal", mode="RAW", thermal_source=P2PRO_SOURCE, tsr_conf=0.85, stop_on_crit=True),
    "Network Stress": dict(scenario="Adverse", mode="RAW", thermal_source=P2PRO_SOURCE, tsr_conf=0.70, stop_on_crit=True),
    "Semantic Safety": dict(scenario="Adverse", mode="SEMANTIC", thermal_source=P2PRO_SOURCE, tsr_conf=0.70, stop_on_crit=True),
}


def _set_timeline_idx(idx):
    st.session_state.t_idx = int(idx)
    st.session_state.timeline_nonce = st.session_state.get("timeline_nonce", 0) + 1


def apply_demo_preset(name):
    preset = PRESET_VALUES[name]
    thermal_source = resolve_thermal_source(preset["thermal_source"])
    st.session_state.demo_preset = name
    st.session_state.scenario_preset = preset["scenario"]
    st.session_state.uplink_mode = preset["mode"]
    st.session_state.thermal_source = thermal_source
    st.session_state.tsr_conf = preset["tsr_conf"]
    st.session_state.stop_on_crit = preset["stop_on_crit"]
    _set_timeline_idx(DEMO_EVENT_TICK)
    st.session_state.train_v_ms = 0.0
    st.session_state.playing = False


def jump_to_event_frame():
    _set_timeline_idx(DEMO_EVENT_TICK)
    st.session_state.train_v_ms = 0.0
    st.session_state.playing = False


def step_timeline(delta, max_idx):
    _set_timeline_idx(min(max_idx, max(0, st.session_state.t_idx + delta)))
    st.session_state.train_v_ms = 0.0
    st.session_state.playing = False


def reset_sim():
    for k in [
        "arr",
        "_times",
        "tsr_real",
        "tsr_tms",
        "work_orders",
        "alerts_feed",
        "sensor_static_cache",
    ]:
        st.session_state.pop(k, None)
    for k, v in [
        ("t_idx", 0),
        ("train_s_m", 0.0),
        ("train_v_ms", 0.0),
        ("bearer", "5G"),
        ("bearer_prev", "5G"),
        ("bearer_ttt", 0),
        ("ho_gap_until", -1),
    ]:
        st.session_state[k] = v
    st.session_state.timeline_nonce = st.session_state.get("timeline_nonce", 0) + 1


def init_session_state():
    for k, v in [
        ("t_idx", 0),
        ("timeline_nonce", 0),
        ("playing", False),
        ("train_s_m", 0.0),
        ("train_v_ms", 0.0),
        ("bearer", "5G"),
        ("bearer_prev", "5G"),
        ("bearer_ttt", 0),
        ("ho_gap_until", -1),
        ("tsr_real", []),
        ("tsr_tms", []),
        ("work_orders", []),
        ("alerts_feed", []),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v
    if "shadow" not in st.session_state:
        st.session_state.shadow = ShadowingTrack()
    for k, v in [
        ("scenario_preset", "Good signal"),
        ("uplink_mode", "SEMANTIC"),
        ("thermal_source", P2PRO_SOURCE),
        ("tsr_conf", 0.85),
        ("stop_on_crit", True),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v


def render_sidebar():
    with st.sidebar:
        st.markdown(
            f"<div style='font-family:IBM Plex Mono;font-size:16px;font-weight:600;"
            f"color:{PAL['cyan']};padding:8px 0 4px;letter-spacing:.05em;'>"
            f"⬡ ENSURE-6G</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-family:IBM Plex Mono;font-size:10px;"
            f"color:{PAL['muted']};padding-bottom:12px;'>"
            f"Rail TMS • Sundsvall → Stockholm</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        active_chapter = st.session_state.get("demo_preset", "Manual")
        event_ready = abs(int(st.session_state.get("t_idx", 0)) - DEMO_EVENT_TICK) <= 2
        tms_ready = (
            st.session_state.get("scenario_preset") == "Adverse"
            and st.session_state.get("uplink_mode") == "SEMANTIC"
            and event_ready
        )
        st.markdown("<div class='sec-hdr'>Presenter Remote</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
<div class="sidebar-status">
  <div><span>Chapter</span><b>{active_chapter}</b></div>
  <div><span>Mode</span><b>{st.session_state.get('uplink_mode', 'SEMANTIC')}</b></div>
  <div><span>Event Frame</span><b>{'READY' if event_ready else 'OFF'}</b></div>
  <div><span>TMS Action</span><b>{'READY' if tms_ready else 'PENDING'}</b></div>
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='sec-hdr'>Story Chapters</div>", unsafe_allow_html=True)
        st.button("1 Baseline - RAW Image/Data", width="stretch", on_click=apply_demo_preset, args=("Baseline",))
        st.button("2 Stress - RAW Under Load", width="stretch", on_click=apply_demo_preset, args=("Network Stress",))
        st.button("3 Semantic Safety - Meaning + Action", width="stretch", on_click=apply_demo_preset, args=("Semantic Safety",))

        st.button("Go to Event Frame 330", width="stretch", on_click=jump_to_event_frame)
        st.markdown(
            "<div class='sidebar-hint'>Frame 330: high thermal risk semantic event used for the scripted TMS action.</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='sec-hdr'>Operator Controls</div>", unsafe_allow_html=True)
        scenario_options = ["Good signal", "Mixed", "Adverse"]
        preset = st.selectbox(
            "Network condition",
            scenario_options,
            key="scenario_preset",
        )
        if preset == "Good signal":
            def_min, def_TTT, def_HO, def_dc = 20, 1000, 200, True
        elif preset == "Mixed":
            def_min, def_TTT, def_HO, def_dc = 20, 1200, 350, True
        else:
            def_min, def_TTT, def_HO, def_dc = 20, 1600, 600, False

        sim_minutes = st.number_input("Duration (min)", 5, 120, def_min, 5)
        mode_options = ["RAW", "HYBRID", "SEMANTIC"]
        mode = st.radio("Transfer mode", mode_options, key="uplink_mode", horizontal=True)

        st.markdown("<div class='sec-hdr'>Thermal Input</div>", unsafe_allow_html=True)
        has_p2pro_data = p2pro_data_available()
        if not has_p2pro_data and st.session_state.get("thermal_source") == P2PRO_SOURCE:
            st.session_state.thermal_source = SYNTHETIC_SOURCE

        source_options = [P2PRO_SOURCE, SYNTHETIC_SOURCE] if has_p2pro_data else [SYNTHETIC_SOURCE]
        thermal_source = st.selectbox("Source", source_options, key="thermal_source")
        if not has_p2pro_data:
            st.markdown(
                f"<div class='s-warn'>Collected thermal data not found at {P2PRO_DIR}. "
                "Using synthetic fallback.</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div class='sec-hdr'>Safety</div>", unsafe_allow_html=True)
        tsr_conf = st.slider("Action threshold", 0.60, 0.95, 0.85, 0.01, key="tsr_conf")
        tsr_speed = st.slider("TSR speed (km/h)", 30, 120, 60, 5)
        stop_on_crit = st.checkbox("STOP at conf >= 0.92", key="stop_on_crit")

        with st.expander("Advanced controls", expanded=False):
            st.markdown("<div class='sec-hdr'>Radio / PHY</div>", unsafe_allow_html=True)
            laneA_reps = st.slider("Lane-A repetitions", 1, 3, 2)
            enable_dc = st.checkbox("Dual Connectivity", def_dc)
            dc_snr_delta = st.slider("DC min dSNR (dB)", 0.0, 10.0, 2.0, 0.5)
            TTT_MS = st.slider("Time-To-Trigger (ms)", 200, 3000, def_TTT, 100)
            HO_GAP_MS = st.slider("HO outage (ms)", 0, 1500, def_HO, 50)
            st.markdown("<div class='sec-hdr'>Synthetic Fallback</div>", unsafe_allow_html=True)
            demo_issues = st.checkbox("Inject summer hotspots", True)
            summer_sev = st.slider("Severity boost (C)", 0.0, 20.0, 12.0, 1.0)
            always_tsr = st.checkbox("Always show TSR zones", True)

        st.markdown("---")
        st.markdown("<div class='sec-hdr'>Playback</div>", unsafe_allow_html=True)
        if st.button("Enable Simulation", width="stretch"):
            st.session_state.playing = True
        ca, cb = st.columns(2)
        max_idx = max(1, int(sim_minutes * 60) - 1)
        ca.button("Step -10", width="stretch", on_click=step_timeline, args=(-10, max_idx))
        cb.button("Step +10", width="stretch", on_click=step_timeline, args=(10, max_idx))
        play_rate = st.selectbox("Playback rate", ["1×", "2×", "4×", "0.5×"])
        r1, r2 = st.columns(2)
        if r1.button("Play", width="stretch"):
            st.session_state.playing = True
        if r2.button("Pause", width="stretch"):
            st.session_state.playing = False
        if st.button("Reset", width="stretch"):
            st.session_state.playing = False
            reset_sim()
            st.rerun()

    return {
        "sim_minutes": sim_minutes,
        "mode": mode,
        "thermal_source": thermal_source,
        "laneA_reps": laneA_reps,
        "enable_dc": enable_dc,
        "dc_snr_delta": dc_snr_delta,
        "TTT_MS": TTT_MS,
        "HO_GAP_MS": HO_GAP_MS,
        "tsr_conf": tsr_conf,
        "tsr_speed": tsr_speed,
        "stop_on_crit": stop_on_crit,
        "demo_issues": demo_issues,
        "summer_sev": summer_sev,
        "always_tsr": always_tsr,
        "play_rate": play_rate,
    }
