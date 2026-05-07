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
.guided-hero{{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:18px;align-items:stretch;background:radial-gradient(circle at top left,rgba(57,208,216,.16),transparent 34%),linear-gradient(135deg,rgba(22,27,34,.98),rgba(13,17,23,.94));border:1px solid {PAL['border']};border-radius:18px;padding:22px;margin:8px 0 18px;box-shadow:0 20px 50px rgba(0,0,0,.26)}}
.guided-eyebrow{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:{PAL['cyan']};text-transform:uppercase;letter-spacing:.14em;margin-bottom:8px}}
.guided-title{{font-family:'IBM Plex Sans',sans-serif;font-size:31px;line-height:1.05;font-weight:600;color:{PAL['text']};max-width:780px}}
.guided-lede{{font-size:14px;line-height:1.55;color:{PAL['muted']};max-width:860px;margin-top:12px}}
.guided-live{{border:1px solid rgba(57,208,216,.32);border-radius:16px;background:rgba(57,208,216,.08);padding:16px;display:flex;flex-direction:column;justify-content:center}}
.guided-live span{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.1em}}
.guided-live b{{font-family:'IBM Plex Mono',monospace;font-size:21px;color:{PAL['cyan']};margin-top:8px}}
.guided-live small{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:{PAL['text']};margin-top:4px}}
.guided-panel-title{{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.12em;border-bottom:1px solid {PAL['border']};padding-bottom:6px;margin:18px 0 10px}}
.guided-facts{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}}
.guided-facts div{{background:{PAL['surface']};border:1px solid {PAL['border']};border-radius:10px;padding:10px}}
.guided-facts span,.guided-mode-stage span{{display:block;font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}}
.guided-facts b,.guided-mode-stage b{{font-family:'IBM Plex Mono',monospace;font-size:15px;color:{PAL['text']};word-break:break-word}}
.risk-low{{color:{PAL['green']}!important}}.risk-medium{{color:{PAL['amber']}!important}}.risk-high{{color:{PAL['red']}!important}}
.guided-decision-card{{background:linear-gradient(145deg,rgba(22,27,34,.98),rgba(13,17,23,.92));border:1px solid {PAL['border']};border-radius:16px;padding:16px;box-shadow:0 16px 38px rgba(0,0,0,.22)}}
.guided-decision-top{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}}
.guided-decision-top span{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.1em}}
.guided-decision-top b{{font-family:'IBM Plex Mono',monospace;font-size:20px;color:{PAL['purple']}}}
.guided-outcome{{display:flex;align-items:center;justify-content:space-between;border-radius:12px;padding:12px;margin-bottom:12px}}
.guided-outcome span{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.1em}}
.guided-outcome b{{font-family:'IBM Plex Mono',monospace;font-size:20px}}
.guided-outcome.low{{background:rgba(61,214,140,.11);border:1px solid rgba(61,214,140,.35);color:{PAL['green']}}}
.guided-outcome.medium{{background:rgba(240,165,0,.12);border:1px solid rgba(240,165,0,.35);color:{PAL['amber']}}}
.guided-outcome.high{{background:rgba(224,90,90,.14);border:1px solid rgba(224,90,90,.42);color:{PAL['red']}}}
.guided-decision-copy{{font-size:13px;color:{PAL['muted']};line-height:1.45;margin-top:10px}}
.guided-mode-card{{background:linear-gradient(150deg,rgba(22,27,34,.98),rgba(13,17,23,.92));border:1px solid {PAL['border']};border-radius:16px;padding:14px;min-height:250px;box-shadow:0 12px 30px rgba(0,0,0,.20)}}
.guided-mode-card.raw{{border-top:3px solid #58A6FF}}.guided-mode-card.hybrid{{border-top:3px solid #3DD68C}}.guided-mode-card.semantic{{border-top:3px solid #B388FF}}
.guided-mode-card.active{{box-shadow:0 18px 42px rgba(179,136,255,.16);border-color:rgba(179,136,255,.45)}}
.guided-mode-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:12px}}
.guided-mode-head span{{font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:700;color:{PAL['text']}}}
.guided-mode-head b{{font-family:'IBM Plex Mono',monospace;font-size:13px;color:{PAL['cyan']}}}
.guided-mode-stage{{border:1px solid {PAL['border']};border-radius:10px;padding:10px;margin:8px 0;background:rgba(13,17,23,.45)}}
.guided-mode-stage.ok{{border-color:rgba(61,214,140,.35);background:rgba(61,214,140,.08)}}.guided-mode-stage.bad{{border-color:rgba(224,90,90,.42);background:rgba(224,90,90,.09)}}
.guided-step-card{{background:{PAL['surface']};border:1px solid {PAL['border']};border-radius:14px;padding:14px;min-height:160px}}
.guided-step-card.current{{border-color:{PAL['cyan']};box-shadow:0 12px 30px rgba(57,208,216,.12)}}.guided-step-card.ready{{opacity:.82}}
.guided-step-name{{font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:700;color:{PAL['cyan']};margin-bottom:5px}}
.guided-step-tag{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:{PAL['amber']};margin-bottom:10px}}
.guided-step-copy{{font-size:13px;color:{PAL['text']};line-height:1.42;margin-top:6px}}
.guided-step-copy b{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.06em}}
.guided-check-strip{{margin:12px 0 4px}}
@media (max-width:900px){{.guided-hero{{grid-template-columns:1fr}}.guided-facts{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
.transfer-card{{position:relative;overflow:hidden;background:radial-gradient(circle at top right,color-mix(in srgb,var(--mode-color) 24%,transparent),transparent 38%),linear-gradient(150deg,rgba(22,27,34,.98),rgba(13,17,23,.94));border:1px solid {PAL['border']};border-radius:16px;padding:16px;min-height:260px;box-shadow:0 16px 40px rgba(0,0,0,.26)}}
.transfer-card:before{{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:linear-gradient(90deg,var(--mode-color),transparent)}}
.transfer-active{{border-color:var(--mode-color);box-shadow:0 18px 48px color-mix(in srgb,var(--mode-color) 18%,transparent)}}
.transfer-topline{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px}}
.transfer-mode{{font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:700;letter-spacing:.08em;color:var(--mode-color)}}
.transfer-pill{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['bg']};background:var(--mode-color);border-radius:999px;padding:3px 8px;font-weight:700;letter-spacing:.06em}}
.transfer-payload{{font-family:'IBM Plex Mono',monospace;font-size:31px;font-weight:700;color:{PAL['text']};line-height:1;margin-bottom:8px}}
.transfer-sub{{font-size:13px;line-height:1.38;color:{PAL['muted']};min-height:38px;margin-bottom:14px}}
.transfer-bars{{display:grid;gap:11px;margin:14px 0}}
.transfer-label{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}}
.transfer-track{{height:8px;background:#30363D;border-radius:999px;overflow:hidden}}
.transfer-fill{{height:8px;background:linear-gradient(90deg,var(--mode-color),#E6EDF3);border-radius:999px}}
.transfer-num{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:{PAL['text']};margin-top:3px;text-align:right}}
.transfer-outcome{{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;letter-spacing:.08em;border-radius:8px;padding:8px 10px;text-align:center;margin-top:12px}}
.transfer-outcome.ok{{background:rgba(61,214,140,.13);border:1px solid rgba(61,214,140,.38);color:{PAL['green']}}}
.transfer-outcome.bad{{background:rgba(224,90,90,.14);border:1px solid rgba(224,90,90,.42);color:{PAL['red']}}}
.packet-head{{display:flex;align-items:center;justify-content:space-between;gap:12px;border-radius:12px;padding:12px 14px;margin:8px 0;background:linear-gradient(135deg,rgba(22,27,34,.96),rgba(13,17,23,.86));border:1px solid {PAL['border']}}}
.packet-head span{{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}
.packet-head b{{font-family:'IBM Plex Mono',monospace;font-size:17px;color:{PAL['text']}}}
.packet-head.raw{{border-color:rgba(88,166,255,.55);box-shadow:inset 3px 0 0 #58A6FF}}
.packet-head.raw span{{color:#58A6FF}}
.packet-head.hybrid{{border-color:rgba(61,214,140,.55);box-shadow:inset 3px 0 0 #3DD68C}}
.packet-head.hybrid span{{color:#3DD68C}}
.packet-head.semantic{{border-color:rgba(179,136,255,.58);box-shadow:inset 3px 0 0 #B388FF}}
.packet-head.semantic span{{color:#B388FF}}
.packet-hint{{font-size:13px;line-height:1.42;color:{PAL['muted']};min-height:56px;margin:4px 0 10px}}
.packet-lines{{display:grid;gap:6px;background:rgba(22,27,34,.72);border:1px solid {PAL['border']};border-radius:10px;padding:10px 12px;margin-top:8px}}
.packet-lines div{{font-size:12px;color:{PAL['text']};line-height:1.35}}
.packet-lines b{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.06em;margin-right:6px}}
.semantic-packet{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0 10px}}
.semantic-packet div{{background:rgba(179,136,255,.10);border:1px solid rgba(179,136,255,.26);border-radius:10px;padding:10px}}
.semantic-packet span{{display:block;font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}}
.semantic-packet b{{font-family:'IBM Plex Mono',monospace;font-size:14px;color:{PAL['purple']};word-break:break-word}}
.receiver-intro{{font-size:13px;color:{PAL['muted']};margin:4px 0 10px}}
.receiver-card{{background:linear-gradient(150deg,rgba(22,27,34,.98),rgba(13,17,23,.92));border:1px solid {PAL['border']};border-radius:16px;padding:14px;margin-bottom:14px;min-height:420px;box-shadow:0 16px 38px rgba(0,0,0,.22)}}
.receiver-card.raw{{border-top:3px solid #58A6FF}}
.receiver-card.hybrid{{border-top:3px solid #3DD68C}}
.receiver-card.semantic{{border-top:3px solid #B388FF}}
.receiver-mode{{font-family:'IBM Plex Mono',monospace;font-size:17px;font-weight:700;letter-spacing:.1em;margin-bottom:10px}}
.receiver-card.raw .receiver-mode{{color:#58A6FF}}
.receiver-card.hybrid .receiver-mode{{color:#3DD68C}}
.receiver-card.semantic .receiver-mode{{color:#B388FF}}
.receiver-step{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.1em;margin:12px 0 6px;border-bottom:1px solid {PAL['border']};padding-bottom:4px}}
.receiver-copy{{font-size:13px;color:{PAL['text']};line-height:1.4;margin-bottom:8px}}
.receiver-placeholder{{border-radius:12px;padding:28px 14px;text-align:center;font-family:'IBM Plex Mono',monospace;font-size:12px;letter-spacing:.05em;min-height:120px;display:flex;align-items:center;justify-content:center}}
.receiver-placeholder.ok{{background:rgba(61,214,140,.10);border:1px dashed rgba(61,214,140,.45);color:{PAL['green']}}}
.receiver-placeholder.bad{{background:repeating-linear-gradient(135deg,rgba(224,90,90,.14),rgba(224,90,90,.14) 10px,rgba(22,27,34,.75) 10px,rgba(22,27,34,.75) 20px);border:1px dashed rgba(224,90,90,.55);color:{PAL['red']}}}
.receiver-status{{display:flex;align-items:center;justify-content:space-between;gap:8px;border-radius:10px;padding:9px 11px;margin:8px 0}}
.receiver-status span{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:{PAL['muted']};text-transform:uppercase;letter-spacing:.08em}}
.receiver-status b{{font-family:'IBM Plex Mono',monospace;font-size:13px}}
.receiver-status.ok{{background:rgba(61,214,140,.11);border:1px solid rgba(61,214,140,.35);color:{PAL['green']}}}
.receiver-status.bad{{background:rgba(224,90,90,.13);border:1px solid rgba(224,90,90,.42);color:{PAL['red']}}}
.receiver-decision{{font-size:12px;line-height:1.42;color:{PAL['text']};background:rgba(22,27,34,.7);border:1px solid {PAL['border']};border-radius:10px;padding:10px 12px}}
.prog-wrap{{background:{PAL['border']};border-radius:4px;height:6px;margin:4px 0 12px;overflow:hidden}}
.prog-fill{{height:6px;border-radius:4px;background:linear-gradient(90deg,{PAL['cyan']},{PAL['blue']});transition:width .4s}}
#MainMenu,footer{{visibility:hidden}}
.block-container{{padding-top:1rem!important}}
</style>
""",
        unsafe_allow_html=True,
    )
