from annet.annlib.tabparser import (  # pylint: disable=unused-import
    AsrFormatter,
    CiscoFormatter,
    CommonFormatter,
    HuaweiFormatter,
    OptixtransFormatter,
    JuniperFormatter,
    JuniperList,
    NokiaFormatter,
    ParserError,
    RibbonFormatter,
    RosFormatter,
    parse_to_tree,
    AristaFormatter,
    NexusFormatter,
    B4comFormatter,
    ArubaFormatter,
)


def make_formatter(hw, **kwargs):
    if hw.OptiXtrans:
        cls = OptixtransFormatter
    elif hw.Huawei:
        cls = HuaweiFormatter
    elif hw.Cisco.ASR or hw.Cisco.XRV:
        cls = AsrFormatter
    elif hw.Nexus:
        cls = NexusFormatter
    elif hw.Cisco:
        cls = CiscoFormatter
    elif hw.B4com:
        cls = B4comFormatter
    elif hw.Aruba:
        cls = ArubaFormatter
    elif hw.Juniper:
        cls = JuniperFormatter
    elif hw.Nokia:
        cls = NokiaFormatter
    elif hw.RouterOS:
        cls = RosFormatter
    elif hw.PC:
        cls = CommonFormatter
    elif hw.Ribbon:
        cls = RibbonFormatter
    elif hw.H3C:
        cls = HuaweiFormatter
    elif hw.Arista:
        cls = AristaFormatter
    else:
        raise NotImplementedError("Unknown formatter for hw '%s'" % hw)

    return cls(**kwargs)
