#!/usr/bin/env python3
"""
STEP 1 — Network + Behavioural Validation
MATSim Dresden — Carola Bridge Policy (corrected run _4)

Part A: Checks all modified links have correct attributes in POLICY network
Part B: Checks that bike agents actually used the new bike links (events file)

Output: analysis_outputs/step1_network_validation.csv
        analysis_outputs/step1_bike_link_usage.csv
"""

import gzip, os, re
import xml.etree.ElementTree as ET
import pandas as pd

# ── PATHS ──────────────────────────────────────────────────────────────────────
ROOT     = "/Users/saudirfan99gmail.com/Desktop/University /TU Berlin/PB-04/MATSim/HA1/HA1_Runs"
BASE_NET = f"{ROOT}/dresden-v1.0-output-1pct_BASE/009.output_network.xml.gz"
POL_NET  = f"{ROOT}/dresden-v1.0-output-1pct_POLICY/matsim-open-dresden-scenario-1pct-20260504_4.output_network.xml.gz"
POL_EVT  = f"{ROOT}/dresden-v1.0-output-1pct_POLICY/matsim-open-dresden-scenario-1pct-20260504_4.output_events.xml.gz"
OUT_DIR  = f"{ROOT}/analysis_outputs"
os.makedirs(OUT_DIR, exist_ok=True)

# ── CHANGESET DEFINITION ───────────────────────────────────────────────────────
CAROLA_CAR  = {"901959078", "4214231"}
ALBER_CAR   = {"505502627#0", "-264360396#1"}
AUGUS_CAR   = {"-264360404", "1031454500"}
FEEDERS     = {
    "-376145739","237502199","-1329159900","4265202","-99478092","60611109#0",
    "4214230","379745367","24209438","25702467#0","657862430","1108789888",
    "150611226","867018480","415552984","138307399",
    "439458122","-294983108","294983108","-504890257","-369971087","1036528789",
    "504885692","233822748#1","213544718","443697736"
}
UNEXPECTED  = {"4539657", "12497357"}

# Bike link prefixes (UUIDs may be truncated — we match by prefix, collect full IDs from network)
BIKE_PREFIXES = {
    "Carola_BIKE":       ["5c67424c-adc0-439e-92d9-", "d5c6ef5d-151d-46ca-81"],
    "Albertbruecke_BIKE":["9305fbe8-9543-4eae-91a1-", "ccf512b2-7eca-406d-b4cf-"],
    "Augustusbruecke_BIKE":["859a1330-0bed-45b2-ad70-", "d4de14b2-f040-4589-a0a1-"],
}

ALL_EXACT = CAROLA_CAR | ALBER_CAR | AUGUS_CAR | FEEDERS | UNEXPECTED

def classify(lid):
    if lid in CAROLA_CAR:    return "Carola_CAR_closed"
    if lid in ALBER_CAR:     return "Albertbruecke_CAR"
    if lid in AUGUS_CAR:     return "Augustusbruecke_CAR"
    if lid in FEEDERS:       return "Feeder"
    if lid in UNEXPECTED:    return "UNEXPECTED_flawed_run"
    for grp, prefixes in BIKE_PREFIXES.items():
        for p in prefixes:
            if lid.startswith(p[:min(len(p),24)]): return grp
    return None

def is_relevant(lid):
    if lid in ALL_EXACT: return True
    for prefixes in BIKE_PREFIXES.values():
        for p in prefixes:
            if lid.startswith(p[:min(len(p),24)]): return True
    return False

# ══════════════════════════════════════════════════════════════════════════════
# PART A — NETWORK STRUCTURAL VALIDATION
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("PART A — NETWORK STRUCTURAL VALIDATION")
print("="*70)

def parse_network(path, label):
    print(f"\nParsing {label} network: {os.path.basename(path)}")
    links = {}
    with gzip.open(path, 'rb') as f:
        for _, elem in ET.iterparse(f, events=['end']):
            if elem.tag == 'link':
                lid = elem.get('id','')
                if is_relevant(lid):
                    links[lid] = {
                        'freespeed': elem.get('freespeed','?'),
                        'capacity':  elem.get('capacity','?'),
                        'permlanes': elem.get('permlanes','?'),
                        'modes':     elem.get('modes','?'),
                        'length':    elem.get('length','?'),
                        'from_node': elem.get('from','?'),
                        'to_node':   elem.get('to','?'),
                    }
                elem.clear()
    print(f"  → {len(links)} relevant links found")
    return links

