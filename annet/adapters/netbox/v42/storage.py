from annetbox.v42.client_sync import NetboxV42
from annetbox.v42 import models as api_models

from annet.adapters.netbox.common.storage_base import BaseNetboxStorage
from annet.adapters.netbox.v41.models import NetboxDeviceV41
from annet.adapters.netbox.v42.models import PrefixV42, IpAddressV42


class NetboxStorageV42(BaseNetboxStorage):
    netbox_class = NetboxV42
    api_models = api_models
    device_model = NetboxDeviceV41
    prefix_model = PrefixV42
    ipaddress_model = IpAddressV42
