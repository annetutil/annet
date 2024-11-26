VENDOR_REVERSES = {
    "huawei": "undo",
    "h3c": "undo",
    "optixtrans": "undo",
    "cisco": "no",
    "nexus": "no",
    "juniper": "delete",
    "arista": "no",
    "nokia": "delete",
    "routeros": "remove",
    "aruba": "no",
    "pc": "-",
    "ribbon": "delete",
    "b4com": "no",
}

VENDOR_DIFF = {
    "huawei": "common.default_diff",
    "optixtrans": "common.default_diff",
    "cisco": "common.default_diff",
    "nexus": "common.default_diff",
    "juniper": "juniper.default_diff",
    "arista": "common.default_diff",
    "nokia": "juniper.default_diff",
    "routeros": "common.default_diff",
    "aruba": "aruba.default_diff",
    "pc": "common.default_diff",
    "ribbon": "ribbon.default_diff",
    "b4com": "common.default_diff",
}

VENDOR_DIFF_ORDERED = {
    "huawei": "common.ordered_diff",
    "optixtrans": "common.ordered_diff",
    "cisco": "common.ordered_diff",
    "nexus": "common.ordered_diff",
    "juniper": "juniper.ordered_diff",
    "arista": "common.ordered_diff",
    "nokia": "juniper.ordered_diff",
    "routeros": "common.ordered_diff",
    "aruba": "common.ordered_diff",
    "pc": "common.ordered_diff",
    "ribbon": "ribbon.default_diff",
    "b4com": "common.ordered_diff",
}

VENDOR_EXIT = {
    "huawei": "quit",
    "h3c": "quit",
    "optixtrans": "quit",
    "cisco": "exit",
    "nexus": "exit",
    "arista": "exit",
    "juniper": "",
    "nokia": "",
    "routeros": "",
    "aruba": "exit",
    "pc": "",
    "ribbon": "exit",
    "b4com": "exit",
}

VENDOR_ALIASES = {
    "h3c": "huawei",
}
