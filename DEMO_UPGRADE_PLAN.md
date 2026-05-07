# ENSURE-6G Demo Upgrade Plan

This document describes the next version of the demo: an industry-focused thermal sensing and semantic communication workflow using the collected `ThermalData` dataset.

## Goal

Upgrade the current Streamlit demo from a mostly synthetic rail simulation into a clearer industry demo:

1. Use collected thermal camera data as the primary sensing input.
2. Extract semantic events from thermal frames.
3. Compare RAW, HYBRID, and SEMANTIC communication modes.
4. Show how semantic messages improve TMS decisions under degraded network conditions.
5. Reduce controls and views that do not support this story.

The target demo story is:

```text
Thermal camera -> anomaly extraction -> semantic message -> 6G network -> TMS action -> train speed/TSR response
```

## Current Dataset

Extracted dataset path:

```text
/Users/kyitha/Documents/New project 3/ThermalData
```

Raw streams:

| Source | Path | Files | Shape | Type | Notes |
| --- | --- | ---: | --- | --- | --- |
| P2 Pro | `ThermalData/p2pro/*.npy` | 1688 | `192 x 256` | `int32` | Recommended primary source |
| Lepton | `ThermalData/lepton/*.npy` | 1688 | `120 x 160` | `uint16` | Needs calibration before temperature use |

Preview assets:

| Source | Path | Files | Notes |
| --- | --- | ---: | --- |
| P2 Pro previews | `ThermalData/p2proPic/*.png` | 1597 | Missing first 91 raw frames |
| Lepton previews | `ThermalData/leptonPic/*.png` | 1597 | Missing first 91 raw frames |

Support files:

- `ThermalData/p2pro_video.mp4`
- `ThermalData/Lepton.mp4`
- `7` helper Python scripts

Frame indexes:

- Raw streams cover indexes `114` to `1823`.
- Both raw streams have the same `22` missing frame indexes.
- Useful warm sequence for demo: around frame indexes `321-336`.

Temperature conversion:

The included helper script suggests this conversion for P2 Pro:

```python
temp_c = raw / 64 - 273.2
```

P2 Pro values look plausible after conversion. Lepton values do not, so Lepton should be treated as a secondary visual stream until calibrated.

## Recommended Scope

Use `P2 Pro` as the first integrated real sensor source.

Keep `Synthetic` mode only as a fallback/debug mode. The default industry demo should use collected thermal data.

Defer Lepton integration until its scale is verified.

## New Architecture

Add a dedicated thermal data module:

```text
ensure6g/thermal_data.py
```

Responsibilities:

- Discover available thermal frames.
- Sort frames by trailing numeric index.
- Load frames lazily or cache derived statistics.
- Convert P2 Pro raw values to Celsius.
- Compute robust frame statistics.
- Produce semantic thermal events for the simulation.

Suggested functions:

```python
list_thermal_frames(source: str) -> list[Path]
load_thermal_frame(source: str, frame_idx: int) -> np.ndarray
thermal_frame_stats(frame: np.ndarray, source: str) -> dict
semantic_event_from_stats(stats: dict, sensor_id: str) -> dict
```

Use `st.cache_data` for stable file discovery and statistics. Avoid loading all raw arrays into session state.

## Thermal Statistics

For each frame, compute:

| Field | Purpose |
| --- | --- |
| `frame_id` | Dataset frame number |
| `mean_temp_c` | Scene baseline |
| `p95_temp_c` | Robust warm-region value |
| `p99_temp_c` | Robust hotspot value |
| `max_temp_c` | Diagnostic only; can include outliers |
| `delta_temp_c` | `p99_temp_c - mean_temp_c` |
| `hotspot_x`, `hotspot_y` | Optional hottest-pixel location |
| `source` | `p2pro` or future source name |

Use `p95` and `p99` for demo decisions, not raw `max`, because some frames contain isolated hot-pixel outliers.

## Semantic Event Model

Semantic communication should transmit compact meaning instead of raw thermal frames.

Example event:

```json
{
  "sensor_id": "S08",
  "frame_id": 325,
  "event_type": "thermal_hotspot",
  "mean_temp_c": 37.8,
  "p99_temp_c": 49.2,
  "delta_temp_c": 11.4,
  "risk_label": "high",
  "confidence": 0.91,
  "recommended_action": "issue_tsr"
}
```

Suggested risk levels:

| Risk | Condition | Action |
| --- | --- | --- |
| `low` | Small or no thermal anomaly | Monitor |
| `medium` | Elevated `p95` or `delta` | Increase monitoring |
| `high` | Strong `p99` and anomaly delta | Issue TSR |
| `critical` | High confidence and safety threshold exceeded | Stop or enforce TSR |

The final thresholds should be demo-tunable from the sidebar.

## Communication Modes

The upgraded demo should make the payload tradeoff visible.

### RAW

Send the full thermal frame.

- P2 Pro frame size is about `196 KB`.
- Best detail, highest bandwidth.
- Most likely to degrade under adverse network conditions.

### HYBRID

Send preview image plus semantic metadata.

- Medium payload.
- Useful for operator inspection.
- Keeps enough visual context while reducing network load.

### SEMANTIC

Send only the extracted event.

- Small payload, usually a few hundred bytes.
- Best for degraded network conditions.
- Directly supports TMS decisions.

