# ENSURE 6G Demo Presenter Script

This script is for running the Streamlit demo live with an audience. The simplified narrative is **Trustworthy Semantic Sensing for Remote Transport Infrastructure**: semantic fusion turns remote infrastructure observations into compact, trustworthy information that can support Traffic Management System (TMS) action.

## Setup

Start the app:

```bash
streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open:

```text
http://127.0.0.1:8501/
```

Before presenting:

- Keep the browser on the `Mission` tab.
- Make sure the sidebar is visible.
- Use the sidebar preset buttons instead of manually tuning controls.
- If the thermal dataset is available, the semantic proof point should use frame `330`.

## 60-Second Opening

Say:

```text
ENSURE 6G studies how future communication systems can remain secure, reliable, and trustworthy for critical infrastructure.

This demo uses remote transport infrastructure as the safety scenario. Think of railway assets, tunnels, bridges, or track-side equipment that are expensive and risky to inspect manually.

The goal is fewer unnecessary inspections, better operational efficiency, and faster response to safety risk. Instead of sending every raw sensor stream, semantic fusion extracts the meaning needed by the TMS.

The key comparison is between sending everything, sending a reduced hybrid payload, or sending only the semantic meaning needed for a decision.
```

Point to:

- The `Mission` tab headline.
- The three-mode comparison: RAW, HYBRID, SEMANTIC.
- The receiver/TMS outcome area.

## Step 1: Baseline RAW Transfer

Click:

```text
Baseline - RAW Image/Data
```

Say:

```text
In the baseline case, the network is healthy and the sensor sends raw image or frame data. This gives the receiver maximum detail, but the payload is large.
```

Show:

- `Live Demo` tab: current mode should be `RAW`.
- `Technical Details` tab: sensor preview, raw matrix, or data details.
- `Transfer Modes` tab: RAW payload is the largest transfer.

Key message:

```text
RAW transfer is useful when the network is good, but it is the most expensive option and does not reduce inspection workload by itself.
```

## Step 2: RAW Under Network Stress

Click:

```text
Stress - RAW Under Load
```

Say:

```text
Now the same type of safety event happens under adverse network conditions. The raw frame still contains the information, but the payload is heavy and more difficult to deliver reliably.
```

Show:

- `Live Demo` tab: scenario should be `Adverse`, mode should be `RAW`.
- `Transfer Modes` tab: receiver-side view for RAW.
- `TMS Decision` tab: raw data still requires processing before action.

Key message:

```text
For remote infrastructure, the problem is not only sensing. The important question is whether the right information reaches the decision system in time to manage safety risk.
```

## Step 3: Semantic Safety Mode

Click:

```text
Semantic Safety - Meaning + Action
```

If needed, click:

```text
Go to Event Frame 330
```

Say:

```text
In semantic mode, the sensor does not send the full image. It sends the extracted meaning: risk level, confidence, hotspot position, and recommended action.

Semantic fusion has already converted the local observations into an operational message. The receiver does not need to reconstruct the full image before deciding. The TMS can directly interpret the semantic packet and trigger a traffic management action.
```

Show:

- `Live Demo` tab: mode should be `SEMANTIC`, frame `330`, risk `HIGH`.
- `Transfer Modes` tab: semantic payload and receiver outcome.
- `TMS Decision` tab: recommended action should be `issue_tsr`.
- `Technical Details` tab: compact semantic packet and fusion logic.

Expected proof point:

```text
Frame: 330
Risk: high
Confidence: about 0.86
Recommended action: issue_tsr
TMS action: triggered
```

Key message:

```text
Semantic communication reduces the transmitted payload while preserving the safety-critical decision and enabling a TMS action.
```

## Optional: Explain HYBRID Mode

Say:

```text
Hybrid mode is the middle ground. It sends a small visual preview plus semantic metadata. This is useful when an operator still needs visual context, but the network should not carry the full raw payload.
```

Show:

- `Transfer Modes` tab: HYBRID card.
- Receiver-side comparison: preview plus metadata.

Key message:

```text
HYBRID supports targeted human inspection. SEMANTIC supports direct machine action.
```

## Closing Summary

Say:

```text
This demo shows why 6G reliability is not only about higher data rates. For remote transport infrastructure, the network must deliver the right information, at the right time, in a trustworthy form.

RAW sends data. HYBRID sends context. SEMANTIC sends meaning.

That is the core value: fewer unnecessary inspections, more efficient operations, clearer safety decisions, and better resilience under degraded conditions.
```

## Troubleshooting

- If the sidebar is hidden, expand it from the top-left Streamlit control.
- If the wrong frame is shown, click `Go to Event Frame 330`.
- If the app does not show collected railway imagery, confirm the thermal dataset exists at `/Users/kyitha/Documents/New project 3/ThermalData`.
- If the app is slow, stop playback and use the preset buttons.
- If a browser warning appears after reload, refresh the page and rerun the selected preset.
