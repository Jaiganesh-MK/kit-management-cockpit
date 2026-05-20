# Upgrade Kits — Curing Line Series

## Overview

Upgrade kits (UK_*) are optional improvements and replacements. They require an explicit customer signal before being proposed. A signal is any evidence that the customer is aware of and interested in the upgrade — technician notes, customer emails, support tickets, or verbal requests documented in service orders.

## HMI Upgrade Kit — 3496300-01002

### Kit Type
UK_Improvement — optional, customer-initiated

### Applicable Equipment
- Material: 3000-MAT-CUR-150, 3000-MAT-CUR-200
- All configurations
- Machines with legacy HMI panel (installed before 2020)

### Customer Signal Required
Do not propose unless one of the following is documented in a service order:
- Technician note contains "HMI", "display", "touchscreen", "interface upgrade"
- Customer explicitly asked about upgrade during service visit
- Open support ticket referencing HMI performance

### Value Proposition
New HMI provides 7-inch touchscreen, remote monitoring capability, predictive maintenance alerts, and OPC-UA connectivity for MES integration. Legacy HMI is no longer supported after 2026.

### Prerequisites
- Aseptic chamber seal replacement (3495770-03003) must be completed first if it is pending
- Electrical cabinet must have firmware version 4.2 or above

### Installation Procedure Summary
1. Backup current HMI configuration via USB export
2. Power down and isolate electrical cabinet
3. Remove legacy display panel (4 M5 screws)
4. Fit new HMI mounting bracket
5. Install new display, connect ribbon cable C1 and power harness C2
6. Power on, load configuration from USB backup
7. Verify all I/O signals in diagnostics menu

### Skills Required
- Tetra Pak electrical technician
- HMI certification HMI-02

### Estimated Downtime
8 hours. Can be scheduled during planned maintenance window.

### Pricing
Refer to current price list. Typical range €2,800–€3,400 depending on machine variant.


## Volume Conversion Kit (VCK) — 150ml to 200ml

### Kit Type
VCK — volume conversion, customer-initiated

### Overview
Changes the machine's packaging volume from 150ml to 200ml. This is a significant change that requires re-evaluation of 9,101 MSTKs because applicability criteria change after conversion.

### Customer Signal Required
Customer must have formally requested volume change. Verify against sales order or account manager confirmation before proposing.

### Post-Installation Actions
After VCK installation is confirmed in the IB:
- Update config_volume field from 150 to 200 in equipment_master
- Trigger re-evaluation of all applicable kits for this serial number
- Notify service planning team to review active kit recommendations

### Prerequisites
None — can be installed independently.

### Estimated Downtime
12 hours. Production line must be fully stopped.

### Important Note
If service order notes reference "VCK" or "volume conversion" or "format change" and the IB still shows the old volume, this is a configuration drift situation. The IB must be updated to reflect the actual installed configuration before kit recommendations can be trusted.
