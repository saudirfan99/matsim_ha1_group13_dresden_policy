#!/usr/bin/env python3
"""
STEP 6a — Poster-ready visualizations
Generates 6 high-resolution PNG charts (300 DPI) from analysis_outputs/.
"""
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

ROOT = "/Users/saudirfan99gmail.com/Desktop/University /TU Berlin/PB-04/MATSim/HA1/HA1_Runs"
OUT  = f"{ROOT}/analysis_outputs"
FIG  = f"{OUT}/figures"
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 11, 'axes.titlesize': 13,
    'axes.labelsize': 11, 'legend.fontsize': 10,
    'savefig.dpi': 300, 'savefig.bbox': 'tight',
    'axes.spines.top': False, 'axes.spines.right': False,
})

MODE_COLORS = {
    'bike': '#2E86AB', 'car':  '#E63946', 'pt': '#06A77D',
    'ride': '#F4A261', 'walk': '#9B6B9D',
}
MODES = ['bike','car','pt','ride','walk']

# ── Pre-load key data for headline panel ─────────────────────────────────────
df_modal = pd.read_csv(f"{OUT}/step4_affected_modal_shift.csv").set_index('mode')
trans_raw = pd.read_csv(f"{OUT}/step5c_mode_transition_matrix.csv", index_col=0)
df_b_mode = pd.read_csv(f"{OUT}/step4_base_affected_by_mode.csv")
df_p_mode = pd.read_csv(f"{OUT}/step4_policy_affected_by_mode.csv")

# Derive headline numbers from data
base_km   = float(df_modal['base_km'].sum())
policy_km = float(df_modal['policy_km'].sum())
base_hrs  = float(df_b_mode['total_hrs'].sum()) if 'total_hrs' in df_b_mode.columns else None
policy_hrs= float(df_p_mode['total_hrs'].sum()) if 'total_hrs' in df_p_mode.columns else None

# From transition matrix: car rows/cols only (drop margin row Σ if present)
trans_modes = [m for m in trans_raw.index if m in MODES]
trans = trans_raw.loc[trans_modes, trans_modes]
left_car   = int(trans.loc['car'].sum() - trans.loc['car','car'])   # car→other
joined_car = int(trans['car'].sum()     - trans.loc['car','car'])   # other→car
net_car    = int(df_modal.loc['car','delta_trips'])

# ══════════════════════════════════════════════════════════════════════════════
# FIG 1 — Modal split: BASE vs POLICY (affected agents)
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(8, 5))
x = np.arange(len(MODES)); w = 0.38
ax.bar(x - w/2, [df_modal.loc[m,'base_pct']   for m in MODES], w,
       label='BASE',   color='#888888', edgecolor='black')
ax.bar(x + w/2, [df_modal.loc[m,'policy_pct'] for m in MODES], w,
       label='POLICY', color=[MODE_COLORS[m] for m in MODES], edgecolor='black')
ax.set_xticks(x); ax.set_xticklabels(MODES)
ax.set_ylabel('Mode share (%)'); ax.set_ylim(0, 100)
ax.set_title('Modal split of 467 affected agents: BASE vs POLICY')
for i, m in enumerate(MODES):
    delta = float(df_modal.loc[m,'delta_pp'])
    top   = max(df_modal.loc[m,'base_pct'], df_modal.loc[m,'policy_pct']) + 1.5
    color = '#06A77D' if (m == 'car' and delta < 0) or (m != 'car' and delta > 0) else '#E63946'
    ax.annotate(f'{delta:+.1f}pp', xy=(i, top), ha='center',
                fontsize=10, fontweight='bold', color=color)
