from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class SubnetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    hosts: int = Field(ge=1, le=65534)


class NetworkRequest(BaseModel):
    profile: Literal["campus_lan", "metro_man", "global_wan", "custom"] = "custom"
    name: str = Field(default="Custom Network", min_length=1, max_length=80)
    endpoints: int = Field(default=100, ge=1, le=100000)
    distance_m: float = Field(default=80, ge=0, le=1000000)
    bandwidth_mbps: int = Field(default=1000, ge=1, le=1000000)
    site_count: int = Field(default=1, ge=1, le=100)
    root_cidr: str = "192.168.0.0/16"
    subnet_requests: list[SubnetRequest] = Field(
        default_factory=lambda: [SubnetRequest(name="USERS", hosts=100)]
    )
    autonomous_systems: int = Field(default=1, ge=1, le=1000)
    external_routing_domain: bool = False
    resiliency: Literal["low", "medium", "high"] = "medium"

    @field_validator("root_cidr")
    @classmethod
    def validate_root_cidr(cls, value: str) -> str:
        import ipaddress
        try:
            network = ipaddress.ip_network(value, strict=True)
        except ValueError as exc:
            raise ValueError(f"Invalid root network: {exc}") from exc
        if network.version != 4:
            raise ValueError("Only IPv4 CIDR networks are supported in this version.")
        return str(network)

    @model_validator(mode="after")
    def validate_subnets(self):
        if not self.subnet_requests:
            raise ValueError("At least one subnet request is required.")
        names = [item.name.strip().lower() for item in self.subnet_requests]
        if len(names) != len(set(names)):
            raise ValueError("Subnet names must be unique.")
        return self
