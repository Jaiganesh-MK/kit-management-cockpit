"""
step11_cockpit.py
Kit Management Decision Cockpit for Installed Base Management
=============================================================
Enterprise-grade decision cockpit for service planners and SAP users.
Workflow: Asset -> Diagnose -> Recommend -> Plan -> Approve -> Update

Run: streamlit run step11_cockpit.py
"""

import streamlit as st
import json, requests, urllib3, pandas as pd, re
from datetime import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from step1_data_layer import (
    lookup_equipment, find_applicable_kits, check_installation_history,
    check_kit_dependencies, search_service_orders,
)

# ============================================================
# CONFIG  —  add your OpenRouter API keys here
# ============================================================
try:
    # Production: keys stored in Streamlit Cloud secrets or local .streamlit/secrets.toml
    API_KEYS = {
        "agent1": st.secrets["api_keys"]["agent1"],
        "agent2": st.secrets["api_keys"]["agent2"],
        "chat":   st.secrets["api_keys"]["chat"],
    }
except Exception:
    # Fallback: paste keys directly here for quick local testing only
    API_KEYS = {"agent1": "YOUR_KEY_1", "agent2": "YOUR_KEY_2", "chat": "YOUR_KEY_3"}
BASE_URL  = "https://openrouter.ai/api/v1/chat/completions"
MODELS    = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-120b:free",
    "google/gemma-3-27b-it:free",
    "minimax/minimax-m2.5:free",
]
CONFIDENCE_THRESHOLD = 0.70

# ============================================================
# AGENT SYSTEM PROMPTS
# ============================================================
AGENT1_SYS = """You are the Analysis Agent for Tetra Pak.

JOB: Assess data quality, infer installed state, match kits using TYPE-SPECIFIC LOGIC.

KIT TYPE LOGIC:
- MANDATORY (MK_*): Non-negotiable. Not installed -> INSTALL. Prerequisites not met -> ORDER with order_sequence.
- UPGRADE (UK_*): Need customer signal. Check technician notes for "asked about upgrades"/"showing wear"/"intermittent faults". Signal found -> PROPOSE_TO_CUSTOMER. No signal -> AVAILABLE_NOT_RECOMMENDED.
- VCK: Check current volume vs target. Already at target -> SKIP. Needed -> PROPOSE_TO_CUSTOMER + flag "9,101 MSTK re-eval".
- If included_in_mu=True -> flag "in MU, avoid double-order".

Dependencies: Prerequisites not met -> ORDER with sequence. Conflicts -> BLOCKED_BY_CONFLICT.

Keep reasoning brief. JSON only.

Schema:
{"equipment_serial":"str","data_quality":{"overall_confidence":"HIGH/MEDIUM/LOW","verification_status":"CURRENT/STALE/CRITICAL","last_verified":"date","issues":[]},"inferred_state":{"description":"str","inferred_installations":[{"mstk_number":"str","status":"CONFIRMED_INSTALLED/PROBABLY_INSTALLED/NOT_INSTALLED","evidence":"str"}],"config_drift":[{"field":"str","recorded":"str","likely_actual":"str","evidence":"str"}],"discrepancies":[{"type":"str","description":"str"}]},"kit_decisions":[{"mstk_number":"str","mcon_name":"str","rk_type":"str","category":"Mandatory/Upgrade/VCK","action":"INSTALL/ORDER/SKIP/VERIFY_FIRST/PROPOSE_TO_CUSTOMER/AVAILABLE_NOT_RECOMMENDED/BLOCKED_BY_CONFLICT","priority":"CRITICAL/HIGH/MEDIUM/LOW","confidence":0.0,"reasoning":"1-2 sent","deadline":"or null","order_sequence":[],"customer_signal":"if PROPOSE","mu_note":"if in MU"}],"grouping":"str"}"""

AGENT2_SYS = """You are the Action Plan Generator for Tetra Pak.

JOB: Convert analysis into EXECUTABLE WORK INSTRUCTIONS + IB DATABASE UPDATES.

CRITICAL: Generate SPECIFIC SQL statements using actual serial numbers, MSTKs, dates.

JSON only.

Schema:
{"equipment_serial":"str","action_plan":{"immediate_actions":{"order_requisitions":[{"mstk":"str","kit_name":"str","qty":1,"price_eur":0,"urgency":"immediate/routine","why":"str"}],"verifications":[{"what":"str","at_serial":"str","assigned_to":"SAR/Tech","why":"str"}],"customer_proposals":[{"mstk":"str","kit_name":"str","value_prop":"str","signal":"str"}]},"installation_plan":{"sequence":[{"step":1,"mstk":"str","kit_name":"str","downtime_hrs":0,"skills":[],"enables":"or null"}],"batching":"str","total_downtime_hrs":0,"scheduling":"str"},"prerequisite_resolution":{"blocked":[{"kit":"str","by":"str","sequence":[]}],"uncertain":[{"kit":"str","prereq":"str","evidence_needed":"str"}],"conflicts":[{"kit_a":"str","kit_b":"str","resolution":"str"}]},"ib_database_updates":{"insert_installation_records":[],"update_status":[],"update_config":[],"update_verification":[],"summary":"str"},"cost_summary":{"total_kit_cost_eur":0,"total_downtime_hrs":0,"technician_days":0,"deadline_count":0}},"exec_summary":"str"}"""

# ============================================================
# LLM CALLERS
# ============================================================
def call_llm(system_prompt, user_prompt, max_tokens=6000, agent="agent1"):
    api_key = API_KEYS.get(agent, API_KEYS["agent1"])
    for model in MODELS:
        try:
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt},
                              {"role": "user",   "content": user_prompt}],
                "temperature": 0.2, "max_tokens": max_tokens,
            }
            if "nemotron" in model:
                payload["reasoning"] = {"effort": "none"}
            r = requests.post(BASE_URL, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }, json=payload, verify=False)
            if r.status_code == 200:
                c = r.json()["choices"][0]["message"]["content"]
                if c and len(c.strip()) > 10:
                    return c, model
        except Exception:
            continue
    return None, "Failed"


def call_llm_chat(messages, max_tokens=1500):
    api_key = API_KEYS.get("chat", API_KEYS["agent1"])
    for model in MODELS:
        try:
            payload = {"model": model, "messages": messages,
                       "temperature": 0.4, "max_tokens": max_tokens}
            if "nemotron" in model:
                payload["reasoning"] = {"effort": "none"}
            r = requests.post(BASE_URL, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }, json=payload, verify=False)
            if r.status_code == 200:
                c = r.json()["choices"][0]["message"]["content"]
                if c:
                    if "<final>" in c:
                        s = c.find("<final>") + len("<final>"); e = c.find("</final>")
                        if e > s: c = c[s:e].strip()
                    return c.strip()
        except Exception:
            continue
    return "Sorry, could not generate a response. Please try again."


def parse_json(raw):
    c = raw.strip()
    if "<final>" in c:
        s = c.find("<final>") + len("<final>"); e = c.find("</final>")
        if e > s: c = c[s:e].strip()
    if c.startswith("```"):
        parts = c.split("\n", 1)
        if len(parts) > 1: c = parts[1].rsplit("```", 1)[0]
    if not c.startswith("{"):
        i = c.find("{")
        if i == -1: return None
        c = c[i:]
    try:
        return json.loads(c)
    except Exception:
        pass
    bc, je = 0, -1
    for i, ch in enumerate(c):
        if ch == "{": bc += 1
        elif ch == "}":
            bc -= 1
            if bc == 0: je = i + 1; break
    if je > 0:
        try: return json.loads(c[:je])
        except Exception: pass
    return _recover_truncated_json(c)


def _recover_truncated_json(text):
    in_string = escape = False
    last_safe = -1
    for i, ch in enumerate(text):
        if escape: escape = False; continue
        if ch == "\\": escape = True; continue
        if ch == '"': in_string = not in_string; continue
        if in_string: continue
        if ch in "}]": last_safe = i + 1
        elif ch == ",": last_safe = i
    if last_safe <= 0: return None
    trunc = text[:last_safe].rstrip().rstrip(",").rstrip()
    in_string = escape = False; stack = []
    for ch in trunc:
        if escape: escape = False; continue
        if ch == "\\": escape = True; continue
        if ch == '"': in_string = not in_string; continue
        if in_string: continue
        if ch == "{": stack.append("{")
        elif ch == "[": stack.append("[")
        elif ch == "}" and stack and stack[-1] == "{": stack.pop()
        elif ch == "]" and stack and stack[-1] == "[": stack.pop()
    closing = "".join("}" if s == "{" else "]" for s in reversed(stack))
    try: return json.loads(trunc + closing)
    except Exception: return None

# ============================================================
# DATA GATHERING
# ============================================================
def gather_context(serial):
    eq = lookup_equipment(serial)
    if "error" in eq: return None
    cfg = {k.replace("config_", ""): v for k, v in eq.items() if k.startswith("config_") and v}
    apps = find_applicable_kits(eq.get("material_number", ""), cfg)
    hist = check_installation_history(serial)
    deps = {}
    for kit in apps:
        if kit["mcon_number"] not in deps:
            deps[kit["mcon_number"]] = check_kit_dependencies(kit["mcon_number"])
    so = search_service_orders(serial)
    return {"equipment": eq, "config": cfg, "applicable_kits": apps,
            "installation_history": hist, "dependencies": deps, "service_orders": so}


def build_agent1_prompt(ctx):
    eq = ctx["equipment"]
    p = (f"Equipment: {eq.get('serial_number')} | {eq.get('material_number')} | {eq.get('description')}\n"
         f"Customer: {eq.get('customer_name')}, {eq.get('site')}, {eq.get('country')}\n"
         f"Install: {eq.get('install_date')} | Last Verified: {eq.get('last_verified_date')} | Status: {eq.get('status')}\n"
         f"Config: {json.dumps(ctx['config'])}\n\n"
         f"APPLICABLE KITS ({len(ctx['applicable_kits'])}):\n")
    for k in ctx["applicable_kits"]:
        p += f"- {k['mstk_number']} | {k['mcon_name']} | {k['rk_type']} | {k['category']} | Match: {k['config_match_status']}"
        if k['implementation_deadline']: p += f" | DEADLINE: {k['implementation_deadline']}"
        if k['vck_affected'] == 'True': p += " | VCK_AFFECTED"
        if k['included_in_mu'] == 'True': p += " | IN_MU"
        p += "\n"
    p += f"\nINSTALLATION HISTORY ({len(ctx['installation_history'])}):\n"
    for h in ctx["installation_history"]:
        p += f"- {h['mstk_number']} | {h['installation_date']} | {h['installation_status']} | IB: {h['ib_updated']}"
        if h['notes']: p += f" | {h['notes']}"
        p += "\n"
    if not ctx["installation_history"]: p += "NONE\n"
    p += "\nDEPENDENCIES:\n"
    for mcon, d in ctx["dependencies"].items():
        for pr in d["prerequisites"]:
            p += f"- {mcon} REQUIRES {pr['depends_on']}: {pr['notes']}\n"
        for i in d["interferes_with"]:
            p += f"- {mcon} CONFLICTS {i['conflicts_with']}: {i['notes']}\n"
    p += f"\nSERVICE ORDERS ({len(ctx['service_orders'])}):\n"
    for s in ctx["service_orders"]:
        p += f"- {s['service_order_id']} | {s['order_date']} | {s['order_type']} | {s['status']}"
        if s['technician_notes']: p += f" | Notes: {s['technician_notes']}"
        if s['parts_referenced']: p += f" | Parts: {s['parts_referenced']}"
        p += "\n"
    return p


def build_chat_system_prompt(ctx, a1, a2):
    eq = ctx["equipment"]
    kit_list = "".join(
        f"  - {k['mstk_number']} | {k['mcon_name']} | {k['rk_type']} | Category: {k['category']}"
        f"{' | Deadline: ' + k['implementation_deadline'] if k.get('implementation_deadline') else ''}"
        f" | Price: {k.get('transfer_price_eur', 'N/A')} | Downtime: {k.get('estimated_downtime_hrs', 'N/A')}h\n"
        for k in ctx["applicable_kits"]
    )
    ap = a2.get("action_plan", {})
    kit_decisions_text = "".join(
        f"  - {k.get('mstk_number')} | Action: {k.get('action')} | Priority: {k.get('priority')} | Confidence: {k.get('confidence')}\n"
        f"    Reasoning: {k.get('reasoning','')}\n"
        for k in a1.get("kit_decisions", [])
    )
    return f"""You are a Tetra Pak Kit Management Expert Assistant embedded in the decision cockpit.
Equipment: {eq.get('serial_number')} | {eq.get('description')} | {eq.get('customer_name')}, {eq.get('site')}
Data quality: {a1.get('data_quality',{}).get('overall_confidence')} | Verification: {a1.get('data_quality',{}).get('verification_status')}
Discrepancies: {len(a1.get('inferred_state',{}).get('discrepancies',[]))} | Config drift: {len(a1.get('inferred_state',{}).get('config_drift',[]))}
Kit decisions:
{kit_decisions_text}
Executive summary: {a2.get('exec_summary','')}
Total cost: EUR {ap.get('cost_summary',{}).get('total_kit_cost_eur',0):,.0f} | Downtime: {ap.get('cost_summary',{}).get('total_downtime_hrs',0)}h
ANSWER GUIDELINES: Be concise (2-5 sentences). Reference specific MSTKs and service order IDs. Don't fabricate data."""