This comparison is the central demo value.

## Simulation Integration

Modify:

```text
ensure6g/simulation.py
```

Current synthetic thermal generation is inside `_sensor_row()`.

Replace or blend this line:

```python
temp = base + np.random.normal(0, 0.6) + boost
```

with a thermal-backed value:

```python
temp = calibrated_mean + anomaly_gain * delta_temp_c + scenario_boost
```

Recommended approach:

1. Compute the current thermal frame from simulation time:

   ```python
   thermal_idx = t % len(thermal_frames)
   ```

2. Extract thermal statistics for that frame.
3. Map the strongest thermal event to one route sensor.
4. Assign lower thermal influence to nearby sensors.
5. Use semantic event confidence to generate alerts, TSR zones, and TMS actions.

Keep existing route, radio, TSR, and TMS logic where possible.

## UI Changes

Simplify sidebar controls.

Keep:

- Thermal source: `Collected P2 Pro`, `Synthetic`
- Communication mode: `RAW`, `HYBRID`, `SEMANTIC`
- Network condition: `Good`, `Mixed`, `Adverse`
- Safety sensitivity
- Play / Pause / Reset

Reduce or hide:

- Low-level PHY sliders by default
- Random hotspot injection as a primary feature
- Excessive radio parameters unless an advanced mode is enabled

Suggested main tabs:

| Tab | Purpose |
| --- | --- |
| `Thermal` | Show current thermal frame, frame id, mean/p99/delta, hotspot marker |
| `Semantic` | Show extracted semantic event, payload size, action recommendation |
| `Network` | Show latency, throughput, delivery success by mode |
| `TMS` | Show TSR zones, train status, safety action, work orders |

## Payload Calculation

Suggested payload estimates:

```python
RAW_BYTES = thermal_frame.nbytes
HYBRID_BYTES = preview_size_bytes + len(json.dumps(event).encode("utf-8"))
SEMANTIC_BYTES = len(json.dumps(event).encode("utf-8"))
```

For P2 Pro:

```text
192 x 256 x int32 = 196,608 bytes per raw frame
```

These values should feed the current capacity, latency, and loss model so the network impact is visible.

## Industry Demo Flow

Recommended scripted run:

1. Start in `RAW` mode under `Good` network.
2. Show full thermal payload and high bandwidth use.
3. Switch to `Adverse` network and show delivery/latency problems.
4. Switch to `SEMANTIC`.
5. Show the small semantic event still reaches TMS.
6. TMS issues TSR based on semantic event.
7. Train slows/stops according to TMS state.

This demonstrates why semantic communication matters.

## Implementation Phases

### Phase 1: Data Loader

- Status: implemented.
- Added `ensure6g/thermal_data.py`.
- Loaded and sorted P2 Pro frame list.
- Computed cached frame stats.
- Added thermal stats in the KPI strip and `Thermal` tab.

### Phase 2: Semantic Events

- Status: implemented.
- Added event extraction from thermal stats.
- Blended collected thermal signal into route sensor behavior.
- Added RAW, HYBRID, and SEMANTIC payload size calculation.

### Phase 3: UI Upgrade

- Status: implemented.
- Added `Thermal`, `Semantic`, and `Demo` tabs.
- Simplified sidebar with one-click presets and advanced controls hidden in expanders.
- Added payload comparison in `Semantic` and `Network` tabs.

### Phase 4: TMS Integration

- Status: implemented.
- Semantic events can trigger Lane-A alerts, Lane-B summaries, TSR zones, and TMS action.
- Timeline behavior was corrected so `t_idx` is the authoritative playback position.

### Phase 5: Demo Polish

- Status: implemented.
- Added `Baseline`, `Network Stress`, and `Semantic Safety` presets.
- Added operator-friendly `Demo` tab with presenter script.
- Added fallback behavior when the thermal data folder is missing.
- Added lightweight tests for thermal frame sorting, stats, semantic action, and fallback behavior.

## Verified Demo Path

Browser verification on `http://127.0.0.1:8501/` confirmed:

| Preset | Scenario | Mode | Event Frame | TMS Action |
| --- | --- | --- | ---: | --- |
| `Baseline` | Good signal | RAW | 330 | No |
| `Stress` | Adverse | RAW | 330 | No |
| `Semantic` | Adverse | SEMANTIC | 330 | Yes |

The `Semantic` preset produces:

- Thermal risk: `HIGH`
- Confidence: about `0.86`
- Semantic delivery: `DELIVERED`
- Recommended action: `issue_tsr`

## Acceptance Criteria

The upgraded demo is ready when:

- The app starts without requiring manual dataset edits.
- `Collected P2 Pro` source appears in the sidebar.
- Thermal frame stats update during playback.
- Frame indexes around `321-336` produce a visible semantic thermal event.
- RAW/HYBRID/SEMANTIC payload sizes differ clearly.
- Under adverse network settings, semantic messages are more reliable than raw frames.
- TMS can issue a TSR or stop recommendation from the semantic event.
- Synthetic mode still works if thermal data is missing.

## Open Questions

- Confirm the correct Lepton temperature conversion.
- Decide whether thermal previews should be regenerated for the first 91 raw frames.
- Decide whether to show thermal images inside Streamlit or only statistics and event summaries.
- Decide final safety thresholds for the public demo narrative.
