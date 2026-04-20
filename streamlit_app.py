# ENSURE-6G • TMS Rail Demo  ▸  v5 — optimised + polished
# Fixes vs v4:
#   PERF-1  sensor BS quality cached per position (not recomputed 22×/frame)
#   PERF-2  sensor segment precomputed once and stored in session state
#   PERF-3  heat path × sensor distance matrix cached; recomputed only when
#           path_coords changes (i.e. when SECS changes), not every frame
#   PERF-4  route_df passed to build_static_layers as a plain tuple hash key
#           instead of .to_json() (avoids O(SECS) JSON serialisation per frame)
#   PERF-5  _tsr_dup uses a set of keys instead of O(n) list scan
#   PERF-6  dead col_play layout column removed
#   UI-1    Larger, cleaner map heights (500px)
#   UI-2    Coverage rings added back as thin PolygonLayer outlines (lightweight)
#   UI-3    Progress bar replaces bare slider
#   UI-4    Sankey node labels coloured per role

import math, numpy as np, pandas as pd, streamlit as st, pydeck as pdk
from shapely.geometry import LineString, Point
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="ENSURE-6G • Rail TMS", layout="wide",
                   initial_sidebar_state="expanded")

# ── Design tokens ──────────────────────────────────────────────────────────
PAL = dict(
    bg="#0D1117", surface="#161B22", border="#30363D",
    text="#E6EDF3", muted="#8B949E",
    cyan="#39D0D8", amber="#F0A500", red="#E05A5A",
    green="#3DD68C", purple="#B388FF", blue="#58A6FF",
)
C = dict(
    good=[0,200,170,230], patchy=[240,165,0,230], poor=[220,80,80,230],
    raw=[88,166,255,245], hybrid=[0,200,140,245], semantic=[179,136,255,245],
    gold=[240,185,20,55], gold_ln=[240,185,20,210],
    track=[88,130,210,210],
    ring_good=[0,200,170], ring_patchy=[240,165,0], ring_poor=[220,80,80],
)
CHART_COLORS = ["#39D0D8","#F0A500","#3DD68C","#B388FF","#E05A5A","#58A6FF"]
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="IBM Plex Mono", color="#8B949E", size=10),
    margin=dict(l=8,r=8,t=8,b=8),
    xaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
    yaxis=dict(gridcolor="#21262D", linecolor="#30363D"),
    legend=dict(orientation="h", y=1.14, x=0, font=dict(size=9)),
)

st.markdown(f"""
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
.prog-wrap{{background:{PAL['border']};border-radius:4px;height:6px;margin:4px 0 12px;overflow:hidden}}
.prog-fill{{height:6px;border-radius:4px;background:linear-gradient(90deg,{PAL['cyan']},{PAL['blue']});transition:width .4s}}
#MainMenu,footer,header{{visibility:hidden}}
.block-container{{padding-top:1rem!important}}
</style>
""", unsafe_allow_html=True)

# ── Geography ──────────────────────────────────────────────────────────────
R_EARTH = 6_371_000.0

def haversine_m(lat1, lon1, lat2, lon2):
    p = math.pi/180
    dlat,dlon = (lat2-lat1)*p,(lon2-lon1)*p
    a = math.sin(dlat/2)**2+math.cos(lat1*p)*math.cos(lat2*p)*math.sin(dlon/2)**2
    return 2*R_EARTH*math.asin(min(1.0,math.sqrt(a)))

def haversine_vec(lat1,lon1,lat2,lon2):
    lat1=np.asarray(lat1,float); p=np.pi/180
    dlat,dlon=(lat2-lat1)*p,(lon2-lon1)*p
    a=np.sin(dlat/2)**2+np.cos(lat1*p)*np.cos(np.asarray(lat2,float)*p)*np.sin(dlon/2)**2
    return 2*R_EARTH*np.arcsin(np.minimum(1.0,np.sqrt(a)))

RAIL_WP = [
    (62.393,17.307),(62.120,17.150),(61.860,17.140),(61.730,17.110),
    (61.560,17.080),(61.390,17.070),(61.300,17.060),(61.070,17.100),
    (60.850,17.160),(60.675,17.141),(60.380,17.330),(60.200,17.450),
    (60.050,17.520),(59.930,17.610),(59.859,17.639),(59.750,17.820),
    (59.660,17.940),(59.610,17.990),(59.550,18.030),(59.480,18.040),
    (59.420,18.060),(59.370,18.070),(59.329,18.069),
]
ROUTE_LS = LineString([(lon,lat) for lat,lon in RAIL_WP])

BASE_STATIONS = [
    ("Sundsvall",62.386,17.325,16000),("Njurunda",62.275,17.354,14000),
    ("Harmånger",61.897,17.170,14000),("Hudiksvall",61.728,17.103,15000),
    ("Söderhamn",61.303,17.058,15000),("Axmar",61.004,17.190,14000),
    ("Gävle",60.675,17.141,16000),("Tierp",60.345,17.513,14000),
    ("Skyttorp",60.030,17.580,14000),("Uppsala",59.858,17.639,16000),
    ("Märsta",59.620,17.860,15000),("Stockholm",59.330,18.070,18000),
]
HOTSPOTS = [
    dict(name="Hudiksvall cut",lat=61.728,lon=17.103,radius_m=12000),
    dict(name="Gävle marsh",   lat=60.675,lon=17.141,radius_m=15000),
    dict(name="Uppsala bend",  lat=59.859,lon=17.639,radius_m=12000),
]
SEG_NAMES = ["Sundsvall→Hudiksvall","Hudiksvall→Söderhamn",
             "Söderhamn→Gävle","Gävle→Uppsala","Uppsala→Stockholm"]

def interpolate_polyline(points,n):
    n=max(2,int(n))
    lat=np.array([p[0] for p in points],float)
    lon=np.array([p[1] for p in points],float)
    cum=np.zeros(len(points))
    for i in range(1,len(points)):
        cum[i]=cum[i-1]+haversine_m(lat[i-1],lon[i-1],lat[i],lon[i])
    tgt=np.linspace(0,cum[-1],n)
    idx=np.clip(np.searchsorted(cum,tgt,"right"),1,len(cum)-1)
    i0,i1=idx-1,idx
    w=(tgt-cum[i0])/np.maximum(cum[i1]-cum[i0],1e-9)
    return pd.DataFrame({"lat":lat[i0]+(lat[i1]-lat[i0])*w,
                         "lon":lon[i0]+(lon[i1]-lon[i0])*w,"s_m":tgt})

def label_segments(n):
    bounds=np.linspace(0,n,len(SEG_NAMES)+1).astype(int)
    lab=np.empty(n,dtype=object)
    for i,name in enumerate(SEG_NAMES): lab[bounds[i]:bounds[i+1]]=name
    return lab

