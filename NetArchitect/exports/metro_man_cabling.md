# Cabling plan (build this in Packet Tracer / GNS3)

| Link | A | A port | B | B port | Subnet |
|---|---|---|---|---|---|
| LINK_HQ_RTR_L3SW | HQ-RTR | GigabitEthernet0/0 | HQ-L3SW | GigabitEthernet0/1 | 10.20.3.0/30 |
| LINK_REMOTE_A_RTR_L3SW | REMOTE-A-RTR | GigabitEthernet0/0 | REMOTE-A-L3SW | GigabitEthernet0/1 | 10.20.3.4/30 |
| LINK_REMOTE_B_RTR_L3SW | REMOTE-B-RTR | GigabitEthernet0/0 | REMOTE-B-L3SW | GigabitEthernet0/1 | 10.20.3.8/30 |
| WAN_HQ_REMOTE_A_1 | HQ-RTR | GigabitEthernet0/1 | REMOTE-A-RTR | GigabitEthernet0/1 | 10.20.3.12/30 |
| WAN_HQ_REMOTE_A_2 | HQ-RTR | GigabitEthernet0/2 | REMOTE-A-RTR | GigabitEthernet0/2 | 10.20.3.16/30 |
| WAN_HQ_REMOTE_B_1 | HQ-RTR | GigabitEthernet0/3 | REMOTE-B-RTR | GigabitEthernet0/1 | 10.20.3.20/30 |
| WAN_HQ_REMOTE_B_2 | HQ-RTR | GigabitEthernet0/4 | REMOTE-B-RTR | GigabitEthernet0/2 | 10.20.3.24/30 |
| TRUNK_1 | HQ-L3SW | GigabitEthernet0/2 | HQ-ACCESS-SW1 | GigabitEthernet0/1 | 802.1Q trunk (LACP) |
| TRUNK_2 | HQ-L3SW | GigabitEthernet0/3 | HQ-ACCESS-SW1 | GigabitEthernet0/2 | 802.1Q trunk (LACP) |
