from annet.adapters.netbox.common.client import (
    collect, )
from annet_netbox import Client
from annet_netbox.api.dcim import dcim_devices_list, dcim_devices_retrieve, dcim_interfaces_list
from annet_netbox.api.ipam import ipam_ip_addresses_list


def use_client(func):
    def wrapper(self, *args, **kwargs):
        return func(client=self, *args, **kwargs)

    return wrapper


class NetboxV37(Client):
    def __init__(self, url: str, token: str):
        headers = {}
        if token:
            headers["Authorization"] = f"Token {token}"
        super().__init__(
            base_url=url,
            headers=headers,
            raise_on_unexpected_status=True,
        )

    interfaces = use_client(dcim_interfaces_list.sync)
    all_interfaces = collect(interfaces, field="device_id")

    ip_addresses = use_client(ipam_ip_addresses_list.sync)
    all_ip_addresses = collect(ip_addresses, field="interface_id")

    devices = use_client(dcim_devices_list.sync)
    all_devices = collect(devices)

    get_device = use_client(dcim_devices_retrieve.sync)