base_links   = parse_network(BASE_NET, "BASE")
policy_links = parse_network(POL_NET,  "POLICY")

# Collect full bike link IDs discovered in POLICY network (used in Part B)
bike_links_found = {}  # group → [full_lid, ...]
for lid, attrs in policy_links.items():
    grp = classify(lid)
    if grp and 'BIKE' in grp:
        bike_links_found.setdefault(grp, []).append(lid)

print(f"\nNew bike links found in POLICY network by group:")
for grp, ids in bike_links_found.items():
    print(f"  {grp}: {ids}")

# ── Build comparison rows ─────────────────────────────────────────────────────
all_ids = sorted(set(list(base_links.keys()) + list(policy_links.keys())))
rows = []

for lid in all_ids:
    grp = classify(lid)
    if grp is None: continue
    b = base_links.get(lid)
    p = policy_links.get(lid)
    issues = []

    if grp == "Carola_CAR_closed":
        if p is None:
            issues.append("MISSING from POLICY")
        else:
            fs  = float(p['freespeed']) if p['freespeed'] not in ('?','') else None
            cap = float(p['capacity'])  if p['capacity']  not in ('?','') else None
            if fs  is not None and abs(fs - 0.1) > 0.01:  issues.append(f"freespeed={fs:.3f} (expected 0.1)")
            if cap is not None and cap > 2:                issues.append(f"capacity={cap} (expected 1)")

    elif grp in ("Albertbruecke_CAR","Augustusbruecke_CAR"):
        if b and p:
            try:
                ratio = float(p['capacity']) / float(b['capacity'])
                if abs(ratio - 0.5) > 0.08: issues.append(f"capacity ratio={ratio:.3f} (expected 0.50)")
            except: issues.append("cannot compute ratio")

    elif grp == "Feeder":
        if b and p:
            try:
                ratio = float(p['capacity']) / float(b['capacity'])
                if abs(ratio - 0.8) > 0.08: issues.append(f"capacity ratio={ratio:.3f} (expected 0.80)")
            except: issues.append("cannot compute ratio")

    elif 'BIKE' in grp:
        if p is None:
            issues.append("MISSING from POLICY — bike link not created")
        else:
            fs  = float(p['freespeed']) if p['freespeed'] not in ('?','') else None
            cap = float(p['capacity'])  if p['capacity']  not in ('?','') else None
            modes = str(p['modes'])
            if fs  and abs(fs - 7.0) > 0.5:   issues.append(f"freespeed={fs} (expected 7.0)")
            if cap and abs(cap - 1200) > 100:  issues.append(f"capacity={cap} (expected 1200)")
            if 'bike' not in modes.lower():    issues.append(f"modes='{modes}' — bike missing")
            if b is not None:                  issues.append("NOTE: link existed in BASE too")

    elif grp == "UNEXPECTED_flawed_run":
        if b and p:
            try:
                cap_changed = abs(float(b['capacity']) - float(p['capacity'])) > 1
                fs_changed  = abs(float(b['freespeed']) - float(p['freespeed'])) > 0.01
                if cap_changed or fs_changed:
                    issues.append(f"⚠️ CHANGED in _4: cap {b['capacity']}→{p['capacity']}, fs {b['freespeed']}→{p['freespeed']}")
            except: pass

    # Capacity ratio for reporting
    cap_ratio = None
    if b and p:
        try:   cap_ratio = round(float(p['capacity']) / float(b['capacity']), 4)
        except: pass

    rows.append({
        'link_id':        lid,
        'group':          grp,
        'in_BASE':        b is not None,
        'in_POLICY':      p is not None,
        'BASE_freespeed': b['freespeed']  if b else 'ABSENT',
        'BASE_capacity':  b['capacity']   if b else 'ABSENT',
        'BASE_modes':     b['modes']      if b else 'ABSENT',
        'POL_freespeed':  p['freespeed']  if p else 'ABSENT',
        'POL_capacity':   p['capacity']   if p else 'ABSENT',
        'POL_modes':      p['modes']      if p else 'ABSENT',
        'capacity_ratio': cap_ratio,
        'issues':         "; ".join(issues) if issues else "OK",
        'status':         "✅ OK" if not issues else ("⚠️  NOTE" if all("NOTE" in i for i in issues) else "❌ FAIL"),
    })

df_net = pd.DataFrame(rows)

