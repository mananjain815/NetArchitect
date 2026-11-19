"""Cisco IOS configuration generator (Packet Tracer / GNS3 friendly).

Per site it emits:   <SITE>-RTR (router)  +  <SITE>-L3SW (multilayer switch with SVIs, DHCP, ACLs)
For the hub site it also emits a representative <SITE>-ACCESS-SW1 (L2 access switch, RSTP, port security).
Everything is derived from the allocator output - nothing is hard coded per profile.
"""
import ipaddress
import re

from app.engines.vlsm_engine import wildcard_mask, subnet_mask

NATIVE_VLAN = 999
EVC_BASE = 200
PLACEHOLDER = "CHANGE_ME_BEFORE_DEPLOY"
CORP_ASN, EXT_ASN = 65001, 65002   # private ASNs, RFC 6996


# ------------------------------------------------------------------------------------------ helpers
def safe(text: str, upper=False) -> str:
    """Make arbitrary text safe for IOS identifiers/descriptions: no whitespace, newlines or symbols."""
    out = re.sub(r"[^A-Za-z0-9_.\-]", "-", str(text)).strip("-")[:32] or "X"
    return out.upper() if upper else out


def hostname(site: str, role: str) -> str:
    return f"{safe(site).replace('_', '-')}-{role}"


def role_of(name: str) -> str:
    n = name.upper()
    if "MGMT" in n or "MANAGEMENT" in n:
        return "mgmt"
    if "ADMIN" in n:
        return "admin"
    if "SERVER" in n or "CLOUD" in n:
        return "server"
    if "IOT" in n or "SENSOR" in n or "SCANNER" in n:
        return "iot"
    if "GUEST" in n:
        return "guest"
    return "user"


def resolve_sites(request) -> list[dict]:
    names = [s.name for s in request.subnet_requests]
    if request.sites:
        sites = [{"name": s.name, "external": s.external,
                  "subnets": [next(n for n in names if n.lower() == x.strip().lower()) for x in s.subnets]}
                 for s in request.sites]
    elif request.site_count == 1:
        sites = [{"name": "CAMPUS" if request.profile == "campus_lan" else "MAIN",
                  "external": False, "subnets": names}]
    else:
        if len(names) < request.site_count:
            raise ValueError("Provide at least one subnet per site (or supply 'sites').")
        sites = [{"name": f"SITE{i + 1}", "external": False, "subnets": []} for i in range(request.site_count)]
        for i, n in enumerate(names):
            sites[i % request.site_count]["subnets"].append(n)
    hubs = [s for s in sites if not s["external"]]
    if not hubs:
        raise ValueError("At least one site must be inside the corporate AS (external=false).")
    hub = hubs[0]
    sites = [hub] + [s for s in sites if s is not hub]
    area = 0
    for s in sites:
        if s is hub or s["external"]:
            s["area"] = 0
        else:
            area += 1
            s["area"] = area
    for i, s in enumerate(sites):
        s["index"] = i
    return sites


def plan_links(sites: list[dict], resiliency: str) -> list[dict]:
    """Point-to-point links that need a /30 each."""
    links = []
    for s in sites:
        links.append({"name": f"LINK_{s['name']}_RTR_L3SW", "kind": "uplink", "site": s["name"],
                      "a": hostname(s["name"], "RTR"), "b": hostname(s["name"], "L3SW")})
    hub = sites[0]
    for s in sites[1:]:
        count = 2 if (resiliency == "high" and not s["external"]) else 1
        for n in range(1, count + 1):
            links.append({"name": f"WAN_{hub['name']}_{s['name']}_{n}", "kind": "wan", "site": s["name"],
                          "n": n, "a": hostname(hub["name"], "RTR"), "b": hostname(s["name"], "RTR")})
    return links


class _Cfg:
    def __init__(self):
        self.lines: list[str] = []

    def add(self, *items):
        self.lines.extend(items)

    def text(self):
        return "\n".join(self.lines) + "\n"


