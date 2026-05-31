#!/usr/bin/env python3
"""
STEP 3 — Affected Agents Identification + Corrected Modal Split
Scans BASE events for persons who used any modified car link.
Filters strictly to residential subpopulation via output_persons.csv.gz.
Outputs: affected_persons.txt, step3_affected_summary.csv, step2b_modal_split_corrected.csv
"""
import gzip, os, re
import xml.etree.ElementTree as ET
import pandas as pd

ROOT     = "/Users/saudirfan99gmail.com/Desktop/University /TU Berlin/PB-04/MATSim/HA1/HA1_Runs"
BASE_DIR = f"{ROOT}/dresden-v1.0-output-1pct_BASE"
POL_DIR  = f"{ROOT}/dresden-v1.0-output-1pct_POLICY"
POL_ANA  = f"{POL_DIR}/analysis/population"
OUT_DIR  = f"{ROOT}/analysis_outputs"
os.makedirs(OUT_DIR, exist_ok=True)

# ── MODIFIED LINK SETS ────────────────────────────────────────────────────────
CAROLA_CAR  = {"901959078", "4214231"}
ALBER_CAR   = {"505502627#0", "-264360396#1"}
AUGUS_CAR   = {"-264360404", "1031454500"}
FEEDERS     = {
    # Augustusbrücke feeders
    "-376145739","237502199","-1329159900","4265202","-99478092","60611109#0",
    # Carolabrücke feeders
    "4214230","379745367","24209438","25702467#0","657862430","1108789888",
    "150611226","867018480","415552984","138307399",
    # Albertbrücke feeders
    "439458122","-294983108","294983108","-504890257","-369971087","1036528789",
    "504885692","233822748#1","213544718","443697736",
    # Confirmed changeset links (retroactively added)
    "4539657","12497357"
}
ALL_MODIFIED = CAROLA_CAR | ALBER_CAR | AUGUS_CAR | FEEDERS

def link_group(lid):
    if lid in CAROLA_CAR:  return "Carola_car_closed"
    if lid in ALBER_CAR:   return "Albertbruecke_car_reduced"
    if lid in AUGUS_CAR:   return "Augustusbruecke_car_reduced"
    if lid in FEEDERS:     return "Feeder"
    return "other"

# ══════════════════════════════════════════════════════════════════════════════
# STEP A — Load residential person IDs from BASE persons file
# ══════════════════════════════════════════════════════════════════════════════
print("="*65)
print("STEP A — Loading residential person IDs")
print("="*65)

base_persons_path = f"{BASE_DIR}/009.output_persons.csv.gz"
pol_persons_path  = f"{POL_DIR}/matsim-open-dresden-scenario-1pct-20260504_4.output_persons.csv.gz"

def load_residential_ids(path, label):
    df = pd.read_csv(path, sep=';', low_memory=False)
    print(f"\n{label} persons file columns: {df.columns.tolist()[:10]}")
    print(f"Total rows: {len(df):,}")
    # Identify subpopulation column
    sub_col = None
    for c in ['subpopulation','Subpopulation','sub_population']:
        if c in df.columns:
            sub_col = c
            break
    if sub_col:
        print(f"Subpopulation counts:\n{df[sub_col].value_counts().head(10)}")
        residential = df[df[sub_col] == 'person']['person'].astype(str).tolist() \
                      if 'person' in df.columns \
                      else df[df[sub_col] == 'person'].iloc[:,0].astype(str).tolist()
    else:
        print("No subpopulation column found — using numeric ID filter only")
        id_col = 'person' if 'person' in df.columns else df.columns[0]
        residential = df[df[id_col].astype(str).str.match(r'^\d+$')][id_col].astype(str).tolist()
    print(f"Residential person count: {len(residential):,}")
    return set(residential)

base_residential = load_residential_ids(base_persons_path, "BASE")
pol_residential  = load_residential_ids(pol_persons_path,  "POLICY")

# ══════════════════════════════════════════════════════════════════════════════
# STEP B — Corrected Modal Split (BASE trips filtered to residential)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*65)
print("STEP B — Corrected BASE modal split (residential only)")
print("="*65)