def nearest_bs_quality(lat,lon):
    best=None
    for name,blat,blon,R in BASE_STATIONS:
        d=haversine_m(lat,lon,blat,blon)
        q="GOOD" if d<=R else ("PATCHY" if d<=2.2*R else "POOR")
        rank={"GOOD":0,"PATCHY":1,"POOR":2}[q]
        if best is None or rank<best[3]: best=(name,d,q,rank)
    return best[0],best[1],best[2]

def cap_loss(qual,t_sec,base_kbps=800,burst=1.4,gl=0.005,bl=0.10):
    cap=int(base_kbps*1000)
    if qual=="GOOD": return int(cap*burst),gl
    if qual=="PATCHY":
        w=0.6+0.2*math.sin(2*math.pi*(t_sec%30)/30)
        return max(int(cap*w*0.9),1),min(0.4,bl*0.5)
    return int(cap*0.25),bl

def point_in_bbox(lat,lon,poly):
    xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
    return min(ys)<=lat<=max(ys) and min(xs)<=lon<=max(xs)

def index_from_s(route_df,s_m):
    s=float(np.clip(s_m,0,float(route_df.s_m.iloc[-1])))
    return min(max(int(np.searchsorted(route_df.s_m.values,s,"left")),0),len(route_df)-1)

# PERF-5: set-based TSR dedup ──────────────────────────────────────────────
def _poly_key(poly): return tuple(tuple(pt) for pt in poly)
def _tsr_key_set(lst): return {_poly_key(p["polygon"]) for p in lst}
def _tsr_dup_set(p,key_set): return _poly_key(p["polygon"]) in key_set
TSR_CAP = 60

# ── PHY model ──────────────────────────────────────────────────────────────
TECH = dict(
    _5G=dict(freq=3.5,bw=5e6,base_lat=20,snr_ok=3,snr_hold=1),
    LTE=dict(freq=1.8,bw=3e6,base_lat=35,snr_ok=0,snr_hold=-2),
    _3G=dict(freq=2.1,bw=1.5e6,base_lat=60,snr_ok=-2,snr_hold=-4),
    GSM=dict(freq=0.9,bw=200e3,base_lat=120,snr_ok=-4,snr_hold=-6),
)
TECH_KEYS = {"5G":"_5G","LTE":"LTE","3G":"_3G","GSM":"GSM"}
P_TX=43

def env_class(lat,lon):
    cities=[(62.391,17.306),(60.675,17.141),(59.859,17.639),(59.329,18.069)]
    return "UMa" if any(haversine_m(lat,lon,c[0],c[1])<15000 for c in cities) else "RMa"

def pathloss_db(freq_GHz,d_m,env):
    d_m=max(d_m,1)
    fspl=32.4+20*np.log10(freq_GHz*1000)+20*np.log10(d_m/1000)
    return fspl+(7 if env=="UMa" else 3)

def noise_dbm(bw): return -174+10*np.log10(bw)+5

class ShadowingTrack:
    def __init__(self,sigma=7,decor=100,seed=7):
        self.rng=np.random.default_rng(seed); self.sigma=sigma; self.decor=decor
        self.last_s=0.0; self.curr=0.0
    def sample(self,s):
        rho=np.exp(-abs(s-self.last_s)/self.decor)
        self.curr=rho*self.curr+math.sqrt(max(1e-9,1-rho**2))*self.rng.normal(0,self.sigma)
        self.last_s=s; return self.curr

def rician_db(K_dB=8):
    K=10**(K_dB/10)
    h=math.sqrt(K/(K+1))+complex(np.random.normal(0,1/math.sqrt(2)),np.random.normal(0,1/math.sqrt(2)))
    return 10*np.log10(max(abs(h)**2/(K+1),1e-6))

def rayleigh_db():
    h=complex(np.random.normal(0,1/math.sqrt(2)),np.random.normal(0,1/math.sqrt(2)))
    return 10*np.log10(max(abs(h)**2,1e-6))

def serving_bs(lat,lon):
    d=[haversine_m(lat,lon,b[1],b[2]) for b in BASE_STATIONS]
    i=int(np.argmin(d))
    return dict(name=BASE_STATIONS[i][0],lat=BASE_STATIONS[i][1],lon=BASE_STATIONS[i][2],
                tech={"5G","LTE","3G","GSM"}),d[i]

def per_from_snr(snr): return max(1e-5,min(0.99,1/(1+math.exp(1.1*(snr-2.0)))))

def pick_bearer(snr_table,techs,curr):
    for b in ["5G","LTE","3G","GSM"]:
        k=TECH_KEYS[b]
        if b in techs and snr_table.get(b,-99)>=TECH[k]["snr_ok"]: return b,True
    avail=[b for b in ["5G","LTE","3G","GSM"] if b in techs]
    return (max(avail,key=lambda x:snr_table.get(x,-99)),True) if avail else (curr,False)

def pick_secondary(primary,snr_table,delta=2.0):
    alts=[(b,s) for b,s in snr_table.items() if b!=primary]
    if not alts: return None
    b2,s2=max(alts,key=lambda x:x[1])
    return b2 if s2+1e-9>=snr_table[primary]-delta else None

# ── TSR polygon (unit-correct) ─────────────────────────────────────────────
def tsr_poly(clat,clon,length_m=1500,half_w=18):
    m2lat=1/111111.0; m2lon=1/(111111.0*math.cos(math.radians(clat)))
    length_deg=length_m*m2lat; step_deg=length_deg/10
    nearest=ROUTE_LS.interpolate(ROUTE_LS.project(Point(clon,clat)))
    pts=[nearest]
    for sgn in (1,-1):
        acc=0.0
        while acc<length_deg/2:
            acc+=step_deg
            s=max(0,min(ROUTE_LS.project(nearest)+sgn*acc,ROUTE_LS.length))
            pts.append(ROUTE_LS.interpolate(s))
    pts=sorted(pts,key=lambda p:ROUTE_LS.project(p))
    p0,p1=pts[0],pts[-1]
    dx,dy=p1.x-p0.x,p1.y-p0.y; L=math.hypot(dx,dy)+1e-12
    nx,ny=-dy/L,dx/L
    return [[p0.x-half_w*m2lon*nx,p0.y-half_w*m2lat*ny],
            [p0.x+half_w*m2lon*nx,p0.y+half_w*m2lat*ny],
            [p1.x+half_w*m2lon*nx,p1.y+half_w*m2lat*ny],
            [p1.x-half_w*m2lon*nx,p1.y-half_w*m2lat*ny]]

