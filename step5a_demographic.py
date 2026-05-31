#!/usr/bin/env python3
"""
STEP 5a — Demographic stratification of affected agents
For 467 affected residential persons:
  - Age group, hhIncome, carAvail, gender, hhSize
  - BASE vs POLICY mode share per group + modal shift
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
MODES      = ['bike','car','pt','ride','walk']

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Load persons + demographics
# ══════════════════════════════════════════════════════════════════════════════
print("\nLoading BASE persons file...")
persons = pd.read_csv(f"{BASE_DIR}/009.output_persons.csv.gz",
                     sep=';', low_memory=False)
print(f"All columns: {persons.columns.tolist()}")

pid_col = 'person' if 'person' in persons.columns else persons.columns[0]
persons[pid_col] = persons[pid_col].astype(str)
aff_demo = persons[persons[pid_col].isin(affected)].copy()
aff_demo.rename(columns={pid_col: 'person'}, inplace=True)
print(f"Affected persons matched with demographics: {len(aff_demo):,}")

# Age bands
if 'age' in aff_demo.columns:
    aff_demo['age'] = pd.to_numeric(aff_demo['age'], errors='coerce')
    aff_demo['age_group'] = pd.cut(
        aff_demo['age'],
        bins=[0, 18, 25, 35, 50, 65, 120],
        labels=['<18','18-24','25-34','35-49','50-64','65+'],
        right=False
    )

# Income bands: hhIncome is ordinal 1-10 scale — bin into thirds
if 'hhIncome' in aff_demo.columns:
    aff_demo['hhIncome'] = pd.to_numeric(aff_demo['hhIncome'], errors='coerce')
    aff_demo['income_group'] = pd.cut(
        aff_demo['hhIncome'],
        bins=[0, 3, 6, 10],
        labels=['low (1-3)','medium (4-6)','high (7-10)'],
        include_lowest=True
    )

print(f"\n── Demographic distribution of affected agents ──")
for col in ['age_group', 'income_group', 'carAvail', 'sex', 'ptTicket', 'hhSize']:
    if col in aff_demo.columns:
        print(f"\n{col}:\n{aff_demo[col].value_counts(dropna=False).head(10)}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Load trips, filter to affected, join demographics
# ══════════════════════════════════════════════════════════════════════════════
print("\nLoading trips...")

def load_affected_trips(path, label):
    df = pd.read_csv(path, sep=';', low_memory=False)
    pid  = 'person' if 'person' in df.columns else df.columns[0]
    mode = next(c for c in df.columns if c in ('main_mode','mode','longest_distance_mode'))
    df[pid] = df[pid].astype(str)
    sub = df[df[pid].isin(affected) & ~df[mode].isin(EXCL_MODES)].copy()
    sub.rename(columns={pid: 'person', mode: 'main_mode'}, inplace=True)
    print(f"  {label}: {len(sub):,} trips")
    return sub

ba = load_affected_trips(f"{BASE_DIR}/009.output_trips.csv.gz", "BASE")
pa = load_affected_trips(
    f"{POL_DIR}/matsim-open-dresden-scenario-1pct-20260504_4.output_trips.csv.gz",
    "POLICY"
)

# Attach demographics
demo_keep = [c for c in
             ['person','age','age_group','income_group','carAvail','sex','ptTicket','hhSize']
             if c in aff_demo.columns]
print(f"Demographic columns used: {demo_keep}")
ba = ba.merge(aff_demo[demo_keep], on='person', how='left')
pa = pa.merge(aff_demo[demo_keep], on='person', how='left')

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Modal shift by each demographic dimension
# ══════════════════════════════════════════════════════════════════════════════
# Ordered category sequences where applicable
DIM_ORDER = {
    'age_group':    ['<18','18-24','25-34','35-49','50-64','65+'],
    'income_group': ['low (1-3)','medium (4-6)','high (7-10)'],
    'carAvail':     ['never','sometimes','always'],
    'sex':          ['f','m'],
    'ptTicket':     ['none','full'],
}

def shift_by(dim):
    if dim not in ba.columns:
        print(f"\n  '{dim}' not in trips data — skipping")
        return None

    print(f"\n{'='*70}")
    print(f"MODAL SHIFT BY {dim.upper()}")
    print(f"{'='*70}")

    all_vals  = ba[dim].dropna().astype(str).unique().tolist()
    groups    = DIM_ORDER.get(dim, sorted(all_vals))
    groups    = [g for g in groups if g in all_vals]  # keep only present values

    rows = []
    for g in groups:
        b_sub = ba[ba[dim].astype(str) == g]
        p_sub = pa[pa[dim].astype(str) == g]
        n_aff = int((aff_demo[dim].astype(str) == g).sum()) if dim in aff_demo.columns else 0
        if len(b_sub) == 0 and len(p_sub) == 0:
            continue
        b_share = (b_sub['main_mode'].value_counts(normalize=True) * 100).round(2)
        p_share = (p_sub['main_mode'].value_counts(normalize=True) * 100).round(2)
        for m in MODES:
            bs = float(b_share.get(m, 0.0))
            ps = float(p_share.get(m, 0.0))
            rows.append({dim: g, 'n_persons': n_aff,
                         'mode': m, 'base_pct': bs, 'policy_pct': ps,
                         'delta_pp': round(ps - bs, 2)})

    df_out = pd.DataFrame(rows)
    pivot_b = df_out.pivot(index=dim, columns='mode', values='base_pct').reindex(groups)
    pivot_p = df_out.pivot(index=dim, columns='mode', values='policy_pct').reindex(groups)
    pivot_d = df_out.pivot(index=dim, columns='mode', values='delta_pp').reindex(groups)

    for m in MODES:
        for piv in (pivot_b, pivot_p, pivot_d):
            if m not in piv.columns:
                piv[m] = 0.0

    n_per = (aff_demo[dim].astype(str).value_counts()
             .reindex(groups).fillna(0).astype(int)) if dim in aff_demo.columns \
            else pd.Series(0, index=groups)

    print(f"\n  Persons per group: { {g: int(n_per.get(g,0)) for g in groups} }")
    print(f"\n  BASE %:\n{pivot_b[MODES].round(1).to_string()}")
    print(f"\n  POLICY %:\n{pivot_p[MODES].round(1).to_string()}")
    print(f"\n  Δ pp (POLICY − BASE):\n{pivot_d[MODES].round(1).to_string()}")
    return df_out

dim_results = {}
for dim in ['age_group','income_group','carAvail','sex','ptTicket','hhSize']:
    dim_results[dim] = shift_by(dim)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Save outputs
# ══════════════════════════════════════════════════════════════════════════════
for dim, df in dim_results.items():
    if df is not None:
        df.to_csv(f"{OUT_DIR}/step5a_mode_shift_by_{dim}.csv", index=False)
aff_demo.to_csv(f"{OUT_DIR}/step5a_affected_demographics.csv", index=False)
print(f"\n✅ Saved files to analysis_outputs/")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Key insight: who shed car most?
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("KEY INSIGHT — which groups shed car most aggressively?")
print("="*70)
for dim, df in dim_results.items():
    if df is None:
        continue
    car_shifts = df[df['mode'] == 'car'][[dim,'n_persons','base_pct','policy_pct','delta_pp']]
    car_shifts = car_shifts[car_shifts['n_persons'] >= 5].sort_values('delta_pp')
    if car_shifts.empty:
        continue
    print(f"\nCar share Δ by {dim}:")
    print(car_shifts.to_string(index=False))

print("\nReady for Step 5b — geographic analysis.")
