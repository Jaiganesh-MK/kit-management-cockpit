\# Service Level Agreements



\## Purpose



This file defines SLA logic for scheduling, urgency, batching, and commercial risk. Agent 2 must use this file when generating order urgency and service-window recommendations.



\## Priority Levels



CRITICAL priority requires response within 24 hours and action plan within 1 business day. Use CRITICAL for overdue safety directives, active contamination risk, machine-stopped corrective work, or warranty-critical failures.



HIGH priority requires response within 3 business days and planned service within 10 business days. Use HIGH for safety deadlines within 90 days, repeated production-impacting faults, or high-confidence mandatory corrective kits.



MEDIUM priority requires response within 5 business days and planned service within 30 calendar days. Use MEDIUM for corrective kits with workaround available or upgrade proposals with customer signal but no immediate risk.



LOW priority requires response within 10 business days and may be batched into the next planned maintenance visit. Use LOW for available upgrades, optional kits, and non-urgent verification.



\## SLA Breach Rules



An SLA breach occurs when the required response or execution window cannot be met after the recommendation date. The agent must compare kit deadline, estimated downtime, required skills, and site scheduling constraint.



A 22-hour downtime job with a 5-day SLA must be scheduled immediately because planning lead time consumes the available SLA window.



If a kit requires customer shutdown approval, the SLA risk must include customer scheduling dependency.



\## Urgency Mapping



Use `immediate` order urgency for CRITICAL priority, overdue deadline, machine-stopped condition, safety directive breach, or prerequisite needed before an urgent mandatory kit.



Use `routine` order urgency for MEDIUM and LOW decisions unless batching would violate a deadline.



Use `expedited\_review` when confidence is below 0.70 but business impact is high. This is not an order urgency; it is a human governance urgency.



\## Batching Rules



Batch kits into one service window when combined installation reduces downtime and no kit has a CRITICAL deadline. Batching is preferred for HMI upgrade plus emergency stop verification, VCK plus dependent MSTK verification, and MU-based overhaul visits.



Do not batch if a safety directive is overdue. Do not delay a mandatory corrective kit to wait for an optional upgrade unless the corrective kit has a valid workaround and approval is documented.



If two kits share prerequisite checks, tools, or technician skills, recommend batching when total downtime is less than separate visits.



\## Downtime Logic



Downtime under 4 hours can often fit into minor planned maintenance windows. Downtime from 4 to 8 hours requires site scheduling and production approval.



Downtime above 8 hours requires planner escalation because production, customer delivery, and resource availability must be coordinated.



Downtime above 16 hours should be flagged for batching review because multiple open kits may be combined with minimal incremental downtime.



\## Commercial Consequence



Failure to meet CRITICAL or HIGH SLA may trigger escalation, customer dissatisfaction, repeat dispatch, or warranty exposure. The agent should not state financial penalties unless contract data is present.



If service notes mention “line stopped,” “production loss,” “customer escalation,” or “delivery commitment,” increase SLA urgency by one level.



If service notes mention “next shutdown available” or “maintenance window booked,” prefer scheduled batching unless safety deadline is overdue.



\## Approval Rules



Service planner approves scheduling recommendations. IB data owner approves record updates. SAP admin approves mass updates or serial mapping corrections.



Any recommendation that changes order urgency from routine to immediate must include evidence. Any recommendation to delay a mandatory kit for batching requires human approval.



\## Agent Output Guidance



Agent 2 must include SLA rationale in scheduling output. The rationale must reference priority, deadline, downtime, skills, and batching decision.



If deadline exists but downtime estimate is unknown, route to VERIFY\_FIRST or planner review instead of assuming routine scheduling.

