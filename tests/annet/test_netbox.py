from datetime import datetime
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from annetbox.base.models import PagingResponse
from annetbox.v37 import models as v37_api_models
from annetbox.v41 import models as v41_api_models
from annetbox.v42 import models as v42_api_models

from annet.adapters.netbox.common import storage_base
from annet.adapters.netbox.common.query import NetboxQuery
from annet.adapters.netbox.common.storage_base import parse_glob
from annet.adapters.netbox.v37 import storage as v37_storage
from annet.adapters.netbox.v41 import storage as v41_storage
from annet.adapters.netbox.v42 import storage as v42_storage


ADAPTERS = [
    pytest.param(v37_storage.NetboxV37Adapter, v37_api_models, id="v37"),
    pytest.param(v41_storage.NetboxV41Adapter, v41_api_models, id="v41"),
    pytest.param(v42_storage.NetboxV42Adapter, v42_api_models, id="v42"),
]


def _make_site(api_mod: ModuleType, site_id: int = 1):
    return api_mod.Site(
        id=site_id,
        name="site-a",
        display="site-a",
        url="http://nb/api/dcim/sites/1/",
        slug="site-a",
        status=api_mod.Label(value="active", label="Active"),
        custom_fields={"tacacs_state": "on"},
        created=datetime(2024, 1, 1),
        last_updated=datetime(2024, 1, 2),
    )


@pytest.mark.parametrize("adapter_cls,api_mod", ADAPTERS)
def test_adapter_get_site_passthrough(adapter_cls, api_mod):
    adapter = adapter_cls.__new__(adapter_cls)
    adapter.netbox = MagicMock()
    adapter.netbox.dcim_site.return_value = _make_site(api_mod)

    site = adapter.get_site(1)

    adapter.netbox.dcim_site.assert_called_once_with(1)
    assert site.id == 1
    assert site.custom_fields == {"tacacs_state": "on"}


@pytest.mark.parametrize("adapter_cls,api_mod", ADAPTERS)
def test_adapter_list_sites_passthrough(adapter_cls, api_mod):
    adapter = adapter_cls.__new__(adapter_cls)
    adapter.netbox = MagicMock()
    adapter.netbox.dcim_all_sites.return_value = PagingResponse(
        count=1,
        next=None,
        previous=None,
        results=[_make_site(api_mod)],
    )

    sites = adapter.list_sites(slug=["site-a"])

    adapter.netbox.dcim_all_sites.assert_called_once_with(slug=["site-a"])
    assert [s.id for s in sites] == [1]


def test_storage_get_site_facade():
    storage = storage_base.BaseNetboxStorage.__new__(storage_base.BaseNetboxStorage)
    storage.netbox = MagicMock()
    storage.netbox.get_site.return_value = _make_site(v42_api_models)

    site = storage.get_site(1)

    storage.netbox.get_site.assert_called_once_with(1)
    assert site.custom_fields["tacacs_state"] == "on"


@pytest.mark.parametrize(
    "api_mod",
    [
        pytest.param(v37_api_models, id="v37"),
        pytest.param(v41_api_models, id="v41"),
        pytest.param(v42_api_models, id="v42"),
    ],
)
def test_netbox_device_site_remains_entity(api_mod):
    """Backward-compat: device.site stays an EntityWithSlug stub, not a full Site."""
    assert api_mod.Device.__annotations__["site"] is api_mod.EntityWithSlug


def test_parse_glob():
    assert parse_glob(True, NetboxQuery(["host"])) == {"name__ie": ["host"]}
    assert parse_glob(False, NetboxQuery(["host"])) == {"name__ic": ["host."]}
    assert parse_glob(True, NetboxQuery(["site:mysite"])) == {"site": ["mysite"]}
    assert parse_glob(True, NetboxQuery(["tag:mysite", "justhost"])) == {
        "name__ie": ["justhost"],
        "tag": ["mysite"],
    }
    with pytest.raises(Exception):
        parse_glob(True, NetboxQuery(["host:"]))
    with pytest.raises(Exception):
        parse_glob(True, NetboxQuery(["NONONO:param"]))
