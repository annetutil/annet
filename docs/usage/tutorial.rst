Annet Tutorial
===============================================

The tutorial tested on MacOS, but should work on Linux also. I'm not sure that Windows WSL supports it too, but why not?

Prepare environment
-------------------

We will use docker compose for lab environment, feel free to use any other kind of virtualization environment. Docker compose looks like easier way and supports no only on linux, but also on macOS and Windows.

To work on MacOS with docker we recommend to use `Docker Desktop for Mac <https://docs.docker.com/desktop/mac/install/>`__ or `orbstack <https://orbstack.dev/>`__.

Arista cEOS
^^^^^^^^^^^

We are choose use Containerized Arista EOS since Arista EOS is widely use and have easy to understand Cisco like interface. But the most important point for us is the image can be `downloaded from official site <https://www.arista.com/en/support/software-download>`__ for free by any register users.

.. note:: Use your own domain or corporate domain for registered email because Arista is not allowed to use common email providers domains, e.g. gmail.

Download image and import it to docker:

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


There is a network with three routers with direct connection between each other.

Out of band management IP addresses are:

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

.. note:: Currently supported 3.7 version (2025q1). Newer versions will be supported soon.

If you like to use your own installation of netbox, you can skip that section. But read the notices at the beginning of next section.

The easiest way to install netbox is to use dockerized version of netbox.

.. code:: bash

  #
  # clone repo with dockerized version of netbox
  git clone https://github.com/netbox-community/netbox-docker.git
  #
  # got into directory
  cd netbox-docker
  #
  # change version to 3.7, you can do it in you favorite editor instead,
  # just replace "VERSION-v4.1-3.0.2" to "VERSION-v3.7" in ./netbox-docker/docker-compose.yml, or use sed:
  # NOTE: be careful, in the tutorial version 3.0.2 of netbox docker is using,
  #  may be you face with newer version and it requires to change something else too,
  #  to checkout the correct version use "git fetch --tags && git checkout tags/3.0.2"
  sed -i.bak 's/VERSION-v4.1-3.0.2/VERSION-v3.7/g' docker-compose.yml
  #
  # if you run netbox on weak hardware you can change timeouts in docker-compose.yml,
  # e.g. multiply all the timeouts by 10 in your favorite editor, or use sed:
  sed -i.bak 's/0s/00s/g' docker-compose.yml


Docker compose override file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some important notice:

1. The directories ``lab/ceos-rX.flash`` are needed to store saved configuration of cEOS.
2. Before run cEOS, we should prepare ``startup-config`` with mgmt IP address and local user ``annet:annet``.
3. ``depends_on`` part added to every cEOS service to avoid overload resources on weaked hardware.
4. The docker-compose contains strict definition of version cEOS, if you use another version, you need to change it in the docker-compose file.
5. If you use your own netbox, you need to

   - create directory  ``netbox-docker``;
   - change it in the ``docker-compose.override.yml`` to ``docker-compose.yml``;
   - remove ``services/netbox`` part form the docker-compose file;
   - remove ``depends_on`` part from cEOS services.

.. code:: bash

  # go to root of your folder
  cd ..
  #
  # create folders for cEOS configuration files
  mkdir -p lab/ceos-r1.flash lab/ceos-r2.flash lab/ceos-r3.flash
  #
  # create configuration files for cEOS
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
  #
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
  #
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
  #
  # create docker-compose override file
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


Run environment
^^^^^^^^^^^^^^^

Now we can run netbox and lab:

.. code:: bash

  docker compose up -d

Check that Netbox is accessible by the url http://localhost:8000/

You need to create a superuser by script:

.. code:: bash

  docker-compose run netbox python manage.py createsuperuser

To be on same page use ``annet`` for login and password. But you can change them to what you like. But in any case you can easily change them in any time.

Try to connect to cEOS CLI:

.. code:: bash

  docker exec -it r1 Cli

