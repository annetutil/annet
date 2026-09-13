Annet Tutorial
==============

This tutorial has been tested on MacOS but should also work on Linux. While it's unclear if Windows WSL supports it, there's no harm in trying!

Prepare Environment
-------------------

We'll use Docker Compose to set up the lab environment. You're welcome to use any other virtualization tool, but Docker Compose is straightforward and works across Linux, macOS, and Windows.

For MacOS, we recommend using `Docker Desktop for Mac <https://docs.docker.com/desktop/mac/install/>`__ or `orbstack <https://orbstack.dev/>`__.

Arista cEOS
^^^^^^^^^^^

We've chosen to use Containerized Arista EOS because Arista EOS is widely used and has a Cisco-like interface that's easy to understand. The key advantage is that the image can be `downloaded from the official site <https://www.arista.com/en/support/software-download>`__ for free by any registered user.

.. note:: Use your own domain or corporate email for registration, as Arista doesn't allow common email providers like Gmail.

Download the image and import it into Docker:

.. code:: bash

  docker image import cEOS64-lab-4.33.1F.tar.xz arista-ceos:4.33.1F --platform linux/amd64

Topology
^^^^^^^^

::

                   ╔════════╗
              Eth1 ║AS 65001║ Eth2
         ┌─────────║   r1   ║──────────┐
         │     .11 ║        ║ .11      │
         │         ╚════════╝          │
         │                             │
    10.1.2.0/24                   10.1.3.0/24
         │                             │
         │                             │
    Eth1 │ .12                     .13 │ Eth1
    ╔════════╗                    ╔════════╗
    ║AS 65002║ Eth2          Eth2 ║AS 65003║
    ║   r2   ║────────────────────║   r3   ║
    ║        ║.12  10.2.3.0/24 .13║        ║
    ╚════════╝                    ╚════════╝

The network consists of three routers directly connected to each other.

Out-of-band management IP addresses are:

+--------+------------------+
| Router |        MGMT      |
+========+==================+
|   r1   | ``172.20.0.101`` |
+--------+------------------+
|   r2   | ``172.20.0.102`` |
+--------+------------------+
|   r3   | ``172.20.0.103`` |
+--------+------------------+

Netbox
^^^^^^

.. note:: Currently, version 4.3 is supported (2025q3)

If you prefer to use your own Netbox installation, you can skip this section. However, make sure to read the notes at the beginning of the next section.

The easiest way to install Netbox is to use the dockerized version.

.. note:: Netbox-docker version 3.3.0 are used in the tutorial.

Clone repo with dockerized version of netbox. If you run netbox on weak hardware you can change timeouts in ``docker-compose.yml``, e.g. multiply all the timeouts by 10.

.. code:: bash

  git clone https://github.com/netbox-community/netbox-docker.git
  cd netbox-docker
  git fetch --tags && git checkout tags/3.3.0
  sed -i.bak 's/0s/00s/g' docker-compose.yml

Docker Compose Override File
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note::

  1. The directories ``lab/ceos-rX.flash`` are required to store the saved configuration of cEOS.
  2. Before running cEOS, prepare the ``startup-config`` with the management IP address and a local user ``annet:annet``.
  3. The ``depends_on`` section is added to each cEOS service to avoid overloading resources on weaker hardware.
  4. The docker-compose file specifies the cEOS version. If you use a different version, update the file accordingly.
  5. If you use your own Netbox, you need to:

     - Clone Netbox-docker repository into directory ``netbox-docker``;
     - Change name ``docker-compose.override.yml`` file to ``docker-compose.yml``;
     - Remove the ``services/netbox`` section from the docker-compose file;
     - Remove the ``depends_on`` section from the cEOS services.

Go to to root of your folder and create folders for cEOS configuration files and configuration files for cEOS.

.. note::

  Your final directory structure should look like this:

  .. code:: bash

    ├── lab
    │   ├── ceos-r1.flash
    │   ├── ceos-r2.flash
    │   └── ceos-r3.flash
    └── netbox-docker
        ├── docker-compose.override.yml
        └── ... other netbox-docker files


.. code:: bash

  cd ..
  mkdir -p lab/ceos-r1.flash lab/ceos-r2.flash lab/ceos-r3.flash

.. code:: bash

  cat > lab/ceos-r1.flash/startup-config <<EOF
  no aaa root
  aaa authorization serial-console
  aaa authorization exec default local
  aaa authorization exec console none
  username annet privilege 15 role network-admin secret 0 annet
  switchport default mode routed
  no service interface inactive port-id allocation disabled
  transceiver qsfp default-mode 4x10G
  service routing protocols model multi-agent
  logging console informational
  spanning-tree mode mstp
  interface Ethernet1
     no switchport
  interface Ethernet2
     no switchport
  interface Ethernet3
     no switchport
  interface Management0
     ip address 172.20.0.101/24
  ip routing
  end
  EOF

.. code:: bash

  cat > lab/ceos-r2.flash/startup-config <<EOF
  no aaa root
  aaa authorization serial-console
  aaa authorization exec default local
  aaa authorization exec console none
  username annet privilege 15 role network-admin secret 0 annet
  switchport default mode routed
  no service interface inactive port-id allocation disabled
  transceiver qsfp default-mode 4x10G
  service routing protocols model multi-agent
  logging console informational
  spanning-tree mode mstp
  interface Ethernet1
     no switchport
  interface Ethernet2
     no switchport
  interface Ethernet3
     no switchport
  interface Management0
     ip address 172.20.0.102/24
  ip routing
  end
  EOF

.. code:: bash

  cat > lab/ceos-r3.flash/startup-config <<EOF
  no aaa root
  aaa authorization serial-console
  aaa authorization exec default local
  aaa authorization exec console none
  username annet privilege 15 role network-admin secret 0 annet
  switchport default mode routed
  no service interface inactive port-id allocation disabled
  transceiver qsfp default-mode 4x10G
  service routing protocols model multi-agent
  logging console informational
  spanning-tree mode mstp
  interface Ethernet1
     no switchport
  interface Ethernet2
     no switchport
  interface Ethernet3
     no switchport
  interface Management0
     ip address 172.20.0.103/24
  ip routing
  end
  EOF

Create docker-compose override file.

.. code:: bash

  cd netbox-docker
  cat > docker-compose.override.yml <<EOF
  networks:
    default:
      driver: bridge
      ipam:
        driver: default
        config:
        - subnet: 172.20.0.0/24
          gateway: 172.20.0.1

    r1r2_net:
      name: r1r2_net
      driver: bridge
      internal: true
      ipam:
        config:
          - subnet: 10.1.2.0/24

    r1r3_net:
      name: r1r3_net
      driver: bridge
      internal: true
      ipam:
        config:
          - subnet: 10.1.3.0/24

    r2r3_net:
      name: r2r3_net
      driver: bridge
      internal: true
      ipam:
        config:
          - subnet: 10.2.3.0/24

  x-ceos-defaults: &ceos-defaults
    image: arista-ceos:4.33.1F
    platform: linux/amd64
    environment:
      - INTFTYPE=eth
      - MGMT_INTF=eth0
      - MAPETH0=1
      - ETBA=1
      - SKIP_ZEROTOUCH_BARRIER_IN_SYSDBINIT=1
      - CEOS=1
      - EOS_PLATFORM=ceoslab
      - container=docker
    privileged: true
    command: >
      /sbin/init
      systemd.setenv=INTFTYPE=eth
      systemd.setenv=MGMT_INTF=eth0
      systemd.setenv=MAPETH0=1
      systemd.setenv=ETBA=1
      systemd.setenv=SKIP_ZEROTOUCH_BARRIER_IN_SYSDBINIT=1
      systemd.setenv=CEOS=1
      systemd.setenv=EOS_PLATFORM=ceoslab
      systemd.setenv=container=docker

  services:
    netbox:
      container_name: netbox
      hostname: netbox
      ports:
        - 8000:8080
    r1:
      <<: *ceos-defaults
      hostname: r1
      container_name: r1
      depends_on:
        netbox:
          condition: service_healthy
      networks:
        default:
          ipv4_address: 172.20.0.101
        r1r2_net:
          ipv4_address: 10.1.2.11
        r1r3_net:
          ipv4_address: 10.1.3.11
      volumes:
        - ../lab/ceos-r1.flash:/mnt/flash/
    r2:
      <<: *ceos-defaults
      hostname: r2
      container_name: r2
      depends_on:
        netbox:
          condition: service_healthy
      networks:
        default:
          ipv4_address: 172.20.0.102
        r1r2_net:
          ipv4_address: 10.1.2.12
        r2r3_net:
          ipv4_address: 10.2.3.12
      volumes:
        - ../lab/ceos-r2.flash:/mnt/flash/
    r3:
      <<: *ceos-defaults
      hostname: r3
      container_name: r3
      depends_on:
        netbox:
          condition: service_healthy
      networks:
        default:
          ipv4_address: 172.20.0.103
        r1r3_net:
          ipv4_address: 10.1.3.13
        r2r3_net:
          ipv4_address: 10.2.3.13
      volumes:
        - ../lab/ceos-r3.flash:/mnt/flash/

  EOF


Run Environment
^^^^^^^^^^^^^^^

Now, let's run Netbox and the lab:

.. code:: none

  docker compose up -d

Ensure Netbox is accessible at http://localhost:8000/.

Create a superuser using the script:

.. code:: none

  docker compose run netbox python manage.py createsuperuser

For consistency, use ``annet`` for both the login and password. You can change these later if needed.

Try connecting to the cEOS CLI:

.. code:: none

  docker exec -it r1 Cli

