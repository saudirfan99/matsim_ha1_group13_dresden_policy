#!/usr/bin/env python3
"""
STEP 5b — Geographic stratification of affected agents
1. Extract Carola Bridge centroid from output_links.csv.gz geometry
2. Get home coordinates of 467 affected agents from output_persons.csv.gz
3. Compute Euclidean distance home → bridge
4. Stratify modal shift by distance band
5. Save CSV ready for QGIS import (point map of affected agents)
"""
import os, re
import pandas as pd
import numpy as np

ROOT     = "/Users/saudirfan99gmail.com/Desktop/University /TU Berlin/PB-04/MATSim/HA1/HA1_Runs"
BASE_DIR = f"{ROOT}/dresden-v1.0-output-1pct_BASE"
POL_DIR  = f"{ROOT}/dresden-v1.0-output-1pct_POLICY"
OUT_DIR  = f"{ROOT}/analysis_outputs"

with open(f"{OUT_DIR}/affected_persons.txt") as f:
    affected = set(line.strip() for line in f if line.strip())
print(f"Affected persons: {len(affected):,}")

CAROLA_CAR  = {"901959078", "4214231"}
EXCL_MODES  = {'truck8t','truck40t','truck18t'}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Extract Carola Bridge centroid from POLICY output_links.csv.gz
# ══════════════════════════════════════════════════════════════════════════════
print("\nExtracting Carola Bridge centroid from network geometry...")
pol_links = pd.read_csv(
    f"{POL_DIR}/matsim-open-dresden-scenario-1pct-20260504_4.output_links.csv.gz",
    sep=';', low_memory=False)
pol_links['link'] = pol_links['link'].astype(str)
carola_geoms = pol_links[pol_links['link'].isin(CAROLA_CAR)]
print(f"Carola car links found: {len(carola_geoms)}")

def parse_linestring(s):
    coords_str = re.sub(r'LINESTRING\s*\(|\)', '', str(s)).strip()
    pts = [c.strip().split() for c in coords_str.split(',')]
    return [(float(p[0]), float(p[1])) for p in pts if len(p) >= 2]

all_xs, all_ys = [], []
for _, row in carola_geoms.iterrows():
    if pd.notna(row.get('geometry','')) and 'LINESTRING' in str(row['geometry']):
        for x, y in parse_linestring(row['geometry']):
            all_xs.append(x); all_ys.append(y)

if not all_xs:
    raise ValueError("No geometry found for Carola links — need network XML parse")

