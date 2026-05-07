import math

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from shapely.geometry import LineString, Point

from ensure6g.theme import C

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