# ── Coverage ring polygon (cheap, no ScatterplotLayer fill blobs) ──────────
# ── PERF-4: Static layers cached by tuple key ─────────────────────────────
@st.cache_data(show_spinner=False)
def build_layers_cached(path_coords_tuple, secs_key):
    """
    PERF-4: accepts path as a tuple (hashable) instead of JSON string.
    Called once per SECS change, not every frame.
    """
    path_coords = [list(pt) for pt in path_coords_tuple]

    track_df = pd.DataFrame([{"path": path_coords}])
    track_layer = pdk.Layer("PathLayer", data=track_df, get_path="path",
                            get_color=C["track"], width_min_pixels=3, width_scale=2)

    bs_dots = pd.DataFrame([{"lat":b[1],"lon":b[2],"name":b[0],
                              "cr":88,"cg":166,"cb":255,"ca":200} for b in BASE_STATIONS])
    bs_layer = pdk.Layer("ScatterplotLayer", data=bs_dots, get_position="[lon,lat]",
                         get_fill_color="[cr,cg,cb,ca]", get_radius=700,
                         radius_min_pixels=4, radius_max_pixels=9,
                         stroked=True, get_line_color=[255,255,255,160],
                         line_width_min_pixels=1, pickable=True)

    # Coverage rings — stroke-ONLY ScatterplotLayer circles (no fill = no white blobs).
    # Three concentric rings per BS: GOOD / PATCHY / POOR radii.
    # pydeck ScatterplotLayer with filled=False, stroked=True draws only the outline.
    ring_rows = []
    for name, lat, lon, r_m in BASE_STATIONS:
        for (cr,cg,cb), radius in [
            (C["ring_good"],  r_m),
            (C["ring_patchy"], int(r_m * 2.2)),
            (C["ring_poor"],   int(r_m * 3.0)),
        ]:
            ring_rows.append({
                "lat": lat, "lon": lon, "radius": radius,
                "cr": cr, "cg": cg, "cb": cb, "ca": 180,
            })
    rings_df = pd.DataFrame(ring_rows)
    rings_layer = pdk.Layer(
        "ScatterplotLayer", data=rings_df,
        get_position="[lon, lat]",
        get_radius="radius",
        get_fill_color=[0, 0, 0, 0],       # fully transparent fill — NO blobs
        get_line_color="[cr, cg, cb, ca]",  # coloured outline only
        filled=False,
        stroked=True,
        line_width_min_pixels=1,
        line_width_max_pixels=2,
    )

    return track_layer, bs_layer, rings_layer, path_coords

# PERF-3: heat distance matrix cached per path+sensor positions ─────────────
@st.cache_data(show_spinner=False)
def build_heat_index(path_coords_tuple, sensor_lats_tuple, sensor_lons_tuple):
    """Returns nearest-sensor index for each path point. Recomputed only when
    path or sensor positions change (i.e. when SECS changes), not every frame."""
    path_np = np.array(path_coords_tuple)   # (N,2)  [lon,lat]
    latv = np.array(sensor_lats_tuple)
    lonv = np.array(sensor_lons_tuple)
    d2 = ((path_np[:,1][:,None]-latv)**2+(path_np[:,0][:,None]-lonv)**2)
    return np.argmin(d2, axis=1)  # shape (N,)

# PERF-1+2: sensor static properties cached per SECS ───────────────────────
@st.cache_data(show_spinner=False)
def sensor_static(secs_key, sensor_lats_tuple, sensor_lons_tuple):
    """Pre-compute BS quality and segment for each sensor. Called once per SECS."""
    N = len(sensor_lats_tuple)
    qualS_list, capS0_list, seg_list = [], [], []
    route_df_local = st.session_state.get("route_df")
    seg_labels_local = st.session_state.get("seg_labels")
    if route_df_local is None:
        # Can't compute yet — return empty, will be populated next frame
        return None
    for i in range(N):
        lat,lon = sensor_lats_tuple[i], sensor_lons_tuple[i]
        _,_,qualS = nearest_bs_quality(lat,lon)
        qualS_list.append(qualS)
        capS0,_ = cap_loss(qualS,0)  # base cap (time-independent part)
        capS0_list.append(capS0)
        d = ((route_df_local.lat-lat)**2+(route_df_local.lon-lon)**2)**0.5
        idx_s = int(np.argmin(d.values))
        seg_list.append(seg_labels_local[idx_s])
    return dict(qualS=qualS_list, capS0=capS0_list, seg=seg_list)

# ── Session state ──────────────────────────────────────────────────────────
def reset_sim():
    for k in ["arr","_times","tsr_real","tsr_tms","work_orders","alerts_feed",
              "sensor_static_cache"]:
        st.session_state.pop(k,None)
    for k,v in [("t_idx",0),("train_s_m",0.0),("train_v_ms",0.0),
                ("bearer","5G"),("bearer_prev","5G"),("bearer_ttt",0),
                ("ho_gap_until",-1)]:
        st.session_state[k]=v

for k,v in [("t_idx",0),("playing",False),("train_s_m",0.0),("train_v_ms",0.0),
            ("bearer","5G"),("bearer_prev","5G"),("bearer_ttt",0),("ho_gap_until",-1),
            ("tsr_real",[]),("tsr_tms",[]),("work_orders",[]),("alerts_feed",[])]:
    if k not in st.session_state: st.session_state[k]=v
if "shadow" not in st.session_state: st.session_state.shadow=ShadowingTrack()

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"<div style='font-family:IBM Plex Mono;font-size:16px;font-weight:600;"
                f"color:{PAL['cyan']};padding:8px 0 4px;letter-spacing:.05em;'>"
                f"⬡ ENSURE-6G</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-family:IBM Plex Mono;font-size:10px;"
                f"color:{PAL['muted']};padding-bottom:12px;'>"
                f"Rail TMS • Sundsvall → Stockholm</div>", unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("<div class='sec-hdr'>Scenario</div>", unsafe_allow_html=True)
    preset = st.selectbox("Preset",["Good signal","Mixed","Adverse"],
                          label_visibility="collapsed")
    if   preset=="Good signal": def_min,def_TTT,def_HO,def_dc=20,1000,200,True
    elif preset=="Mixed":       def_min,def_TTT,def_HO,def_dc=20,1200,350,True
    else:                       def_min,def_TTT,def_HO,def_dc=20,1600,600,False

    sim_minutes = st.number_input("Duration (min)",5,120,def_min,5)
    mode = st.radio("Uplink mode",["RAW","SEMANTIC","HYBRID"],index=2,horizontal=True)

    st.markdown("<div class='sec-hdr'>Radio</div>", unsafe_allow_html=True)
    laneA_reps   = st.slider("Lane-A repetitions",1,3,2)
    enable_dc    = st.checkbox("Dual Connectivity",def_dc)
    dc_snr_delta = st.slider("DC min ΔSNR (dB)",0.0,10.0,2.0,0.5)
    TTT_MS       = st.slider("Time-To-Trigger (ms)",200,3000,def_TTT,100)
    HO_GAP_MS    = st.slider("HO outage (ms)",0,1500,def_HO,50)

    st.markdown("<div class='sec-hdr'>Safety</div>", unsafe_allow_html=True)
    tsr_conf     = st.slider("Buckling threshold",0.60,0.95,0.85,0.01)
    tsr_speed    = st.slider("TSR speed (km/h)",30,120,60,5)
    stop_on_crit = st.checkbox("STOP at conf ≥ 0.92",True)

    st.markdown("<div class='sec-hdr'>Hotspot Injection</div>", unsafe_allow_html=True)
    demo_issues  = st.checkbox("Inject summer hotspots",True)
    summer_sev   = st.slider("Severity boost (°C)",0.0,20.0,12.0,1.0)
    always_tsr   = st.checkbox("Always show TSR zones",True)

    st.markdown("---")
    ca,cb,cc = st.columns(3)
    if ca.button("◀◀",use_container_width=True):
        st.session_state.t_idx=max(0,st.session_state.t_idx-10)
    if cb.button("▶▶",use_container_width=True):
        st.session_state.t_idx=min(max(1,int(sim_minutes*60)-1),st.session_state.t_idx+10)
    play_rate = cc.selectbox("Rate",["1×","2×","4×","0.5×"],label_visibility="collapsed")
    r1,r2=st.columns(2)
    if r1.button("▶ Play",use_container_width=True):  st.session_state.playing=True
    if r2.button("⏸ Pause",use_container_width=True): st.session_state.playing=False
    if st.button("⏹ Stop & Reset",use_container_width=True):
        st.session_state.playing=False; reset_sim(); st.rerun()

