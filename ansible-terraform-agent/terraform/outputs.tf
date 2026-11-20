output "deployment_id" {
  value = local.spec.deployment_id
}

output "pool" {
  value = proxmox_virtual_environment_pool.deployment.pool_id
}

output "vms" {
  description = "Per VM-sleutel: VMID, naam, node en eerste IPv4-adres (via guest agent)."
  value = {
    for key, vm in proxmox_virtual_environment_vm.vm : key => {
      vmid = vm.vm_id
      name = vm.name
      node = vm.node_name
      ipv4 = try([for ip in flatten(vm.ipv4_addresses) : ip if !startswith(ip, "127.")][0], null)
    }
  }
}