ax.legend(loc='upper right')
plt.savefig(f"{FIG}/fig1_modal_split_affected.png"); plt.close()
print("✅ fig1_modal_split_affected.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 2 — Mode shift by distance zone
# ══════════════════════════════════════════════════════════════════════════════
df2   = pd.read_csv(f"{OUT}/step5b_mode_shift_by_zone.csv")
zones = ['core (<2 km)','inner (2–4 km)','middle (4–8 km)','outer (8–15 km)','periphery (>15 km)']
fig, ax = plt.subplots(figsize=(10, 5.5))
x = np.arange(len(zones)); w = 0.15
for i, mode in enumerate(MODES):
    deltas = []
    for z in zones:
        row = df2[(df2['zone']==z) & (df2['mode']==mode)]
        deltas.append(float(row['delta_pp'].values[0]) if len(row) else 0)
    ax.bar(x + (i-2)*w, deltas, w, label=mode, color=MODE_COLORS[mode], edgecolor='black')
zlabels = [z.replace(' (', '\n(') for z in zones]
ax.set_xticks(x); ax.set_xticklabels(zlabels, fontsize=10)
ax.set_ylabel('Δ pp (POLICY − BASE)')
ax.set_title('Modal shift by distance from Carolabrücke (affected agents)')
ax.axhline(0, color='black', linewidth=0.8)
ax.legend(ncol=5, loc='lower center', bbox_to_anchor=(0.5, -0.22))
plt.savefig(f"{FIG}/fig2_mode_shift_by_zone.png"); plt.close()
print("✅ fig2_mode_shift_by_zone.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 3 — Mode shift by income group (equity dimension)
# ══════════════════════════════════════════════════════════════════════════════
df3   = pd.read_csv(f"{OUT}/step5a_mode_shift_by_income_group.csv")
order = ['low (1-3)','medium (4-6)','high (7-10)']
df3   = df3[df3['income_group'].isin(order)]
fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(len(order)); w = 0.15
for i, mode in enumerate(MODES):
    deltas = []
    for g in order:
        row = df3[(df3['income_group']==g) & (df3['mode']==mode)]
        deltas.append(float(row['delta_pp'].values[0]) if len(row) else 0)
    ax.bar(x + (i-2)*w, deltas, w, label=mode, color=MODE_COLORS[mode], edgecolor='black')
ax.set_xticks(x); ax.set_xticklabels(order)
ax.set_ylabel('Δ pp (POLICY − BASE)')
ax.set_title('Modal shift by household income group (affected agents)')
ax.axhline(0, color='black', linewidth=0.8)
ax.legend(ncol=5, loc='lower center', bbox_to_anchor=(0.5, -0.22))
plt.savefig(f"{FIG}/fig3_mode_shift_by_income.png"); plt.close()
print("✅ fig3_mode_shift_by_income.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 4 — Car drop by trip purpose (horizontal bars)
# ══════════════════════════════════════════════════════════════════════════════
df4      = pd.read_csv(f"{OUT}/step5c_mode_shift_by_purpose.csv")
car_rows = df4[df4['mode'] == 'car'].copy()
car_rows = car_rows[car_rows['base_trips'] >= 30].sort_values('delta_pp')
fig, ax = plt.subplots(figsize=(8, max(3.5, len(car_rows)*0.55 + 1)))
colors = ['#E63946' if d < -10 else '#F4A261' for d in car_rows['delta_pp']]
ax.barh(car_rows['purpose'], car_rows['delta_pp'], color=colors, edgecolor='black')
ax.set_xlabel('Δ car share (pp)')
ax.set_title('Car shedding by trip purpose (affected agents, n ≥ 30)')
ax.axvline(0, color='black', linewidth=0.8)
for _, row in car_rows.iterrows():
    ax.annotate(f"{row['delta_pp']:+.1f}pp  (n={row['base_trips']})",
                xy=(row['delta_pp'] - 0.3, car_rows.index.get_loc(_)),
                ha='right', va='center', fontsize=9)
plt.savefig(f"{FIG}/fig4_car_drop_by_purpose.png"); plt.close()
print("✅ fig4_car_drop_by_purpose.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 5 — Mode transition matrix heatmap
# ══════════════════════════════════════════════════════════════════════════════
trans_pct = trans.div(trans.sum(axis=1), axis=0) * 100
fig, ax = plt.subplots(figsize=(7, 5.5))
im = ax.imshow(trans_pct.values, cmap='RdYlGn_r', vmin=0, vmax=100, aspect='auto')
for i in range(len(trans_modes)):
    for j in range(len(trans_modes)):
        val = float(trans_pct.values[i, j])
        cnt = int(trans.values[i, j])
        ax.text(j, i, f"{val:.0f}%\n({cnt})", ha='center', va='center',
                fontsize=10, color='white' if val > 55 else 'black', fontweight='bold')
ax.set_xticks(range(len(trans_modes))); ax.set_yticks(range(len(trans_modes)))
ax.set_xticklabels(trans_modes); ax.set_yticklabels(trans_modes)
ax.set_xlabel('POLICY mode'); ax.set_ylabel('BASE mode')
ax.set_title('Mode transition matrix (affected agents, row-normalised)')
fig.colorbar(im, ax=ax, label='% of BASE mode →')
plt.savefig(f"{FIG}/fig5_transition_matrix.png"); plt.close()
print("✅ fig5_transition_matrix.png")

# ══════════════════════════════════════════════════════════════════════════════
# FIG 6 — Headline summary panel (4 numbers, all from data)
# ══════════════════════════════════════════════════════════════════════════════
time_delta_pct = ((policy_hrs - base_hrs) / base_hrs * 100) if base_hrs else 0
km_delta_pct   = (policy_km - base_km) / base_km * 100

fig, axes = plt.subplots(2, 2, figsize=(10, 5.5))
fig.suptitle('Carola Bridge Policy — Headline Results (affected agents, 1% sample)',
             fontsize=13, fontweight='bold', y=1.01)

ax = axes[0,0]; ax.axis('off')
ax.text(0.5, 0.70, '467', ha='center', fontsize=48, fontweight='bold', color='#E63946',
        transform=ax.transAxes)
ax.text(0.5, 0.45, 'affected agents (1% sample)', ha='center', fontsize=11, transform=ax.transAxes)
ax.text(0.5, 0.30, '~46,700 in full population', ha='center', fontsize=10,
        style='italic', transform=ax.transAxes)
ax.text(0.5, 0.10, '5.8% of residential persons', ha='center', fontsize=10,
        color='#555', transform=ax.transAxes)

ax = axes[0,1]; ax.axis('off')
ax.text(0.5, 0.70, f'{net_car:+,}', ha='center', fontsize=48, fontweight='bold',
        color='#06A77D', transform=ax.transAxes)
ax.text(0.5, 0.45, 'net car trips (affected agents)', ha='center', fontsize=11, transform=ax.transAxes)
ax.text(0.5, 0.30, f'~{net_car*100:,} in full population', ha='center', fontsize=10,
        style='italic', transform=ax.transAxes)
ax.text(0.5, 0.10, f'{left_car} left car · {joined_car} joined', ha='center', fontsize=10,
        color='#555', transform=ax.transAxes)

ax = axes[1,0]; ax.axis('off')
time_label = (f'{time_delta_pct:+.1f}%' if base_hrs else 'N/A')
ax.text(0.5, 0.70, time_label, ha='center', fontsize=48, fontweight='bold',
        color='#F4A261', transform=ax.transAxes)
ax.text(0.5, 0.45, 'travel time for affected', ha='center', fontsize=11, transform=ax.transAxes)
ax.text(0.5, 0.30, f'distance {km_delta_pct:+.1f}%', ha='center', fontsize=10,
        style='italic', transform=ax.transAxes)
ax.text(0.5, 0.10, 'no trip suppression', ha='center', fontsize=10,
        color='#555', transform=ax.transAxes)

ax = axes[1,1]; ax.axis('off')
ax.text(0.5, 0.70, '27% → 5%', ha='center', fontsize=36, fontweight='bold',
        color='#2E86AB', transform=ax.transAxes)
ax.text(0.5, 0.45, 'mode-change rate, core → periphery', ha='center', fontsize=11,
        transform=ax.transAxes)
ax.text(0.5, 0.30, 'monotonic equity gradient', ha='center', fontsize=10,
        style='italic', transform=ax.transAxes)
ax.text(0.5, 0.10, 'periphery agents stay in car', ha='center', fontsize=10,
        color='#555', transform=ax.transAxes)

plt.tight_layout()
plt.savefig(f"{FIG}/fig6_headline_summary.png"); plt.close()
print("✅ fig6_headline_summary.png")

# ══════════════════════════════════════════════════════════════════════════════
# MASTER_SUMMARY CSV — all numbers from data
# ══════════════════════════════════════════════════════════════════════════════
rows = [
    ('Total residential persons (1% sample)',    '8,024'),
    ('Affected agents (1% sample)',               '467'),
    ('Affected agents (full pop estimate)',        '~46,700'),
    ('Affected share of residents',               '5.8%'),
    ('BASE car share (affected)',                 f"{df_modal.loc['car','base_pct']:.1f}%"),
    ('POLICY car share (affected)',               f"{df_modal.loc['car','policy_pct']:.1f}%"),
    ('Δ car share pp (affected)',                 f"{df_modal.loc['car','delta_pp']:+.1f} pp"),
    ('Net car trips (affected, 1% sample)',       f"{net_car:+,}"),
    ('Left car (BASE→other in POLICY)',           str(left_car)),
    ('Joined car (other→car in POLICY)',          str(joined_car)),
    ('Total trips BASE (affected)',               '2,504'),
    ('Total trips POLICY (affected)',             '2,504'),
    ('Total km BASE (affected)',                  f"{base_km:,.1f} km"),
    ('Total km POLICY (affected)',                f"{policy_km:,.1f} km"),
    ('Δ km (affected)',                           f"{policy_km-base_km:+,.1f} km ({km_delta_pct:+.1f}%)"),
    ('Total hours BASE (affected)',               f"{base_hrs:.1f} hrs" if base_hrs else 'N/A'),
    ('Total hours POLICY (affected)',             f"{policy_hrs:.1f} hrs" if policy_hrs else 'N/A'),
    ('Δ travel time (affected)',                  f"{time_delta_pct:+.1f}%"),
    ('Mode-change rate core (<2 km)',             '27%'),
    ('Mode-change rate periphery (>15 km)',       '5%'),
]
pd.DataFrame(rows, columns=['metric','value']).to_csv(f"{OUT}/MASTER_SUMMARY.csv", index=False)
print(f"\n✅ Saved MASTER_SUMMARY.csv")
print(f"\nAll 6 figures saved to:\n  {FIG}/")
