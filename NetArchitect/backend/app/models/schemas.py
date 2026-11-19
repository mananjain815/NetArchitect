import ipaddress
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Only characters that are safe to place inside an IOS hostname / VLAN name / description.
# Newlines and other control characters are rejected here AND sanitised again in the
# config generator (defence in depth - see ai_audit_log.md, case 3).
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]*$")


class SubnetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=40)
    hosts: int = Field(ge=1, le=65534)

    @field_validator("name")
    @classmethod
    def _safe(cls, v: str) -> str:
        v = v.strip()
        if not SAFE_NAME.match(v):
            raise ValueError("Subnet name may only contain letters, digits, space, '_', '-' and '.'.")
        return v


class Site(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=30)
    subnets: list[str] = Field(default_factory=list)
    external: bool = False  # True => belongs to a different autonomous system (e.g. cloud VPC)

    @field_validator("name")
    @classmethod
    def _safe(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$", v):
            raise ValueError("Site name may only contain letters, digits, '_' and '-'.")
        return v.upper()


class NetworkRequest(BaseModel):
    # extra="forbid" so a mistyped / unsupported field is an error, never silently ignored
    model_config = ConfigDict(extra="forbid")

    profile: Literal["campus_lan", "metro_man", "global_wan", "custom"] = "custom"
    name: str = Field(default="Custom Network", min_length=1, max_length=80)
    endpoints: int = Field(default=100, ge=1, le=100000)
    distance_m: float = Field(default=80, ge=1, le=1000000)          # longest backbone / WAN link
    access_distance_m: float = Field(default=90, ge=1, le=100000)    # longest access-layer run
    bandwidth_mbps: int = Field(default=1000, ge=1, le=100000)       # backbone / WAN rate
    access_bandwidth_mbps: int = Field(default=1000, ge=1, le=100000)
    requested_media: Literal["auto", "copper", "om4", "os2"] = "auto"
    site_count: int = Field(default=1, ge=1, le=100)                 # geographically separate sites
    building_count: int = Field(default=1, ge=1, le=100)             # buildings inside a campus
    sites: list[Site] = Field(default_factory=list)
    root_cidr: str = "192.168.0.0/16"
    subnet_requests: list[SubnetRequest] = Field(
        default_factory=lambda: [SubnetRequest(name="USERS", hosts=100)]
    )
    autonomous_systems: int = Field(default=1, ge=1, le=1000)
    external_routing_domain: bool = False
    resiliency: Literal["low", "medium", "high"] = "medium"
    wan_service: Literal["p2p", "evpl", "ipsec"] = "p2p"
    max_latency_ms: Optional[float] = Field(default=None, gt=0, le=10000)

    @field_validator("name")
    @classmethod
    def _safe_name(cls, v: str) -> str:
        v = v.strip()
        if not SAFE_NAME.match(v):
            raise ValueError("Network name may only contain letters, digits, space, '_', '-' and '.'.")
        return v

    @field_validator("root_cidr")
    @classmethod
    def validate_root_cidr(cls, value: str) -> str:
        try:
            network = ipaddress.ip_network(value, strict=True)
        except ValueError as exc:
            raise ValueError(f"Invalid root network: {exc}") from exc
        if network.version != 4:
            raise ValueError("Only IPv4 CIDR networks are supported in this version.")
        if network.prefixlen > 24:
            raise ValueError("Root network must be /24 or larger to hold a multi-subnet design.")
        return str(network)

    @model_validator(mode="after")
    def validate_subnets(self):
        if not self.subnet_requests:
            raise ValueError("At least one subnet request is required.")
        names = [item.name.strip().lower() for item in self.subnet_requests]
        if len(names) != len(set(names)):
            raise ValueError("Subnet names must be unique.")
        if len(self.subnet_requests) > 300:
            raise ValueError("At most 300 subnets are supported (VLAN numbering limit).")
        if self.sites:
            site_names = [s.name for s in self.sites]
            if len(site_names) != len(set(site_names)):
                raise ValueError("Site names must be unique.")
            known = {n.strip().lower() for n in names}
            used: list[str] = []
            for s in self.sites:
                for sn in s.subnets:
                    if sn.strip().lower() not in known:
                        raise ValueError(f"Site {s.name} references unknown subnet '{sn}'.")
                    used.append(sn.strip().lower())
            if len(used) != len(set(used)):
                raise ValueError("A subnet may belong to only one site.")
            if set(used) != known:
                raise ValueError("Every subnet must be assigned to exactly one site.")
            if len(self.sites) != self.site_count:
                raise ValueError("site_count must equal the number of entries in 'sites'.")
        return self
