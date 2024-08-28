from annet.annlib.tabparser import (  # pylint: disable=unused-import
    AsrFormatter,
    CiscoFormatter,
    CommonFormatter,
    HuaweiFormatter,
    HuaweiDWDMFormatter,
    JuniperFormatter,
    JuniperList,
    NokiaFormatter,
    ParserError,
    RibbonFormatter,
    RosFormatter,
    parse_to_tree,
)


def make_formatter(hw, **kwargs):
    if hw.Huawei:
        cls = HuaweiFormatter
    elif hw.HuaweiDWDM:
        cls = HuaweiDWDMFormatter
    elif hw.Cisco.ASR or hw.Cisco.XRV:
        cls = AsrFormatter
    elif hw.Nexus or hw.Cisco or hw.Arista or hw.Aruba:
        cls = CiscoFormatter
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
    else:
        raise NotImplementedError("Unknown formatter for hw '%s'" % hw)

    return cls(**kwargs)
