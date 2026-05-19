"""
STEP 1: Data Layer
==================
Load the synthetic dataset and build lookup functions.
These functions will become the "tools" your AI agent calls.

Run: python step1_data_layer.py
"""

import pandas as pd
import os

# ============================================================
# LOAD ALL TABLES
# ============================================================

# Update this path to where your CSV files are
DATA_DIR = "./dataset"  # Change this if your CSVs are elsewhere

print("Loading dataset...")
equipment = pd.read_csv(f"{DATA_DIR}/01_equipment_master.csv", dtype=str).fillna("")
kits = pd.read_csv(f"{DATA_DIR}/02_kit_master.csv", dtype=str).fillna("")
dependencies = pd.read_csv(f"{DATA_DIR}/03_kit_dependencies.csv", dtype=str).fillna("")
installations = pd.read_csv(f"{DATA_DIR}/04_installation_history.csv", dtype=str).fillna("")
service_orders = pd.read_csv(f"{DATA_DIR}/05_service_orders.csv", dtype=str).fillna("")

print(f"  Equipment:     {len(equipment)} records")
print(f"  Kits:          {len(kits)} records")
print(f"  Dependencies:  {len(dependencies)} records")
print(f"  Installations: {len(installations)} records")
print(f"  Service Orders:{len(service_orders)} records")


# ============================================================
# TOOL 1: Look up equipment by serial number
# ============================================================

def lookup_equipment(serial_number: str) -> dict:
    """Given a serial number, return equipment details."""
    match = equipment[equipment["serial_number"] == serial_number]
    if match.empty:
        return {"error": f"Equipment {serial_number} not found"}
    
    row = match.iloc[0]
    # Build a clean dict with only non-empty fields
    result = {}
    for col in row.index:
        if row[col] != "":
            result[col] = row[col]
    return result


# ============================================================
# TOOL 2: Find applicable kits for an equipment
# ============================================================

def find_applicable_kits(material_number: str, config: dict = None) -> list:
    """Given an equipment material number and optional config, find matching MSTKs."""
    # First filter: match on material number
    matches = kits[kits["applicable_material_number"] == material_number]
    
    if matches.empty:
        return []
    
    results = []
    for _, kit in matches.iterrows():
        kit_dict = {
            "mstk_number": kit["mstk_number"],
            "mcon_number": kit["mcon_number"],
            "mcon_name": kit["mcon_name"],
            "rk_type": kit["rk_type"],
            "category": kit["category"],
            "config_match_key": kit["config_match_key"],
            "config_match_value": kit["config_match_value"],
            "implementation_deadline": kit["implementation_deadline"],
            "estimated_downtime_hrs": kit["estimated_downtime_hrs"],
            "vck_affected": kit["vck_affected"],
            "included_in_mu": kit["included_in_mu"],
        }
        
        # Check config match
        if kit["config_match_key"] == "ANY":
            kit_dict["config_match_status"] = "MATCHES_ALL"
        elif config and kit["config_match_key"] in config:
            if config[kit["config_match_key"]] == kit["config_match_value"]:
                kit_dict["config_match_status"] = "EXACT_MATCH"
            else:
                kit_dict["config_match_status"] = "NO_MATCH"
                continue  # Skip this kit - doesn't match config
        else:
            kit_dict["config_match_status"] = "UNKNOWN_CANNOT_VERIFY"
        
        results.append(kit_dict)
    
    return results


# ============================================================
# TOOL 3: Check installation history for an equipment
# ============================================================

def check_installation_history(serial_number: str) -> list:
    """Check what kits have been installed on this equipment."""
    matches = installations[installations["equipment_serial"] == serial_number]
    
    if matches.empty:
        return []
    
    results = []
    for _, inst in matches.iterrows():
        results.append({
            "installation_id": inst["installation_id"],
            "mstk_number": inst["mstk_number"],
            "mcon_number": inst["mcon_number"],
            "installation_date": inst["installation_date"],
            "installation_status": inst["installation_status"],
            "ib_updated": inst["ib_updated"],
            "performed_by": inst["performed_by"],
            "notes": inst["notes"],
        })
    
    return results


# ============================================================
# TOOL 4: Check kit dependencies
# ============================================================