Try connecting to cEOS via SSH using ``annet:annet``:

.. code:: none

  ssh annet@172.20.0.101

Update Netbox Database
^^^^^^^^^^^^^^^^^^^^^^

Annet uses data from Netbox to generate configurations. Ensure the data is in place before working with Annet.

1. In **Organisation/Site**, add a Site - name: ``lab``, slug: ``lab``.
2. In **Devices/Manufacturers**, add a Manufacturer - name: ``Arista``, slug: ``arista``.
3. In **Devices/Device Types**, add a Device Type - Manufacturer: ``Arista``, model: ``cEOS``, slug: ``ceos``.
4. In **Devices/Device Roles**, add a Device Role - name: ``switch``, slug: ``switch``, color: choose any.
5. In **Devices/Devices**, add three Devices:

   - name: ``r1.lab``, device role: ``switch``, device type: ``cEOS``, site: ``lab``;
   - name: ``r2.lab``, device role: ``switch``, device type: ``cEOS``, site: ``lab``;
   - name: ``r3.lab``, device role: ``switch``, device type: ``cEOS``, site: ``lab``.

6. For each device, add interfaces in **Add Components/Interfaces**:

   - name: ``Ethernet1``, type: ``1000Base-T``;
   - name: ``Ethernet2``, type: ``1000Base-T``;
   - name: ``Ethernet3``, type: ``1000Base-T``;
   - name: ``Management0``, type: ``1000Base-T``, Management only: ``True``.

7. For each device, add an IP address in the **Interfaces** tab:

   - device: ``r1.lab``, interface: ``Management0``, IP address: ``172.20.0.101/24``;
   - device: ``r2.lab``, interface: ``Management0``, IP address: ``172.20.0.102/24``;
   - device: ``r3.lab``, interface: ``Management0``, IP address: ``172.20.0.103/24``.

8. For each device, assign a **Primary IPv4** address. In edit mode, assign **Primary IPv4** to ``172.20.0.101``, ``172.20.0.102``, and ``172.20.0.103`` respectively.
9. Finally, create connections between devices following the topology. In the **Interfaces** tab, add cables between:

   - device: ``r1.lab``, interface: ``Ethernet1``, connected to device: ``r2.lab``, interface: ``Ethernet1``;
   - device: ``r1.lab``, interface: ``Ethernet2``, connected to device: ``r3.lab``, interface: ``Ethernet1``;
   - device: ``r2.lab``, interface: ``Ethernet2``, connected to device: ``r3.lab``, interface: ``Ethernet2``.

Annet Installation
------------------

Create a virtual environment and install Annet along with the required packages. We recommend using Python 3.12 or later.

.. code:: bash

  # go to root of your folder
  cd ..
  #
  # create and activate venv
  python3 -m venv .venv
  source .venv/bin/activate
  #
  # install packages
  pip install "annet[netbox]" gnetcli_adapter gnetclisdk

gnetcli
^^^^^^^

Before we start, we need to install the gnetcli server binary. You have two options here.

1. Use ``go install``

.. note:: This step requires Golang to be installed.

.. code:: bash

  export GOPATH=~/go
  export PATH=$PATH:$GOPATH/bin
  go install github.com/annetutil/gnetcli/cmd/gnetcli_server@latest

2. Download binary for your platform from https://github.com/annetutil/gnetcli/releases. Annet will use this binary, so ensure the folder containing it is added to your PATH environment variable. You can follow the example below:

.. code:: bash

  mkdir -p ~/go/bin
  tar -xf gnetcli_server-v1.0.79-darwin-amd64.tar.gz -C ~/go/bin
  export PATH=$PATH:~/go/bin


Annet Configuration
-------------------

Annet interacts with devices and Netbox, so we need to define:

1. Device credentials. For the lab environment, we use ``annet:annet``.
2. A Netbox token. Open Netbox, go to **Admins/API Tokens**, and add a new token for the user ``annet``.

Create folder for future annet generators:

.. code:: bash

  mkdir generators
  touch generators/__init__.py

Create configuration file:

.. code:: bash

  cat > annet_config.yaml <<EOF
  fetcher:
    default:
      adapter: gnetcli
      params: &gnetcli_params
        dev_login: annet
        dev_password: annet

  deployer:
    default:
      adapter: gnetcli
      params:
        <<: *gnetcli_params

  generators:
    default:
      - generators/__init__.py

  storage:
    netbox:
      adapter: netbox
      params:
        url: http://127.0.0.1:8000
        token: 0217a15128a1f8f66bac4b84b3edc5261ba33863
  context:
    default:
      fetcher: default
      deployer: default
      generators: default
      storage: netbox

  selected_context: default
  EOF

Define path to configuration file:

.. code:: bash

  export ANN_CONTEXT_CONFIG_PATH=annet_config.yaml

Let's check if everything works!

Try to get the Netbox device model:

.. code:: bash

  annet show device-dump r1.lab

Got a Netbox data serialized to the Device structure like this:

.. code:: none

  > annet show device-dump r1.lab
  device.asset_tag = None
  device.breed = 'eos4'
  device.created = datetime.datetime(2025, 1, 26, 12, 0, 14, 63670, tzinfo=tzutc())
  device.device_role.id = 1
  device.device_role.name = 'switch'
  device.device_type = DeviceType(id=1, manufacturer=Entity(id=1, name='Arista'), model='cEOS')
  device.display = 'r1.lab'
  device.face = None
  device.fqdn = 'r1.lab'
  device.hostname = 'r1.lab'
  device.hw.model = 'Arista cEOS'
  device.hw.soft = ''
  device.hw.vendor = 'arista'
  device.hw.Arista = True
  ...

Try to get the current configuration of a device:

.. code:: bash

  annet show current r1.lab

Got current device configuration as plain text:

.. code:: none

  > annet show current r1.lab
  # -------------------- r1.lab.cfg --------------------
  ! Command: show running-config
  ! device: r1 (cEOSLab, EOS-4.33.1F-39879738.4331F (engineering build))
  !
  no aaa root
  !
  username annet privilege 15 role network-admin secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.
  !
  switchport default mode routed
  !
  no service interface inactive port-id allocation disabled
  !
  transceiver qsfp default-mode 4x10G
  !
  service routing protocols model multi-agent
  !
  hostname r1
  !
  spanning-tree mode mstp
  !
  system l1
     unsupported speed action error
     unsupported error-correction action error
  !
  aaa authorization serial-console
  aaa authorization exec default local
  aaa authorization exec console none
  !
  interface Ethernet1
     no switchport
  !
  interface Ethernet2
     no switchport
  !
  interface Ethernet3
     no switchport
  !
  interface Management0
     ip address 172.20.0.101/24
  !
  ip routing
  !
  router multicast
     ipv4
        software-forwarding kernel
     !
     ipv6
        software-forwarding kernel
  !
  end

Let's Play with Annet
----------------------

Create First Generator
^^^^^^^^^^^^^^^^^^^^^^

For now, let's create a generator for interface descriptions.

Create a file ``generators/description.py``:

.. code:: python

  from annet.generators import PartialGenerator
  from annet.storage import Device


  class Description(PartialGenerator):
      """Generator of description on interfaces"""

      # tags allow more usefully execute set of generators
      TAGS = ["description", "iface"]

      # for partial generators there are two methods for each vendors should be:
      #  - acl_<vendor name>
      #  - run_<vendor name>
      def acl_arista(self, _: Device):
          """ACL for Arista devices"""

          return """
          interface
              description
          """

      def run_arista(self, device: Device):
          """Generator for Arista devices"""

          for interface in device.interfaces:
              if interface.connected_endpoints:
                  with self.block(f"interface {interface.name}"):
                      remote_device = interface.connected_endpoints[0].device.name.split(".")[0]
                      remote_iface = interface.connected_endpoints[0].name
                      yield f"description {remote_device}@{remote_iface}"

And update the file ``generators/__init__.py``:

.. code:: python

  from annet.generators import BaseGenerator
  from annet.storage import Storage

  from . import description


  def get_generators(store: Storage) -> list[BaseGenerator]:
      """All the generators should be returned by the function"""

      return [
          description.Description(store),
      ]

Check the list of generators:

.. code:: bash

  annet show generators

.. code:: none

  > annet show generators
  | PARTIAL-Class   | Tags               | Module                                              | Description                            |
  |-----------------+--------------------+-----------------------------------------------------+----------------------------------------|
  | Description     | description, iface | Users_gslv_annet_generators___init___py.description | Generator of description on interfaces |

Get the generated configuration for all three devices:

.. code:: bash

  annet gen -g description r1.lab r2.lab r3.lab

.. code:: none

  > annet gen -g description r1.lab r2.lab r3.lab
  # -------------------- r1.lab.cfg --------------------
  interface Ethernet1
    description r2@Ethernet1
  interface Ethernet2
    description r3@Ethernet1
  # -------------------- r2.lab.cfg --------------------
  interface Ethernet1
    description r1@Ethernet1
  interface Ethernet2
    description r3@Ethernet2
  # -------------------- r3.lab.cfg --------------------
  interface Ethernet1
    description r1@Ethernet2
  interface Ethernet2
    description r2@Ethernet2

Look at the diff:

.. code:: bash

  annet diff -g description r1.lab r2.lab r3.lab

.. code:: diff

  > annet diff -g description r1.lab r2.lab r3.lab
  # -------------------- r2.lab.cfg --------------------
    interface Ethernet1
  +   description r1@Ethernet1
    interface Ethernet2
  +   description r3@Ethernet2
  # -------------------- r3.lab.cfg --------------------
    interface Ethernet1
  +   description r1@Ethernet2
    interface Ethernet2
  +   description r2@Ethernet2
  # -------------------- r1.lab.cfg --------------------
    interface Ethernet1
  +   description r2@Ethernet1
    interface Ethernet2
  +   description r3@Ethernet1

