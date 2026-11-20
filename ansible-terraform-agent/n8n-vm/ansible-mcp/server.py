"""ansible-mcp: MCP-server die deployments configureert met Ansible.

Tools voor de n8n-agent:
  list_roles()                         -> rollen uit ansible/catalog.yml
  configure_deployment(deployment_id)  -> start een run op de achtergrond
  get_configure_status(deployment_id)  -> status en resultaat van de laatste run

Een run haalt de deployment (VM's, rollen, gebruikers) zelf op bij infra-tf, wacht tot de
VM's aangemaakt zijn (status "applied"), valideert alles en voert playbooks/deploy.yml uit.
Dat playbook gebruikt ansible.mcp om via proxmox-mcp de VM's en IP-adressen op te halen.
De agent geeft dus alleen een deployment_id door, nooit SSH-keys of VM-lijsten.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import anyio
import yaml
from fastmcp import Client, FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

BASE = Path(os.environ.get("INFRA_AGENT_HOME", "/opt/infra-agent"))
ANSIBLE_DIR = BASE / "ansible"
CATALOG = ANSIBLE_DIR / "catalog.yml"
DATA = Path(os.environ.get("INFRA_AGENT_DATA", "/var/lib/infra-agent"))
JOBS, LOGS = DATA / "jobs", DATA / "logs"
RUN_DIR = Path("/tmp/infra-agent")
SECRETS = Path(os.environ.get("SECRETS_DIR", "/run/secrets"))
INFRA_TF_URL = os.environ.get("INFRA_TF_URL", "")
WAIT_FOR_APPLY = 45 * 60
PLAYBOOK_TIMEOUT = 3600

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,38}[a-z0-9]$")
VM_KEY_RE = re.compile(r"^[a-z][a-z0-9]{0,11}[0-9]{2}$")
NODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,62}$")
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
RESERVED_USERS = {"root", "infraadmin", "runner", "daemon", "bin", "sys", "sync", "nobody", "www-data", "sshd", "docker"}
SSH_KEY_RE = re.compile(r"^(ssh-ed25519|ecdsa-sha2-nistp(256|384|521)|ssh-rsa) [A-Za-z0-9+/=]{20,8192}( [\x20-\x7e]{0,100})?$")
TEXT_RE = re.compile(r"^[\w .,()+\-/&'À-ÿ]{0,80}$")
TYPES = {"bool": bool, "int": int, "str": str}

_running: dict[str, threading.Thread] = {}
_guard = threading.Lock()


class JobError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def secret(name: str) -> str:
    return (SECRETS / name).read_text(encoding="utf-8").strip()


def catalog_roles() -> dict:
    return (yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}).get("roles") or {}


# ------------------------------------------------------------ jobstatus ---
def job_path(dep_id: str) -> Path:
    return JOBS / f"{dep_id}.json"


def save_job(job: dict) -> None:
    job["updated_at"] = now()
    tmp = job_path(job["deployment_id"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(job_path(job["deployment_id"]))


def load_job(dep_id: str) -> dict | None:
    p = job_path(dep_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ---------------------------------------------------------------- infra-tf ---
def infra_call(tool: str, args: dict) -> dict:
    """Roept een tool van infra-tf aan en geeft het JSON-resultaat terug."""
    async def go():
        transport = StreamableHttpTransport(url=INFRA_TF_URL, headers={"Authorization": f"Bearer {secret('infra_tf_token')}"})
        async with Client(transport, timeout=120) as client:
            return await client.call_tool(tool, args, raise_on_error=False)
    res = asyncio.run(go())
    data = getattr(res, "structured_content", None)
    if isinstance(data, dict):
        return data.get("result", data) if set(data) == {"result"} else data
    for item in getattr(res, "content", None) or []:
        text = getattr(item, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"fout": text[:500]}
    return {"fout": "leeg antwoord van infra-tf"}


# --------------------------------------------------------------- validatie ---
def build_payload(dep: dict) -> dict:
    """Zet get_deployment(include_users=True) om naar de variabele 'deploy' voor het playbook en valideert alles."""
    roles_catalog = catalog_roles()
    dep_id = dep.get("deployment_id", "")
    if not ID_RE.fullmatch(dep_id):
        raise JobError("ongeldige deployment_id van infra-tf")
    naam = str(dep.get("naam", ""))
    if not TEXT_RE.fullmatch(naam):
        raise JobError("ongeldige naam")
    vms = []
    seen_keys, seen_ids = set(), set()
    for vm in dep.get("vms") or []:
        key, vmid, node = vm.get("key"), vm.get("vmid"), vm.get("node")
        if not (isinstance(key, str) and VM_KEY_RE.fullmatch(key)) or vm.get("name") != f"{dep_id}-{key}":
            raise JobError(f"ongeldige VM-sleutel of -naam: {key}")
        if not isinstance(vmid, int) or not 5000 <= vmid <= 5999 or not (isinstance(node, str) and NODE_RE.fullmatch(node)):
            raise JobError(f"{key}: ongeldige VMID of node")
        if key in seen_keys or vmid in seen_ids:
            raise JobError("dubbele VM-sleutel of VMID")
        seen_keys.add(key)
        seen_ids.add(vmid)
        roles = vm.get("roles") or []
        if any(r not in roles_catalog for r in roles) or len(set(roles)) != len(roles):
            raise JobError(f"{key}: rol niet in catalog.yml (pas catalog.yml en ROLES_JSON gelijk)")
        role_vars = vm.get("role_vars") or {}
        for role, values in role_vars.items():
            if role not in roles or not isinstance(values, dict):
                raise JobError(f"{key}: role_vars voor niet-gekozen rol {role}")
            for name, value in values.items():
                expected = TYPES.get((roles_catalog[role].get("vars") or {}).get(name, ""))
                if expected is None or type(value) is not expected:
                    raise JobError(f"{key}: rolvariabele {role}.{name} niet toegestaan")
        users = []
        for u in vm.get("users") or []:
            if (not isinstance(u, dict) or not USER_RE.fullmatch(str(u.get("name", ""))) or u["name"] in RESERVED_USERS
                    or not SSH_KEY_RE.fullmatch(str(u.get("ssh_public_key", ""))) or not isinstance(u.get("sudo"), bool)):
                raise JobError(f"{key}: ongeldige gebruiker")
            users.append({"name": u["name"], "ssh_public_key": u["ssh_public_key"], "sudo": u["sudo"]})
        vms.append({"key": key, "name": vm["name"], "vmid": vmid, "node": node,
                    "roles": roles, "role_vars": role_vars, "users": users})
    if not 1 <= len(vms) <= 50:
        raise JobError("deployment bevat geen (of te veel) VM's")
    return {"deployment_id": dep_id, "naam": naam, "vms": vms}


def summarize(stdout: str) -> tuple[dict, list]:
    try:
        report = json.loads(stdout[stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return {}, [{"host": "-", "task": "-", "msg": "Ansible-uitvoer kon niet gelezen worden"}]
    failures = []
    for play in report.get("plays", []):
        for task in play.get("tasks", []):
            name = task.get("task", {}).get("name", "?")
            for host, res in (task.get("hosts") or {}).items():
                if res.get("failed") or res.get("unreachable"):
                    msg = res.get("msg") or res.get("stderr") or "mislukt"
                    for item in res.get("results") or []:
                        if isinstance(item, dict) and (item.get("failed") or item.get("unreachable")) and item.get("msg"):
                            msg = item["msg"]
                            break
                    failures.append({"host": host, "task": name, "msg": str(msg)[:300]})
    return report.get("stats", {}), failures[:30]


# --------------------------------------------------------------------- run ---
def run_job(dep_id: str) -> None:
    try:
        _run_job(dep_id)
    except Exception:
        logging.exception("configuratierun voor %s afgebroken", dep_id)


def _run_job(dep_id: str) -> None:
    job = {"deployment_id": dep_id, "status": "running", "fase": "wachten op VM's", "started_at": now()}
    save_job(job)
    try:
        deadline = time.time() + WAIT_FOR_APPLY
        while True:
            dep = infra_call("get_deployment", {"deployment_id": dep_id, "include_users": True})
            if "fout" in dep:
                raise JobError(dep["fout"])
            status = dep.get("status")
            if status == "applied":
                break
            if status != "applying":
                raise JobError(f"deployment heeft status '{status}'; alleen 'applied' (of 'applying') kan geconfigureerd worden")
            if time.time() > deadline:
                raise JobError("time-out: de VM's zijn na 45 minuten nog niet klaar")
            time.sleep(20)

        payload = build_payload(dep)
        job["fase"] = "ansible"
        save_job(job)
        RUN_DIR.mkdir(mode=0o700, exist_ok=True)
        vars_file, hosts_file = RUN_DIR / f"{dep_id}.json", RUN_DIR / f"{dep_id}-hosts.json"
        hosts_file.unlink(missing_ok=True)
        vars_file.write_text(json.dumps({"deploy": payload}), encoding="utf-8")
        os.chmod(vars_file, 0o600)
        env = {**os.environ, "ANSIBLE_STDOUT_CALLBACK": "ansible.posix.json", "ANSIBLE_NOCOLOR": "1",
               "ANSIBLE_PERSISTENT_CONNECT_TIMEOUT": "60", "ANSIBLE_PERSISTENT_COMMAND_TIMEOUT": "180"}
        try:
            proc = subprocess.run(["ansible-playbook", "playbooks/deploy.yml", "-e", f"@{vars_file}"],
                                  cwd=ANSIBLE_DIR, env=env, capture_output=True, text=True, timeout=PLAYBOOK_TIMEOUT)
            rc, out, err = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            rc, out, err = 124, "", f"time-out na {PLAYBOOK_TIMEOUT} s"
        finally:
            vars_file.unlink(missing_ok=True)
        try:
            (LOGS / f"{dep_id}-{time.strftime('%Y%m%dT%H%M%S')}.log").write_text(out + "\n--- stderr ---\n" + err, encoding="utf-8")
        except OSError:
            pass
        stats, failures = summarize(out)
        if rc != 0 and not failures:
            failures = [{"host": "-", "task": "-", "msg": (err.strip() or f"rc={rc}")[-300:]}]
        try:
            vms = json.loads(hosts_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            vms = []
        users = {vm["key"]: [u["name"] for u in vm["users"]] for vm in payload["vms"]}
        for vm in vms:
            vm["users"] = users.get(vm.get("key"), [])
        ok = rc == 0 and len(vms) == len(payload["vms"]) and all(v.get("configured") for v in vms)
        job.update(status="ok" if ok else "failed", fase="klaar", rc=rc, stats=stats, failures=failures, vms=vms,
                   finished_at=now())
    except JobError as e:
        job.update(status="failed", fase="mislukt", error=str(e), finished_at=now())
    except Exception as e:  # onverwachte fout: zonder details die geheimen kunnen bevatten
        job.update(status="failed", fase="mislukt", error=f"interne fout ({type(e).__name__})", finished_at=now())
    save_job(job)


# --------------------------------------------------------------------- MCP ---
token = secret("ansible_mcp_token")
if len(token) < 32:
    raise SystemExit("ansible_mcp_token moet minstens 32 tekens hebben.")
mcp = FastMCP("ansible-mcp", auth=StaticTokenVerifier(tokens={token: {"client_id": "n8n-agent", "scopes": ["ansible"]}},
                                                      required_scopes=["ansible"]))


@mcp.tool
async def list_roles() -> dict:
    """Rollen die per VM-groep gekozen kunnen worden, met hun variabelen (base en user_access gelden altijd)."""
    return {"rollen": await anyio.to_thread.run_sync(catalog_roles),
            "altijd": ["base (updates, tijdzone, fail2ban, SSH alleen met sleutel)", "user_access (gebruikers + SSH-keys)"]}


@mcp.tool
async def configure_deployment(deployment_id: str) -> dict:
    """Configureer alle VM's van een deployment met Ansible (rollen, gebruikers, snapshot 'baseline').
    Mag meteen na apply_deployment: wacht zelf tot de VM's klaar zijn. Loopt op de achtergrond;
    volg op met get_configure_status. Kan ook opnieuw uitgevoerd worden (idempotent)."""
    if not ID_RE.fullmatch(deployment_id or ""):
        return {"fout": "ongeldige deployment_id"}
    with _guard:
        t = _running.get(deployment_id)
        if t and t.is_alive():
            return {"deployment_id": deployment_id, "status": "running", "bericht": "Er loopt al een configuratierun."}
        t = threading.Thread(target=run_job, args=(deployment_id,), daemon=True)
        _running[deployment_id] = t
        t.start()
    return {"deployment_id": deployment_id, "status": "gestart",
            "bericht": "Configuratie gestart: wacht op de VM's en draait daarna Ansible. Volg op met get_configure_status."}


@mcp.tool
async def get_configure_status(deployment_id: str) -> dict:
    """Status van de laatste configuratierun: running, ok of failed, met per VM het IP en eventuele fouten."""
    if not ID_RE.fullmatch(deployment_id or ""):
        return {"fout": "ongeldige deployment_id"}
    job = await anyio.to_thread.run_sync(load_job, deployment_id)
    return job or {"deployment_id": deployment_id, "status": "geen", "bericht": "Nog geen configuratierun voor deze deployment."}


if __name__ == "__main__":
    for d in (JOBS, LOGS):
        d.mkdir(parents=True, exist_ok=True)
    # Runs die bij een herstart bezig waren, zijn afgebroken.
    for p in JOBS.glob("*.json"):
        try:
            job = json.loads(p.read_text(encoding="utf-8"))
            if job.get("status") == "running":
                job.update(status="failed", fase="mislukt", error="onderbroken door een herstart; voer configure_deployment opnieuw uit")
                save_job(job)
        except (OSError, json.JSONDecodeError):
            continue
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("MCP_PORT", "8000")), path="/mcp")