def _header(c: _Cfg, host: str, banner: str):
    c.add("enable", "configure terminal", f"hostname {host}", "!",
          f"! NetArchitect - {banner}", "! Replace every CHANGE_ME_BEFORE_DEPLOY value before production use.", "!",
          "no ip domain-lookup", "service password-encryption", "ip domain-name netarchitect.local",
          f"enable secret {PLACEHOLDER}", f"username netadmin privilege 15 secret {PLACEHOLDER}",
          "crypto key generate rsa modulus 2048", "ip ssh version 2", "!")


def _footer(c: _Cfg):
    c.add("!", "line console 0", " logging synchronous", " exec-timeout 10 0", "!",
          "line vty 0 4", " login local", " transport input ssh", " exec-timeout 10 0", "!",
          "end", "write memory")


# ------------------------------------------------------------------------------------------- ACLs
def build_acls(lan: list[dict], root_cidr: str) -> dict[str, dict]:
    """Return {subnet_name: {"acl_name", "lines"}} - inbound ACL for each LAN subnet's SVI."""
    root = ipaddress.ip_network(root_cidr)
    root_spec = f"{root.network_address} {root.hostmask}"
    servers = [a for a in lan if role_of(a["name"]) == "server"]
    protected = [a for a in lan if role_of(a["name"]) in ("server", "admin", "mgmt")]
    out = {}
    for a in lan:
        role = role_of(a["name"])
        me = f"{a['network']} {a['wildcard_mask']}"
        L = [f" remark NetArchitect policy: role={role} subnet={a['cidr']}"]
        if role in ("user", "admin", "iot", "guest"):
            L.append(" permit udp host 0.0.0.0 host 255.255.255.255 eq 67")      # DHCP discover/request
        if role in ("iot", "guest"):
            L.append(f" permit udp {me} host {a['gateway']} eq 67")              # DHCP renew to the gateway
        if role == "user":
            for s in servers:
                sp = f"{s['network']} {s['wildcard_mask']}"
                L += [f" permit tcp {me} {sp} eq 80", f" permit tcp {me} {sp} eq 443",
                      f" permit udp {me} {sp} eq 53", f" permit icmp {me} {sp} echo"]
            for p in protected:
                L.append(f" deny ip {me} {p['network']} {p['wildcard_mask']}")
            L.append(f" permit ip {me} any")
        elif role in ("admin", "mgmt"):
            L.append(f" permit ip {me} any")
        elif role in ("iot", "guest"):
            for s in servers:
                sp = f"{s['network']} {s['wildcard_mask']}"
                L += [f" permit udp {me} {sp} eq 53", f" permit tcp {me} {sp} eq 443"]
                if role == "iot":
                    L += [f" permit udp {me} {sp} eq 123", f" permit tcp {me} {sp} eq 8883"]
            L += [f" deny ip {me} {root_spec}", f" permit ip {me} any"]
        elif role == "server":
            L += [f" permit tcp {me} any established", f" permit udp {me} eq 53 any",
                  f" permit icmp {me} any echo-reply"]
        L.append(" deny ip any any")
        name = f"ACL-{safe(a['name'], upper=True)}-IN"
        out[a["name"]] = {"acl_name": name, "lines": ["ip access-list extended " + name] + L, "role": role}
    return out


