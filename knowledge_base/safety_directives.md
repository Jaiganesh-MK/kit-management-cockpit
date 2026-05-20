\# Safety Directives



\## Purpose



This file defines safety, regulatory, and compliance directives that override normal kit prioritization. The agent must treat directive-backed kits as mandatory unless the installed base proves the directive has already been embodied and verified.



\## SD-2024-447 — Safety Guard Retrofit for Moving Jaw Area



Directive SD-2024-447 applies to TBA/19, TBA/21, and TBA/22 filling machines with `config\_jaw\_type = LEGACY\_JAW` or `config\_jaw\_type = STANDARD\_JAW`. The directive applies to equipment installed before 2024-01-01 unless an installation record exists for the approved guard retrofit MSTK.



The compliance deadline is 2026-12-31 for active production lines. Machines under scheduled shutdown or relocation may use a grace period until the first restart after 2026-12-31, but the machine must not resume production without the guard retrofit verified.



Non-compliance creates a safety exposure around operator access to the jaw area. The service planner must flag CE conformity risk, customer liability exposure, and warranty restriction for incidents linked to unguarded moving parts.



SD-2024-447 supersedes local safety bulletin LS-2022-091. If both directives appear in service notes, SD-2024-447 must be treated as the controlling directive.



\## SD-2024-118 — Drive Belt Tensioner Guard Mandate



Directive SD-2024-118 applies to Cap Applicator and Accumulator equipment with belt drive assemblies installed before 2023-07-01. The directive applies when `status = ACTIVE` and the equipment is part of a running packaging line.



The compliance deadline is 2025-09-30 for high-speed lines and 2026-03-31 for standard-speed lines. High-speed means line speed above 7,000 packages per hour or service notes indicating frequent belt access.



If not complied with, technicians must classify the asset as requiring a safety corrective visit. Warranty is not void for the machine as a whole, but warranty claims involving belt damage, guarding, or access injury may be rejected.



This directive does not supersede SD-2024-447 because it concerns a different hazard zone.



\## SD-2023-205 — Aseptic Door Interlock Verification



Directive SD-2023-205 applies to aseptic filling equipment including A3/Flex, A3/Speed, TBA/19, and TBA/22 where service notes mention aseptic chamber door access, repeated cleaning intervention, or interlock bypass.



The compliance deadline is the next planned preventive maintenance visit or within 90 calendar days after detection, whichever is earlier.



If not complied with, the customer carries contamination and sterility risk. The agent must flag this as a quality and safety compliance issue, not only a maintenance issue.



SD-2023-205 does not automatically require kit installation. It requires verification first. If verification fails, the applicable interlock corrective MSTK must be ordered.



\## SD-2025-031 — Emergency Stop Circuit Standardization



Directive SD-2025-031 applies to packaging line assets with legacy HMI panels or field-wired emergency stop loops. The directive is especially relevant where HMI upgrade kit `3496300-01002` is proposed or installed.



The compliance deadline is 2027-06-30 for all active production assets. If the asset has an HMI upgrade scheduled before that date, the emergency stop verification must be batched into the same visit.



If not complied with, the asset may fail safety validation after HMI modernization. The agent must not recommend HMI upgrade without checking whether SD-2025-031 verification is required.



\## SD-2024-309 — Volume Conversion Safety Revalidation



Directive SD-2024-309 applies when a Volume Conversion Kit changes production format from 150ml to 200ml, 200ml to 250ml, or 250ml to 1000ml. The directive applies to VCKs that change jaw timing, package flow, cap applicator setup, or filling parameters.



The compliance deadline is immediate at commissioning. Production cannot continue after VCK installation until revalidation is completed.



This directive requires re-evaluation of dependent MSTKs after volume conversion. For the 150ml to 200ml conversion, the agent must flag “9,101 MSTK re-eval required” when the VCK is proposed or completed.



\## Hard Rules for Agent Decisions



A directive-backed mandatory kit cannot be downgraded to AVAILABLE\_NOT\_RECOMMENDED. If installation evidence is missing, the agent must choose INSTALL, ORDER, or VERIFY\_FIRST depending on confidence and prerequisites.



If a directive deadline has passed and no completed installation record exists, priority must be CRITICAL. If the deadline is within 90 days, priority must be HIGH.



If service notes indicate production continues despite an overdue safety directive, the decision must be routed to human approval with evidence attached.