# ── Route setup ───────────────────────────────────────────────────────────
SECS = max(2,int(sim_minutes*60))
if st.session_state.get("route_secs")!=SECS:
    st.session_state.route_df   = interpolate_polyline(RAIL_WP,SECS)
    st.session_state.seg_labels = label_segments(SECS)
    st.session_state.route_secs = SECS
    for k in ["arr","_times","sensor_static_cache"]:
        st.session_state.pop(k,None)

route_df   = st.session_state.route_df
seg_labels = st.session_state.seg_labels
V_MAX_MS=200/3.6; A_MAX=0.6; B_MAX=0.9

# ── Auto-advance ─────────────────────────────────────────────────────────
if st.session_state.playing:
    rate_ms={"0.5×":1400,"1×":700,"2×":350,"4×":175}.get(play_rate,700)
    st_autorefresh(interval=rate_ms,key=f"tick_{SECS}")
    st.session_state.t_idx=min(st.session_state.t_idx+1,SECS-1)
    if st.session_state.t_idx>=SECS-1: st.session_state.playing=False

t=st.session_state.t_idx

# ── Frame computation ─────────────────────────────────────────────────────
idx_s   = index_from_s(route_df,st.session_state.train_s_m)
trainA  = (float(route_df.lat.iloc[idx_s]),float(route_df.lon.iloc[idx_s]))
seg     = seg_labels[idx_s]
s_along = float(route_df.s_m.iloc[idx_s])

# PHY
bsA,dA = serving_bs(*trainA)
envA   = env_class(*trainA)
shadow = st.session_state.shadow
snr_table={}
for b in ["5G","LTE","3G","GSM"]:
    if b in bsA["tech"]:
        k=TECH_KEYS[b]
        pl=pathloss_db(TECH[k]["freq"],dA,envA)
        sh=shadow.sample(s_along)
        fad=rician_db(8) if envA=="RMa" else rayleigh_db()
        snr_table[b]=P_TX-pl+sh+fad-noise_dbm(TECH[k]["bw"])

# Bearer/handover
cand,valid=pick_bearer(snr_table,bsA["tech"],st.session_state.bearer)
if valid and cand!=st.session_state.bearer:
    st.session_state.bearer_ttt+=700
    if st.session_state.bearer_ttt>=TTT_MS:
        st.session_state.bearer_prev=st.session_state.bearer
        st.session_state.bearer=cand
        st.session_state.bearer_ttt=0
        st.session_state.ho_gap_until=t+math.ceil(HO_GAP_MS/700)
else:
    st.session_state.bearer_ttt=0

bearer   = st.session_state.bearer
tk       = TECH_KEYS[bearer]
snr_use  = snr_table.get(bearer,-20.0)
per1     = per_from_snr(snr_use)
secondary= pick_secondary(bearer,snr_table,dc_snr_delta) if enable_dc else None
per2     = per_from_snr(snr_table.get(secondary,-20.0)) if secondary else None
laneA_phy= (1-(1-(1-per1)**laneA_reps)*(1-(1-per2)**laneA_reps)
            if secondary else (1-per1)**laneA_reps)

_,_,quality = nearest_bs_quality(*trainA)
cap_bps,rand_loss = cap_loss(quality,t)
in_gap = t<st.session_state.ho_gap_until

# ── Sensors ───────────────────────────────────────────────────────────────
N_SENS=22
sidx=np.linspace(0,len(route_df)-1,N_SENS).astype(int)
s_lats=tuple(float(route_df.lat.iloc[j]) for j in sidx)
s_lons=tuple(float(route_df.lon.iloc[j]) for j in sidx)
sensors_base=pd.DataFrame([{"sid":f"S{i:02d}","lat":s_lats[i],"lon":s_lons[i]}
                            for i in range(N_SENS)])

# PERF-1/2: load cached static sensor properties
ss=sensor_static(SECS, s_lats, s_lons)
if ss is None:
    ss=dict(qualS=["GOOD"]*N_SENS, capS0=[int(800000*1.4)]*N_SENS, seg=[SEG_NAMES[0]]*N_SENS)

def sensor_row(args):
    i,(r,qualS,capS0,seg_s)=args
    base=24+10*math.sin(2*math.pi*((t/60)%1440)/1440)
    boost,hot=0.0,""
    if demo_issues:
        for h in HOTSPOTS:
            d=haversine_m(r.lat,r.lon,h["lat"],h["lon"])
            if d<=h["radius_m"]:
                w=max(0.0,1.0-d/h["radius_m"]); b=w*summer_sev
                if b>boost: boost,hot=b,h["name"]
    temp   =base+np.random.normal(0,0.6)+boost
    strain =max(0.0,(temp-35)*0.8+np.random.normal(0,0.5))
    ballast=max(0.0,np.random.normal(0.3,0.1)+0.015*boost)
    score  =min(1.0,0.01*(temp-30)**2+0.04*max(0,strain-8)+0.2*(boost>6))
    label  ="high" if score>0.75 else ("medium" if score>0.4 else "low")
    exc    =(["temp>38"] if temp>=38 else [])+(["strain>10"] if strain>=10 else [])
    # PERF-1: use cached qualS; only recompute time-varying lossS
    _,lossS=cap_loss(qualS,t)
    return dict(score=score,label=label,exceeded=exc,
                temp=round(temp,1),strain=round(strain,1),ballast=round(ballast,2),
                qualS=qualS,capS=capS0,lossS=lossS,hotspot=hot,segment=seg_s)

