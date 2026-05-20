\# Equipment Configurations



\## Purpose



The agent must treat configuration as the basis for kit applicability. A kit is not applicable merely because the material number matches. The current physical configuration must also match or be inferred with sufficient confidence.



\## Filling Machine Configuration Fields



TBA/19, TBA/21, and TBA/22 equipment use `config\_jaw\_type`, `config\_volume\_ml`, and `config\_cap\_size` as primary matching fields. Valid jaw values are LEGACY\_JAW, STANDARD\_JAW, UPGRADED\_JAW, and HIGH\_SPEED\_JAW.



Valid volume values are 150, 200, 250, 500, and 1000 ml. A configuration showing 150ml with HIGH\_SPEED\_JAW is physically implausible unless a special high-speed small-format campaign is documented in service orders.



Valid cap sizes are NONE, SMALL\_CAP, MEDIUM\_CAP, LARGE\_CAP, and SPORT\_CAP. Cap size NONE is valid only for non-cap package configurations.



\## A3/Flex and A3/Speed Configuration Fields



A3/Flex supports flexible volume and cap combinations. A3/Speed supports HIGH\_SPEED\_JAW and UPGRADED\_JAW but should not show LEGACY\_JAW after 2022 unless the machine has not undergone modernization.



If an A3/Speed record shows last verification before 2022 and LEGACY\_JAW, the agent must flag stale configuration. If service orders mention “high-speed jaw calibration,” infer UPGRADED\_JAW or HIGH\_SPEED\_JAW depending on technician language.



\## Cap Applicator Configuration



Cap Applicator equipment uses cap size, applicator head type, belt drive type, and HMI version as key configuration fields. Valid cap size values are SMALL\_CAP, MEDIUM\_CAP, LARGE\_CAP, and SPORT\_CAP.



A Cap Applicator with SPORT\_CAP and legacy belt tensioner requires SD-2024-118 evaluation. If service notes mention frequent belt adjustment or cap misalignment at high speed, the agent should treat belt drive configuration as uncertain.



\## Processing Equipment Configuration



C3 Homogenizer, A6 Pasteurizer, and D8 Separator use capacity, pressure, plate configuration, temperature range, and cleaning mode as primary fields. These machines do not use jaw type or cap size.



If processing equipment has packaging-specific configuration values, the agent must flag the equipment master as wrong material-family mapping. Do not recommend packaging MSTKs to processing equipment unless the kit master explicitly lists the processing material number.



\## Volume Conversion Effects



A VCK changes the configuration state and invalidates prior compatibility assumptions. A VCK from 150ml to 200ml changes `config\_volume\_ml` to 200 and requires re-evaluation of dependent MSTKs.



The 150ml to 200ml VCK must trigger “9,101 MSTK re-eval required.” The agent must not assume a previously valid mandatory kit remains valid after conversion.



A VCK from 200ml to 250ml requires cap applicator re-check if the package uses MEDIUM\_CAP or larger. A VCK from 250ml to 1000ml requires conveyor, jaw timing, and filling parameter verification.



\## End-of-Life Configurations



LEGACY\_JAW is unsupported for new mandatory corrective kits after 2026-12-31 unless a transition kit is listed. If a current record shows LEGACY\_JAW and last verification is older than 24 months, route to VERIFY\_FIRST.



Legacy HMI version HMI\_V1 is end-of-life for HMI upgrade decisions. If service notes mention screen lag, missing data export, or obsolete operator panel, the agent may detect a valid upgrade signal.



\## Field Identification Rules



Jaw type can be identified from jaw housing label, service calibration screen, or part number on timing assembly. If technician notes mention “new jaw block,” “HS jaw,” or “upgraded linkage,” infer UPGRADED\_JAW with medium confidence.



Volume can be identified from active recipe, package mold, fill volume validation sheet, or product order history. If SAP says 150ml but three recent service orders mention 200ml production, infer configuration drift.



Cap size can be identified from cap applicator head part number, packaging recipe, cap inspection notes, or service order parts. If multiple cap sizes appear in recent notes, route to VERIFY\_FIRST before recommending cap-specific kits.

