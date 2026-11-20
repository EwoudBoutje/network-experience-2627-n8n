# De deployment-spec komt als één JSON-string uit n8n (via tf_deploy.py in
# deployment.auto.tfvars.json). Gebruikers en SSH-keys zitten er bewust NIET in:
# Terraform kent alleen VM's en hun hardwareprofiel.
#
# Voorbeeld:
# {
#   "schema_version": 1,
#   "deployment_id": "webshop-test",
#   "proxmox": { "node": "pve1", "storage": "local-lvm", "bridge": "vmbr1",
#                "vlan": 120, "pool": "deploy-webshop-test" },
#   "vms": [
#     { "key": "web01", "vmid": 5000, "template_vmid": 9000, "cpu": 2, "memory_mb": 2048, "disk_gb": 20 },
#     { "key": "db01",  "vmid": 5001, "template_vmid": 9000, "cpu": 2, "memory_mb": 4096, "disk_gb": 40 }
#   ]
# }
#
# De grenzen hieronder zijn de harde ondergrens van wat technisch toegelaten is.
# Strengere grenzen (quota) staan in de n8n-node "Configuratie".

variable "deployment_spec_json" {
  description = "Deployment-spec als JSON-string (gegenereerd door n8n)."
  type        = string

  validation {
    condition     = can(jsondecode(var.deployment_spec_json))
    error_message = "deployment_spec_json is geen geldige JSON."
  }

  validation {
    condition     = try(jsondecode(var.deployment_spec_json).schema_version == 1, false)
    error_message = "schema_version moet 1 zijn."
  }

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{2,38}[a-z0-9]$", jsondecode(var.deployment_spec_json).deployment_id))
    error_message = "deployment_id moet ^[a-z0-9][a-z0-9-]{2,38}[a-z0-9]$ volgen."
  }

  validation {
    condition = try(
      jsondecode(var.deployment_spec_json).proxmox.pool == "deploy-${jsondecode(var.deployment_spec_json).deployment_id}",
      false
    )
    error_message = "De pool moet exact deploy-<deployment_id> heten."
  }

  validation {
    condition = try(
      length(jsondecode(var.deployment_spec_json).vms) >= 1 &&
      length(jsondecode(var.deployment_spec_json).vms) <= 50,
      false
    )
    error_message = "Een deployment bevat 1 tot 50 VM's."
  }

  validation {
    condition = try(
      alltrue([
        for vm in jsondecode(var.deployment_spec_json).vms :
        can(regex("^[a-z][a-z0-9]{0,11}[0-9]{2}$", vm.key)) &&
        vm.vmid >= 5000 && vm.vmid <= 5999 &&
        vm.template_vmid >= 100 &&
        vm.cpu >= 1 && vm.cpu <= 16 &&
        vm.memory_mb >= 512 && vm.memory_mb <= 65536 &&
        vm.disk_gb >= 4 && vm.disk_gb <= 1000
      ]),
      false
    )
    error_message = "Elke VM heeft een sleutel zoals web01, een VMID 5000-5999, een template en cpu 1-16, memory_mb 512-65536, disk_gb 4-1000."
  }

  validation {
    condition = try(
      length(distinct([for vm in jsondecode(var.deployment_spec_json).vms : vm.vmid])) == length(jsondecode(var.deployment_spec_json).vms) &&
      length(distinct([for vm in jsondecode(var.deployment_spec_json).vms : vm.key])) == length(jsondecode(var.deployment_spec_json).vms),
      false
    )
    error_message = "VMID's en VM-sleutels moeten uniek zijn."
  }
}

variable "admin_username" {
  description = "Cloud-init-gebruiker waarmee Ansible inlogt (geen eindgebruiker)."
  type        = string
  default     = "infraadmin"
}

variable "admin_ssh_public_key" {
  description = "Publieke SSH-key van ansible-control (uit /etc/infra-agent/admin_ssh_public_key)."
  type        = string

  validation {
    condition     = can(regex("^(ssh-ed25519|ecdsa-sha2-nistp(256|384|521)|ssh-rsa) [A-Za-z0-9+/=]+( .*)?$", trimspace(var.admin_ssh_public_key)))
    error_message = "admin_ssh_public_key is geen geldige OpenSSH-publieke sleutel."
  }
}
