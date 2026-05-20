# Kit Dependencies and Prerequisite Rules

## Overview

Kit dependencies define which kits must be installed before others (prerequisites), which kits cannot coexist (conflicts), and which kits should be installed together to minimise downtime (groupings).

## Prerequisite Rules

### Base Rail Kit → Safety Guard Retrofit

Kit 3495770-01003 (Base Rail Kit) **must** be installed before 3495770-02002 (Safety Guard Retrofit).

**Why:** The safety guard bracket mounts directly to the base rail. Installing the guard without the rail results in incorrect alignment and will cause the sensor to fail verification.

**Resolution if base rail not in IB:** Order base rail kit first. Schedule safety guard installation at the following service window after base rail is confirmed installed and IB updated.

### Aseptic Chamber Seal → HMI Upgrade

Kit 3495770-03003 (Aseptic Chamber Seal Replacement) should be completed before 3496300-01002 (HMI Upgrade) if the seal replacement is pending.

**Why:** HMI upgrade requires partial cabinet disassembly that provides access to the aseptic chamber area. Completing both in the same window saves 4 hours of downtime compared to two separate visits.

**Note:** This is a scheduling preference, not a hard prerequisite. HMI can be installed independently.

## Conflict Rules

### Legacy Display Panel vs HMI Upgrade

The legacy display panel kit (any MSTK prefixed 3496100-*) conflicts with the HMI Upgrade Kit 3496300-01002. Both cannot be installed simultaneously. If legacy display panel kit shows as installed, HMI upgrade is incompatible until the legacy panel is removed.

### Jaw System Kits

Standard jaw kits (MSTK prefix 3495770-02*) conflict with Enhanced jaw kits (MSTK prefix 3495770-04*). Only one jaw system variant can be active. Check config_jaw_type in equipment_master before recommending any jaw kit.

## Grouping Recommendations

### Safety Bundle — Curing Line 150ml

The following three kits should be installed together in a single planned shutdown to minimise total downtime:

1. 3495770-01003 — Base Rail Kit (6h)
2. 3495770-02002 — Safety Guard Retrofit (4h)
3. 3495770-03003 — Aseptic Chamber Seal Replacement (8h)

Installed sequentially in a single 18-hour planned stop versus three separate visits totalling 28+ hours including travel and setup. Recommended when all three are pending on the same machine.

### Maintenance Unit MU-CUR-01

Maintenance Unit MU-CUR-01 includes the following kits as components:
- Drive belt tensioner 3495880-01002
- Bearing set 3495880-02001
- Seal kit 3495880-03001

If MU-CUR-01 is installed or planned, do not order any of the above kits individually — they are already included. Ordering them separately will result in duplicate parts and wasted cost.

Always check the included_in_mu flag on a kit before ordering.

## Prerequisite Verification Checklist

Before scheduling any kit installation, verify:

1. All prerequisite kits show status COMPLETED in installation_history
2. No conflicting kits are currently installed (check IB)
3. If IB record is stale (>24 months), treat as unverified — request on-site check
4. For safety kits, confirm prerequisite install date is within 12 months (old prerequisites may need re-inspection)
