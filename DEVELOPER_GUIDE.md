# ENSURE-6G Demo 1 Developer Guide

This guide documents the current modular Streamlit app, the collected thermal-data integration, and the verified semantic-safety demo path.

## Project Layout

- `streamlit_app.py`
  - Thin app entrypoint.
  - Calls page setup, session initialization, sidebar rendering, simulation frame computation, and view rendering.
- `ensure6g/sidebar.py`
  - Session-state defaults, reset behavior, playback controls, and one-click demo presets.
  - Presets: `Baseline`, `Network Stress`, and `Semantic Safety`.
- `ensure6g/simulation.py`
  - Per-frame rail, radio, thermal, semantic delivery, TSR, and TMS simulation.
- `ensure6g/views.py`
  - Header KPIs and all tabs: `Demo`, `Thermal`, `Semantic`, `Maps`, `Telemetry`, `Network`, `TMS`.
- `ensure6g/thermal_data.py`
  - P2 Pro frame discovery, sorting, Celsius conversion, frame statistics, semantic event extraction, and missing-data fallback helpers.
- `ensure6g/core.py`
  - Route, geography, radio, sensor, map-layer, and TSR helper functions.
- `ensure6g/theme.py`
  - Streamlit page config, CSS, colors, and chart layout constants.
- `tests/test_thermal_data.py`
  - Lightweight tests for thermal frame sorting, conversion, event action, and fallback behavior.

## Runtime Flow

Streamlit reruns `streamlit_app.py` top-to-bottom on every interaction.

1. `setup_page()` configures Streamlit.
2. `apply_theme()` injects styling.
3. `init_session_state()` creates missing session keys.
4. `render_sidebar()` returns the current operator controls.
5. `prepare_route()` builds or reuses route samples for the selected duration.
6. `auto_advance()` updates `t_idx` when playback is enabled.
7. `compute_frame()` computes one simulation frame.
8. `render_header_and_timeline()` renders top-level KPIs and timeline.
9. `render_tabs()` renders the detailed demo views.

## Thermal Data

Default dataset path:

```text
/Users/kyitha/Documents/New project 3/ThermalData/p2pro
```

The P2 Pro raw frames are `.npy` arrays with shape `192 x 256` and `int32` values. The app converts them to Celsius with:

```python
temp_c = raw / 64.0 - 273.2
```

`ensure6g/thermal_data.py` computes:

- `mean_temp_c`
- `p95_temp_c`
- `p99_temp_c`
- `delta_temp_c`
- `hotspot_x`, `hotspot_y`
- `risk_label`
- semantic payload size
- hybrid and raw payload estimates

If collected data is missing, the sidebar automatically switches to `Synthetic` and shows a warning. This keeps the app usable on machines without the full dataset.

## Semantic Event Path

Each collected thermal frame can produce a compact semantic event:

```json
{
  "sensor_id": "S07",
  "frame_id": 330,
  "event_type": "thermal_hotspot",
  "risk_label": "high",
  "confidence": 0.86,
  "recommended_action": "issue_tsr"
}
```

The current scripted proof point uses simulation tick `211`, which maps to dataset frame `330`.

Expected result for the `Semantic Safety` preset:

- Scenario: `Adverse`
- Mode: `SEMANTIC`
- Frame: `330`
- Risk: `high`
- Confidence: about `0.86`
- Semantic delivery: `DELIVERED`
- TMS action: `YES`
- Recommended action: `issue_tsr`

## Demo Presets

Use the sidebar `Demo Presets` buttons:

| Button | Scenario | Mode | Expected Outcome |
| --- | --- | --- | --- |
| `Baseline` | Good signal | RAW | Thermal frame is visible; raw delivery is not the semantic proof point |
| `Stress` | Adverse | RAW | Same event under degraded conditions; raw path does not trigger the scripted TMS action |
| `Semantic` | Adverse | SEMANTIC | Semantic event reaches TMS and produces `issue_tsr` |

The `Demo` tab contains the presenter script and a current-state checklist.

## Verification

Run unit tests:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache .venv/bin/python -m unittest discover -s tests -v
```

Compile changed modules:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache .venv/bin/python -m py_compile streamlit_app.py ensure6g/*.py tests/test_thermal_data.py
```

Start Streamlit:

```bash
.venv/bin/streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

Health check:

```bash
curl -I http://127.0.0.1:8501
```

Scripted semantic smoke check:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache .venv/bin/python - <<'PY'
from ensure6g.thermal_data import DEMO_EVENT_TICK, P2PRO_SOURCE, current_thermal_stats

stats = current_thermal_stats(P2PRO_SOURCE, DEMO_EVENT_TICK)
event = stats.get("semantic_event", {})
print(stats.get("available"), stats.get("frame_id"), event.get("risk_label"), event.get("confidence"), event.get("recommended_action"))
PY
```

Expected output includes:

```text
True 330 high 0.86 issue_tsr
```

## Browser Verification Checklist

At `http://127.0.0.1:8501/`:

1. Click `Baseline`.
2. Confirm the `Demo` tab shows `Scenario = Good signal`, `Mode = RAW`, `At event frame = YES`.
3. Click `Stress`.
4. Confirm the `Demo` tab shows `Scenario = Adverse`, `Mode = RAW`, `At event frame = YES`.
5. Click `Semantic`.
6. Confirm the `Demo` tab shows `Scenario = Adverse`, `Mode = SEMANTIC`, `At event frame = YES`, `TMS action = YES`.
7. Confirm the thermal KPI strip shows frame `330`, risk `HIGH`, and TMS delivery `DELIVERED`.
8. Check browser console logs; there should be no frontend errors.

## Maintenance Notes

- Avoid wildcard imports from `ensure6g.core`; underscore-prefixed helpers must be imported explicitly.
- Keep large thermal arrays out of session state. Use cached frame discovery and cached per-frame statistics.
- Preserve `t_idx` as the authoritative timeline position. `train_s_m` should follow it, not drive it.
- Do not set Streamlit widget-backed `st.session_state` keys after the widget is instantiated in the same rerun.
- Keep demo presets deterministic. The `Semantic Safety` preset should continue to produce a TMS action without manual slider tuning.
