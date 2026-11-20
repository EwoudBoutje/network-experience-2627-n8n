locals {
  spec    = jsondecode(var.deployment_spec_json)
  proxmox = local.spec.proxmox

  # for_each op de VM-sleutel: een VM toevoegen of weghalen raakt alleen die VM.
  vms = { for vm in local.spec.vms : vm.key => vm }

  # Ansible controleert deze tags voordat het een VM configureert.
  tags = sort(["infra-agent", local.spec.deployment_id])
}

resource "proxmox_virtual_environment_pool" "deployment" {
  pool_id = local.proxmox.pool
  comment = "Deployment ${local.spec.deployment_id} - beheerd door de Terraform/Ansible-agent"
}

resource "proxmox_virtual_environment_vm" "vm" {
  for_each = local.vms

  name        = "${local.spec.deployment_id}-${each.key}"
  description = "Deployment ${local.spec.deployment_id}, VM ${each.key}. Beheerd door Terraform; niet manueel wijzigen."
  node_name   = local.proxmox.node
  vm_id       = each.value.vmid
  pool_id     = proxmox_virtual_environment_pool.deployment.pool_id
  tags        = local.tags

  started = true
  on_boot = false

  clone {
    vm_id = each.value.template_vmid
    full  = true
  }

  agent {
    # Het template moet qemu-guest-agent bevatten: IP-adressen komen via de guest agent.
    enabled = true
    timeout = "10m"
  }

  cpu {
    cores = each.value.cpu
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = each.value.memory_mb
  }

  disk {
    # Moet overeenkomen met de schijf van het template (cloud images: scsi0).
    datastore_id = local.proxmox.storage
    interface    = "scsi0"
    size         = each.value.disk_gb
  }

  network_device {
    bridge  = local.proxmox.bridge
    vlan_id = try(local.proxmox.vlan, null)
  }

  operating_system {
    type = "l26"
  }

  # Cloud images verwachten vaak een seriële console.
  serial_device {}

  initialization {
    datastore_id = local.proxmox.storage

    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }

    user_account {
      username = var.admin_username
      keys     = [trimspace(var.admin_ssh_public_key)]
    }
  }
}