Try to connect to cEOS SSH use ``annet:annet``:

.. code:: bash

  ssh annet@172.20.0.101

Update netbox database
^^^^^^^^^^^^^^^^^^^^^^

Annet will use data from netbox to generate configuration. Of course the data should be there before we start to work with annet.

1. In **Organisation/Site** add Site - name: ``lab``, slug: ``lab``.
2. In **Devices/Manufacturers** add Manufacturer - name: ``Arista``, slug: ``arista``.
3. In **Devices/Device Types** add Device Type - Manufacturer: ``Arista``, name: ``cEOS``, slug: ``ceos``.
4. In **Devices/Device Roles** add Device Role - name: ``switch``, slug: ``switch``, color: choose what you like.
5. In **Devices/Devices** add three Device

   - name: ``r1.lab``, device role: ``switch``, device type: ``cEOS``, site: ``lab``;
   - name: ``r2.lab``, device role: ``switch``, device type: ``cEOS``, site: ``lab``;
   - name: ``r3.lab``, device role: ``switch``, device type: ``cEOS``, site: ``lab``.

6. For each device add interfaces in **Add Components/Interfaces**:

   - name: ``Ethernet1``, type: ``1000Base-T``;
   - name: ``Ethernet2``, type: ``1000Base-T``;
   - name: ``Ethernet3``, type: ``1000Base-T``;
   - name: ``Management0``, type: ``1000Base-T``, Management only: ``True``.

7. For each device add IP address in tab **Interfaces**:

   - device: ``r1.lab``, interface: ``Management0``, IP address: ``172.20.0.101/24``;
   - device: ``r2.lab``, interface: ``Management0``, IP address: ``172.20.0.102/24``;
   - device: ``r3.lab``, interface: ``Management0``, IP address: ``172.20.0.103/24``.

8. For each device assign **Primary IPv4**, in edit mode assign **Primary IPv4** to ``172.20.0.101``, ``172.20.0.102``, ``172.20.0.103`` respectively.
9. And finally create connection between devices follow the topology. In tab Interfaces add cables between:

   - device: ``r1.lab``, interface: ``Ethernet1``, connected to device: ``r2.lab``, interface: ``Ethernet1``;
   - device: ``r1.lab``, interface: ``Ethernet2``, connected to device: ``r3.lab``, interface: ``Ethernet1``;
   - device: ``r2.lab``, interface: ``Ethernet2``, connected to device: ``r3.lab``, interface: ``Ethernet2``.

Annet Installation
----------------------

Create Virtual environment and install annet and requirements packages. We recommend to use Python 3.12 and later.

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

Before we start we should install gentcli server binary

.. note:: The step requires to have installed golang. You also can just download binary for your platform from https://github.com/annetutil/gnetcli/releases. Annet will use it, be sure that folder with the binary is added to PATH environments.

.. code:: bash

  export GOPATH=~/go
  export PATH=$PATH:$GOPATH/bin
  go install github.com/annetutil/gnetcli/cmd/gnetcli_server@latest


Annet configuration
-------------------

Annet will work with devices and netbox, for that reason we should define:

1. Device credentials, we use annet:annet for lab environment.
2. Netbox token. Open netbox and go to **Admins/API Tokens**, add new one for user annet.

.. code:: bash

  #
  # create folder for future annet generators
  mkdir generators
  touch generators/__init__.py
  #
  # create configuration file:
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
  #
  # define path to configuration file:
  export ANN_CONTEXT_CONFIG_PATH=annet_config.yaml

Let's check!

Try to get netbox device model:

.. code:: bash

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


Try to get current configuration of the device:

.. code::

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

Let's play with annet
----------------------

Create first generator
^^^^^^^^^^^^^^^^^^^^^^

For now, we create generator of interface descriptions.

Create file ``generators/description.py``.

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


