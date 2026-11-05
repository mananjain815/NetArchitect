import ipaddress


class AddressSpaceExhaustedError(ValueError):
    pass


def wildcard_mask(prefix: int) -> str:
    if not 0 <= prefix <= 32:
        raise ValueError("IPv4 prefix must be between /0 and /32.")
    network = ipaddress.ip_network(f"0.0.0.0/{prefix}")
    wildcard = int(network.hostmask)
    return str(ipaddress.IPv4Address(wildcard))


def _required_prefix(hosts: int) -> int:
    if hosts < 1:
        raise ValueError("Each subnet must request at least one host.")
    # Conventional LAN allocation reserves network and broadcast addresses.
    host_bits = 2
    while (2 ** host_bits) - 2 < hosts:
        host_bits += 1
    return 32 - host_bits


def allocate_vlsm(root_cidr: str, requests: list[dict]) -> dict:
    root = ipaddress.ip_network(root_cidr, strict=True)
    if root.version != 4:
        raise ValueError("Only IPv4 is supported.")

    prepared = []
    for item in requests:
        name = str(item["name"]).strip()
        hosts = int(item["hosts"])
        prefix = _required_prefix(hosts)
        if prefix < root.prefixlen:
            raise AddressSpaceExhaustedError(
                f"{name} needs /{prefix}, larger than available root network {root}."
            )
        prepared.append({"name": name, "hosts": hosts, "prefix": prefix})

    prepared.sort(key=lambda item: (item["prefix"], -item["hosts"]))
    cursor = int(root.network_address)
    root_end = int(root.broadcast_address)
    allocations = []

    for item in prepared:
        block_size = 2 ** (32 - item["prefix"])
        aligned = ((cursor + block_size - 1) // block_size) * block_size
        end = aligned + block_size - 1
        if aligned < int(root.network_address) or end > root_end:
            raise AddressSpaceExhaustedError(
                f"Address space exhausted while allocating {item['name']} ({item['hosts']} hosts) "
                f"inside {root}."
            )

        subnet = ipaddress.ip_network((aligned, item["prefix"]))
        if subnet.network_address not in root or subnet.broadcast_address not in root:
            raise AddressSpaceExhaustedError(f"{subnet} does not fit inside {root}.")

        if item["prefix"] <= 30:
            first_usable = subnet.network_address + 1
            last_usable = subnet.broadcast_address - 1
            gateway = str(first_usable)
            usable_count = subnet.num_addresses - 2
        else:
            # The normal allocator won't generate /31 or /32 for LAN host requests.
            first_usable = subnet.network_address
            last_usable = subnet.broadcast_address
            gateway = None
            usable_count = subnet.num_addresses

        allocations.append({
            "name": item["name"],
            "requested_hosts": item["hosts"],
            "network": str(subnet.network_address),
            "cidr": str(subnet),
            "prefix": item["prefix"],
            "subnet_mask": str(subnet.netmask),
            "wildcard_mask": str(subnet.hostmask),
            "first_usable": str(first_usable),
            "last_usable": str(last_usable),
            "gateway": gateway,
            "broadcast": str(subnet.broadcast_address),
            "usable_addresses": usable_count,
            "utilization_percent": round(item["hosts"] / usable_count * 100, 2),
        })
        cursor = end + 1

    return {
        "root_network": str(root),
        "allocations": allocations,
        "allocation_order": [item["name"] for item in prepared],
        "rationale": (
            "Requests are sorted by descending subnet size, then aligned to their block boundaries. "
            "Each allocation advances the cursor beyond the previous broadcast address, preventing overlap."
        ),
    }
