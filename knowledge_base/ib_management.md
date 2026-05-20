# Installed Base Management — Data Quality and Reconciliation

## Overview

The Installed Base (IB) is the system of record for what is physically installed on each customer asset. When the IB is stale or incorrect, kit recommendations cannot be trusted. This document describes common IB problems and how to identify and resolve them.

## Common IB Data Quality Issues

### Stale Verification

An IB record is considered stale if the last_verified_date is more than 24 months ago. Stale records frequently contain configuration drift — the physical machine has been modified since the last verification and the IB was not updated.

**Indicators in service orders:**
- Technician notes referencing parts or configurations not in the IB
- Service orders closed as "completed" without an IB update flag
- Multiple service orders on a machine with no corresponding IB updates

**Action:** Flag for on-site verification at next service visit. Do not fully trust configuration fields in a stale IB record.

### Configuration Drift

Configuration drift occurs when the recorded IB configuration no longer matches the physical machine. Most common causes:

1. **VCK installed but not recorded** — volume conversion done in field, IB still shows old volume
2. **Upgrade kit installed, IB not updated** — technician installs kit, marks service order complete, but does not update IB
3. **Customer self-modification** — customer modifies machine without notifying Tetra Pak

**Detection method:** Cross-reference service order parts lists with IB installation records. If a part appears in service order parts but has no corresponding IB installation record, drift is likely.

### Missing Installation Records

An installation record is missing when there is credible evidence a kit was installed but no formal record exists. Evidence includes:
- Service order parts list contains the kit MSTK number
- Technician notes reference the kit by name or MSTK
- Configuration data consistent with kit being installed

**Risk of missing records:** If a kit is in the IB it will not be recommended for re-installation. If the record is missing even though the kit was installed, the system will incorrectly recommend installing it again — resulting in wasted cost and unnecessary downtime.

## IB Update SQL Patterns

### Insert a missing installation record
```sql
INSERT INTO installation_history 
  (serial_number, mstk_number, installation_date, installation_status, ib_updated, notes)
VALUES 
  ('<serial>', '<mstk>', '<date>', 'COMPLETED', 'YES', 
   'IB reconciliation — evidence from service order <SO_ID>');
```

### Update a stale configuration field
```sql
UPDATE equipment_master
SET config_volume_ml = '<new_value>',
    last_verified_date = '<today>',
    updated_by = 'IB_RECONCILIATION'
WHERE serial_number = '<serial>';
```

### Update verification date
```sql
UPDATE equipment_master
SET last_verified_date = '<today>',
    verification_status = 'CURRENT'
WHERE serial_number = '<serial>';
```

## IB Reconciliation Priority Levels

| Situation | Priority | Action |
|-----------|----------|--------|
| Safety kit missing from IB, evidence it was installed | HIGH | Insert record immediately |
| Volume conversion not reflected in IB | HIGH | Update config and re-evaluate kits |
| Cosmetic upgrade missing from IB | MEDIUM | Insert record at next service |
| Verification date stale, no other issues | LOW | Update date at next visit |
