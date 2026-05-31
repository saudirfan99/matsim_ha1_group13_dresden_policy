#!/usr/bin/env python3
"""
STEP 4 — Affected Agent Behaviour: BASE vs POLICY
Compares the 467 affected residential persons:
  - mode distribution shift
  - total km travelled
  - total time in traffic
  - trip suppression check
Both BASE and POLICY use output_trips.csv.gz directly.
"""
import os
import pandas as pd
import numpy as np

ROOT     = "/Users/saudirfan99gmail.com/Desktop/University /TU Berlin/PB-04/MATSim/HA1/HA1_Runs"
BASE_DIR = f"{ROOT}/dresden-v1.0-output-1pct_BASE"
POL_DIR  = f"{ROOT}/dresden-v1.0-output-1pct_POLICY"
OUT_DIR  = f"{ROOT}/analysis_outputs"

# ── Load affected persons ─────────────────────────────────────────────────────
with open(f"{OUT_DIR}/affected_persons.txt") as f:
    affected = set(line.strip() for line in f if line.strip())
print(f"Affected persons loaded: {len(affected):,}")

EXCL_MODES = {'truck8t','truck40t','truck18t'}

# ══════════════════════════════════════════════════════════════════════════════
# Helper: load and filter a trips file
# ══════════════════════════════════════════════════════════════════════════════
def load_trips(path, label):
    df = pd.read_csv(path, sep=';', low_memory=False)
    print(f"\n{label} — {len(df):,} total trips")
    df['person'] = df['person'].astype(str)

    mode_col = next(c for c in df.columns if c in ('main_mode','mode','longest_distance_mode'))
    dist_col = next((c for c in df.columns if 'traveled_distance' in c.lower()), None) \
            or next((c for c in df.columns if 'distance' in c.lower()), None)
    time_col = next((c for c in df.columns
                     if 'trav_time' in c.lower() or 'travel_time' in c.lower()), None)

    df = df[df['person'].isin(affected) & ~df[mode_col].isin(EXCL_MODES)].copy()
    df.rename(columns={mode_col: 'main_mode', dist_col: 'distance_m',
                       time_col: 'time_s'}, inplace=True)

    df['distance_m'] = pd.to_numeric(df['distance_m'], errors='coerce').fillna(0)
    # Convert HH:MM:SS or numeric seconds → float seconds
    try:
        df['time_s'] = pd.to_timedelta(df['time_s']).dt.total_seconds()
    except Exception:
        df['time_s'] = pd.to_numeric(df['time_s'], errors='coerce').fillna(0)
    print(f"{label} — {len(df):,} trips for affected agents")
    return df

# ══════════════════════════════════════════════════════════════════════════════
# PART 1 & 2 — Load BASE and POLICY trips
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*65)
print("PART 1 — BASE trips for affected agents")
print("="*65)
ba = load_trips(f"{BASE_DIR}/009.output_trips.csv.gz", "BASE")

print("\n" + "="*65)
print("PART 2 — POLICY trips for affected agents")
print("="*65)
pa = load_trips(
    f"{POL_DIR}/matsim-open-dresden-scenario-1pct-20260504_4.output_trips.csv.gz",
    "POLICY"
)

# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — Comparison: mode shift, km, time, suppression
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*65)
print("PART 3 — Affected agents: BASE vs POLICY")
print("="*65)

def summarise(df, label):
    by_mode = df.groupby('main_mode').agg(
        trips      =('main_mode','count'),
        total_km   =('distance_m', lambda x: x.sum()/1000),
        total_hrs  =('time_s',     lambda x: x.sum()/3600),
    )
    by_mode['avg_km_per_trip'] = by_mode['total_km'] / by_mode['trips']
    by_mode['avg_speed_kmh']   = by_mode['total_km'] / by_mode['total_hrs'].replace(0, np.nan)
    by_mode['share_pct']       = (by_mode['trips'] / by_mode['trips'].sum() * 100).round(2)
    print(f"\n{label}:\n{by_mode.round(2)}")
    return by_mode

b_summary = summarise(ba, "BASE — affected agents")
p_summary = summarise(pa, "POLICY — affected agents")

