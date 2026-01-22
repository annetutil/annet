import io
import re
from typing import Dict, List, Tuple

from annet import patching
from annet.diff import diff_cmp, diff_ops, gen_pre_as_diff, resort_diff
from annet.types import Diff


before = """
acl number 2610
-     rule 0 permit source 10.1.184.201 0
-     rule 1 permit source 10.15.221.2 0
-     rule 10 permit source  10.25.232.33 0
-     rule 11 permit source 10.15.191.138 0
-     rule 12 permit source  10.18.132.129 0
-     rule 13 permit source  10.18.248.129 0
-     rule 14 permit source  10.25.243.136 0
-     rule 15 permit source 10.19.68.124 0
-     rule 2 permit source  10.5.214.115 0
-     rule 3 permit source  10.25.232.34 0
-     rule 4 permit source 10.1.184.221 0
-     rule 5 permit source 10.3.62.125 0
-     rule 6 permit source 10.8.158.93 0
-     rule 7 permit source 10.133.1.117 0
-     rule 8 permit source 10.15.201.60 0
-     rule 9 permit source 10.0.215.13 0
+     rule 0 permit source  10.5.214.115 0
+     rule 1 permit source 10.19.68.124 0
+     rule 10 permit source  10.18.248.129 0
+     rule 11 permit source 10.15.201.60 0
+     rule 12 permit source 10.0.215.13 0
+     rule 2 permit source 10.133.1.117 0
+     rule 3 permit source 10.1.184.201 0
+     rule 4 permit source  10.25.232.33 0
+     rule 5 permit source  10.25.232.34 0
+     rule 6 permit source  10.25.243.136 0
+     rule 7 permit source 10.8.158.93 0
+     rule 8 permit source  10.18.132.129 0
+     rule 9 permit source  10.18.132.157 0


interface 40GE1/0/14
-     description
-     stp edged-port disable
+     stp edged-port enable

+     mac-address notification learning

bgp 65401
     ipv6-family vpn-instance VpnExample
+         group RR_11 external
+         group RR_12 external
+         group RR_13 external
+         group RR_14 external
+         maximum load-balancing 16
-         maximum load-balancing eibgp 16
-         peer FE80::11:11 advertise-community
-         peer FE80::11:11 bfd enable
-         peer FE80::11:11 bfd min-tx-interval 250 min-rx-interval 250
-         peer FE80::11:11 connect-interface 40GE1/0/17.3001
-         peer FE80::11:12 advertise-community
-         peer FE80::11:12 bfd enable
-         peer FE80::11:12 bfd min-tx-interval 250 min-rx-interval 250
-         peer FE80::11:12 connect-interface 40GE1/0/18.3001
-         peer FE80::11:13 advertise-community
-         peer FE80::11:13 bfd enable
-         peer FE80::11:13 bfd min-tx-interval 250 min-rx-interval 250
-         peer FE80::11:13 connect-interface 40GE1/0/19.3001
-         peer FE80::11:14 advertise-community
-         peer FE80::11:14 bfd enable
-         peer FE80::11:14 bfd min-tx-interval 250 min-rx-interval 250
-         peer FE80::11:14 connect-interface 40GE1/0/20.3001
-         peer FE80::12:11 advertise-community
-         peer FE80::12:11 connect-interface 40GE1/0/17.3001
-         peer FE80::12:12 advertise-community
-         peer FE80::12:12 connect-interface 40GE1/0/18.3001
-         peer FE80::12:13 advertise-community
-         peer FE80::12:13 connect-interface 40GE1/0/19.3001
-         peer FE80::12:14 advertise-community
-         peer FE80::12:14 connect-interface 40GE1/0/20.3001
+         peer FE80::11:11 group RR_11
+         peer FE80::11:12 group RR_12
+         peer FE80::11:13 group RR_13
+         peer FE80::11:14 group RR_14
+         peer FE80::12:11 group RR_11
+         peer FE80::12:12 group RR_12
+         peer FE80::12:13 group RR_13
+         peer FE80::12:14 group RR_14
+         peer RR_11 advertise-community
+         peer RR_11 as-number 64996
+         peer RR_11 connect-interface 40GE1/0/17.3001
+         peer RR_12 advertise-community
+         peer RR_12 as-number 64996
+         peer RR_12 connect-interface 40GE1/0/18.3001
+         peer RR_13 advertise-community
+         peer RR_13 as-number 64996
+         peer RR_13 connect-interface 40GE1/0/19.3001
+         peer RR_14 advertise-community
+         peer RR_14 as-number 64996
+         peer RR_14 connect-interface 40GE1/0/20.3001
"""

