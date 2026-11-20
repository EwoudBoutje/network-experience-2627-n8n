"""infra-tf: MCP-server op de Terraform-VM.

Laat de AI-agent deployments (VM-sets op Proxmox) plannen, toepassen en verwijderen met de
lokale Terraform CLI. Impactvolle stappen vereisen een goedkeuringscode die NIET aan de agent
wordt teruggegeven: ze wordt per e-mail naar de goedkeurders gestuurd (APPROVAL_MODE=email)
of is een vast beheerderstoken (APPROVAL_MODE=token).

Per deployment: /var/lib/infra-agent/deployments/<id>/ met meta.json (spec, status,
historiek), een kopie van de Terraform-module, deployment.auto.tfvars.json en terraform.tfstate.

Configuratie: omgevingsvariabelen uit /etc/infra-agent/config.env (zie config.env.example).
Proxmox-toegang: /etc/infra-agent/proxmox.env (alleen voor het terraform-proces).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import shutil
import smtplib
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import anyio
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

# ------------------------------------------------------------------ config --
E = os.environ
ROOT = Path(E.get("INFRA_AGENT_ROOT", "/var/lib/infra-agent"))
CONF = Path(E.get("INFRA_AGENT_CONF", "/etc/infra-agent"))
MODULE_DIR = Path(E.get("INFRA_AGENT_MODULE", "/opt/infra-agent/module"))
LOG_DIR = Path(E.get("INFRA_AGENT_LOGS", "/var/log/infra-agent"))
DEPLOY_DIR, ARCHIVE_DIR, PLUGIN_CACHE = ROOT / "deployments", ROOT / "archive", ROOT / "plugin-cache"


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in E.get(name, default).split(",") if x.strip()]


def _int(name: str, default: int) -> int:
    return int(E.get(name, str(default)))


ALLOWED_NODES = _list("ALLOWED_NODES", "pve1")
ALLOWED_STORAGES = _list("ALLOWED_STORAGES", "local-lvm")
TEMPLATES = {int(k): v for k, v in (p.split("=", 1) for p in E.get("TEMPLATES", "9000=Debian 13 cloud-init").split(";") if "=" in p)}
BRIDGE = E.get("BRIDGE", "vmbr1")
VLAN = int(E["VLAN"]) if E.get("VLAN", "").strip() else None
ROLES = json.loads(E.get("ROLES_JSON", '{"webserver": {"install_php": "bool"}, "docker": {}}'))
LIMITS = {
    "max_vms": _int("MAX_VMS", 40), "cpu": (1, _int("MAX_CPU", 4)), "memory_mb": (512, _int("MAX_MEMORY_MB", 8192)),
    "disk_gb": (8, _int("MAX_DISK_GB", 100)), "max_total_memory_mb": _int("MAX_TOTAL_MEMORY_MB", 131072),
    "max_days": _int("MAX_DAYS", 365),
}
VMID_BASE, VMIDS_PER, MAX_SLOTS = _int("VMID_BASE", 5000), _int("VMIDS_PER_DEPLOYMENT", 50), _int("MAX_SLOTS", 20)
APPROVAL_MODE = E.get("APPROVAL_MODE", "email")
APPROVERS = _list("APPROVERS")
APPROVAL_TOKEN = E.get("APPROVAL_TOKEN", "")
APPROVAL_TTL = timedelta(hours=_int("APPROVAL_TTL_HOURS", 24))

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,38}[a-z0-9]$")
PREFIX_RE = re.compile(r"^[a-z][a-z0-9]{0,11}$")
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
RESERVED_USERS = {"root", "infraadmin", "runner", "daemon", "bin", "sys", "sync", "nobody", "www-data", "sshd", "docker"}
SSH_KEY_RE = re.compile(r"^(ssh-ed25519|ecdsa-sha2-nistp(256|384|521)|ssh-rsa) [A-Za-z0-9+/=]{20,8192}( [\x20-\x7e]{0,100})?$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TEXT_RE = re.compile(r"^[\w .,()+\-/&'À-ÿ]{1,80}$")
TYPES = {"bool": bool, "int": int, "str": str}
PLAN_FILES = {"apply": "deployment.tfplan", "destroy": "destroy.tfplan"}
BUSY = {"applying", "destroying"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("infra-tf")
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class ToolError(Exception):
    """Fout die als leesbare melding naar de agent gaat."""


def now() -> datetime:
    return datetime.now(timezone.utc)


def lock_for(dep_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(dep_id, threading.Lock())


# ------------------------------------------------------------------- meta ---
def dep_dir(dep_id: str) -> Path:
    if not ID_RE.fullmatch(dep_id or ""):
        raise ToolError("Ongeldige deployment_id (verwacht kleine letters, cijfers en '-', 4-40 tekens).")
    return DEPLOY_DIR / dep_id


def load_meta(dep_id: str) -> dict | None:
    path = dep_dir(dep_id) / "meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_meta(meta: dict, event: str | None = None, detail: str = "") -> None:
    meta["updated_at"] = now().isoformat()
    if event:
        meta.setdefault("history", []).append({"ts": meta["updated_at"], "event": event, "detail": detail[:500]})
        meta["history"] = meta["history"][-50:]
    path = dep_dir(meta["deployment_id"]) / "meta.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def all_metas() -> list[dict]:
    out = []
    for path in sorted(DEPLOY_DIR.glob("*/meta.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def state_resources(dep_id: str) -> int:
    state = dep_dir(dep_id) / "terraform.tfstate"
    if not state.exists():
        return 0
    try:
        return len(json.loads(state.read_text(encoding="utf-8")).get("resources") or [])
    except (OSError, json.JSONDecodeError):
        return -1


# -------------------------------------------------------------- terraform ---
def proxmox_env() -> dict:
    env = {}
    for line in (CONF / "proxmox.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if k.strip().startswith("PROXMOX_VE_"):
                env[k.strip()] = v.strip().strip('"').strip("'")
    if not env.get("PROXMOX_VE_ENDPOINT") or not env.get("PROXMOX_VE_API_TOKEN"):
        raise ToolError("Serverconfiguratie onvolledig: PROXMOX_VE_ENDPOINT/PROXMOX_VE_API_TOKEN ontbreken.")
    return env


def terraform(args: list[str], dep_id: str, timeout: int) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(ROOT), "TF_IN_AUTOMATION": "1", "TF_INPUT": "0",
           "CHECKPOINT_DISABLE": "1", "TF_PLUGIN_CACHE_DIR": str(PLUGIN_CACHE), **proxmox_env()}
    try:
        proc = subprocess.run(["terraform", *args], cwd=dep_dir(dep_id), env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc = subprocess.CompletedProcess(args, 124, "", f"time-out na {timeout} s")
    try:
        logf = LOG_DIR / f"{dep_id}-{time.strftime('%Y%m%dT%H%M%S')}-{args[0]}.log"
        logf.write_text(f"$ terraform {' '.join(args)}\n{proc.stdout}\n--- stderr ---\n{proc.stderr}", encoding="utf-8")
        os.chmod(logf, 0o600)
    except OSError:
        pass
    return proc


def tf_error(proc: subprocess.CompletedProcess) -> str:
    text = (proc.stderr or proc.stdout or "").strip()
    idx = text.find("Error:")
    return (text[idx:] if idx >= 0 else text)[:800] or f"terraform rc={proc.returncode}"


def summarize_plan(dep_id: str, plan_file: str) -> dict:
    proc = terraform(["show", "-json", "-no-color", plan_file], dep_id, 300)
    if proc.returncode != 0:
        raise ToolError("Plan kon niet gelezen worden: " + tf_error(proc))
    counts = {"create": 0, "update": 0, "delete": 0}
    vm_changes = []
    for rc in json.loads(proc.stdout).get("resource_changes") or []:
        actions = [a for a in (rc.get("change") or {}).get("actions") or [] if a != "no-op"]
        for a in actions:
            if a in counts:
                counts[a] += 1
        if actions and rc.get("type") == "proxmox_virtual_environment_vm":
            vm_changes.append(f"{'/'.join(actions)} {rc.get('index')}")
    return {"counts": counts, "vm_changes": vm_changes}


# ------------------------------------------------------------- validatie ---
def slug(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40].strip("-")


def build_meta(spec: dict, old: dict | None) -> dict:
    """Valideert de spec van de agent en vult VMID's, pool en netwerk aan. Gooit ToolError met alle fouten."""
    errors: list[str] = []
    if not isinstance(spec, dict):
        raise ToolError("spec moet een JSON-object zijn.")
    allowed_keys = {"deployment_id", "naam", "aanvrager_email", "beschrijving", "ends_at", "access_mode",
                    "users_sudo", "users", "proxmox", "groups", "toelichting"}
    if set(spec) - allowed_keys:
        errors.append(f"Onbekende velden: {sorted(set(spec) - allowed_keys)}.")

    naam = str(spec.get("naam", "")).strip()
    if not TEXT_RE.fullmatch(naam):
        errors.append("naam: 1-80 tekens (letters, cijfers, spaties, .,-()/&').")
    dep_id = str(spec.get("deployment_id") or slug(naam))
    if not ID_RE.fullmatch(dep_id):
        errors.append("deployment_id: kleine letters, cijfers en '-', 4-40 tekens.")
    email = str(spec.get("aanvrager_email", "")).strip().lower()
    if not EMAIL_RE.fullmatch(email):
        errors.append("aanvrager_email is ongeldig.")
    ends_at = spec.get("ends_at")
    if ends_at:
        try:
            end = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if end <= now():
                errors.append("ends_at ligt in het verleden.")
            elif end - now() > timedelta(days=LIMITS["max_days"]):
                errors.append(f"ends_at ligt meer dan {LIMITS['max_days']} dagen in de toekomst.")
            ends_at = end.isoformat()
        except ValueError:
            errors.append("ends_at is geen geldige ISO-datum (bv. 2027-06-30T20:00:00+02:00).")
    else:
        ends_at = None

    mode = spec.get("access_mode", "none")
    if mode not in ("per_vm", "all", "none"):
        errors.append("access_mode moet per_vm, all of none zijn.")
    sudo = spec.get("users_sudo", False)
    if not isinstance(sudo, bool):
        errors.append("users_sudo moet true of false zijn.")
    users = spec.get("users") or []
    seen_users: set[str] = set()
    if not isinstance(users, list) or len(users) > 50:
        errors.append("users: lijst van maximaal 50 gebruikers.")
        users = []
    clean_users = []
    for u in users:
        name = str((u or {}).get("name", "")).strip().lower() if isinstance(u, dict) else ""
        key = str((u or {}).get("ssh_public_key", "")).strip() if isinstance(u, dict) else ""
        if not USER_RE.fullmatch(name) or name in RESERVED_USERS:
            errors.append(f"Gebruiker '{name}': ongeldige of gereserveerde naam.")
        elif name in seen_users:
            errors.append(f"Gebruiker '{name}' staat dubbel.")
        if not SSH_KEY_RE.fullmatch(key):
            errors.append(f"Gebruiker '{name}': ongeldige publieke SSH-key.")
        seen_users.add(name)
        clean_users.append({"name": name, "ssh_public_key": key})
    if mode in ("per_vm", "all") and not clean_users:
        errors.append(f"access_mode {mode} vereist minstens één gebruiker.")

    px = spec.get("proxmox") or {}
    node = px.get("node") or (ALLOWED_NODES[0] if ALLOWED_NODES else "")
    storage = px.get("storage") or (ALLOWED_STORAGES[0] if ALLOWED_STORAGES else "")
    if node not in ALLOWED_NODES:
        errors.append(f"Node '{node}' niet toegestaan ({', '.join(ALLOWED_NODES)}).")
    if storage not in ALLOWED_STORAGES:
        errors.append(f"Storage '{storage}' niet toegestaan ({', '.join(ALLOWED_STORAGES)}).")

    groups = spec.get("groups") or []
    if not isinstance(groups, list) or not 1 <= len(groups) <= 10:
        errors.append("groups: 1 tot 10 VM-groepen.")
        groups = []
    if mode == "per_vm" and len(groups) != 1:
        errors.append("access_mode per_vm vereist exact één groep (één VM per gebruiker).")
    clean_groups, prefixes = [], set()
    for g in groups:
        if not isinstance(g, dict):
            errors.append("Elke groep moet een object zijn.")
            continue
        # Taalmodellen sturen getallen soms als tekst ("2"): netjes omzetten.
        g = {k: (int(v) if k in ("count", "template_vmid", "cpu", "memory_mb", "disk_gb")
                 and isinstance(v, str) and v.strip().isdigit() else v) for k, v in g.items()}
        prefix = str(g.get("prefix", ""))
        count = len(clean_users) if mode == "per_vm" else g.get("count")
        tpl = g.get("template_vmid")
        if not PREFIX_RE.fullmatch(prefix) or prefix in prefixes:
            errors.append(f"Groep '{prefix}': prefix moet uniek zijn, ^[a-z][a-z0-9]{{0,11}}$.")
        prefixes.add(prefix)
        if not isinstance(count, int) or count < 1:
            errors.append(f"Groep '{prefix}': count moet minstens 1 zijn.")
            count = 0
        if tpl not in TEMPLATES:
            errors.append(f"Groep '{prefix}': template {tpl} niet toegestaan ({', '.join(map(str, TEMPLATES))}).")
        for field in ("cpu", "memory_mb", "disk_gb"):
            lo, hi = LIMITS[field]
            v = g.get(field)
            if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
                errors.append(f"Groep '{prefix}': {field} moet tussen {lo} en {hi} liggen.")
        roles = g.get("roles") or []
        if not isinstance(roles, list) or len(set(roles)) != len(roles) or any(r not in ROLES for r in roles):
            errors.append(f"Groep '{prefix}': rollen moeten uniek zijn en uit {sorted(ROLES)} komen.")
            roles = []
        role_vars = g.get("role_vars") or {}
        clean_rv: dict = {}
        if not isinstance(role_vars, dict):
            errors.append(f"Groep '{prefix}': role_vars moet een object zijn.")
            role_vars = {}
        for role, values in role_vars.items():
            if role not in roles or not isinstance(values, dict):
                errors.append(f"Groep '{prefix}': role_vars voor niet-gekozen rol '{role}'.")
                continue
            for k, v in values.items():
                expected = TYPES.get((ROLES.get(role) or {}).get(k, ""))
                if expected is None or type(v) is not expected:
                    errors.append(f"Groep '{prefix}': rolvariabele {role}.{k} niet toegestaan of verkeerd type.")
                else:
                    clean_rv.setdefault(role, {})[k] = v
        clean_groups.append({"prefix": prefix, "count": count, "template_vmid": tpl, "cpu": g.get("cpu"),
                             "memory_mb": g.get("memory_mb"), "disk_gb": g.get("disk_gb"),
                             "roles": roles, "role_vars": clean_rv})

    total = sum(g["count"] for g in clean_groups)
    if total > min(LIMITS["max_vms"], VMIDS_PER):
        errors.append(f"Maximaal {min(LIMITS['max_vms'], VMIDS_PER)} VM's per deployment (gevraagd: {total}).")
    mem = sum(g["count"] * (g["memory_mb"] or 0) for g in clean_groups if isinstance(g["memory_mb"], int))
    if mem > LIMITS["max_total_memory_mb"]:
        errors.append(f"Totaal geheugen {mem} MB is meer dan {LIMITS['max_total_memory_mb']} MB.")
    if old and old.get("aanvrager_email") and old["aanvrager_email"] != email:
        errors.append("Deze deployment bestaat al en hoort bij een andere aanvrager.")
    if old and old.get("status") in BUSY:
        errors.append(f"Deze deployment is bezig ({old['status']}); probeer later opnieuw.")
    if errors:
        raise ToolError("Spec geweigerd:\n- " + "\n- ".join(errors))

    # VMID-blok: bestaande deployment houdt haar slot; nieuwe krijgt het laagste vrije slot.
    if old:
        slot = old["vmid_slot"]
    else:
        used = {m.get("vmid_slot") for m in all_metas()}
        free = [s for s in range(MAX_SLOTS) if s not in used]
        if not free:
            raise ToolError("Geen vrij VMID-blok meer; ruim eerst een deployment op.")
        slot = free[0]
    block = range(VMID_BASE + slot * VMIDS_PER, VMID_BASE + (slot + 1) * VMIDS_PER)
    # Bestaande VM-sleutels behouden hun VMID, zodat Terraform ze niet vervangt.
    old_vmids = {vm["key"]: vm["vmid"] for vm in (old or {}).get("vms", [])}
    taken = set()
    vms = []
    for g in clean_groups:
        for i in range(1, g["count"] + 1):
            key = f"{g['prefix']}{i:02d}"
            vmid = old_vmids.get(key)
            vms.append({"key": key, "name": f"{dep_id}-{key}", "vmid": vmid, "node": node,
                        "template_vmid": g["template_vmid"], "cpu": g["cpu"], "memory_mb": g["memory_mb"],
                        "disk_gb": g["disk_gb"], "roles": g["roles"], "role_vars": g["role_vars"], "users": []})
            if vmid:
                taken.add(vmid)
    free_ids = iter(v for v in block if v not in taken)
    for vm in vms:
        if not vm["vmid"]:
            vm["vmid"] = next(free_ids)
    names = sorted(u["name"] for u in clean_users)
    for i, vm in enumerate(vms):
        vm["users"] = [names[i]] if mode == "per_vm" else (names if mode == "all" else [])

    meta = dict(old or {})
    meta.update({
        "schema_version": 1, "deployment_id": dep_id, "naam": naam, "aanvrager_email": email,
        "beschrijving": str(spec.get("beschrijving", ""))[:2000], "ends_at": ends_at,
        "access_mode": mode, "users_sudo": sudo, "users": clean_users,
        "proxmox": {"node": node, "storage": storage, "bridge": BRIDGE, "vlan": VLAN, "pool": f"deploy-{dep_id}"},
        "groups": clean_groups, "vms": vms, "vmid_slot": slot,
        "toelichting": str(spec.get("toelichting", ""))[:1000],
    })
    meta.setdefault("status", "new")
    meta.setdefault("created_at", now().isoformat())
    return meta


