def generate_cisco_configs(network_name: str, allocations: list[dict]) -> dict:
    """Generate a baseline illustrative router/switch config from VLSM allocations."""
    router = [
        "enable", "configure terminal",
        f"hostname {network_name[:25].replace(' ', '-')}-Router",
        "!",
        "! Review interface names and routing design before deployment.",
    ]
    switch = [
        "enable", "configure terminal",
        f"hostname {network_name[:25].replace(' ', '-')}-Switch",
        "!",
    ]
    acl = [
        "!",
        "! Example source allow-list only; adapt to the actual security policy.",
        "ip access-list standard NETARCHITECT-SUBNET-SOURCES",
    ]

    for index, subnet in enumerate(allocations, start=1):
        vlan_id = 10 + (index - 1) * 10
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in subnet["name"].upper())[:20]
        switch.extend([
            f"vlan {vlan_id}",
            f" name {safe_name}",
            "!",
        ])
        if subnet["gateway"] and subnet["prefix"] <= 30:
            router.extend([
                f"interface GigabitEthernet0/0.{vlan_id}",
                f" encapsulation dot1Q {vlan_id}",
                f" ip address {subnet['gateway']} {subnet['subnet_mask']}",
                " no shutdown",
                "!",
            ])
        acl.append(f" permit {subnet['network']} {subnet['wildcard_mask']}")

    switch.extend([
        "interface GigabitEthernet0/1",
        " description Uplink-to-router",
        " switchport mode trunk",
        " switchport trunk allowed vlan " + ",".join(
            str(10 + i * 10) for i in range(len(allocations))
        ),
        " no shutdown",
        "!",
        "end",
        "write memory",
    ])
    router.extend([
        "!",
        "interface GigabitEthernet0/0",
        " description 802.1Q-trunk-to-switch",
        " no shutdown",
        "!",
        "end",
        "write memory",
    ])
    acl.extend(["!", "! ACL is generated as a policy starting point and is not applied automatically.", "end"])

    return {
        "router_config": "\n".join(router) + "\n",
        "switch_config": "\n".join(switch) + "\n",
        "acl_config": "\n".join(acl) + "\n",
        "notes": [
            "Interface names vary by Cisco platform; verify them in Packet Tracer/GNS3.",
            "The generated ACL is an example source allow-list and is intentionally not applied to an interface.",
            "Configure access ports, spanning tree, management access and routing adjacencies for the actual topology.",
            "This baseline does not claim to be a complete production configuration.",
        ],
    }