want = """
acl number 2610
-     rule 0 permit source 10.1.184.201 0
+     rule 0 permit source  10.5.214.115 0
-     rule 1 permit source 10.15.221.2 0
+     rule 1 permit source 10.19.68.124 0
-     rule 10 permit source  10.25.232.33 0
+     rule 10 permit source  10.18.248.129 0
+     rule 5 permit source  10.25.232.34 0
+     rule 9 permit source  10.18.132.157 0
-     rule 11 permit source 10.15.191.138 0
+     rule 11 permit source 10.15.201.60 0
+     rule 2 permit source 10.133.1.117 0
+     rule 7 permit source 10.8.158.93 0
-     rule 12 permit source  10.18.132.129 0
+     rule 12 permit source 10.0.215.13 0
+     rule 3 permit source 10.1.184.201 0
-     rule 13 permit source  10.18.248.129 0
-     rule 14 permit source  10.25.243.136 0
-     rule 15 permit source 10.19.68.124 0
-     rule 2 permit source  10.5.214.115 0
-     rule 3 permit source  10.25.232.34 0
-     rule 4 permit source 10.1.184.221 0
+     rule 4 permit source  10.25.232.33 0
-     rule 5 permit source 10.3.62.125 0
-     rule 6 permit source 10.8.158.93 0
+     rule 6 permit source  10.25.243.136 0
-     rule 7 permit source 10.133.1.117 0
-     rule 8 permit source 10.15.201.60 0
+     rule 8 permit source  10.18.132.129 0
-     rule 9 permit source 10.0.215.13 0
interface 40GE1/0/14
-     description
-     stp edged-port disable
+     stp edged-port enable
+     mac-address notification learning
bgp 65401
     ipv6-family vpn-instance VpnExample
+         group RR_11 external
+         group RR_12 external
+         group RR_13 external
+         group RR_14 external
-         maximum load-balancing eibgp 16
+         maximum load-balancing 16
-         peer FE80::11:11 advertise-community
-         peer FE80::11:11 bfd enable
-         peer FE80::11:11 bfd min-tx-interval 250 min-rx-interval 250
-         peer FE80::11:11 connect-interface 40GE1/0/17.3001
+         peer FE80::11:11 group RR_11
-         peer FE80::11:12 advertise-community
-         peer FE80::11:12 bfd enable
-         peer FE80::11:12 bfd min-tx-interval 250 min-rx-interval 250
-         peer FE80::11:12 connect-interface 40GE1/0/18.3001
+         peer FE80::11:12 group RR_12
-         peer FE80::11:13 advertise-community
-         peer FE80::11:13 bfd enable
-         peer FE80::11:13 bfd min-tx-interval 250 min-rx-interval 250
-         peer FE80::11:13 connect-interface 40GE1/0/19.3001
+         peer FE80::11:13 group RR_13
-         peer FE80::11:14 advertise-community
-         peer FE80::11:14 bfd enable
-         peer FE80::11:14 bfd min-tx-interval 250 min-rx-interval 250
-         peer FE80::11:14 connect-interface 40GE1/0/20.3001
+         peer FE80::11:14 group RR_14
-         peer FE80::12:11 advertise-community
-         peer FE80::12:11 connect-interface 40GE1/0/17.3001
+         peer FE80::12:11 group RR_11
-         peer FE80::12:12 advertise-community
-         peer FE80::12:12 connect-interface 40GE1/0/18.3001
+         peer FE80::12:12 group RR_12
-         peer FE80::12:13 advertise-community
-         peer FE80::12:13 connect-interface 40GE1/0/19.3001
+         peer FE80::12:13 group RR_13
-         peer FE80::12:14 advertise-community
-         peer FE80::12:14 connect-interface 40GE1/0/20.3001
+         peer FE80::12:14 group RR_14
+         peer RR_11 advertise-community
+         peer RR_11 as-number 64996
+         peer RR_11 connect-interface 40GE1/0/17.3001
+         peer RR_12 advertise-community
+         peer RR_12 as-number 64996
+         peer RR_12 connect-interface 40GE1/0/18.3001
+         peer RR_13 advertise-community
+         peer RR_13 as-number 64996
+         peer RR_13 connect-interface 40GE1/0/19.3001
+         peer RR_14 advertise-community
+         peer RR_14 as-number 64996
+         peer RR_14 connect-interface 40GE1/0/20.3001
"""