And update file ``generators/__init__.py``:

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

  > annet show generators
  | PARTIAL-Class   | Tags               | Module                                              | Description                            |
  |-----------------+--------------------+-----------------------------------------------------+----------------------------------------|
  | Description     | description, iface | Users_gslv_annet_generators___init___py.description | Generator of description on interfaces |


Get generated configuration for all three devices:

.. code:: bash

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

Look at diff:

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

  > annet deploy -g description r1.lab r2.lab r3.lab

Verify the result:

.. code:: bash

  > ssh annet@172.20.0.101
  (annet@172.20.0.101) Password:
  Last login: Sun Jan 26 15:29:33 2025 from 172.20.0.0
  r1#sh int desc
  Interface                      Status         Protocol           Description
  Et1                            up             up                 r2@Ethernet1
  Et2                            up             up                 r3@Ethernet1
  Ma0                            up             up
  r1#

Extend coverage
^^^^^^^^^^^^^^^

Because of ACL, we can add new configuration parts to annet step by step, do not touch other parts of the configuration.

Add generators for aaa, hostname, ip address, routing and stp.

Create files:

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

``generators/hostnmae.py``:

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

Look at list of generators:

.. code:: bash

  > annet show generators
  | PARTIAL-Class   | Tags               | Module                                                  | Description                                          |
  |-----------------+--------------------+---------------------------------------------------------+------------------------------------------------------|
  | Aaa             | aaa                | Users_gslv_dev_annet_generators___init___py.aaa         | Generator of AAA                                     |
  | Description     | description, iface | Users_gslv_dev_annet_generators___init___py.description | Generator of description on interfaces               |
  | Hostname        | hostname           | Users_gslv_dev_annet_generators___init___py.hostname    | Generator of Hostname                                |
  | IpAddress       | routing, iface     | Users_gslv_dev_annet_generators___init___py.ip_address  | Generator of IP addresses                            |
  | Routing         | routing            | Users_gslv_dev_annet_generators___init___py.routing     | Generator of Routing                                 |
  | Stp             | stp                | Users_gslv_dev_annet_generators___init___py.stp         | Generator of STP                                     |

Look at diff:

.. code:: diff

  > annet diff r1.lab r2.lab r3.lab
  # -------------------- r3.lab.cfg --------------------
  - username annet privilege 15 role network-admin secret sha512 $6$s7NCIG5Rocu3FSK0$018nDOmgJctLO7qGVotvo9OOD1qyKVMTwaURO8sh7YaoCitMIE2HRWePYq2T5aGqEsa2Y0ukqe5/PKlNV43zc0
  + username annet privilege 15 role network-admin secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.
  # -------------------- r2.lab.cfg --------------------
  - username annet privilege 15 role network-admin secret sha512 $6$ycnCXwDzpQPU6WqS$6u0MD.hyOKaRh6r8Tnb97S8zFQVYeXaQuo8nkFHCez7VlBxeJmGsbbgeTePg.k23hEdK.LN1TB5sCjfkS7Mdu.
  + username annet privilege 15 role network-admin secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.

We notice that user annet has different hash on r2 and r3, it is ok because we created users annet by default configuration with plain text password.

Look at patch:

.. code:: bash

  > annet patch r2.lab r3.lab
  # -------------------- r2.lab.patch --------------------
  username annet privilege 15 role network-admin secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.
  # -------------------- r3.lab.patch --------------------
  username annet privilege 15 role network-admin secret sha512 $6$i5LaTWzHeAJx/vLu$rYUKKATawfpjItHKJJie3Fgsa2EqkMyH0XYY2.1Dl/2G.uNVzuntS5poblWuf6urafiurknH2/NotkUHiamoP.

And deploy it:

.. code:: bash

  > annet deploy r2.lab r3.lab

Again look at diff:

.. code:: bash

  > annet diff r1.lab r2.lab r3.lab


No diff found - everything is ok for now.

Look at doff without ACL to check what's configurations lines is still not covered by annet:

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

We are skipped them, but if you want, you can create some new generators to add therm to annet.

