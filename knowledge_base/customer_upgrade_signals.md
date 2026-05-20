\# Customer Upgrade Signals



\## Purpose



Upgrade kit recommendations require evidence of customer intent or business value. The agent must distinguish customer interest in improvement from complaints that require corrective repair.



\## Valid Upgrade Signals



The phrase “customer asked about upgrade” is a direct upgrade signal. The agent may recommend PROPOSE\_TO\_CUSTOMER for relevant UK\_Improvement kits when this phrase appears in technician notes.



The phrase “customer wants better reporting” is a valid signal for HMI Upgrade `3496300-01002`. The value proposition is improved operator interface, better visibility, and easier service diagnostics.



The phrase “customer requested higher throughput” is a valid signal for speed, automation, and format improvement upgrades. The agent must still verify that current configuration supports the upgrade.



The phrase “operator asked whether newer HMI is available” is a valid signal for HMI upgrade proposal. The agent should not classify it as mandatory.



The phrase “customer planning 200ml launch” is a valid signal for Volume Conversion Kit proposal if the current configuration is not already 200ml.



The phrase “customer wants to reduce manual adjustments” is a valid signal for improvement upgrades where the kit reduces setup time, changeover effort, or operator intervention.



\## Weak or Ambiguous Signals



The phrase “customer complained about downtime” is not automatically an upgrade signal. It may indicate corrective maintenance or reliability issue.



The phrase “operator unhappy with performance” is ambiguous. The agent should route to VERIFY\_FIRST unless the note identifies desired improvement such as speed, quality, reporting, or new format.



The phrase “machine is old” is not an upgrade signal by itself. It supports lifecycle risk assessment but not a customer proposal.



The phrase “intermittent HMI fault” is a replacement or corrective signal unless notes also mention interest in new interface or digital reporting.



The phrase “production target changed” requires clarification. If it refers to package volume or format, it may support VCK proposal. If it refers to quantity only, it may support performance improvement review.



\## Non-Signals



A breakdown note is not an upgrade signal. If the machine failed, the agent should evaluate mandatory corrective kits first.



A safety directive is not an upgrade signal. Safety directives create mandatory compliance actions.



A technician recommendation alone is not a customer signal unless the customer discussed value, budget, upgrade timing, or production requirement.



A spare part shortage is not an upgrade signal. It may justify replacement or alternative sourcing, not improvement.



\## Upgrade vs Replacement Logic



UK\_Improvement is appropriate when the customer wants better capability, higher efficiency, new functionality, improved visibility, or future-state readiness.



UK\_Replacement is appropriate when the current component is obsolete, failed, unsupported, or needs lifecycle replacement. It does not require customer interest in new functionality.



If a service note says “part obsolete, replacement recommended,” choose UK\_Replacement. If a service note says “customer wants digital reporting,” choose UK\_Improvement.



\## Segment Patterns



High-volume dairy and beverage customers often request throughput, changeover, and volume conversion upgrades. Use value proposition around reduced downtime and format flexibility.



Customers with multiple lines often request HMI standardization and reporting upgrades. Use value proposition around operator training consistency and data visibility.



Customers launching new SKUs often request VCK or optional functionality kits. Use value proposition around new format enablement and controlled conversion.



\## Human Review Rules



If customer signal confidence is below 0.70, recommend AVAILABLE\_NOT\_RECOMMENDED or VERIFY\_FIRST rather than PROPOSE\_TO\_CUSTOMER.



If upgrade recommendation requires downtime above 6 hours, route to service planner review even when customer signal is strong.



If mandatory corrective action is also present, corrective kit must be prioritized before optional upgrade proposal unless batching is explicitly beneficial.