def str2diff(raw_diff: str) -> Diff:
    res = []
    for raw_line in raw_diff.splitlines():
        level = 0
        if len(raw_line) < 2:
            continue
        op, line = raw_line.split(maxsplit=1)
        if raw_line[0] not in [x for x in diff_ops.keys() if x != " "]:
            op, line = " ", raw_line
        m = re.match(r"([+-])?(\s+)", raw_line)
        if m:
            level = (len(m.group(2)) - 1) // 4
        diffline: Tuple[str, str, List, Dict] = (
            diff_ops[op],
            line,
            [],
            {"raw_rule": line, "key": 33, "attrs": {"multiline": False}},
        )
        if level == 0:
            res.append(diffline)
        elif level == 1:
            res[-1][2].append(diffline)
        elif level == 2:
            res[-1][2][-1][2].append(diffline)
        else:
            raise Exception("adsfkl;sa")
    return res


def test_sort():
    l1 = (diff_ops["-"], "peer FE80::11:11 bfd min-tx-interval 250 min-rx-interval 250", [], {})
    l2 = (diff_ops["+"], "peer RR_11 advertise-community", [], {})
    assert diff_cmp(l1, l2) == 0
    l1 = (diff_ops["-"], "peer FE80::11:12 advertise-community", [], {})
    l2 = (diff_ops["-"], "peer FE80::11:11 bfd min-tx-interval 250 min-rx-interval 250", [], {})
    assert diff_cmp(l1, l2) == 0
    l1 = (diff_ops["+"], "maximum load-balancing 16", [], {})
    l2 = (diff_ops["-"], "maximum load-balancing eibgp 16", [], {})
    assert diff_cmp(l1, l2) > 0
    l1 = (diff_ops["+"], "rule 0 permit source  10.5.214.115 0", [], {})
    l2 = (diff_ops["-"], "rule 0 permit source 10.1.184.201 0", [], {})
    assert diff_cmp(l1, l2) > 0
    l1 = (diff_ops["+"], "rule 0 permit source  10.5.214.115 0", [], {})
    l2 = (diff_ops["-"], "rule 0 permit source  10.5.214.115 0", [], {})
    assert diff_cmp(l1, l2) > 0
    l1 = (diff_ops["-"], "rule 2 permit source  10.5.214.115 0", [], {})
    l2 = (diff_ops["-"], "rule 10 permit source  10.5.214.115 0", [], {})
    assert diff_cmp(l1, l2) == 0
    l1 = (diff_ops["-"], "rule 2 permit source  10.5.214.115 0", [], {})
    l2 = (diff_ops["-"], "rule 10 permit source  10.25.232.33 0", [], {})
    assert diff_cmp(l1, l2) == 0


def test_diff():
    with io.StringIO() as test_result:
        tf = resort_diff(str2diff(before))
        pd = patching.make_pre(tf)
        for pre_as_diff in gen_pre_as_diff(pd, False, " ", False):
            test_result.write(pre_as_diff)
        actual = test_result.getvalue()
    with io.StringIO() as want_result:
        af = str2diff(want)
        pd = patching.make_pre(af)
        for pre_as_diff in gen_pre_as_diff(pd, False, " ", False):
            want_result.write(pre_as_diff)
        w = want_result.getvalue()
    assert actual == w
