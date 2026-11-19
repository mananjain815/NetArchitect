# Cabling plan (build this in Packet Tracer / GNS3)

| Link | A | A port | B | B port | Subnet |
|---|---|---|---|---|---|
| LINK_CITY_1_RTR_L3SW | CITY-1-RTR | GigabitEthernet0/0 | CITY-1-L3SW | GigabitEthernet0/1 | 10.30.8.128/30 |
| LINK_CITY_2_RTR_L3SW | CITY-2-RTR | GigabitEthernet0/0 | CITY-2-L3SW | GigabitEthernet0/1 | 10.30.8.132/30 |
| LINK_CITY_3_RTR_L3SW | CITY-3-RTR | GigabitEthernet0/0 | CITY-3-L3SW | GigabitEthernet0/1 | 10.30.8.136/30 |
| LINK_CITY_4_RTR_L3SW | CITY-4-RTR | GigabitEthernet0/0 | CITY-4-L3SW | GigabitEthernet0/1 | 10.30.8.140/30 |
| LINK_CLOUD_VPC_RTR_L3SW | CLOUD-VPC-RTR | GigabitEthernet0/0 | CLOUD-VPC-L3SW | GigabitEthernet0/1 | 10.30.8.144/30 |
| WAN_CITY_1_CITY_2_1 | CITY-1-RTR | GigabitEthernet0/1 | CITY-2-RTR | GigabitEthernet0/1 | 10.30.8.148/30 |
| WAN_CITY_1_CITY_2_2 | CITY-1-RTR | GigabitEthernet0/2 | CITY-2-RTR | GigabitEthernet0/2 | 10.30.8.152/30 |
| WAN_CITY_1_CITY_3_1 | CITY-1-RTR | GigabitEthernet0/3 | CITY-3-RTR | GigabitEthernet0/1 | 10.30.8.156/30 |
| WAN_CITY_1_CITY_3_2 | CITY-1-RTR | GigabitEthernet0/4 | CITY-3-RTR | GigabitEthernet0/2 | 10.30.8.160/30 |
| WAN_CITY_1_CITY_4_1 | CITY-1-RTR | GigabitEthernet0/5 | CITY-4-RTR | GigabitEthernet0/1 | 10.30.8.164/30 |
| WAN_CITY_1_CITY_4_2 | CITY-1-RTR | GigabitEthernet0/6 | CITY-4-RTR | GigabitEthernet0/2 | 10.30.8.168/30 |
| WAN_CITY_1_CLOUD_VPC_1 | CITY-1-RTR | GigabitEthernet0/7 | CLOUD-VPC-RTR | GigabitEthernet0/1 | 10.30.8.172/30 |
| TRUNK_1 | CITY-1-L3SW | GigabitEthernet0/2 | CITY-1-ACCESS-SW1 | GigabitEthernet0/1 | 802.1Q trunk (LACP) |
| TRUNK_2 | CITY-1-L3SW | GigabitEthernet0/3 | CITY-1-ACCESS-SW1 | GigabitEthernet0/2 | 802.1Q trunk (LACP) |
