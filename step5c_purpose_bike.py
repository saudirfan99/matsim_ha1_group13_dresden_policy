#!/usr/bin/env python3
"""
STEP 5c — Trip Purpose Shift + Bike Paradox Quantification
Part A: Mode shift by trip purpose (work, education, leisure, shop, other)
Part B: BASE bike trips by affected agents — what mode do they become in POLICY?
"""
import os
import pandas as pd
import numpy as np

ROOT     = "/Users/saudirfan99gmail.com/Desktop/University /TU Berlin/PB-04/MATSim/HA1/HA1_Runs"
BASE_DIR = f"{ROOT}/dresden-v1.0-output-1pct_BASE"
POL_DIR  = f"{ROOT}/dresden-v1.0-output-1pct_POLICY"
OUT_DIR  = f"{ROOT}/analysis_outputs"

with open(f"{OUT_DIR}/affected_persons.txt") as f:
    affected = set(line.strip() for line in f if line.strip())
print(f"Affected persons: {len(affected):,}")

EXCL_MODES = {'truck8t','truck40t','truck18t'}
MODES = ['bike','car','pt','ride','walk']

# ── Load trips ───────────────────────────────────────────────────────────────
print("\nLoading trip files...")
bt = pd.read_csv(f"{BASE_DIR}/009.output_trips.csv.gz", sep=';', low_memory=False)
pt = pd.read_csv(f"{POL_DIR}/matsim-open-dresden-scenario-1pct-20260504_4.output_trips.csv.gz",
                 sep=';', low_memory=False)

def find_cols(df, label):
    p = 'person' if 'person' in df.columns else df.columns[0]
    m = next(c for c in df.columns if c in ('main_mode','mode','longest_distance_mode'))
    purp = next((c for c in df.columns if c in ('end_activity_type','endActType',
                                                 'end_act_type','main_act_type',
                                                 'purpose','trip_purpose')), None)
    dist = next((c for c in df.columns if 'traveled_distance' in c.lower() or
                                          'distance' in c.lower()), None)
    trip = next((c for c in df.columns if c in ('trip_id','trip_number','tripId')), None)
    print(f"  {label}: person={p}, mode={m}, purpose={purp}, dist={dist}, trip={trip}")
    return p, m, purp, dist, trip

bp, bm, bpurp, bdist, btrip = find_cols(bt, "BASE")
pp, pm, ppurp, pdist, ptrip = find_cols(pt, "POLICY")
bt[bp] = bt[bp].astype(str); pt[pp] = pt[pp].astype(str)

ba = bt[bt[bp].isin(affected) & ~bt[bm].isin(EXCL_MODES)].copy()
pa = pt[pt[pp].isin(affected) & ~pt[pm].isin(EXCL_MODES)].copy()
print(f"\nBASE trips for affected:   {len(ba):,}")
print(f"POLICY trips for affected: {len(pa):,}")

ba = ba.rename(columns={bp:'person', bm:'mode'})
pa = pa.rename(columns={pp:'person', pm:'mode'})
if bpurp: ba['purpose'] = ba[bpurp]
if ppurp: pa['purpose'] = pa[ppurp]
if bdist: ba['distance_m'] = pd.to_numeric(ba[bdist], errors='coerce')
if pdist: pa['distance_m'] = pd.to_numeric(pa[pdist], errors='coerce')

# ══════════════════════════════════════════════════════════════════════════════
# PART A — MODE SHIFT BY TRIP PURPOSE
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("PART A — MODE SHIFT BY TRIP PURPOSE (affected agents)")
print("="*70)

def normalize_purpose(p):
    if pd.isna(p): return 'unknown'
    p = str(p).lower()
    if any(k in p for k in ['work','arbeit','job']): return 'work'
    if any(k in p for k in ['educ','school','uni','student']): return 'education'
    if any(k in p for k in ['shop','einkauf','daily','grocer']): return 'shop'
    if any(k in p for k in ['leisure','freizeit','sport']): return 'leisure'
    if any(k in p for k in ['visit','social','besuch']): return 'visit'
    if 'home' in p: return 'home'
    if any(k in p for k in ['errand','other','sonst']): return 'errands_other'
    return p