And deploy it:

.. code:: bash

  annet deploy -g description r1.lab r2.lab r3.lab

Verify the result:

.. code:: none

  > ssh annet@172.20.0.101
  (annet@172.20.0.101) Password:
  Last login: Sun Jan 26 15:29:33 2025 from 172.20.0.0
  r1#sh int desc
  Interface                      Status         Protocol           Description
  Et1                            up             up                 r2@Ethernet1
  Et2                            up             up                 r3@Ethernet1
  Ma0                            up             up
  r1#

Extend Coverage
^^^^^^^^^^^^^^^

Thanks to ACL, we can add new configuration parts to Annet step by step without affecting other parts of the configuration.

Add generators for AAA, hostname, IP address, routing, and STP.

Create the following files:

``generators/aaa.py``:

.. code:: python

  from annet.generators import PartialGenerator
  from annet.storage import Device


  LOCAL_USERS = {
      "annet": {
          "privilege": 15,
          "role": "network-admin",
          "secret sha512": "$6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP."
      }

  }


  class Aaa(PartialGenerator):
      """Generator of AAA"""

      TAGS = ["aaa"]

      def acl_arista(self, _: Device):
          """ACL for Arista devices"""

          return """
          aaa
          username
          """

      def run_arista(self, _: Device):
          """Generator for Arista devices"""

          yield "no aaa root"
          yield "aaa authorization serial-console"
          yield "aaa authorization exec default local"
          yield "aaa authorization exec console none"

          for username, attributes in LOCAL_USERS.items():
              attributes_line = " ".join(f"{key} {value}" for key, value in attributes.items())
              yield f"username {username} {attributes_line}"

``generators/hostname.py``:

.. code:: python

  from annet.generators import PartialGenerator
  from annet.storage import Device


  class Hostname(PartialGenerator):
      """Generator of Hostname"""

      TAGS = ["hostname"]

      def acl_arista(self, _: Device):
          """ACL for Arista devices"""

          return """
          hostname
          """

      def run_arista(self, device: Device):
          """Generator for Arista devices"""
          yield f"hostname {device.hostname.split('.')[0]}"

``generators/ip_address.py``:

.. code:: python

  from annet.generators import PartialGenerator
  from annet.storage import Device

  class IpAddress(PartialGenerator):
      """Generator of IP addresses"""

      TAGS = ["routing", "iface"]

      def acl_arista(self, _: Device):
          """ACL for Arista devices"""

          return """
          interface
              ip address
              no switchport
          """

      def run_arista(self, device: Device):
          """Generator for Arista devices"""

          for interface in device.interfaces:
              with self.block(f"interface {interface.name}"):
                  for ip_address in interface.ip_addresses:
                      yield f"ip address {ip_address.address}"
                  if interface.name.startswith("Ethernet"):
                      yield "no switchport"

``generators/routing.py``:

.. code:: python

  from annet.generators import PartialGenerator
  from annet.storage import Device


  class Routing(PartialGenerator):
      """Generator of Routing"""

      TAGS = ["routing"]

      def acl_arista(self, _: Device):
          """ACL for Arista devices"""

          return """
          service routing
          ip routing
          """

      def run_arista(self, _: Device):
          """Generator for Arista devices"""

          yield "service routing protocols model multi-agent"
          yield "ip routing"

``generators/stp.py``:

.. code:: python

  from annet.generators import PartialGenerator
  from annet.storage import Device


  class Stp(PartialGenerator):
      """Generator of STP"""

      TAGS = ["stp"]

      def acl_arista(self, _: Device):
          """ACL for Arista devices"""

          return """
          spanning-tree
          """

      def run_arista(self, _: Device):
          """Generator for Arista devices"""

          yield "spanning-tree mode mstp"


Again, update ``generators/__init__.py``:

.. code:: python

  from annet.generators import BaseGenerator
  from annet.storage import Storage

  from . import aaa, description, hostname, ip_address, routing, stp


  def get_generators(store: Storage) -> list[BaseGenerator]:
      """All the generators should be returned by the function"""

      return [
          aaa.Aaa(store),
          description.Description(store),
          hostname.Hostname(store),
          ip_address.IpAddress(store),
          routing.Routing(store),
          stp.Stp(store),
      ]

Look at the list of generators:

.. code:: bash

  annet show generators

.. code:: none

  > annet show generators
  | PARTIAL-Class   | Tags               | Module                                                  | Description                                          |
  |-----------------+--------------------+---------------------------------------------------------+------------------------------------------------------|
  | Aaa             | aaa                | Users_gslv_dev_annet_generators___init___py.aaa         | Generator of AAA                                     |
  | Description     | description, iface | Users_gslv_dev_annet_generators___init___py.description | Generator of description on interfaces               |
  | Hostname        | hostname           | Users_gslv_dev_annet_generators___init___py.hostname    | Generator of Hostname                                |
  | IpAddress       | routing, iface     | Users_gslv_dev_annet_generators___init___py.ip_address  | Generator of IP addresses                            |
  | Routing         | routing            | Users_gslv_dev_annet_generators___init___py.routing     | Generator of Routing                                 |
  | Stp             | stp                | Users_gslv_dev_annet_generators___init___py.stp         | Generator of STP                                     |

Look at the diff:

.. code:: bash

  annet diff r1.lab r1.lab r2.lab r3.lab

.. code:: diff

  > annet diff r1.lab r1.lab r2.lab r3.lab
  # -------------------- r1.lab.cfg --------------------
  - username annet privilege 15 role network-admin secret sha512 $6$6NGBAcZ7vJqeAvgb$X5i/S/PsC3f9Rl8VePUY4cPB7BA0btRIUQ5fTvh9f0nmc2H4skUOuq7u62ekrwAKcrFR/7XArVh19F3N8n1GR0
  + username annet privilege 15 role network-admin secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.
  # -------------------- r3.lab.cfg --------------------
  - username annet privilege 15 role network-admin secret sha512 $6$MemUeEzIROMxkxaJ$n.TrV5PWlkEH0S7YP0W9c44cVGhaF.j29kRah1JOo/r0ZorN13ADWHK9VP29ODZd234eq76Xa.nZCfSQJpz0O.
  + username annet privilege 15 role network-admin secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.
  # -------------------- r2.lab.cfg --------------------
  - username annet privilege 15 role network-admin secret sha512 $6$l03Ecws7s3guk5ef$c3.NffpXlhDdWxwgnjrlnLOXl0c8dYC8F4R7D3O9eLLLi5aPgHuifSlCdnEgsSrDqRUDbExKnLwQZCwuO4DDO.
  + username annet privilege 15 role network-admin secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.

We notice that the user ``annet`` has a different hash on the routers. This is fine because we created the user ``annet`` with a plain text password in the default configuration.

Look at the patch:

.. code:: bash

  annet patch r1.lab r2.lab r3.lab

.. code:: none

  > annet patch r1.lab r2.lab r3.lab
  # -------------------- r1.lab.patch --------------------
  username annet secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.
  # -------------------- r2.lab.patch --------------------
  username annet secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.
  # -------------------- r3.lab.patch --------------------
  username annet secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.

And deploy it:

.. code:: bash

  annet deploy r1.lab r2.lab r3.lab

Again look at the diff:

.. code:: bash

  annet diff r1.lab r2.lab r3.lab

No diff found - everything is ok for now.

Look at the diff without ACL to check what's configurations lines is still not covered by annet:

.. code:: bash

  annet diff r1.lab r2.lab r3.lab --no-acl

.. code:: diff

  > annet diff r1.lab r2.lab r3.lab --no-acl
  # -------------------- r1.lab.cfg, r2.lab.cfg, r3.lab.cfg --------------------
  - switchport default mode routed
  - transceiver qsfp default-mode 4x10G
  - system l1
  -   unsupported speed action error
  -   unsupported error-correction action error
  - router multicast
  -   ipv4
  -     software-forwarding kernel
  -   ipv6
  -     software-forwarding kernel
  - end
  - no service interface inactive port-id allocation disabled

We've skipped them, but if you want, you can create new generators to add them to Annet.

BGP Configuration
^^^^^^^^^^^^^^^^^

Annet has a brilliant tool for creating BGP peers — mesh. It allows us to create templates for BGP peers and apply them to Netbox devices. Annet takes connections between devices from Netbox and passes them through templates. As a result, we get a list of local and remote peer pairs. This list can be used in generators.
Some people call mesh templates "network design in Python code!"

Imagine we need to have BGP sessions between ``r1``, ``r2``, and ``r3`` over direct links to exchange IPv4 routes.

Create a mesh template ``generators/mesh_views/routers.py``:

