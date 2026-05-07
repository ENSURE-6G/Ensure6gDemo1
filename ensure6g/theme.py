import streamlit as st

PAL = dict(
    bg="#0D1117",
    surface="#161B22",
    border="#30363D",
    text="#E6EDF3",
    muted="#8B949E",
    cyan="#39D0D8",
    amber="#F0A500",
    red="#E05A5A",
    green="#3DD68C",
    purple="#B388FF",
    blue="#58A6FF",
)

C = dict(
    good=[0, 200, 170, 230],
    patchy=[240, 165, 0, 230],
    poor=[220, 80, 80, 230],
    raw=[88, 166, 255, 245],
    hybrid=[0, 200, 140, 245],
    semantic=[179, 136, 255, 245],
    gold=[240, 185, 20, 55],
    gold_ln=[240, 185, 20, 210],
    track=[88, 130, 210, 210],
    ring_good=[0, 200, 170],
    ring_patchy=[240, 165, 0],
    ring_poor=[220, 80, 80],
)

CHART_COLORS = ["#39D0D8", "#F0A500", "#3DD68C", "#B388FF", "#E05A5A", "#58A6FF"]
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="IBM Plex Mono", color="#8B949E", size=10),
    margin=dict(l=8, r=8, t=8, b=8),
    xaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
    yaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
    legend=dict(orientation="h", y=1.14, x=0, font=dict(size=9)),
)


def setup_page():
    st.set_page_config(
        page_title="ENSURE-6G • Rail TMS",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def apply_theme():
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html,body,[data-testid="stAppViewContainer"]{{background:{PAL['bg']}!important;color:{PAL['text']}!important;font-family:'IBM Plex Sans',sans-serif}}
[data-testid="stSidebar"]{{background:{PAL['surface']}!important;border-right:1px solid {PAL['border']}!important}}
[data-testid="stSidebar"] *{{color:{PAL['text']}!important}}
.stTabs [data-baseweb="tab-list"]{{background:{PAL['surface']};border-radius:8px;padding:4px;gap:4px;border:1px solid {PAL['border']}}}
.stTabs [data-baseweb="tab"]{{background:transparent!important;color:{PAL['muted']}!important;border-radius:6px!important;font-family:'IBM Plex Mono',monospace!important;font-size:12px!important;padding:6px 16px!important}}
.stTabs [aria-selected="true"]{{background:{PAL['border']}!important;color:{PAL['cyan']}!important}}
.stButton>button{{background:{PAL['surface']}!important;color:{PAL['cyan']}!important;border:1px solid {PAL['border']}!important;border-radius:6px!important;font-family:'IBM Plex Mono',monospace!important;font-size:12px!important;transition:all .15s}}
.stButton>button:hover{{border-color:{PAL['cyan']}!important;background:#1C2A32!important}}
.stSlider label,.stCheckbox label,.stRadio label,.stSelectbox label{{color:{PAL['muted']}!important;font-size:12px!important;font-family:'IBM Plex Mono',monospace!important}}
.stDataFrame{{border:1px solid {PAL['border']};border-radius:8px}}
div[data-testid="metric-container"]{{background:{PAL['surface']};border:1px solid {PAL['border']};border-radius:8px;padding:10px 14px}}
div[data-testid="metric-container"] label{{color:{PAL['muted']}!important;font-family:'IBM Plex Mono',monospace!important;font-size:11px!important}}
div[data-testid="metric-container"] [data-testid="stMetricValue"]{{color:{PAL['cyan']}!important;font-family:'IBM Plex Mono',monospace!important;font-size:20px!important}}
.kpi-bar{{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 12px}}
.kpi{{display:flex;flex-direction:column;background:{PAL['surface']};border:1px solid {PAL['border']};border-radius:8px;padding:8px 14px;min-width:105px}}
.kpi-label{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.08em}}
.kpi-value{{font-family:'IBM Plex Mono',monospace;font-size:17px;font-weight:600;margin-top:2px}}
.kv-cyan{{color:{PAL['cyan']}}}.kv-amber{{color:{PAL['amber']}}}.kv-red{{color:{PAL['red']}}}
.kv-green{{color:{PAL['green']}}}.kv-blue{{color:{PAL['blue']}}}.kv-purple{{color:{PAL['purple']}}}
.map-lbl{{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;background:{PAL['surface']};color:{PAL['cyan']};border:1px solid {PAL['border']};border-radius:6px;padding:4px 12px;display:inline-block;margin-bottom:4px}}
.map-lbl-tms{{color:{PAL['amber']}}}
.alert-row{{font-family:'IBM Plex Mono',monospace;font-size:11px;padding:5px 10px;border-radius:5px;margin:3px 0;border-left:3px solid {PAL['amber']};background:rgba(240,165,0,.08);color:{PAL['text']}}}
.alert-row.high{{border-color:{PAL['red']};background:rgba(220,80,80,.08)}}
.sec-hdr{{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.12em;border-bottom:1px solid {PAL['border']};padding-bottom:4px;margin:14px 0 8px}}
.legend{{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0}}
.legend-item{{display:flex;align-items:center;gap:5px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']}}}
.dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.s-ok{{background:rgba(61,214,140,.12);border:1px solid rgba(61,214,140,.3);border-radius:6px;padding:6px 12px;color:{PAL['green']};font-family:'IBM Plex Mono',monospace;font-size:12px}}
.s-warn{{background:rgba(240,165,0,.12);border:1px solid rgba(240,165,0,.3);border-radius:6px;padding:6px 12px;color:{PAL['amber']};font-family:'IBM Plex Mono',monospace;font-size:12px}}
.s-crit{{background:rgba(220,80,80,.15);border:1px solid rgba(220,80,80,.4);border-radius:6px;padding:6px 12px;color:{PAL['red']};font-family:'IBM Plex Mono',monospace;font-size:12px}}
.demo-card{{background:linear-gradient(145deg,rgba(22,27,34,.96),rgba(13,17,23,.9));border:1px solid {PAL['border']};border-radius:10px;padding:14px;margin:6px 0 12px;min-height:142px;box-shadow:0 10px 24px rgba(0,0,0,.18)}}
.demo-title{{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;color:{PAL['cyan']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}}
.demo-copy{{font-family:'IBM Plex Sans',sans-serif;font-size:13px;line-height:1.45;color:{PAL['text']};margin:6px 0}}
.demo-copy b{{color:{PAL['muted']};font-family:'IBM Plex Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:.06em}}
.demo-check-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:8px}}
@media (max-width:900px){{.demo-check-grid{{grid-template-columns:1fr}}}}
.prog-wrap{{background:{PAL['border']};border-radius:4px;height:6px;margin:4px 0 12px;overflow:hidden}}
.prog-fill{{height:6px;border-radius:4px;background:linear-gradient(90deg,{PAL['cyan']},{PAL['blue']});transition:width .4s}}
#MainMenu,footer{{visibility:hidden}}
.block-container{{padding-top:1rem!important}}
</style>
""",
        unsafe_allow_html=True,
    )
