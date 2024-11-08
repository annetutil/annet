from typing import Optional

from annet.annlib.netdev.devdb import parse_hw_model

from .dump import DumpableView


class HardwareLeaf(DumpableView):
    def __new__(cls, *_, **__):
        obj = super(HardwareLeaf, cls).__new__(cls)
        obj.__path = ()
        obj.__true_sequences = set()
        obj.__false_sequences = set()
        return obj

    def __init__(self, path, true_sequences, false_sequences):
        self.__path = path
        self.__true_sequences = true_sequences
        self.__false_sequences = false_sequences

    def __bool__(self):
        if len(self.__path) == 0 or self.__path in self.__true_sequences:
            return True
        elif self.__path in self.__false_sequences:
            return False
        raise AttributeError("HW: " + ".".join(self.__path))

    def __getattr__(self, name):
        path = self.__path + (name,)
        if path in self.__true_sequences or path in self.__false_sequences:
            return HardwareLeaf(path, self.__true_sequences, self.__false_sequences)
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError("HW: " + ".".join(path))

    def __str__(self):
        return str(" | ".join(".".join(x) for x in self.__true_sequences))

    __repr__ = __str__

    def dump(self, prefix, **kwargs):  # pylint: disable=arguments-differ
        ret = super().dump(prefix, **kwargs)
        seen = set()
        for seq in sorted(self.__true_sequences, key=len, reverse=True):
            if any(name in seen for name in seq):
                continue
            seen.update(seq)
            ret.append("%s.%s = True" % (prefix, ".".join(seq)))
        return ret


class HardwareView(HardwareLeaf):
    def __init__(self, hw_model, sw_version):
        (true_sequences, false_sequences) = parse_hw_model(hw_model or "")
        super().__init__((), true_sequences, false_sequences)
        self.model = hw_model or ""
        self._soft = sw_version or ""

    @property
    def vendor(self) -> Optional[str]:
        return hw_to_vendor(self)

    @property
    def soft(self) -> str:
        return self._soft

    def __hash__(self):
        return hash(self.model)

    def __eq__(self, other):
        return self.model == other.model


def hw_to_vendor(hw: HardwareView) -> Optional[str]:
    if hw.Nexus:
        return "nexus"
    elif hw.Cisco:
        return "cisco"
    elif hw.OptiXtrans:
        return "optixtrans"
    elif hw.Huawei:
        return "huawei"
    elif hw.Juniper:
        return "juniper"
    elif hw.Arista:
        return "arista"
    elif hw.PC:
        return "pc"
    elif hw.Nokia:
        return "nokia"
    elif hw.RouterOS:
        return "routeros"
    elif hw.Aruba:
        return "aruba"
    elif hw.Ribbon:
        return "ribbon"
    elif hw.H3C:
        return "h3c"
    elif hw.B4com:
        return "b4com"
    return None


def vendor_to_hw(vendor):
    hw = HardwareView(
        {
            "cisco": "Cisco",
            "catalyst": "Cisco Catalyst",
            "nexus": "Cisco Nexus",
            "huawei": "Huawei",
            "optixtrans": "Huawei OptiXtrans",
            "juniper": "Juniper",
            "arista": "Arista",
            "pc": "PC",
            "nokia": "Nokia",
            "aruba": "Aruba",
            "routeros": "RouterOS",
            "ribbon": "Ribbon",
            "h3c": "H3C",
            "b4com": "B4com",
        }.get(vendor.lower(), vendor),
        None,
    )
    return hw


def lag_name(hw: HardwareView, nlagg: int) -> str:
    if hw.Huawei:
        return f"Eth-Trunk{nlagg}"
    if hw.Cisco:
        return f"port-channel{nlagg}"
    if hw.Nexus:
        return f"port-channel{nlagg}"
    if hw.Arista:
        return f"Port-Channel{nlagg}"
    if hw.Juniper:
        return f"ae{nlagg}"
    if hw.Nokia:
        return f"lag-{nlagg}"
    if hw.PC.Whitebox:
        return f"bond{nlagg}"
    if hw.PC:
        return f"lagg{nlagg}"
    if hw.Nokia:
        return f"lagg-{nlagg}"
    raise NotImplementedError(hw)


def svi_name(hw: HardwareView, num: int) -> str:
    if hw.Juniper:
        return f"irb.{num}"
    elif hw.Huawei:
        return f"Vlanif{num}"
    else:
        return f"vlan{num}"
