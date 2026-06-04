import json
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ensure6g.core import BASE_STATIONS, build_heat_index
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


def _fmt_bytes(num_bytes):
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes:,} B"


def _mode_rows(thermal):
    rows = thermal.get("mode_comparison", [])
    if rows:
        return rows
    if not thermal.get("available"):
        return []
    return [
        {"mode": "RAW", "description": "Full P2 Pro thermal frame", "payload_bytes": thermal["payload_bytes"]},
        {"mode": "HYBRID", "description": "Preview-scale context plus event", "payload_bytes": thermal["hybrid_payload_bytes"]},
        {"mode": "SEMANTIC", "description": "Event meaning only", "payload_bytes": thermal["semantic_payload_bytes"]},
    ]


def _thermal_preview_figure(temp_c, hotspot=None, downsample=1, title=None):
    z = temp_c[::downsample, ::downsample]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            colorscale=[
                [0, "#0D1117"],
                [0.35, "#1F6FEB"],
                [0.65, "#F0A500"],
                [1, "#E05A5A"],
            ],
            showscale=False,
        )
    )
    if hotspot:
        fig.add_scatter(
            x=[hotspot[0] / downsample],
            y=[hotspot[1] / downsample],
            mode="markers",
            marker=dict(size=9, color="#E6EDF3", symbol="x"),
            showlegend=False,
        )
    heatmap_layout = {**CHART_LAYOUT, "yaxis": {**CHART_LAYOUT.get("yaxis", {}), "autorange": "reversed"}}
    fig.update_layout(height=210, title=dict(text=title or "", font=dict(size=11)), **heatmap_layout)
    return fig


