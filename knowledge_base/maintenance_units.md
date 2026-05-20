\# Maintenance Units



\## Purpose



Maintenance Units bundle multiple MSTKs into one service package. The agent must prevent double-ordering and must decide when the MU is preferable to individual component kits.



\## MU-JAW-700 — Jaw Service Maintenance Unit



MU-JAW-700 covers jaw area overhaul for TBA/19, TBA/21, TBA/22, A3/Flex, and A3/Speed machines. It includes jaw timing corrective MSTK, jaw linkage wear MSTK, sensor alignment MSTK, and selected sealing-area consumables.



Use MU-JAW-700 when two or more included MSTKs are recommended within the same service window. Use the MU when service notes mention repeated jaw timing, seal quality, and linkage wear together.



Order individual kits instead of MU-JAW-700 when only one included component is faulty and the remaining jaw area components were verified within the last 180 days.



The lead time for MU-JAW-700 is longer than most individual MSTKs because it is picked as a service package. If SLA is critical and only one corrective component is needed, individual ordering may be faster.



In the installed base, MU-JAW-700 may appear either as one MU record or as multiple component MSTK records. If service orders mention MU installation but component records are absent, propose component status update after approval.



\## MU-CAP-320 — Cap Applicator Maintenance Unit



MU-CAP-320 covers cap applicator head, belt tensioner, cap alignment, and selected sensor components. It is relevant for Cap Applicator assets with SMALL\_CAP, MEDIUM\_CAP, LARGE\_CAP, or SPORT\_CAP configurations.



Use MU-CAP-320 when cap alignment failure, belt tensioner issues, and cap reject increase are all present. Use individual kits when the failure is isolated to cap head wear or a single safety directive.



If SD-2024-118 applies, do not assume MU-CAP-320 satisfies the safety directive unless the included belt tensioner guard MSTK is explicitly present.



The agent must check `included\_in\_mu=True` for all component MSTKs before creating an order requisition. If an individual MSTK is included in MU-CAP-320 and the MU is being ordered, flag “avoid double-order.”



\## MU-HMI-900 — Control Panel Modernization Unit



MU-HMI-900 covers HMI upgrade, operator panel harness, legacy communication converter, and emergency stop circuit verification package.



Use MU-HMI-900 when HMI upgrade is combined with safety circuit standardization or communication modernization. Use HMI Upgrade `3496300-01002` alone when only the operator panel upgrade is required.



If SD-2025-031 is open, MU-HMI-900 is preferred because it batches HMI modernization and emergency stop verification.



Do not order MU-HMI-900 for a simple HMI screen failure unless customer wants modernization or legacy panel replacement is mandatory.



\## MU-VCK-200 — 150ml to 200ml Conversion Support Unit



MU-VCK-200 supports 150ml to 200ml conversion and includes conversion hardware, parameter validation support items, selected cap/jaw adjustment kits, and inspection consumables.



Use MU-VCK-200 when VCK 150ml to 200ml is approved and multiple dependent MSTKs require re-evaluation. Do not use it for corrective maintenance without customer conversion intent.



The agent must flag “9,101 MSTK re-eval required” whenever MU-VCK-200 or the underlying VCK is proposed.



\## Cost and Ordering Logic



The agent must not compare exact internal cost unless authorized. The decision should compare service efficiency, downtime reduction, and duplication risk.



An MU is preferred when batching reduces downtime, multiple included kits are due, or installation dependencies are tightly coupled.



Individual kits are preferred when only one component is needed, when SLA cannot tolerate MU lead time, or when the MU contains unnecessary components.



\## Approval Rules



Any MU order that replaces more than three individual MSTKs requires service planner approval. Any MU order that affects configuration state requires IB data owner approval after installation.