base_trips_path = f"{BASE_DIR}/009.output_trips.csv.gz"
base_trips_raw  = pd.read_csv(base_trips_path, sep=';', low_memory=False)
print(f"BASE trips total rows: {len(base_trips_raw):,}")
print(f"Columns sample: {base_trips_raw.columns.tolist()[:12]}")

# Identify key columns
pid_col    = 'person' if 'person' in base_trips_raw.columns else base_trips_raw.columns[0]
mode_col   = next((c for c in base_trips_raw.columns
                   if c in ('main_mode','mode','longest_distance_mode')), None)
dist_col   = next((c for c in base_trips_raw.columns
                   if 'distance' in c.lower() and 'traveled' in c.lower()), None) \
          or next((c for c in base_trips_raw.columns if 'distance' in c.lower()), None)
time_col   = next((c for c in base_trips_raw.columns
                   if 'travel_time' in c.lower() or 'trav_time' in c.lower()), None)

print(f"Using: person='{pid_col}', mode='{mode_col}', dist='{dist_col}', time='{time_col}'")

base_trips_raw[pid_col] = base_trips_raw[pid_col].astype(str)
EXCL_MODES = {'truck8t','truck40t','truck18t'}

# Filter to residential persons only (strict subpopulation filter)
base_res_trips = base_trips_raw[
    base_trips_raw[pid_col].isin(base_residential) &
    ~base_trips_raw[mode_col].isin(EXCL_MODES)
].copy()
print(f"BASE residential trips (filtered): {len(base_res_trips):,}")

base_counts = base_res_trips[mode_col].value_counts()
base_total  = base_counts.sum()
base_share  = (base_counts / base_total * 100).round(2)

# POLICY modal split from pre-computed file
pol_ms = pd.read_csv(f"{POL_ANA}/mode_share.csv")
print(f"\nPOLICY mode_share columns: {pol_ms.columns.tolist()}")
mode_c  = next(c for c in pol_ms.columns if c in ('main_mode','mode','Mode'))
val_c   = next(c for c in pol_ms.columns if c in ('count','trips','n','share','amount'))
pol_ms_f = pol_ms[~pol_ms[mode_c].isin(EXCL_MODES)].copy()
# Aggregate across distance groups (shares already sum to 1 across all rows)
pol_mode_agg = pol_ms_f.groupby(mode_c)[val_c].sum()
if pol_mode_agg.max() <= 1.01:
    pol_total = len(pol_residential)  # use actual residential count
    pol_counts = (pol_mode_agg * pol_total).round(0)
else:
    pol_counts = pol_mode_agg
    pol_total = pol_counts.sum()
pol_share  = (pol_counts / pol_total * 100).round(2)

print(f"\n{'Mode':<10} {'BASE trips':>11} {'BASE %':>8} {'POL trips':>10} {'POL %':>8} {'Δ pp':>7}")
print("-"*60)
rows_ms = []
for mode in ['bike','car','pt','ride','walk']:
    bn = int(base_counts.get(mode,0)); bs = float(base_share.get(mode,0))
    pn = float(pol_counts.get(mode,0)); ps = float(pol_share.get(mode,0))
    dpp = ps - bs
    print(f"{mode:<10} {bn:>11,} {bs:>7.1f}% {pn:>10,.0f} {ps:>7.1f}% {dpp:>+6.1f}pp")
    rows_ms.append({'mode':mode,'base_trips':bn,'base_pct':bs,
                    'policy_trips':pn,'policy_pct':ps,'delta_pp':dpp})
print(f"{'TOTAL':<10} {base_total:>11,} {'100%':>8} {pol_total:>10,} {'100%':>8}")
pd.DataFrame(rows_ms).to_csv(f"{OUT_DIR}/step2b_modal_split_corrected.csv", index=False)

# ══════════════════════════════════════════════════════════════════════════════
# STEP C — Affected Agents: scan BASE events
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*65)
print("STEP C — Scanning BASE events for affected agents")
print("(This will take several minutes — streaming parse)")
print("="*65)