.. code:: python

  from annet.mesh import DirectPeer, GlobalOptions, MeshRulesRegistry, MeshSession


  # create registry, short name allows skip domain parts in templates
  registry = MeshRulesRegistry(match_short_name=True)

  # define base asnum
  BASE_ASNUM = 65000


  # define global options of the host
  @registry.device("r{num}")
  def global_options(global_opts: GlobalOptions):
      """Define global options"""

      global_opts.router_id = f"1.1.1.{global_opts.match.num}"


  # define peering between routers, we use different names for num, because if they have the same names they have to be with the same value
  # e.g. ("r{num}", "r{num}") means the only peering between r1 and r1, r2 and r2 and r3 and r3 passed though templates
  @registry.direct("r{num1}", "r{num2}")
  def routers_peerings(router1: DirectPeer, router2: DirectPeer, session: MeshSession):
      """Define peering between routers for IPv4 unicast family"""

      # find minimal and maximum numbers of routers
      min_num = min(router1.match.num1, router2.match.num2)
      max_num = max(router1.match.num1, router2.match.num2)

      # define first router params
      router1.asnum = BASE_ASNUM + router1.match.num1
      router1.addr = f"10.{min_num}.{max_num}.1{router1.match.num1}/24"
      router1.families = {"ipv4_unicast"}
      router1.group_name = "ROUTERS"

      # define second router params
      router2.asnum = BASE_ASNUM + router2.match.num2
      router2.addr = f"10.{min_num}.{max_num}.1{router2.match.num2}/24"
      router2.families = {"ipv4_unicast"}
      router2.group_name = "ROUTERS"

Create an init file ``generators/mesh_views/__init__.py``:

.. code:: python

  from annet.mesh import MeshRulesRegistry

  from . import routers


  registry = MeshRulesRegistry(match_short_name=True)
  registry.include(routers.registry)

Now, we should use mesh data in generators. First, update the IpAddress generator ``generators/ip_address.py``:

.. code:: python

  from annet.generators import PartialGenerator
  # import mesh executor to get access to mesh data
  from annet.mesh import MeshExecutor
  from annet.storage import Device

  # import mesh registry
  from .mesh_views import registry


  class IpAddress(PartialGenerator):
      """Generator of IP addresses"""

      TAGS = ["routing", "iface"]

      def acl_arista(self, _: Device):
          """ACL for Arista devices"""

          return """
          interface
              ip address
              no switchport
          """

      def run_arista(self, device: Device):
          """Generator for Arista devices"""

          # update device storage with mesh data
          executor: MeshExecutor = MeshExecutor(registry, device.storage)
          executor.execute_for(device)
          for interface in device.interfaces:
              with self.block(f"interface {interface.name}"):
                  for ip_address in interface.ip_addresses:
                      yield f"ip address {ip_address.address}"
                  if interface.name.startswith("Ethernet"):
                      yield "no switchport"

Add a new generator for BGP configuration — ``generators/bgp.py``:

.. code:: python

  from typing import Optional

  from annet.bgp_models import ASN, BgpConfig
  from annet.generators import PartialGenerator
  from annet.mesh.executor import MeshExecutor
  from annet.storage import Device

  from .mesh_views import registry


  def bgp_asnum(mesh_data: BgpConfig) -> Optional[ASN]:
      """Return AS number parse mesh bgp peers"""
      if not mesh_data:
          return None

      # AS can be defined in global options
      if mesh_data.global_options.local_as:
          return mesh_data.global_options.local_as

      # If AS is not defined in global options, look for it in peers
      asnum: set[ASN] = set()
      for peer in mesh_data.peers:
          asnum.add(peer.options.local_as)

      if len(asnum) == 1:
          return asnum.pop()
      elif len(asnum) > 1:
          raise RuntimeError(f"AutonomusSystemIsNotDefined: {str(asnum)}")

      return None


  class Bgp(PartialGenerator):
      """Generator of BGP process and neighbors"""

      TAGS = ["bgp", "routing"]

      def acl_arista(self, _: Device) -> str:
          """ACL for Arista devices"""

          return """
          router bgp
              router-id
              neighbor
              redistribute connected
              maximum-paths
              address-family
                  neighbor
          """

      def run_arista(self, device: Device):
          """Generator for Arista devices"""

          executor: MeshExecutor = MeshExecutor(registry, device.storage)
          mesh_data: BgpConfig = executor.execute_for(device)

          rid: Optional[str] = mesh_data.global_options.router_id if mesh_data.global_options.router_id else None
          asnum: Optional[ASN] = bgp_asnum(mesh_data)

          if not asnum or not rid:
              return
          with self.block("router bgp", asnum):
              yield "router-id", rid

              # group configuration
              for peer in mesh_data.peers:
                  yield "neighbor", peer.group_name, "peer group"

                  # use conditional context for group configuration
                  with self.block_if("address-family ipv4", condition=("ipv4_unicast" in peer.families)):
                      yield "neighbor", peer.group_name, "activate"

              # peer configuration
              for peer in mesh_data.peers:
                  yield "neighbor", peer.addr, "peer group", peer.group_name
                  yield "neighbor", peer.addr, "remote-as", peer.remote_as

Again, update ``generators/__init__.py``:

.. code:: python

  from annet.generators import BaseGenerator
  from annet.storage import Storage

  from . import aaa, bgp, description, hostname, ip_address, routing, stp


  def get_generators(store: Storage) -> list[BaseGenerator]:
      """All the generators should be returned by the function"""

      return [
          aaa.Aaa(store),
          bgp.Bgp(store),
          description.Description(store),
          hostname.Hostname(store),
          ip_address.IpAddress(store),
          routing.Routing(store),
          stp.Stp(store),
      ]

Check the list of generators:

.. code:: bash

  annet show generators

.. code:: none

  > annet show generators
  | PARTIAL-Class   | Tags               | Module                                                  | Description                                          |
  |-----------------+--------------------+---------------------------------------------------------+------------------------------------------------------|
  | Aaa             | aaa                | Users_gslv_dev_annet_generators___init___py.aaa         | Generator of AAA                                     |
  | Bgp             | bgp, routing       | Users_gslv_dev_annet_generators___init___py.bgp         | Generator of BGP process and neighbors               |
  | Description     | description, iface | Users_gslv_dev_annet_generators___init___py.description | Generator of description on interfaces               |
  | Hostname        | hostname           | Users_gslv_dev_annet_generators___init___py.hostname    | Generator of Hostname                                |
  | IpAddress       | routing, iface     | Users_gslv_dev_annet_generators___init___py.ip_address  | Generator of IP addresses                            |
  | Routing         | routing            | Users_gslv_dev_annet_generators___init___py.routing     | Generator of Routing                                 |
  | Stp             | stp                | Users_gslv_dev_annet_generators___init___py.stp         | Generator of STP                                     |


Check the diff:

.. code:: bash

  annet diff r1.lab r2.lab r3.lab

.. code:: diff

  > annet diff r1.lab r2.lab r3.lab
  # -------------------- r1.lab.cfg --------------------
    interface Ethernet1
  +   ip address 10.1.2.11/24
    interface Ethernet2
  +   ip address 10.1.3.11/24
  + router bgp 65001
  +   router-id 1.1.1.1
  +   neighbor ROUTERS peer group
  +   address-family ipv4
  +     neighbor ROUTERS activate
  +   neighbor 10.1.2.12 peer group ROUTERS
  +   neighbor 10.1.2.12 remote-as 65002
  +   neighbor 10.1.3.13 peer group ROUTERS
  +   neighbor 10.1.3.13 remote-as 65003
  # -------------------- r2.lab.cfg --------------------
    interface Ethernet1
  +   ip address 10.1.2.12/24
    interface Ethernet2
  +   ip address 10.2.3.12/24
  + router bgp 65002
  +   router-id 1.1.1.2
  +   neighbor ROUTERS peer group
  +   address-family ipv4
  +     neighbor ROUTERS activate
  +   neighbor 10.1.2.11 peer group ROUTERS
  +   neighbor 10.1.2.11 remote-as 65001
  +   neighbor 10.2.3.13 peer group ROUTERS
  +   neighbor 10.2.3.13 remote-as 65003
  # -------------------- r3.lab.cfg --------------------
    interface Ethernet1
  +   ip address 10.1.3.13/24
    interface Ethernet2
  +   ip address 10.2.3.13/24
  + router bgp 65003
  +   router-id 1.1.1.3
  +   neighbor ROUTERS peer group
  +   address-family ipv4
  +     neighbor ROUTERS activate
  +   neighbor 10.1.3.11 peer group ROUTERS
  +   neighbor 10.1.3.11 remote-as 65001
  +   neighbor 10.2.3.12 peer group ROUTERS
  +   neighbor 10.2.3.12 remote-as 65002

Looks great! Deploy it to the devices:

.. code:: bash

  annet deploy r1.lab r2.lab r3.lab

Check the result:

.. code:: none

  > ssh annet@172.20.0.101
  (annet@172.20.0.101) Password:
  Last login: Tue Feb  4 05:27:51 2025 from 172.20.0.0
  r1#sh ip bgp sum
  BGP summary information for VRF default
  Router identifier 1.1.1.1, local AS number 65001
  Neighbor Status Codes: m - Under maintenance
    Neighbor  V AS           MsgRcvd   MsgSent  InQ OutQ  Up/Down State   PfxRcd PfxAcc
    10.1.2.12 4 65002              4         4    0    0 00:00:05 Estab   0      0
    10.1.3.13 4 65003              4         4    0    0 00:00:05 Estab   0      0
  r1#

Redistribute Connected
^^^^^^^^^^^^^^^^^^^^^^

Let's go deeper. The task now is to configure the redistribution of connected networks into BGP.

Create a ``Loopback10`` interface on each router with an address in Netbox, following the table:

+--------+--------------------+
| Router | Loopback10 address |
+========+====================+
|   r1   | ``192.168.1.1/24`` |
+--------+--------------------+
|   r2   | ``192.168.2.1/24`` |
+--------+--------------------+
|   r3   | ``192.168.3.1/24`` |
+--------+--------------------+

Go to the router page, click **Add Components**, and choose **Interfaces**. Use the name ``Loopback10`` and type ``Virtual``. Next, add an IP address to the interface following the table.