rows=[sensor_row((i,(r,ss["qualS"][i],ss["capS0"][i],ss["seg"][i])))
      for i,r in enumerate(sensors_base.itertuples())]
S=pd.DataFrame(rows)
sensors=pd.concat([sensors_base,S],axis=1)

# Modality
def choose_mod(r):
    if r["qualS"]=="POOR" or r["capS"]<100_000: return "SEMANTIC"
    if r["qualS"]=="GOOD" and r["score"]<0.4 and r["capS"]>400_000: return "RAW"
    return "HYBRID"
sensors["modality"]=sensors.apply(choose_mod,axis=1)

RAW_HZ={"RAW":2.0,"HYBRID":0.2,"SEMANTIC":0.0}
BYTES_RAW=24; BYTES_ALERT=280; BYTES_SUMM=180
sensors["raw_hz"] =sensors["modality"].map(RAW_HZ).fillna(0.0)
sensors["raw_bps"]=sensors["raw_hz"]*BYTES_RAW*(1.0-sensors["lossS"])
raw_bps_delivered =int(sensors["raw_bps"].sum())

# Lane-A alerts
rng_a=np.random.default_rng(42+t)
laneA_alerts=[]
for r in sensors.itertuples():
    if r.label in ("medium","high") and r.exceeded:
        conf=round(0.6+0.4*r.score,2)
        if rng_a.uniform()<(1.0-r.lossS):
            laneA_alerts.append(dict(sid=r.sid,lat=r.lat,lon=r.lon,
                                     severity=r.label,confidence=conf,
                                     temp=r.temp,strain=r.strain,ballast=r.ballast))

# Lane-B
laneB_msgs=[]
if mode in ("SEMANTIC","HYBRID") and sensors["modality"].isin(["SEMANTIC","HYBRID"]).any():
    laneB_msgs.append({"bhs":int((sensors.ballast>0.6).sum()),"alerts":len(laneA_alerts)})

laneA_bps=len(laneA_alerts)*BYTES_ALERT*(2 if (enable_dc and secondary) else 1)
laneB_bps=len(laneB_msgs)*BYTES_SUMM
bps_total=laneA_bps+laneB_bps+raw_bps_delivered

# TSR creation — PERF-5 set-based dedup
real_keys=_tsr_key_set(st.session_state.tsr_real)
for a in laneA_alerts:
    if a["confidence"]>=tsr_conf:
        poly=tsr_poly(a["lat"],a["lon"])
        entry=dict(polygon=poly,speed=tsr_speed,created_idx=t,
                   critical=True,stop=(a["confidence"]>=0.92 and stop_on_crit))
        if _poly_key(poly) not in real_keys:
            st.session_state.tsr_real.append(entry); real_keys.add(_poly_key(poly))

if demo_issues and always_tsr:
    latv=sensors["lat"].values; lonv=sensors["lon"].values
    for h in HOTSPOTS:
        d=haversine_vec(latv,lonv,h["lat"],h["lon"])
        in_h=d<=h["radius_m"]
        if in_h.any():
            top=sensors.loc[in_h].sort_values("score",ascending=False).iloc[0]
            poly=tsr_poly(float(top.lat),float(top.lon))
            entry=dict(polygon=poly,speed=tsr_speed,created_idx=t,
                       critical=True,stop=(float(top.score)>0.92))
            if _poly_key(poly) not in real_keys:
                st.session_state.tsr_real.append(entry); real_keys.add(_poly_key(poly))

if len(st.session_state.tsr_real)>TSR_CAP:
    st.session_state.tsr_real=st.session_state.tsr_real[-TSR_CAP:]

# Downlink to TMS
loss_down=min(0.95,rand_loss+(0.3 if in_gap else 0.0))
tms_keys=_tsr_key_set(st.session_state.tsr_tms)
if np.random.random()>loss_down:
    for p in st.session_state.tsr_real:
        pk=_poly_key(p["polygon"])
        if pk not in tms_keys:
            st.session_state.tsr_tms.append(p); tms_keys.add(pk)
if len(st.session_state.tsr_tms)>TSR_CAP:
    st.session_state.tsr_tms=st.session_state.tsr_tms[-TSR_CAP:]

enforce_stop=any(p.get("stop") for p in st.session_state.tsr_tms)
crash=any(p["critical"] and _poly_key(p["polygon"]) not in tms_keys
          and point_in_bbox(trainA[0],trainA[1],p["polygon"])
          for p in st.session_state.tsr_real)

tsr_here=min((p["speed"] for p in st.session_state.tsr_tms
              if point_in_bbox(trainA[0],trainA[1],p["polygon"])),default=None)
v_target=0.0 if enforce_stop else (tsr_here/3.6 if tsr_here else V_MAX_MS)

# Kinematics
v_cur=st.session_state.train_v_ms
v_new=(min(v_cur+A_MAX,v_target) if v_target>=v_cur else max(v_cur-B_MAX,v_target))
s_new=float(np.clip(st.session_state.train_s_m+v_new,0,float(route_df.s_m.iloc[-1])))
if s_new>=float(route_df.s_m.iloc[-1])-1: v_new=0.0; st.session_state.playing=False
st.session_state.train_v_ms=v_new; st.session_state.train_s_m=s_new

# E2E latency
cap_safe=max(cap_bps,1)
lat_ms=TECH[tk]["base_lat"]+bps_total/1000
if bps_total>cap_safe: lat_ms*=min(4.0,1+0.35*(bps_total/cap_safe-1))
if in_gap: lat_ms+=80
laneA_success=laneA_phy
if in_gap and not secondary: laneA_success=max(0.0,laneA_success*0.85)

# Alerts feed
for a in laneA_alerts[:4]:
    st.session_state.alerts_feed.append(
        dict(t=t,sid=a["sid"],severity=a["severity"],
             conf=int(a["confidence"]*100),temp=a["temp"],strain=a["strain"]))
st.session_state.alerts_feed=st.session_state.alerts_feed[-8:]

# Telemetry history
if "_times" not in st.session_state:
    st.session_state._times=np.full(SECS,np.nan)
    st.session_state.arr={k:np.full(SECS,np.nan) for k in
        ["raw","laneA","laneB","cap","snr","succ","lat_ms","speed"]}
if math.isnan(st.session_state._times[t]):
    st.session_state._times[t]=t
    a=st.session_state.arr
    a["raw"][t]=raw_bps_delivered; a["laneA"][t]=laneA_bps; a["laneB"][t]=laneB_bps
    a["cap"][t]=cap_bps; a["snr"][t]=snr_use
    a["succ"][t]=laneA_success*100; a["lat_ms"][t]=lat_ms; a["speed"][t]=v_new*3.6

