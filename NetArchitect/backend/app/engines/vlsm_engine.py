"""Bitwise VLSM allocator (stdlib `ipaddress` is used only for parsing/printing; the block
arithmetic - alignment, sizing, overlap checks - is done with explicit integer bit operations)."""
import ipaddress
import math


class AddressSpaceExhaustedError(ValueError):
    pass


def prefix_to_mask_int(prefix: int) -> int:
    if not isinstance(prefix, int) or not 0 <= prefix <= 32:
        raise ValueError("IPv4 prefix must be an integer between /0 and /32.")
    return (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF if prefix else 0


def int_to_ip(value: int) -> str:
    return ".".join(str((value >> s) & 0xFF) for s in (24, 16, 8, 0))


def wildcard_mask(prefix: int) -> str:
    """Wildcard (inverse) mask = bitwise NOT of the subnet mask, e.g. /26 -> 0.0.0.63."""
    return int_to_ip(~prefix_to_mask_int(prefix) & 0xFFFFFFFF)


def subnet_mask(prefix: int) -> str:
    return int_to_ip(prefix_to_mask_int(prefix))


def required_prefix(hosts: int) -> int:
    """Smallest host-bit count n with 2^n - 2 >= hosts (network + broadcast reserved); min /30."""
    if hosts < 1:
        raise ValueError("Each subnet must request at least one host.")
    n = 2
    while (1 << n) - 2 < hosts:
        n += 1
    if n > 32:
        raise AddressSpaceExhaustedError("Host request does not fit in IPv4.")
    return 32 - n


_required_prefix = required_prefix  # backwards-compatible alias


def _entry(name, hosts, subnet_int, prefix, **extra):
    size = 1 << (32 - prefix)
    net = subnet_int
    bcast = net + size - 1
    usable = size - 2
    row = {
        "name": name,
        "requested_hosts": hosts,
        "network": int_to_ip(net),
        "cidr": f"{int_to_ip(net)}/{prefix}",
        "prefix": prefix,
        "subnet_mask": subnet_mask(prefix),
        "wildcard_mask": wildcard_mask(prefix),
        "first_usable": int_to_ip(net + 1),
        "last_usable": int_to_ip(bcast - 1),
        "gateway": int_to_ip(net + 1),
        "broadcast": int_to_ip(bcast),
        "block_size": size,
        "usable_addresses": usable,
        "utilization_percent": round(hosts / usable * 100, 2),
        "math": f"2^{32 - prefix} - 2 = {usable} usable >= {hosts} hosts -> /{prefix}",
    }
    row.update(extra)
    return row


def allocate_vlsm(root_cidr: str, requests: list[dict]) -> dict:
    """Flat VLSM: sort descending, align each block to its own size, never overlap."""
    root = ipaddress.ip_network(root_cidr, strict=True)
    if root.version != 4:
        raise ValueError("Only IPv4 is supported.")
    root_start = int(root.network_address)
    root_end = int(root.broadcast_address)

    prepared = []
    for item in requests:
        name = str(item["name"]).strip()
        hosts = int(item["hosts"])
        prefix = required_prefix(hosts)
        if prefix < root.prefixlen:
            raise AddressSpaceExhaustedError(
                f"{name} needs /{prefix}, larger than available root network {root}."
            )
        prepared.append({"name": name, "hosts": hosts, "prefix": prefix})

    prepared.sort(key=lambda i: (i["prefix"], -i["hosts"], i["name"]))
    cursor = root_start
    allocations = []
    for item in prepared:
        size = 1 << (32 - item["prefix"])
        aligned = (cursor + size - 1) & ~(size - 1)  # round UP to a multiple of size
        end = aligned + size - 1
        if aligned < root_start or end > root_end:
            raise AddressSpaceExhaustedError(
                f"Address space exhausted while allocating {item['name']} ({item['hosts']} hosts) inside {root}."
            )
        allocations.append(_entry(item["name"], item["hosts"], aligned, item["prefix"]))
        cursor = end + 1

    allocated = sum(a["block_size"] for a in allocations)
    requested = sum(a["requested_hosts"] for a in allocations)
    usable = sum(a["usable_addresses"] for a in allocations)
    return {
        "root_network": str(root),
        "allocations": allocations,
        "allocation_order": [i["name"] for i in prepared],
        "total_requested_hosts": requested,
        "total_allocated_addresses": allocated,
        "root_size": root.num_addresses,
        "root_utilization_percent": round(allocated / root.num_addresses * 100, 3),
        "host_efficiency_percent": round(requested / usable * 100, 2),
        "rationale": _rationale(root, allocations, requested, usable, allocated),
    }


def _rationale(root, allocations, requested, usable, allocated) -> str:
    lines = [
        f"Requests were sorted by descending size and each block was aligned to a multiple of its own "
        f"size inside {root} (block start = ceil(cursor / size) x size), so no block can overlap the previous one.",
    ]
    for a in allocations:
        lines.append(
            f"{a['name']}: {a['requested_hosts']} hosts -> {a['math']} -> {a['cidr']} "
            f"({a['utilization_percent']}% used)."
        )
    lines.append(
        f"Total: {requested} hosts requested in {usable} usable addresses = "
        f"{round(requested / usable * 100, 1)}% host efficiency; {allocated} of {root.num_addresses} "
        f"addresses ({round(allocated / root.num_addresses * 100, 2)}%) of {root} consumed, leaving "
        f"{root.num_addresses - allocated} addresses free for growth."
    )
    return " ".join(lines)


def _next_pow2_prefix(total_addresses: int) -> int:
    bits = max(2, math.ceil(math.log2(total_addresses)))
    return 32 - bits


def allocate_hierarchical(root_cidr: str, sites: list[dict], requests: list[dict],
                          infra_requests: list[dict]) -> dict:
    """Hierarchical VLSM: every site receives ONE aligned supernet (so it can be summarised with a
    single `area range` / BGP aggregate), and subnets are VLSM-allocated inside it.

    sites: [{"name","subnets":[names],"external":bool}]
    """
    root = ipaddress.ip_network(root_cidr, strict=True)
    root_start, root_end = int(root.network_address), int(root.broadcast_address)
    req_by_name = {r["name"].strip().lower(): r for r in requests}

    blocks = []  # (label, prefix, [requests], external)
    for site in sites:
        site_reqs = [req_by_name[n.strip().lower()] for n in site["subnets"]]
        need = sum(1 << (32 - required_prefix(int(r["hosts"]))) for r in site_reqs)
        blocks.append({"name": site["name"], "prefix": _next_pow2_prefix(need),
                       "reqs": site_reqs, "external": site.get("external", False), "kind": "lan"})
    if infra_requests:
        need = sum(1 << (32 - required_prefix(int(r["hosts"]))) for r in infra_requests)
        blocks.append({"name": "INFRA", "prefix": _next_pow2_prefix(need), "reqs": infra_requests,
                       "external": False, "kind": "p2p"})
    # largest supernet first (descending); external sites last among equals so they never sit
    # inside the corporate aggregate
    blocks.sort(key=lambda b: (b["prefix"], b["external"], b["name"]))

    cursor = root_start
    allocations, site_blocks = [], []
    for b in blocks:
        if b["prefix"] < root.prefixlen:
            raise AddressSpaceExhaustedError(f"Site {b['name']} needs a /{b['prefix']}, larger than {root}.")
        size = 1 << (32 - b["prefix"])
        start = (cursor + size - 1) & ~(size - 1)
        end = start + size - 1
        if end > root_end:
            raise AddressSpaceExhaustedError(
                f"Address space exhausted allocating the {b['name']} supernet (/{b['prefix']}) inside {root}."
            )
        supernet = ipaddress.ip_network((start, b["prefix"]))
        inner = allocate_vlsm(str(supernet), b["reqs"])
        for a in inner["allocations"]:
            a["site"] = b["name"]
            a["kind"] = b["kind"]
            allocations.append(a)
        used = inner["total_allocated_addresses"]
        site_blocks.append({
            "site": b["name"], "cidr": str(supernet), "kind": b["kind"], "external": b["external"],
            "size": size, "used_addresses": used,
            "utilization_percent": round(used / size * 100, 2),
        })
        cursor = end + 1

    allocations.sort(key=lambda a: int(ipaddress.ip_address(a["network"])))
    allocated = sum(b["size"] for b in site_blocks)
    requested = sum(a["requested_hosts"] for a in allocations if a["kind"] == "lan")
    usable_lan = sum(a["usable_addresses"] for a in allocations if a["kind"] == "lan")
    rationale = (
        f"Hierarchical VLSM: each site gets one power-of-two supernet sized to the sum of its subnet "
        f"blocks, supernets are placed largest-first on their own size boundary, then subnets are VLSM-"
        f"allocated largest-first inside each supernet. "
        + " ".join(
            f"{b['site']} -> {b['cidr']} ({b['utilization_percent']}% of block used)."
            for b in site_blocks
        )
        + f" LAN hosts requested: {requested} in {usable_lan} usable addresses "
        f"({round(requested / usable_lan * 100, 1)}% host efficiency). {allocated} of {root.num_addresses} "
        f"addresses of {root} are reserved ({round(allocated / root.num_addresses * 100, 2)}%)."
    )
    return {
        "root_network": str(root),
        "allocations": allocations,
        "site_blocks": site_blocks,
        "allocation_order": [a["name"] for a in allocations],
        "total_requested_hosts": requested,
        "total_allocated_addresses": allocated,
        "root_size": root.num_addresses,
        "root_utilization_percent": round(allocated / root.num_addresses * 100, 3),
        "host_efficiency_percent": round(requested / usable_lan * 100, 2) if usable_lan else 0,
        "rationale": rationale,
    }