def check_kit_dependencies(mcon_number: str) -> dict:
    """Check prerequisites, interferences, and groupings for a kit."""
    prereqs = dependencies[
        (dependencies["mcon_number"] == mcon_number) & 
        (dependencies["dependency_type"] == "PREREQUISITE")
    ]
    interferes = dependencies[
        (dependencies["mcon_number"] == mcon_number) & 
        (dependencies["dependency_type"] == "INTERFERES_WITH")
    ]
    groups = dependencies[
        (dependencies["mcon_number"] == mcon_number) & 
        (dependencies["dependency_type"] == "GROUP_WITH")
    ]
    
    return {
        "mcon_number": mcon_number,
        "prerequisites": [
            {"depends_on": r["depends_on_mcon"], "notes": r["notes"]} 
            for _, r in prereqs.iterrows()
        ],
        "interferes_with": [
            {"conflicts_with": r["depends_on_mcon"], "notes": r["notes"]} 
            for _, r in interferes.iterrows()
        ],
        "group_with": [
            {"batch_with": r["depends_on_mcon"], "notes": r["notes"]} 
            for _, r in groups.iterrows()
        ],
    }


# ============================================================
# TOOL 5: Search service orders for indirect evidence
# ============================================================

def search_service_orders(serial_number: str) -> list:
    """Find service orders for an equipment - may contain indirect evidence of kit installs."""
    matches = service_orders[service_orders["equipment_serial"] == serial_number]
    
    if matches.empty:
        return []
    
    results = []
    for _, so in matches.iterrows():
        results.append({
            "service_order_id": so["service_order_id"],
            "order_date": so["order_date"],
            "order_type": so["order_type"],
            "status": so["status"],
            "technician_notes": so["technician_notes"],
            "parts_referenced": so["parts_referenced"],
        })
    
    return results


# ============================================================
# TEST: Run all tools on one equipment to verify they work
# ============================================================

if __name__ == "__main__":
    import json
    
    # Pick a test equipment
    TEST_SERIAL = "SN-10005"
    
    print(f"\n{'='*60}")
    print(f"TESTING ALL TOOLS FOR: {TEST_SERIAL}")
    print(f"{'='*60}")
    
    # Tool 1: Equipment lookup
    print(f"\n--- Tool 1: lookup_equipment('{TEST_SERIAL}') ---")
    eq = lookup_equipment(TEST_SERIAL)
    print(json.dumps(eq, indent=2))
    
    # Extract config for kit matching
    config = {}
    for key, val in eq.items():
        if key.startswith("config_") and val:
            config[key.replace("config_", "")] = val
    print(f"\nExtracted config: {config}")
    
    # Tool 2: Find applicable kits
    print(f"\n--- Tool 2: find_applicable_kits('{eq.get('material_number', '')}') ---")
    applicable = find_applicable_kits(eq.get("material_number", ""), config)
    print(f"Found {len(applicable)} applicable kits:")
    for kit in applicable:
        print(f"  {kit['mstk_number']} | {kit['mcon_name'][:40]} | {kit['rk_type']} | match: {kit['config_match_status']}")
    
    # Tool 3: Installation history
    print(f"\n--- Tool 3: check_installation_history('{TEST_SERIAL}') ---")
    history = check_installation_history(TEST_SERIAL)
    print(f"Found {len(history)} installation records:")
    for inst in history:
        print(f"  {inst['mstk_number']} | {inst['installation_date']} | {inst['installation_status']} | IB updated: {inst['ib_updated']}")
    
    # Tool 4: Dependencies for each applicable kit
    print(f"\n--- Tool 4: check_kit_dependencies (for each applicable kit) ---")
    seen_mcons = set()
    for kit in applicable:
        mcon = kit["mcon_number"]
        if mcon in seen_mcons:
            continue
        seen_mcons.add(mcon)
        deps = check_kit_dependencies(mcon)
        if deps["prerequisites"] or deps["interferes_with"] or deps["group_with"]:
            print(f"  {mcon} ({kit['mcon_name'][:30]}):")
            for p in deps["prerequisites"]:
                print(f"    REQUIRES: {p['depends_on']} - {p['notes']}")
            for i in deps["interferes_with"]:
                print(f"    CONFLICTS: {i['conflicts_with']} - {i['notes']}")
            for g in deps["group_with"]:
                print(f"    BATCH WITH: {g['batch_with']} - {g['notes']}")
    
    # Tool 5: Service orders
    print(f"\n--- Tool 5: search_service_orders('{TEST_SERIAL}') ---")
    orders = search_service_orders(TEST_SERIAL)
    print(f"Found {len(orders)} service orders:")
    for so in orders[:5]:  # Show first 5
        print(f"  {so['service_order_id']} | {so['order_date']} | {so['order_type']} | {so['status']}")
        if so['technician_notes']:
            print(f"    Notes: {so['technician_notes'][:80]}")
    if len(orders) > 5:
        print(f"  ... and {len(orders) - 5} more")
    
    print(f"\n{'='*60}")
    print("ALL TOOLS WORKING")
    print(f"{'='*60}")
    print("\nNext step: Step 2 will connect these tools to the AI model.")
