"""
Early Alarm: festival-ready fix list (Datathon 2026, Track 3: Smart City)

Run:   streamlit run app.py
Needs: locations.csv, incidents.csv, public_complaints.csv in the same folder
       (or in ./data). Synthetic data only. Not for real public safety decisions.

One scoring engine, three views (+ a Trust & limits tab):
  1. City view       -> ranked list + map + "why this rank" panel
  2. Event planner   -> pick a place and date, see verdict + fixes that must happen first
  3. Commercial view -> suitability for shops/ads (NOT a sales prediction)
  4. Trust & limits  -> noise check, weight-sensitivity check, guard rails
"""

import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="Early Alarm", page_icon="🚨", layout="wide")

# ----------------------------------------------------------------------------
# Look & feel: pre-dusk festival night. Indigo base, marigold = the alarm.
# (Also see .streamlit/config.toml so sliders/buttons pick up the same accent.)
# ----------------------------------------------------------------------------
NIGHT, NIGHT_DEEP, PANEL, LINE = "#121936", "#0C1128", "#1B2347", "#2E3868"
MARIGOLD, VERMILION, TEAL, INK, MUTED = "#FFB224", "#FF5C4D", "#34D1BF", "#EEF1FF", "#9AA5D1"

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'IBM Plex Sans', system-ui, sans-serif; }}
.stApp {{ background: radial-gradient(1200px 500px at 70% -10%, #26306a 0%, {NIGHT} 55%, {NIGHT_DEEP} 100%); color: {INK}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; }}
.block-container {{ padding-top: 1.6rem; max-width: 1400px; }}
h1, h2, h3, h4 {{ font-family: 'Bricolage Grotesque', sans-serif !important; letter-spacing: -0.01em; color: {INK}; }}
h3 {{ font-weight: 700; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: {NIGHT_DEEP}; border-right: 1px solid {LINE}; }}
[data-testid="stSidebar"] h2 {{ font-size: 1.05rem; color: {MARIGOLD}; margin-top: 0.4rem; }}
.brand {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 1.5rem; color: {INK}; padding: 0.2rem 0 0.6rem; }}
.brand span {{ color: {MARIGOLD}; }}

/* tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 0.4rem; border-bottom: 1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{ background: transparent; border-radius: 10px 10px 0 0; padding: 0.55rem 1.1rem; color: {MUTED}; font-weight: 600; }}
.stTabs [aria-selected="true"] {{ color: {MARIGOLD} !important; background: {PANEL}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: {MARIGOLD}; }}

/* metrics */
[data-testid="stMetric"] {{ background: {PANEL}; border: 1px solid {LINE}; border-left: 4px solid {MARIGOLD}; border-radius: 10px; padding: 0.7rem 1rem; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; }}
[data-testid="stMetricValue"] {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700; }}

/* tables, alerts, buttons */
[data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 10px; overflow: hidden; }}
[data-testid="stAlert"] {{ border-radius: 10px; }}
.stDownloadButton button {{ background: {MARIGOLD}; color: #1a1300; border: 0; font-weight: 600; border-radius: 8px; }}
.stDownloadButton button:hover {{ filter: brightness(1.08); color: #1a1300; }}
hr {{ border-color: {LINE}; }}

/* hero: the countdown to the festival is the one memorable thing on the page */
.hero {{ display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 2rem; align-items: center;
  background: linear-gradient(135deg, {PANEL} 0%, #232d5e 100%); border: 1px solid {LINE}; border-radius: 16px; padding: 1.6rem 2rem; margin-bottom: 1.2rem; }}
.hero h1 {{ font-size: 2.6rem; font-weight: 800; line-height: 1.05; margin: 0 0 0.5rem; padding: 0; }}
.hero p {{ color: {MUTED}; margin: 0; max-width: 46ch; line-height: 1.5; }}
.count {{ display: flex; align-items: baseline; gap: 0.6rem; }}
.count .num {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 4.6rem; line-height: 1; color: {MARIGOLD}; }}
.count .lbl {{ color: {INK}; font-size: 1.05rem; font-weight: 500; }}
.chip {{ display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.25rem 0.7rem; border-radius: 999px; font-size: 0.82rem; font-weight: 600; margin-top: 0.5rem; }}
.chip.open {{ background: rgba(255,92,77,0.16); color: {VERMILION}; }}
.chip.wait {{ background: rgba(52,209,191,0.14); color: {TEAL}; }}
.chip.off {{ background: rgba(154,165,209,0.14); color: {MUTED}; }}
.dot {{ width: 8px; height: 8px; border-radius: 50%; background: currentColor; }}
.chip.open .dot {{ animation: pulse 1.4s ease-out infinite; }}
@keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(255,92,77,0.7); }} 100% {{ box-shadow: 0 0 0 10px rgba(255,92,77,0); }} }}
@media (prefers-reduced-motion: reduce) {{ .chip.open .dot {{ animation: none; }} }}
.track {{ position: relative; height: 14px; border-radius: 7px; background: #0C1128; margin: 1.1rem 0 0.4rem; }}
.track .win {{ position: absolute; top: 0; bottom: 0; border-radius: 7px; background: linear-gradient(90deg, rgba(255,178,36,0.35), {MARIGOLD}); }}
.track .now {{ position: absolute; top: -5px; width: 4px; height: 24px; border-radius: 2px; background: {INK}; }}
.ticks {{ display: flex; justify-content: space-between; color: {MUTED}; font-size: 0.78rem; }}
@media (max-width: 900px) {{ .hero {{ grid-template-columns: 1fr; }} .hero h1 {{ font-size: 2rem; }} }}

/* verdict banner (Event planner) */
.verdict {{ border-radius: 12px; padding: 1rem 1.3rem; background: {PANEL}; border: 1px solid {LINE}; border-left: 8px solid var(--c); margin: 0.4rem 0 1rem; }}
.verdict .t {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 1.5rem; color: var(--c); }}
.verdict .d {{ color: {MUTED}; margin-top: 0.2rem; }}
</style>
""",
    unsafe_allow_html=True,
)


def hero_html(fest_name, fest_date, today, window_days, festival_on):
    if not (festival_on and fest_date is not None):
        return (
            '<div class="hero"><div><h1>Early Alarm</h1>'
            "<p>Where should we fix first? A ranked fix list with the reasons and the confidence behind every rank.</p></div>"
            '<div><span class="chip off"><span class="dot"></span>Festival mode is off</span></div></div>'
        )
    days_to = (fest_date - today).days
    if days_to < 0:
        num, lbl, chip = "–", f"{fest_name} has passed", '<span class="chip off"><span class="dot"></span>Pick the next festival</span>'
        bar = ""
    else:
        span = max(days_to, window_days, 1)
        now_pos = (span - days_to) / span * 100
        win_pos = (span - window_days) / span * 100
        is_open = days_to <= window_days
        num = str(days_to)
        lbl = f"day{'s' if days_to != 1 else ''} to {fest_name}"
        chip = (
            f'<span class="chip open"><span class="dot"></span>Fix window open: act now</span>'
            if is_open
            else f'<span class="chip wait"><span class="dot"></span>Window opens in {days_to - window_days} days</span>'
        )
        bar = (
            f'<div class="track"><div class="win" style="left:{win_pos:.1f}%;right:0"></div>'
            f'<div class="now" style="left:calc({min(now_pos, 98):.1f}% )"></div></div>'
            f'<div class="ticks"><span>Today</span><span>{window_days}-day window</span><span>{fest_date:%d %b}</span></div>'
        )
    return (
        '<div class="hero"><div><h1>Early Alarm</h1>'
        "<p>Where should we fix first? A festival-ready fix list: what to repair, why it ranks, and how sure we are, before the crowd arrives.</p></div>"
        f'<div><div class="count"><span class="num">{num}</span><span class="lbl">{lbl}</span></div>{chip}{bar}</div></div>'
    )


def verdict_html(title, detail, color):
    return f'<div class="verdict" style="--c:{color}"><div class="t">{title}</div><div class="d">{detail}</div></div>'

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
SEV_POINTS = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
PED_POINTS = {"Low": 0.0, "Medium": 0.5, "High": 1.0}
OPEN_STATUSES = ["Open", "Assigned", "In progress"]  # Resolved / Closed = done

# Road access for the Commercial view (design assumption, not learned)
ROAD_TYPE_ACCESS = {"Highway": 0.6, "Arterial": 1.0, "Collector": 0.8, "Local": 0.5, "Residential": 0.4}
ROAD_COND_ACCESS = {"Good": 1.0, "Fair": 0.75, "Poor": 0.4, "Critical": 0.1}

# What a crew actually has to do for each incident type
FIX_ACTION = {
    "Streetlight outage": "Repair / replace streetlight",
    "Signal failure": "Fix traffic signal",
    "Pothole": "Patch / resurface pothole",
    "Blocked drain": "Clear blocked drain",
    "Collision": "Review junction safety (signage, barriers, markings)",
    "Flooding": "Fix drainage / pre-clear waterlogging",
}

# Festival calendar. NOT learned from data: lunar dates move every year.
# Dates below were filled from general knowledge: VERIFY before presenting. Editable in the sidebar.
DEFAULT_FESTIVALS = pd.DataFrame(
    {
        "festival": [
            "Dussehra",
            "Diwali",
            "Christmas",
            "New Year's Eve",
            "Makar Sankranti",
            "Republic Day",
            "Maha Shivaratri",
            "Holi",
            "Independence Day",
        ],
        "date": [
            date(2026, 10, 20),
            date(2026, 11, 8),
            date(2026, 12, 25),
            date(2026, 12, 31),
            date(2027, 1, 14),
            date(2027, 1, 26),
            date(2027, 3, 6),
            date(2027, 3, 22),
            date(2027, 8, 15),
        ],
    }
)

# ----------------------------------------------------------------------------
# Data loading + per-location features
# ----------------------------------------------------------------------------
# If the app can't find your CSVs, paste the folder path here, e.g. r"D:/Datathon 2026/data"
DATA_DIR = ""


def find_data_dir() -> str | None:
    here = Path(__file__).resolve().parent
    cands = [Path(DATA_DIR)] if DATA_DIR else []
    cands += [Path("."), Path("data"), here, here / "data", here.parent, here.parent / "data"]
    for c in cands:
        if (c / "locations.csv").exists():
            return str(c)
    # last resort: look one or two folders down from the app and its parent
    for base in (here, here.parent):
        for hit in list(base.glob("*/locations.csv")) + list(base.glob("*/*/locations.csv")):
            return str(hit.parent)
    return None


@st.cache_data
def load_raw(data_dir: str):
    d = Path(data_dir)
    loc = pd.read_csv(d / "locations.csv")
    inc = pd.read_csv(d / "incidents.csv", parse_dates=["timestamp"])
    com = pd.read_csv(d / "public_complaints.csv", parse_dates=["created_at"])
    inc["sev_pts"] = inc["severity"].map(SEV_POINTS)
    inc["is_open"] = inc["resolved"] == 0
    inc["is_serious"] = inc["severity"].isin(["High", "Critical"])
    com["is_open"] = com["status"].isin(OPEN_STATUSES)
    return loc, inc, com


@st.cache_data
def build_features(data_dir: str) -> pd.DataFrame:
    loc, inc, com = load_raw(data_dir)
    ids = loc["location_id"]

    g = inc.groupby("location_id")
    f_inc = pd.DataFrame(
        {
            "n_inc": g.size(),
            "sev_sum": g["sev_pts"].sum(),
            "n_open_inc": g["is_open"].sum(),
        }
    )
    f_inc["n_open_serious"] = (
        inc[inc["is_open"] & inc["is_serious"]].groupby("location_id").size()
    )
    gc = com.groupby("location_id")
    f_com = pd.DataFrame({"n_comp": gc.size(), "n_open_comp": gc["is_open"].sum()})

    F = (
        loc.set_index("location_id")
        .join(f_inc)
        .join(f_com)
        .reindex(ids)
        .fillna({"n_inc": 0, "sev_sum": 0, "n_open_inc": 0, "n_open_serious": 0, "n_comp": 0, "n_open_comp": 0})
        .reset_index()
    )
    for c in ["n_inc", "sev_sum", "n_open_inc", "n_open_serious", "n_comp", "n_open_comp"]:
        F[c] = F[c].astype(int)

    # consequence ingredients (all 0..1)
    F["near_school"] = F["near_school"].astype(int)
    F["near_hospital"] = F["near_hospital"].astype(int)
    F["ped"] = F["pedestrian_activity"].map(PED_POINTS).astype(float)
    d = F["population_density_per_km2"].astype(float)
    F["dens_n"] = (d - d.min()) / (d.max() - d.min() + 1e-9)
    # crowd exposure: who gets hurt if a festival crowd hits a bad spot
    F["exposure"] = (F["near_school"] + (F["pedestrian_activity"] == "High").astype(int) + F["dens_n"]) / 3
    return F


# ----------------------------------------------------------------------------
# Scoring engine
# ----------------------------------------------------------------------------
def _norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return (x - x.min()) / (x.max() - x.min() + 1e-9)


def score_parts(F: pd.DataFrame, w: dict, shrink: float, crowd_mult: float, festival_on: bool):
    """
    score = (w_inc*incident_severity + w_oi*open_incidents + w_oc*open_complaints) * (1 + consequence)

    - incident_severity: severity-weighted count, shrunk toward the city average (empirical-Bayes style):
        est = mean + (1 - shrink) * (observed - mean)
      shrink=0 keeps raw counts, shrink=1 ignores a location's own history completely.
    - consequence: school/hospital/pedestrian/density weights. In festival mode it is boosted by
      (1 + (crowd_mult - 1) * exposure), so high-crowd places get up to crowd_mult times more weight.
    Returns arrays on a 0-100 scale (scaled so the top location is 100).
    """
    mu = F["sev_sum"].mean()
    inc_est = mu + (1 - shrink) * (F["sev_sum"].values - mu)
    inc_n = _norm(inc_est)
    oi_n = _norm(F["n_open_inc"].values)
    oc_n = _norm(F["n_open_comp"].values)

    cons = (
        w["school"] * F["near_school"].values
        + w["hosp"] * F["near_hospital"].values
        + w["ped"] * F["ped"].values
        + w["dens"] * F["dens_n"].values
    )
    if festival_on:
        cons = cons * (1 + (crowd_mult - 1) * F["exposure"].values)

    p_inc, p_oi, p_oc = w["inc"] * inc_n, w["oi"] * oi_n, w["oc"] * oc_n
    base = p_inc + p_oi + p_oc
    raw = base * (1 + cons)
    scale = 100.0 / (raw.max() + 1e-9)
    return {
        "score": raw * scale,
        "c_inc": p_inc * scale,
        "c_oi": p_oi * scale,
        "c_oc": p_oc * scale,
        "c_cons": base * cons * scale,
        "cons": cons,
    }


def poisson_sf(k: int, mu: float) -> float:
    """P(X >= k) for X ~ Poisson(mu). Pure python so no scipy needed."""
    if k <= 0:
        return 1.0
    term = math.exp(-mu)
    cdf = term
    for i in range(1, k):
        term *= mu / i
        cdf += term
    return max(0.0, 1.0 - cdf)


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = pd.Series(a).rank().values
    rb = pd.Series(b).rank().values
    return float(np.corrcoef(ra, rb)[0, 1])


def perturbed_runs(F, w, shrink, crowd_mult, festival_on, pct, n_runs, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_runs):
        w2 = {k: v * rng.uniform(1 - pct, 1 + pct) for k, v in w.items()}
        out.append(score_parts(F, w2, shrink, crowd_mult, festival_on)["score"])
    return np.array(out)


@st.cache_data(show_spinner=False)
def stability(_F, w_items, shrink, crowd_mult, festival_on, top_n):
    """Share of random +/-20% weight wiggles in which each location stays in the top N."""
    w = dict(w_items)
    runs = perturbed_runs(_F, w, shrink, crowd_mult, festival_on, 0.20, 150)
    ranks = np.argsort(np.argsort(-runs, axis=1), axis=1)  # 0 = best
    return (ranks < top_n).mean(axis=0)


@st.cache_data(show_spinner=False)
def sensitivity_table(_F, w_items, shrink, crowd_mult, festival_on, top_n):
    w = dict(w_items)
    base = score_parts(_F, w, shrink, crowd_mult, festival_on)["score"]
    base_top = set(np.argsort(-base)[:top_n])
    rows = []
    for pct in (0.05, 0.10, 0.20):
        runs = perturbed_runs(_F, w, shrink, crowd_mult, festival_on, pct, 100, seed=int(pct * 100))
        rhos = [spearman(base, r) for r in runs]
        overlaps = [len(base_top & set(np.argsort(-r)[:top_n])) / top_n for r in runs]
        rows.append(
            {
                "Weights moved by": f"±{int(pct * 100)}%",
                "Avg Spearman (full ranking)": round(float(np.mean(rhos)), 3),
                f"Avg top-{top_n} overlap": f"{np.mean(overlaps) * 100:.0f}%",
                f"Worst top-{top_n} overlap": f"{np.min(overlaps) * 100:.0f}%",
            }
        )
    return pd.DataFrame(rows)


def conf_label(share: float) -> str:
    return "High" if share >= 0.8 else ("Medium" if share >= 0.5 else "Low")


# ----------------------------------------------------------------------------
# Explanations
# ----------------------------------------------------------------------------
def explain(r: pd.Series) -> str:
    bits = [
        f"{int(r.n_inc)} incidents in 2025 ({int(r.n_open_inc)} still unresolved, "
        f"{int(r.n_open_serious)} of those High/Critical) and {int(r.n_open_comp)} open complaints."
    ]
    cons = []
    if r.near_school:
        cons.append("near a school")
    if r.near_hospital:
        cons.append("near a hospital")
    if r.pedestrian_activity != "Low":
        cons.append(f"{r.pedestrian_activity.lower()} pedestrian activity")
    if r.population_density_per_km2 > 0:
        cons.append(f"{int(r.population_density_per_km2):,} people/km²")
    bits.append("Consequence if it fails: " + ", ".join(cons) + ".")
    parts = {
        "past incident severity": r.c_inc,
        "unresolved incidents": r.c_oi,
        "open complaints": r.c_oc,
        "consequence uplift": r.c_cons,
    }
    top = max(parts, key=parts.get)
    bits.append(f"Biggest driver of its score: {top}.")
    return " ".join(bits)


def guardrail_flags(r: pd.Series) -> list[str]:
    flags = []
    if r.n_open_serious > 0 and r.near_school:
        flags.append("Open High/Critical incident near a school")
    if r.n_open_serious > 0 and r.near_hospital:
        flags.append("Open High/Critical incident near a hospital")
    if r.near_hospital:
        flags.append("Hospital access must stay clear for any event")
    return flags


# ----------------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------------
data_dir = find_data_dir()
if data_dir is None:
    st.error("Couldn't find locations.csv. Put locations.csv, incidents.csv and public_complaints.csv next to app.py (or in ./data).")
    manual = st.text_input("Or type the folder path that holds the CSVs")
    if manual and (Path(manual) / "locations.csv").exists():
        data_dir = manual
    else:
        st.stop()

F = build_features(data_dir)
loc_raw, inc_raw, com_raw = load_raw(data_dir)

# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.markdown('<div class="brand">Early<span>Alarm</span></div>', unsafe_allow_html=True)
st.sidebar.header("Weights (design choices)")
w = {
    "inc": st.sidebar.slider("Past incidents", 0.0, 2.0, 1.0, 0.05),
    "oi": st.sidebar.slider("Open incidents", 0.0, 2.0, 1.0, 0.05),
    "oc": st.sidebar.slider("Open complaints", 0.0, 2.0, 0.5, 0.05),
    "school": st.sidebar.slider("School nearby", 0.0, 1.0, 0.4, 0.05),
    "hosp": st.sidebar.slider("Hospital nearby", 0.0, 1.0, 0.4, 0.05),
    "ped": st.sidebar.slider("Pedestrian activity", 0.0, 1.0, 0.4, 0.05),
    "dens": st.sidebar.slider("Population density", 0.0, 1.0, 0.3, 0.05),
}
top_n = st.sidebar.slider("List size", 5, 50, 20)
shrink = st.sidebar.slider(
    "Shrinkage of past incidents",
    0.0,
    1.0,
    0.5,
    0.05,
    help="0 = trust each location's own count. 1 = ignore it and use the city average. "
    "Higher = a location with few records is ranked less confidently.",
)

st.sidebar.header("Festival layer")
festival_on = st.sidebar.toggle("Festival mode", value=True)
with st.sidebar.expander("Festival calendar (editable, verify dates)"):
    fest_df = st.data_editor(
        DEFAULT_FESTIVALS,
        num_rows="dynamic",
        hide_index=True,
        key="fest_table",
        column_config={"date": st.column_config.DateColumn("date")},
    )
fest_df = fest_df.dropna(subset=["festival", "date"]).copy()
fest_df["date"] = pd.to_datetime(fest_df["date"]).dt.date
fest_df = fest_df.sort_values("date")

today = st.sidebar.date_input("Today (override for demo)", value=date.today())
upcoming = fest_df[fest_df["date"] >= today]
fest_options = upcoming if len(upcoming) else fest_df
fest_names = [f"{r.festival} ({r.date:%d %b %Y})" for r in fest_options.itertuples()]
fest_choice = st.sidebar.selectbox("Festival", fest_names) if fest_names else None
window_days = st.sidebar.slider("Pre-festival window (days)", 3, 7, 4)
crowd_mult = st.sidebar.slider(
    "Crowd multiplier",
    1.0,
    3.0,
    1.5,
    0.1,
    help="Assumption, not learned from data: how much more consequence weight "
    "high-crowd places (school, high footfall, dense) get during the festival.",
)

fest_date = None
fest_name = None
if fest_choice:
    row = fest_options.iloc[fest_names.index(fest_choice)]
    fest_date, fest_name = row["date"], row["festival"]
    window_start = fest_date - timedelta(days=window_days)
    days_to = (fest_date - today).days
    if days_to < 0:
        st.sidebar.info(f"{fest_name} already passed.")
    elif today >= window_start:
        st.sidebar.warning(f"Window is OPEN: {fest_name} in {days_to} day(s).")
    else:
        st.sidebar.success(
            f"{fest_name} in {days_to} days. Window opens {window_start:%d %b} "
            f"({(window_start - today).days} days from now)."
        )

# ----------------------------------------------------------------------------
# Score everything
# ----------------------------------------------------------------------------
parts = score_parts(F, w, shrink, crowd_mult, festival_on and fest_date is not None)
R = F.copy()
for k in ("score", "c_inc", "c_oi", "c_oc", "c_cons"):
    R[k] = parts[k]
R["rank"] = R["score"].rank(ascending=False, method="first").astype(int)
R["stability"] = stability(F, tuple(w.items()), shrink, crowd_mult, festival_on and fest_date is not None, top_n)
R["confidence"] = R["stability"].map(conf_label)

mu_inc = F["n_inc"].mean()
R["p_noise"] = [min(1.0, poisson_sf(int(k), mu_inc) * len(F)) for k in F["n_inc"]]  # Bonferroni-adjusted
R["beyond_noise"] = np.where(R["p_noise"] < 0.05, "Yes", "No (could be chance)")
R = R.sort_values("rank").reset_index(drop=True)
top = R.head(top_n)

# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.markdown(hero_html(fest_name, fest_date, today, window_days, festival_on), unsafe_allow_html=True)
st.caption("Synthetic data and simulated coordinates. Not for real public safety decisions.")
if festival_on and fest_date is not None:
    st.caption(f"Crowd multiplier {crowd_mult:.1f}x is an assumption set in the sidebar, not something learned from the data.")

tab_city, tab_event, tab_comm, tab_trust = st.tabs(
    ["🏙️ City view", "🎪 Event planner", "🏪 Commercial view", "🛡️ Trust & limits"]
)

# ----------------------------------------------------------------------------
# City view
# ----------------------------------------------------------------------------
with tab_city:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Locations", f"{len(F):,}")
    m2.metric("Incidents (2025)", f"{len(inc_raw):,}")
    m3.metric("Open complaints", f"{int(F['n_open_comp'].sum()):,}")
    m4.metric("Top-list with High confidence", f"{(top['confidence'] == 'High').sum()} / {len(top)}")

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader(f"Top {top_n} locations to fix first")
        show = top[
            ["rank", "location_id", "zone", "road_type", "score", "confidence", "n_open_inc", "n_open_serious", "n_open_comp", "beyond_noise"]
        ].copy()
        show["score"] = show["score"].round(1)
        show["confidence"] = show["confidence"].map({"High": "●●● High", "Medium": "●●○ Medium", "Low": "●○○ Low"})
        st.dataframe(
            show,
            hide_index=True,
            height=420,
            column_config={
                "score": st.column_config.ProgressColumn("score", min_value=0, max_value=100, format="%.1f"),
                "rank": st.column_config.NumberColumn("rank", width="small"),
                "n_open_inc": st.column_config.NumberColumn("open inc."),
                "n_open_serious": st.column_config.NumberColumn("open serious"),
                "n_open_comp": st.column_config.NumberColumn("open compl."),
                "beyond_noise": st.column_config.TextColumn("beyond noise?"),
            },
        )
        st.download_button(
            "Download ranked list (CSV)",
            R[["rank", "location_id", "zone", "road_type", "score", "confidence", "n_inc", "n_open_inc", "n_open_serious", "n_comp", "n_open_comp"]].to_csv(index=False),
            file_name="early_alarm_ranking.csv",
            mime="text/csv",
        )

    with right:
        st.subheader("Map (simulated coordinates)")
        md = top.copy()
        md["radius"] = 250 + md["score"] * 6
        md["halo"] = md["radius"] * 2.4
        pal = {"High": [255, 178, 36], "Medium": [124, 140, 255], "Low": [110, 120, 165]}
        md["color"] = md["confidence"].map(lambda c: pal[c] + [230])
        md["halo_color"] = md["confidence"].map(lambda c: pal[c] + [55])
        md["score_txt"] = md["score"].round(1).astype(str)
        halo = pdk.Layer("ScatterplotLayer", data=md, get_position="[longitude, latitude]", get_radius="halo", get_fill_color="halo_color")
        core = pdk.Layer(
            "ScatterplotLayer",
            data=md,
            get_position="[longitude, latitude]",
            get_radius="radius",
            get_fill_color="color",
            get_line_color=[255, 255, 255, 200],
            stroked=True,
            line_width_min_pixels=1,
            pickable=True,
        )
        view = pdk.ViewState(latitude=float(md["latitude"].mean()), longitude=float(md["longitude"].mean()), zoom=8.5)
        st.pydeck_chart(
            pdk.Deck(
                layers=[halo, core],
                initial_view_state=view,
                map_style="dark",
                tooltip={"text": "#{rank} {location_id} ({zone})\nScore {score_txt}\nConfidence: {confidence}"},
            ),
        )
        st.caption("Dot size = score. Gold = high confidence, blue = medium, grey-blue = low.")

    st.divider()
    st.subheader("Why does this location rank where it does?")
    pick = st.selectbox(
        "Pick a location from the list",
        top["location_id"].tolist(),
        format_func=lambda x: f"#{int(R.loc[R.location_id == x, 'rank'].iloc[0])}  {x}  ({R.loc[R.location_id == x, 'zone'].iloc[0]})",
    )
    r = R[R.location_id == pick].iloc[0]
    e1, e2 = st.columns([1.4, 1])
    with e1:
        st.markdown(f"**Rank #{int(r['rank'])} · score {r.score:.1f} · confidence {r.confidence}**")
        st.write(explain(r))
        st.write(
            f"**Distinguishable from random noise?** {r.beyond_noise}. "
            f"It had {int(r.n_inc)} incidents versus a city average of {mu_inc:.1f}; "
            f"stays in the top {top_n} in {r.stability * 100:.0f}% of random ±20% weight changes."
        )
        for fl in guardrail_flags(r):
            st.warning(fl)
    with e2:
        st.bar_chart(
            pd.DataFrame(
                {
                    "points": [r.c_inc, r.c_oi, r.c_oc, r.c_cons],
                },
                index=["Past incidents", "Open incidents", "Open complaints", "Consequence uplift"],
            ),
            horizontal=True,
            color=MARIGOLD,
        )

    flagged = top[(top["n_open_serious"] > 0) & ((top["near_school"] == 1) | (top["near_hospital"] == 1))]
    if len(flagged):
        with st.expander(f"⚠️ {len(flagged)} locations in the top list have open serious issues near a school or hospital"):
            st.dataframe(
                flagged[["rank", "location_id", "zone", "near_school", "near_hospital", "n_open_serious"]],
                hide_index=True,
            )

# ----------------------------------------------------------------------------
# Event planner
# ----------------------------------------------------------------------------
with tab_event:
    st.subheader("Event planner: can this place host an event, and what must be fixed first?")
    c1, c2 = st.columns(2)
    with c1:
        ev_loc = st.selectbox(
            "Proposed location (sorted by risk)",
            R["location_id"].tolist(),
            format_func=lambda x: f"{x}  ({R.loc[R.location_id == x, 'zone'].iloc[0]}, rank #{int(R.loc[R.location_id == x, 'rank'].iloc[0])})",
            key="ev_loc",
        )
    with c2:
        ev_date = st.date_input("Event date", value=fest_date or today, key="ev_date")

    er = R[R.location_id == ev_loc].iloc[0]
    pct = 100 * (1 - (er["rank"] - 1) / len(R))  # 100 = riskiest
    days_left = (ev_date - today).days

    if er.near_hospital:
        v_title, v_color = "HOLD: keep hospital access clear", VERMILION
    elif er.n_open_serious > 0 or pct >= 90:
        v_title, v_color = "FIX FIRST", VERMILION
    elif pct >= 70:
        v_title, v_color = "READY WITH FIXES", MARIGOLD
    else:
        v_title, v_color = "READY", TEAL
    st.markdown(
        verdict_html(
            v_title,
            f"Risk percentile {pct:.0f} (100 = riskiest) · confidence {er.confidence} · "
            f"{int(er.n_open_serious)} open High/Critical incident(s)",
            v_color,
        ),
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Days until event", days_left)
    k2.metric("Unresolved incidents", int(er.n_open_inc))
    k3.metric("Open complaints", int(er.n_open_comp))
    k4.metric("Road condition", er.road_condition)

    st.write(explain(er))
    for fl in guardrail_flags(er):
        st.warning(fl)
    if days_left < 0:
        st.info("That date is in the past (relative to the 'Today' date in the sidebar).")

    st.markdown("#### Fixes that must happen first")
    open_inc = inc_raw[(inc_raw["location_id"] == ev_loc) & inc_raw["is_open"]].copy()
    fixes = []
    if len(open_inc):
        gi = (
            open_inc.groupby("incident_type")
            .agg(count=("incident_id", "size"), worst=("sev_pts", "max"))
            .reset_index()
            .sort_values(["worst", "count"], ascending=False)
        )
        inv = {v: k for k, v in SEV_POINTS.items()}
        for x in gi.itertuples():
            fixes.append(
                {
                    "Priority": "Must fix" if x.worst >= 3 else "Should fix",
                    "Action": FIX_ACTION.get(x.incident_type, x.incident_type),
                    "Evidence": f"{x.count} unresolved '{x.incident_type}' incident(s), worst severity {inv[x.worst]}",
                }
            )
    if er.road_condition in ("Poor", "Critical"):
        fixes.append(
            {
                "Priority": "Must fix" if er.road_condition == "Critical" else "Should fix",
                "Action": "Repair / resurface road",
                "Evidence": f"Road condition is {er.road_condition} (crowds on bad roads raise consequence)",
            }
        )
    open_com = com_raw[(com_raw["location_id"] == ev_loc) & com_raw["is_open"]]
    if len(open_com):
        for cat, n in open_com["category"].value_counts().items():
            fixes.append({"Priority": "Should fix", "Action": f"Close out '{cat}' complaints", "Evidence": f"{n} open complaint(s)"})
    if fixes:
        fx = pd.DataFrame(fixes)
        fx["_o"] = fx["Priority"].map({"Must fix": 0, "Should fix": 1})
        st.dataframe(fx.sort_values("_o").drop(columns="_o"), hide_index=True)
    else:
        st.success("No unresolved incidents, open complaints or poor road condition on record here.")

    st.markdown("#### Lower-risk alternatives in the same zone")
    alt = R[(R["zone"] == er["zone"]) & (R["location_id"] != ev_loc) & (R["near_hospital"] == 0)].sort_values("score").head(5)
    st.dataframe(
        alt[["location_id", "road_type", "road_condition", "pedestrian_activity", "score", "n_open_inc", "n_open_comp"]].assign(score=lambda d: d["score"].round(1)),
        hide_index=True,
    )

# ----------------------------------------------------------------------------
# Commercial view
# ----------------------------------------------------------------------------
with tab_comm:
    st.subheader("Commercial view: suitability for shops or ads")
    st.caption("Suitability = footfall + density + access. This is NOT a sales prediction.")
    C = F.copy()
    C["access"] = 0.5 * C["road_type"].map(ROAD_TYPE_ACCESS) + 0.5 * C["road_condition"].map(ROAD_COND_ACCESS)
    C["suitability"] = 100 * (0.4 * C["ped"] + 0.3 * C["dens_n"] + 0.3 * C["access"])
    zone_tbl = (
        C.groupby("zone")
        .agg(
            avg_suitability=("suitability", "mean"),
            avg_pedestrian=("ped", "mean"),
            avg_access=("access", "mean"),
            locations=("location_id", "size"),
        )
        .sort_values("avg_suitability", ascending=False)
        .round(2)
    )
    cc1, cc2 = st.columns([1, 1.2])
    with cc1:
        st.markdown("**Zones ranked by average suitability**")
        st.bar_chart(zone_tbl["avg_suitability"], color=TEAL)
    with cc2:
        z = st.selectbox("Zone", zone_tbl.index.tolist())
        cz = C[C["zone"] == z].sort_values("suitability", ascending=False).head(10).copy()
        cz["hospital_access_note"] = np.where(cz["near_hospital"] == 1, "Keep hospital access clear", "")
        cz["suitability"] = cz["suitability"].round(1)
        st.markdown(f"**Top 10 spots in {z}**")
        st.dataframe(
            cz[["location_id", "road_type", "road_condition", "pedestrian_activity", "suitability", "hospital_access_note"]],
            hide_index=True,
        )
    st.caption(
        "Weights (0.4 footfall, 0.3 density, 0.3 access) and the access scores per road type/condition are design assumptions. "
        "Complaint counts are deliberately NOT used: low complaints do not mean a better area."
    )

# ----------------------------------------------------------------------------
# Trust & limits
# ----------------------------------------------------------------------------
with tab_trust:
    st.subheader("Trust & limits")
    st.markdown("#### 1. Is the ranking stable when weights change?")
    st.dataframe(
        sensitivity_table(F, tuple(w.items()), shrink, crowd_mult, festival_on and fest_date is not None, top_n),
        hide_index=True,
    )
    st.caption("100 random runs per row: every weight multiplied by a random factor in the stated range, ranking compared with the current one.")

    st.markdown("#### 2. Is past history real signal or luck?")
    n = F["n_inc"].values
    var_ratio = n.var() / n.mean()
    rng = np.random.default_rng(1)
    sim_max = [rng.poisson(n.mean(), len(n)).max() for _ in range(300)]
    h1 = inc_raw[inc_raw["timestamp"].dt.month <= 6].groupby("location_id").size().reindex(F["location_id"]).fillna(0)
    h2 = inc_raw[inc_raw["timestamp"].dt.month > 6].groupby("location_id").size().reindex(F["location_id"]).fillna(0)
    t1, t2, t3 = st.columns(3)
    t1.metric("Variance / mean of incident counts", f"{var_ratio:.2f}", help="About 1.0 means pure Poisson chance.")
    t2.metric("Worst location vs luck-only max", f"{n.max()} vs ~{np.percentile(sim_max, 50):.0f}", help="Median of the max in 300 simulations of random locations.")
    t3.metric("Jan-Jun vs Jul-Dec correlation", f"{np.corrcoef(h1, h2)[0, 1]:.2f}", help="Near 0 means hotspots don't persist.")
    st.write(
        "If these three numbers look like chance, a location's own incident count says little about its future. "
        "That is why Early Alarm leans on **consequence and unresolved backlog**, shrinks small counts toward the city average, "
        "and shows a confidence level instead of a bare score."
    )
    st.markdown("#### 3. What we tested and rejected")
    st.write(
        "- Festival effect: in the analysis notebook, incidents and complaints on 2025 festival windows were not significantly "
        "different from other days (incidents p = 0.54, complaints p = 0.23; festival dates approximate).\n"
        "- Road condition, road type, school proximity, pedestrian activity, density and zone did not change incident counts.\n"
        "- So the festival layer is a **planning tool using a known calendar**, not a predictor."
    )
    st.markdown("#### 4. Guard rails")
    st.write(
        "- Never recommend an event that blocks hospital access (Event planner shows HOLD near hospitals).\n"
        "- Open High/Critical incidents near schools and hospitals are always flagged.\n"
        "- Crowd multiplier and all weights are visible assumptions you can change.\n"
        "- Data quirk: unresolved incidents still carry resolution hours, so resolution time is **not** used in the score."
    )
    st.error("Synthetic data, simulated coordinates. Not an official city dataset. Do not use for real public safety decisions.")
