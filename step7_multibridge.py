#!/usr/bin/env python3
"""
STEP 7 — Multi-Bridge Corridor Analysis
Part A: Cross-Elbe car volume redistribution (modified + unmodified bridges)
Part B: Three-layer policy evaluation (Carola closure, alt capacity, feeder gating)
Part C: Per-bridge affected-agent behaviour comparison
"""
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT     = "/Users/saudirfan99gmail.com/Desktop/University /TU Berlin/PB-04/MATSim/HA1/HA1_Runs"
BASE_DIR = f"{ROOT}/dresden-v1.0-output-1pct_BASE"
POL_DIR  = f"{ROOT}/dresden-v1.0-output-1pct_POLICY"
OUT      = f"{ROOT}/analysis_outputs"
FIG      = f"{OUT}/figures"
os.makedirs(FIG, exist_ok=True)

# ── Known modified link IDs ───────────────────────────────────────────────────
CAROLA_CAR  = ["901959078", "4214231"]
ALBER_CAR   = ["505502627#0", "-264360396#1"]
AUGUS_CAR   = ["-264360404", "1031454500"]
FEEDERS_CAR = [
    "-376145739","237502199","-1329159900","4265202","-99478092","60611109#0",
    "4214230","379745367","24209438","25702467#0","657862430","1108789888",
    "150611226","867018480","415552984","138307399",
    "439458122","-294983108","294983108","-504890257","-369971087","1036528789",
    "504885692","233822748#1","213544718","443697736","4539657","12497357"
]

EXCL = {'truck8t','truck40t','truck18t'}
MODES = ['bike','car','pt','ride','walk']

# ══════════════════════════════════════════════════════════════════════════════
# Load link files
# ══════════════════════════════════════════════════════════════════════════════
print("Loading link files...")
bas = pd.read_csv(f"{BASE_DIR}/009.output_links.csv.gz", sep=';', low_memory=False)
pol = pd.read_csv(f"{POL_DIR}/matsim-open-dresden-scenario-1pct-20260504_4.output_links.csv.gz",
                  sep=';', low_memory=False)
for df in (bas, pol):
    df['link'] = df['link'].astype(str)
    df['name_s'] = df['name'].astype(str)

def get_vol(df, link_ids):
    sub = df[df['link'].isin([str(l) for l in link_ids])]
    return float(sub['vol_car'].sum()) if 'vol_car' in sub.columns else 0.0

def links_by_name(df, name_exact):
    """Return car link IDs whose name exactly matches (case-insensitive)."""
    mask = (df['name_s'].str.lower() == name_exact.lower()) & \
            df['modes'].str.contains('car', na=False)
    return df.loc[mask, 'link'].tolist()

# ══════════════════════════════════════════════════════════════════════════════
# PART A — Bridge volume table
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("PART A — Cross-Elbe car volume redistribution")
print("="*70)

# For volume totals use ALL directional links named for each bridge
bridge_groups = {
    'Carolabrücke':         ('Layer 1 (closed)',     links_by_name(bas, 'Carolabrücke')),
    'Albertbrücke':         ('Layer 2 (cap −50%)',   links_by_name(bas, 'Albertbrücke')),
    'Augustusbrücke':       ('Layer 2 (cap −50%)',   links_by_name(bas, 'Augustusbrücke')),
    'Marienbrücke':         ('Spillover',             links_by_name(bas, 'Marienbrücke')),
    'Waldschlößchenbrücke': ('Spillover',             links_by_name(bas, 'Waldschlößchenbrücke')),
    'Flügelwegbrücke':      ('Spillover',             links_by_name(bas, 'Flügelwegbrücke')),
    'Loschwitzer Brücke':   ('Spillover',             links_by_name(bas, 'Loschwitzer Brücke')),
}

print(f"\n{'Bridge':<26} {'Layer':<22} {'#links':>6} {'BASE vol':>10} {'POL vol':>10} {'Δ %':>8}")
print("-"*85)

