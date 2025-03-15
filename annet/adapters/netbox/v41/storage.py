from annetbox.v41.client_sync import NetboxV41
from annetbox.v41 import models as api_models

from annet.adapters.netbox.v41.models import IpAddressV41, NetboxDeviceV41, PrefixV41
from annet.adapters.netbox.common.storage_base import BaseNetboxStorage


class NetboxStorageV41(BaseNetboxStorage):
    netbox_class = NetboxV41
    api_models = api_models
    device_model = NetboxDeviceV41
    prefix_model = PrefixV41
    ipaddress_model = IpAddressV41
