"""Tiny extended-ACL evaluator used to *verify* generated ACLs with packet-flow tests.

Supports exactly the IOS syntax NetArchitect emits:
    permit|deny <ip|tcp|udp|icmp> <src> [eq N] <dst> [eq N | established | echo | echo-reply] [log]
where <src>/<dst> is `any`, `host A.B.C.D` or `A.B.C.D wildcard`.
First match wins; implicit deny at the end - exactly like IOS.
"""
import ipaddress
from dataclasses import dataclass
from typing import Optional


@dataclass
class Packet:
    proto: str                 # ip | tcp | udp | icmp
    src: str
    dst: str
    sport: Optional[int] = None
    dport: Optional[int] = None
    established: bool = False  # TCP ACK/RST bit set (reply traffic)
    icmp_type: Optional[str] = None  # echo | echo-reply


def _addr(tokens, i):
    if tokens[i] == "any":
        return ("any",), i + 1
    if tokens[i] == "host":
        return ("host", int(ipaddress.ip_address(tokens[i + 1]))), i + 2
    return ("net", int(ipaddress.ip_address(tokens[i])), int(ipaddress.ip_address(tokens[i + 1]))), i + 2


def _match_addr(spec, ip: str) -> bool:
    v = int(ipaddress.ip_address(ip))
    if spec[0] == "any":
        return True
    if spec[0] == "host":
        return v == spec[1]
    _, base, wild = spec
    return (v & ~wild & 0xFFFFFFFF) == (base & ~wild & 0xFFFFFFFF)


def parse_rule(line: str):
    t = line.split()
    if len(t) < 4 or t[0] not in ("permit", "deny"):
        return None
    action, proto = t[0], t[1]
    i = 2
    src, i = _addr(t, i)
    sport = dport = None
    est = False
    icmp_t = None
    if i < len(t) and t[i] == "eq":
        sport = int(t[i + 1]); i += 2
    dst, i = _addr(t, i)
    while i < len(t):
        if t[i] == "eq":
            dport = int(t[i + 1]); i += 2
        elif t[i] == "established":
            est = True; i += 1
        elif t[i] in ("echo", "echo-reply"):
            icmp_t = t[i]; i += 1
        elif t[i] == "log":
            i += 1
        else:
            raise ValueError(f"Unsupported ACL token {t[i]!r} in: {line}")
    return {"action": action, "proto": proto, "src": src, "dst": dst, "sport": sport,
            "dport": dport, "est": est, "icmp": icmp_t, "text": line.strip()}


def extract_acl(config_text: str, name: str) -> list[dict]:
    """Pull the rules of `ip access-list extended <name>` out of a config."""
    rules, inside = [], False
    for raw in config_text.splitlines():
        line = raw.strip()
        if line.startswith("ip access-list extended"):
            inside = line.split()[-1] == name
            continue
        if inside:
            if not raw.startswith(" "):
                break
            if line.startswith("remark") or not line:
                continue
            r = parse_rule(line)
            if r:
                rules.append(r)
    return rules


def evaluate(rules: list[dict], pkt: Packet) -> tuple[str, Optional[str]]:
    for r in rules:
        if r["proto"] != "ip" and r["proto"] != pkt.proto:
            continue
        if not _match_addr(r["src"], pkt.src) or not _match_addr(r["dst"], pkt.dst):
            continue
        if r["sport"] is not None and r["sport"] != pkt.sport:
            continue
        if r["dport"] is not None and r["dport"] != pkt.dport:
            continue
        if r["est"] and not pkt.established:
            continue
        if r["icmp"] is not None and r["icmp"] != pkt.icmp_type:
            continue
        return r["action"], r["text"]
    return "deny", "implicit deny"