Now, we need to add the redistribution of connected networks to BGP in the mesh. Additionally, we want to filter prefixes between routers!

To do this, update the file ``generators/mesh_views/routers.py``:

.. code:: python

  from annet.bgp_models import Redistribute
  from annet.mesh import DirectPeer, GlobalOptions, MeshRulesRegistry, MeshSession


  # create registry, short name allows skip domain parts in templates
  registry = MeshRulesRegistry(match_short_name=True)

  # define base asnum
  BASE_ASNUM = 65000


  # define global options of the host
  @registry.device("r{num}")
  def global_options(global_opts: GlobalOptions):
      """Define global options"""

      global_opts.router_id = f"1.1.1.{global_opts.match.num}"

      # define redistribute
      global_opts.ipv4_unicast.redistributes = (
          Redistribute(protocol="connected", policy="IMPORT_CONNECTED"),
      )


  # define peering between routers, we use different names for num, because if they have the same names they have to be with the same value
  # e.g. ("r{num}", "r{num}") means the only peering between r1 and r1, r2 and r2 and r3 and r3 passed though templates
  @registry.direct("r{num1}", "r{num2}")
  def routers_peerings(router1: DirectPeer, router2: DirectPeer, session: MeshSession):
      """Define peering between routers for IPv4 unicast family"""

      # find minimal and maximum numbers of routers
      min_num = min(router1.match.num1, router2.match.num2)
      max_num = max(router1.match.num1, router2.match.num2)

      # define first router params
      router1.asnum = BASE_ASNUM + router1.match.num1
      router1.addr = f"10.{min_num}.{max_num}.1{router1.match.num1}/24"
      router1.families = {"ipv4_unicast"}
      router1.group_name = "ROUTERS"
      router1.import_policy = "ROUTERS_IMPORT"
      router1.export_policy = "ROUTERS_EXPORT"
      router1.send_community = True

      # define second router params
      router2.asnum = BASE_ASNUM + router2.match.num2
      router2.addr = f"10.{min_num}.{max_num}.1{router2.match.num2}/24"
      router2.families = {"ipv4_unicast"}
      router2.group_name = "ROUTERS"
      router2.import_policy = "ROUTERS_IMPORT"
      router2.export_policy = "ROUTERS_EXPORT"
      router2.send_community = True

You'll notice that the redistribution has a link to the policy ``IMPORT_CONNECTED``. This can be defined by a new generator as plain config, but Annet has a special tool for working with policies. Currently, only Huawei VRP, Arista EOS, and FRR (2025q3) are supported, but we expect this to be updated soon.

First, create a new module by creating an empty file ``generators/rpl_views/__init__.py``. This module will contain policies and their elements.

Create a Python file with the policies — ``generators/rpl_views/route_map.py``:

.. code:: python

  from annet.adapters.netbox.common.models import NetboxDevice
  from annet.rpl import R, Route, RouteMap


  # create routemap decorator
  routemap = RouteMap[NetboxDevice]()


  # define redistribute policy
  @routemap
  def IMPORT_CONNECTED(_: NetboxDevice, route: Route):
      with route(
              R.protocol == "connected",
              R.match_v4("LOCAL_NETS", or_longer=(16, 24)),
              number=10
      ) as rule:
          rule.community.set("ADVERTISE")
          rule.allow()
      with route(number=20) as rule:
          rule.deny()


  @routemap
  def ROUTERS_IMPORT(_: NetboxDevice, route: Route):
      with route(
              R.match_v4("LOCAL_NETS", or_longer=(16, 24)),  # custom ge/le
              R.community.has("ADVERTISE"),
              number=10
      ) as rule:
          rule.allow()
      with route(number=20) as rule:
          rule.deny()


  @routemap
  def ROUTERS_EXPORT(_: NetboxDevice, route: Route):
      with route(
              R.community.has("ADVERTISE"),
              number=10
      ) as rule:
          rule.allow()
      with route(number=20) as rule:
          rule.deny()

For more details on how to use RPL, refer to the `documentation <https://annetutil.github.io/annet/main/rpl/index.html>`__.

The next two files contain community and prefix list definitions.

``generators/rpl_views/community.py``:

.. code:: python

  from annet.rpl_generators import CommunityList


  COMMUNITIES = [
      CommunityList(name="ADVERTISE", members=["65000:1"])
  ]

``generators/rpl_views/prefix_list.py``:

.. code:: python

  from annet.rpl_generators import IpPrefixList


  PREFIX_LISTS = [
      IpPrefixList(name="LOCAL_NETS", members=["192.168.0.0/16"])
  ]

This doesn't look too difficult, but we need to create three generators for:

- Policy
- Community
- Prefix list

Policy generator — ``generators/route_map.py``:

.. code:: python

  from typing import Any

  from annet.mesh import MeshExecutor
  from annet.rpl import RoutingPolicy
  from annet.rpl_generators import (
      AsPathFilter,
      CommunityList,
      IpPrefixList,
      RDFilter,
      RoutingPolicyGenerator,
      get_policies,
  )

  from .mesh_views import registry
  from .rpl_views import community, prefix_list, route_map


  # the class inherited from RoutingPolicyGenerator which has already has generators for some vendors,
  # but we should define some required methods
  class RouteMap(RoutingPolicyGenerator):
      """Generator of Routing Policy"""

      # mandatory method to get policies, in our case it takes policies mentioned in mesh
      def get_policies(self, device: Any) -> list[RoutingPolicy]:
          """Get mentioned in mesh policies"""

          return get_policies(
              routemap=route_map.routemap,
              device=device,
              mesh_executor=MeshExecutor(
                  registry,
                  self.storage,
              ),
          )

      # mandatory method to get communities
      def get_community_lists(self, device: Any) -> list[CommunityList]:
          """Get community lists"""

          return community.COMMUNITIES

      # mandatory method to get prefix list
      def get_prefix_lists(self, _: Any) -> list[IpPrefixList]:
          """Get prefix lists, not used right now"""

          return prefix_list.PREFIX_LISTS

      # mandatory method which not used right now
      def get_as_path_filters(self, _: Any) -> list[AsPathFilter]:
          """Get as-path filters, not used right now"""

          return []

      # mandatory method which not used right now
      def get_rd_filters(self, _: Any) -> list[RDFilter]:
          """Get rd filters, not used right now"""

          return []

Community generator — ``generators/community.py``:

.. code:: python

  from typing import Any

  from annet.mesh import MeshExecutor
  from annet.rpl import RoutingPolicy
  from annet.rpl_generators import CommunityList, CommunityListGenerator, get_policies

  from .mesh_views import registry
  from .rpl_views import community, route_map


  class Community(CommunityListGenerator):
      """Generator of Community Lists"""

      # mandatory method to get policies, in our case it takes policies mentioned in mesh
      def get_policies(self, device: Any) -> list[RoutingPolicy]:
          """Get mentioned in mesh policies"""

          return get_policies(
              routemap=route_map.routemap,
              device=device,
              mesh_executor=MeshExecutor(
                  registry,
                  self.storage,
              ),
          )

      # mandatory method to get communities
      def get_community_lists(self, _: Any) -> list[CommunityList]:
          """Get community lists"""

          return community.COMMUNITIES

Prefix list generator — ``generators/prefix_list.py``:

.. code:: python

  from typing import Any

  from annet.mesh import MeshExecutor
  from annet.rpl import RoutingPolicy
  from annet.rpl_generators import IpPrefixList, PrefixListFilterGenerator, get_policies

  from .mesh_views import registry
  from .rpl_views import prefix_list, route_map


  class PrefixList(PrefixListFilterGenerator):
      """Generator of Community Lists"""

      # mandatory method to get policies, in our case it takes policies mentioned in mesh
      def get_policies(self, device: Any) -> list[RoutingPolicy]:
          """Get mentioned in mesh policies"""

          return get_policies(
              routemap=route_map.routemap,
              device=device,
              mesh_executor=MeshExecutor(
                  registry,
                  self.storage,
              ),
          )

      # mandatory method to get communities
      def get_prefix_lists(self, _: Any) -> list[IpPrefixList]:
          """Get prefix lists, not used right now"""

          return prefix_list.PREFIX_LISTS

Again, update ``generators/__init__.py``:

.. code:: python

  from annet.generators import BaseGenerator
  from annet.storage import Storage

  from . import (
      aaa,
      bgp,
      community,
      description,
      hostname,
      ip_address,
      prefix_list,
      route_map,
      routing,
      stp,
  )


  def get_generators(store: Storage) -> list[BaseGenerator]:
      """All the generators should be returned by the function"""

      return [
          aaa.Aaa(store),
          bgp.Bgp(store),
          community.Community(store),
          description.Description(store),
          hostname.Hostname(store),
          ip_address.IpAddress(store),
          prefix_list.PrefixList(store),
          route_map.RouteMap(store),
          routing.Routing(store),
          stp.Stp(store),
      ]

Don't forget to update the BGP generator to support import/export policies and send communities — ``generators/bgp.py``:

