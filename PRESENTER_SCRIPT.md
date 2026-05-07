# ENSURE 6G Demo Presenter Script

This script is for running the Streamlit demo live with an audience. It focuses on the message: semantic communication can preserve the safety decision even when raw data transfer becomes expensive or unreliable.

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

- Keep the browser on the `Demo` tab.
- Make sure the sidebar is visible.
- Use the sidebar preset buttons instead of manually tuning controls.
- If the thermal dataset is available, the semantic proof point should use frame `330`.

## 60-Second Opening

Say:

```text
ENSURE 6G studies how future communication systems can remain secure, reliable, and trustworthy for critical infrastructure.

This demo uses railway thermal sensing as a safety scenario. A track-side thermal sensor observes the railway environment, extracts the important meaning from the data, sends it over a simulated 6G network, and the Traffic Management System decides whether action is needed.

The key comparison is between sending everything, sending a reduced hybrid payload, or sending only the semantic meaning needed for a safety decision.
```

Point to:

- The `Demo` tab headline.
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

- `Demo` tab: current mode should be `RAW`.
- `Thermal` tab: railway thermal preview and raw matrix.
- `Network` tab: RAW payload is the largest transfer.

Key message:

```text
RAW transfer is useful when the network is good, but it is the most expensive option.
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

- `Demo` tab: scenario should be `Adverse`, mode should be `RAW`.
- `Network` tab: receiver-side view for RAW.
- `TMS` tab: raw data still requires processing before action.

Key message:

```text
For mission-critical systems, the problem is not only sensing. The important question is whether the right information reaches the decision system in time.
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

The receiver does not need to reconstruct the full image before deciding. The TMS can directly interpret the semantic packet and trigger a traffic management action.
```

Show:

- `Demo` tab: mode should be `SEMANTIC`.
- `Thermal` tab: frame `330`, risk `HIGH`.
- `Semantic` tab: compact semantic packet.
- `Network` tab: semantic payload and receiver outcome.
- `TMS` tab: recommended action should be `issue_tsr`.

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
Semantic communication reduces the transmitted payload while preserving the safety-critical decision.
```

## Optional: Explain HYBRID Mode

Say:

```text
Hybrid mode is the middle ground. It sends a small visual preview plus semantic metadata. This is useful when an operator still needs visual context, but the network should not carry the full raw payload.
```

Show:

- `Network` tab: HYBRID card.
- Receiver-side comparison: preview plus metadata.

Key message:

```text
HYBRID supports human inspection. SEMANTIC supports direct machine action.
```

## Closing Summary

Say:

```text
This demo shows why 6G reliability is not only about higher data rates. For critical infrastructure, the network must deliver the right information, at the right time, in a trustworthy form.

RAW sends data. HYBRID sends context. SEMANTIC sends meaning.

That is the core value: smaller payload, clearer decision, and better resilience under degraded conditions.
```

## Troubleshooting

- If the sidebar is hidden, expand it from the top-left Streamlit control.
- If the wrong frame is shown, click `Go to Event Frame 330`.
- If the app does not show collected railway imagery, confirm the thermal dataset exists at `/Users/kyitha/Documents/New project 3/ThermalData`.
- If the app is slow, stop playback and use the preset buttons.
- If a browser warning appears after reload, refresh the page and rerun the selected preset.