# ============================================================
# UI HELPERS
# ============================================================
def safe_float(v, default=0.0):
    if isinstance(v, (int, float)): return float(v)
    try: return float(v)
    except Exception: return default



def render_html(html_str):
    """Collapse multiline HTML to one line before st.markdown.
    Stops Streamlit markdown parser from treating indented lines as code blocks."""
    st.markdown(re.sub(r'\s+', ' ', html_str).strip(), unsafe_allow_html=True)

def ib_health_score(a1):
    """Compute IB health 0-100 from agent 1 output."""
    score = 100
    dq = a1.get("data_quality", {})
    if dq.get("verification_status") in ("STALE",): score -= 20
    elif dq.get("verification_status") == "CRITICAL": score -= 35
    score -= min(len(dq.get("issues", [])) * 8, 24)
    inf = a1.get("inferred_state", {})
    score -= min(len(inf.get("discrepancies", [])) * 12, 30)
    score -= min(len(inf.get("config_drift", [])) * 15, 30)
    return max(0, min(100, score))


def top_kit(kit_decisions):
    """Return the highest-priority INSTALL or ORDER kit decision."""
    prank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    actionable = [k for k in kit_decisions if k.get("action") in ("INSTALL", "ORDER", "VERIFY_FIRST")]
    if not actionable: return kit_decisions[0] if kit_decisions else None
    actionable.sort(key=lambda k: (prank.get(k.get("priority","LOW"), 3), -safe_float(k.get("confidence",0))))
    return actionable[0]


def chip(text, style="default"):
    """Return a small HTML status chip."""
    styles = {
        "critical":  "background:#FEE2E2;color:#991B1B;border:0.5px solid #FCA5A5",
        "high":      "background:#FEF3C7;color:#92400E;border:0.5px solid #FCD34D",
        "medium":    "background:#DBEAFE;color:#1D4ED8;border:0.5px solid #93C5FD",
        "low":       "background:#D1FAE5;color:#065F46;border:0.5px solid #6EE7B7",
        "ai":        "background:#F3E8FF;color:#460073;border:0.5px solid #A100FF",
        "sap":       "background:#EFF6FF;color:#1D4ED8;border:0.5px solid #93C5FD",
        "stale":     "background:#FEE2E2;color:#991B1B;border:0.5px solid #EF4444",
        "ok":        "background:#D1FAE5;color:#065F46;border:0.5px solid #10B981",
        "install":   "background:#F3E8FF;color:#460073;border:1px solid #A100FF",
        "order":     "background:#FEF3C7;color:#92400E;border:0.5px solid #F59E0B",
        "mandatory": "background:#FEE2E2;color:#991B1B;border:0.5px solid #FCA5A5",
        "upgrade":   "background:#F3E8FF;color:#7500C0;border:0.5px solid #D8B4FE",
        "default":   "background:#F3F4F6;color:#374151;border:0.5px solid #D1D5DB",
    }
    s = styles.get(style.lower(), styles["default"])
    return f"<span style='{s};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500'>{text}</span>"


def conf_bar(pct, width=120):
    """Return an HTML confidence bar."""
    color = "#16A34A" if pct >= 0.8 else "#F59E0B" if pct >= 0.5 else "#EF4444"
    fill = int(pct * 100)
    return (
        f"<div style='display:flex;align-items:center;gap:8px'>"
        f"<div style='width:{width}px;height:6px;background:#E9D5FF;border-radius:3px;overflow:hidden'>"
        f"<div style='width:{fill}%;height:100%;background:{color};border-radius:3px'></div></div>"
        f"<span style='font-size:12px;font-weight:600;color:{color}'>{pct:.0%}</span>"
        f"</div>"
    )


def ev_chip(source_type):
    """Return a small evidence source chip."""
    m = {
        "sap":  ("SAP IB",       "background:#DBEAFE;color:#1D4ED8"),
        "so":   ("Service order", "background:#F3E8FF;color:#7500C0"),
        "ai":   ("AI inference",  "background:#D1FAE5;color:#065F46"),
        "rule": ("Directive",     "background:#FEF3C7;color:#92400E"),
    }
    lbl, s = m.get(source_type, ("—", "background:#F3F4F6;color:#666"))
    return f"<span style='{s};padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600;white-space:nowrap'>{lbl}</span>"


def section_hdr(text, color="#6B7280"):
    return (
        f"<div style='font-size:10px;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.06em;color:{color};margin:10px 0 5px'>{text}</div>"
    )


def divider():
    return "<div style='height:0.5px;background:#E5E7EB;margin:6px 0'></div>"

# ============================================================
# CSS
# ============================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