.. code:: python

  from typing import Optional

  from annet.bgp_models import ASN, BgpConfig
  from annet.generators import PartialGenerator
  from annet.mesh.executor import MeshExecutor
  from annet.storage import Device

  from .mesh_views import registry


  def bgp_asnum(mesh_data: BgpConfig) -> Optional[ASN]:
      """Return AS number parse mesh bgp peers"""
      if not mesh_data:
          return None

      # AS can be defined in global options
      if mesh_data.global_options.local_as:
          return mesh_data.global_options.local_as

      # If AS is not defined in global options, look for it in peers
      asnum: set[ASN] = set()
      for peer in mesh_data.peers:
          asnum.add(peer.options.local_as)

      if len(asnum) == 1:
          return asnum.pop()
      elif len(asnum) > 1:
          raise RuntimeError(f"AutonomusSystemIsNotDefined: {str(asnum)}")

      return None


  class Bgp(PartialGenerator):
      """Partial generator class of BGP process and neighbors"""

      TAGS = ["bgp", "routing"]

      def acl_arista(self, _: Device) -> str:
          """ACL for Arista devices"""

          return """
          router bgp
              router-id
              neighbor
              maximum-paths
              address-family
                  redistribute
                  neighbor
          """

      def run_arista(self, device: Device):
          """Generator for Arista devices"""

          executor: MeshExecutor = MeshExecutor(registry, device.storage)
          mesh_data: BgpConfig = executor.execute_for(device)

          rid: Optional[str] = mesh_data.global_options.router_id if mesh_data.global_options.router_id else None
          asnum: Optional[ASN] = bgp_asnum(mesh_data)

          if not asnum or not rid:
              return
          with self.block("router bgp", asnum):
              yield "router-id", rid

              # redistribute
              with self.block("address-family ipv4"):
                  if mesh_data.global_options and mesh_data.global_options.ipv4_unicast and \
                          mesh_data.global_options.ipv4_unicast.redistributes:
                      for redistribute in mesh_data.global_options.ipv4_unicast.redistributes:
                          yield "redistribute", redistribute.protocol, "" \
                              if not redistribute.policy else f"route-map {redistribute.policy}"

              # group configuration
              for peer in mesh_data.peers:
                  yield "neighbor", peer.group_name, "peer group"

                  # import/export policies
                  if peer.import_policy:
                      yield "neighbor", peer.group_name, "route-map", peer.import_policy, "in"
                  if peer.export_policy:
                      yield "neighbor", peer.group_name, "route-map", peer.export_policy, "out"

                  if peer.options.send_community:
                      yield "neighbor", peer.group_name, "send-community"

                  # use conditional context for group configuration
                  with self.block_if("address-family ipv4", condition=("ipv4_unicast" in peer.families)):
                      yield "neighbor", peer.group_name, "activate"

              # peer configuration
              for peer in mesh_data.peers:
                  yield "neighbor", peer.addr, "peer group", peer.group_name
                  yield "neighbor", peer.addr, "remote-as", peer.remote_as

Let's check the diff:

.. code:: bash

  annet diff r1.lab

.. code:: diff

  > annet diff r1.lab
  # -------------------- r1.lab.cfg --------------------
  + interface Loopback10
  +   ip address 192.168.1.1/24
  + ip prefix-list LOCAL_NETS_16_24
  +   seq 10 permit 192.168.0.0/16 ge 16 le 24
  + ip community-list ADVERTISE permit 65000:1
  + route-map IMPORT_CONNECTED permit 10
  +   match source-protocol connected
  +   match ip address prefix-list LOCAL_NETS_16_24
  +   set community community-list ADVERTISE
  + route-map IMPORT_CONNECTED deny 20
  + route-map ROUTERS_IMPORT permit 10
  +   match ip address prefix-list LOCAL_NETS_16_24
  +   match community ADVERTISE
  + route-map ROUTERS_IMPORT deny 20
  + route-map ROUTERS_EXPORT permit 10
  +   match community ADVERTISE
  + route-map ROUTERS_EXPORT deny 20
    router bgp 65001
      address-family ipv4
  +     redistribute connected route-map IMPORT_CONNECTED
  +   neighbor ROUTERS route-map ROUTERS_IMPORT in
  +   neighbor ROUTERS route-map ROUTERS_EXPORT out
  +   neighbor ROUTERS send-community

And the patch:

.. code:: bash

  annet patch r1.lab

.. code:: none

  > annet patch r1.lab
  # -------------------- r1.lab.patch --------------------
  interface Loopback10
    ip address 192.168.1.1/24
    exit
  ip community-list ADVERTISE permit 65000:1
  ip prefix-list LOCAL_NETS_16_24
    seq 10 permit 192.168.0.0/16 ge 16 le 24
    exit
  route-map IMPORT_CONNECTED permit 10
    match source-protocol connected
    match ip address prefix-list LOCAL_NETS_16_24
    set community community-list ADVERTISE
    exit
  route-map IMPORT_CONNECTED deny 20
    exit
  route-map ROUTERS_IMPORT permit 10
    match ip address prefix-list LOCAL_NETS_16_24
    match community ADVERTISE
    exit
  route-map ROUTERS_IMPORT deny 20
    exit
  route-map ROUTERS_EXPORT permit 10
    match community ADVERTISE
    exit
  route-map ROUTERS_EXPORT deny 20
    exit
  router bgp 65001
    address-family ipv4
      redistribute connected route-map IMPORT_CONNECTED
      exit
    neighbor ROUTERS route-map ROUTERS_IMPORT in
    neighbor ROUTERS route-map ROUTERS_EXPORT out
    neighbor ROUTERS send-community
    exit

Deploy it on all three routers:

.. code:: bash

  annet deploy r1.lab r2.lab r3.lab

Check the result:

.. code:: none

  > ssh annet@172.20.0.101
  (annet@172.20.0.101) Password:
  Last login: Wed Feb  5 19:44:08 2025 from 172.20.0.0
  r1#sh ip bgp
  BGP routing table information for VRF default
  Router identifier 1.1.1.1, local AS number 65001
  Route status codes: s - suppressed contributor, * - valid, > - active, E - ECMP head, e - ECMP
                      S - Stale, c - Contributing to ECMP, b - backup, L - labeled-unicast
                      % - Pending best path selection
  Origin codes: i - IGP, e - EGP, ? - incomplete
  RPKI Origin Validation codes: V - valid, I - invalid, U - unknown
  AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

            Network                Next Hop              Metric  AIGP       LocPref Weight  Path
   * >      192.168.1.0/24         -                     -       -          -       0       i
   * >      192.168.2.0/24         10.1.2.12             0       -          100     0       65002 i
   *        192.168.2.0/24         10.1.3.13             0       -          100     0       65003 65002 i
   * >      192.168.3.0/24         10.1.3.13             0       -          100     0       65003 i
   *        192.168.3.0/24         10.1.2.12             0       -          100     0       65002 65003 i
  r1#

Indirect BGP
^^^^^^^^^^^^

We're going to create IS-IS peering between ``r2`` and ``r3`` to exchange ``Loopback0`` addresses. After that, we'll establish indirect BGP peering between ``r2`` and ``r3`` instead of direct peering. We'll also change the ASN on ``r2`` and ``r3`` to ``65004``.

The details are presented in the diagram:

::

                  ╔════════╗
             Eth1 ║AS 65001║ Eth2
        ┌─────────║   r1   ║──────────┐
        │     .11 ║        ║ .11      │
        │         ╚════════╝          │
        │                             │
   10.1.2.0/24                   10.1.3.0/24
        │                             │
        │                             │
   Eth1 │ .12                     .13 │ Eth1
   ╔════════╗                    ╔════════╗
   ║AS 65004║ Eth2   IS-IS  Eth2 ║AS 65004║
   ║   r2   ║────────────────────║   r3   ║
   ║        ║.12  10.2.3.0/24 .13║        ║
   ╚════════╝                    ╚════════╝
       Lo0                           Lo0
   1.1.1.2/32                    1.1.1.3/32
        |                             |
        |                             |
        +------------iBGP-------------+

First, we need to change the mesh. Here are the steps:

1. Add a ``Loopback0`` interface with IP addresses to ``r2`` and ``r3``, following the diagram.
2. Disable direct peering between ``r2`` and ``r3``.
3. Create a simple policy ``PERMIT_ANY`` for indirect peering.
4. Create indirect peering between ``r2`` and ``r3`` using the ``Loopback0`` interfaces.

To add a new loopback interface, repeat the steps from the **Redistribute Connected** section. Use addresses form the table:

+--------+--------------------+
| Router | Loopback0 address  |
+========+====================+
|   r2   | ``1.1.1.2/32``     |
+--------+--------------------+
|   r3   | ``1.1.1.3/32``     |
+--------+--------------------+

Disabling direct peering is easy — just add an additional condition that returns nothing. Configuring indirect peering requires using the ``@registry.indirect`` decorator. Here's the updated mesh—``generators/mesh_views/routers.py``:

