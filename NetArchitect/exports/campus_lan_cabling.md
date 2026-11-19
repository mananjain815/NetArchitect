# Cabling plan (build this in Packet Tracer / GNS3)

| Link | A | A port | B | B port | Subnet |
|---|---|---|---|---|---|
| LINK_CAMPUS_RTR_L3SW | CAMPUS-RTR | GigabitEthernet0/0 | CAMPUS-L3SW | GigabitEthernet0/1 | 10.10.16.0/30 |
| TRUNK_1 | CAMPUS-L3SW | GigabitEthernet0/2 | CAMPUS-ACCESS-SW1 | GigabitEthernet0/1 | 802.1Q trunk (LACP) |
| TRUNK_2 | CAMPUS-L3SW | GigabitEthernet0/3 | CAMPUS-ACCESS-SW1 | GigabitEthernet0/2 | 802.1Q trunk (LACP) |