base_events = f"{BASE_DIR}/009.output_events.xml.gz"
# If uncompressed version exists, it may be faster
base_events_raw = f"{BASE_DIR}/009.output_events.xml"
use_path = base_events_raw if os.path.exists(base_events_raw) else base_events
print(f"Using: {os.path.basename(use_path)}")

# person_id → set of link groups they used
affected = {}       # person_id → set of groups
event_count = 0

def extract_person(vehicle_id):
    """Extract numeric person ID from vehicle ID, stripping known suffixes."""
    v = str(vehicle_id)
    for sfx in ['_car','_bike','_ride','_walk','_pt']:
        if v.endswith(sfx):
            v = v[:-len(sfx)]
            break
    return v if re.match(r'^\d+$', v) else None

opener = open if use_path.endswith('.xml') else gzip.open
mode_arg = 'rb' if use_path.endswith('.gz') else 'r'

with opener(use_path, mode_arg) as f:
    for _, elem in ET.iterparse(f, events=['end']):
        if elem.tag != 'event':
            elem.clear(); continue
        event_count += 1
        if event_count % 3_000_000 == 0:
            print(f"  ... {event_count/1e6:.0f}M events, "
                  f"{len(affected):,} affected persons so far")

        if elem.get('type') == 'entered link':
            lid = elem.get('link','')
            if lid in ALL_MODIFIED:
                vehicle = elem.get('vehicle', elem.get('person',''))
                pid = extract_person(vehicle)
                if pid and pid in base_residential:
                    affected.setdefault(pid, set()).add(link_group(lid))
        elem.clear()

print(f"\nDone. {event_count/1e6:.1f}M events scanned.")
print(f"Unique affected residential persons: {len(affected):,}")

# ── Summary by bridge group ───────────────────────────────────────────────────
from collections import Counter
group_counts = Counter()
for pid, groups in affected.items():
    for g in groups:
        group_counts[g] += 1

# Persons affected by each bridge (may overlap)
carola_only  = {p for p,g in affected.items() if 'Carola_car_closed' in g}
alber_only   = {p for p,g in affected.items() if 'Albertbruecke_car_reduced' in g}
augus_only   = {p for p,g in affected.items() if 'Augustusbruecke_car_reduced' in g}
feeder_only  = {p for p,g in affected.items() if 'Feeder' in g}
all_affected = set(affected.keys())

print(f"\n── Affected persons by link group (persons may appear in multiple groups) ──")
print(f"  Used Carola car links:        {len(carola_only):>6,}")
print(f"  Used Albertbrücke car links:  {len(alber_only):>6,}")
print(f"  Used Augustusbrücke car links:{len(augus_only):>6,}")
print(f"  Used feeder links:            {len(feeder_only):>6,}")
print(f"  ─────────────────────────────────────")
print(f"  TOTAL unique affected:        {len(all_affected):>6,}")
print(f"  (scaled to full population:   {len(all_affected)*100:>6,} estimated)")
print(f"  Share of all residential:     {len(all_affected)/len(base_residential)*100:.1f}%")

# ── Save outputs ─────────────────────────────────────────────────────────────
# affected_persons.txt — one ID per line
with open(f"{OUT_DIR}/affected_persons.txt", 'w') as f:
    for pid in sorted(all_affected):
        f.write(pid + "\n")

# Detailed summary CSV
rows_aff = []
for pid, groups in affected.items():
    rows_aff.append({
        'person_id': pid,
        'used_carola':      'Carola_car_closed' in groups,
        'used_albertbruecke': 'Albertbruecke_car_reduced' in groups,
        'used_augustusbruecke': 'Augustusbruecke_car_reduced' in groups,
        'used_feeder':      'Feeder' in groups,
        'group_count':      len(groups),
    })
df_aff = pd.DataFrame(rows_aff)
df_aff.to_csv(f"{OUT_DIR}/step3_affected_agents.csv", index=False)

print(f"\n✅ Saved: affected_persons.txt ({len(all_affected):,} IDs)")
print(f"✅ Saved: step3_affected_agents.csv")
print(f"✅ Saved: step2b_modal_split_corrected.csv")
print("\nPaste full output. Step 4 is next — affected agent behaviour comparison.")