.. code:: python

  from annet.bgp_models import Redistribute
  from annet.mesh import (
      DirectPeer,
      GlobalOptions,
      IndirectPeer,
      MeshRulesRegistry,
      MeshSession,
  )


  # create registry, short name allows skip domain parts in templates
  registry = MeshRulesRegistry(match_short_name=True)

  # define base asnum
  BASE_ASNUM = 65000


  # define global options of the host
  @registry.device("r{num}")
  def global_options(global_opts: GlobalOptions):
      """Define global options"""

      global_opts.router_id = f"1.1.1.{global_opts.match.num}"

      # define redistribute
      global_opts.ipv4_unicast.redistributes = (
          Redistribute(protocol="connected", policy="IMPORT_CONNECTED"),
      )


  # define peering between routers, we use different names for num, because if they have the same names they have to be with the same value
  # e.g. ("r{num}", "r{num}") means the only peering between r1 and r1, r2 and r2 and r3 and r3 passed though templates
  @registry.direct("r{num1}", "r{num2}")
  def routers_peerings(router1: DirectPeer, router2: DirectPeer, _: MeshSession):
      """Define peering between routers for IPv4 unicast family"""

      # disable direct peering between r2 and r3
      if (router1.match.num1 == 2 and router2.match.num2 == 3
              or router1.match.num1 == 3 and router2.match.num2 == 2):
          return

      # find minimal and maximum numbers of routers
      min_num = min(router1.match.num1, router2.match.num2)
      max_num = max(router1.match.num1, router2.match.num2)

      # define first router params
      router1.asnum = BASE_ASNUM + 4 if router1.match.num1 in (2, 3) else BASE_ASNUM + router1.match.num1
      router1.addr = f"10.{min_num}.{max_num}.1{router1.match.num1}/24"
      router1.families = {"ipv4_unicast"}
      router1.group_name = "ROUTERS"
      router1.import_policy = "ROUTERS_IMPORT"
      router1.export_policy = "ROUTERS_EXPORT"
      router1.send_community = True

      # define second router params
      router2.asnum = BASE_ASNUM + 4 if router2.match.num2 in (2, 3) else BASE_ASNUM + router2.match.num2
      router2.addr = f"10.{min_num}.{max_num}.1{router2.match.num2}/24"
      router2.families = {"ipv4_unicast"}
      router2.group_name = "ROUTERS"
      router2.import_policy = "ROUTERS_IMPORT"
      router2.export_policy = "ROUTERS_EXPORT"
      router2.send_community = True


  # define indirect between routers r2 and r3, note that we use colon after match name.
  #  it means that after colum follow regex, by default regex is any digit - '\d+',
  #  but for now we want to set specific numbers. also indirect peering do not relies on connection in netbox,
  #  since we should define ifname and addr from exited interface
  @registry.indirect("r{num1:2}", "r{num2:3}")
  def routers_indirect_peerings(router1: IndirectPeer, router2: IndirectPeer, _: MeshSession):
      """Define indirect peering between routers r2 and r3 for IPv4 unicast family"""

      for device in (router1, router2):
          for iface in device.device.interfaces:
              if iface.name == "Loopback0" and iface.type.value == "virtual" and iface.ip_addresses:
                  device.ifname = iface.name
                  device.addr = iface.ip_addresses[0].address

      # define first router params
      router1.asnum = BASE_ASNUM + 4
      router1.families = {"ipv4_unicast"}
      router1.group_name = "INTERNAL"
      router1.import_policy = "PERMIT_ANY"
      router1.export_policy = "PERMIT_ANY"
      router1.send_community = True
      router1.update_source = device.ifname

      # define second router params
      router2.asnum = BASE_ASNUM + 4
      router2.families = {"ipv4_unicast"}
      router2.group_name = "INTERNAL"
      router2.import_policy = "PERMIT_ANY"
      router2.export_policy = "PERMIT_ANY"
      router2.send_community = True
      router2.update_source = device.ifname

We also updated the policy view — ``generators/rpl_views/route_map.py``:

.. code:: python

  from annet.adapters.netbox.common.models import NetboxDevice
  from annet.rpl import R, Route, RouteMap


  # create routemap decorator
  routemap = RouteMap[NetboxDevice]()


  # define redistribute policy
  @routemap
  def IMPORT_CONNECTED(_: NetboxDevice, route: Route):
      with route(
              R.protocol == "connected",
              R.match_v4("LOCAL_NETS", or_longer=(16, 24)),
              number=10
      ) as rule:
          rule.community.set("ADVERTISE")
          rule.allow()
      with route(number=20) as rule:
          rule.deny()


  @routemap
  def ROUTERS_IMPORT(_: NetboxDevice, route: Route):
      with route(
              R.match_v4("LOCAL_NETS", or_longer=(16, 24)),  # custom ge/le
              R.community.has("ADVERTISE"),
              number=10
      ) as rule:
          rule.allow()
      with route(number=20) as rule:
          rule.deny()


  @routemap
  def ROUTERS_EXPORT(_: NetboxDevice, route: Route):
      with route(
              R.community.has("ADVERTISE"),
              number=10
      ) as rule:
          rule.allow()
      with route(number=20) as rule:
          rule.deny()


  @routemap
  def PERMIT_ANY(_: NetboxDevice, route: Route):
      with route(number=10) as rule:
          rule.allow()


Also we should add to the BGP BGP generator update source interface support — ``generators/bgp.py``:

.. code:: python

  from typing import Optional

  from annet.bgp_models import ASN, BgpConfig
  from annet.generators import PartialGenerator
  from annet.mesh.executor import MeshExecutor
  from annet.storage import Device

  from .mesh_views import registry


  def bgp_asnum(mesh_data: BgpConfig) -> Optional[ASN]:
      """Return AS number parse mesh bgp peers"""
      if not mesh_data:
          return None

      # AS can be defined in global options
      if mesh_data.global_options.local_as:
          return mesh_data.global_options.local_as

      # If AS is not defined in global options, look for it in peers
      asnum: set[ASN] = set()
      for peer in mesh_data.peers:
          asnum.add(peer.options.local_as)

      if len(asnum) == 1:
          return asnum.pop()
      elif len(asnum) > 1:
          raise RuntimeError(f"AutonomusSystemIsNotDefined: {str(asnum)}")

      return None


  class Bgp(PartialGenerator):
      """Partial generator class of BGP process and neighbors"""

      TAGS = ["bgp", "routing"]

      def acl_arista(self, _: Device) -> str:
          """ACL for Arista devices"""

          return """
          router bgp
              router-id
              neighbor
              maximum-paths
              address-family
                  redistribute
                  neighbor
          """

      def run_arista(self, device: Device):
          """Generator for Arista devices"""

          executor: MeshExecutor = MeshExecutor(registry, device.storage)
          mesh_data: BgpConfig = executor.execute_for(device)

          rid: Optional[str] = mesh_data.global_options.router_id if mesh_data.global_options.router_id else None
          asnum: Optional[ASN] = bgp_asnum(mesh_data)

          if not asnum or not rid:
              return
          with self.block("router bgp", asnum):
              yield "router-id", rid

              # redistribute
              with self.block("address-family ipv4"):
                  if mesh_data.global_options and mesh_data.global_options.ipv4_unicast and \
                          mesh_data.global_options.ipv4_unicast.redistributes:
                      for redistribute in mesh_data.global_options.ipv4_unicast.redistributes:
                          yield "redistribute", redistribute.protocol, "" \
                              if not redistribute.policy else f"route-map {redistribute.policy}"

              # group configuration
              for peer in mesh_data.peers:
                  yield "neighbor", peer.group_name, "peer group"

                  # import/export policies
                  if peer.import_policy:
                      yield "neighbor", peer.group_name, "route-map", peer.import_policy, "in"
                  if peer.export_policy:
                      yield "neighbor", peer.group_name, "route-map", peer.export_policy, "out"

                  if peer.options.send_community:
                      yield "neighbor", peer.group_name, "send-community"

                  # update source
                  if peer.update_source:
                      yield "neighbor", peer.group_name, "update-source", peer.update_source

                  # use conditional context for group configuration
                  with self.block_if("address-family ipv4", condition=("ipv4_unicast" in peer.families)):
                      yield "neighbor", peer.group_name, "activate"

              # peer configuration
              for peer in mesh_data.peers:
                  yield "neighbor", peer.addr, "peer group", peer.group_name
                  yield "neighbor", peer.addr, "remote-as", peer.remote_as


What else? We need to configure an IGP to provide connectivity between loopbacks! Unfortunately, the mesh doesn't support any protocols except BGP for now (2025q3). We need to assign IP addresses to interfaces and create a new generator for the ISIS protocol.

Let's assign IP addresses following the table:

+--------+-------------------+
| Router | Ethernet2 address |
+========+===================+
|   r2   | ``10.2.3.12/24``  |
+--------+-------------------+
|   r3   | ``10.2.3.13/24``  |
+--------+-------------------+

Here's the ISIS generator and updated init file:
``generators/isis.py``:

.. code:: python

  from typing import Optional

  from annet.bgp_models import BgpConfig
  from annet.generators import PartialGenerator
  from annet.mesh.executor import MeshExecutor
  from annet.storage import Device

  from .mesh_views import registry


  def _get_isis_net(area: str, ip_address: str) -> str:
      """Generate ISIS net address from IPv4 address"""

      padded_octets = [str(int(octet)).zfill(3) for octet in ip_address.split(".")]
      combined = "".join(padded_octets)

      return area + ".".join([combined[i:i+4] for i in range(0, len(combined), 4)]) + ".00"


  class Isis(PartialGenerator):
      """Partial generator class of ISIS process"""

      TAGS = ["isis", "routing"]

      def acl_arista(self, _: Device) -> str:
          """ACL for Arista devices"""

          return """
          router isis
              ~ %global
          interface %cant_delete
              isis
          """

      def run_arista(self, device: Device):
          """Generator for Arista devices"""

          ISIS_NEIGHBORS = {
              "r2.lab": "r3.lab",
              "r3.lab": "r2.lab"
          }

          executor: MeshExecutor = MeshExecutor(registry, device.storage)
          mesh_data: BgpConfig = executor.execute_for(device)
          rid: Optional[str] = mesh_data.global_options.router_id if mesh_data.global_options.router_id else None

          if device.hostname not in ISIS_NEIGHBORS or not rid:
              return

          with self.block("router isis 1"):
              yield "net", _get_isis_net("49.0001.", rid)
              yield "router-id ipv4 ", rid
              yield "is-type level-2"
              yield "address-family ipv4 unicast"

          for interface in device.interfaces:
              if interface.name == "Loopback0" and interface.type.value == "virtual" and interface.ip_addresses:
                  with self.block(f"interface {interface.name}"):
                      yield "isis enable 1"
              if interface.connected_endpoints:
                  for endpoint in interface.connected_endpoints:
                      if device.hostname in ISIS_NEIGHBORS and ISIS_NEIGHBORS[device.hostname] == endpoint.device.name:
                          with self.block(f"interface {interface.name}"):
                              yield "isis enable 1"