BGP configuration
^^^^^^^^^^^^^^^^^

Annet has brilliance tool to create BGP peers - mesh. It allows us to create templates for BGP peers and apply them to netbox device. Annet takes connections between devices from netbox and passed them through templates. As result, we got a list of local and remote peers pairs. The list can be used in generators.
Someone calls mesh templates as network design in Python code!

Imagine that we need to have BGP session between r1, r2 and r3 over direct links to exchange IPv4 routes.

Create mesh template ``generators/mesh_views/routers.py``

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

Create init file ``generators/mesh_views/__init__.py``

.. code:: python

  from annet.mesh import MeshRulesRegistry

  from . import routers


  registry = MeshRulesRegistry(match_short_name=True)
  registry.include(routers.registry)


Now we should use mesh data in generators. First of all update L3Addresses generators ``generators/l3_addresses.py``:

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

Adding new generators for BGP configuration - ``generators/bgp.py``:

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

Checks list of generators:

.. code:: bash

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

Checks the diff:

.. code:: diff

  annet diff r1.lab r2.lab r3.lab
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


Looks great! Do deploy it to the devices:

.. code:: bash

  > annet deploy r1.lab r2.lab r3.lab


Checks result:

.. code::

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

Redistribute connected
^^^^^^^^^^^^^^^^^^^^^^

Go deeper, the task for now is configuring redistribute connected network to BGP.

Create on each router interface ``loopback10`` with address in Netbox follow the table:

+--------+--------------------+
| Router | Loopback10 address |
+========+====================+
|   r1   | ``192.168.1.1/24`` |
+--------+--------------------+
|   r2   | ``192.168.2.1/24`` |
+--------+--------------------+
|   r3   | ``192.168.3.1/24`` |
+--------+--------------------+

Go to router page press **Add Components**, choose **Interfaces**. Use name: ``loopback10`` and type: ``Virtual``. Next, add IP address to the interface follow the table.

For now, we should add to mesh redistribute connected network to BGP. Moreover, we want to filter prefixes between routers!

To do that update file ``generators/mesh_views/routers.py``:

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
  # pylint: disable=unused-argument
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

You can notice that redistribute has link to policy ``IMPORT_CONNECTED``. It can be defined by new generator as plain config, but annet has special tool to work with policies. For now supported only Huawei VRP, Arista EOS and FRR (2025q1). But we expect that it will be updated soon.

First of all create a new module by touch empty file ``generators/rpl_views/__init__.py``. There is module will contain policies and their elements.

Create Python file with the policies - ``generators/rpl_views/routemap.py``:

