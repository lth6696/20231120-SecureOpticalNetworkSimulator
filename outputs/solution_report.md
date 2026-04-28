# ILP Solution Report

## Summary
| item | value |
| --- | --- |
| status | Optimal |
| accepted_requests | 5/10 |
| phase1_max_accept | 5 |
| phase2_min_cost | 542.9237 |
| key_rate_cost | 16.8 |
| logical_hop_tiebreak | 0.012 |
| physical_hop_tiebreak | 0.024 |
| security_distance_cost | 476.0877 |
| security_port_cost | 36 |
| security_wavelength_cost | 14 |

## Request To Lightpath Mapping
| request | source_target | bandwidth | security_level | admitted | security_enabled | service_lightpaths | security_lightpaths |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r1 | 5->1 | 1 | 2 | False | False | - | - |
| r2 | 2->4 | 2 | 1 | True | True | (2,3,0), (3,4,1) | (2,3,1), (3,4,0) |
| r3 | 5->2 | 1 | 1 | False | False | - | - |
| r4 | 1->2 | 1 | 1 | True | True | (1,2,1) | (1,2,0) |
| r5 | 4->2 | 1 | 2 | False | False | - | - |
| r6 | 2->4 | 4 | 1 | True | True | (2,4,0) | (2,4,1) |
| r7 | 5->0 | 2 | 2 | True | True | (5,0,0) | (5,0,1) |
| r8 | 2->5 | 2 | 2 | False | False | - | - |
| r9 | 1->5 | 1 | 1 | False | False | - | - |
| r10 | 3->2 | 3 | 1 | True | True | (3,2,1) | (3,2,0) |

## Lightpath To Physical Edge Mapping
| layer | lightpath_mnk | requests | carried_load | physical_edge_ij | wavelength_w | distance |
| --- | --- | --- | --- | --- | --- | --- |
| service | (1,2,1) | r4 | 1 | 1->0 | 1 | 4290.2079 |
| service | (1,2,1) | r4 | 1 | 0->2 | 1 | 7783.6449 |
| service | (2,3,0) | r2 | 2 | 2->0 | 1 | 7783.6449 |
| service | (2,3,0) | r2 | 2 | 0->5 | 1 | 3219.6518 |
| service | (2,3,0) | r2 | 2 | 5->3 | 1 | 7783.6449 |
| service | (2,4,0) | r6 | 4 | 2->0 | 0 | 7783.6449 |
| service | (2,4,0) | r6 | 4 | 0->5 | 0 | 3219.6518 |
| service | (2,4,0) | r6 | 4 | 5->4 | 0 | 4290.2079 |
| service | (3,2,1) | r10 | 3 | 3->5 | 0 | 7783.6449 |
| service | (3,2,1) | r10 | 3 | 5->0 | 0 | 3219.6518 |
| service | (3,2,1) | r10 | 3 | 0->2 | 0 | 7783.6449 |
| service | (3,4,1) | r2 | 2 | 3->5 | 1 | 7783.6449 |
| service | (3,4,1) | r2 | 2 | 5->4 | 1 | 4290.2079 |
| service | (5,0,0) | r7 | 2 | 5->3 | 0 | 7783.6449 |
| service | (5,0,0) | r7 | 2 | 3->2 | 0 | 287.4529 |
| service | (5,0,0) | r7 | 2 | 2->1 | 0 | 3929.1937 |
| service | (5,0,0) | r7 | 2 | 1->0 | 0 | 4290.2079 |
| security | (1,2,0) | r4 | 2 | 1->2 | 1 | 3929.1937 |
| security | (2,3,1) | r2 | 2 | 2->3 | 0 | 287.4529 |
| security | (2,4,1) | r6 | 3 | 2->3 | 1 | 287.4529 |
| security | (2,4,1) | r6 | 3 | 3->4 | 1 | 3929.1937 |
| security | (3,2,0) | r10 | 3 | 3->2 | 1 | 287.4529 |
| security | (3,4,0) | r2 | 2 | 3->4 | 0 | 3929.1937 |
| security | (5,0,1) | r7 | 4 | 5->0 | 1 | 3219.6518 |
