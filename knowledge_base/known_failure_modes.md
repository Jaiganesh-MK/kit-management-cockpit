\# Known Failure Modes



\## Purpose



This file maps field symptoms to likely root causes and corrective kits. The agent must use these patterns when technician notes contain symptoms that are not directly structured in SAP fields.



\## FM-JAW-011 — Intermittent Jaw Timing Error



This failure affects TBA/19, TBA/21, TBA/22, A3/Flex, and A3/Speed machines. The technician may report “intermittent jaw timing,” “jaw sync fault,” “jaw not closing evenly,” or “seal timing out of range.”



Observable symptoms include HMI jaw synchronization alarms, inconsistent package sealing, abnormal jaw noise, and repeated timing calibration. Fault codes may include JAW-TIM-07, JAW-SYNC-11, or operator notes mentioning “timing drift.”



The root cause is usually worn timing linkage, incorrect parameter set after VCK, or sensor misalignment. The corrective kit is the applicable Mandatory Corrective jaw timing MSTK for the machine family.



Temporary workaround is low-speed production with increased inspection frequency. This workaround is valid only until the next planned service window and cannot be used if seal integrity fails.



Distinguish this from package-weight variation by checking whether the note mentions seal timing or jaw closure. Weight variation without jaw alarms usually points to filling or dosing issues.



\## FM-CAP-021 — Cap Misalignment at High Speed



This failure affects Cap Applicator equipment and filling lines with SMALL\_CAP, MEDIUM\_CAP, or SPORT\_CAP configuration. Notes may say “cap skew,” “cap not seated,” “cap alignment issue,” or “cap reject increases at high speed.”



Root cause is usually applicator head wear, belt tensioner drift, or incompatible cap size after format conversion. If belt access is mentioned, evaluate SD-2024-118.



The resolving kit is the cap applicator alignment MSTK or belt tensioner safety kit when the belt drive assembly is implicated.



Temporary workaround is reduced line speed and increased reject monitoring. Do not recommend only an HMI upgrade for this failure unless notes mention operator interface problems.



\## FM-FILL-034 — Package Weight Variation



This failure affects TBA/19, TBA/22, A3/Flex, A3/Speed, and processing-to-filling integrated lines. Technician notes may say “underfill,” “overfill,” “weight fluctuation,” “fill volume unstable,” or “package weight variation.”



Root cause can be dosing valve wear, recipe mismatch after VCK, fill parameter drift, or upstream processing instability.



If the note mentions recent volume conversion, the agent must check VCK status before recommending a corrective kit. If the note mentions recipe mismatch, recommend verification before part order.



Temporary workaround is batch hold, weight sampling, and low-speed run. Corrective kit depends on machine family and configuration.



\## FM-HMI-041 — Obsolete HMI / Operator Interface Failure



This failure affects assets with HMI\_V1 or HMI\_V2 panels. Notes may say “screen freezes,” “operator cannot access recipe,” “panel obsolete,” “customer asked about new interface,” or “data export unavailable.”



Root cause is HMI hardware aging, unsupported firmware, or incompatibility with newer reporting requirements.



The resolving kit is HMI Upgrade `3496300-01002` when customer signal is present. If the note says only “operator reported fault,” classify as replacement or repair signal, not necessarily improvement signal.



Temporary workaround is HMI restart or backup panel use. Repeated HMI resets within 90 days increase upgrade confidence.



\## FM-VCK-052 — Format Conversion Incomplete



This failure affects lines that changed volume format or package family. Notes may say “conversion completed but validation pending,” “running 200ml on old setup,” “format mismatch,” or “MSTK mapping not updated.”



Root cause is partial VCK installation, missing configuration update, or failure to re-evaluate dependent MSTKs.



The resolving action is not a single corrective kit. The agent must recommend VCK verification, dependent MSTK re-evaluation, and installed-base update.



\## FM-ASEPTIC-063 — Aseptic Door Interlock Bypass



This failure affects aseptic filling equipment. Notes may say “interlock bypass,” “door switch bridged,” “chamber access fault,” or “cleaning door alarm disabled.”



Root cause is failed interlock sensor, misalignment, or temporary field bypass after cleaning issue.



The resolving action is SD-2023-205 verification. If verification fails, order the relevant interlock corrective MSTK.



This must be treated as safety and quality critical. Route to human approval if any evidence suggests production continued with bypass active.