rows_br = []
total_b, total_p = 0.0, 0.0
for name, (layer, ids) in bridge_groups.items():
    b = get_vol(bas, ids)
    p = get_vol(pol, ids)
    pct = (p - b) / b * 100 if b > 0 else 0
    total_b += b; total_p += p
    print(f"{name:<26} {layer:<22} {len(ids):>6} {b:>10.0f} {p:>10.0f} {pct:>+7.1f}%")
    rows_br.append({'bridge':name, 'layer':layer, 'n_links':len(ids),
                    'base_vol_car':b, 'policy_vol_car':p, 'pct_change':round(pct,1)})

print("-"*85)
total_pct = (total_p - total_b) / total_b * 100 if total_b > 0 else 0
print(f"{'TOTAL':<26} {'':<22} {'':<6} {total_b:>10.0f} {total_p:>10.0f} {total_pct:>+7.1f}%")
print(f"\n  Full-population estimates (×100):")
print(f"    BASE:   {total_b*100:>10,.0f} daily car crossings")
print(f"    POLICY: {total_p*100:>10,.0f} daily car crossings")
print(f"    Net:    {(total_p-total_b)*100:>+10,.0f} daily car crossings")

pd.DataFrame(rows_br).to_csv(f"{OUT}/step7_cross_elbe_redistribution.csv", index=False)

# ══════════════════════════════════════════════════════════════════════════════
# PART B — Layer 3: feeder gating check
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("PART B — Layer 3: Feeder link volumes")
print("="*70)

feeder_b = get_vol(bas, FEEDERS_CAR)
feeder_p = get_vol(pol, FEEDERS_CAR)
feeder_pct = (feeder_p - feeder_b) / feeder_b * 100 if feeder_b > 0 else 0
print(f"\nTotal feeder vol_car ({len(FEEDERS_CAR)} links):")
print(f"  BASE:   {feeder_b:>8.0f}")
print(f"  POLICY: {feeder_p:>8.0f}  ({feeder_pct:+.1f}%)")

feeder_rows = []
for lid in FEEDERS_CAR:
    b = get_vol(bas, [lid]); p = get_vol(pol, [lid])
    name = bas.loc[bas['link']==str(lid), 'name'].values
    name = name[0] if len(name) else ''
    feeder_rows.append({'link':lid, 'name':name, 'base':b, 'policy':p,
                        'delta':p-b, 'pct':(p-b)/b*100 if b>0 else 0})
df_feed = pd.DataFrame(feeder_rows).sort_values('delta')
print(f"\nTop 5 feeder DROPS (gating working):")
print(df_feed.head(5)[['link','name','base','policy','delta','pct']].to_string(index=False))
print(f"\nTop 5 feeder INCREASES (reroute targets):")
print(df_feed.tail(5)[['link','name','base','policy','delta','pct']].to_string(index=False))
df_feed.to_csv(f"{OUT}/step7_feeder_volumes.csv", index=False)

# ══════════════════════════════════════════════════════════════════════════════
# PART C — Per-bridge subgroup: mode shift
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("PART C — Mode shift by bridge-user subgroup")
print("="*70)

aff_groups = pd.read_csv(f"{OUT}/step3_affected_agents.csv")
aff_groups['person_id'] = aff_groups['person_id'].astype(str)

bt = pd.read_csv(f"{BASE_DIR}/009.output_trips.csv.gz", sep=';', low_memory=False)
pt_df = pd.read_csv(
    f"{POL_DIR}/matsim-open-dresden-scenario-1pct-20260504_4.output_trips.csv.gz",
    sep=';', low_memory=False)
for df in (bt, pt_df):
    df['person'] = df['person'].astype(str)
bt = bt[~bt['main_mode'].isin(EXCL)].copy()
pt_df = pt_df[~pt_df['main_mode'].isin(EXCL)].copy()

subgroups = {
    'Carola users':        aff_groups[aff_groups['used_carola']]['person_id'].tolist(),
    'Albertbrücke users':  aff_groups[aff_groups['used_albertbruecke']]['person_id'].tolist(),
    'Augustusbrücke users':aff_groups[aff_groups['used_augustusbruecke']]['person_id'].tolist(),
    'Feeder-only users':   aff_groups[
        aff_groups['used_feeder'] &
        ~aff_groups['used_carola'] &
        ~aff_groups['used_albertbruecke'] &
        ~aff_groups['used_augustusbruecke']
    ]['person_id'].tolist(),
}

