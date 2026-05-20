\# Kit Installation Procedures



\## General Rule



The agent must generate installation plans that respect prerequisites, safety isolation, technician certification, downtime windows, and post-install verification. A kit recommendation is incomplete unless it includes installation sequence, required skills, downtime, and sign-off criteria.



\## Mandatory Safety Kit Procedure — Guard Retrofit



Before starting a safety guard retrofit, verify equipment serial number, machine family, production status, and lockout-tagout readiness. Confirm that the current installed-base record does not already show the same safety MSTK as completed.



Step 1: Stop production and isolate electrical and pneumatic sources. Estimated time is 0.5 hours. Required skill is SC-01 safety isolation.



Step 2: Remove existing guard or access panel. Use tool set TP-810 mechanical hand tools and torque wrench TP-880. Estimated time is 0.7 hours.



Step 3: Install retrofit guard assembly. Torque M8 bolts to 45 Nm using calibrated torque wrench TP-880. Estimated time is 1.2 hours.



Step 4: Verify interlock or access switch alignment if the kit includes a sensor. Required skill is SC-03 machine safety validation. Estimated time is 0.6 hours.



Step 5: Run dry-cycle validation for five cycles at low speed and five cycles at normal speed. No abnormal vibration, access alarm, or guard interference may occur.



Total planned downtime is 3.0 to 4.0 hours. Production cannot continue during installation.



\## Mandatory Corrective Kit Procedure — Jaw Timing Correction



Before starting, verify jaw type, package volume, latest jaw timing fault, and whether a VCK was recently installed. Do not install jaw timing corrective kits if the machine has unresolved VCK revalidation.



Step 1: Capture current jaw timing parameter screen and HMI alarm list. Required skill is HMI-02. Estimated time is 0.3 hours.



Step 2: Inspect jaw linkage, cam follower, and timing sensor. Required tools are TP-820 inspection gauge and TP-880 torque wrench. Estimated time is 0.8 hours.



Step 3: Replace timing kit components. Required skill is MECH-03 and HMI-02. Estimated time is 1.5 hours.



Step 4: Upload corrected parameter set and run validation at low-speed and nominal-speed modes. Estimated time is 0.8 hours.



Common failure point is installation against stale volume configuration. If service notes mention a recent format conversion, route to VERIFY\_FIRST.



\## Upgrade Kit Procedure — HMI Upgrade 3496300-01002



Before recommending installation, confirm a valid upgrade signal. Valid signals include operator complaints about obsolete interface, service note mentioning upgrade discussion, repeated HMI faults, or customer request for digital reporting.



Step 1: Back up existing HMI recipe, alarms, operator screens, and service parameters. Required skill is HMI-02. Estimated time is 0.8 hours.



Step 2: Verify emergency stop circuit compatibility under SD-2025-031. Required skill is SC-03. Estimated time is 0.5 hours.



Step 3: Install HMI hardware and connect communication harness. Required tools are TP-710 electrical service kit and TP-990 ESD kit. Estimated time is 1.2 hours.



Step 4: Load approved software image and restore validated recipe set. Required skill is HMI-03. Estimated time is 1.0 hours.



Step 5: Run operator acceptance check and alarm validation. Estimated time is 0.5 hours.



Total downtime is 4.0 to 5.0 hours. Production must stop.



\## Volume Conversion Kit Procedure — 150ml to 200ml



Before installation, confirm customer intent and production target. Confirm whether current physical setup already matches 200ml. Do not execute VCK based only on old SAP configuration.



Step 1: Photograph current forming, filling, jaw, cap, and conveyor settings. Estimated time is 0.5 hours.



Step 2: Install conversion hardware. Required skills are MECH-03 and ASEPTIC-01 for aseptic fillers. Estimated time is 3.0 hours.



Step 3: Load validated 200ml configuration and update HMI parameters. Required skill is HMI-02. Estimated time is 1.0 hour.



Step 4: Run format validation, package weight check, seal integrity check, and cap alignment check. Estimated time is 2.0 hours.



Step 5: Trigger MSTK re-evaluation for all dependent kits. For 150ml to 200ml conversion, flag “9,101 MSTK re-eval required.”



Total downtime is 6.0 to 8.0 hours. Production cannot continue.



\## Maintenance Unit Procedure



Use a Maintenance Unit when multiple included MSTKs require replacement within the same service window. Do not order individual kits separately unless only one included component has failed and the remaining MU components are recently verified.



Before installation, check whether any component MSTK in the MU is already installed. If partially installed, route to human review to avoid duplicate consumption.



Post-install verification requires update of both MU-level installation status and included MSTK component status.