arr=st.session_state.arr; x=np.arange(SECS)
def series(k): return [None if (isinstance(v,float) and math.isnan(v)) else v for v in arr[k]]

# ── Header KPI bar ────────────────────────────────────────────────────────
speed_kmh=v_new*3.6
q_cls={"GOOD":"kv-green","PATCHY":"kv-amber","POOR":"kv-red"}[quality]
st_cls="kv-red" if enforce_stop else ("kv-amber" if crash else "kv-green")
st_lbl="🛑 STOP" if enforce_stop else ("⚠ RISK" if crash else "NOMINAL")
spd_cls="kv-amber" if (tsr_here and speed_kmh>tsr_here) else "kv-cyan"

st.markdown(f"""
<div class="kpi-bar">
  <div class="kpi"><span class="kpi-label">Status</span><span class="kpi-value {st_cls}">{st_lbl}</span></div>
  <div class="kpi"><span class="kpi-label">Coverage</span><span class="kpi-value {q_cls}">{quality}</span></div>
  <div class="kpi"><span class="kpi-label">Bearer</span><span class="kpi-value kv-blue">{bearer}</span></div>
  <div class="kpi"><span class="kpi-label">Speed</span><span class="kpi-value {spd_cls}">{speed_kmh:.0f} km/h</span></div>
  <div class="kpi"><span class="kpi-label">Latency</span><span class="kpi-value kv-cyan">{int(lat_ms)} ms</span></div>
  <div class="kpi"><span class="kpi-label">Lane-A</span><span class="kpi-value kv-green">{laneA_success*100:.0f}%</span></div>
  <div class="kpi"><span class="kpi-label">Capacity</span><span class="kpi-value kv-purple">{cap_bps//1000:,} kbps</span></div>
  <div class="kpi"><span class="kpi-label">Segment</span><span class="kpi-value" style="font-size:10px;color:#8B949E">{seg}</span></div>
  <div class="kpi"><span class="kpi-label">Time</span><span class="kpi-value kv-amber">{t}s / {SECS}s</span></div>
</div>
""",unsafe_allow_html=True)

# Progress bar
pct=int(t/max(SECS-1,1)*100)
st.markdown(f'<div class="prog-wrap"><div class="prog-fill" style="width:{pct}%"></div></div>',
            unsafe_allow_html=True)

# Time slider
if st.session_state.playing:
    st.slider("t",0,SECS-1,t,disabled=True,label_visibility="collapsed")
else:
    new_t=st.slider("t",0,SECS-1,t,label_visibility="collapsed")
    if new_t!=t: st.session_state.t_idx=new_t

# ── Tabs ──────────────────────────────────────────────────────────────────
tab_map,tab_tele,tab_flow,tab_ops=st.tabs(["🗺 Maps","📡 Telemetry","🔀 Comm Flow","🔧 Ops"])

