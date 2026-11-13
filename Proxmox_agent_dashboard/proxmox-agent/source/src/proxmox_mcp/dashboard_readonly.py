"""Local ProxmoxMCP-Plus extension: GET requests only, no guest execution."""
from datetime import datetime, timezone
import re

CONFIG_KEYS = {'name','description','tags','cores','sockets','vcpus','cpu','memory','balloon',
 'ostype','bios','machine','boot','onboot','agent','protection','template','numa',
 'hotplug','scsihw','startup','lock','vmgenid'}

def collect(api, include_guest_ips=False):
    resources = api.cluster.resources.get(type='vm')
    if not isinstance(resources, list):
        raise ValueError('Unexpected cluster inventory')
    rows = []
    for resource in resources:
        if resource.get('type') != 'qemu':
            continue
        node, vmid = resource.get('node'), resource.get('vmid')
        if not isinstance(node, str) or not str(vmid).isdigit():
            continue
        row = {'vmid': int(vmid), 'node': node, 'name': resource.get('name'),
               'inventory': resource, 'runtime': None, 'config': None,
               'snapshots': None, 'guest_network': None, 'errors': {}}
        guest = api.nodes(node).qemu(int(vmid))
        for section, fetch in (
            ('runtime', lambda: guest.status.current.get()),
            ('config', lambda: guest.config.get()),
            ('snapshots', lambda: guest.snapshot.get()),
        ):
            try:
                data = fetch()
                if section == 'config':
                    data = {k: v for k, v in data.items() if k in CONFIG_KEYS or
                            re.fullmatch(r'(net|scsi|sata|ide|virtio|hostpci|usb)\d+', k)}
                row[section] = data
            except Exception as exc:
                # Do not expose credentials, URLs or exception messages.
                row['errors'][section] = type(exc).__name__
        if include_guest_ips and (row['runtime'] or resource).get('status') == 'running':
            try:
                row['guest_network'] = guest.agent('network-get-interfaces').get()
            except Exception as exc:
                row['errors']['guest_network'] = type(exc).__name__
        rows.append(row)
    return {'schema_version': 1, 'sampled_at': datetime.now(timezone.utc).isoformat(),
            'vms': sorted(rows, key=lambda vm: vm['vmid'])}