# ----------------------------------------------------------- goedkeuring ---
def send_mail(to: list[str], subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = E.get("SMTP_FROM", "infra-agent@localhost"), ", ".join(to), subject
    msg.set_content(body)
    with smtplib.SMTP(E.get("SMTP_HOST", "localhost"), _int("SMTP_PORT", 587), timeout=30) as smtp:
        if E.get("SMTP_STARTTLS", "true").lower() == "true":
            smtp.starttls()
        if E.get("SMTP_USER"):
            smtp.login(E["SMTP_USER"], E.get("SMTP_PASSWORD", ""))
        smtp.send_message(msg)


def request_approval(meta: dict, kind: str, plan_sha: str, summary_text: str) -> str:
    """Zet de goedkeuring klaar; geeft de tekst terug die de agent aan de gebruiker toont (zonder code)."""
    expires = now() + APPROVAL_TTL
    pending = {"kind": kind, "plan_sha": plan_sha, "expires_at": expires.isoformat(), "attempts": 0}
    if APPROVAL_MODE == "email":
        if not APPROVERS:
            raise ToolError("Serverconfiguratie onvolledig: APPROVERS ontbreekt.")
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        pending["code_hash"] = hashlib.sha256(f"{code}:{plan_sha}".encode()).hexdigest()
        actie = "AANMAKEN/WIJZIGEN" if kind == "apply" else "VERWIJDEREN"
        send_mail(APPROVERS, f"[infra-agent] Goedkeuring {actie}: {meta['deployment_id']}",
                  f"De AI-agent wil deployment '{meta['deployment_id']}' {actie.lower()}.\n\n{summary_text}\n\n"
                  f"Goedkeuringscode: {code}\nGeldig tot: {expires:%Y-%m-%d %H:%M} UTC\n\n"
                  "Geef deze code alleen door als je akkoord gaat. Zonder code gebeurt er niets.")
        msg = (f"Een goedkeuringscode is gemaild naar de goedkeurders ({len(APPROVERS)}). "
               f"Vraag de gebruiker om die code; ze is geldig tot {expires:%Y-%m-%d %H:%M} UTC.")
    elif APPROVAL_MODE == "token":
        msg = "Vraag de gebruiker om het goedkeuringstoken van de beheerder."
    else:
        raise ToolError("Serverconfiguratie: APPROVAL_MODE moet email of token zijn.")
    meta["pending"] = pending
    return msg


def check_approval(meta: dict, kind: str, plan_sha: str, code: str) -> None:
    p = meta.get("pending")
    if not p or p["kind"] != kind:
        raise ToolError("Er wacht geen plan van dit type op goedkeuring. Maak eerst een nieuw plan.")
    if p["plan_sha"] != plan_sha:
        raise ToolError("plan_sha komt niet overeen met het plan dat op goedkeuring wacht.")
    if datetime.fromisoformat(p["expires_at"]) < now():
        raise ToolError("De goedkeuring is verlopen. Maak een nieuw plan.")
    code = (code or "").strip().upper()
    if APPROVAL_MODE == "token":
        ok = bool(APPROVAL_TOKEN) and hmac.compare_digest(code, APPROVAL_TOKEN.upper())
    else:
        ok = hmac.compare_digest(hashlib.sha256(f"{code}:{plan_sha}".encode()).hexdigest(), p.get("code_hash", ""))
    if not ok:
        p["attempts"] = p.get("attempts", 0) + 1
        if p["attempts"] >= 5:
            meta.pop("pending", None)
            save_meta(meta, "goedkeuring geblokkeerd", "5 foute codes")
            raise ToolError("Te veel foute codes; het plan is ingetrokken. Maak een nieuw plan.")
        save_meta(meta)
        raise ToolError("Goedkeuringscode is fout. Vraag de gebruiker de code opnieuw na te kijken.")


# ------------------------------------------------------------- operaties ---
def summary_text(meta: dict, plan: dict, kind: str) -> str:
    c = plan["counts"]
    lines = [f"Deployment: {meta['naam']} ({meta['deployment_id']})", f"Aanvrager:  {meta['aanvrager_email']}",
             f"Einddatum:  {meta.get('ends_at') or 'geen (blijft tot verwijderd)'}",
             f"Terraform:  +{c['create']} ~{c['update']} -{c['delete']}"]
    if kind == "apply":
        for g in meta["groups"]:
            lines.append(f"Groep {g['prefix']}: {g['count']}x {g['cpu']} vCPU / {g['memory_mb']} MB / {g['disk_gb']} GB, "
                         f"template {g['template_vmid']}, rollen: {', '.join(g['roles']) or '-'}")
        lines.append(f"Proxmox:    node {meta['proxmox']['node']}, storage {meta['proxmox']['storage']}, pool {meta['proxmox']['pool']}")
        lines.append(f"Toegang:    {meta['access_mode']} ({len(meta['users'])} gebruiker(s), sudo: {'ja' if meta['users_sudo'] else 'nee'})")
    if c["update"] or c["delete"]:
        lines.append("LET OP: dit plan wijzigt of verwijdert bestaande resources: " + "; ".join(plan["vm_changes"][:20]))
    if meta.get("toelichting"):
        lines.append(f"Toelichting agent: {meta['toelichting']}")
    return "\n".join(lines)


def op_plan(spec: dict) -> dict:
    tmp_id = str(spec.get("deployment_id") or slug(str(spec.get("naam", ""))))
    with lock_for(tmp_id):
        old = load_meta(tmp_id) if ID_RE.fullmatch(tmp_id) else None
        meta = build_meta(spec, old)
        dep_id = meta["deployment_id"]
        d = dep_dir(dep_id)
        d.mkdir(mode=0o750, parents=True, exist_ok=True)
        for src in list(MODULE_DIR.glob("*.tf")) + [MODULE_DIR / ".terraform.lock.hcl"]:
            if src.exists():
                shutil.copy2(src, d / src.name)
        tf_spec = {"schema_version": 1, "deployment_id": dep_id, "proxmox": meta["proxmox"],
                   "vms": [{k: vm[k] for k in ("key", "vmid", "template_vmid", "cpu", "memory_mb", "disk_gb")} for vm in meta["vms"]]}
        admin_key = (CONF / "admin_ssh_public_key").read_text(encoding="utf-8").strip()
        tfvars = d / "deployment.auto.tfvars.json"
        tfvars.write_text(json.dumps({"deployment_spec_json": json.dumps(tf_spec), "admin_ssh_public_key": admin_key}), encoding="utf-8")
        os.chmod(tfvars, 0o600)
        for f in PLAN_FILES.values():
            (d / f).unlink(missing_ok=True)
        meta.pop("pending", None)
        save_meta(meta, "plan gestart", f"{len(meta['vms'])} VM's")

        proc = terraform(["init", "-input=false", "-no-color"], dep_id, 600)
        if proc.returncode == 0:
            proc = terraform(["plan", "-input=false", "-no-color", "-out=" + PLAN_FILES["apply"]], dep_id, 900)
        if proc.returncode != 0:
            err = tf_error(proc)
            meta["last_error"] = err
            save_meta(meta, "plan mislukt", err)
            raise ToolError("Terraform-plan mislukt:\n" + err)
        plan = summarize_plan(dep_id, PLAN_FILES["apply"])
        sha = hashlib.sha256((d / PLAN_FILES["apply"]).read_bytes()).hexdigest()
        text = summary_text(meta, plan, "apply")
        if not any(plan["counts"].values()):
            (d / PLAN_FILES["apply"]).unlink(missing_ok=True)
            save_meta(meta, "plan zonder wijzigingen")
            return {"deployment_id": dep_id, "wijzigingen": plan["counts"], "samenvatting": text,
                    "volgende_stap": "Geen infrastructuurwijzigingen nodig. Je kunt configure_deployment (ansible) opnieuw uitvoeren."}
        try:
            approval_msg = request_approval(meta, "apply", sha, text)
        except (OSError, smtplib.SMTPException) as e:
            raise ToolError(f"Goedkeuringsmail kon niet verstuurd worden ({type(e).__name__}); er gebeurt niets.")
        if meta["status"] in ("new", "planned", "plan_failed"):
            meta["status"] = "planned"
        meta["last_error"] = None
        save_meta(meta, "plan klaar", f"sha {sha[:12]}")
        return {"deployment_id": dep_id, "plan_sha": sha, "wijzigingen": plan["counts"], "samenvatting": text,
                "goedkeuring": approval_msg,
                "volgende_stap": "Toon de samenvatting, vraag de goedkeuringscode en roep daarna apply_deployment aan."}


def _run_apply(dep_id: str, kind: str) -> None:
    lock = lock_for(dep_id)
    with lock:
        meta = load_meta(dep_id)
        proc = terraform(["apply", "-input=false", "-no-color", PLAN_FILES[kind]], dep_id, 3600)
        (dep_dir(dep_id) / PLAN_FILES[kind]).unlink(missing_ok=True)
        if proc.returncode != 0:
            err = tf_error(proc)
            meta.update(status="apply_failed" if kind == "apply" else "destroy_failed", last_error=err)
            save_meta(meta, f"{kind} mislukt", err)
            return
        if kind == "apply":
            out = terraform(["output", "-json", "-no-color"], dep_id, 120)
            outputs = {k: v.get("value") for k, v in json.loads(out.stdout or "{}").items()} if out.returncode == 0 else {}
            ips = {k: v.get("ipv4") for k, v in (outputs.get("vms") or {}).items()}
            for vm in meta["vms"]:
                vm["ipv4"] = ips.get(vm["key"])
            meta.update(status="applied", last_error=None)
            save_meta(meta, "apply klaar", f"{len(meta['vms'])} VM's")
            return
        remaining = state_resources(dep_id)
        if remaining != 0:
            meta.update(status="destroy_failed", last_error=f"na destroy staan nog {remaining} resource(s) in de state")
            save_meta(meta, "destroy onvolledig", meta["last_error"])
            return
        meta.update(status="destroyed", last_error=None)
        save_meta(meta, "destroy klaar")
        ARCHIVE_DIR.mkdir(mode=0o750, exist_ok=True)
        shutil.move(str(dep_dir(dep_id)), ARCHIVE_DIR / f"{dep_id}-{time.strftime('%Y%m%dT%H%M%S')}")


def op_apply(dep_id: str, plan_sha: str, code: str, kind: str) -> dict:
    with lock_for(dep_id):
        meta = load_meta(dep_id)
        if not meta:
            raise ToolError("Onbekende deployment.")
        if meta["status"] in BUSY:
            raise ToolError(f"Deployment is al bezig ({meta['status']}).")
        check_approval(meta, kind, plan_sha, code)
        if not (dep_dir(dep_id) / PLAN_FILES[kind]).exists():
            raise ToolError("Het opgeslagen plan ontbreekt. Maak een nieuw plan.")
        if hashlib.sha256((dep_dir(dep_id) / PLAN_FILES[kind]).read_bytes()).hexdigest() != plan_sha:
            raise ToolError("Het opgeslagen plan verschilt van het goedgekeurde plan; niets uitgevoerd.")
        meta.pop("pending", None)
        meta["status"] = "applying" if kind == "apply" else "destroying"
        meta["approved_at"] = now().isoformat()
        save_meta(meta, f"{kind} goedgekeurd", f"sha {plan_sha[:12]}")
    threading.Thread(target=_run_apply, args=(dep_id, kind), daemon=True).start()
    wat = "aangemaakt/gewijzigd" if kind == "apply" else "verwijderd"
    return {"deployment_id": dep_id, "status": meta["status"],
            "bericht": f"Goedgekeurd. De VM's worden nu {wat}; dit duurt enkele minuten. Volg op met get_deployment."
                       + (" Roep meteen configure_deployment (ansible) aan: die wacht zelf tot de VM's klaar zijn." if kind == "apply" else "")}


def op_plan_destroy(dep_id: str) -> dict:
    with lock_for(dep_id):
        meta = load_meta(dep_id)
        if not meta:
            raise ToolError("Onbekende deployment.")
        if meta["status"] in BUSY:
            raise ToolError(f"Deployment is bezig ({meta['status']}).")
        for f in PLAN_FILES.values():
            (dep_dir(dep_id) / f).unlink(missing_ok=True)
        proc = terraform(["plan", "-destroy", "-input=false", "-no-color", "-out=" + PLAN_FILES["destroy"]], dep_id, 900)
        if proc.returncode != 0:
            raise ToolError("Destroy-plan mislukt:\n" + tf_error(proc))
        plan = summarize_plan(dep_id, PLAN_FILES["destroy"])
        if plan["counts"]["create"] or plan["counts"]["update"]:
            (dep_dir(dep_id) / PLAN_FILES["destroy"]).unlink(missing_ok=True)
            raise ToolError("Onveilig destroy-plan (maakt of wijzigt resources); geweigerd.")
        sha = hashlib.sha256((dep_dir(dep_id) / PLAN_FILES["destroy"]).read_bytes()).hexdigest()
        text = summary_text(meta, plan, "destroy")
        try:
            approval_msg = request_approval(meta, "destroy", sha, text)
        except (OSError, smtplib.SMTPException) as e:
            raise ToolError(f"Goedkeuringsmail kon niet verstuurd worden ({type(e).__name__}); er gebeurt niets.")
        save_meta(meta, "destroy-plan klaar", f"sha {sha[:12]}")
        return {"deployment_id": dep_id, "plan_sha": sha, "wijzigingen": plan["counts"], "samenvatting": text,
                "goedkeuring": approval_msg,
                "volgende_stap": "Toon de samenvatting, vraag de goedkeuringscode en roep daarna apply_destroy aan."}


def op_discard(dep_id: str) -> dict:
    with lock_for(dep_id):
        meta = load_meta(dep_id)
        if not meta:
            raise ToolError("Onbekende deployment.")
        if meta["status"] in BUSY:
            raise ToolError(f"Deployment is bezig ({meta['status']}).")
        for f in PLAN_FILES.values():
            (dep_dir(dep_id) / f).unlink(missing_ok=True)
        meta.pop("pending", None)
        if state_resources(dep_id) == 0 and meta["status"] in ("new", "planned", "plan_failed"):
            shutil.rmtree(dep_dir(dep_id))
            return {"deployment_id": dep_id, "bericht": "Plan verworpen; er bestonden nog geen VM's, de deployment is verwijderd."}
        save_meta(meta, "plan verworpen")
        return {"deployment_id": dep_id, "bericht": "Plan verworpen; bestaande VM's blijven ongewijzigd.", "status": meta["status"]}


def public_view(meta: dict, include_users: bool) -> dict:
    keys = {u["name"]: u["ssh_public_key"] for u in meta.get("users", [])}
    vms = []
    for vm in meta.get("vms", []):
        v = {k: vm.get(k) for k in ("key", "name", "vmid", "node", "cpu", "memory_mb", "disk_gb", "roles", "role_vars", "ipv4")}
        v["users"] = ([{"name": n, "ssh_public_key": keys.get(n, ""), "sudo": meta.get("users_sudo", False)} for n in vm.get("users", [])]
                      if include_users else list(vm.get("users", [])))
        vms.append(v)
    out = {k: meta.get(k) for k in ("deployment_id", "naam", "aanvrager_email", "beschrijving", "status", "ends_at",
                                    "access_mode", "proxmox", "last_error", "created_at", "updated_at", "toelichting")}
    out["vms"] = vms
    out["wacht_op_goedkeuring"] = (meta.get("pending") or {}).get("kind")
    out["historiek"] = (meta.get("history") or [])[-10:]
    return out


# ------------------------------------------------------------------ MCP ---
tokens = {}
if E.get("MCP_TOKEN_AGENT"):
    tokens[E["MCP_TOKEN_AGENT"]] = {"client_id": "n8n-agent", "scopes": ["infra"]}
if E.get("MCP_TOKEN_ANSIBLE"):
    tokens[E["MCP_TOKEN_ANSIBLE"]] = {"client_id": "ansible-mcp", "scopes": ["infra"]}
for t in tokens:
    if len(t) < 32:
        raise SystemExit("MCP-tokens moeten minstens 32 tekens hebben.")
if not tokens:
    raise SystemExit("Stel MCP_TOKEN_AGENT (en MCP_TOKEN_ANSIBLE) in.")

mcp = FastMCP("infra-tf", auth=StaticTokenVerifier(tokens=tokens, required_scopes=["infra"]))


async def _call(fn, *args):
    try:
        return await anyio.to_thread.run_sync(fn, *args)
    except ToolError as e:
        return {"fout": str(e)}


@mcp.tool
async def get_limits() -> dict:
    """Toegestane keuzes en grenzen voor een deployment. Roep dit aan vóór je een spec opstelt."""
    return {"nodes": ALLOWED_NODES, "storages": ALLOWED_STORAGES, "templates": TEMPLATES,
            "rollen": ROLES, "limieten": LIMITS, "netwerk": {"bridge": BRIDGE, "vlan": VLAN},
            "goedkeuring": APPROVAL_MODE}


@mcp.tool
async def plan_deployment(spec: dict) -> dict:
    """Valideer een deployment-spec en maak een Terraform-plan. Er wordt NIETS aangemaakt.

    spec-velden: naam, aanvrager_email, beschrijving, ends_at (ISO-datum of null),
    access_mode (per_vm = elke gebruiker een eigen VM | all = alle gebruikers op alle VM's | none),
    users_sudo (bool), users [{name, ssh_public_key}], proxmox {node, storage},
    groups [{prefix, count, template_vmid, cpu, memory_mb, disk_gb, roles, role_vars}], toelichting.
    Optioneel deployment_id om een bestaande deployment te wijzigen (zelfde aanvrager).
    Na een geslaagd plan wordt een goedkeuringscode naar de goedkeurders gestuurd; jij krijgt die code niet.
    """
    return await _call(op_plan, spec)


@mcp.tool
async def apply_deployment(deployment_id: str, plan_sha: str, approval_code: str) -> dict:
    """Pas een goedgekeurd plan toe (VM's aanmaken/wijzigen). Gebruik ALLEEN de code die de gebruiker zelf geeft;
    verzin of raad nooit een code. Loopt op de achtergrond; volg op met get_deployment."""
    return await _call(op_apply, deployment_id, plan_sha, approval_code, "apply")


@mcp.tool
async def plan_destroy(deployment_id: str) -> dict:
    """Maak een plan om alle VM's van een deployment te verwijderen. Er wordt NIETS verwijderd.
    Een goedkeuringscode gaat naar de goedkeurders."""
    return await _call(op_plan_destroy, deployment_id)


@mcp.tool
async def apply_destroy(deployment_id: str, plan_sha: str, approval_code: str) -> dict:
    """Verwijder de deployment volgens het goedgekeurde destroy-plan. Gebruik ALLEEN de code van de gebruiker."""
    return await _call(op_apply, deployment_id, plan_sha, approval_code, "destroy")


@mcp.tool
async def discard_plan(deployment_id: str) -> dict:
    """Verwerp een plan dat op goedkeuring wacht (bv. als de gebruiker niet akkoord gaat)."""
    return await _call(op_discard, deployment_id)


@mcp.tool
async def get_deployment(deployment_id: str, include_users: bool = False) -> dict:
    """Status, VM's (met IP-adressen na apply), gebruikers en historiek van één deployment."""
    def run():
        meta = load_meta(deployment_id)
        if not meta:
            raise ToolError("Onbekende deployment (of al verwijderd en gearchiveerd).")
        return public_view(meta, include_users)
    return await _call(run)


@mcp.tool
async def list_deployments(expired_only: bool = False) -> dict:
    """Overzicht van alle actieve deployments. expired_only=true geeft alleen deployments waarvan de einddatum voorbij is."""
    def run():
        items = []
        for m in all_metas():
            expired = bool(m.get("ends_at")) and datetime.fromisoformat(m["ends_at"]) < now()
            if expired_only and not expired:
                continue
            items.append({"deployment_id": m["deployment_id"], "naam": m.get("naam"), "status": m.get("status"),
                          "aanvrager_email": m.get("aanvrager_email"), "ends_at": m.get("ends_at"),
                          "verlopen": expired, "vms": len(m.get("vms", []))})
        return {"deployments": items}
    return await _call(run)


def recover_interrupted() -> None:
    """Na een herstart kan een apply/destroy niet meer lopen: markeer als mislukt."""
    for m in all_metas():
        if m.get("status") in BUSY:
            m["status"] = "apply_failed" if m["status"] == "applying" else "destroy_failed"
            m["last_error"] = "Onderbroken door een herstart van infra-tf; controleer de state en plan opnieuw."
            save_meta(m, "onderbroken")


if __name__ == "__main__":
    for d in (DEPLOY_DIR, ARCHIVE_DIR, PLUGIN_CACHE, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
    recover_interrupted()
    mcp.run(transport="http", host=E.get("MCP_HOST", "0.0.0.0"), port=_int("MCP_PORT", 8001), path="/mcp")
