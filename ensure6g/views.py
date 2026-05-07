import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from ensure6g.core import build_heat_index, build_layers_cached
from ensure6g.core import _poly_key, _tsr_key_set
from ensure6g.theme import C, CHART_COLORS, CHART_LAYOUT, PAL
from ensure6g.thermal_data import DEMO_EVENT_TICK, thermal_frame_celsius


def _series(arr, key):
    return [None if (isinstance(v, float) and math.isnan(v)) else v for v in arr[key]]


def _render_thermal_panel(thermal):
    if not thermal:
        return
    if not thermal.get("available"):
        msg = thermal.get("error", f"Thermal source: {thermal.get('source', 'Synthetic')}")
        st.markdown(
            f"<div class='s-warn' style='margin:4px 0 12px'>{msg}</div>",
            unsafe_allow_html=True,
        )
        return

    risk_cls = {"low": "kv-green", "medium": "kv-amber", "high": "kv-red"}.get(thermal["risk_label"], "kv-cyan")
    delivery_label = "DELIVERED" if thermal.get("delivered_to_tms") else ("DROPPED" if thermal["risk_label"] != "low" else "NOMINAL")
    delivery_cls = "kv-green" if delivery_label in ("DELIVERED", "NOMINAL") else "kv-red"
    st.markdown(
        f"""
<div class="kpi-bar" style="margin-top:-4px">
  <div class="kpi"><span class="kpi-label">Thermal Source</span><span class="kpi-value kv-cyan">{thermal['source']}</span></div>
  <div class="kpi"><span class="kpi-label">Frame</span><span class="kpi-value kv-amber">{thermal['frame_id']}</span></div>
  <div class="kpi"><span class="kpi-label">Mean</span><span class="kpi-value kv-blue">{thermal['mean_temp_c']:.1f} C</span></div>
  <div class="kpi"><span class="kpi-label">P99</span><span class="kpi-value kv-purple">{thermal['p99_temp_c']:.1f} C</span></div>
  <div class="kpi"><span class="kpi-label">Delta</span><span class="kpi-value kv-cyan">{thermal['delta_temp_c']:.1f} C</span></div>
  <div class="kpi"><span class="kpi-label">Risk</span><span class="kpi-value {risk_cls}">{thermal['risk_label'].upper()}</span></div>
  <div class="kpi"><span class="kpi-label">Semantic Payload</span><span class="kpi-value kv-green">{thermal['semantic_payload_bytes']} B</span></div>
  <div class="kpi"><span class="kpi-label">TMS Delivery</span><span class="kpi-value {delivery_cls}">{delivery_label}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )


def _payload_rows(thermal):
    return pd.DataFrame(
        [
            {"Mode": "RAW", "Payload": f"{thermal['payload_bytes']:,} B", "Role": "Full thermal frame"},
            {"Mode": "HYBRID", "Payload": f"{thermal['hybrid_payload_bytes']:,} B", "Role": "Preview-scale payload plus event"},
            {"Mode": "SEMANTIC", "Payload": f"{thermal['semantic_payload_bytes']:,} B", "Role": "Event meaning only"},
        ]
    )


def _render_thermal_tab(frame):
    thermal = frame.get("thermal", {})
    if not thermal.get("available"):
        st.markdown("<div class='s-warn'>Collected thermal data is not available.</div>", unsafe_allow_html=True)
        return

    left, right = st.columns([2, 1], gap="medium")
    with left:
        st.markdown("<div class='sec-hdr'>P2 Pro Thermal Frame</div>", unsafe_allow_html=True)
        temp_c = thermal_frame_celsius(thermal["frame_path"])
        fig = go.Figure(
            go.Heatmap(
                z=temp_c,
                colorscale=[
                    [0, "#0D1117"],
                    [0.35, "#1F6FEB"],
                    [0.65, "#F0A500"],
                    [1, "#E05A5A"],
                ],
                colorbar=dict(title="C"),
            )
        )
        fig.add_scatter(
            x=[thermal["hotspot_x"]],
            y=[thermal["hotspot_y"]],
            mode="markers",
            marker=dict(size=10, color="#E6EDF3", symbol="x"),
            name="Hotspot",
        )
        heatmap_layout = {**CHART_LAYOUT, "yaxis": {**CHART_LAYOUT.get("yaxis", {}), "autorange": "reversed"}}
        fig.update_layout(height=440, **heatmap_layout)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with right:
        st.markdown("<div class='sec-hdr'>Frame Stats</div>", unsafe_allow_html=True)
        st.metric("Frame", thermal["frame_id"])
        st.metric("Mean", f"{thermal['mean_temp_c']:.1f} C")
        st.metric("P95", f"{thermal['p95_temp_c']:.1f} C")
        st.metric("P99", f"{thermal['p99_temp_c']:.1f} C")
        st.metric("Delta", f"{thermal['delta_temp_c']:.1f} C")
        st.metric("Risk", thermal["risk_label"].upper())


def _render_semantic_tab(frame):
    thermal = frame.get("thermal", {})
    if not thermal.get("available"):
        st.markdown("<div class='s-warn'>Semantic event extraction is using synthetic fallback.</div>", unsafe_allow_html=True)
        return

    left, right = st.columns([1, 1], gap="medium")
    event = thermal.get("semantic_event", {})
    with left:
        st.markdown("<div class='sec-hdr'>Semantic Event</div>", unsafe_allow_html=True)
        st.json(event, expanded=True)
        delivery = "Delivered to TMS" if thermal.get("delivered_to_tms") else "Not delivered"
        cls = "s-ok" if thermal.get("delivered_to_tms") or event.get("risk_label") == "low" else "s-crit"
        st.markdown(
            f"<div class='{cls}' style='margin-top:8px'>{delivery} | loss={thermal.get('delivery_loss', 0)*100:.0f}%</div>",
            unsafe_allow_html=True,
        )

    with right:
        st.markdown("<div class='sec-hdr'>Payload Strategy</div>", unsafe_allow_html=True)
        st.dataframe(_payload_rows(thermal), width="stretch", hide_index=True)
        raw = max(thermal["payload_bytes"], 1)
        semantic = max(thermal["semantic_payload_bytes"], 1)
        reduction = 100 * (1 - semantic / raw)
        st.metric("Payload reduction", f"{reduction:.1f}%")
        st.metric("Current thermal load", f"{frame['thermal_bps']:,} bps")
        st.metric("Recommended action", event.get("recommended_action", "monitor"))
        st.markdown("<div class='sec-hdr'>TMS Outcome</div>", unsafe_allow_html=True)
        if event.get("risk_label") == "low":
            st.markdown("<div class='s-ok'>No thermal intervention required.</div>", unsafe_allow_html=True)
        elif thermal.get("delivered_to_tms"):
            st.markdown("<div class='s-ok'>Event delivered. TMS can act on the semantic message.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='s-crit'>Event dropped. TMS may miss this thermal condition.</div>", unsafe_allow_html=True)


def _render_demo_tab(frame):
    thermal = frame.get("thermal", {})
    event = thermal.get("semantic_event", {}) if thermal.get("available") else {}
    current_mode = st.session_state.get("uplink_mode", "SEMANTIC")
    current_scenario = st.session_state.get("scenario_preset", "Good signal")
    near_event = abs(int(st.session_state.get("t_idx", 0)) - DEMO_EVENT_TICK) <= 2
    tms_action = event.get("recommended_action") == "issue_tsr" and thermal.get("delivered_to_tms")

    st.markdown("<div class='sec-hdr'>Presenter Script</div>", unsafe_allow_html=True)
    st.markdown(
        """
<div class="demo-card">
  <div class="demo-title">Goal</div>
  <div class="demo-copy">Show that collected thermal camera data can be compressed into a semantic event and still drive a TMS safety action when the network is degraded.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    steps = [
        {
            "name": "1. Baseline",
            "sidebar": "Click Baseline in the sidebar.",
            "talk": "Start with normal radio conditions and show the collected thermal frame plus raw payload cost.",
            "expect": "Thermal data is visible; TMS state is nominal or low-pressure.",
            "active": current_scenario == "Good signal" and current_mode == "RAW",
        },
        {
            "name": "2. Network Stress",
            "sidebar": "Click Stress in the sidebar.",
            "talk": "Move to adverse network conditions and explain that full-frame thermal payloads are more fragile under load.",
            "expect": "The same thermal event is harder to deliver reliably as raw data.",
            "active": current_scenario == "Adverse" and current_mode == "RAW",
        },
        {
            "name": "3. Semantic Safety",
            "sidebar": "Click Semantic in the sidebar.",
            "talk": "Switch to semantic communication: transmit event meaning instead of the full thermal frame.",
            "expect": "Frame 330 produces high risk, confidence about 0.86, and TMS action issue_tsr.",
            "active": current_scenario == "Adverse" and current_mode == "SEMANTIC",
        },
    ]
    cols = st.columns(3, gap="medium")
    for col, step in zip(cols, steps):
        state_cls = "s-ok" if step["active"] else "s-warn"
        state_label = "CURRENT" if step["active"] else "READY"
        with col:
            st.markdown(
                f"""
<div class="demo-card">
  <div class="demo-title">{step['name']}</div>
  <div class="{state_cls}" style="margin:6px 0">{state_label}</div>
  <div class="demo-copy"><b>Action:</b> {step['sidebar']}</div>
  <div class="demo-copy"><b>Say:</b> {step['talk']}</div>
  <div class="demo-copy"><b>Expected:</b> {step['expect']}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("<div class='sec-hdr'>Current Script Check</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scenario", current_scenario)
    c2.metric("Mode", current_mode)
    c3.metric("At event frame", "YES" if near_event else "NO")
    c4.metric("TMS action", "YES" if tms_action else "NO")

    if not thermal.get("available"):
        st.markdown(
            "<div class='s-warn'>Collected thermal data is unavailable, so this run is using the synthetic fallback. "
            "The scripted semantic proof point requires the P2 Pro dataset.</div>",
            unsafe_allow_html=True,
        )
        return

    risk_cls = "s-ok" if event.get("risk_label") == "high" else "s-warn"
    delivery_cls = "s-ok" if thermal.get("delivered_to_tms") else "s-crit"
    action_cls = "s-ok" if tms_action else "s-warn"
    st.markdown(
        f"""
<div class="demo-check-grid">
  <div class="{risk_cls}">Thermal risk: {event.get('risk_label', 'unknown').upper()} | frame {thermal.get('frame_id')}</div>
  <div class="{delivery_cls}">Semantic delivery: {'DELIVERED' if thermal.get('delivered_to_tms') else 'NOT DELIVERED'} | loss {thermal.get('delivery_loss', 0)*100:.0f}%</div>
  <div class="{action_cls}">Recommended action: {event.get('recommended_action', 'monitor')}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_header_and_timeline(frame, secs, route_df=None):
    q_cls = {"GOOD": "kv-green", "PATCHY": "kv-amber", "POOR": "kv-red"}[frame["quality"]]
    st_cls = "kv-red" if frame["enforce_stop"] else ("kv-amber" if frame["crash"] else "kv-green")
    st_lbl = "🛑 STOP" if frame["enforce_stop"] else ("⚠ RISK" if frame["crash"] else "NOMINAL")
    spd_cls = "kv-amber" if (frame["tsr_here"] and frame["speed_kmh"] > frame["tsr_here"]) else "kv-cyan"

    st.markdown(
        f"""
<div class="kpi-bar">
  <div class="kpi"><span class="kpi-label">Status</span><span class="kpi-value {st_cls}">{st_lbl}</span></div>
  <div class="kpi"><span class="kpi-label">Coverage</span><span class="kpi-value {q_cls}">{frame['quality']}</span></div>
  <div class="kpi"><span class="kpi-label">Bearer</span><span class="kpi-value kv-blue">{frame['bearer']}</span></div>
  <div class="kpi"><span class="kpi-label">Speed</span><span class="kpi-value {spd_cls}">{frame['speed_kmh']:.0f} km/h</span></div>
  <div class="kpi"><span class="kpi-label">Latency</span><span class="kpi-value kv-cyan">{int(frame['lat_ms'])} ms</span></div>
  <div class="kpi"><span class="kpi-label">Lane-A</span><span class="kpi-value kv-green">{frame['laneA_success']*100:.0f}%</span></div>
  <div class="kpi"><span class="kpi-label">Capacity</span><span class="kpi-value kv-purple">{frame['cap_bps']//1000:,} kbps</span></div>
  <div class="kpi"><span class="kpi-label">Segment</span><span class="kpi-value" style="font-size:10px;color:#8B949E">{frame['seg']}</span></div>
  <div class="kpi"><span class="kpi-label">Time</span><span class="kpi-value kv-amber">{frame['t']}s / {secs}s</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    pct = int(frame["t"] / max(secs - 1, 1) * 100)
    st.markdown(
        f'<div class="prog-wrap"><div class="prog-fill" style="width:{pct}%"></div></div>',
        unsafe_allow_html=True,
    )
    _render_thermal_panel(frame.get("thermal"))

    if st.session_state.playing:
        st.slider("t", 0, secs - 1, frame["t"], disabled=True, label_visibility="collapsed")
    else:
        new_t = st.slider("t", 0, secs - 1, frame["t"], label_visibility="collapsed")
        if new_t != frame["t"]:
            st.session_state.t_idx = new_t
            if route_df is not None:
                st.session_state.train_s_m = float(route_df.s_m.iloc[new_t])
                st.session_state.train_v_ms = 0.0


def render_tabs(frame, route_df, secs):
    arr = st.session_state.arr
    x = np.arange(secs)
    tab_demo, tab_thermal, tab_semantic, tab_map, tab_tele, tab_flow, tab_ops = st.tabs(
        ["Demo", "Thermal", "Semantic", "Maps", "Telemetry", "Network", "TMS"]
    )

    with tab_demo:
        _render_demo_tab(frame)

    with tab_thermal:
        _render_thermal_tab(frame)

    with tab_semantic:
        _render_semantic_tab(frame)

    with tab_map:
        map_col, side_col = st.columns([3, 1], gap="medium")

        with side_col:
            st.markdown("<div class='sec-hdr'>Legend</div>", unsafe_allow_html=True)
            legend_items = [
                ("#3DD68C", "GOOD coverage"),
                ("#F0A500", "PATCHY coverage"),
                ("#E05A5A", "POOR coverage"),
                ("#58A6FF", "Sensor RAW"),
                ("#39D0D8", "Sensor HYBRID"),
                ("#B388FF", "Sensor SEMANTIC"),
                ("#F0B914", "TSR zone"),
                ("#58A6FF", "Base station"),
            ]
            html = "".join(
                f'<div class="legend-item"><div class="dot" style="background:{c}"></div>{l}</div>' for c, l in legend_items
            )
            st.markdown(f'<div class="legend">{html}</div>', unsafe_allow_html=True)

            st.markdown("<div class='sec-hdr'>Lane-A Alerts</div>", unsafe_allow_html=True)
            if st.session_state.alerts_feed:
                for a in reversed(st.session_state.alerts_feed[-5:]):
                    cls = "high" if a["severity"] == "high" else ""
                    st.markdown(
                        f'<div class="alert-row {cls}">t={a["t"]}s &nbsp;{a["sid"]}<br>'
                        f'{a["severity"].upper()} conf={a["conf"]}%<br>'
                        f'T={a["temp"]}°C &nbsp;S={a["strain"]} kN</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    f"<div style='font-family:IBM Plex Mono;font-size:11px;color:{PAL['muted']}'>No alerts yet.</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("<div class='sec-hdr'>Sensor Risks</div>", unsafe_allow_html=True)
            sensors = frame["sensors"]
            aff = sensors[sensors["label"] != "low"][["sid", "label", "score", "qualS", "modality", "temp"]].copy()
            if aff.empty:
                st.markdown(
                    f"<div style='font-family:IBM Plex Mono;font-size:11px;color:{PAL['muted']}'>All nominal.</div>",
                    unsafe_allow_html=True,
                )
            else:
                aff = aff.sort_values("score", ascending=False)
                aff["score"] = (aff["score"] * 100).round(0).astype(int).astype(str) + "%"
                aff.columns = ["ID", "Risk", "Score", "Link", "Mode", "T°C"]
                st.dataframe(aff, width="stretch", height=190, hide_index=True)

            if st.session_state.tsr_real:
                n_r = len(st.session_state.tsr_real)
                n_t = len(st.session_state.tsr_tms)
                diff = n_r - n_t
                cls = "s-crit" if diff > 0 else "s-ok"
                msg = f"⚠ {diff} TSR(s) unknown to TMS" if diff > 0 else f"✓ TMS aware of all {n_r} TSR(s)"
                st.markdown(f'<div class="{cls}" style="margin-top:10px">{msg}</div>', unsafe_allow_html=True)
            if frame["enforce_stop"]:
                st.markdown('<div class="s-crit" style="margin-top:6px">🛑 STOP ORDER ACTIVE</div>', unsafe_allow_html=True)

            thermal = frame.get("thermal", {})
            if thermal.get("available"):
                st.markdown("<div class='sec-hdr'>Semantic Event</div>", unsafe_allow_html=True)
                event = thermal.get("semantic_event", {})
                st.json(event, expanded=False)
                if thermal.get("risk_label") != "low":
                    cls = "s-ok" if thermal.get("delivered_to_tms") else "s-crit"
                    msg = "Semantic event reached TMS" if thermal.get("delivered_to_tms") else "Semantic event lost before TMS"
                    st.markdown(
                        f"<div class='{cls}' style='margin-top:8px'>{msg} | loss={thermal.get('delivery_loss', 0)*100:.0f}%</div>",
                        unsafe_allow_html=True,
                    )

        with map_col:
            step = max(1, secs // 400)
            path_coords_tuple = tuple((float(route_df.lon.iloc[i]), float(route_df.lat.iloc[i])) for i in range(0, secs, step))
            track_layer, bs_layer, rings_layer, path_coords = build_layers_cached(path_coords_tuple, secs)

            heat_j = build_heat_index(path_coords_tuple, frame["s_lats"], frame["s_lons"])
            lbls = frame["sensors"]["label"].values[heat_j]
            cmap = {"low": C["good"][:3] + [100], "medium": C["patchy"][:3] + [150], "high": C["poor"][:3] + [190]}
            heat_rows = []
            for i in range(len(path_coords) - 1):
                c = cmap.get(lbls[i], C["good"][:3] + [100])
                heat_rows.append({"path": [path_coords[i], path_coords[i + 1]], "cr": c[0], "cg": c[1], "cb": c[2], "ca": c[3]})
            heat_df = pd.DataFrame(heat_rows)
            heat_layer = pdk.Layer("PathLayer", data=heat_df, get_path="path", get_color="[cr,cg,cb,ca]", width_min_pixels=5, width_scale=3)

            def s_color(row):
                m = getattr(row, "modality", "RAW")
                if m == "RAW":
                    return C["raw"]
                if m == "HYBRID":
                    return C["hybrid"]
                if m == "SEMANTIC":
                    return C["semantic"]
                return {"GOOD": C["good"], "PATCHY": C["patchy"], "POOR": C["poor"]}.get(getattr(row, "qualS", "GOOD"), C["good"])

            sens_rows = []
            for row in frame["sensors"].itertuples():
                c = s_color(row)
                lbl = getattr(row, "label", "low")
                rad = 2200 if lbl == "high" else (1800 if lbl == "medium" else 1400)
                sens_rows.append(
                    {
                        "lat": float(row.lat),
                        "lon": float(row.lon),
                        "sid": row.sid,
                        "cr": c[0],
                        "cg": c[1],
                        "cb": c[2],
                        "ca": c[3],
                        "radius": rad,
                        "tooltip": f"{row.sid} | {lbl} | {getattr(row, 'qualS', '')} | {getattr(row, 'modality', '')}",
                    }
                )
            sens_df = pd.DataFrame(sens_rows)
            s_layer = pdk.Layer(
                "ScatterplotLayer",
                data=sens_df,
                get_position="[lon,lat]",
                get_fill_color="[cr,cg,cb,ca]",
                get_radius="radius",
                radius_min_pixels=4,
                radius_max_pixels=14,
                stroked=True,
                get_line_color=[255, 255, 255, 80],
                line_width_min_pixels=1,
                pickable=True,
            )
            txt_layer = pdk.Layer(
                "TextLayer",
                data=sens_df,
                get_position="[lon,lat]",
                get_text="sid",
                get_size=11,
                get_color=[220, 220, 220, 200],
                get_pixel_offset=[0, -18],
                size_units="pixels",
            )

            def make_tsr_layer(lst):
                if not lst:
                    return pdk.Layer("PolygonLayer", data=[], get_polygon="polygon", get_fill_color=[0, 0, 0, 0])
                return pdk.Layer(
                    "PolygonLayer",
                    data=[{"polygon":p["polygon"],"tooltip":f"TSR {p['speed']}km/h{'  🛑 STOP' if p.get('stop') else ''}"} for p in lst],
                    get_polygon="polygon",
                    get_fill_color=C["gold"],
                    get_line_color=C["gold_ln"],
                    stroked=True,
                    filled=True,
                    line_width_min_pixels=2,
                    pickable=True,
                )

            halo_c = {"GOOD": C["good"], "PATCHY": C["patchy"], "POOR": C["poor"]}.get(frame["quality"], C["good"])
            halo_df = pd.DataFrame([{"lat": frame["trainA"][0], "lon": frame["trainA"][1], "cr": halo_c[0], "cg": halo_c[1], "cb": halo_c[2], "ca": 55}])
            halo_l = pdk.Layer("ScatterplotLayer", data=halo_df, get_position="[lon,lat]", get_fill_color="[cr,cg,cb,ca]", get_radius=1600, radius_min_pixels=8, radius_max_pixels=22)
            train_df = pd.DataFrame(
                [
                    {
                        "lat": frame["trainA"][0],
                        "lon": frame["trainA"][1],
                        "icon": {"url": "https://img.icons8.com/emoji/96/railway-car.png", "width": 96, "height": 96, "anchorY": 96},
                    }
                ]
            )
            icon_l = pdk.Layer("IconLayer", data=train_df, get_position="[lon,lat]", get_icon="icon", get_size=4, size_scale=12)
            view = pdk.ViewState(latitude=60.7, longitude=17.5, zoom=6.2, pitch=0)
            MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json"
            TOOLTIP = {"html":"<b>{tooltip}</b>","style":{"background":"rgba(13,17,23,.92)","color":"#E6EDF3","font-family":"IBM Plex Mono","font-size":"11px","border-radius":"6px","padding":"6px 10px"}}

            def make_deck(tsr_list):
                return pdk.Deck(
                    layers=[rings_layer, track_layer, heat_layer, make_tsr_layer(tsr_list), bs_layer, halo_l, s_layer, txt_layer, icon_l],
                    initial_view_state=view,
                    map_style=MAP_STYLE,
                    tooltip=TOOLTIP,
                )

            rw_col, tms_col = st.columns(2, gap="small")
            with rw_col:
                st.markdown('<div class="map-lbl">⬤ Real World</div>', unsafe_allow_html=True)
                st.pydeck_chart(make_deck(st.session_state.tsr_real), use_container_width=True, height=500)
            with tms_col:
                st.markdown('<div class="map-lbl map-lbl-tms">⬤ TMS View</div>', unsafe_allow_html=True)
                st.pydeck_chart(make_deck(st.session_state.tsr_tms), use_container_width=True, height=500)

    with tab_tele:
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown("<div class='sec-hdr'>Throughput (bps)</div>", unsafe_allow_html=True)
            fig = go.Figure()
            for nm, key, col in [("RAW", "raw", CHART_COLORS[0]), ("Lane-A", "laneA", CHART_COLORS[1]), ("Lane-B", "laneB", CHART_COLORS[2]), ("Capacity", "cap", CHART_COLORS[3])]:
                fig.add_scatter(x=x, y=_series(arr, key), name=nm, mode="lines", line=dict(color=col, width=1.5))
            fig.add_vline(x=frame["t"], line_width=1, line_dash="dash", line_color="#8B949E")
            fig.update_layout(height=230, **CHART_LAYOUT)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with c2:
            st.markdown("<div class='sec-hdr'>Speed & Latency</div>", unsafe_allow_html=True)
            fig2 = go.Figure()
            fig2.add_scatter(x=x, y=_series(arr, "speed"), name="Speed (km/h)", mode="lines", line=dict(color=CHART_COLORS[0], width=1.5))
            fig2.add_scatter(x=x, y=_series(arr, "lat_ms"), name="Latency (ms)", mode="lines", line=dict(color=CHART_COLORS[1], width=1.5), yaxis="y2")
            fig2.add_vline(x=frame["t"], line_width=1, line_dash="dash", line_color="#8B949E")
            fig2.update_layout(height=230, yaxis2=dict(overlaying="y", side="right", gridcolor="#21262D", title="ms", color="#8B949E"), **CHART_LAYOUT)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        c3, c4 = st.columns(2, gap="medium")
        with c3:
            st.markdown("<div class='sec-hdr'>SNR & Lane-A Success</div>", unsafe_allow_html=True)
            fig3 = go.Figure()
            fig3.add_scatter(x=x, y=_series(arr, "snr"), name="SNR (dB)", mode="lines", line=dict(color=CHART_COLORS[4], width=1.5))
            fig3.add_scatter(x=x, y=_series(arr, "succ"), name="Lane-A (%)", mode="lines", line=dict(color=CHART_COLORS[2], width=1.5), yaxis="y2")
            fig3.add_vline(x=frame["t"], line_width=1, line_dash="dash", line_color="#8B949E")
            fig3.update_layout(height=230, yaxis2=dict(overlaying="y", side="right", gridcolor="#21262D", range=[0, 100], title="%", color="#8B949E"), **CHART_LAYOUT)
            st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

        with c4:
            st.markdown("<div class='sec-hdr'>Live KPIs</div>", unsafe_allow_html=True)
            mc1, mc2 = st.columns(2)
            mc1.metric("SNR", f"{frame['snr_use']:.1f} dB")
            mc2.metric("Bearer", frame["bearer"])
            mc1.metric("Capacity", f"{frame['cap_bps']//1000:,} kbps")
            mc2.metric("Load", f"{frame['bps_total']//1000:,} kbps")
            mc1.metric("Dual Conn.", "ON" if frame["secondary"] else "OFF")
            mc2.metric("HO Gap", "YES" if frame["in_gap"] else "NO")
            mc1.metric("TSR zones", str(len(st.session_state.tsr_real)))
            mc2.metric("Alerts", str(len(st.session_state.alerts_feed)))

    with tab_flow:
        st.markdown("<div class='sec-hdr'>Data Flow - Sensors -> BS -> TMS -> Train</div>", unsafe_allow_html=True)
        s_to_bs = max(1, frame["bps_total"])
        to_train = max(1, frame["laneA_bps"] + frame["laneB_bps"])
        to_maint = max(1, frame["laneB_bps"] or 100)
        nodes = ["Sensors", f"BS ({frame['bearer']})", "Core Net", "TMS", "Train DAS", "Maintenance"]
        ni = {n: i for i, n in enumerate(nodes)}
        node_colors = ["#3DD68C", "#58A6FF", "#39D0D8", "#F0A500", "#B388FF", "#E05A5A"]
        sankey = go.Sankey(
            node=dict(label=nodes, pad=22, thickness=16, color=node_colors, line=dict(color=PAL["border"], width=0.5)),
            link=dict(
                source=[ni["Sensors"], ni[f"BS ({frame['bearer']})"], ni["Core Net"], ni["TMS"], ni["TMS"]],
                target=[ni[f"BS ({frame['bearer']})"], ni["Core Net"], ni["TMS"], ni["Train DAS"], ni["Maintenance"]],
                value=[s_to_bs, s_to_bs, s_to_bs, to_train, to_maint],
                label=["uplink", "backhaul", "to TMS", "advisories/TSR", "work orders"],
                color=["rgba(57,208,216,.35)", "rgba(57,208,216,.28)", "rgba(57,208,216,.28)", "rgba(240,165,0,.35)", "rgba(61,214,140,.35)"],
            ),
        )
        fig_sk = go.Figure(sankey)
        fig_sk.update_layout(height=400, **CHART_LAYOUT)
        st.plotly_chart(fig_sk, use_container_width=True, config={"displayModeBar": False})
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("RAW bps", f"{frame['raw_bps_delivered']:,}")
        c2.metric("Lane-A bps", f"{frame['laneA_bps']:,}")
        c3.metric("Lane-B bps", f"{frame['laneB_bps']:,}")
        c4.metric("Thermal bps", f"{frame['thermal_bps']:,}")

        thermal = frame.get("thermal", {})
        if thermal.get("available"):
            st.markdown("<div class='sec-hdr'>Thermal Payload Comparison</div>", unsafe_allow_html=True)
            st.dataframe(_payload_rows(thermal), width="stretch", hide_index=True)
            c5, c6 = st.columns(2)
            c5.metric("Semantic delivery", "YES" if thermal.get("delivered_to_tms") else "NO")
            c6.metric("Thermal loss model", f"{thermal.get('delivery_loss', 0)*100:.0f}%")

    with tab_ops:
        st.markdown("<div class='sec-hdr'>Status</div>", unsafe_allow_html=True)
        if frame["enforce_stop"]:
            st.markdown('<div class="s-crit">🛑 STOP ORDER in effect (TMS view)</div>', unsafe_allow_html=True)
        tms_keys = _tsr_key_set(st.session_state.tsr_tms)
        unknown = [p for p in st.session_state.tsr_real if _poly_key(p["polygon"]) not in tms_keys]
        if unknown:
            st.markdown(f'<div class="s-warn">⚠ {len(unknown)} real TSR(s) not yet in TMS — potential missed alert</div>', unsafe_allow_html=True)
        if not frame["enforce_stop"] and not unknown:
            st.markdown('<div class="s-ok">✓ All clear — no unresolved discrepancies</div>', unsafe_allow_html=True)

        for w in st.session_state.work_orders:
            if w["status"] == "Dispatched" and frame["t"] >= w.get("eta_done_idx", 9e9):
                w["status"] = "Resolved"
        resolved = {_poly_key(w["polygon"]) for w in st.session_state.work_orders if w["status"] == "Resolved"}
        st.session_state.tsr_real = [p for p in st.session_state.tsr_real if _poly_key(p["polygon"]) not in resolved]
        st.session_state.tsr_tms = [p for p in st.session_state.tsr_tms if _poly_key(p["polygon"]) not in resolved]

        st.markdown("<div class='sec-hdr'>Work Orders</div>", unsafe_allow_html=True)
        if st.session_state.work_orders:
            rows = [dict(ID=f"WO-{i+1:03d}", Status=w["status"], Created=w.get("created_idx", "—"), ETA=w.get("eta_done_idx", "—")) for i, w in enumerate(st.session_state.work_orders)]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            st.markdown(f"<div style='font-family:IBM Plex Mono;font-size:12px;color:{PAL['muted']}'>No active work orders.</div>", unsafe_allow_html=True)

        st.markdown("<div class='sec-hdr'>Active TSR Zones</div>", unsafe_allow_html=True)
        if st.session_state.tsr_real:
            tms_k = _tsr_key_set(st.session_state.tsr_tms)
            for i, p in enumerate(st.session_state.tsr_real):
                in_tms = _poly_key(p["polygon"]) in tms_k
                clr = PAL["green"] if in_tms else PAL["red"]
                icon = "✓" if in_tms else "✗"
                st.markdown(
                    f"<div style='font-family:IBM Plex Mono;font-size:11px;color:{clr};padding:3px 0'>"
                    f"{icon} TSR-{i+1:02d} &nbsp;{p['speed']} km/h"
                    f"{'&nbsp; 🛑 STOP' if p.get('stop') else ''}"
                    f"{'&nbsp; [TMS aware]' if in_tms else '&nbsp; [TMS unaware]'}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(f"<div style='font-family:IBM Plex Mono;font-size:11px;color:{PAL['muted']}'>No active TSR zones.</div>", unsafe_allow_html=True)