def _render_transfer_payload_examples(thermal):
    event = thermal.get("semantic_event", {})
    temp_c = thermal_frame_celsius(thermal["frame_path"])
    hotspot = (thermal["hotspot_x"], thermal["hotspot_y"])
    preview_path = thermal.get("preview_path")
    raw_shape = " x ".join(str(v) for v in thermal["shape"])
    semantic_json = json.dumps(event, indent=2)
    hybrid_json = json.dumps(
        {
            "preview": "32 x 24 thermal thumbnail",
            "frame_id": event.get("frame_id"),
            "hotspot": [thermal["hotspot_x"], thermal["hotspot_y"]],
            "risk_label": event.get("risk_label"),
            "confidence": event.get("confidence"),
            "recommended_action": event.get("recommended_action"),
        },
        indent=2,
    )

    st.markdown("<div class='sec-hdr'>What Gets Transferred</div>", unsafe_allow_html=True)
    raw_col, hybrid_col, semantic_col = st.columns(3, gap="medium")

    with raw_col:
        st.markdown(
            f"""
<div class="packet-head raw">
  <span>RAW transfer</span>
  <b>{_fmt_bytes(thermal['payload_bytes'])}</b>
</div>
<div class="packet-hint">Full railway thermal image plus raw temperature matrix. Best visual detail, but every pixel/sample must cross the network.</div>
""",
            unsafe_allow_html=True,
        )
        if preview_path:
            st.image(preview_path, caption=f"Railway thermal preview | frame {thermal['frame_id']}", use_container_width=True)
            with st.expander("Show raw temperature matrix", expanded=False):
                st.plotly_chart(
                    _thermal_preview_figure(temp_c, hotspot=hotspot, downsample=1, title=f"Raw thermal matrix | {raw_shape} samples"),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
        else:
            st.plotly_chart(
                _thermal_preview_figure(temp_c, hotspot=hotspot, downsample=1, title=f"Raw thermal matrix | {raw_shape} samples"),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        st.markdown(
            """
<div class="packet-lines">
  <div><b>Contains</b> railway preview + full temperature matrix</div>
  <div><b>Good for</b> human inspection, replay, and offline analysis</div>
  <div><b>Risk</b> high bandwidth, higher drop chance under stress</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with hybrid_col:
        st.markdown(
            f"""
<div class="packet-head hybrid">
  <span>HYBRID transfer</span>
  <b>{_fmt_bytes(thermal['hybrid_payload_bytes'])}</b>
</div>
<div class="packet-hint">Compressed railway preview plus event metadata. Operator keeps context without sending the full raw matrix.</div>
""",
            unsafe_allow_html=True,
        )
        if preview_path:
            st.image(preview_path, caption="Hybrid preview image + semantic metadata", use_container_width=True)
        else:
            st.plotly_chart(
                _thermal_preview_figure(temp_c, hotspot=hotspot, downsample=8, title="Thumbnail + hotspot context"),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        st.code(hybrid_json, language="json")

    with semantic_col:
        risk = event.get("risk_label", "low").upper()
        confidence = event.get("confidence", 0)
        action = event.get("recommended_action", "monitor")
        st.markdown(
            f"""
<div class="packet-head semantic">
  <span>SEMANTIC transfer</span>
  <b>{_fmt_bytes(thermal['semantic_payload_bytes'])}</b>
</div>
<div class="packet-hint">Meaning-only safety packet. The network carries the decision-relevant facts, not the image.</div>
<div class="semantic-packet">
  <div><span>Risk</span><b>{risk}</b></div>
  <div><span>Confidence</span><b>{confidence:.2f}</b></div>
  <div><span>Action</span><b>{action}</b></div>
  <div><span>Frame</span><b>{event.get('frame_id')}</b></div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.code(semantic_json, language="json")


def _mode_row(rows, mode):
    for row in rows:
        if row.get("mode") == mode:
            return row
    return {"mode": mode, "delivered": False, "tms_action": False, "delivery_loss": 1.0}


def _receiver_status_html(mode, row, decision):
    delivered = bool(row.get("delivered"))
    status_cls = "ok" if delivered else "bad"
    status = "RECEIVED" if delivered else "MISSING"
    return f"""
<div class="receiver-status {status_cls}">
  <span>{mode} receiver status</span>
  <b>{status}</b>
</div>
<div class="receiver-decision">{decision}</div>
"""


def _render_receiver_view(thermal, rows):
    event = thermal.get("semantic_event", {})
    preview_path = thermal.get("preview_path")
    semantic_json = json.dumps(event, indent=2)
    hybrid_json = json.dumps(
        {
            "preview": "railway thermal thumbnail",
            "frame_id": event.get("frame_id"),
            "risk_label": event.get("risk_label"),
            "confidence": event.get("confidence"),
            "recommended_action": event.get("recommended_action"),
        },
        indent=2,
    )

    st.markdown("<div class='sec-hdr'>Receiver / TMS View</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='receiver-intro'>Same sensor event, three transmission modes. This shows what the TMS actually receives and what it can decide.</div>",
        unsafe_allow_html=True,
    )
    raw_col, hybrid_col, semantic_col = st.columns(3, gap="medium")

    raw_row = _mode_row(rows, "RAW")
    with raw_col:
        st.markdown("<div class='receiver-card raw'><div class='receiver-mode'>RAW</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-step'>1. Sent from sensor</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-copy'>Full railway thermal frame + raw temperature matrix.</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-step'>2. Received by TMS</div>", unsafe_allow_html=True)
        if raw_row.get("delivered") and preview_path:
            st.image(preview_path, caption="Full railway thermal image received", use_container_width=True)
        elif raw_row.get("delivered"):
            st.markdown("<div class='receiver-placeholder ok'>RAW matrix received, visual preview unavailable.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='receiver-placeholder bad'>Image missing or corrupted under network stress.</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-step'>3. TMS decision</div>", unsafe_allow_html=True)
        st.markdown(
            _receiver_status_html(
                "RAW",
                raw_row,
                "TMS needs image processing before action. If the full frame drops, the safety action can be delayed or missed.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    hybrid_row = _mode_row(rows, "HYBRID")
    with hybrid_col:
        st.markdown("<div class='receiver-card hybrid'><div class='receiver-mode'>HYBRID</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-step'>1. Sent from sensor</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-copy'>Compressed railway preview + compact event metadata.</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-step'>2. Received by TMS</div>", unsafe_allow_html=True)
        if hybrid_row.get("delivered") and preview_path:
            st.image(preview_path, caption="Preview received with metadata", use_container_width=True)
            st.code(hybrid_json, language="json")
        elif hybrid_row.get("delivered"):
            st.code(hybrid_json, language="json")
        else:
            st.markdown("<div class='receiver-placeholder bad'>Preview and metadata are partial or missing.</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-step'>3. TMS decision</div>", unsafe_allow_html=True)
        st.markdown(
            _receiver_status_html(
                "HYBRID",
                hybrid_row,
                "TMS can inspect the preview and use event metadata. This is faster than processing the full raw matrix.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    semantic_row = _mode_row(rows, "SEMANTIC")
    with semantic_col:
        st.markdown("<div class='receiver-card semantic'><div class='receiver-mode'>SEMANTIC</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-step'>1. Sent from sensor</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-copy'>Meaning-only packet: risk, confidence, frame, and recommended action.</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-step'>2. Received by TMS</div>", unsafe_allow_html=True)
        if semantic_row.get("delivered"):
            st.markdown(
                f"""
<div class="semantic-packet">
  <div><span>Risk</span><b>{event.get('risk_label', 'low').upper()}</b></div>
  <div><span>Confidence</span><b>{event.get('confidence', 0):.2f}</b></div>
  <div><span>Action</span><b>{event.get('recommended_action', 'monitor')}</b></div>
  <div><span>Frame</span><b>{event.get('frame_id')}</b></div>
</div>
""",
                unsafe_allow_html=True,
            )
            st.code(semantic_json, language="json")
        else:
            st.markdown("<div class='receiver-placeholder bad'>Semantic packet missing.</div>", unsafe_allow_html=True)
        st.markdown("<div class='receiver-step'>3. TMS decision</div>", unsafe_allow_html=True)
        st.markdown(
            _receiver_status_html(
                "SEMANTIC",
                semantic_row,
                "TMS directly triggers the recommended action when confidence and risk pass the safety threshold.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def _render_receiver_summary(thermal, rows):
    event = thermal.get("semantic_event", {})
    summaries = [
        (
            "RAW",
            "Sensor side",
            "Full railway image + raw matrix",
            "TMS side",
            "Image processing required before action",
            _mode_row(rows, "RAW"),
        ),
        (
            "HYBRID",
            "Sensor side",
            "Preview + event metadata",
            "TMS side",
            "Visual context plus structured hints",
            _mode_row(rows, "HYBRID"),
        ),
        (
            "SEMANTIC",
            "Sensor side",
            "Meaning-only event packet",
            "TMS side",
            f"Direct action: {event.get('recommended_action', 'monitor')}",
            _mode_row(rows, "SEMANTIC"),
        ),
    ]
    st.markdown("<div class='sec-hdr'>Receiver Result Summary</div>", unsafe_allow_html=True)
    cols = st.columns(3, gap="medium")
    for col, (mode, sent_label, sent, recv_label, decision, row) in zip(cols, summaries):
        delivered = bool(row.get("delivered"))
        status = "RECEIVED" if delivered else "DROPPED"
        status_cls = "ok" if delivered else "bad"
        action_cls = "action" if row.get("tms_action") else ""
        with col:
            st.markdown(
                f"""
<div class="receiver-summary {mode.lower()} {status_cls} {action_cls}">
  <div class="receiver-summary-head">
    <span>{mode}</span>
    <b>{status}</b>
  </div>
  <div class="receiver-summary-row"><small>{sent_label}</small><strong>{sent}</strong></div>
  <div class="receiver-summary-row"><small>{recv_label}</small><strong>{decision}</strong></div>
</div>
""",
                unsafe_allow_html=True,
            )


def _render_transfer_comparison(frame):
    thermal = frame.get("thermal", {})
    if not thermal.get("available"):
        st.markdown("<div class='s-warn'>Transfer comparison needs collected thermal data.</div>", unsafe_allow_html=True)
        return

    rows = _mode_rows(thermal)
    event = thermal.get("semantic_event", {})
    active_mode = st.session_state.get("uplink_mode", "SEMANTIC")
    palette = {"RAW": "#58A6FF", "HYBRID": "#3DD68C", "SEMANTIC": "#B388FF"}
    labels = {
        "RAW": "Maximum fidelity, maximum bandwidth pressure.",
        "HYBRID": "Balanced: some visual context plus semantic meaning.",
        "SEMANTIC": "Smallest payload, strongest safety path under network stress.",
    }
    raw_payload = max(int(thermal.get("payload_bytes", 1)), 1)

    st.markdown(
        f"""
<div class="evidence-hero">
  <div>
    <div class="guided-eyebrow">Network evidence view</div>
    <div class="evidence-title">Why semantic transfer survives network stress</div>
    <div class="guided-lede">Compare what leaves the sensor, what survives the network, and what the TMS can use for a safety decision.</div>
  </div>
  <div class="evidence-kpis">
    <div><span>Frame</span><b>{thermal.get('frame_id')}</b></div>
    <div><span>Risk</span><b>{event.get('risk_label', 'low').upper()}</b></div>
    <div><span>Action</span><b>{event.get('recommended_action', 'monitor')}</b></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='sec-hdr'>Thermal Data Transfer Modes</div>", unsafe_allow_html=True)
    card_cols = st.columns(3, gap="medium")
    for col, row in zip(card_cols, rows):
        mode = row["mode"]
        payload = int(row["payload_bytes"])
        reduction = 100 * (1 - payload / raw_payload)
        reliability = row.get("reliability_pct")
        delivered = row.get("delivered")
        action = row.get("tms_action")
        active_cls = " transfer-active" if mode == active_mode else ""
        outcome_cls = "ok" if delivered else "bad"
        outcome = "TMS ACTION" if action else ("DELIVERED" if delivered else "DROPPED")
        with col:
            st.markdown(
                f"""
<div class="transfer-card{active_cls}" style="--mode-color:{palette[mode]}">
  <div class="transfer-topline">
    <span class="transfer-mode">{mode}</span>
    <span class="transfer-pill">{'ACTIVE' if mode == active_mode else 'COMPARE'}</span>
  </div>
  <div class="transfer-payload">{_fmt_bytes(payload)}</div>
  <div class="transfer-sub">{labels[mode]}</div>
  <div class="transfer-bars">
    <div>
      <div class="transfer-label">Payload reduction vs RAW</div>
      <div class="transfer-track"><div class="transfer-fill" style="width:{max(0, reduction):.1f}%"></div></div>
      <div class="transfer-num">{reduction:.1f}%</div>
    </div>
    <div>
      <div class="transfer-label">Estimated reliability</div>
      <div class="transfer-track"><div class="transfer-fill" style="width:{max(0, min(100, reliability or 0)):.1f}%"></div></div>
      <div class="transfer-num">{(reliability or 0):.0f}%</div>
    </div>
  </div>
  <div class="transfer-outcome {outcome_cls}">{outcome}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    _render_transfer_payload_examples(thermal)
    _render_receiver_summary(thermal, rows)
    with st.expander("Receiver / TMS detail", expanded=False):
        _render_receiver_view(thermal, rows)

    chart_df = pd.DataFrame(rows)
    if not chart_df.empty:
        st.markdown("<div class='sec-hdr'>Payload + Reliability Chart</div>", unsafe_allow_html=True)
        chart_df["payload_kb"] = chart_df["payload_bytes"] / 1024
        chart_df["reliability_pct"] = chart_df["reliability_pct"].fillna(0)
        fig = go.Figure()
        fig.add_bar(
            x=chart_df["mode"],
            y=chart_df["payload_kb"],
            name="Payload (KB)",
            marker_color=[palette[m] for m in chart_df["mode"]],
            text=[_fmt_bytes(int(v)) for v in chart_df["payload_bytes"]],
            textposition="outside",
        )
        fig.add_scatter(
            x=chart_df["mode"],
            y=chart_df["reliability_pct"],
            name="Reliability (%)",
            mode="lines+markers",
            yaxis="y2",
            line=dict(color="#F0A500", width=3),
            marker=dict(size=10),
        )
        fig.update_layout(
            height=320,
            yaxis=dict(title="Payload KB", gridcolor="#21262D", linecolor="#30363D"),
            yaxis2=dict(title="Reliability %", overlaying="y", side="right", range=[0, 105], gridcolor="#21262D"),
            **{k: v for k, v in CHART_LAYOUT.items() if k not in ("yaxis",)},
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    summary_cols = st.columns(4)
    semantic_payload = max(int(thermal.get("semantic_payload_bytes", 1)), 1)
    summary_cols[0].metric("RAW frame", _fmt_bytes(raw_payload))
    summary_cols[1].metric("Semantic event", _fmt_bytes(semantic_payload))
    summary_cols[2].metric("Compression", f"{raw_payload / semantic_payload:,.0f}x")
    summary_cols[3].metric("Recommended action", event.get("recommended_action", "monitor"))


def _render_thermal_tab(frame):
    thermal = frame.get("thermal", {})
    if not thermal.get("available"):
        st.markdown("<div class='s-warn'>Collected thermal data is not available.</div>", unsafe_allow_html=True)
        return

    event = thermal.get("semantic_event", {})
    preview_path = thermal.get("preview_path")
    risk_cls = {"low": "risk-low", "medium": "risk-medium", "high": "risk-high"}.get(thermal["risk_label"], "risk-low")
    left, right = st.columns([2, 1], gap="medium")
    with left:
        st.markdown("<div class='sec-hdr'>Human View - Railway Thermal Preview</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='thermal-note'>This preview is for the audience and operator: it shows rails, sleepers, and ballast. The raw `.npy` matrix below is what the semantic extraction uses.</div>",
            unsafe_allow_html=True,
        )
        if preview_path:
            st.image(preview_path, caption=f"P2 Pro railway thermal preview | frame {thermal['frame_id']}", use_container_width=True)
        else:
            st.markdown("<div class='s-warn'>Preview PNG is not available for this frame. Showing generated thermal matrix instead.</div>", unsafe_allow_html=True)

        temp_c = thermal_frame_celsius(thermal["frame_path"])
        with st.expander("Raw algorithm view - temperature matrix", expanded=not bool(preview_path)):
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
            fig.update_layout(height=360, **heatmap_layout)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with right:
        st.markdown("<div class='sec-hdr'>Semantic Extraction</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
<div class="thermal-summary">
  <div><span>Frame</span><b>{thermal['frame_id']}</b></div>
  <div><span>Shape</span><b>{thermal['shape'][0]} x {thermal['shape'][1]}</b></div>
  <div><span>Payload</span><b>{_fmt_bytes(thermal['payload_bytes'])}</b></div>
  <div><span>Risk</span><b class="{risk_cls}">{thermal['risk_label'].upper()}</b></div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.metric("Frame", thermal["frame_id"])
        st.metric("Mean", f"{thermal['mean_temp_c']:.1f} C")
        st.metric("P95", f"{thermal['p95_temp_c']:.1f} C")
        st.metric("P99", f"{thermal['p99_temp_c']:.1f} C")
        st.metric("Delta", f"{thermal['delta_temp_c']:.1f} C")
        st.markdown("<div class='sec-hdr'>Extracted Event</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
<div class="semantic-packet">
  <div><span>Sensor</span><b>{event.get('sensor_id', 'thermal-camera')}</b></div>
  <div><span>Confidence</span><b>{event.get('confidence', 0):.2f}</b></div>
  <div><span>Action</span><b>{event.get('recommended_action', 'monitor')}</b></div>
  <div><span>Hotspot</span><b>{thermal['hotspot_x']}, {thermal['hotspot_y']}</b></div>
</div>
""",
            unsafe_allow_html=True,
        )


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


def _render_mission_tab(frame):
    thermal = frame.get("thermal", {})
    event = thermal.get("semantic_event", {}) if thermal.get("available") else {}
    st.markdown(
        """
<div class="mission-hero">
  <div>
    <div class="guided-eyebrow">ENSURE-6G use case</div>
    <div class="mission-title">Trustworthy semantic sensing for remote transport infrastructure</div>
    <div class="mission-lede">The demo focuses on one critical-infrastructure story: remote railway sensing, semantic fusion at the edge, resilient 6G transfer, and a TMS decision that can reduce inspection burden and safety risk.</div>
  </div>
  <div class="mission-proof">
    <span>Live proof point</span>
    <b>Frame 330</b>
    <small>thermal risk -> semantic event -> TMS action</small>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    cards = [
        ("Remote infrastructure", "Connected thermal sensing monitors rail, road, logistics, and harsh transport corridors where continuous human inspection is difficult."),
        ("Costly inspections", "Remote measurements and intelligent analysis reduce repeated field visits and help focus maintenance teams on real anomalies."),
        ("Operational efficiency", "Semantic events improve situational awareness so transport operators can prioritize disruptions, risks, and response."),
        ("Safety risks", "Earlier hazard detection gives the TMS a compact, actionable signal before the issue becomes an accident or service disruption."),
    ]
    cols = st.columns(4, gap="medium")
    for idx, (title, copy) in enumerate(cards, start=1):
        with cols[idx - 1]:
            st.markdown(
                f"""
<div class="mission-card">
  <div class="mission-num">0{idx}</div>
  <div class="mission-card-title">{title}</div>
  <div class="mission-card-copy">{copy}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("<div class='sec-hdr'>Simplified ENSURE-6G Pattern</div>", unsafe_allow_html=True)
    pipeline = [
        ("Infrastructure", "Remote railway corridor", "Large and harsh environment"),
        ("Sensing", "Thermal frame + context", "Continuous remote observation"),
        ("Semantic Fusion", "Risk, confidence, action", "Meaning instead of raw volume"),
        ("6G Transfer", "RAW / HYBRID / SEMANTIC", "Resilience under network stress"),
        ("TMS Decision", event.get("recommended_action", "issue_tsr"), "Decision support for safety response"),
    ]
    st.markdown(
        "<div class='mission-pipeline'>"
        + "".join(
            f"""
<div class="mission-stage">
  <span>{name}</span>
  <b>{value}</b>
  <small>{hint}</small>
</div>
"""
            for name, value, hint in pipeline
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="mission-note">
  Railway is the demonstrator. The same pattern can extend to roads, logistics routes, ports, energy corridors, and other remote infrastructure where trusted 6G communication must carry the right meaning at the right time.
</div>
""",
        unsafe_allow_html=True,
    )


def _render_live_demo_tab(frame):
    thermal = frame.get("thermal", {})
    event = thermal.get("semantic_event", {}) if thermal.get("available") else {}
    st.markdown(
        f"""
<div class="fusion-strip">
  <div>
    <span>1. Connected sensing</span>
    <b>Railway thermal frame</b>
    <small>Remote infrastructure condition</small>
  </div>
  <div>
    <span>2. Edge semantic fusion</span>
    <b>{event.get('risk_label', 'risk').upper()} / {event.get('confidence', 0):.2f}</b>
    <small>Risk, confidence, location, action</small>
  </div>
  <div>
    <span>3. Resilient 6G transfer</span>
    <b>{st.session_state.get('uplink_mode', 'SEMANTIC')}</b>
    <small>RAW, HYBRID, or SEMANTIC payload</small>
  </div>
  <div>
    <span>4. TMS decision</span>
    <b>{event.get('recommended_action', 'monitor')}</b>
    <small>Operational safety response</small>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    _render_demo_tab(frame)


def _render_tms_decision_tab(frame):
    thermal = frame.get("thermal", {})
    event = thermal.get("semantic_event", {}) if thermal.get("available") else {}
    rows = _mode_rows(thermal) if thermal.get("available") else []
    active_mode = st.session_state.get("uplink_mode", "SEMANTIC")
    active_row = _mode_row(rows, active_mode)
    delivered = bool(active_row.get("delivered") or thermal.get("delivered_to_tms"))
    high_risk = event.get("risk_label") in ("high", "critical")
    action = event.get("recommended_action", "monitor")
    confidence = event.get("confidence", 0.0)
    decision = "ISSUE TSR" if delivered and high_risk and action == "issue_tsr" else ("MONITOR" if not high_risk else "WAIT FOR TRUSTED EVENT")
    status_cls = "ok" if decision == "ISSUE TSR" else ("bad" if high_risk and not delivered else "warn")

    st.markdown(
        f"""
<div class="decision-hero {status_cls}">
  <div>
    <div class="guided-eyebrow">Trust & decision layer</div>
    <div class="decision-title">TMS decision from trusted semantic meaning</div>
    <div class="guided-lede">The receiver does not need every pixel to act. It needs a trustworthy event with enough confidence, delivery, and operational context.</div>
  </div>
  <div class="decision-verdict">
    <span>Current decision</span>
    <b>{decision}</b>
    <small>mode={active_mode} | delivered={'YES' if delivered else 'NO'}</small>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Risk", event.get("risk_label", "low").upper())
    c2.metric("Confidence", f"{confidence:.2f}")
    c3.metric("Recommended action", action)
    c4.metric("Receiver status", "Trusted event" if delivered else "Missing/degraded")

    st.markdown("<div class='sec-hdr'>Decision Inputs</div>", unsafe_allow_html=True)
    cols = st.columns(3, gap="medium")
    decision_inputs = [
        ("Sensing evidence", f"Frame {thermal.get('frame_id', 'n/a')}", f"P99={thermal.get('p99_temp_c', 0):.1f} C, delta={thermal.get('delta_temp_c', 0):.1f} C"),
        ("Network evidence", active_mode, f"payload={_fmt_bytes(int(active_row.get('payload_bytes', 0)))}"),
        ("Trust evidence", "accepted" if delivered else "not accepted", f"confidence={confidence:.2f}, loss={thermal.get('delivery_loss', 0)*100:.0f}%"),
    ]
    for col, (title, value, copy) in zip(cols, decision_inputs):
        with col:
            st.markdown(
                f"""
<div class="decision-input">
  <span>{title}</span>
  <b>{value}</b>
  <small>{copy}</small>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("<div class='sec-hdr'>Operational State</div>", unsafe_allow_html=True)
    tms_keys = _tsr_key_set(st.session_state.tsr_tms)
    unknown = [p for p in st.session_state.tsr_real if _poly_key(p["polygon"]) not in tms_keys]
    if frame["enforce_stop"]:
        st.markdown('<div class="s-crit">STOP ORDER active in the TMS view.</div>', unsafe_allow_html=True)
    elif unknown:
        st.markdown(f'<div class="s-warn">{len(unknown)} real TSR zone(s) are not yet known to TMS.</div>', unsafe_allow_html=True)
    elif delivered and action == "issue_tsr":
        st.markdown('<div class="s-ok">Trusted semantic event is available for TMS action.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="s-ok">No unresolved safety discrepancy in the current TMS view.</div>', unsafe_allow_html=True)

    if st.session_state.tsr_real:
        rows_out = []
        for i, p in enumerate(st.session_state.tsr_real):
            rows_out.append(
                {
                    "Zone": f"TSR-{i+1:02d}",
                    "Speed": f"{p['speed']} km/h",
                    "Stop": "YES" if p.get("stop") else "NO",
                    "TMS aware": "YES" if _poly_key(p["polygon"]) in tms_keys else "NO",
                }
            )
        st.dataframe(pd.DataFrame(rows_out), width="stretch", hide_index=True)


def _render_demo_tab(frame):
    thermal = frame.get("thermal", {})
    event = thermal.get("semantic_event", {}) if thermal.get("available") else {}
    current_mode = st.session_state.get("uplink_mode", "SEMANTIC")
    current_scenario = st.session_state.get("scenario_preset", "Good signal")
    near_event = abs(int(st.session_state.get("t_idx", 0)) - DEMO_EVENT_TICK) <= 2
    tms_action = event.get("recommended_action") == "issue_tsr" and thermal.get("delivered_to_tms")

    steps = [
        {
            "name": "Baseline",
            "tag": "RAW Image/Data",
            "talk": "Normal network. Show the railway thermal frame and explain the raw payload cost.",
            "expect": "Full sensor context is available, but this is the heaviest transfer.",
            "active": current_scenario == "Good signal" and current_mode == "RAW",
        },
        {
            "name": "Network Stress",
            "tag": "RAW Under Stress",
            "talk": "Adverse network. The same image/data transfer becomes fragile.",
            "expect": "The TMS may receive late, partial, or missing visual evidence.",
            "active": current_scenario == "Adverse" and current_mode == "RAW",
        },
        {
            "name": "Semantic Safety",
            "tag": "Meaning + Action",
            "talk": "Transmit the safety meaning instead of the full frame.",
            "expect": "Frame 330 produces high risk, confidence 0.86, and TMS action issue_tsr.",
            "active": current_scenario == "Adverse" and current_mode == "SEMANTIC",
        },
    ]

    current_step = next((step for step in steps if step["active"]), steps[0])
    action_label = event.get("recommended_action", "monitor")
    delivery_label = "DELIVERED" if thermal.get("delivered_to_tms") else ("DROPPED" if event.get("risk_label") != "low" else "NOMINAL")
    tms_label = "TSR ISSUED" if tms_action else ("MONITOR" if event.get("risk_label") == "low" else "ACTION PENDING")

    st.markdown(
        f"""
<div class="guided-hero">
  <div>
    <div class="guided-eyebrow">ENSURE-6G industry demo</div>
    <div class="guided-title">Remote sensing -> semantic fusion -> trusted TMS decision</div>
    <div class="guided-lede">A railway thermal sensor represents remote transport infrastructure. The demo compares RAW image/data, HYBRID preview + metadata, and SEMANTIC meaning-only transfer to show what the TMS can trust and use under network stress.</div>
  </div>
  <div class="guided-live">
    <span>Current chapter</span>
    <b>{current_step['name']}</b>
    <small>{current_step['tag']}</small>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if not thermal.get("available"):
        st.markdown(
            "<div class='s-warn'>Collected thermal data is unavailable, so this run is using the synthetic fallback. "
            "The scripted semantic proof point requires the P2 Pro dataset.</div>",
            unsafe_allow_html=True,
        )
        return

    preview_path = thermal.get("preview_path")
    risk_cls = "high" if event.get("risk_label") == "high" else ("medium" if event.get("risk_label") == "medium" else "low")
    rows = _mode_rows(thermal)
    raw_row = _mode_row(rows, "RAW")
    hybrid_row = _mode_row(rows, "HYBRID")
    semantic_row = _mode_row(rows, "SEMANTIC")

    visual_col, decision_col = st.columns([1.15, 1], gap="large")
    with visual_col:
        st.markdown("<div class='guided-panel-title'>1. Sensor sees the railway</div>", unsafe_allow_html=True)
        if preview_path:
            st.image(preview_path, caption=f"P2 Pro railway thermal preview | frame {thermal['frame_id']}", use_container_width=True)
        else:
            temp_c = thermal_frame_celsius(thermal["frame_path"])
            st.plotly_chart(
                _thermal_preview_figure(
                    temp_c,
                    hotspot=(thermal["hotspot_x"], thermal["hotspot_y"]),
                    title=f"Raw thermal matrix | frame {thermal['frame_id']}",
                ),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        st.markdown(
            f"""
<div class="guided-facts">
  <div><span>Frame</span><b>{thermal['frame_id']}</b></div>
  <div><span>P99</span><b>{thermal['p99_temp_c']:.1f} C</b></div>
  <div><span>Delta</span><b>{thermal['delta_temp_c']:.1f} C</b></div>
  <div><span>Risk</span><b class="risk-{risk_cls}">{event.get('risk_label', 'low').upper()}</b></div>
</div>
""",
            unsafe_allow_html=True,
        )

    with decision_col:
        st.markdown("<div class='guided-panel-title'>2. TMS receives what the network delivers</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
<div class="guided-decision-card">
  <div class="guided-decision-top">
    <span>Transfer mode</span>
    <b>{current_mode}</b>
  </div>
  <div class="guided-outcome {risk_cls}">
    <span>Semantic risk</span>
    <b>{event.get('risk_label', 'low').upper()}</b>
  </div>
  <div class="semantic-packet">
    <div><span>Confidence</span><b>{event.get('confidence', 0):.2f}</b></div>
    <div><span>Delivery</span><b>{delivery_label}</b></div>
    <div><span>Action</span><b>{action_label}</b></div>
    <div><span>TMS result</span><b>{tms_label}</b></div>
  </div>
  <div class="guided-decision-copy">Use the sidebar preset buttons to move through the story. The strongest proof point is Semantic Safety: small payload, high-risk event, and direct TMS action.</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("<div class='guided-panel-title'>3. Compare what each mode gives the receiver</div>", unsafe_allow_html=True)
    mode_cards = [
        ("RAW Image/Data", "RAW", raw_row, "Full railway image and temperature matrix", "TMS must process the image before action."),
        ("Preview + Metadata", "HYBRID", hybrid_row, "Small railway preview plus event fields", "TMS gets visual context and structured hints."),
        ("Meaning + Action", "SEMANTIC", semantic_row, "Risk, confidence, frame, recommended action", "TMS can act directly when thresholds pass."),
    ]
    cols = st.columns(3, gap="medium")
    for col, (title, mode, row, received, decision) in zip(cols, mode_cards):
        delivered = bool(row.get("delivered"))
        payload = int(row.get("payload_bytes", 0))
        active_cls = " active" if mode == current_mode else ""
        status_cls = "ok" if delivered else "bad"
        with col:
            st.markdown(
                f"""
<div class="guided-mode-card {mode.lower()}{active_cls}">
  <div class="guided-mode-head">
    <span>{title}</span>
    <b>{_fmt_bytes(payload)}</b>
  </div>
  <div class="guided-mode-stage"><span>Sensor sends</span><b>{received}</b></div>
  <div class="guided-mode-stage {status_cls}"><span>TMS receives</span><b>{'Received' if delivered else 'Missing or degraded'}</b></div>
  <div class="guided-mode-stage"><span>Decision</span><b>{decision}</b></div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("<div class='guided-panel-title'>Presenter path</div>", unsafe_allow_html=True)
    cols = st.columns(3, gap="medium")
    for col, step in zip(cols, steps):
        state_cls = "current" if step["active"] else "ready"
        with col:
            st.markdown(
                f"""
<div class="guided-step-card {state_cls}">
  <div class="guided-step-name">{step['name']}</div>
  <div class="guided-step-tag">{step['tag']}</div>
  <div class="guided-step-copy"><b>Say:</b> {step['talk']}</div>
  <div class="guided-step-copy"><b>Expected:</b> {step['expect']}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    status_cls = "s-ok" if tms_action else ("s-warn" if near_event else "s-warn")
    st.markdown(
        f"""
<div class="guided-check-strip">
  <div class="{status_cls}">Script check: scenario={current_scenario} | mode={current_mode} | event frame={'YES' if near_event else 'NO'} | TMS action={'YES' if tms_action else 'NO'}</div>
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
        st.slider("t", 0, secs - 1, frame["t"], disabled=True, label_visibility="collapsed", key=f"timeline_play_{frame['t']}")
    else:
        new_t = st.slider(
            "t",
            0,
            secs - 1,
            frame["t"],
            label_visibility="collapsed",
            key=f"timeline_manual_{st.session_state.get('timeline_nonce', 0)}",
        )
        if new_t != frame["t"]:
            st.session_state.t_idx = new_t
            if route_df is not None:
                st.session_state.train_s_m = float(route_df.s_m.iloc[new_t])
                st.session_state.train_v_ms = 0.0


def _rgba(color, alpha=1.0):
    r, g, b = color[:3]
    return f"rgba({int(r)},{int(g)},{int(b)},{alpha})"


def _coverage_ring(lat, lon, radius_m, points=96):
    angles = np.linspace(0, 2 * np.pi, points)
    lat_scale = 1 / 111_111.0
    lon_scale = 1 / (111_111.0 * math.cos(math.radians(lat)))
    lats = lat + np.sin(angles) * radius_m * lat_scale
    lons = lon + np.cos(angles) * radius_m * lon_scale
    return lats, lons


def _add_geo_trace(fig, lon, lat, name, color, width=2, mode="lines", fill=None, text=None, size=None):
    fig.add_trace(
        go.Scattergeo(
            lon=lon,
            lat=lat,
            mode=mode,
            name=name,
            line=dict(color=color, width=width),
            marker=dict(color=color, size=size or 7, line=dict(color="rgba(230,237,243,.55)", width=1)),
            fill=fill,
            fillcolor=color if fill else None,
            text=text,
            hovertemplate="%{text}<extra></extra>" if text is not None else "%{fullData.name}<extra></extra>",
            textfont=dict(color="#E6EDF3", size=10),
        )
    )


def _render_cloud_safe_map(frame, route_df, secs, tsr_list, title, tms_view=False):
    """Token-free map rendering for hosted Streamlit deployments."""
    step = max(1, secs // 360)
    path_coords = [(float(route_df.lon.iloc[i]), float(route_df.lat.iloc[i])) for i in range(0, secs, step)]
    path_coords_tuple = tuple(path_coords)
    heat_j = build_heat_index(path_coords_tuple, frame["s_lats"], frame["s_lons"])
    lbls = frame["sensors"]["label"].values[heat_j]
    risk_colors = {"low": _rgba(C["good"], 0.72), "medium": _rgba(C["patchy"], 0.82), "high": _rgba(C["poor"], 0.94)}

    fig = go.Figure()
    for name, lat, lon, radius in BASE_STATIONS:
        for color, ring_radius in [
            (_rgba(C["ring_good"], 0.28), radius),
            (_rgba(C["ring_patchy"], 0.22), int(radius * 2.2)),
            (_rgba(C["ring_poor"], 0.16), int(radius * 3.0)),
        ]:
            ring_lats, ring_lons = _coverage_ring(lat, lon, ring_radius)
            _add_geo_trace(fig, ring_lons, ring_lats, f"{name} coverage", color, width=1)

    for i in range(len(path_coords) - 1):
        _add_geo_trace(
            fig,
            [path_coords[i][0], path_coords[i + 1][0]],
            [path_coords[i][1], path_coords[i + 1][1]],
            "rail risk overlay",
            risk_colors.get(lbls[i], risk_colors["low"]),
            width=4,
        )

    _add_geo_trace(
        fig,
        [pt[0] for pt in path_coords],
        [pt[1] for pt in path_coords],
        "rail corridor",
        _rgba(C["track"], 0.95),
        width=2,
    )

    for p in tsr_list:
        poly = list(p["polygon"])
        closed = poly + [poly[0]]
        _add_geo_trace(
            fig,
            [pt[0] for pt in closed],
            [pt[1] for pt in closed],
            f"TSR {p['speed']} km/h",
            _rgba(C["gold"], 0.35),
            width=2,
            fill="toself",
            text=[f"TSR {p['speed']} km/h{' STOP' if p.get('stop') else ''}"] * len(closed),
        )

    fig.add_trace(
        go.Scattergeo(
            lon=[b[2] for b in BASE_STATIONS],
            lat=[b[1] for b in BASE_STATIONS],
            mode="markers",
            name="base stations",
            marker=dict(size=8, color=_rgba(C["raw"], 0.95), symbol="circle", line=dict(color="#E6EDF3", width=1)),
            text=[f"{name}<br>Base station" for name, *_ in BASE_STATIONS],
            hovertemplate="%{text}<extra></extra>",
        )
    )

    sensors = frame["sensors"].copy()
    mode_color = {"RAW": C["raw"], "HYBRID": C["hybrid"], "SEMANTIC": C["semantic"]}
    sensor_colors = [_rgba(mode_color.get(row.modality, C["good"]), 0.95) for row in sensors.itertuples()]
    sensor_sizes = [13 if row.label == "high" else (10 if row.label == "medium" else 8) for row in sensors.itertuples()]
    sensor_text = [
        f"{row.sid}<br>Risk: {row.label}<br>Mode: {row.modality}<br>Link: {row.qualS}<br>Temp: {row.temp:.1f} C"
        for row in sensors.itertuples()
    ]
    fig.add_trace(
        go.Scattergeo(
            lon=sensors["lon"],
            lat=sensors["lat"],
            mode="markers+text",
            name="sensors",
            marker=dict(size=sensor_sizes, color=sensor_colors, line=dict(color="rgba(230,237,243,.65)", width=1)),
            text=sensors["sid"],
            textposition="top center",
            textfont=dict(color="#E6EDF3", size=9),
            customdata=sensor_text,
            hovertemplate="%{customdata}<extra></extra>",
        )
    )

    train_color = _rgba({"GOOD": C["good"], "PATCHY": C["patchy"], "POOR": C["poor"]}.get(frame["quality"], C["good"]), 1.0)
    fig.add_trace(
        go.Scattergeo(
            lon=[frame["trainA"][1]],
            lat=[frame["trainA"][0]],
            mode="markers+text",
            name="train",
            marker=dict(size=18, color=train_color, symbol="diamond", line=dict(color="#FFFFFF", width=2)),
            text=["TRAIN"],
            textposition="bottom center",
            textfont=dict(color="#E6EDF3", size=10),
            hovertemplate=f"Train<br>Link: {frame['quality']}<br>Bearer: {frame['bearer']}<extra></extra>",
        )
    )

    fig.update_geos(
        projection_type="mercator",
        showland=True,
        landcolor="#101820",
        showocean=True,
        oceancolor="#08111A",
        showlakes=True,
        lakecolor="#08111A",
        showcountries=True,
        countrycolor="#303A46",
        coastlinecolor="#303A46",
        showframe=False,
        lonaxis=dict(range=[16.75, 18.35]),
        lataxis=dict(range=[59.2, 62.55]),
        bgcolor="#0D1117",
    )
    fig.update_layout(
        height=500,
        margin=dict(l=0, r=0, t=34, b=0),
        title=dict(text=title, font=dict(color="#E6EDF3", size=13)),
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        legend=dict(orientation="h", y=0.01, x=0.01, font=dict(color="#8B949E", size=9), bgcolor="rgba(13,17,23,.65)"),
        showlegend=not tms_view,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_tabs(frame, route_df, secs):
    arr = st.session_state.arr
    x = np.arange(secs)
    tab_mission, tab_live, tab_transfer, tab_tms, tab_details = st.tabs(
        ["Mission", "Live Demo", "Transfer Modes", "TMS Decision", "Technical Details"]
    )

    with tab_mission:
        _render_mission_tab(frame)

    with tab_live:
        _render_live_demo_tab(frame)

    with tab_transfer:
        _render_transfer_comparison(frame)

    with tab_tms:
        _render_tms_decision_tab(frame)

    with tab_details:
        detail_thermal, detail_semantic, detail_map, detail_tele, detail_flow, detail_ops = st.tabs(
            ["Sensing", "Semantic JSON", "Map", "Telemetry", "Data Flow", "Ops Debug"]
        )

    with detail_thermal:
        _render_thermal_tab(frame)

    with detail_semantic:
        _render_semantic_tab(frame)

    with detail_map:
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
            rw_col, tms_col = st.columns(2, gap="small")
            with rw_col:
                st.markdown('<div class="map-lbl">⬤ Real World</div>', unsafe_allow_html=True)
                _render_cloud_safe_map(frame, route_df, secs, st.session_state.tsr_real, "Real-world rail corridor")
            with tms_col:
                st.markdown('<div class="map-lbl map-lbl-tms">⬤ TMS View</div>', unsafe_allow_html=True)
                _render_cloud_safe_map(frame, route_df, secs, st.session_state.tsr_tms, "TMS-known rail corridor", tms_view=True)

    with detail_tele:
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

    with detail_flow:
        st.markdown("<div class='sec-hdr'>Supporting Data Flow - Sensors -> BS -> TMS -> Train</div>", unsafe_allow_html=True)
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

    with detail_ops:
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
