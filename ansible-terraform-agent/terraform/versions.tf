terraform {
  required_version = ">= 1.6.0"

  required_providers {
    proxmox = {
      source = "bpg/proxmox"
      # Pin na de eerste geslaagde run op een exacte versie en commit .terraform.lock.hcl.
      version = ">= 0.66.0, < 1.0.0"
    }
  }

  # Lokale state: één map per deployment op de Terraform-VM
  # (/var/lib/infra-agent/deployments/<deployment_id>/terraform.tfstate).
}

# De verbinding komt uit omgevingsvariabelen die tf_deploy.py zet vanuit
# /etc/infra-agent/proxmox.env op de Terraform-VM:
#   PROXMOX_VE_ENDPOINT  = https://<proxmox-host>:8006/
#   PROXMOX_VE_API_TOKEN = terraform@pve!infra=<secret>
# Het Proxmox-CA-certificaat staat in de systeem-truststore van de Terraform-VM.
provider "proxmox" {}