# ------------------------------------------------------------------------------- main generator
def generate_configs(request, sites, vlsm, routing, media, topology) -> dict:
    allocs = {a["name"]: a for a in vlsm["allocations"]}
    lan_all = [a for a in vlsm["allocations"] if a["kind"] == "lan"]
    root = ipaddress.ip_network(request.root_cidr)
    root_wild = f"{root.network_address} {root.hostmask}"

    # stable VLAN numbering by request order
    vlan_id = {s.name: 10 * (i + 1) for i, s in enumerate(request.subnet_requests)}
    acls = build_acls(lan_all, request.root_cidr)
    links = plan_links(sites, request.resiliency)
    for L in links:
        L["alloc"] = allocs[L["name"]]
        net = ipaddress.ip_network(L["alloc"]["cidr"])
        hosts = list(net.hosts())
        L["ip_a"], L["ip_b"], L["mask"], L["wild"] = str(hosts[0]), str(hosts[1]), str(net.netmask), str(net.hostmask)

    multi_area = routing["multi_area"]
    use_bgp = routing["uses_bgp"]
    ipsec = request.wan_service == "ipsec"
    evpl = request.wan_service == "evpl"
    qos = request.max_latency_ms is not None or evpl
    hub = sites[0]
    dual = request.resiliency in ("medium", "high")
    notes = [
        "Interface names assume Packet Tracer 2911 routers (Gi0/0..) and 3560 / 2960 switches; adapt to your platform.",
        "Hub router needs one routed port per WAN link - add NIM/HWIC modules or use a larger router.",
        "On dot1q-only switches (3650/9300) remove 'switchport trunk encapsulation dot1q'.",
        f"All secrets are the placeholder {PLACEHOLDER}.",
    ]
    if routing["protocol"] == "Multi-Area OSPF" and len(sites) == 1:
        notes.append("Single-site design with >=50 subnets: all VLANs are placed in Area 0 here; split by building "
                     "into additional areas if the LSDB grows.")
    if ipsec:
        notes.append("IKE/IPsec uses SHA-256 / DH group 14. Packet Tracer only supports SHA-1 and DH 1/2/5: "
                     "swap the marked '! PACKET TRACER' alternatives in.")

    devices: dict[str, str] = {}
    cabling: list[dict] = []

    # corporate aggregate (BGP) : cover all non-external LAN supernets, unless it would swallow external space
    corp_blocks = [ipaddress.ip_network(b["cidr"]) for b in vlsm["site_blocks"]
                   if b["kind"] == "lan" and not b["external"]]
    ext_blocks = [ipaddress.ip_network(b["cidr"]) for b in vlsm["site_blocks"] if b["external"]]
    aggregate = None
    if corp_blocks:
        lo = min(int(n.network_address) for n in corp_blocks)
        hi = max(int(n.broadcast_address) for n in corp_blocks)
        agg = ipaddress.ip_network((lo, 32))
        for p in range(32, -1, -1):
            cand = ipaddress.ip_network((lo, p), strict=False)
            if int(cand.network_address) <= lo and int(cand.broadcast_address) >= hi:
                agg = cand
                break
        if not any(agg.overlaps(e) for e in ext_blocks):
            aggregate = agg

    link_by = {(L["name"]): L for L in links}
    wan_ifc: dict[str, int] = {}      # next WAN interface index per router

    def next_wan(router):
        wan_ifc[router] = wan_ifc.get(router, 0) + 1
        return f"GigabitEthernet0/{wan_ifc[router]}"

    # assign interfaces once so both ends agree
    for L in links:
        if L["kind"] == "uplink":
            L["if_a"], L["if_b"] = "GigabitEthernet0/0", "GigabitEthernet0/1"
        else:
            L["if_a"], L["if_b"] = next_wan(L["a"]), next_wan(L["b"])
            L["evc"] = EVC_BASE + links.index(L)
        cabling.append({"link": L["name"], "a": L["a"], "if_a": L["if_a"], "b": L["b"], "if_b": L["if_b"],
                        "subnet": L["alloc"]["cidr"], "ip_a": L["ip_a"], "ip_b": L["ip_b"]})

    for s in sites:
        site_lan = [allocs[n] for n in s["subnets"]]
        rtr, sw = hostname(s["name"], "RTR"), hostname(s["name"], "L3SW")
        up = next(L for L in links if L["kind"] == "uplink" and L["site"] == s["name"])
        wans = [L for L in links if L["kind"] == "wan" and s["name"] in (L["site"],)] if s is not hub else \
               [L for L in links if L["kind"] == "wan"]
        area = s["area"] if multi_area else 0
        acc_lan = [a for a in site_lan if role_of(a["name"]) != "server"]
        acc_vlans = ",".join(str(vlan_id[a["name"]]) for a in acc_lan)
        all_vlans = [vlan_id[a["name"]] for a in site_lan]

        # ======================================================================= L3 switch
        c = _Cfg()
        _header(c, sw, f"{s['name']} multilayer switch: SVIs, RSTP, DHCP, ACLs, OSPF")
        c.add("ip routing", "!",
              "spanning-tree mode rapid-pvst",
              ("spanning-tree vlan " + ",".join(map(str, all_vlans)) + " priority 4096") if all_vlans else "!", "!",
              f"vlan {NATIVE_VLAN}", " name NATIVE_UNUSED")
        for a in site_lan:
            c.add(f"vlan {vlan_id[a['name']]}", f" name {safe(a['name'], True)}")
        c.add("!")
        for a in site_lan:
            r = role_of(a["name"])
            if r not in ("server", "mgmt"):
                first = ipaddress.ip_address(a["gateway"])
                last_excl = min(int(first) + 9, int(ipaddress.ip_address(a["last_usable"])) - 1)
                if last_excl > int(first):
                    c.add(f"ip dhcp excluded-address {a['gateway']} {ipaddress.ip_address(last_excl)}")
                else:
                    c.add(f"ip dhcp excluded-address {a['gateway']}")
                c.add(f"ip dhcp pool {safe(a['name'], True)}", f" network {a['network']} {a['subnet_mask']}",
                      f" default-router {a['gateway']}", "!")
        for a in site_lan:
            c.add(f"interface Vlan{vlan_id[a['name']]}", f" description GW-{safe(a['name'], True)}",
                  f" ip address {a['gateway']} {a['subnet_mask']}",
                  f" ip access-group {acls[a['name']]['acl_name']} in", " no shutdown", "!")
        c.add(f"interface {up['if_b']}", f" description UPLINK-TO-{rtr}", " no switchport",
              f" ip address {up['ip_b']} {up['mask']}",
              " ip ospf network point-to-point", " no shutdown", "!")
        if s is hub and acc_vlans:
            members = ["GigabitEthernet0/2", "GigabitEthernet0/3"] if dual else ["GigabitEthernet0/2"]
            for m in members:
                c.add(f"interface {m}", f" description TRUNK-TO-{hostname(s['name'], 'ACCESS-SW1')}",
                      " switchport trunk encapsulation dot1q", " switchport mode trunk",
                      " switchport nonegotiate")
                if dual:
                    c.add(" channel-group 1 mode active")
                else:
                    c.add(f" switchport trunk native vlan {NATIVE_VLAN}", f" switchport trunk allowed vlan {acc_vlans}")
                c.add(" no shutdown", "!")
            if dual:
                c.add("interface Port-channel1", " description LACP-TRUNK-TO-ACCESS",
                      " switchport trunk encapsulation dot1q", " switchport mode trunk",
                      f" switchport trunk native vlan {NATIVE_VLAN}", f" switchport trunk allowed vlan {acc_vlans}", "!")
        c.add("! --- ACL definitions (applied inbound on each SVI above) ---")
        for a in site_lan:
            c.add(*acls[a["name"]]["lines"])
        c.add("!", "router ospf 1", f" router-id 10.255.{s['index'] + 1}.1", " passive-interface default",
              f" no passive-interface {up['if_b']}", " auto-cost reference-bandwidth 10000")
        for a in site_lan:
            c.add(f" network {a['network']} {a['wildcard_mask']} area {area}")
        c.add(f" network {up['ip_b']} 0.0.0.0 area {area}")
        _footer(c)
        devices[f"{sw}.cfg"] = c.text()

        # ======================================================================= router
        c = _Cfg()
        _header(c, rtr, f"{s['name']} router: routing, WAN links" + (", QoS" if qos else "") + (", IPsec" if ipsec else ""))
        my_wans = [L for L in links if L["kind"] == "wan" and (rtr in (L["a"], L["b"]))]
        c.add(f"interface {up['if_a']}", f" description DOWNLINK-TO-{sw}", f" ip address {up['ip_a']} {up['mask']}",
              " ip ospf network point-to-point", " no shutdown", "!")

        if qos and my_wans:
            crit = [a for a in lan_all if role_of(a["name"]) == "server"]
            c.add("ip access-list extended QOS-CRITICAL")
            for a in crit:
                c.add(f" permit ip any {a['network']} {a['wildcard_mask']}", f" permit ip {a['network']} {a['wildcard_mask']} any")
            if not crit:
                c.add(" permit tcp any any eq 443")
            c.add("class-map match-any VOICE", " match dscp ef",
                  "class-map match-any CRITICAL", " match access-group name QOS-CRITICAL", " match dscp af31 af41",
                  "policy-map WAN-QOS", " class VOICE", "  priority percent 20",
                  " class CRITICAL", "  bandwidth percent 40", " class class-default", "  fair-queue", "!")

        if ipsec and my_wans:
            c.add("! --- IKE phase 1 / IPsec phase 2 ---", "crypto isakmp policy 10", " encryption aes 256",
                  " hash sha256", " authentication pre-share", " group 14", " lifetime 86400",
                  "! PACKET TRACER: use ' hash sha' and ' group 5' instead of sha256 / group 14",
                  "crypto ipsec transform-set TS-AES256 esp-aes 256 esp-sha256-hmac", " mode tunnel",
                  "! PACKET TRACER: use 'esp-aes 256 esp-sha-hmac'", "!")
        acl_no = 100
        for L in my_wans:
            is_a = (L["a"] == rtr)
            my_if, my_ip = (L["if_a"], L["ip_a"]) if is_a else (L["if_b"], L["ip_b"])
            peer_ip = L["ip_b"] if is_a else L["ip_a"]
            primary = (L.get("n", 1) == 1)
            peer_site = next(x for x in sites if x["name"] == L["site"])
            if ipsec:
                acl_no += 1
                spoke_block = next(b for b in vlsm["site_blocks"] if b["site"] == L["site"])
                sb = ipaddress.ip_network(spoke_block["cidr"])
                a_spec, b_spec = (root_wild, f"{sb.network_address} {sb.hostmask}")
                src, dst = (a_spec, b_spec) if is_a else (b_spec, a_spec)
                c.add(f"access-list {acl_no} permit ip {src} {dst}",
                      f"crypto isakmp key {PLACEHOLDER} address {peer_ip}",
                      f"crypto map VPN-{L['n']}-{safe(L['site'], True)} 10 ipsec-isakmp",
                      f" set peer {peer_ip}", " set transform-set TS-AES256", f" match address {acl_no}", "!")
            if evpl:
                c.add(f"interface {my_if}", f" description EVPL-PHYSICAL-{safe(L['name'])}", " no ip address")
                if qos:
                    c.add(" service-policy output WAN-QOS")
                c.add(" no shutdown", "!", f"interface {my_if}.{L['evc']}",
                      f" description EVPL-EVC-{L['evc']}-TO-{safe(L['b'] if is_a else L['a'])}",
                      f" encapsulation dot1Q {L['evc']}", f" ip address {my_ip} {L['mask']}")
            else:
                c.add(f"interface {my_if}", f" description WAN-TO-{safe(L['b'] if is_a else L['a'])}",
                      f" ip address {my_ip} {L['mask']}")
                if qos:
                    c.add(" service-policy output WAN-QOS")
                if ipsec:
                    c.add(f" crypto map VPN-{L['n']}-{safe(L['site'], True)}")
            if not peer_site["external"]:
                c.add(" ip ospf network point-to-point", f" ip ospf cost {10 if primary else 100}")
            c.add(" no shutdown", "!")

        # ---- OSPF
        my_site_is_ext = s["external"]
        c.add("router ospf 1", f" router-id 10.255.{s['index'] + 1}.2", " auto-cost reference-bandwidth 10000",
              f" network {up['ip_a']} 0.0.0.0 area {area}")
        if s is hub:
            for L in my_wans:
                tgt = next(x for x in sites if x["name"] == L["site"])
                if tgt["external"]:
                    continue
                ar = tgt["area"] if multi_area else 0
                c.add(f" network {L['ip_a']} 0.0.0.0 area {ar}")
            if multi_area:
                for tgt in sites[1:]:
                    if tgt["external"]:
                        continue
                    blk = ipaddress.ip_network(next(b for b in vlsm["site_blocks"] if b["site"] == tgt["name"])["cidr"])
                    c.add(f" area {tgt['area']} range {blk.network_address} {blk.netmask}")
        elif not my_site_is_ext:
            for L in my_wans:
                c.add(f" network {L['ip_b']} 0.0.0.0 area {area}")
        if use_bgp and (s is hub or my_site_is_ext):
            c.add(f" redistribute bgp {EXT_ASN if my_site_is_ext else CORP_ASN} subnets")

        # ---- BGP
        if use_bgp and (s is hub or my_site_is_ext):
            ext_link = next((L for L in links if L["kind"] == "wan" and
                             next(x for x in sites if x["name"] == L["site"])["external"]), None)
            if ext_link:
                if s is hub:
                    peer, asn, my_asn = ext_link["ip_b"], EXT_ASN, CORP_ASN
                    out_nets = [aggregate] if aggregate else [ipaddress.ip_network(b["cidr"]) for b in vlsm["site_blocks"]
                                                              if b["kind"] == "lan" and not b["external"]]
                    in_nets = [ipaddress.ip_network(a["cidr"]) for a in lan_all
                               if next(x for x in sites if x["name"] == a["site"])["external"]]
                else:
                    peer, asn, my_asn = ext_link["ip_a"], CORP_ASN, EXT_ASN
                    out_nets = [ipaddress.ip_network(a["cidr"]) for a in site_lan]
                    in_nets = [aggregate] if aggregate else [ipaddress.ip_network(b["cidr"]) for b in vlsm["site_blocks"]
                                                             if b["kind"] == "lan" and not b["external"]]
                c.add("!", f"router bgp {my_asn}", f" bgp router-id 10.255.{s['index'] + 1}.2", " bgp log-neighbor-changes",
                      f" neighbor {peer} remote-as {asn}", f" neighbor {peer} description EBGP-AS{asn}",
                      f" neighbor {peer} prefix-list PL-OUT out", f" neighbor {peer} prefix-list PL-IN in")
                for n in out_nets:
                    c.add(f" network {n.network_address} mask {n.netmask}")
                c.add("!")
                for i, n in enumerate(out_nets, 1):
                    c.add(f"ip prefix-list PL-OUT seq {i * 5} permit {n}")
                for i, n in enumerate(in_nets, 1):
                    c.add(f"ip prefix-list PL-IN seq {i * 5} permit {n}")
                if s is hub and aggregate:
                    c.add(f"ip route {aggregate.network_address} {aggregate.netmask} Null0",
                          "! Null0 route anchors the aggregate so BGP can originate it (route summarisation)")
        _footer(c)
        devices[f"{rtr}.cfg"] = c.text()

        # ======================================================================= access switch (hub only)
        if s is hub and acc_lan:
            c = _Cfg()
            acc = hostname(s["name"], "ACCESS-SW1")
            _header(c, acc, f"{s['name']} access switch (template - replicate per closet): RSTP, port security")
            c.add("spanning-tree mode rapid-pvst", "spanning-tree portfast bpduguard default", "!",
                  f"vlan {NATIVE_VLAN}", " name NATIVE_UNUSED")
            for a in acc_lan:
                c.add(f"vlan {vlan_id[a['name']]}", f" name {safe(a['name'], True)}")
            c.add("!")
            port = 1
            for a in acc_lan:
                if role_of(a["name"]) == "mgmt":
                    continue
                end = min(port + 3, 20)
                if port > 20:
                    break
                c.add(f"interface range FastEthernet0/{port} - {end}", f" description ACCESS-{safe(a['name'], True)}",
                      " switchport mode access", f" switchport access vlan {vlan_id[a['name']]}",
                      " switchport nonegotiate", " spanning-tree portfast", " spanning-tree bpduguard enable",
                      " switchport port-security", " switchport port-security maximum 2",
                      " switchport port-security violation restrict", " switchport port-security mac-address sticky",
                      " no shutdown", "!")
                port = end + 1
            if port <= 24:
                c.add(f"interface range FastEthernet0/{port} - 24", " description UNUSED-PARKED",
                      " switchport mode access", f" switchport access vlan {NATIVE_VLAN}", " shutdown", "!")
            ups = ["GigabitEthernet0/1", "GigabitEthernet0/2"] if dual else ["GigabitEthernet0/1"]
            for u in ups:
                c.add(f"interface {u}", f" description TRUNK-TO-{sw}", " switchport mode trunk", " switchport nonegotiate")
                if dual:
                    c.add(" channel-group 1 mode active")
                else:
                    c.add(f" switchport trunk native vlan {NATIVE_VLAN}", f" switchport trunk allowed vlan {acc_vlans}")
                c.add(" no shutdown", "!")
            if dual:
                c.add("interface Port-channel1", " description LACP-TRUNK-TO-L3SW", " switchport mode trunk",
                      f" switchport trunk native vlan {NATIVE_VLAN}", f" switchport trunk allowed vlan {acc_vlans}", "!")
            mg = next((a for a in acc_lan if role_of(a["name"]) == "mgmt"), None)
            if mg:
                ip = ipaddress.ip_address(mg["gateway"]) + 1
                c.add(f"interface Vlan{vlan_id[mg['name']]}", " description MANAGEMENT",
                      f" ip address {ip} {mg['subnet_mask']}", " no shutdown", f"ip default-gateway {mg['gateway']}")
            _footer(c)
            devices[f"{acc}.cfg"] = c.text()
            for i, u in enumerate(ups):
                cabling.append({"link": f"TRUNK_{i + 1}", "a": sw, "if_a": f"GigabitEthernet0/{i + 2}",
                                "b": acc, "if_b": u, "subnet": "802.1Q trunk" + (" (LACP)" if dual else ""),
                                "ip_a": "", "ip_b": ""})

    # ============================================================================ standalone ACL file
    c = _Cfg()
    c.add("enable", "configure terminal", "!", "! NetArchitect inter-VLAN policy bundle (same ACLs are already inside the L3SW files).",
          "! Apply with:  interface VlanX / ip access-group <name> in")
    for a in lan_all:
        c.add(*acls[a["name"]]["lines"])
    c.add("!", "end", "write memory")
    devices["POLICY-ACLS.cfg"] = c.text()

    bundle = []
    for fname, text in devices.items():
        bundle.append(f"!{'=' * 70}\n! FILE: {fname}\n!{'=' * 70}\n{text}")
    return {
        "devices": devices,
        "bundle": "\n".join(bundle),
        "cabling": cabling,
        "vlan_ids": vlan_id,
        "acls": {n: v["lines"] for n, v in acls.items()},
        "aggregate": str(aggregate) if aggregate else None,
        "notes": notes,
        # kept for backward compatibility with the starter UI
        "router_config": next(v for k, v in devices.items() if k.endswith("-RTR.cfg")),
        "switch_config": next(v for k, v in devices.items() if k.endswith("-L3SW.cfg")),
        "acl_config": devices["POLICY-ACLS.cfg"],
    }