``generators/__init__.py``:

.. code:: python

  from annet.generators import BaseGenerator
  from annet.storage import Storage

  from . import (
      aaa,
      bgp,
      community,
      description,
      hostname,
      ip_address,
      isis,
      prefix_list,
      route_map,
      routing,
      stp,
  )


  def get_generators(store: Storage) -> list[BaseGenerator]:
      """All the generators should be returned by the function"""

      return [
          aaa.Aaa(store),
          bgp.Bgp(store),
          community.Community(store),
          description.Description(store),
          hostname.Hostname(store),
          ip_address.IpAddress(store),
          isis.Isis(store),
          prefix_list.PrefixList(store),
          route_map.RouteMap(store),
          routing.Routing(store),
          stp.Stp(store),
      ]

Look at the diff and patch:

.. code:: bash

  annet diff r1.lab r2.lab r3.lab

.. code:: diff

  > annet diff r1.lab r2.lab r3.lab
  # -------------------- r1.lab.cfg --------------------
    router bgp 65001
  -   neighbor 10.1.2.12 remote-as 65002
  +   neighbor 10.1.2.12 remote-as 65004
  -   neighbor 10.1.3.13 remote-as 65003
  +   neighbor 10.1.3.13 remote-as 65004
  # -------------------- r2.lab.cfg --------------------
  + router isis 1
  +   net 49.0001.0010.0100.1002.00
  +   router-id ipv4 1.1.1.2
  +   is-type level-2
  +   address-family ipv4 unicast
    interface Ethernet2
  +   isis enable 1
  + interface Loopback0
  +   ip address 1.1.1.2/32
  +   isis enable 1
  - router bgp 65002
  -   router-id 1.1.1.2
  -   neighbor ROUTERS peer group
  -   neighbor ROUTERS route-map ROUTERS_IMPORT in
  -   neighbor ROUTERS route-map ROUTERS_EXPORT out
  -   neighbor ROUTERS send-community
  -   neighbor 10.1.2.11 peer group ROUTERS
  -   neighbor 10.1.2.11 remote-as 65001
  -   neighbor 10.2.3.13 peer group ROUTERS
  -   neighbor 10.2.3.13 remote-as 65003
  -   address-family ipv4
  -     neighbor ROUTERS activate
  -     redistribute connected route-map IMPORT_CONNECTED
  + router bgp 65004
  +   router-id 1.1.1.2
  +   address-family ipv4
  +     redistribute connected route-map IMPORT_CONNECTED
  +     neighbor ROUTERS activate
  +     neighbor INTERNAL activate
  +   neighbor ROUTERS peer group
  +   neighbor ROUTERS route-map ROUTERS_IMPORT in
  +   neighbor ROUTERS route-map ROUTERS_EXPORT out
  +   neighbor ROUTERS send-community
  +   neighbor INTERNAL peer group
  +   neighbor INTERNAL route-map PERMIT_ANY in
  +   neighbor INTERNAL route-map PERMIT_ANY out
  +   neighbor INTERNAL send-community
  +   neighbor INTERNAL update-source Loopback0
  +   neighbor 10.1.2.11 peer group ROUTERS
  +   neighbor 10.1.2.11 remote-as 65001
  +   neighbor 1.1.1.3 peer group INTERNAL
  +   neighbor 1.1.1.3 remote-as 65004
  + route-map PERMIT_ANY permit 10
  # -------------------- r3.lab.cfg --------------------
  + router isis 1
  +   net 49.0001.0010.0100.1003.00
  +   router-id ipv4 1.1.1.3
  +   is-type level-2
  +   address-family ipv4 unicast
    interface Ethernet2
  +   isis enable 1
  + interface Loopback0
  +   ip address 1.1.1.3/32
  +   isis enable 1
  - router bgp 65003
  -   router-id 1.1.1.3
  -   neighbor ROUTERS peer group
  -   neighbor ROUTERS route-map ROUTERS_IMPORT in
  -   neighbor ROUTERS route-map ROUTERS_EXPORT out
  -   neighbor ROUTERS send-community
  -   neighbor 10.1.3.11 peer group ROUTERS
  -   neighbor 10.1.3.11 remote-as 65001
  -   neighbor 10.2.3.12 peer group ROUTERS
  -   neighbor 10.2.3.12 remote-as 65002
  -   address-family ipv4
  -     neighbor ROUTERS activate
  -     redistribute connected route-map IMPORT_CONNECTED
  + router bgp 65004
  +   router-id 1.1.1.3
  +   address-family ipv4
  +     redistribute connected route-map IMPORT_CONNECTED
  +     neighbor ROUTERS activate
  +     neighbor INTERNAL activate
  +   neighbor ROUTERS peer group
  +   neighbor ROUTERS route-map ROUTERS_IMPORT in
  +   neighbor ROUTERS route-map ROUTERS_EXPORT out
  +   neighbor ROUTERS send-community
  +   neighbor INTERNAL peer group
  +   neighbor INTERNAL route-map PERMIT_ANY in
  +   neighbor INTERNAL route-map PERMIT_ANY out
  +   neighbor INTERNAL send-community
  +   neighbor INTERNAL update-source Loopback0
  +   neighbor 10.1.3.11 peer group ROUTERS
  +   neighbor 10.1.3.11 remote-as 65001
  +   neighbor 1.1.1.2 peer group INTERNAL
  +   neighbor 1.1.1.2 remote-as 65004
  + route-map PERMIT_ANY permit 10

.. code:: bash

  annet patch r1.lab r2.lab r3.lab

.. code:: none

  > annet patch r1.lab r2.lab r3.lab
  # -------------------- r1.lab.patch --------------------
  router bgp 65001
    no neighbor 10.1.2.12 remote-as 65002
    no neighbor 10.1.3.13 remote-as 65003
    neighbor 10.1.2.12 remote-as 65004
    neighbor 10.1.3.13 remote-as 65004
    exit
  # -------------------- r2.lab.patch --------------------
  no router bgp 65002
  router isis 1
    net 49.0001.0010.0100.1002.00
    router-id ipv4 1.1.1.2
    is-type level-2
    address-family ipv4 unicast
    exit
  interface Ethernet2
    isis enable 1
    exit
  interface Loopback0
    ip address 1.1.1.2/32
    isis enable 1
    exit
  route-map PERMIT_ANY permit 10
    exit
  router bgp 65004
    router-id 1.1.1.2
    address-family ipv4
      redistribute connected route-map IMPORT_CONNECTED
      neighbor ROUTERS activate
      neighbor INTERNAL activate
      exit
    neighbor ROUTERS peer group
    neighbor ROUTERS route-map ROUTERS_IMPORT in
    neighbor ROUTERS route-map ROUTERS_EXPORT out
    neighbor ROUTERS send-community
    neighbor INTERNAL peer group
    neighbor INTERNAL route-map PERMIT_ANY in
    neighbor INTERNAL route-map PERMIT_ANY out
    neighbor INTERNAL send-community
    neighbor INTERNAL update-source Loopback0
    neighbor 10.1.2.11 peer group ROUTERS
    neighbor 10.1.2.11 remote-as 65001
    neighbor 1.1.1.3 peer group INTERNAL
    neighbor 1.1.1.3 remote-as 65004
    exit
  # -------------------- r3.lab.patch --------------------
  no router bgp 65003
  router isis 1
    net 49.0001.0010.0100.1003.00
    router-id ipv4 1.1.1.3
    is-type level-2
    address-family ipv4 unicast
    exit
  interface Ethernet2
    isis enable 1
    exit
  interface Loopback0
    ip address 1.1.1.3/32
    isis enable 1
    exit
  route-map PERMIT_ANY permit 10
    exit
  router bgp 65004
    router-id 1.1.1.3
    address-family ipv4
      redistribute connected route-map IMPORT_CONNECTED
      neighbor ROUTERS activate
      neighbor INTERNAL activate
      exit
    neighbor ROUTERS peer group
    neighbor ROUTERS route-map ROUTERS_IMPORT in
    neighbor ROUTERS route-map ROUTERS_EXPORT out
    neighbor ROUTERS send-community
    neighbor INTERNAL peer group
    neighbor INTERNAL route-map PERMIT_ANY in
    neighbor INTERNAL route-map PERMIT_ANY out
    neighbor INTERNAL send-community
    neighbor INTERNAL update-source Loopback0
    neighbor 10.1.3.11 peer group ROUTERS
    neighbor 10.1.3.11 remote-as 65001
    neighbor 1.1.1.2 peer group INTERNAL
    neighbor 1.1.1.2 remote-as 65004
    exit

Deploy it:

.. code:: none

  annet deploy r1.lab r2.lab r3.lab

And check the result:

.. code:: none

  ssh annet@172.20.0.102
  (annet@172.20.0.102) Password:
  Last login: Fri Feb  7 08:34:22 2025 from 172.20.0.0
  r2#sh ip bgp sum
  BGP summary information for VRF default
  Router identifier 1.1.1.2, local AS number 65004
  Neighbor Status Codes: m - Under maintenance
    Neighbor  V AS           MsgRcvd   MsgSent  InQ OutQ  Up/Down State   PfxRcd PfxAcc
    1.1.1.3   4 65004              6         7    0    0 00:01:00 Estab   2      2
    10.1.2.11 4 65001           2656      2652    0    0 00:01:33 Estab   1      1
  r2#
