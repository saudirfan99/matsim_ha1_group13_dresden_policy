# matsim_ha1_group13_dresden_policy
# MATSim HA1 — Carolabrücke Policy Analysis
Group 13 · MATSim · TU Berlin VSP · Summer Semester 2026

## Scripts
- step1_network_validation.py — validates changeset application in POLICY network
- step1b_bike_diagnostic.py — checks bike teleportation, justifies vol_bike instrument
- step3_affected_agents.py — identifies 467 directly affected residential agents
- step4_affected_behaviour.py — mode, km, time comparison for affected agents
- step5a_demographic.py — modal shift by age, income, PT ticket, trip purpose
- step5b_geographic.py — spatial equity gradient by home distance from bridge
- step5c_bike_paradox.py — bike mode transition matrix and infrastructure usage
- step7_corridor_analysis.py — cross-Elbe volume redistribution across all bridges
- step8_walk_diagnostic.py — walk distance realism check

## Data
All analysis uses the Open Dresden 1% MATSim scenario.
Base case: 500 iterations. Policy case: 100 iterations.
CRS: EPSG:25832.
