# ENSURE 6G Thermal Semantic Communication Demo

This repository contains a Streamlit demonstration for the ENSURE 6G project. The demo shows how railway thermal sensing data can be transformed into compact semantic messages and delivered through a simulated 6G network to support Traffic Management System (TMS) decisions.

## About ENSURE 6G

ENSURE 6G is a research initiative focused on developing secure, reliable, and trustworthy next-generation communication systems.

As 6G networks evolve to support critical applications across industry, society, and infrastructure, ensuring robustness against failures, attacks, and uncertainties becomes essential.

### Key Objectives

- Strengthen security and resilience in next-generation wireless networks.
- Enable reliable communication for mission-critical applications.
- Develop adaptive and intelligent system mechanisms.
- Improve trustworthiness and robustness of distributed infrastructures.

### Research Focus

- Secure and reliable communication in emerging 6G systems.
- Data-driven monitoring and anomaly detection.
- Industrial IoT and critical systems.
- Autonomous and intelligent network operation.

### Application Domains

- Industrial IoT.
- Smart infrastructure and cities.
- Mission-critical systems.
- Cyber-physical systems.

### Collaboration

ENSURE 6G brings together academic and industrial partners to bridge the gap between research and real-world deployment, contributing to future communication infrastructures.

## Demo Story

The demo presents a railway safety scenario where thermal camera data is collected from track-side infrastructure and transmitted to a TMS over a simulated 6G network.

```text
Railway thermal sensor -> anomaly extraction -> communication mode -> receiver/TMS -> action
```

The main goal is to compare three communication approaches:

- **RAW**: send the full thermal image or raw frame. This preserves detail but requires the highest bandwidth and is most vulnerable under degraded network conditions.
- **HYBRID**: send a reduced preview plus semantic metadata. This keeps operator context while reducing the payload.
- **SEMANTIC**: send only the extracted meaning, such as risk level, confidence, hotspot location, and recommended TMS action.

The scripted semantic path demonstrates that a small semantic packet can still trigger a safety action when full image delivery is unreliable.

## What The App Shows

- A guided `Demo` tab for presenters and visitors.
- A `Thermal` tab showing railway thermal preview images and the raw algorithm matrix.
- A `Semantic` tab showing extracted event payloads.
- A `Network` tab comparing RAW, HYBRID, and SEMANTIC transmission and receiver-side outcomes.
- A `TMS` tab showing whether the event becomes a traffic management action.
- One-click sidebar presets for baseline, stressed raw transfer, and semantic safety operation.

## Thermal Dataset

The demo can use collected railway thermal data from:

```text
/Users/kyitha/Documents/New project 3/ThermalData
```

Primary source:

- `p2pro/*.npy`: raw P2 Pro thermal frames, shape `192 x 256`.
- `p2proPic/*.png`: grayscale railway preview images for human-facing display.

Secondary source:

- `lepton/*.npy`: Lepton raw thermal frames.
- `leptonPic/*.png`: Lepton preview images.

The app uses P2 Pro as the primary source because its raw data has a known temperature conversion:

```python
temp_c = raw / 64.0 - 273.2
```

If the local thermal dataset is not available, the app falls back to synthetic thermal data so the demo can still run.

For Streamlit Cloud and other hosted deployments, the repository also includes a small bundled P2 Pro demo sample:

```text
ensure6g/sample_data/p2pro/p2img00330.npy
ensure6g/sample_data/p2proPic/p2img00330.png
```

The app uses the full external dataset when it is available. If the full dataset is missing, it uses the bundled event frame so the thermal, semantic, and TMS proof point still works online.

## Local Setup

Clone the repository:

```bash
git clone https://github.com/ENSURE-6G/Ensure6gDemo1.git
cd Ensure6gDemo1
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the Streamlit app:

```bash
streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open:

```text
http://127.0.0.1:8501/
```

## Presenter Flow

Use the sidebar presets:

1. **Baseline - RAW Image/Data**: shows normal full-frame transfer.
2. **Stress - RAW Under Load**: shows how large raw payloads become fragile in adverse network conditions.
3. **Semantic Safety - Meaning + Action**: shows compact semantic delivery and a TMS action.

For the scripted safety proof point, use the event frame shortcut in the sidebar. The expected result is:

- Thermal frame: `330`.
- Risk: `high`.
- Recommended action: `issue_tsr`.
- TMS action: triggered in semantic mode.

## Repository Structure

```text
streamlit_app.py          App entrypoint.
ensure6g/sidebar.py      Sidebar controls, presets, and session state.
ensure6g/simulation.py   Per-frame simulation and semantic delivery logic.
ensure6g/views.py        Streamlit tabs and visual UI.
ensure6g/thermal_data.py Thermal frame loading, statistics, and event extraction.
ensure6g/core.py         Route, radio, TMS, TSR, and helper logic.
ensure6g/theme.py        Page configuration and visual styling.
tests/                   Unit tests.
```

## Verification

Run tests:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache .venv/bin/python -m unittest discover -s tests -v
```

Compile the app modules:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache .venv/bin/python -m py_compile streamlit_app.py ensure6g/*.py tests/test_thermal_data.py
```

## Additional Documentation

- `DEVELOPER_GUIDE.md`: implementation notes, runtime flow, and browser verification checklist.
- `DEMO_UPGRADE_PLAN.md`: roadmap for turning the initial simulation into the current thermal semantic communication demo.