bridge_x = np.mean(all_xs)
bridge_y = np.mean(all_ys)
print(f"Carola Bridge centroid (EPSG:25832): X = {bridge_x:.1f}, Y = {bridge_y:.1f}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Home coordinates of affected agents
# ══════════════════════════════════════════════════════════════════════════════
print("\nReading persons file for home coordinates...")
persons = pd.read_csv(f"{BASE_DIR}/009.output_persons.csv.gz",
                      sep=';', low_memory=False)
pid = 'person' if 'person' in persons.columns else persons.columns[0]
persons[pid] = persons[pid].astype(str)

x_col = next((c for c in persons.columns
              if c.lower() in ('home_x','first_act_x','homex','x')), None)
y_col = next((c for c in persons.columns
              if c.lower() in ('home_y','first_act_y','homey','y')), None)
if x_col is None or y_col is None:
    print(f"Available columns: {persons.columns.tolist()}")
    raise ValueError("Could not find home_x / home_y columns — inspect output above")

print(f"Using home coordinates from: '{x_col}', '{y_col}'")
aff_homes = persons[persons[pid].isin(affected)][[pid, x_col, y_col]].copy()
aff_homes.columns = ['person','home_x','home_y']
aff_homes['home_x'] = pd.to_numeric(aff_homes['home_x'], errors='coerce')
aff_homes['home_y'] = pd.to_numeric(aff_homes['home_y'], errors='coerce')
aff_homes = aff_homes.dropna(subset=['home_x','home_y'])
print(f"Affected agents with valid coordinates: {len(aff_homes):,}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Distance from home to bridge centroid
# ══════════════════════════════════════════════════════════════════════════════
aff_homes['dist_to_bridge_m']  = np.hypot(
    aff_homes['home_x'] - bridge_x,
    aff_homes['home_y'] - bridge_y)
aff_homes['dist_to_bridge_km'] = aff_homes['dist_to_bridge_m'] / 1000

bins   = [0, 2, 4, 8, 15, 100]
labels = ['core (<2 km)','inner (2–4 km)','middle (4–8 km)','outer (8–15 km)','periphery (>15 km)']
aff_homes['zone'] = pd.cut(aff_homes['dist_to_bridge_km'], bins=bins, labels=labels)

print(f"\n── Distance distribution of affected agents ──")
print(f"  Mean:   {aff_homes['dist_to_bridge_km'].mean():.2f} km")
print(f"  Median: {aff_homes['dist_to_bridge_km'].median():.2f} km")
print(f"  Min:    {aff_homes['dist_to_bridge_km'].min():.2f} km")
print(f"  Max:    {aff_homes['dist_to_bridge_km'].max():.2f} km\n")
print(aff_homes['zone'].value_counts().reindex(labels).fillna(0).astype(int))

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Modal shift by zone
# ══════════════════════════════════════════════════════════════════════════════
print("\nLoading trips files (BASE & POLICY)...")
bt = pd.read_csv(f"{BASE_DIR}/009.output_trips.csv.gz", sep=';', low_memory=False)
pt = pd.read_csv(f"{POL_DIR}/matsim-open-dresden-scenario-1pct-20260504_4.output_trips.csv.gz",
                 sep=';', low_memory=False)

def find_cols(df):
    p = 'person' if 'person' in df.columns else df.columns[0]
    m = next(c for c in df.columns if c in ('main_mode','mode','longest_distance_mode'))
    return p, m

bp, bm = find_cols(bt); pp, pm = find_cols(pt)
bt[bp] = bt[bp].astype(str); pt[pp] = pt[pp].astype(str)
ba = bt[bt[bp].isin(affected) & ~bt[bm].isin(EXCL_MODES)][[bp, bm]].copy()
pa = pt[pt[pp].isin(affected) & ~pt[pm].isin(EXCL_MODES)][[pp, pm]].copy()
ba.columns = ['person','base_mode']; pa.columns = ['person','policy_mode']

# Per-person dominant mode
def dominant(df, mode_col):
    return df.groupby('person')[mode_col].agg(lambda x: x.value_counts().idxmax())
b_dom = dominant(ba, 'base_mode').reset_index()
p_dom = dominant(pa, 'policy_mode').reset_index()
aff_homes = aff_homes.merge(b_dom, on='person', how='left')
aff_homes = aff_homes.merge(p_dom, on='person', how='left')
aff_homes['mode_changed'] = aff_homes['base_mode'] != aff_homes['policy_mode']

# ── Modal shift table per zone ───────────────────────────────────────────────
print("\n" + "="*70)
print("MODAL SHIFT BY DISTANCE-FROM-BRIDGE ZONE")
print("="*70)

ba_zoned = ba.merge(aff_homes[['person','zone']], on='person', how='left')
pa_zoned = pa.merge(aff_homes[['person','zone']], on='person', how='left')

MODES = ['bike','car','pt','ride','walk']
rows_geo = []

for z in labels:
    bz = ba_zoned[ba_zoned['zone'] == z]
    pz = pa_zoned[pa_zoned['zone'] == z]
    n_persons = int((aff_homes['zone'] == z).sum())
    if n_persons == 0:
        continue
    bs = (bz['base_mode'].value_counts(normalize=True) * 100).round(2)
    ps = (pz['policy_mode'].value_counts(normalize=True) * 100).round(2)
    print(f"\n── {z}  |  {n_persons} persons  |  {len(bz)} BASE / {len(pz)} POL trips ──")
    print(f"  {'Mode':<6} {'BASE %':>7} {'POL %':>7} {'Δ pp':>7}")
    for m in MODES:
        b = float(bs.get(m, 0)); p = float(ps.get(m, 0))
        print(f"  {m:<6} {b:>6.1f}% {p:>6.1f}% {p-b:>+6.1f}")
        rows_geo.append({'zone':z, 'n_persons':n_persons,
                         'mode':m, 'base_pct':b, 'policy_pct':p,
                         'delta_pp':round(p-b, 2)})

# ── Mode-change rate by zone ─────────────────────────────────────────────────
print("\n── Mode-change rate (dominant mode differs BASE vs POLICY) by zone ──")
for z in labels:
    sub = aff_homes[aff_homes['zone'] == z]
    if len(sub) == 0:
        continue
    changed = sub['mode_changed'].sum()
    print(f"  {z:<25} {changed:>3}/{len(sub):>3} changed  "
          f"({changed/len(sub)*100:.0f}%)")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Save outputs
# ══════════════════════════════════════════════════════════════════════════════
pd.DataFrame(rows_geo).to_csv(f"{OUT_DIR}/step5b_mode_shift_by_zone.csv", index=False)

aff_homes[['person','home_x','home_y','dist_to_bridge_km',
           'zone','base_mode','policy_mode','mode_changed']].to_csv(
    f"{OUT_DIR}/step5b_affected_agents_geo.csv", index=False)

with open(f"{OUT_DIR}/step5b_carola_centroid.txt", 'w') as f:
    f.write(f"x;y;label\n{bridge_x};{bridge_y};Carola Bridge centroid\n")

print(f"\n✅ Saved 3 files: step5b_mode_shift_by_zone.csv, "
      f"step5b_affected_agents_geo.csv, step5b_carola_centroid.txt")
print("\nFor QGIS map:")
print("  1. Layer → Add Layer → Add Delimited Text Layer")
print("  2. step5b_affected_agents_geo.csv: X=home_x, Y=home_y, CRS=EPSG:25832")
print("  3. Symbolise by 'mode_changed' or 'policy_mode' (categorised)")
print("  4. Add step5b_carola_centroid.txt as a second layer for the bridge marker")