# ═══ TAB 1 — MAPS ════════════════════════════════════════════════════════
with tab_map:
    map_col,side_col=st.columns([3,1],gap="medium")

    with side_col:
        st.markdown("<div class='sec-hdr'>Legend</div>",unsafe_allow_html=True)
        legend_items=[
            ("#3DD68C","GOOD coverage"),("#F0A500","PATCHY coverage"),
            ("#E05A5A","POOR coverage"),("#58A6FF","Sensor RAW"),
            ("#39D0D8","Sensor HYBRID"),("#B388FF","Sensor SEMANTIC"),
            ("#F0B914","TSR zone"),("#58A6FF","Base station"),
        ]
        html="".join(f'<div class="legend-item"><div class="dot" style="background:{c}"></div>{l}</div>'
                     for c,l in legend_items)
        st.markdown(f'<div class="legend">{html}</div>',unsafe_allow_html=True)

        st.markdown("<div class='sec-hdr'>Lane-A Alerts</div>",unsafe_allow_html=True)
        if st.session_state.alerts_feed:
            for a in reversed(st.session_state.alerts_feed[-5:]):
                cls="high" if a["severity"]=="high" else ""
                st.markdown(
                    f'<div class="alert-row {cls}">t={a["t"]}s &nbsp;{a["sid"]}<br>'
                    f'{a["severity"].upper()} conf={a["conf"]}%<br>'
                    f'T={a["temp"]}°C &nbsp;S={a["strain"]} kN</div>',
                    unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='font-family:IBM Plex Mono;font-size:11px;"
                        f"color:{PAL['muted']}'>No alerts yet.</div>",unsafe_allow_html=True)

        st.markdown("<div class='sec-hdr'>Sensor Risks</div>",unsafe_allow_html=True)
        aff=sensors[sensors["label"]!="low"][["sid","label","score","qualS","modality","temp"]].copy()
        if aff.empty:
            st.markdown(f"<div style='font-family:IBM Plex Mono;font-size:11px;"
                        f"color:{PAL['muted']}'>All nominal.</div>",unsafe_allow_html=True)
        else:
            aff=aff.sort_values("score",ascending=False)
            aff["score"]=(aff["score"]*100).round(0).astype(int).astype(str)+"%"
            aff.columns=["ID","Risk","Score","Link","Mode","T°C"]
            st.dataframe(aff,use_container_width=True,height=190,hide_index=True)

        if st.session_state.tsr_real:
            n_r=len(st.session_state.tsr_real); n_t=len(st.session_state.tsr_tms)
            diff=n_r-n_t
            cls="s-crit" if diff>0 else "s-ok"
            msg=f"⚠ {diff} TSR(s) unknown to TMS" if diff>0 else f"✓ TMS aware of all {n_r} TSR(s)"
            st.markdown(f'<div class="{cls}" style="margin-top:10px">{msg}</div>',
                        unsafe_allow_html=True)
        if enforce_stop:
            st.markdown('<div class="s-crit" style="margin-top:6px">🛑 STOP ORDER ACTIVE</div>',
                        unsafe_allow_html=True)

    with map_col:
        # Static layers (cached)
        step=max(1,SECS//400)
        path_coords_tuple=tuple((float(route_df.lon.iloc[i]),float(route_df.lat.iloc[i]))
                                 for i in range(0,SECS,step))
        track_layer,bs_layer,rings_layer,path_coords=build_layers_cached(
            path_coords_tuple, SECS)

        # PERF-3: heat index cached
        heat_j=build_heat_index(path_coords_tuple,s_lats,s_lons)
        lbls=sensors["label"].values[heat_j]
        cmap={"low":C["good"][:3]+[100],"medium":C["patchy"][:3]+[150],"high":C["poor"][:3]+[190]}
        heat_rows=[]
        for i in range(len(path_coords)-1):
            c=cmap.get(lbls[i],C["good"][:3]+[100])
            heat_rows.append({"path":[path_coords[i],path_coords[i+1]],
                               "cr":c[0],"cg":c[1],"cb":c[2],"ca":c[3]})
        heat_df=pd.DataFrame(heat_rows)
        heat_layer=pdk.Layer("PathLayer",data=heat_df,get_path="path",
                             get_color="[cr,cg,cb,ca]",width_min_pixels=5,width_scale=3)

        # Dynamic sensor dots
        def s_color(r):
            m=getattr(r,"modality","RAW")
            if m=="RAW":      return C["raw"]
            if m=="HYBRID":   return C["hybrid"]
            if m=="SEMANTIC": return C["semantic"]
            return {"GOOD":C["good"],"PATCHY":C["patchy"],"POOR":C["poor"]}.get(
                getattr(r,"qualS","GOOD"),C["good"])
        sens_rows=[]
        for r in sensors.itertuples():
            c=s_color(r); lbl=getattr(r,"label","low")
            rad=2200 if lbl=="high" else (1800 if lbl=="medium" else 1400)
            sens_rows.append({"lat":float(r.lat),"lon":float(r.lon),"sid":r.sid,
                               "cr":c[0],"cg":c[1],"cb":c[2],"ca":c[3],"radius":rad,
                               "tooltip":f"{r.sid} | {lbl} | {getattr(r,'qualS','')} | {getattr(r,'modality','')}"})
        sens_df=pd.DataFrame(sens_rows)
        s_layer=pdk.Layer("ScatterplotLayer",data=sens_df,get_position="[lon,lat]",
                           get_fill_color="[cr,cg,cb,ca]",get_radius="radius",
                           radius_min_pixels=4,radius_max_pixels=14,
                           stroked=True,get_line_color=[255,255,255,80],
                           line_width_min_pixels=1,pickable=True)
        txt_layer=pdk.Layer("TextLayer",data=sens_df,get_position="[lon,lat]",
                            get_text="sid",get_size=11,get_color=[220,220,220,200],
                            get_pixel_offset=[0,-18],size_units="pixels")

        # TSR layer
        def make_tsr_layer(lst):
            if not lst:
                return pdk.Layer("PolygonLayer",data=[],get_polygon="polygon",
                                 get_fill_color=[0,0,0,0])
            return pdk.Layer("PolygonLayer",
                             data=[{"polygon":p["polygon"],
                                    "tooltip":f"TSR {p['speed']}km/h{'  🛑 STOP' if p.get('stop') else ''}"}
                                   for p in lst],
                             get_polygon="polygon",
                             get_fill_color=C["gold"],get_line_color=C["gold_ln"],
                             stroked=True,filled=True,line_width_min_pixels=2,pickable=True)

        # Train
        halo_c={"GOOD":C["good"],"PATCHY":C["patchy"],"POOR":C["poor"]}.get(quality,C["good"])
        halo_df=pd.DataFrame([{"lat":trainA[0],"lon":trainA[1],
                                "cr":halo_c[0],"cg":halo_c[1],"cb":halo_c[2],"ca":55}])
        halo_l=pdk.Layer("ScatterplotLayer",data=halo_df,get_position="[lon,lat]",
                          get_fill_color="[cr,cg,cb,ca]",get_radius=1600,
                          radius_min_pixels=8,radius_max_pixels=22)
        train_df=pd.DataFrame([{"lat":trainA[0],"lon":trainA[1],
                                 "icon":{"url":"https://img.icons8.com/emoji/96/railway-car.png",
                                         "width":96,"height":96,"anchorY":96}}])
        icon_l=pdk.Layer("IconLayer",data=train_df,get_position="[lon,lat]",
                          get_icon="icon",get_size=4,size_scale=12)

        view=pdk.ViewState(latitude=60.7,longitude=17.5,zoom=6.2,pitch=0)
        MAP_STYLE="https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json"
        TOOLTIP={"html":"<b>{tooltip}</b>",
                 "style":{"background":"rgba(13,17,23,.92)","color":"#E6EDF3",
                          "font-family":"IBM Plex Mono","font-size":"11px",
                          "border-radius":"6px","padding":"6px 10px"}}

        def make_deck(tsr_list):
            return pdk.Deck(
                layers=[rings_layer,track_layer,heat_layer,
                        make_tsr_layer(tsr_list),
                        bs_layer,halo_l,s_layer,txt_layer,icon_l],
                initial_view_state=view,map_style=MAP_STYLE,tooltip=TOOLTIP)

        rw_col,tms_col=st.columns(2,gap="small")
        with rw_col:
            st.markdown('<div class="map-lbl">⬤ Real World</div>',unsafe_allow_html=True)
            st.pydeck_chart(make_deck(st.session_state.tsr_real),
                            use_container_width=True,height=500)
        with tms_col:
            st.markdown('<div class="map-lbl map-lbl-tms">⬤ TMS View</div>',
                        unsafe_allow_html=True)
            st.pydeck_chart(make_deck(st.session_state.tsr_tms),
                            use_container_width=True,height=500)

# ═══ TAB 2 — TELEMETRY ══════════════════════════════════════════════════
with tab_tele:
    c1,c2=st.columns(2,gap="medium")
    with c1:
        st.markdown("<div class='sec-hdr'>Throughput (bps)</div>",unsafe_allow_html=True)
        fig=go.Figure()
        for nm,key,col in [("RAW","raw",CHART_COLORS[0]),("Lane-A","laneA",CHART_COLORS[1]),
                            ("Lane-B","laneB",CHART_COLORS[2]),("Capacity","cap",CHART_COLORS[3])]:
            fig.add_scatter(x=x,y=series(key),name=nm,mode="lines",
                            line=dict(color=col,width=1.5))
        fig.add_vline(x=t,line_width=1,line_dash="dash",line_color="#8B949E")
        fig.update_layout(height=230,**CHART_LAYOUT)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

    with c2:
        st.markdown("<div class='sec-hdr'>Speed & Latency</div>",unsafe_allow_html=True)
        fig2=go.Figure()
        fig2.add_scatter(x=x,y=series("speed"),name="Speed (km/h)",mode="lines",
                         line=dict(color=CHART_COLORS[0],width=1.5))
        fig2.add_scatter(x=x,y=series("lat_ms"),name="Latency (ms)",mode="lines",
                         line=dict(color=CHART_COLORS[1],width=1.5),yaxis="y2")
        fig2.add_vline(x=t,line_width=1,line_dash="dash",line_color="#8B949E")
        fig2.update_layout(height=230,yaxis2=dict(overlaying="y",side="right",
                           gridcolor="#21262D",title="ms",color="#8B949E"),**CHART_LAYOUT)
        st.plotly_chart(fig2,use_container_width=True,config={"displayModeBar":False})

    c3,c4=st.columns(2,gap="medium")
    with c3:
        st.markdown("<div class='sec-hdr'>SNR & Lane-A Success</div>",unsafe_allow_html=True)
        fig3=go.Figure()
        fig3.add_scatter(x=x,y=series("snr"),name="SNR (dB)",mode="lines",
                         line=dict(color=CHART_COLORS[4],width=1.5))
        fig3.add_scatter(x=x,y=series("succ"),name="Lane-A (%)",mode="lines",
                         line=dict(color=CHART_COLORS[2],width=1.5),yaxis="y2")
        fig3.add_vline(x=t,line_width=1,line_dash="dash",line_color="#8B949E")
        fig3.update_layout(height=230,yaxis2=dict(overlaying="y",side="right",
                           gridcolor="#21262D",range=[0,100],title="%",color="#8B949E"),
                           **CHART_LAYOUT)
        st.plotly_chart(fig3,use_container_width=True,config={"displayModeBar":False})

    with c4:
        st.markdown("<div class='sec-hdr'>Live KPIs</div>",unsafe_allow_html=True)
        mc1,mc2=st.columns(2)
        mc1.metric("SNR",f"{snr_use:.1f} dB")
        mc2.metric("Bearer",bearer)
        mc1.metric("Capacity",f"{cap_bps//1000:,} kbps")
        mc2.metric("Load",f"{bps_total//1000:,} kbps")
        mc1.metric("Dual Conn.","ON" if secondary else "OFF")
        mc2.metric("HO Gap","YES" if in_gap else "NO")
        mc1.metric("TSR zones",str(len(st.session_state.tsr_real)))
        mc2.metric("Alerts",str(len(laneA_alerts)))

# ═══ TAB 3 — COMM FLOW ══════════════════════════════════════════════════
with tab_flow:
    st.markdown("<div class='sec-hdr'>Data Flow — Sensors → BS → TMS → Train</div>",
                unsafe_allow_html=True)
    s_to_bs=max(1,bps_total); to_train=max(1,laneA_bps+laneB_bps)
    to_maint=max(1,laneB_bps or 100)
    nodes=["Sensors",f"BS ({bearer})","Core Net","TMS","Train DAS","Maintenance"]
    ni={n:i for i,n in enumerate(nodes)}
    node_colors=["#3DD68C","#58A6FF","#39D0D8","#F0A500","#B388FF","#E05A5A"]
    sankey=go.Sankey(
        node=dict(label=nodes,pad=22,thickness=16,color=node_colors,
                  line=dict(color=PAL["border"],width=0.5)),
        link=dict(
            source=[ni["Sensors"],ni[f"BS ({bearer})"],ni["Core Net"],ni["TMS"],ni["TMS"]],
            target=[ni[f"BS ({bearer})"],ni["Core Net"],ni["TMS"],ni["Train DAS"],ni["Maintenance"]],
            value=[s_to_bs,s_to_bs,s_to_bs,to_train,to_maint],
            label=["uplink","backhaul","to TMS","advisories/TSR","work orders"],
            color=["rgba(57,208,216,.35)","rgba(57,208,216,.28)","rgba(57,208,216,.28)",
                   "rgba(240,165,0,.35)","rgba(61,214,140,.35)"],
        ),
    )
    fig_sk=go.Figure(sankey)
    fig_sk.update_layout(height=400,**CHART_LAYOUT)
    st.plotly_chart(fig_sk,use_container_width=True,config={"displayModeBar":False})
    c1,c2,c3,c4=st.columns(4)
    c1.metric("RAW bps",f"{raw_bps_delivered:,}")
    c2.metric("Lane-A bps",f"{laneA_bps:,}")
    c3.metric("Lane-B bps",f"{laneB_bps:,}")
    c4.metric("Cap kbps",f"{cap_bps//1000:,}")

# ═══ TAB 4 — OPS ════════════════════════════════════════════════════════
with tab_ops:
    st.markdown("<div class='sec-hdr'>Status</div>",unsafe_allow_html=True)
    if enforce_stop:
        st.markdown('<div class="s-crit">🛑 STOP ORDER in effect (TMS view)</div>',
                    unsafe_allow_html=True)
    unknown=[p for p in st.session_state.tsr_real
             if _poly_key(p["polygon"]) not in tms_keys]
    if unknown:
        st.markdown(f'<div class="s-warn">⚠ {len(unknown)} real TSR(s) not yet in TMS — '
                    f'potential missed alert</div>',unsafe_allow_html=True)
    if not enforce_stop and not unknown:
        st.markdown('<div class="s-ok">✓ All clear — no unresolved discrepancies</div>',
                    unsafe_allow_html=True)

    # Work orders
    for w in st.session_state.work_orders:
        if w["status"]=="Dispatched" and t>=w.get("eta_done_idx",9e9):
            w["status"]="Resolved"
    resolved={_poly_key(w["polygon"]) for w in st.session_state.work_orders
              if w["status"]=="Resolved"}
    st.session_state.tsr_real=[p for p in st.session_state.tsr_real
                                if _poly_key(p["polygon"]) not in resolved]
    st.session_state.tsr_tms=[p for p in st.session_state.tsr_tms
                               if _poly_key(p["polygon"]) not in resolved]

    st.markdown("<div class='sec-hdr'>Work Orders</div>",unsafe_allow_html=True)
    if st.session_state.work_orders:
        rows=[dict(ID=f"WO-{i+1:03d}",Status=w["status"],
                   Created=w.get("created_idx","—"),ETA=w.get("eta_done_idx","—"))
              for i,w in enumerate(st.session_state.work_orders)]
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else:
        st.markdown(f"<div style='font-family:IBM Plex Mono;font-size:12px;"
                    f"color:{PAL['muted']}'>No active work orders.</div>",
                    unsafe_allow_html=True)

    st.markdown("<div class='sec-hdr'>Active TSR Zones</div>",unsafe_allow_html=True)
    if st.session_state.tsr_real:
        tms_k=_tsr_key_set(st.session_state.tsr_tms)
        for i,p in enumerate(st.session_state.tsr_real):
            in_tms=_poly_key(p["polygon"]) in tms_k
            clr=PAL["green"] if in_tms else PAL["red"]
            icon="✓" if in_tms else "✗"
            st.markdown(
                f"<div style='font-family:IBM Plex Mono;font-size:11px;color:{clr};padding:3px 0'>"
                f"{icon} TSR-{i+1:02d} &nbsp;{p['speed']} km/h"
                f"{'&nbsp; 🛑 STOP' if p.get('stop') else ''}"
                f"{'&nbsp; [TMS aware]' if in_tms else '&nbsp; [TMS unaware]'}"
                f"</div>",unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='font-family:IBM Plex Mono;font-size:11px;"
                    f"color:{PAL['muted']}'>No active TSR zones.</div>",
                    unsafe_allow_html=True)