# ── Print grouped results ────────────────────────────────────────────────────
for grp in df_net['group'].unique():
    sub = df_net[df_net['group'] == grp]
    print(f"\n── {grp} ({len(sub)} links) ──")
    for _, r in sub.iterrows():
        ratio_str = f"  cap_ratio={r['capacity_ratio']}" if r['capacity_ratio'] is not None else ""
        print(f"  {r['status']}  {str(r['link_id'])[:46]:<48}{ratio_str}  {r['issues']}")

ok = (df_net['status']=='✅ OK').sum()
fail = (df_net['status']=='❌ FAIL').sum()
note = (df_net['status']=='⚠️  NOTE').sum()
print(f"\n── PART A SUMMARY: ✅ OK={ok}  ❌ FAIL={fail}  ⚠️ NOTE={note}  (total checked={len(df_net)}) ──")

df_net.to_csv(f"{OUT_DIR}/step1_network_validation.csv", index=False)

# ══════════════════════════════════════════════════════════════════════════════
# PART B — BEHAVIOURAL VALIDATION: Did bike agents use the new links?
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("PART B — BEHAVIOURAL VALIDATION (events file — may take 2–5 min)")
print("="*70)

# Flatten all discovered bike link IDs from Part A
all_bike_link_ids = {lid for ids in bike_links_found.values() for lid in ids}

if not all_bike_link_ids:
    print("⚠️  No bike links found in POLICY network. Skipping Part B.")
else:
    print(f"Scanning events for {len(all_bike_link_ids)} bike link IDs ...")
    print(f"Bike link IDs: {all_bike_link_ids}\n")

    # We track: for each bike link, which unique vehicle IDs entered it
    # In MATSim with network-routed bike, the vehicle id = person id for bike legs
    link_vehicles  = {lid: set() for lid in all_bike_link_ids}  # lid → set of vehicle IDs
    person_id_re   = re.compile(r'^\d+$')                        # numeric = regular person

    event_count = 0
    hit_count   = 0

    with gzip.open(POL_EVT, 'rb') as f:
        for _, elem in ET.iterparse(f, events=['end']):
            if elem.tag == 'event':
                event_count += 1
                if event_count % 2_000_000 == 0:
                    print(f"  ... {event_count:,} events scanned, {hit_count} hits so far")

                etype = elem.get('type','')
                if etype == 'entered link':
                    lid = elem.get('link','')
                    if lid in all_bike_link_ids:
                        vehicle = elem.get('vehicle', elem.get('person',''))
                        link_vehicles[lid].add(vehicle)
                        hit_count += 1
                elem.clear()

    print(f"\n  Done. {event_count:,} events scanned, {hit_count} 'entered link' hits on bike links.\n")

    # ── Build result table ────────────────────────────────────────────────────
    bike_rows = []
    for grp, ids in bike_links_found.items():
        for lid in ids:
            vehicles = link_vehicles.get(lid, set())
            # Split: numeric = person agents, non-numeric = transit/freight vehicles
            persons   = {v for v in vehicles if person_id_re.match(v)}
            non_persons = vehicles - persons
            bike_rows.append({
                'link_id':            lid,
                'bridge_group':       grp,
                'total_vehicle_uses': len(vehicles),   # total traversals (not unique — one person = 1 use per entry)
                'unique_persons':     len(persons),
                'non_person_vehicles':len(non_persons),
                'person_ids_sample':  ", ".join(sorted(persons)[:5]) + ("..." if len(persons)>5 else ""),
                'used_by_agents':     len(persons) > 0,
            })

    df_bike = pd.DataFrame(bike_rows)

    print("── NEW BIKE LINK USAGE ──")
    print(f"{'Bridge Group':<28} {'Link ID':<42} {'Unique Persons':>15} {'Total Entries':>14} {'Used?':>6}")
    print("-"*110)
    for _, r in df_bike.iterrows():
        used = "✅ YES" if r['used_by_agents'] else "❌ NO"
        print(f"{r['bridge_group']:<28} {str(r['link_id'])[:40]:<42} {r['unique_persons']:>15,} {r['total_vehicle_uses']:>14,} {used:>6}")

    total_unique = df_bike.groupby('bridge_group')['unique_persons'].sum()
    print(f"\n── Unique persons using new bike links by bridge ──")
    for grp, n in total_unique.items():
        print(f"  {grp}: {n:,} unique persons")

    df_bike.to_csv(f"{OUT_DIR}/step1_bike_link_usage.csv", index=False)
    print(f"\nSaved: {OUT_DIR}/step1_bike_link_usage.csv")

print(f"\nSaved: {OUT_DIR}/step1_network_validation.csv")
print("\n✅ Step 1 complete. Paste full output above before proceeding to Step 2.")