# Side-by-side delta
print("\n" + "="*65)
print("MODAL SHIFT — affected agents only")
print("="*65)
print(f"{'Mode':<8} {'BASE trips':>10} {'POL trips':>10} {'Δ trips':>9} "
      f"{'BASE %':>7} {'POL %':>7} {'Δ pp':>7}")
print("-"*60)
rows4 = []
for mode in ['bike','car','pt','ride','walk']:
    bt = int(b_summary['trips'].get(mode, 0))
    pt_ = int(p_summary['trips'].get(mode, 0))
    bs = float(b_summary['share_pct'].get(mode, 0))
    ps = float(p_summary['share_pct'].get(mode, 0))
    print(f"{mode:<8} {bt:>10,} {pt_:>10,} {pt_-bt:>+9,} "
          f"{bs:>6.1f}% {ps:>6.1f}% {ps-bs:>+6.1f}pp")
    rows4.append({'mode': mode, 'base_trips': bt, 'policy_trips': pt_,
                  'delta_trips': pt_-bt, 'base_pct': bs, 'policy_pct': ps,
                  'delta_pp': ps-bs,
                  'base_km':  float(b_summary['total_km'].get(mode, 0)),
                  'policy_km':float(p_summary['total_km'].get(mode, 0)),
                  'base_hrs': float(b_summary['total_hrs'].get(mode, 0)),
                  'policy_hrs':float(p_summary['total_hrs'].get(mode, 0))})

# Totals
print(f"\n── TOTALS for affected agents (1% sample) ──")
print(f"{'Metric':<22} {'BASE':>12} {'POLICY':>12} {'Δ':>12} {'Δ %':>9}")
print("-"*70)
def line(label, b, p, fmt="{:,.1f}"):
    delta = p - b
    pct = (delta/b*100) if b else 0
    delta_str = ("+" if delta >= 0 else "") + fmt.format(delta)
    print(f"{label:<22} {fmt.format(b):>12} {fmt.format(p):>12} "
          f"{delta_str:>12} {pct:>+8.1f}%")
line("Total trips",          len(ba),                        len(pa),                        fmt="{:,.0f}")
line("Total km",             ba['distance_m'].sum()/1000,    pa['distance_m'].sum()/1000)
line("Total hrs in traffic", ba['time_s'].sum()/3600,        pa['time_s'].sum()/3600)

# ══════════════════════════════════════════════════════════════════════════════
# PART 4 — Trip suppression: trips per affected agent
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n── TRIP SUPPRESSION CHECK ──")
b_per = ba.groupby('person').size()
p_per = pa.groupby('person').size()

all_aff = pd.Index(sorted(affected))
b_per = b_per.reindex(all_aff, fill_value=0)
p_per = p_per.reindex(all_aff, fill_value=0)
delta_per_person = p_per - b_per

print(f"  Mean trips per affected (BASE):   {b_per.mean():.2f}")
print(f"  Mean trips per affected (POLICY): {p_per.mean():.2f}")
print(f"  Agents with fewer trips in POL:  {(delta_per_person < 0).sum():,}")
print(f"  Agents with same number:         {(delta_per_person == 0).sum():,}")
print(f"  Agents with more trips:          {(delta_per_person > 0).sum():,}")
print(f"  Net change in trip count:        {delta_per_person.sum():+,}")

# ── Save outputs ──────────────────────────────────────────────────────────────
pd.DataFrame(rows4).to_csv(f"{OUT_DIR}/step4_affected_modal_shift.csv", index=False)
b_summary.to_csv(f"{OUT_DIR}/step4_base_affected_by_mode.csv")
p_summary.to_csv(f"{OUT_DIR}/step4_policy_affected_by_mode.csv")
pd.DataFrame({
    'person':        all_aff,
    'base_trips':    b_per.values,
    'policy_trips':  p_per.values,
    'delta':         delta_per_person.values,
}).to_csv(f"{OUT_DIR}/step4_trip_suppression.csv", index=False)

print(f"\n✅ Saved 4 files to analysis_outputs/")
print("\nPaste the output. Step 5a (demographic) and 5b (geographic) come next.")
