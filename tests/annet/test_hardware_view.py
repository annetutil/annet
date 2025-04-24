import pytest

from annet.annlib.netdev.views.hardware import HardwareView


@pytest.mark.parametrize(
    "hw_model, expected",
    [
        ("Arista DCS-7050CX4-24D8-F", "Arista"),
        ("Arista DCS-7050DX4-32S-F", "Arista"),
        ("Arista DCS-7050SX3-48YC8", "Arista"),
        ("Arista DCS-7060CX-32S-F", "A7060 | Arista | Arista.A7060"),
        ("Arista DCS-7060X6-64PE-F", "A7060 | Arista | Arista.A7060"),
        (
            "Arista DCS-7260CX3-64-F",
            "A7260 | A7260.CX3 | Arista | Arista.A7260 | Arista.A7260.CX3 | Arista.CX3 | CX3",
        ),
        ("Arista DCS-7368", "Arista"),
        (
            "Aruba AP-515",
            "AP | AP.AP500 | AP.AP500.AP515 | AP.AP515 | AP500 | AP500.AP515 | AP515 | Aruba | Aruba.AP | Aruba.AP.AP500 | Aruba.AP.AP500.AP515 | Aruba.AP.AP515 | Aruba.AP500 | Aruba.AP515",
        ),
        (
            "Aruba AP-565",
            "AP | AP.AP500 | AP500 | Aruba | Aruba.AP | Aruba.AP.AP500 | Aruba.AP500",
        ),
        (
            "Aruba AP-655",
            "AP | AP.AP600 | AP.AP600.AP655 | AP.AP655 | AP600 | AP600.AP655 | AP655 | Aruba | Aruba.AP | Aruba.AP.AP600 | Aruba.AP.AP600.AP655 | Aruba.AP.AP655 | Aruba.AP600 | Aruba.AP655",
        ),
        ("Cisco 8201-32FH", "Cisco | Cisco.XR | XR"),
        ("Cisco C1000-24P-4X-L", "Cisco"),
        ("Cisco C9200L-24P-4X", "Cisco"),
        ("Cisco C9200L-48P-4X", "Cisco"),
        ("Cisco C9200L-48T-4X-E", "Cisco"),
        ("Cisco CGS-2520-16S-8PC", "CGS | Cisco | Cisco.CGS"),
        ("Cisco IE-2000-16TC-L", "Cisco | Cisco.IE | IE"),
        ("Cisco N3K-C3172PQ-10GE", "Cisco"),
        ("Cisco N9K-C93180YC-EX", "Cisco"),
        (
            "Cisco WS-C2960+48TC-S",
            "C2900 | C2900.C2960 | C2960 | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2960 | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2960",
        ),
        (
            "Cisco WS-C2960-24PC-L",
            "C2900 | C2900.C2960 | C2960 | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2960 | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2960",
        ),
        (
            "Cisco WS-C2960-24TC-L",
            "C2900 | C2900.C2960 | C2960 | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2960 | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2960",
        ),
        (
            "Cisco WS-C2960-48TC-S",
            "C2900 | C2900.C2960 | C2960 | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2960 | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2960",
        ),
        (
            "Cisco WS-C2960G-24TC-L",
            "C2900 | C2900.C2960 | C2900.C2960.C2960G | C2900.C2960G | C2960 | C2960.C2960G | C2960G | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2900.C2960.C2960G | Catalyst.C2900.C2960G | Catalyst.C2960 | Catalyst.C2960G | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.C2960G | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2900.C2960.C2960G | Cisco.Catalyst.C2900.C2960G | Cisco.Catalyst.C2960 | Cisco.Catalyst.C2960G",
        ),
        (
            "Cisco WS-C2960G-48TC-L",
            "C2900 | C2900.C2960 | C2900.C2960.C2960G | C2900.C2960G | C2960 | C2960.C2960G | C2960G | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2900.C2960.C2960G | Catalyst.C2900.C2960G | Catalyst.C2960 | Catalyst.C2960G | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.C2960G | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2900.C2960.C2960G | Cisco.Catalyst.C2900.C2960G | Cisco.Catalyst.C2960 | Cisco.Catalyst.C2960G",
        ),
        (
            "Cisco WS-C2960G-48TC-S",
            "C2900 | C2900.C2960 | C2900.C2960.C2960G | C2900.C2960G | C2960 | C2960.C2960G | C2960G | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2900.C2960.C2960G | Catalyst.C2900.C2960G | Catalyst.C2960 | Catalyst.C2960G | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.C2960G | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2900.C2960.C2960G | Cisco.Catalyst.C2900.C2960G | Cisco.Catalyst.C2960 | Cisco.Catalyst.C2960G",
        ),
        (
            "Cisco WS-C2960S-24PS-L",
            "C2900 | C2900.C2960 | C2900.C2960.C2960S | C2900.C2960S | C2960 | C2960.C2960S | C2960S | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2900.C2960.C2960S | Catalyst.C2900.C2960S | Catalyst.C2960 | Catalyst.C2960S | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.C2960S | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2900.C2960.C2960S | Cisco.Catalyst.C2900.C2960S | Cisco.Catalyst.C2960 | Cisco.Catalyst.C2960S",
        ),
        (
            "Cisco WS-C2960S-F48LPS-L",
            "C2900 | C2900.C2960 | C2900.C2960.C2960S | C2900.C2960S | C2960 | C2960.C2960S | C2960S | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2900.C2960.C2960S | Catalyst.C2900.C2960S | Catalyst.C2960 | Catalyst.C2960S | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.C2960S | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2900.C2960.C2960S | Cisco.Catalyst.C2900.C2960S | Cisco.Catalyst.C2960 | Cisco.Catalyst.C2960S",
        ),
        (
            "Cisco WS-C2960X-24PD-L",
            "C2900 | C2900.C2960 | C2900.C2960.C2960X | C2900.C2960X | C2960 | C2960.C2960X | C2960X | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2900.C2960.C2960X | Catalyst.C2900.C2960X | Catalyst.C2960 | Catalyst.C2960X | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.C2960X | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2900.C2960.C2960X | Cisco.Catalyst.C2900.C2960X | Cisco.Catalyst.C2960 | Cisco.Catalyst.C2960X",
        ),
        (
            "Cisco WS-C2960X-48FPD-L",
            "C2900 | C2900.C2960 | C2900.C2960.C2960X | C2900.C2960X | C2960 | C2960.C2960X | C2960X | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2900.C2960.C2960X | Catalyst.C2900.C2960X | Catalyst.C2960 | Catalyst.C2960X | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.C2960X | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2900.C2960.C2960X | Cisco.Catalyst.C2900.C2960X | Cisco.Catalyst.C2960 | Cisco.Catalyst.C2960X",
        ),
        (
            "Cisco WS-C2960X-48LPS-L",
            "C2900 | C2900.C2960 | C2900.C2960.C2960X | C2900.C2960X | C2960 | C2960.C2960X | C2960X | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2900.C2960.C2960X | Catalyst.C2900.C2960X | Catalyst.C2960 | Catalyst.C2960X | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.C2960X | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2900.C2960.C2960X | Cisco.Catalyst.C2900.C2960X | Cisco.Catalyst.C2960 | Cisco.Catalyst.C2960X",
        ),
        (
            "Cisco WS-C2960X-48TD-L",
            "C2900 | C2900.C2960 | C2900.C2960.C2960X | C2900.C2960X | C2960 | C2960.C2960X | C2960X | Catalyst | Catalyst.C2900 | Catalyst.C2900.C2960 | Catalyst.C2900.C2960.C2960X | Catalyst.C2900.C2960X | Catalyst.C2960 | Catalyst.C2960X | Cisco | Cisco.C2900 | Cisco.C2960 | Cisco.C2960X | Cisco.Catalyst | Cisco.Catalyst.C2900 | Cisco.Catalyst.C2900.C2960 | Cisco.Catalyst.C2900.C2960.C2960X | Cisco.Catalyst.C2900.C2960X | Cisco.Catalyst.C2960 | Cisco.Catalyst.C2960X",
        ),
        (
            "Huawei CE12812",
            "CE | CE.CE12800 | CE12800 | Huawei | Huawei.CE | Huawei.CE.CE12800 | Huawei.CE12800",
        ),
        (
            "Huawei CE5850-48T4S2Q-EI",
            "CE | CE.CE5800 | CE5800 | EI | Huawei | Huawei.CE | Huawei.CE.CE5800 | Huawei.CE5800 | Huawei.EI",
        ),
        (
            "Huawei CE6850-48S4Q-EI",
            "CE | CE.CE6800 | CE.CE6800.CE6850 | CE.CE6850 | CE6800 | CE6800.CE6850 | CE6850 | EI | Huawei | Huawei.CE | Huawei.CE.CE6800 | Huawei.CE.CE6800.CE6850 | Huawei.CE.CE6850 | Huawei.CE6800 | Huawei.CE6850 | Huawei.EI",
        ),
        (
            "Huawei CE6860-48S8CQ-EI",
            "CE | CE.CE6800 | CE.CE6800.CE6860 | CE.CE6860 | CE6800 | CE6800.CE6860 | CE6860 | EI | Huawei | Huawei.CE | Huawei.CE.CE6800 | Huawei.CE.CE6800.CE6860 | Huawei.CE.CE6860 | Huawei.CE6800 | Huawei.CE6860 | Huawei.EI",
        ),
        (
            "Huawei CE6865-48S6CQ-EI",
            "CE | CE.CE6800 | CE.CE6800.CE6865 | CE.CE6865 | CE6800 | CE6800.CE6865 | CE6865 | EI | Huawei | Huawei.CE | Huawei.CE.CE6800 | Huawei.CE.CE6800.CE6865 | Huawei.CE.CE6865 | Huawei.CE6800 | Huawei.CE6865 | Huawei.EI",
        ),
        (
            "Huawei CE6865-48S8CQ-EI",
            "CE | CE.CE6800 | CE.CE6800.CE6865 | CE.CE6865 | CE6800 | CE6800.CE6865 | CE6865 | EI | Huawei | Huawei.CE | Huawei.CE.CE6800 | Huawei.CE.CE6800.CE6865 | Huawei.CE.CE6865 | Huawei.CE6800 | Huawei.CE6865 | Huawei.EI",
        ),
        (
            "Huawei CE6865-48S8CQ-SI",
            "CE | CE.CE6800 | CE.CE6800.CE6865 | CE.CE6865 | CE6800 | CE6800.CE6865 | CE6865 | Huawei | Huawei.CE | Huawei.CE.CE6800 | Huawei.CE.CE6800.CE6865 | Huawei.CE.CE6865 | Huawei.CE6800 | Huawei.CE6865 | Huawei.SI | SI",
        ),
        (
            "Huawei CE6865E-48S8CQ",
            "CE | CE.CE6800 | CE.CE6800.CE6865 | CE.CE6800.CE6865E | CE.CE6865 | CE.CE6865E | CE6800 | CE6800.CE6865 | CE6800.CE6865E | CE6865 | CE6865E | Huawei | Huawei.CE | Huawei.CE.CE6800 | Huawei.CE.CE6800.CE6865 | Huawei.CE.CE6800.CE6865E | Huawei.CE.CE6865 | Huawei.CE.CE6865E | Huawei.CE6800 | Huawei.CE6865 | Huawei.CE6865E",
        ),
        (
            "Huawei CE6870-48S6CQ-EI",
            "CE | CE.CE6800 | CE.CE6800.CE6870 | CE.CE6870 | CE6800 | CE6800.CE6870 | CE6870 | EI | Huawei | Huawei.CE | Huawei.CE.CE6800 | Huawei.CE.CE6800.CE6870 | Huawei.CE.CE6870 | Huawei.CE6800 | Huawei.CE6870 | Huawei.EI",
        ),
        (
            "Huawei CE8850-32CQ-EI",
            "CE | CE.CE8800 | CE.CE8800.CE8850 | CE.CE8850 | CE8800 | CE8800.CE8850 | CE8850 | EI | Huawei | Huawei.CE | Huawei.CE.CE8800 | Huawei.CE.CE8800.CE8850 | Huawei.CE.CE8850 | Huawei.CE8800 | Huawei.CE8850 | Huawei.EI",
        ),
        (
            "Huawei CE8850-64CQ-EI",
            "CE | CE.CE8800 | CE.CE8800.CE8850 | CE.CE8850 | CE8800 | CE8800.CE8850 | CE8850 | EI | Huawei | Huawei.CE | Huawei.CE.CE8800 | Huawei.CE.CE8800.CE8850 | Huawei.CE.CE8850 | Huawei.CE8800 | Huawei.CE8850 | Huawei.EI",
        ),
        (
            "Huawei CE8851-32CQ8DQ-P",
            "CE | CE.CE8800 | CE.CE8800.CE8851 | CE.CE8851 | CE8800 | CE8800.CE8851 | CE8851 | Huawei | Huawei.CE | Huawei.CE.CE8800 | Huawei.CE.CE8800.CE8851 | Huawei.CE.CE8851 | Huawei.CE8800 | Huawei.CE8851",
        ),
        ("Huawei CES6700-48-EI", "EI | Huawei | Huawei.EI"),
        (
            "Huawei LS-S5352C-EI",
            "EI | Huawei | Huawei.EI | Huawei.Quidway | Huawei.Quidway.S5300 | Huawei.S5300 | Quidway | Quidway.S5300 | S5300",
        ),
        (
            "Huawei LS-S5352C-SI",
            "Huawei | Huawei.Quidway | Huawei.Quidway.S5300 | Huawei.S5300 | Huawei.SI | Quidway | Quidway.S5300 | S5300 | SI",
        ),
        (
            "Huawei NE40E-F1A-14H24Q",
            "Huawei | Huawei.NE | Huawei.NE.NE40E | Huawei.NE40E | NE | NE.NE40E | NE40E",
        ),
        (
            "Huawei S5731-S48T4X",
            "Huawei | Huawei.Quidway | Huawei.Quidway.S5700 | Huawei.S5700 | Quidway | Quidway.S5700 | S5700",
        ),
        (
            "Huawei S5735-S48T4XE-V2",
            "Huawei | Huawei.Quidway | Huawei.Quidway.S5700 | Huawei.S5700 | Quidway | Quidway.S5700 | S5700",
        ),
        ("Juniper MX10003", "Juniper | Juniper.MX | MX"),
        ("Juniper MX204", "Juniper | Juniper.MX | MX"),
        ("Juniper MX304", "Juniper | Juniper.MX | MX"),
        (
            "Juniper MX80",
            "Juniper | Juniper.MX | Juniper.MX.MX80 | Juniper.MX80 | MX | MX.MX80 | MX80",
        ),
        (
            "Juniper MX960",
            "Juniper | Juniper.MX | Juniper.MX.MX960 | Juniper.MX960 | MX | MX.MX960 | MX960",
        ),
        ("Juniper PTX10001-36MR", "Juniper | Juniper.PTX | PTX"),
        ("Juniper PTX10002-60C", "Juniper | Juniper.PTX | PTX"),
        ("Juniper QFX10016", "Juniper | Juniper.QFX | QFX"),
        ("Juniper QFX5120-48Y", "Juniper | Juniper.QFX | QFX"),
        ("Juniper QFX5120-48Y-AFO", "Juniper | Juniper.QFX | QFX"),
        (
            "Juniper QFX5200-32C-AFI",
            "Juniper | Juniper.QFX | Juniper.QFX.QFX5200 | Juniper.QFX5200 | QFX | QFX.QFX5200 | QFX5200",
        ),
        (
            "Mellanox SN3700",
            "Mellanox | Mellanox.SN | Mellanox.SN.SN3700 | Mellanox.SN3700 | PC | PC.Mellanox | PC.SN3700 | PC.Whitebox | PC.Whitebox.Mellanox | PC.Whitebox.Mellanox.SN | PC.Whitebox.Mellanox.SN.SN3700 | PC.Whitebox.Mellanox.SN3700 | PC.Whitebox.SN3700 | SN.SN3700 | SN3700 | Whitebox | Whitebox.Mellanox | Whitebox.Mellanox.SN | Whitebox.Mellanox.SN.SN3700 | Whitebox.Mellanox.SN3700 | Whitebox.SN3700",
        ),
        ("Mikrotik CCR1009-7G-1C-1S+", "RouterOS"),
        ("Mikrotik CCR2004-16G-2S+", "RouterOS"),
        ("Mikrotik CCR2116-12G-4S+", "RouterOS"),
        ("Mikrotik CCR2216-1G-12XS-2XQ", "RouterOS"),
        ("Mikrotik CRS326-24G-2S+RM", "RouterOS"),
        ("Moxa NP6610-32-YNDX", "Moxa | PC | PC.Moxa"),
        (
            "NVIDIA MQM9790-NS2R",
            "NVIDIA | PC | PC.NVIDIA | PC.Whitebox | PC.Whitebox.NVIDIA | Whitebox | Whitebox.NVIDIA",
        ),
        (
            "NVIDIA SN5400",
            "NVIDIA | NVIDIA.SN | NVIDIA.SN.SN5400 | NVIDIA.SN5400 | PC | PC.NVIDIA | PC.SN5400 | PC.Whitebox | PC.Whitebox.NVIDIA | PC.Whitebox.NVIDIA.SN | PC.Whitebox.NVIDIA.SN.SN5400 | PC.Whitebox.NVIDIA.SN5400 | PC.Whitebox.SN5400 | SN.SN5400 | SN5400 | Whitebox | Whitebox.NVIDIA | Whitebox.NVIDIA.SN | Whitebox.NVIDIA.SN.SN5400 | Whitebox.NVIDIA.SN5400 | Whitebox.SN5400",
        ),
        (
            "NVIDIA SN5600",
            "NVIDIA | NVIDIA.SN | NVIDIA.SN.SN5600 | NVIDIA.SN5600 | PC | PC.NVIDIA | PC.SN5600 | PC.Whitebox | PC.Whitebox.NVIDIA | PC.Whitebox.NVIDIA.SN | PC.Whitebox.NVIDIA.SN.SN5600 | PC.Whitebox.NVIDIA.SN5600 | PC.Whitebox.SN5600 | SN.SN5600 | SN5600 | Whitebox | Whitebox.NVIDIA | Whitebox.NVIDIA.SN | Whitebox.NVIDIA.SN.SN5600 | Whitebox.NVIDIA.SN5600 | Whitebox.SN5600",
        ),
        ("Nebius Canary", "Nebius | PC | PC.Nebius"),
        ("Nebius NB-D-M-CSM-R", "Nebius | PC | PC.Nebius"),
        ("Nokia 7750 SR1-48D", "NS7750 | Nokia | Nokia.NS7750"),
    ],
)
def test_hardware_view_model(hw_model, expected):
    hw = HardwareView(hw_model, "")
    assert str(hw) == expected