if 'purpose' in ba.columns and 'purpose' in pa.columns:
    ba['purp'] = ba['purpose'].apply(normalize_purpose)
    pa['purp'] = pa['purpose'].apply(normalize_purpose)

    purposes = sorted(set(ba['purp'].unique()) | set(pa['purp'].unique()))
    print(f"\nDetected purposes: {purposes}")
    print(f"\n{'Purpose':<16} {'BASE n':>7} {'POL n':>7} {'Δ trips':>9}   "
          f"{'Top BASE mode':>13}  {'Top POL mode':>13}  Δcar pp")
    print("-"*95)
    rows_p = []
    for purp in purposes:
        bs = ba[ba['purp'] == purp]
        ps = pa[pa['purp'] == purp]
        n_b, n_p = len(bs), len(ps)
        if n_b + n_p < 10:
            continue
        b_share = (bs['mode'].value_counts(normalize=True) * 100).round(2)
        p_share = (ps['mode'].value_counts(normalize=True) * 100).round(2)
        top_b = bs['mode'].mode().iloc[0] if n_b else '-'
        top_p = ps['mode'].mode().iloc[0] if n_p else '-'
        dcar = float(p_share.get('car', 0)) - float(b_share.get('car', 0))
        print(f"{purp:<16} {n_b:>7,} {n_p:>7,} {n_p-n_b:>+9,}   "
              f"{top_b:>13}  {top_p:>13}  {dcar:>+6.1f}")
        for m in MODES:
            rows_p.append({'purpose':purp, 'mode':m,
                           'base_trips':   int(bs[bs['mode']==m].shape[0]),
                           'policy_trips': int(ps[ps['mode']==m].shape[0]),
                           'base_pct':     float(b_share.get(m, 0)),
                           'policy_pct':   float(p_share.get(m, 0)),
                           'delta_pp':     round(float(p_share.get(m, 0)) -
                                                 float(b_share.get(m, 0)), 2)})

    df_purp = pd.DataFrame(rows_p)
    df_purp.to_csv(f"{OUT_DIR}/step5c_mode_shift_by_purpose.csv", index=False)
    print(f"\n✅ Saved step5c_mode_shift_by_purpose.csv")
else:
    print("⚠️ No purpose column found — skipping Part A")
    df_purp = None

# ══════════════════════════════════════════════════════════════════════════════
# PART B — BIKE PARADOX: where do BASE bike trips go in POLICY?
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("PART B — BIKE PARADOX (BASE bike trips by affected agents → POLICY mode)")
print("="*70)

def index_trips(df):
    df = df.sort_values(['person']).copy()
    df['ord'] = df.groupby('person').cumcount()
    return df

ba_idx = index_trips(ba)
pa_idx = index_trips(pa)
merged = ba_idx.merge(pa_idx[['person','ord','mode'] +
                              (['distance_m'] if 'distance_m' in pa.columns else [])],
                       on=['person','ord'], suffixes=('_base','_policy'))
print(f"\nMatched trips (BASE ord ↔ POLICY ord): {len(merged):,}")

print(f"\n── MODE TRANSITION MATRIX (rows: BASE mode, columns: POLICY mode) ──")
trans = pd.crosstab(merged['mode_base'], merged['mode_policy'], margins=True, margins_name='Σ')
print(trans)

bike_base = merged[merged['mode_base'] == 'bike']
print(f"\n── BASE bike trips by affected agents: {len(bike_base):,} ──")
print(f"  Where they went in POLICY:")
pol_dist = bike_base['mode_policy'].value_counts()
pol_pct  = (bike_base['mode_policy'].value_counts(normalize=True) * 100).round(1)
for m in MODES:
    n = int(pol_dist.get(m, 0))
    p = float(pol_pct.get(m, 0))
    flag = "  ← stayed" if m == 'bike' else ""
    print(f"  → {m:<6}: {n:>4,} trips ({p:>5.1f}%){flag}")

if 'distance_m_base' in bike_base.columns:
    print(f"\n  BASE bike trip distance distribution:")
    print(f"    Mean:   {bike_base['distance_m_base'].mean()/1000:.2f} km")
    print(f"    Median: {bike_base['distance_m_base'].median()/1000:.2f} km")
    print(f"    Max:    {bike_base['distance_m_base'].max()/1000:.2f} km")
    print(f"\n  By POLICY mode (mean BASE bike trip distance):")
    grp = bike_base.groupby('mode_policy')['distance_m_base'].mean() / 1000
    for m, v in grp.items():
        print(f"    → {m:<6}: {v:.2f} km")

bike_policy = merged[merged['mode_policy'] == 'bike']
print(f"\n── POLICY bike trips by affected agents: {len(bike_policy):,} ──")
print(f"  Where they came from in BASE:")
src_dist = bike_policy['mode_base'].value_counts()
src_pct  = (bike_policy['mode_base'].value_counts(normalize=True) * 100).round(1)
for m in MODES:
    n = int(src_dist.get(m, 0))
    p = float(src_pct.get(m, 0))
    flag = "  ← stayed" if m == 'bike' else ""
    print(f"  ← {m:<6}: {n:>4,} trips ({p:>5.1f}%){flag}")

trans.to_csv(f"{OUT_DIR}/step5c_mode_transition_matrix.csv")
merged_save = merged[['person','ord','mode_base','mode_policy'] +
                     (['distance_m_base'] if 'distance_m_base' in merged.columns else [])]
merged_save.to_csv(f"{OUT_DIR}/step5c_trip_transitions.csv", index=False)
print(f"\n✅ Saved step5c_mode_transition_matrix.csv, step5c_trip_transitions.csv")
print("\nStep 5c complete. Step 6 next: consolidated poster summary + visualisations.")
