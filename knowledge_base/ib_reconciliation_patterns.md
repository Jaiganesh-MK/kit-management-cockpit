\# IB Reconciliation Patterns



\## Purpose



This file defines repeatable installed-base data failure patterns and the correct reconciliation response. The agent must use these patterns when generating SQL update proposals and governance items.



\## Pattern IB-STALE-001 — Stale Verification Date



This pattern occurs when `last\_verified\_date` is older than 24 months and recent service orders reference configuration-sensitive work. It is high risk when kit applicability depends on jaw type, volume, cap size, HMI version, or VCK state.



Detection rule: equipment master date is stale, and at least one service order in the last 24 months references configuration, format, upgrade, or kit installation.



Correct action is VERIFY\_FIRST unless service evidence is strong enough to infer a change. The IB data owner must approve verification-date updates.



SQL template:

`UPDATE equipment\_master SET last\_verified\_date = '{approval\_date}' WHERE serial\_number = '{serial\_number}';`



Risk if unresolved is Medium. It typically causes wrong recommendations after two service cycles.



\## Pattern IB-MISSING-INSTALL-002 — Completed Kit Without IB Update



This pattern occurs when installation history or service order notes show a kit completed, but `ib\_updated = FALSE` or no installed-base record exists.



Detection rule: service order status is CLOSED or COMPLETED, technician notes mention installed kit or completed retrofit, and installation history does not show completed IB update.



Correct action is create missing installation record and update kit status after human approval.



SQL template:

`INSERT INTO installation\_history (serial\_number, mstk\_number, installation\_date, installation\_status, ib\_updated, notes) VALUES ('{serial\_number}', '{mstk\_number}', '{installation\_date}', 'COMPLETED', TRUE, 'Backfilled from approved service evidence');`



Approval owner is IB data owner. SAP admin approval is required if the update touches multiple tables.



Risk if unresolved is High. It can cause double ordering immediately.



\## Pattern IB-CONFIG-DRIFT-003 — Physical Configuration Differs From SAP



This pattern occurs when service notes or parts referenced imply a different jaw type, volume, cap size, or HMI version than equipment master.



Detection rule: at least two independent evidence sources contradict a configuration field, or one high-confidence work order references a completed conversion.



Correct action is update the configuration field only after service planner and IB data owner approval.



SQL template:

`UPDATE equipment\_master SET {config\_field} = '{new\_value}', last\_verified\_date = '{approval\_date}' WHERE serial\_number = '{serial\_number}';`



Risk if unresolved is Critical for VCK and safety-directive decisions. It can cause wrong kit recommendation on the next query.



\## Pattern IB-PREREQ-UNCERTAIN-004 — Prerequisite Evidence Missing



This pattern occurs when a kit depends on another kit but the prerequisite status is missing, partial, or contradictory.



Detection rule: dependency table lists prerequisite, and installation history does not confirm the prerequisite, while service orders mention related work.



Correct action is route to VERIFY\_FIRST. Do not install dependent kit until prerequisite is confirmed or ordered.



SQL template after confirmation:

`UPDATE installation\_history SET installation\_status = 'COMPLETED', ib\_updated = TRUE WHERE serial\_number = '{serial\_number}' AND mstk\_number = '{prereq\_mstk}';`



Approval owner is service planner. SAP admin approval is not required unless inserting a new row.



Risk if unresolved is High. It can create failed service visits and invalid installation sequence.



\## Pattern IB-DUPLICATE-MU-005 — MU and Component Kit Double Count



This pattern occurs when an MU is installed, but individual component MSTKs are also recommended because component-level IB records are missing.



Detection rule: kit master shows `included\_in\_mu = TRUE`, and installation history shows an MU installed within the relevant service window.



Correct action is suppress duplicate individual kit orders and propose component status reconciliation.



SQL template:

`INSERT INTO ib\_change\_log (serial\_number, change\_type, evidence, approval\_status) VALUES ('{serial\_number}', 'MU\_COMPONENT\_RECONCILIATION', '{mu\_id}', 'PENDING\_APPROVAL');`



Approval owner is IB data owner. Risk if unresolved is Medium to High depending on kit cost and downtime.



\## Pattern IB-ORPHAN-006 — Service Record References Unknown Serial



This pattern occurs when a service order references a serial number not present in equipment master.



Detection rule: service order serial does not match any equipment master serial, but customer, site, or material reference matches an existing asset.



Correct action is not automatic update. Route to SAP admin for serial mapping.



Risk if unresolved is Medium. It can hide evidence needed for future kit decisions.