print(f"\n{'Subgroup':<22} {'N':>5} {'Δcar pp':>9} {'Δpt pp':>9} {'Δwalk pp':>9} {'Δride pp':>9} {'Δbike pp':>9}")
print("-"*77)
sub_rows = []
for label, ids in subgroups.items():
    bsub = bt[bt['person'].isin(ids)]
    psub = pt_df[pt_df['person'].isin(ids)]
    if len(bsub) == 0:
        print(f"{label:<22} {len(ids):>5}  (no BASE trips)")
        continue
    bs = (bsub['main_mode'].value_counts(normalize=True)*100)
    ps = (psub['main_mode'].value_counts(normalize=True)*100)
    d = {m: float(ps.get(m,0)) - float(bs.get(m,0)) for m in MODES}
    print(f"{label:<22} {len(ids):>5} {d['car']:>+8.1f} {d['pt']:>+8.1f} "
          f"{d['walk']:>+8.1f} {d['ride']:>+8.1f} {d['bike']:>+8.1f}")
    sub_rows.append({'subgroup':label, 'n':len(ids),
                     'base_car_pct': float(bs.get('car',0)),
                     'policy_car_pct': float(ps.get('car',0)),
                     **{f'delta_{m}': d[m] for m in MODES}})
    # Full mode shares for this subgroup
    print(f"  BASE:   " + "  ".join(f"{m}={float(bs.get(m,0)):.1f}%" for m in MODES))
    print(f"  POLICY: " + "  ".join(f"{m}={float(ps.get(m,0)):.1f}%" for m in MODES))

pd.DataFrame(sub_rows).to_csv(f"{OUT}/step7_per_bridge_subgroups.csv", index=False)

# ══════════════════════════════════════════════════════════════════════════════
# PART D — Figure: redistribution bar chart
# ══════════════════════════════════════════════════════════════════════════════
df_br = pd.DataFrame(rows_br)
df_plot = df_br[df_br['base_vol_car'] > 0].copy()

fig, ax = plt.subplots(figsize=(11, 5.5))
x = np.arange(len(df_plot)); w = 0.38
color_map = {
    'Layer 1 (closed)':   '#E63946',
    'Layer 2 (cap −50%)': '#F4A261',
    'Spillover':          '#2E86AB',
}
colors_p = [color_map[l] for l in df_plot['layer']]

ax.bar(x - w/2, df_plot['base_vol_car']*100,  w, label='BASE',
       color='#888', edgecolor='black')
ax.bar(x + w/2, df_plot['policy_vol_car']*100, w, label='POLICY',
       color=colors_p, edgecolor='black')

ax.set_xticks(x)
ax.set_xticklabels(df_plot['bridge'], rotation=22, ha='right', fontsize=10)
ax.set_ylabel('Daily car crossings (full-pop est., vol ×100)')
ax.set_title('Cross-Elbe car volume redistribution: BASE vs POLICY')

for i, (_, row) in enumerate(df_plot.iterrows()):
    pct = row['pct_change']
    color = '#E63946' if pct > 5 else '#06A77D' if pct < -5 else 'black'
    ax.annotate(f"{pct:+.0f}%",
                xy=(i + w/2, row['policy_vol_car']*100),
                xytext=(0, 6), textcoords='offset points',
                ha='center', fontsize=10, fontweight='bold', color=color)

ax.legend(handles=[
    mpatches.Patch(color='#888',     label='BASE'),
    mpatches.Patch(color='#E63946', label='Layer 1: Closed'),
    mpatches.Patch(color='#F4A261', label='Layer 2: Cap −50%'),
    mpatches.Patch(color='#2E86AB', label='Spillover (unmodified)'),
], loc='upper right', fontsize=9)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig(f"{FIG}/fig7_cross_elbe_redistribution.png", dpi=300, bbox_inches='tight')
plt.close()
print(f"\n✅ fig7_cross_elbe_redistribution.png")
print(f"✅ step7_cross_elbe_redistribution.csv")
print(f"✅ step7_feeder_volumes.csv")
print(f"✅ step7_per_bridge_subgroups.csv")