.. code:: python

  # pylint: disable=missing-function-docstring
  from annet.adapters.netbox.common.models import NetboxDevice
  from annet.rpl import R, Route, RouteMap


  # create routemap decorator
  routemap = RouteMap[NetboxDevice]()


  # define redistribute policy
  @routemap
  def IMPORT_CONNECTED(_: NetboxDevice, route: Route):
      with route(
              R.protocol == "connected",
              R.match_v4("LOCAL_NETS", or_longer=(24, 32)),
              number=10
      ) as rule:
          rule.community.set("ADVERTISE")
          rule.allow()
      with route(number=20) as rule:
          rule.deny()


  @routemap
  def ROUTERS_IMPORT(_: NetboxDevice, route: Route):
      with route(
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

More details how to use rpl you can find in `documentation <https://annetutil.github.io/annet/main/rpl/index.html>`__.

Next two files contains community and prefix lists definitions.

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

Looks not so difficult, but we should create three generators of:
- policy
- community
- prefix list

Policy generator - ``generators/route_map.py``:

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

Community generator - ``generators/community.py``:

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

Prefix list generator - ``generators/prefix_list.py``:

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

And again, update ``generators/__init__.py``:

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

Do not forget update BGP generator to support import/export policies and send community - ``generators/bgp.py``:

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

.. code:: diff

  > annet diff r1.lab
  # -------------------- r1.lab.cfg --------------------
  + interface Loopback10
  +   ip address 192.168.1.1/24
  + ip prefix-list LOCAL_NETS seq 5 permit 192.168.0.0/16 ge 24 le 32
  + ip community-list ADVERTISE permit 65000:1
  + route-map IMPORT_CONNECTED permit 10
  +   match source-protocol connected
  +   match ip address prefix-list LOCAL_NETS
  +   set community community-list ADVERTISE
  + route-map IMPORT_CONNECTED deny 20
  + route-map ROUTERS_IMPORT permit 10
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

And patch:

.. code::

  > annet patch r1.lab
  # -------------------- r1.lab.patch --------------------
  interface Loopback10
    ip address 192.168.1.1/24
    exit
  ip prefix-list LOCAL_NETS seq 5 permit 192.168.0.0/16 ge 24 le 32
  ip community-list ADVERTISE permit 65000:1
  route-map IMPORT_CONNECTED permit 10
    match source-protocol connected
    match ip address prefix-list LOCAL_NETS
    set community community-list ADVERTISE
    exit
  route-map IMPORT_CONNECTED deny 20
    exit
  route-map ROUTERS_IMPORT permit 10
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

And deploy on all three routers:

.. code:: bash

  annet deploy r1.lab r2.lab r3.lab


Check the result:

.. code::

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

We are going to create IS-IS peering between ``r2`` and ``r3`` to exchange Loopback0 addresses. After we established indirect BGP peering between ``r2`` and ``r3`` instead of direct peering. Also, we change ASN on ``r2`` and ``r3`` to ``65004``.

The details are presented on diagram:

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


First of all we change mesh. What steps we need to do:
1. Add interface ``Loopback0`` with ip addresses to ``r2`` and ``r3`` follow the diagram.
2. Disable direct peering between ``r2`` and ``r3``.
3. Create a simple policy ``PERMIT_ANY`` for indirect peering.
4. Create indirect peering between ``r2`` and ``r3`` by using interfaces ``Loopback0``.

To add new loopback interface repeat actions from (Redistribute connected)[#Redistribute connected] step.

Disabling direct peering easy to achieve by adding additional equation which just return nothing. Configuring indirect peering required to use ``@registry.indirect`` decorator. This is updated mesh - ``generators/mesh_views/routers.py``

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

Also we updated policy view - ``generators/rpl_views/route_map.py``:

.. code:: python

  # pylint: disable=missing-function-docstring
  from annet.adapters.netbox.common.models import NetboxDevice
  from annet.rpl import R, Route, RouteMap


  # create routemap decorator
  routemap = RouteMap[NetboxDevice]()


  # define redistribute policy
  @routemap
  def IMPORT_CONNECTED(_: NetboxDevice, route: Route):
      with route(
              R.protocol == "connected",
              R.match_v4("LOCAL_NETS", or_longer=(24, 32)),
              number=10
      ) as rule:
          rule.community.set("ADVERTISE")
          rule.allow()
      with route(number=20) as rule:
          rule.deny()


  @routemap
  def ROUTERS_IMPORT(_: NetboxDevice, route: Route):
      with route(
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

Ok, what else? We should configure IGP to provide connectivity between loopbacks! Unfortunately mesh doesn't support any protocols except BGP for now (2025q1). We need to assign IP addresses to interfaces and create new generator for ISIS protocol.

Let's assign IP addresses follow the table:

+--------+------------------+
| Router |   Eth2 address   |
+========+==================+
|   r2   | ``10.2.3.12/24`` |
+--------+------------------+
|   r3   | ``10.2.3.13/24`` |
+--------+------------------+

This is ISIS generator and updated init file:
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

Look at diff and patch

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


.. code::

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

And deploy it

.. code:: bash

  annet deploy r1.lab r2.lab r3.lab


And check result:

.. code::

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