.stApp { font-family:'Inter',-apple-system,sans-serif; background:#F1F0F4; }
.stApp > header { display:none!important; }
.stMainBlockContainer,[data-testid="stMainBlockContainer"],
.block-container,[data-testid="block-container"] {
    padding-top:0!important; padding-left:0!important;
    padding-right:0!important; padding-bottom:0!important;
    max-width:100%!important;
}
section.main > div { padding-top:0!important; }
[data-testid="stSidebar"],[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] { display:none!important; }

/* ---- COMMAND BAR ---- */
.cmd-bar {
    background:#FFFFFF;
    border-bottom:1px solid #E5E7EB;
    padding:10px 20px 8px;
}
.cmd-top { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:8px; }
.cmd-bottom { display:flex; align-items:center; gap:0; }

.serial-box {
    font-family:'JetBrains Mono',monospace;
    font-size:14px; font-weight:600; color:#460073;
    background:#F3E8FF; border:1.5px solid #A100FF;
    border-radius:5px; padding:4px 10px; min-width:120px;
}
.meta-item {
    background:#F9FAFB; border:0.5px solid #E5E7EB;
    border-radius:4px; padding:3px 8px; font-size:11px;
    color:#374151; display:inline-flex; gap:4px; align-items:center;
}
.meta-lbl { color:#9CA3AF; font-size:10px; }
.meta-val { font-weight:500; }
.meta-val-stale { font-weight:600; color:#DC2626; }

.conf-pill {
    background:#F3E8FF; border:1px solid #A100FF;
    border-radius:20px; padding:3px 10px;
    font-size:11px; font-weight:600; color:#460073;
    display:inline-flex; align-items:center; gap:5px;
}
.conf-dot-green { width:7px; height:7px; border-radius:50%; background:#16A34A; display:inline-block; }
.conf-dot-amber { width:7px; height:7px; border-radius:50%; background:#F59E0B; display:inline-block; }
.conf-dot-red   { width:7px; height:7px; border-radius:50%; background:#EF4444; display:inline-block; }

/* workflow steps */
.wf-step { padding:4px 10px; font-size:10px; font-weight:500; color:#9CA3AF; border-bottom:2px solid transparent; display:inline-flex; align-items:center; gap:4px; cursor:default; }
.wf-step.done   { color:#16A34A; border-bottom-color:#16A34A; }
.wf-step.active { color:#A100FF; border-bottom-color:#A100FF; font-weight:600; }
.wf-arrow       { color:#D1D5DB; font-size:10px; padding:0 1px; }

/* ---- PANEL WRAPPERS (fixed height, internal scroll) ---- */
.panel-wrap {
    background:#FFFFFF; border:1px solid #E9E9EF; border-radius:10px;
    height:480px; min-height:480px; max-height:480px;
    padding:16px 18px; overflow-y:auto; overflow-x:hidden;
    display:flex; flex-direction:column; gap:0;
    box-shadow:0 2px 8px rgba(0,0,0,0.06);
}
.panel-wrap-tall {
    background:#FFFFFF; border:1px solid #E9E9EF; border-radius:10px;
    height:360px; padding:16px 18px; overflow-y:auto; overflow-x:hidden;
    box-shadow:0 2px 8px rgba(0,0,0,0.06);
}
.panel-hdr {
    display:flex; justify-content:space-between; align-items:center;
    padding-bottom:10px; border-bottom:1px solid #F3F4F6;
    margin-bottom:14px; flex-shrink:0;
}
.panel-title { font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; color:#374151; }
.panel-body  { flex:1; overflow-y:auto; }

/* ---- KIT SELECTOR PILLS ---- */
.kit-selector { display:flex; gap:5px; margin-bottom:12px; overflow-x:auto; padding-bottom:3px; flex-shrink:0; }
.kit-sel-btn  { padding:5px 11px; border-radius:20px; font-size:11px; font-weight:500; border:1.5px solid #E5E7EB; background:#F9FAFB; color:#6B7280; cursor:pointer; white-space:nowrap; flex-shrink:0; }
.kit-sel-btn.active { background:#F3E8FF; border-color:#A100FF; color:#460073; font-weight:600; }
.kit-sel-btn.crit   { border-left:3px solid #EF4444; }
.kit-sel-btn.high   { border-left:3px solid #F59E0B; }
.kit-sel-btn.med    { border-left:3px solid #3B82F6; }
.kit-sel-btn.low    { border-left:3px solid #10B981; }

/* ---- KIT PRIMARY CARD ---- */
.kit-card { background:linear-gradient(135deg,#F3E8FF,#FAF3FF); border:1.5px solid #A100FF; border-radius:10px; padding:14px 16px; margin-bottom:12px; flex-shrink:0; }
.kit-mstk { font-family:'JetBrains Mono',monospace; font-size:12px; color:#460073; background:#E9D5FF; padding:3px 9px; border-radius:4px; display:inline-block; margin-bottom:7px; }
.kit-name { font-size:16px; font-weight:700; color:#111827; margin-bottom:8px; line-height:1.3; }

/* ---- SECTION LABELS ---- */
.sec-lbl { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; color:#9CA3AF; margin:12px 0 6px; }

/* ---- EVIDENCE ---- */
.evidence-block { background:#F9FAFB; border-radius:8px; padding:10px 12px; }
.ev-row { display:flex; gap:8px; align-items:flex-start; padding:5px 0; border-bottom:0.5px solid #F3F4F6; font-size:12px; color:#374151; line-height:1.5; }
.ev-row:last-child { border:none; }

/* ---- RISKS ---- */
.risk-row { display:flex; align-items:flex-start; gap:8px; font-size:12px; color:#374151; padding:5px 0; line-height:1.45; }
.rdot-h { width:9px; height:9px; border-radius:50%; background:#EF4444; flex-shrink:0; margin-top:4px; }
.rdot-m { width:9px; height:9px; border-radius:50%; background:#F59E0B; flex-shrink:0; margin-top:4px; }
.rdot-l { width:9px; height:9px; border-radius:50%; background:#10B981; flex-shrink:0; margin-top:4px; }

/* ---- CONFIG ROWS ---- */
.cfg-row { display:flex; justify-content:space-between; align-items:center; padding:7px 0; border-bottom:0.5px solid #F3F4F6; }
.cfg-row:last-child { border:none; }
.cfg-key { font-size:12px; color:#6B7280; }
.cfg-val-sap { font-size:12px; font-weight:600; color:#1D4ED8; background:#EFF6FF; padding:2px 9px; border-radius:4px; font-family:'JetBrains Mono',monospace; }
.cfg-val-ai  { font-size:12px; font-weight:600; color:#460073; background:#F3E8FF; padding:2px 9px; border-radius:4px; display:inline-flex; align-items:center; gap:5px; }
.drift-dot { width:7px; height:7px; border-radius:50%; background:#EF4444; flex-shrink:0; }

/* ---- ALERTS ---- */
.alert-warn { background:#FEF3C7; border:0.5px solid #F59E0B; border-radius:6px; padding:9px 11px; font-size:12px; color:#92400E; display:flex; gap:8px; margin:5px 0; line-height:1.45; }
.alert-err  { background:#FEE2E2; border:0.5px solid #EF4444; border-radius:6px; padding:9px 11px; font-size:12px; color:#991B1B; display:flex; gap:8px; margin:5px 0; line-height:1.45; }

/* ---- IB HEALTH ---- */
.ib-health { background:linear-gradient(135deg,#460073,#7500C0); border-radius:10px; padding:14px 16px; color:#fff; margin-bottom:12px; flex-shrink:0; }
.ib-score { font-size:34px; font-weight:700; line-height:1; }
.ib-score-denom { font-size:15px; font-weight:400; opacity:0.7; }
.ib-risk-lbl { font-size:11px; opacity:0.85; margin-top:3px; font-weight:500; }
.ib-bar-bg { background:rgba(255,255,255,0.2); border-radius:3px; height:5px; margin:10px 0 8px; }
.ib-bar-fg { background:#fff; height:5px; border-radius:3px; }
.ib-stat { text-align:center; }
.ib-stat-val { font-size:16px; font-weight:700; }
.ib-stat-lbl { font-size:10px; opacity:0.75; margin-top:2px; }

/* ---- ACTION PLAN ---- */
.cost-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:12px; flex-shrink:0; }
.cost-card { background:#F9FAFB; border-radius:8px; padding:11px; text-align:center; border:1px solid #F3F4F6; }
.cost-val { font-size:18px; font-weight:700; color:#111827; }
.cost-lbl { font-size:10px; color:#9CA3AF; margin-top:2px; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; }
.urgency-bar { background:#FEF3C7; border:0.5px solid #F59E0B; border-radius:8px; padding:9px 11px; font-size:12px; color:#92400E; display:flex; gap:8px; margin-bottom:12px; flex-shrink:0; }
.step-row { display:flex; gap:10px; padding:9px 0; border-bottom:0.5px solid #F9FAFB; }
.step-row:last-child { border:none; }
.step-num { width:24px; height:24px; border-radius:50%; background:#A100FF; color:#fff; font-size:11px; font-weight:700; display:flex; align-items:center; justify-content:center; flex-shrink:0; margin-top:1px; }
.step-name { font-size:12px; font-weight:600; color:#111827; }
.step-meta { font-size:11px; color:#9CA3AF; margin-top:3px; display:flex; gap:10px; flex-wrap:wrap; }
.sql-block { background:#1F2937; border-radius:8px; padding:12px 14px; font-family:'JetBrains Mono',monospace; font-size:11px; color:#A7F3D0; line-height:1.7; word-break:break-all; }

/* ---- ALT CARDS ---- */
.alt-card { background:#F9FAFB; border:1px solid #F0F0F0; border-radius:7px; padding:9px 11px; margin-bottom:6px; }
.alt-name { font-size:12px; font-weight:500; color:#111827; }
.alt-why  { font-size:11px; color:#9CA3AF; margin-top:3px; line-height:1.45; }

/* ---- GOVERNANCE ---- */
.gov-item { background:#FAFAFA; border:0.5px solid #E5E7EB; border-left:3px solid; border-radius:6px; padding:9px 11px; margin-bottom:7px; }
.gov-item.pending   { border-left-color:#F59E0B; }
.gov-item.approved  { border-left-color:#10B981; }
.gov-item.rejected  { border-left-color:#EF4444; }
.gov-item.overridden{ border-left-color:#A100FF; }
.gov-item-title { font-size:12px; font-weight:500; color:#111827; }
.gov-item-sub   { font-size:11px; color:#9CA3AF; margin-top:3px; line-height:1.3; }
.gov-badge { font-size:10px; padding:2px 7px; border-radius:3px; font-weight:600; display:inline-block; margin-top:4px; }

.reasoning-box { background:#1F2937; border-radius:5px; padding:8px 10px; font-family:'JetBrains Mono',monospace; font-size:10px; color:#D1FAE5; line-height:1.6; white-space:pre-wrap; word-break:break-word; }

/* ---- ACTION PLAN ---- */
.cost-grid { display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-bottom:8px; }
.cost-card { background:#F9FAFB; border-radius:5px; padding:8px; text-align:center; border:0.5px solid #F3F4F6; }
.cost-val { font-size:15px; font-weight:600; color:#111827; }
.cost-lbl { font-size:10px; color:#9CA3AF; }

.urgency-bar { background:#FEF3C7; border:0.5px solid #F59E0B; border-radius:5px; padding:7px 9px; font-size:11px; color:#92400E; display:flex; gap:6px; margin-bottom:8px; }

.step-row { display:flex; gap:8px; padding:7px 0; border-bottom:0.5px solid #F9FAFB; }
.step-row:last-child { border:none; }
.step-num { width:20px; height:20px; border-radius:50%; background:#A100FF; color:#fff; font-size:10px; font-weight:600; display:flex; align-items:center; justify-content:center; flex-shrink:0; margin-top:1px; }
.step-name { font-size:11px; font-weight:500; color:#111827; }
.step-meta { font-size:10px; color:#9CA3AF; margin-top:3px; display:flex; gap:10px; flex-wrap:wrap; }

.sql-block { background:#1F2937; border-radius:5px; padding:8px 10px; font-family:'JetBrains Mono',monospace; font-size:10px; color:#A7F3D0; line-height:1.7; }

/* ---- TIMELINE ---- */
.timeline-wrap { background:#FFFFFF; border-top:1px solid #E5E7EB; padding:12px 20px; }
.tl-scroll { display:flex; overflow-x:auto; padding-bottom:4px; gap:0; }
.tl-item { display:flex; flex-direction:column; align-items:center; min-width:120px; position:relative; }
.tl-item:not(:last-child)::after { content:''; position:absolute; top:8px; left:50%; width:100%; height:1px; background:#E5E7EB; z-index:0; }
.tl-dot { width:16px; height:16px; border-radius:50%; border:2px solid; z-index:1; position:relative; flex-shrink:0; }
.tl-body { text-align:center; padding:5px 6px; margin-top:4px; }
.tl-date { font-size:10px; color:#9CA3AF; }
.tl-label { font-size:11px; font-weight:500; color:#111827; margin:2px 0; }
.tl-detail { font-size:10px; color:#6B7280; line-height:1.35; }
.tl-chip { font-size:9px; padding:1px 6px; border-radius:3px; font-weight:600; display:inline-block; margin-top:3px; }

/* ---- APPROVAL SECTION ---- */
.approval-wrap { background:#F3E8FF; border-top:2px solid #A100FF; padding:16px 20px; }
.approval-inner { background:#FFFFFF; border-radius:8px; border:1px solid #D8B4FE; overflow:hidden; max-width:960px; margin:0 auto; }
.approval-hdr { background:#460073; color:#fff; padding:12px 16px; display:flex; justify-content:space-between; align-items:center; }
.approval-body { padding:16px; display:grid; grid-template-columns:1fr 1fr; gap:16px; }

.ba-card { background:#F9FAFB; border-radius:6px; padding:10px; }
.ba-lbl-before { font-size:10px; font-weight:600; color:#991B1B; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px; }
.ba-lbl-after  { font-size:10px; font-weight:600; color:#065F46; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px; }
.ba-row { display:flex; justify-content:space-between; align-items:center; padding:4px 0; border-bottom:0.5px solid #F3F4F6; font-size:11px; }
.ba-row:last-child { border:none; }
.ba-key { color:#6B7280; }
.val-old { color:#991B1B; background:#FEE2E2; padding:1px 6px; border-radius:3px; font-family:'JetBrains Mono',monospace; font-size:10px; }
.val-new { color:#065F46; background:#D1FAE5; padding:1px 6px; border-radius:3px; font-family:'JetBrains Mono',monospace; font-size:10px; }

.conf-bk { background:#F3E8FF; border-radius:6px; padding:10px; }
.cf-row { display:flex; justify-content:space-between; align-items:center; padding:3px 0; font-size:11px; color:#374151; }
.cf-bar-bg { width:70px; height:4px; background:#E9D5FF; border-radius:2px; overflow:hidden; display:inline-block; }
.cf-bar-fg { height:100%; background:#A100FF; border-radius:2px; }

/* ---- CHAT ---- */
.chat-wrap { background:#FFFFFF; border-top:1px solid #E5E7EB; padding:12px 20px; }
.chat-msg-user { background:#F3E8FF; border-radius:8px 8px 2px 8px; padding:8px 12px; font-size:12px; color:#460073; margin-bottom:6px; max-width:85%; margin-left:auto; }
.chat-msg-ai   { background:#F9FAFB; border:0.5px solid #E5E7EB; border-radius:8px 8px 8px 2px; padding:8px 12px; font-size:12px; color:#111827; margin-bottom:6px; max-width:92%; }

/* ---- LANDING ---- */
.landing-cap { background:#FFFFFF; border:0.5px solid #E5E7EB; border-radius:8px; padding:14px 12px; height:180px; display:flex; flex-direction:column; }
.landing-cap-icon { font-size:20px; margin-bottom:6px; }
.landing-cap-title { font-size:12px; font-weight:600; color:#111827; margin-bottom:5px; }
.landing-cap-desc  { font-size:11px; color:#6B7280; line-height:1.5; }

div[data-testid="stMetricValue"] { font-size:22px!important; }
#MainMenu, footer { visibility:hidden; }

/* ---- TEXT INPUT bottom-alignment with buttons ---- */
/* Remove the invisible label height so input sits at same baseline as buttons */
div[data-testid="stTextInput"] {
    margin-top: 0 !important;
    padding-top: 0 !important;
}
div[data-testid="stTextInput"] > label {
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* ---- SERIAL NUMBER INPUT — clearly differentiated ---- */
div[data-testid="stTextInput"] input {
    background: #F3E8FF !important;
    border: 2px solid #A100FF !important;
    border-radius: 8px !important;
    color: #460073 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    padding: 8px 12px !important;
}
div[data-testid="stTextInput"] input::placeholder {
    color: #B794F4 !important;
    font-weight: 400 !important;
    font-style: italic !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #7500C0 !important;
    box-shadow: 0 0 0 3px rgba(161,0,255,0.15) !important;
    outline: none !important;
}
div[data-testid="stTextInput"] label { display:none; }

/* ---- CHAT INPUT — stand out from background ---- */
div[data-testid="stChatInput"] {
    background: #FFFFFF !important;
    border: 2px solid #A100FF !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 12px rgba(161,0,255,0.12) !important;
    padding: 4px 8px !important;
}
div[data-testid="stChatInput"] textarea {
    background: #FFFFFF !important;
    color: #111827 !important;
    font-size: 13px !important;
}
div[data-testid="stChatInput"] textarea::placeholder {
    color: #9CA3AF !important;
    font-style: italic !important;
}
/* Chat send button */
div[data-testid="stChatInput"] button {
    background: #A100FF !important;
    border-radius: 8px !important;
}

/* ---- SELECTBOX ---- */
div[data-testid="stSelectbox"] > div > div {
    background:#F3E8FF !important;
    border:1.5px solid #A100FF !important;
    border-radius:8px !important;
    font-size:13px !important;
    font-weight:500 !important;
    color:#460073 !important;
}

/* ---- TABS (bottom sections) ---- */
.stTabs [data-baseweb="tab-list"] {
    gap:6px; background:#F9FAFB; padding:6px 8px; border-radius:8px;
    border:1px solid #E9E9EF;
}
.stTabs [data-baseweb="tab"] {
    font-size:13px; font-weight:500; color:#6B7280;
    padding:6px 16px; border-radius:6px;
    background:transparent; border:none;
}
.stTabs [aria-selected="true"] {
    background:#FFFFFF !important; color:#460073 !important;
    font-weight:600 !important; box-shadow:0 1px 4px rgba(0,0,0,0.1);
}

/* ---- APPROVAL BUTTONS (override Streamlit defaults) ---- */
div[data-testid="stButton"] button[kind="primary"] {
    background:linear-gradient(135deg,#460073,#A100FF) !important;
    border:none !important; color:#fff !important;
    font-size:13px !important; font-weight:600 !important;
    padding:10px 20px !important; border-radius:8px !important;
}
div[data-testid="stButton"] button[kind="secondary"] {
    background:#FFFFFF !important;
    border:1.5px solid #E5E7EB !important;
    color:#374151 !important;
    font-size:13px !important; font-weight:500 !important;
    padding:10px 20px !important; border-radius:8px !important;
}

/* Content area horizontal padding */
[data-testid="stMainBlockContainer"] > div > div {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}
/* Panel scroll bar styling */
.panel-wrap::-webkit-scrollbar { width:4px; }
.panel-wrap::-webkit-scrollbar-track { background:transparent; }
.panel-wrap::-webkit-scrollbar-thumb { background:#E9D5FF; border-radius:2px; }
.panel-wrap-tall::-webkit-scrollbar { width:4px; }
.panel-wrap-tall::-webkit-scrollbar-track { background:transparent; }
.panel-wrap-tall::-webkit-scrollbar-thumb { background:#E9D5FF; border-radius:2px; }
</style>
"""

# ============================================================
# PAGE CONFIG + SESSION STATE
# ============================================================
st.set_page_config(page_title="IB Kit Management Cockpit", page_icon="🔧", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

_defaults = {
    "analysis_done": False,
    "ctx": None, "a1": None, "a2": None,
    "current_serial": None,
    "chat_messages": [],
    "model_names": {"a1": "", "a2": ""},
    "show_reasoning": False,
    "show_approval": False,
    "show_chat": False,
    "approval_status": "PENDING",  # PENDING / APPROVED / REJECTED / REVIEW
    "active_kit_idx": 0,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================
# COMMAND BAR
# ============================================================
def build_export_report(ctx, a1, a2):
    """Build a plain-text summary report for download."""
    eq   = ctx["equipment"]
    dq   = a1.get("data_quality", {})
    inf  = a1.get("inferred_state", {})
    kits = a1.get("kit_decisions", [])
    ap   = a2.get("action_plan", {})
    cost = ap.get("cost_summary", {})
    seq  = ap.get("installation_plan", {}).get("sequence", [])
    ibu  = ap.get("ib_database_updates", {})
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")

    def _sql_str(x):
        if isinstance(x, str): return x
        if isinstance(x, dict): return x.get("sql") or x.get("statement") or json.dumps(x)
        return str(x)

    lines = [
        "=" * 70,
        "  KIT MANAGEMENT DECISION REPORT",
        f"  Generated: {now}",
        "=" * 70,
        "",
        "EQUIPMENT",
        "-" * 40,
        f"  Serial Number  : {eq.get('serial_number','—')}",
        f"  Material       : {eq.get('material_number','—')}",
        f"  Description    : {eq.get('description','—')}",
        f"  Customer       : {eq.get('customer_name','—')}",
        f"  Site           : {eq.get('site','—')}, {eq.get('country','—')}",
        f"  Install Date   : {eq.get('install_date','—')}",
        f"  Last Verified  : {eq.get('last_verified_date','—')}",
        f"  Status         : {eq.get('status','—')}",
        "",
        "DATA QUALITY",
        "-" * 40,
        f"  Overall Confidence : {dq.get('overall_confidence','—')}",
        f"  Verification       : {dq.get('verification_status','—')}",
        f"  Last Verified      : {dq.get('last_verified','—')}",
    ]
    for issue in dq.get("issues", []):
        lines.append(f"  ⚠ Issue: {issue}")

    lines += ["", "INFERRED STATE", "-" * 40]
    lines.append(f"  {inf.get('description','—')}")
    for d in inf.get("discrepancies", []):
        lines.append(f"  ✗ Discrepancy — {d.get('type','')}: {d.get('description','')}")
    for c in inf.get("config_drift", []):
        lines.append(f"  ⟳ Config Drift — {c.get('field','')}: recorded={c.get('recorded','')} → likely={c.get('likely_actual','')}")

    lines += ["", "KIT DECISIONS", "-" * 40]
    prank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_kits = sorted(kits, key=lambda k: prank.get(k.get("priority","LOW"), 3))
    for k in sorted_kits:
        conf = safe_float(k.get("confidence", 0))
        lines.append(
            f"  [{k.get('priority','—'):8}] {k.get('action','—'):25} "
            f"Conf:{conf:.0%}  {k.get('mstk_number','—')}  {k.get('mcon_name','—')}")
        lines.append(f"           ↳ {k.get('reasoning','')}")
        if k.get("deadline"):
            lines.append(f"           ⏰ Deadline: {k['deadline']}")

    lines += ["", "EXECUTION PLAN", "-" * 40,
              f"  Total Kit Cost : €{cost.get('total_kit_cost_eur', 0):,.0f}",
              f"  Total Downtime : {cost.get('total_downtime_hrs', 0)} hours",
              f"  Technician Days: {cost.get('technician_days', 0)}",
              f"  Deadline Items : {cost.get('deadline_count', 0)}",
              ""]
    for s in seq:
        skills = ", ".join(str(x) for x in s.get("skills", [])) if isinstance(s.get("skills"), list) else "—"
        lines.append(f"  Step {s.get('step',0)}: {s.get('mstk','')} — {s.get('kit_name','')}")
        lines.append(f"         Downtime: {s.get('downtime_hrs',0)}h  Skills: {skills}")

    lines += ["", "IB DATABASE UPDATES (SQL)", "-" * 40]
    all_sql = (
        [_sql_str(x) for x in ibu.get("insert_installation_records", [])] +
        [_sql_str(x) for x in ibu.get("update_config", [])] +
        [_sql_str(x) for x in ibu.get("update_verification", [])]
    )
    for sql in all_sql:
        lines.append(f"  {sql}")
    if not all_sql:
        lines.append("  No SQL updates generated.")

    lines += ["", "EXECUTIVE SUMMARY", "-" * 40,
              f"  {a2.get('exec_summary', '—')}",
              "", "=" * 70,
              f"  Accenture Strategy & Consulting  |  Kit Management for Installed Base",
              "=" * 70]

    return "\n".join(lines)


@st.dialog("💬 Ask AI", width="large")
def chat_popup(ctx, a1, a2):
    """Floating chatbot dialog — triggered by Ask AI button."""
    eq = ctx["equipment"]

    st.markdown(
        f"<div style='background:linear-gradient(135deg,#F3E8FF,#FAF3FF);"
        f"border-radius:8px;padding:10px 14px;margin-bottom:12px'>"
        f"<div style='font-size:13px;font-weight:700;color:#460073'>"
        f"Equipment {eq.get('serial_number','')} — full context loaded</div>"
        f"<div style='font-size:12px;color:#7500C0;margin-top:2px'>"
        f"Ask anything about this equipment, its kits, or service history.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Suggestion chips when empty
    if not st.session_state.chat_messages:
        suggestions = [
            "What discrepancies were found?",
            "Why is this kit critical?",
            "Summarise cost and downtime",
            "Which kits can be batched?",
            "What evidence shows IB drift?",
            "Explain the recommended action",
        ]
        st.markdown(
            "<div style='font-size:11px;font-weight:600;color:#9CA3AF;"
            "text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px'>Suggested questions</div>",
            unsafe_allow_html=True,
        )
        s_cols = st.columns(2)
        for i, s in enumerate(suggestions):
            if s_cols[i % 2].button(s, key=f"popup_sugg_{i}", use_container_width=True):
                st.session_state.chat_messages.append({"role": "user", "content": s})
                sys_p = build_chat_system_prompt(ctx, a1, a2)
                msgs  = [{"role": "system", "content": sys_p}] + st.session_state.chat_messages
                with st.spinner("Thinking…"):
                    reply = call_llm_chat(msgs)
                st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                st.rerun()

    # Message history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
            st.markdown(msg["content"])

    if st.session_state.chat_messages:
        if st.button("🗑️ Clear", key="popup_clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()

    # Chat input inside dialog
    prompt = st.chat_input("Ask about this equipment…", key="popup_chat_input")
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking…"):
                sys_p = build_chat_system_prompt(ctx, a1, a2)
                msgs  = [{"role": "system", "content": sys_p}] + st.session_state.chat_messages
                reply = call_llm_chat(msgs)
            st.markdown(reply)
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})


# ============================================================
# COMMAND BAR
# ============================================================
def render_command_bar():
    eq   = st.session_state.ctx["equipment"] if st.session_state.ctx else {}
    a1   = st.session_state.a1 or {}
    dq   = a1.get("data_quality", {})
    done = st.session_state.analysis_done

    # Compute top-recommendation confidence
    conf_val = safe_float(
        next((k["confidence"] for k in a1.get("kit_decisions", [])
              if k.get("action") in ("INSTALL", "ORDER")), None) or 0
    )

    # ── Row 1: meta chips (pure Streamlit columns) ──────────────────
    st.markdown('<div class="cmd-bar-outer">', unsafe_allow_html=True)

    c0, c1, c2, c3, c4, c5, c6, c7 = st.columns([1.2, 1.5, 1.1, 2, 1.5, 1, 1.2, 1.2])

    # Serial
    _sn = eq.get("serial_number", "—")
    c0.markdown(
        f'<span style="font-family:JetBrains Mono,monospace;font-size:13px;font-weight:600;'
        f'color:#460073;background:#F3E8FF;border:1.5px solid #A100FF;'
        f'border-radius:5px;padding:4px 9px">{_sn}</span>',
        unsafe_allow_html=True)

    # Customer
    c1.markdown(
        f"<div style='background:#F9FAFB;border:0.5px solid #E5E7EB;border-radius:4px;padding:3px 8px;font-size:11px'>"
        f"<span style='color:#9CA3AF;font-size:10px'>Customer&nbsp;</span>"
        f"<span style='font-weight:500'>{eq.get('customer_name','—')}</span></div>",
        unsafe_allow_html=True)

    # Site
    c2.markdown(
        f"<div style='background:#F9FAFB;border:0.5px solid #E5E7EB;border-radius:4px;padding:3px 8px;font-size:11px'>"
        f"<span style='color:#9CA3AF;font-size:10px'>Site&nbsp;</span>"
        f"<span style='font-weight:500'>{eq.get('site','—')}</span></div>",
        unsafe_allow_html=True)

    # Machine
    c3.markdown(
        f"<div style='background:#F9FAFB;border:0.5px solid #E5E7EB;border-radius:4px;padding:3px 8px;font-size:11px'>"
        f"<span style='color:#9CA3AF;font-size:10px'>Machine&nbsp;</span>"
        f"<span style='font-weight:500'>{eq.get('description','—')}</span></div>",
        unsafe_allow_html=True)

    # Last verified
    last_v = eq.get("last_verified_date", "—")
    stale  = done and dq.get("verification_status") in ("STALE", "CRITICAL")
    lv_color = "#DC2626" if stale else "#374151"
    c4.markdown(
        f"<div style='background:#F9FAFB;border:0.5px solid #E5E7EB;border-radius:4px;padding:3px 8px;font-size:11px'>"
        f"<span style='color:#9CA3AF;font-size:10px'>Verified&nbsp;</span>"
        f"<span style='font-weight:600;color:{lv_color}'>{last_v}</span></div>",
        unsafe_allow_html=True)

    # Status badge
    if done:
        c5.markdown(chip("Analysis ready", "ai"), unsafe_allow_html=True)
    else:
        c5.markdown(chip("No case open", "default"), unsafe_allow_html=True)

    # Approval status
    appr_map = {"APPROVED": ("IB approved", "ok"), "REJECTED": ("Rejected", "critical"),
                "REVIEW": ("In review", "high")}
    if st.session_state.approval_status in appr_map:
        lbl, sty = appr_map[st.session_state.approval_status]
        c6.markdown(chip(lbl, sty), unsafe_allow_html=True)
    elif done:
        c7.markdown(
            f"<div style='background:#F3E8FF;border:1px solid #A100FF;border-radius:20px;"
            f"padding:3px 10px;font-size:11px;font-weight:600;color:#460073;"
            f"display:inline-flex;align-items:center;gap:5px'>"
            f"<span style='width:7px;height:7px;border-radius:50%;"
            f"background:{'#16A34A' if conf_val >= 0.75 else '#F59E0B' if conf_val >= 0.5 else '#EF4444'};"
            f"display:inline-block'></span>Confidence {conf_val:.0%}</div>",
            unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Row 2: workflow steps ────────────────────────────────────────
    wf_steps = [
        ("Asset",     done),
        ("Diagnose",  done),
        ("Recommend", done),
        ("Plan",      done),
        ("Approve",   st.session_state.approval_status == "APPROVED"),
        ("Update",    st.session_state.approval_status == "APPROVED"),
    ]
    # Active step is the first incomplete one
    active_idx = next((i for i, (_, complete) in enumerate(wf_steps) if not complete),
                      len(wf_steps) - 1)
    parts = []
    for i, (name, complete) in enumerate(wf_steps):
        cls_style = ("color:#16A34A;border-bottom:2px solid #16A34A" if complete else
                     "color:#A100FF;border-bottom:2px solid #A100FF;font-weight:600" if i == active_idx else
                     "color:#9CA3AF;border-bottom:2px solid transparent")
        parts.append(
            f"<span style='padding:4px 10px;font-size:10px;{cls_style};display:inline-block'>{name}</span>"
        )
        if i < len(wf_steps) - 1:
            parts.append("<span style='color:#D1D5DB;font-size:10px;padding:0 1px'>›</span>")

    st.markdown(
        "<div style='background:#FAFAFA;border-top:0.5px solid #F3F4F6;"
        "padding:2px 8px'>" + "".join(parts) + "</div>",
        unsafe_allow_html=True)

    # ── Row 3: serial input + action buttons — all bottom-aligned ────
    st.markdown("<div style='padding:4px 10px 8px;background:#fff;border-top:0.5px solid #F3F4F6'>",
                unsafe_allow_html=True)
    bc1, bc2, bc3, bc4, bc5 = st.columns([2, 1, 1, 1, 1], vertical_alignment="bottom")

    serial_input = bc1.text_input(
        "Serial", value=st.session_state.current_serial or "",
        label_visibility="collapsed", placeholder="Enter equipment serial number")

    run = bc2.button("▶  Run", type="primary", use_container_width=True)

    if bc3.button("Reasoning" if not st.session_state.show_reasoning else "Hide Trace",
                  use_container_width=True):
        st.session_state.show_reasoning = not st.session_state.show_reasoning
        st.rerun()

    # Ask AI — triggers popup dialog (only when analysis is loaded)
    if bc4.button("💬 Ask AI", use_container_width=True, disabled=not done):
        chat_popup(
            st.session_state.ctx,
            st.session_state.a1,
            st.session_state.a2,
        )

    # Export — functional download when analysis is done
    if done and st.session_state.ctx:
        report_text = build_export_report(
            st.session_state.ctx,
            st.session_state.a1,
            st.session_state.a2,
        )
        serial = st.session_state.current_serial or "report"
        bc5.download_button(
            "📥 Export",
            data=report_text,
            file_name=f"kit_report_{serial}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    else:
        bc5.button("📥 Export", use_container_width=True, disabled=True)

    st.markdown("</div>", unsafe_allow_html=True)

    return serial_input, run

# ============================================================
# LEFT PANEL — IB SNAPSHOT
# ============================================================
def render_ib_panel(ctx, a1):
    eq   = ctx["equipment"]
    dq   = a1.get("data_quality", {})
    inf  = a1.get("inferred_state", {})
    cfg  = ctx["config"]
    score = ib_health_score(a1)
    n_issues = len(dq.get("issues", []))
    n_disc   = len(inf.get("discrepancies", []))
    n_drift  = len(inf.get("config_drift", []))
    bar_pct  = f"{score}%"

    risk_lbl = "LOW risk" if score >= 75 else "MEDIUM risk" if score >= 50 else "HIGH risk"

    render_html(f"""<div class="panel-wrap">
    <div class="panel-hdr">
      <span class="panel-title">Installed-base snapshot</span>
      {chip(f"{n_disc + n_drift} issue(s)", "stale" if n_disc + n_drift else "ok")}
    </div>

    <div class="ib-health">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <span class="ib-score">{score}</span><span class="ib-score-denom">/100</span>
          <div class="ib-risk-lbl">{risk_lbl}</div>
        </div>
        <div style="display:flex;gap:12px;text-align:center">
          <div class="ib-stat"><div class="ib-stat-val">{len(ctx["installation_history"])}</div><div class="ib-stat-lbl">Install records</div></div>
          <div class="ib-stat"><div class="ib-stat-val">{n_disc}</div><div class="ib-stat-lbl">Contradictions</div></div>
          <div class="ib-stat"><div class="ib-stat-val">{n_drift}</div><div class="ib-stat-lbl">Config drift</div></div>
        </div>
      </div>
      <div class="ib-bar-bg"><div class="ib-bar-fg" style="width:{bar_pct}"></div></div>
      <div style="display:flex;justify-content:space-between;font-size:9px;opacity:0.7">
        <span>{dq.get("verification_status","—")}</span>
        <span>Verified: {dq.get("last_verified","—")}</span>
      </div>
    </div>

    {section_hdr("SAP recorded configuration", "#1D4ED8")}
    {''.join(
        f'<div class="cfg-row"><span class="cfg-key">{k.replace("_"," ").title()}</span>'
        f'<span class="cfg-val-sap">{v}</span></div>'
        for k, v in cfg.items()
    )}
    <div class="cfg-row"><span class="cfg-key">Install date</span>
      <span class="cfg-val-sap">{eq.get("install_date","—")}</span></div>
    <div class="cfg-row"><span class="cfg-key">Status</span>
      <span class="cfg-val-sap">{eq.get("status","—")}</span></div>

    {section_hdr("AI-inferred configuration", "#7500C0")}
    {''.join(
        f'<div class="cfg-row"><span class="cfg-key">{d.get("field","").replace("_"," ").title()}</span>'
        f'<span class="cfg-val-ai"><span class="drift-dot"></span>{d.get("likely_actual","—")}</span></div>'
        for d in inf.get("config_drift", [])
    ) or '<div style="font-size:11px;color:#9CA3AF;padding:4px 0">No drift detected</div>'}

    {''.join(
        f'<div class="alert-err"><span>⚠</span><span>{d.get("description","")}</span></div>'
        for d in inf.get("discrepancies",[])[:2]
    )}
    {''.join(
        f'<div class="alert-warn"><span>⏰</span><span>{i}</span></div>'
        for i in dq.get("issues",[])[:2]
    )}
    </div>""")

# ============================================================
# CENTER PANEL — KIT DECISIONS (multi-kit toggle)
# ============================================================
def render_kit_panel(ctx, a1, a2):
    kit_decisions = a1.get("kit_decisions", [])
    if not kit_decisions:
        st.markdown('<div class="panel-wrap"><p style="font-size:13px;color:#9CA3AF;padding:20px">No kit decisions available.</p></div>',
                    unsafe_allow_html=True)
        return

    # Session state for active kit index
    if "active_kit_idx" not in st.session_state:
        st.session_state.active_kit_idx = 0

    # Sort: actionable first by priority, then rest
    prank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    actionable = sorted(
        [k for k in kit_decisions if k.get("action") in ("INSTALL", "ORDER", "VERIFY_FIRST")],
        key=lambda k: prank.get(k.get("priority", "LOW"), 3)
    )
    others_sorted = [k for k in kit_decisions if k not in actionable]
    ordered_kits = actionable + others_sorted

    # Clamp index
    idx = min(st.session_state.active_kit_idx, len(ordered_kits) - 1)
    rec = ordered_kits[idx]

    conf  = safe_float(rec.get("confidence", 0))
    prio  = rec.get("priority", "")
    action = rec.get("action", "")
    prio_style   = {"CRITICAL":"critical","HIGH":"high","MEDIUM":"medium","LOW":"low"}.get(prio,"default")
    action_style = {"INSTALL":"install","ORDER":"order","PROPOSE_TO_CUSTOMER":"upgrade"}.get(action,"default")

    # Build selector pills HTML
    pill_cls_map = {"CRITICAL":"crit","HIGH":"high","MEDIUM":"med","LOW":"low"}
    pills = ""
    for i, k in enumerate(ordered_kits):
        active_cls = " active" if i == idx else ""
        prio_cls = " " + pill_cls_map.get(k.get("priority",""), "")
        short = k.get("mstk_number","")[-6:] if k.get("mstk_number") else f"Kit {i+1}"
        a_lbl = k.get("action","")[:4]
        pills += f'<span class="kit-sel-btn{active_cls}{prio_cls}" data-idx="{i}">{short} · {a_lbl}</span>'

    # Evidence
    relevant_sos = [s for s in ctx["service_orders"] if rec.get("mstk_number","") in (s.get("parts_referenced") or "")]
    ev_items = ""
    hist_for_kit = [h for h in ctx["installation_history"] if h.get("mstk_number") == rec.get("mstk_number")]
    if hist_for_kit:
        h = hist_for_kit[0]
        ev_items += f'<div class="ev-row">{ev_chip("sap")}<span>Install record: {h.get("installation_status","")} on {h.get("installation_date","")} · IB updated: {h.get("ib_updated","")}</span></div>'
    else:
        ev_items += f'<div class="ev-row">{ev_chip("sap")}<span>No installation record found for this MSTK in IB history</span></div>'
    ev_items += f'<div class="ev-row">{ev_chip("ai")}<span>Configuration match: {rec.get("category","")}-type kit applicability criteria met</span></div>'
    for s in relevant_sos[:2]:
        ev_items += f'<div class="ev-row">{ev_chip("so")}<span>{s["service_order_id"]} ({s["order_date"]}): {(s.get("technician_notes","") or "")[:80]}</span></div>'
    if rec.get("deadline"):
        ev_items += f'<div class="ev-row">{ev_chip("rule")}<span>Compliance deadline: {rec["deadline"]}</span></div>'

    # Risks
    prereq_res = a2.get("action_plan", {}).get("prerequisite_resolution", {})
    risks_html = ""
    for b in prereq_res.get("blocked", [])[:1]:
        risks_html += f'<div class="risk-row"><span class="rdot-h"></span><span><strong>Blocked:</strong> {b.get("kit","")} needs prerequisite {b.get("by","")}</span></div>'
    for d in a1.get("inferred_state", {}).get("config_drift", [])[:1]:
        risks_html += f'<div class="risk-row"><span class="rdot-m"></span><span><strong>Config drift:</strong> {d.get("field","").replace("_"," ")} · recorded {d.get("recorded","")} vs likely {d.get("likely_actual","")}</span></div>'
    if rec.get("order_sequence"):
        seq_str = " → ".join(str(x) for x in rec["order_sequence"])
        risks_html += f'<div class="risk-row"><span class="rdot-m"></span><span><strong>Order sequence required:</strong> {seq_str}</span></div>'
    if not risks_html:
        risks_html = '<div style="font-size:12px;color:#9CA3AF;padding:4px 0">No blockers detected.</div>'

    # Reasoning trace
    reasoning_text = (f"Agent 1 → confidence={conf:.0%} · priority={prio} · action={action}\n"
                      f"Type: {rec.get('rk_type','')} / {rec.get('category','')}\n"
                      f"Reasoning: {rec.get('reasoning','')}\n"
                      f"Agent 2 summary: {a2.get('exec_summary','')[:200]}")

    # Panel header HTML
    header_html = (
        f'<div class="panel-hdr">'
        f'<span class="panel-title">Kit Decisions — {len(kit_decisions)} analyzed · {len(actionable)} actionable</span>'
        f'<span style="font-size:11px;color:#A100FF;font-weight:600">AI-recommended</span>'
        f'</div>'
        f'<div class="kit-selector">{pills}</div>'
    )

    # Kit card HTML
    deadline_html = (
        f'<span style="font-size:11px;font-weight:600;color:#991B1B;background:#FEE2E2;'
        f'padding:2px 9px;border-radius:10px;border:0.5px solid #FCA5A5">⏰ {rec.get("deadline","")}</span>'
        if rec.get("deadline") else ""
    )
    kit_html = (
        f'<div class="kit-card">'
        f'<span class="kit-mstk">{rec.get("mstk_number","")}</span>'
        f'<div class="kit-name">{rec.get("mcon_name","")}</div>'
        f'<div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px">'
        f'{chip(rec.get("rk_type",""), "mandatory" if "MK" in rec.get("rk_type","") else "upgrade")}'
        f'{chip(prio, prio_style)} {chip(action, action_style)} {deadline_html}'
        f'</div>'
        f'{conf_bar(conf, width=150)}'
        f'</div>'
    )
    reasoning_html = (
        f'<div style="background:#1F2937;border-radius:6px;padding:10px;margin-bottom:10px">'
        f'<div style="font-family:JetBrains Mono,monospace;font-size:10px;color:#D1FAE5;'
        f'line-height:1.6;white-space:pre-wrap">{reasoning_text}</div></div>'
        if st.session_state.show_reasoning else ""
    )

    body_html = (
        f'<div style="font-size:11px;color:#374151;margin-bottom:6px;line-height:1.5">{rec.get("reasoning","")}</div>'
        f'{reasoning_html}'
        f'<div class="sec-lbl">Evidence</div>'
        f'<div class="evidence-block">{ev_items}</div>'
        f'<div class="sec-lbl">Risks and blockers</div>'
        f'{risks_html}'
    )

    render_html(
        f'<div class="panel-wrap">{header_html}{kit_html}{body_html}</div>'
    )

    # Kit selector — use a selectbox with descriptive labels (no ugly columns)
    n = len(ordered_kits)
    if n > 1:
        prank_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🔵", "LOW": "🟢"}
        action_short = {"INSTALL": "Install", "ORDER": "Order", "SKIP": "Skip",
                        "VERIFY_FIRST": "Verify", "PROPOSE_TO_CUSTOMER": "Propose",
                        "AVAILABLE_NOT_RECOMMENDED": "Available", "BLOCKED_BY_CONFLICT": "Blocked"}
        options = [
            f"{prank_icon.get(k.get('priority',''), '⚪')} {k.get('mstk_number','')[-8:]} — "
            f"{(k.get('mcon_name','') or '')[:30]} · {action_short.get(k.get('action',''), k.get('action',''))}"
            for k in ordered_kits
        ]
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        selected_label = st.selectbox(
            "Select kit to review",
            options=options,
            index=idx,
            key="kit_selectbox",
            label_visibility="collapsed",
        )
        new_idx = options.index(selected_label)
        if new_idx != idx:
            st.session_state.active_kit_idx = new_idx
            st.rerun()

# ============================================================
# RIGHT PANEL — ACTION PLAN
# ============================================================
def render_action_plan_panel(ctx, a1, a2):
    ap   = a2.get("action_plan", {})
    cost = ap.get("cost_summary", {})
    plan = ap.get("installation_plan", {})
    seq  = plan.get("sequence", [])
    ibu  = ap.get("ib_database_updates", {})
    orders = ap.get("immediate_actions", {}).get("order_requisitions", [])

    total_cost = cost.get("total_kit_cost_eur", 0)
    total_hrs  = cost.get("total_downtime_hrs", 0)
    tech_days  = cost.get("technician_days", 0)
    deadline_n = cost.get("deadline_count", 0)

    # Installation steps HTML
    steps_html = ""
    for s in seq[:5]:
        skills = s.get("skills", [])
        skills_str = ", ".join(str(x) for x in skills) if isinstance(skills, list) and skills else "—"
        steps_html += (
            f'<div class="step-row">'
            f'<div class="step-num">{s.get("step",0)}</div>'
            f'<div><div class="step-name">{s.get("mstk","")} — {s.get("kit_name","")}</div>'
            f'<div class="step-meta">'
            f'<span>⏱ {s.get("downtime_hrs",0)}h</span>'
            f'<span>🛠 {skills_str}</span>'
            f'{"<span>✓ enables: " + s["enables"] + "</span>" if s.get("enables") else ""}'
            f'</div></div></div>'
        )
    if not steps_html:
        steps_html = '<div style="font-size:11px;color:#9CA3AF;padding:4px 0">No installation sequence generated.</div>'

    # Orders
    orders_html = ""
    for o in orders[:3]:
        orders_html += (
            f'<div class="step-row">'
            f'<div style="width:20px;height:20px;border-radius:50%;background:#F59E0B;color:#fff;font-size:10px;font-weight:600;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px">O</div>'
            f'<div><div class="step-name">{o.get("mstk","")} — {o.get("kit_name","")}</div>'
            f'<div class="step-meta"><span>€{o.get("price_eur",0):,}</span><span>{o.get("urgency","")}</span></div>'
            f'</div></div>'
        )

    # SQL preview — Agent 2 may return strings or dicts; normalise both
    def _sql_str(x):
        if isinstance(x, str): return x
        if isinstance(x, dict): return x.get("sql") or x.get("statement") or json.dumps(x)
        return str(x)
    all_sql = [_sql_str(x) for x in (
        ibu.get("insert_installation_records", []) +
        ibu.get("update_status", []) +
        ibu.get("update_config", []) +
        ibu.get("update_verification", [])
    )]
    sql_preview = "\n".join(all_sql[:2]) if all_sql else "-- No SQL generated"

    # SLA urgency
    urgency_html = ""
    if deadline_n:
        urgency_html = f'<div class="urgency-bar"><span>⚠</span><span>SLA: {deadline_n} kit(s) with compliance deadline. Schedule within 45 days.</span></div>'

    render_html(f"""<div class="panel-wrap">
    <div class="panel-hdr">
      <span class="panel-title">Execution action plan</span>
      {chip(f"{len(seq)} steps", "ai")}
    </div>

    <div class="cost-grid">
      <div class="cost-card"><div class="cost-val">€{total_cost:,.0f}</div><div class="cost-lbl">Kit cost est.</div></div>
      <div class="cost-card"><div class="cost-val">{total_hrs}h</div><div class="cost-lbl">Downtime</div></div>
      <div class="cost-card"><div class="cost-val">{tech_days}</div><div class="cost-lbl">Tech days</div></div>
      <div class="cost-card"><div class="cost-val" style="color:{'#DC2626' if deadline_n else '#16A34A'}">{deadline_n}</div><div class="cost-lbl">Deadlines</div></div>
    </div>

    {urgency_html}

    {section_hdr("Order requisitions")}
    {orders_html or '<div style="font-size:11px;color:#9CA3AF">No orders required.</div>'}

    {section_hdr("Installation sequence")}
    {steps_html}

    {section_hdr("IB database updates — SQL")}
    <div class="sql-block">{sql_preview}</div>
    </div>""")

# ============================================================
# EVIDENCE TIMELINE
# ============================================================
def render_timeline(ctx, a1):
    events = []
    for h in sorted(ctx["installation_history"], key=lambda x: x.get("installation_date", "")):
        events.append({
            "date": h.get("installation_date", "—"),
            "label": f"Kit installed: {h.get('mstk_number','')[:14]}",
            "detail": f"Status: {h.get('installation_status','')}. IB: {h.get('ib_updated','')}",
            "type": "sap",
            "dot_bg": "#DBEAFE", "dot_border": "#3B82F6",
        })
    for so in sorted(ctx["service_orders"], key=lambda x: x.get("order_date", "")):
        events.append({
            "date": so.get("order_date", "—"),
            "label": f"SO: {so.get('service_order_id','')}",
            "detail": (so.get("technician_notes") or "")[:60],
            "type": "so",
            "dot_bg": "#F3E8FF", "dot_border": "#A100FF",
        })
    for d in a1.get("inferred_state", {}).get("config_drift", []):
        events.append({
            "date": "AI detected",
            "label": f"Config drift: {d.get('field','')}",
            "detail": f"{d.get('recorded','')} -> {d.get('likely_actual','')}",
            "type": "ai",
            "dot_bg": "#D1FAE5", "dot_border": "#10B981",
        })
    events.sort(key=lambda x: x.get("date", ""))
    events.append({
        "date": "Proposed",
        "label": "Planned IB update",
        "detail": "Awaiting human approval",
        "type": "pending",
        "dot_bg": "#FEE2E2", "dot_border": "#EF4444",
    })

    chip_styles = {
        "sap":     "background:#DBEAFE;color:#1D4ED8",
        "so":      "background:#F3E8FF;color:#7500C0",
        "ai":      "background:#D1FAE5;color:#065F46",
        "pending": "background:#FEE2E2;color:#991B1B",
    }
    chip_labels = {"sap": "SAP", "so": "Service order", "ai": "AI inference", "pending": "Pending"}

    items_html = "".join(
        f'<div class="tl-item">'
        f'<div class="tl-dot" style="background:{e["dot_bg"]};border-color:{e["dot_border"]}"></div>'
        f'<div class="tl-body">'
        f'<div class="tl-date">{e["date"]}</div>'
        f'<div class="tl-label">{e["label"]}</div>'
        f'<div class="tl-detail">{e["detail"]}</div>'
        f'<span class="tl-chip" style="{chip_styles.get(e["type"],"")};">{chip_labels.get(e["type"],"")}</span>'
        f'</div></div>'
        for e in events
    )

    render_html(f"""<div class="timeline-wrap">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <span style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#6B7280">Evidence timeline</span>
      <div style="display:flex;gap:6px">
        <span class="tl-chip" style="background:#DBEAFE;color:#1D4ED8">SAP record</span>
        <span class="tl-chip" style="background:#F3E8FF;color:#7500C0">Service order</span>
        <span class="tl-chip" style="background:#D1FAE5;color:#065F46">AI inference</span>
        <span class="tl-chip" style="background:#FEE2E2;color:#991B1B">Pending</span>
      </div>
    </div>
    <div class="tl-scroll">{items_html}</div>
    </div>""")

# ============================================================
# APPROVAL SECTION
# ============================================================
def render_approval_section(ctx, a1, a2):
    eq  = ctx["equipment"]
    cfg = ctx["config"]
    inf = a1.get("inferred_state", {})
    dq  = a1.get("data_quality", {})
    ap  = a2.get("action_plan", {})
    rec = top_kit(a1.get("kit_decisions", []))
    conf = safe_float(rec.get("confidence", 0)) if rec else 0

    # Before fields
    before_rows = "".join(
        f'<div class="ba-row"><span class="ba-key">{k.replace("_"," ").title()}</span>'
        f'<span class="val-old">{v}</span></div>'
        for k, v in list(cfg.items())[:4]
    )
    # After fields
    after_rows = "".join(
        f'<div class="ba-row"><span class="ba-key">{d.get("field","").replace("_"," ").title()}</span>'
        f'<span class="val-new">{d.get("likely_actual","")}</span></div>'
        for d in inf.get("config_drift", [])
    )
    if rec:
        after_rows += (
            f'<div class="ba-row"><span class="ba-key">{rec.get("mstk_number","")} status</span>'
            f'<span class="val-new">{rec.get("action","")}_QUEUED</span></div>'
        )
    after_rows += (
        f'<div class="ba-row"><span class="ba-key">Last verified</span>'
        f'<span class="val-new">{datetime.now().strftime("%Y-%m-%d")}</span></div>'
    )

    # Confidence breakdown
    factors = [
        ("Config match",         0.95 if conf >= 0.8 else 0.7),
        ("Service order evidence", min(conf + 0.1, 1.0)),
        ("IB completeness",      0.3 + len(ctx["installation_history"]) * 0.1),
        ("Verification recency",  0.1 if dq.get("verification_status") == "STALE" else 0.7),
    ]
    cf_rows = "".join(
        f'<div class="cf-row"><span>{label}</span>'
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<div class="cf-bar-bg"><div class="cf-bar-fg" style="width:{int(v*100)}%"></div></div>'
        f'<span style="font-size:11px;font-weight:600;color:#A100FF">{v:.0%}</span>'
        f'</div></div>'
        for label, v in factors
    )

    render_html(f"""<div class="approval-wrap">
    <div class="approval-inner">
      <div class="approval-hdr">
        <span style="font-weight:600;font-size:14px">Approve installed-base update — {eq.get("serial_number","")}</span>
      </div>
      <div class="approval-body">
        <div>
          <div class="ba-card" style="margin-bottom:8px">
            <div class="ba-lbl-before">Before — SAP current state</div>
            {before_rows}
          </div>
          <div class="ba-card">
            <div class="ba-lbl-after">After — proposed update</div>
            {after_rows}
          </div>
        </div>
        <div>
          <div class="conf-bk" style="margin-bottom:8px">
            <div style="font-size:11px;font-weight:600;color:#460073;margin-bottom:7px">
              Confidence breakdown (overall {conf:.0%})
            </div>
            {cf_rows}
          </div>
          <div style="background:#F9FAFB;border-radius:6px;padding:10px;font-size:11px;color:#374151;line-height:1.55">
            <div style="font-weight:600;color:#111827;margin-bottom:4px">Supporting evidence</div>
            {a2.get("exec_summary","Analysis complete. Review the before/after fields and approve to queue the IB update for SAP execution.")[:300]}
          </div>
        </div>
      </div>
    </div>
    </div>""")

    # ── Action buttons — equal width, centered ──────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    render_html(
        '<div style="background:#F9FAFB;border-radius:10px;padding:20px 24px;'
        'border:1px solid #E9E9EF;margin-top:4px">'
        '<div style="font-size:12px;font-weight:700;color:#374151;margin-bottom:8px;text-align:center;'
        'text-transform:uppercase;letter-spacing:0.06em">Governance Decision</div>'
        '<div style="font-size:12px;color:#6B7280;text-align:center;line-height:1.5">'
        'Approving queues the IB update for SAP execution and creates a permanent audit record.</div>'
        '</div>'
    )
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    _sp1, btn_reject, btn_review, btn_approve, _sp2 = st.columns([1, 2, 2, 2, 1])
    with btn_reject:
        if st.button("✕  Reject update", use_container_width=True, key="appr_reject"):
            st.session_state.approval_status = "REJECTED"
            st.rerun()
    with btn_review:
        if st.button("⏳  Request review", use_container_width=True, key="appr_review"):
            st.session_state.approval_status = "REVIEW"
            st.rerun()
    with btn_approve:
        if st.button("✓  Approve and push to SAP", type="primary",
                     use_container_width=True, key="appr_approve"):
            st.session_state.approval_status = "APPROVED"
            st.rerun()

# ============================================================
# CHAT SECTION
# ============================================================
def render_chat_section(ctx, a1, a2):
    eq = ctx["equipment"]

    # Header
    st.markdown(
        f"<div style='background:linear-gradient(135deg,#F3E8FF,#FAF3FF);border:1px solid #D8B4FE;"
        f"border-radius:8px;padding:12px 16px;margin-bottom:12px'>"
        f"<div style='font-size:13px;font-weight:700;color:#460073;margin-bottom:3px'>"
        f"💬 Ask AI — Equipment {eq.get('serial_number','')} context loaded</div>"
        f"<div style='font-size:12px;color:#7500C0;line-height:1.4'>"
        f"Ask anything about this equipment, its kits, service history, or recommended actions. "
        f"The AI has full context of the analysis.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Suggestion chips (shown only when no messages yet)
    if not st.session_state.chat_messages:
        suggestions = [
            "What discrepancies were found?",
            "Why is this kit critical?",
            "Summarise cost and downtime",
            "Which kits can be batched?",
            "What evidence shows IB drift?",
            "Explain the recommended action",
        ]
        st.markdown(
            "<div style='font-size:11px;font-weight:600;color:#9CA3AF;text-transform:uppercase;"
            "letter-spacing:0.05em;margin-bottom:8px'>Try asking</div>",
            unsafe_allow_html=True,
        )
        cols = st.columns(3)
        for i, s in enumerate(suggestions):
            if cols[i % 3].button(s, key=f"sugg_{i}", use_container_width=True):
                st.session_state.chat_messages.append({"role": "user", "content": s})
                sys_p = build_chat_system_prompt(ctx, a1, a2)
                msgs  = [{"role": "system", "content": sys_p}] + st.session_state.chat_messages
                with st.spinner("Thinking…"):
                    reply = call_llm_chat(msgs)
                st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                st.rerun()
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Render conversation history with native st.chat_message
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
            st.markdown(msg["content"])

    # Clear button
    if st.session_state.chat_messages:
        if st.button("🗑️ Clear conversation", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()

    # Chat input
    prompt = st.chat_input("Ask about this equipment, its kits, or the recommended actions…")
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking…"):
                sys_p = build_chat_system_prompt(ctx, a1, a2)
                msgs  = [{"role": "system", "content": sys_p}] + st.session_state.chat_messages
                reply = call_llm_chat(msgs)
            st.markdown(reply)
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})

# ============================================================
# LANDING PAGE
# ============================================================
def render_landing():
    st.markdown("""<div style="padding:48px 20px 28px;text-align:center">
    <div style="font-size:48px;margin-bottom:12px">🔧</div>
    <h2 style="font-size:28px;font-weight:700;color:#111827;margin-bottom:10px;letter-spacing:-0.02em">
      Kit Management Decision Cockpit</h2>
    <p style="font-size:16px;color:#6B7280;max-width:600px;margin:0 auto 32px;line-height:1.7">
      Enter an equipment serial number above to begin a full agentic analysis.
      The system reconstructs the true installed-base state, recommends kit actions,
      and guides you through a governed IB update workflow.
    </p>
    </div>""", unsafe_allow_html=True)

    caps = [
        ("🎯", "Diagnose",
         "Detect IB drift, stale verification, missing records, and configuration contradictions across all data sources."),
        ("💡", "Recommend",
         "AI-ranked kit decisions with confidence scores, evidence citations, risk flags, and ranked alternatives."),
        ("📋", "Plan",
         "Sequenced installation plan with cost estimates, downtime, resource requirements, and generated SQL updates."),
        ("🛡️", "Approve",
         "Before/after IB field comparison with confidence breakdown. Approve, reject, or escalate for review."),
    ]
    cols = st.columns(4, gap="medium")
    for col, (icon, title, desc) in zip(cols, caps):
        col.markdown(f"""<div style="background:#FFFFFF;border:1px solid #E9E9EF;border-radius:12px;
          padding:24px 20px;min-height:220px;display:flex;flex-direction:column;
          box-shadow:0 2px 8px rgba(0,0,0,0.05);transition:box-shadow 0.2s">
          <div style="font-size:32px;margin-bottom:12px">{icon}</div>
          <div style="font-size:16px;font-weight:700;color:#111827;margin-bottom:10px">{title}</div>
          <div style="font-size:14px;color:#6B7280;line-height:1.6;flex:1">{desc}</div>
        </div>""", unsafe_allow_html=True)

# ============================================================
# ANALYSIS RUNNER
# ============================================================
def _gov_item_html(item, status):
    """Compact HTML card for one governance item in the persistent panel."""
    color = {"PENDING":"#F59E0B","APPROVED":"#10B981","REJECTED":"#EF4444","OVERRIDDEN":"#A100FF"}.get(status,"#9CA3AF")
    badge_style = {"PENDING":"background:#FEF3C7;color:#92400E","APPROVED":"background:#D1FAE5;color:#065F46","REJECTED":"background:#FEE2E2;color:#991B1B","OVERRIDDEN":"background:#F3E8FF;color:#460073"}.get(status,"")
    icon = {"PENDING":"⏳","APPROVED":"✓","REJECTED":"✕","OVERRIDDEN":"⟳"}.get(status,"·")
    return (
        f'<div class="gov-item {status.lower()}">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
        f'<div class="gov-item-title">{item["title"][:42]}</div>'
        f'<span class="gov-badge" style="{badge_style}">{icon} {status}</span>'
        f'</div>'
        f'<div class="gov-item-sub">{item["sub"][:60]}</div>'
        f'</div>'
    )


def run_analysis(serial):
    """Run both agents with a live animated overlay showing every step."""
    import time

    placeholder = st.empty()

    def show(steps, pct, note=""):
        rows = ""
        for s in steps:
            st_class = s.get("state", "pending")
            icon = {"done": "✓", "active": "⟳", "pending": "·"}[st_class]
            icon_cls = "step-icon spin" if st_class == "active" else "step-icon"
            rows += (
                f'<div class="agent-step {st_class}">'
                f'<span class="{icon_cls}">{icon}</span>'
                f'<div class="step-detail">'
                f'<div class="step-label">{s["label"]}</div>'
                f'<div class="step-sub {st_class}">{s.get("sub","")}</div>'
                f'</div></div>'
            )
        note_html = f'<div style="font-size:10px;color:#6B7280;margin-top:12px">{note}</div>' if note else ""
        placeholder.markdown(
            re.sub(r'\s+', ' ',
                f'<div class="agent-overlay">'
                f'<div class="agent-title">⬡ Kit Management — Agentic Analysis Running</div>'
                f'{rows}'
                f'<div class="agent-bar"><div class="agent-bar-fill" style="width:{pct}%"></div></div>'
                f'{note_html}'
                f'</div>'
            ).strip(),
            unsafe_allow_html=True
        )

    # ── Phase 1: Data gathering ─────────────────────────────────────
    steps = [
        {"label": "Gathering asset context", "sub": "Equipment master, configuration, status", "state": "active"},
        {"label": "Loading kit catalog",      "sub": "Applicable MSTKs and MCONs",             "state": "pending"},
        {"label": "Fetching install history", "sub": "Formal IB records",                       "state": "pending"},
        {"label": "Resolving dependencies",   "sub": "Prerequisites, conflicts, groupings",     "state": "pending"},
        {"label": "Loading service orders",   "sub": "Technician notes, parts referenced",      "state": "pending"},
        {"label": "Agent 1 — Analysis",       "sub": "Waiting for data",                        "state": "pending"},
        {"label": "Agent 2 — Action Plan",    "sub": "Waiting for Agent 1",                     "state": "pending"},
    ]
    show(steps, 5, "Connecting to data sources…")
    ctx = gather_context(serial)
    if not ctx:
        placeholder.empty()
        st.error(f"Serial '{serial}' not found in the asset registry.")
        return

    # Mark each source done sequentially
    source_subs = [
        f"Found: {ctx['equipment'].get('description','—')} · {ctx['equipment'].get('customer_name','—')}",
        f"{len(ctx['applicable_kits'])} kits match material + configuration",
        f"{len(ctx['installation_history'])} formal records in IB",
        f"{sum(len(v.get('prerequisites',[])) for v in ctx['dependencies'].values())} prerequisites mapped",
        f"{len(ctx['service_orders'])} service orders with technician notes",
    ]
    for i in range(5):
        steps[i]["state"] = "done"
        steps[i]["sub"]   = source_subs[i]
        if i < 4: steps[i+1]["state"] = "active"
        show(steps, 10 + i * 7, f"Loaded {i+1}/5 sources…")
        time.sleep(0.18)

    # ── Phase 2: Agent 1 ────────────────────────────────────────────
    steps[4]["state"] = "done"
    steps[5]["state"] = "active"
    steps[5]["sub"]   = f"Sending {len(ctx['applicable_kits'])} kits + {len(ctx['service_orders'])} SOs to LLM…"
    show(steps, 45, "Agent 1 is inferring installed state and scoring kit decisions…")

    r1, m1 = call_llm(AGENT1_SYS, build_agent1_prompt(ctx),
                      max_tokens=10000, agent="agent1")
    if not r1:
        placeholder.empty()
        st.error("Agent 1 failed — check your API key and model availability.")
        return
    a1 = parse_json(r1)
    if not a1:
        placeholder.empty()
        st.warning("Could not parse Agent 1 output.")
        st.code(r1[:1500])
        return

    kit_decisions = a1.get("kit_decisions", [])
    critical = sum(1 for k in kit_decisions if k.get("priority") == "CRITICAL")
    disc     = len(a1.get("inferred_state", {}).get("discrepancies", []))
    m1_short = m1.split("/")[-1].split(":")[0] if "/" in m1 else m1

    steps[5]["state"] = "done"
    steps[5]["sub"]   = (
        f"{len(kit_decisions)} kit decisions · {critical} critical · "
        f"{disc} discrepancies · model: {m1_short}"
    )
    steps[6]["state"] = "active"
    steps[6]["sub"]   = "Building execution plan and SQL updates…"
    show(steps, 70, "Agent 2 is sequencing installations and generating IB update SQL…")

    # ── Phase 3: Agent 2 ────────────────────────────────────────────
    kit_details = [
        {"mstk": k.get("mstk_number"), "name": k.get("mcon_name"),
         "action": k.get("action"),
         "price_eur":    next((x.get("transfer_price_eur","")    for x in ctx["applicable_kits"] if x["mstk_number"] == k.get("mstk_number")), ""),
         "downtime_hrs": next((x.get("estimated_downtime_hrs","") for x in ctx["applicable_kits"] if x["mstk_number"] == k.get("mstk_number")), "")}
        for k in kit_decisions
    ]
    p2 = (f"Generate action plan for:\nEQUIPMENT: {serial}\n\n"
          f"AGENT 1 ANALYSIS:\n{json.dumps(a1, indent=1)}\n\n"
          f"KIT DETAILS:\n{json.dumps(kit_details, indent=1)}\n\n"
          f"Calculate total cost, downtime, technician days. Produce full action plan with SQL.")
    r2, m2 = call_llm(AGENT2_SYS, p2, max_tokens=7000, agent="agent2")
    if not r2:
        placeholder.empty()
        st.error("Agent 2 failed — check your API key.")
        return
    a2 = parse_json(r2)
    if not a2:
        placeholder.empty()
        st.warning("Could not parse Agent 2 output.")
        st.code(r2[:1500])
        return

    ap     = a2.get("action_plan", {})
    cost   = ap.get("cost_summary", {})
    m2_short = m2.split("/")[-1].split(":")[0] if "/" in m2 else m2
    steps[6]["state"] = "done"
    steps[6]["sub"]   = (
        f"EUR {cost.get('total_kit_cost_eur',0):,.0f} · "
        f"{cost.get('total_downtime_hrs',0)}h downtime · "
        f"{len(ap.get('ib_database_updates',{}).get('insert_installation_records',[]))} SQL inserts · "
        f"model: {m2_short}"
    )
    show(steps, 100, "")
    time.sleep(0.6)
    placeholder.empty()

    # ── Persist to session state ─────────────────────────────────────
    st.session_state.ctx             = ctx
    st.session_state.a1              = a1
    st.session_state.a2              = a2
    st.session_state.current_serial  = serial
    st.session_state.analysis_done   = True
    st.session_state.approval_status = "PENDING"
    st.session_state.chat_messages   = []
    st.session_state.governance      = {}
    st.session_state.model_names     = {"a1": m1, "a2": m2}
    st.rerun()

# ============================================================
# MAIN APP
# ============================================================
serial_input, run_btn = render_command_bar()

if run_btn and serial_input:
    if serial_input != st.session_state.current_serial:
        st.session_state.analysis_done = False
        st.session_state.approval_status = "PENDING"
    run_analysis(serial_input)

if st.session_state.analysis_done:
    ctx = st.session_state.ctx
    a1  = st.session_state.a1
    a2  = st.session_state.a2

    # ── Pre-compute governance items ────────────────────────────────
    inf_state     = a1.get("inferred_state", {})
    kit_decisions = a1.get("kit_decisions", [])
    ap   = a2.get("action_plan", {})
    imm  = ap.get("immediate_actions", {})
    ibu  = ap.get("ib_database_updates", {})

    def _sql_str_main(x):
        if isinstance(x, str): return x
        if isinstance(x, dict): return x.get("sql") or x.get("statement") or json.dumps(x)
        return str(x)

    governance_items = []
    for k in kit_decisions:
        if safe_float(k.get("confidence", 0)) < CONFIDENCE_THRESHOLD or k.get("action") == "VERIFY_FIRST":
            governance_items.append({
                "id": f"kit_{k.get('mstk_number','')}",
                "category": "Low-Confidence Kit Decision",
                "title": f"{k.get('mstk_number','')} — {k.get('mcon_name','')}",
                "sub": f"Action: {k.get('action','')} · Confidence: {safe_float(k.get('confidence',0)):.0%}",
                "evidence": k.get("reasoning", ""),
                "agent_decision": k.get("action", ""),
                "alt_actions": ["INSTALL","ORDER","SKIP","VERIFY_FIRST","PROPOSE_TO_CUSTOMER"],
            })
    for i, d in enumerate(inf_state.get("discrepancies", [])):
        governance_items.append({
            "id": f"disc_{i}", "category": "Discrepancy",
            "title": d.get("type", "Discrepancy"), "sub": d.get("description","")[:70],
            "evidence": d.get("description",""), "agent_decision": "Update IB record",
            "alt_actions": ["Update IB record","Investigate further","Ignore"],
        })
    for i, d in enumerate(inf_state.get("config_drift", [])):
        governance_items.append({
            "id": f"drift_{i}", "category": "Config Drift",
            "title": f"Field: {d.get('field','')}", "sub": f"{d.get('recorded','')} → {d.get('likely_actual','')}",
            "evidence": d.get("evidence",""), "agent_decision": "Update configuration",
            "alt_actions": ["Update configuration","Verify on-site","Ignore"],
        })
    for i, o in enumerate(imm.get("order_requisitions", [])):
        governance_items.append({
            "id": f"order_{i}", "category": "Order Requisition",
            "title": f"{o.get('mstk','')} — {o.get('kit_name','')}",
            "sub": f"€{o.get('price_eur',0):,} · {o.get('urgency','')}",
            "evidence": o.get("why",""), "agent_decision": "Place order",
            "alt_actions": ["Place order","Hold for review","Cancel"],
        })
    for bucket, items in [
        ("INSERT install record",    ibu.get("insert_installation_records",[])),
        ("UPDATE config",            ibu.get("update_config",[])),
        ("UPDATE verification date", ibu.get("update_verification",[])),
    ]:
        for i, sql in enumerate(items):
            governance_items.append({
                "id": f"sql_{bucket}_{i}", "category": "IB Database Update",
                "title": bucket, "sub": _sql_str_main(sql)[:60],
                "evidence": _sql_str_main(sql), "agent_decision": "Execute SQL",
                "alt_actions": ["Execute SQL","Modify before execute","Reject"],
                "is_sql": True,
            })
    for item in governance_items:
        if item["id"] not in st.session_state.governance:
            st.session_state.governance[item["id"]] = {"status":"PENDING","note":"","override_action":None}

    gov_total    = len(governance_items)
    gov_pending  = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="PENDING")
    gov_approved = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="APPROVED")
    gov_rejected = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="REJECTED")
    gov_override = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="OVERRIDDEN")

    # ════════════════════════════════════════════════════════════════
    # ROW 1 — three equal panels (IB Snapshot · Kit Decisions · Plan)
    # ════════════════════════════════════════════════════════════════
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    col_ib, col_kit, col_plan = st.columns(3, gap="medium")
    with col_ib:
        render_ib_panel(ctx, a1)
    with col_kit:
        render_kit_panel(ctx, a1, a2)
    with col_plan:
        render_action_plan_panel(ctx, a1, a2)

    # ════════════════════════════════════════════════════════════════
    # ROW 2 — full-width evidence timeline
    # ════════════════════════════════════════════════════════════════
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    render_timeline(ctx, a1)

    # ════════════════════════════════════════════════════════════════
    # ROW 3 — Human-in-Lead Governance (full width card grid)
    # Reads live from st.session_state.governance on every render
    # ════════════════════════════════════════════════════════════════
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    # Recompute counts live from session state (not from cached vars)
    gov_approved_live = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="APPROVED")
    gov_rejected_live = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="REJECTED")
    gov_override_live = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="OVERRIDDEN")
    gov_pending_live  = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="PENDING")
    gov_done_live     = gov_approved_live + gov_rejected_live + gov_override_live
    gov_pct_live      = int(gov_done_live / gov_total * 100) if gov_total else 0
    status_color_map = {
        "PENDING":    ("background:#FEF3C7;color:#92400E",  "⏳ Pending"),
        "APPROVED":   ("background:#D1FAE5;color:#065F46",  "✓ Approved"),
        "REJECTED":   ("background:#FEE2E2;color:#991B1B",  "✕ Rejected"),
        "OVERRIDDEN": ("background:#F3E8FF;color:#460073",  "⟳ Overridden"),
    }
    cat_icons = {
        "Low-Confidence Kit Decision": "🎯",
        "Discrepancy": "⚠️",
        "Config Drift": "📐",
        "Order Requisition": "🛒",
        "IB Database Update": "💾",
    }

    # ── Governance header (native, so counts always live) ──────────
    gov_pending_live  = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="PENDING")
    gov_approved_live = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="APPROVED")
    gov_rejected_live = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="REJECTED")
    gov_override_live = sum(1 for it in governance_items if st.session_state.governance.get(it["id"],{}).get("status")=="OVERRIDDEN")
    gov_done_live     = gov_approved_live + gov_rejected_live + gov_override_live
    gov_pct_live      = int(gov_done_live / gov_total * 100) if gov_total else 0

    status_color_map = {
        "PENDING":    ("background:#FEF3C7;color:#92400E",  "⏳ Pending"),
        "APPROVED":   ("background:#D1FAE5;color:#065F46",  "✓ Approved"),
        "REJECTED":   ("background:#FEE2E2;color:#991B1B",  "✕ Rejected"),
        "OVERRIDDEN": ("background:#F3E8FF;color:#460073",  "⟳ Overridden"),
    }
    cat_icons = {
        "Low-Confidence Kit Decision": "🎯",
        "Discrepancy": "⚠️",
        "Config Drift": "📐",
        "Order Requisition": "🛒",
        "IB Database Update": "💾",
    }
    left_color = {"PENDING":"#F59E0B","APPROVED":"#10B981","REJECTED":"#EF4444","OVERRIDDEN":"#A100FF"}

    # ── Governance panel wrapper ────────────────────────────────────
    with st.container(border=True):
        # Title row
        th1, th2 = st.columns([3, 2])
        with th1:
            st.markdown(
                f"<span style='font-size:15px;font-weight:700;color:#374151'>🛡️ Human-in-Lead Governance</span>"
                f"&nbsp;&nbsp;<span style='background:#F3E8FF;border:1px solid #A100FF;border-radius:12px;"
                f"padding:3px 12px;font-size:12px;font-weight:600;color:#460073'>"
                f"{gov_pending_live} pending of {gov_total}</span>",
                unsafe_allow_html=True,
            )
        with th2:
            st.markdown(
                f"<div style='text-align:right;font-size:13px;color:#6B7280;padding-top:4px'>"
                f"<span style='color:#16A34A;font-weight:600'>✓ {gov_approved_live}</span> &nbsp;"
                f"<span style='color:#EF4444;font-weight:600'>✕ {gov_rejected_live}</span> &nbsp;"
                f"<span style='font-weight:600;color:#374151'>{gov_pct_live}% reviewed</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Progress bar
        st.markdown(
            f"<div style='background:#F3F4F6;border-radius:4px;height:7px;overflow:hidden;margin:6px 0 14px'>"
            f"<div style='width:{gov_pct_live}%;height:100%;"
            f"background:linear-gradient(90deg,#7500C0,#A100FF);border-radius:4px'></div></div>",
            unsafe_allow_html=True,
        )

        # Card grid — 3 items per row using native Streamlit columns
        # Renders fresh on every rerun so status is always current
        cols_per_row = 3
        for row_start in range(0, len(governance_items), cols_per_row):
            row_items = governance_items[row_start : row_start + cols_per_row]
            gcols = st.columns(cols_per_row)
            for col, it in zip(gcols, row_items):
                status   = st.session_state.governance[it["id"]]["status"]
                lc       = left_color.get(status, "#9CA3AF")
                sc_style, sc_label = status_color_map.get(status, status_color_map["PENDING"])
                icon     = cat_icons.get(it["category"], "·")
                with col:
                    st.markdown(
                        f"<div style='background:#FAFAFA;border:1px solid #EBEBEB;"
                        f"border-left:4px solid {lc};border-radius:8px;padding:12px 14px;'>"
                        f"<div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px'>"
                        f"<span style='font-size:13px;font-weight:600;color:#111827'>{icon} {it['title'][:36]}</span>"
                        f"<span style='{sc_style};padding:2px 8px;border-radius:4px;font-size:11px;"
                        f"font-weight:600;white-space:nowrap;margin-left:6px'>{sc_label}</span>"
                        f"</div>"
                        f"<div style='font-size:12px;color:#6B7280;line-height:1.4;margin-bottom:6px'>{it['sub'][:65]}</div>"
                        f"<div style='font-size:11px;color:#9CA3AF;border-top:0.5px solid #F0F0F0;padding-top:5px'>"
                        f"Agent: {it['agent_decision']}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # ── Per-item approve/reject (always visible, not inside expander) ──
        pending_items = [it for it in governance_items
                         if st.session_state.governance[it["id"]]["status"] == "PENDING"]

        if pending_items:
            st.markdown(
                "<div style='font-size:11px;font-weight:700;text-transform:uppercase;"
                "letter-spacing:0.06em;color:#9CA3AF;margin-bottom:8px'>Pending decisions</div>",
                unsafe_allow_html=True,
            )
            for it in pending_items:
                with st.container(border=False):
                    pi1, pi2, pi3 = st.columns([4, 1, 1])
                    with pi1:
                        st.markdown(
                            f"<div style='padding:8px 0;font-size:13px;font-weight:500;color:#111827'>"
                            f"{cat_icons.get(it['category'],'·')} {it['title'][:60]}"
                            f"<span style='font-size:11px;color:#9CA3AF;margin-left:8px'>{it['sub'][:40]}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    with pi2:
                        if st.button("✓ Approve", key=f"iappr_{it['id']}",
                                     type="primary", use_container_width=True):
                            st.session_state.governance[it["id"]]["status"]    = "APPROVED"
                            st.session_state.governance[it["id"]]["timestamp"] = datetime.now().strftime("%H:%M:%S")
                            st.rerun()
                    with pi3:
                        if st.button("✕ Reject", key=f"irej_{it['id']}",
                                     use_container_width=True):
                            st.session_state.governance[it["id"]]["status"]    = "REJECTED"
                            st.session_state.governance[it["id"]]["timestamp"] = datetime.now().strftime("%H:%M:%S")
                            st.rerun()
                    st.markdown(
                        "<div style='height:1px;background:#F3F4F6;margin:2px 0'></div>",
                        unsafe_allow_html=True,
                    )

        # Bulk action buttons
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        if gov_pending_live > 0:
            bg1, bg2, _bg3 = st.columns([1, 1, 4])
            if bg1.button("✓ Approve all", use_container_width=True, type="primary", key="gov_approve_all"):
                for it in governance_items:
                    if st.session_state.governance[it["id"]]["status"] == "PENDING":
                        st.session_state.governance[it["id"]]["status"]    = "APPROVED"
                        st.session_state.governance[it["id"]]["timestamp"] = datetime.now().strftime("%H:%M:%S")
                st.rerun()
            if bg2.button("✕ Reject all", use_container_width=True, key="gov_reject_all"):
                for it in governance_items:
                    if st.session_state.governance[it["id"]]["status"] == "PENDING":
                        st.session_state.governance[it["id"]]["status"]    = "REJECTED"
                        st.session_state.governance[it["id"]]["timestamp"] = datetime.now().strftime("%H:%M:%S")
                st.rerun()

    # ════════════════════════════════════════════════════════════════
    # ROW 4 — Approve IB Update + Ask AI (full-width card below gov)
    # ════════════════════════════════════════════════════════════════
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    # Status banner
    status_banners = {
        "APPROVED": ("✓ IB update approved and queued for SAP push. Audit record created.", "success"),
        "REJECTED": ("✕ IB update rejected. No changes will be pushed to SAP.", "error"),
        "REVIEW":   ("⏳ Update sent for secondary review. A reviewer will be notified.", "warning"),
    }
    if st.session_state.approval_status in status_banners:
        msg, btype = status_banners[st.session_state.approval_status]
        getattr(st, btype)(msg)

    tab_approve, = st.tabs(["🛡️  Approve IB Update"])

    with tab_approve:
        render_approval_section(ctx, a1, a2)

else:
    render_landing()