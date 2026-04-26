# ILP Solution Report

## Summary
| item | value |
| --- | --- |
| status | Optimal |
| accepted_requests | 10/10 |
| phase1_max_accept | 10 |
| phase2_min_cost | 646.3998 |
| key_rate_cost | 16.8 |
| logical_hop_tiebreak | 0.04 |
| physical_hop_tiebreak | 0.013 |
| security_distance_cost | 587.5468 |
| security_port_cost | 30 |
| security_wavelength_cost | 12 |

## Request To Lightpath Mapping
| request | source_target | bandwidth | security_level | admitted | security_enabled | service_lightpaths | security_lightpaths |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r1 | 5->1 | 1 | 1 | True | True | (5,0,0), (0,1,0) | (5,0,1), (0,1,1) |
| r2 | 5->4 | 3 | 1 | True | True | (5,4,1) | (5,0,1), (0,1,1), (1,2,1), (2,4,0) |
| r3 | 2->4 | 2 | 1 | True | True | (2,4,1) | (2,4,0) |
| r4 | 5->2 | 1 | 2 | True | True | (5,0,0), (0,1,0), (1,2,0) | (5,0,1), (0,1,1), (1,2,1) |
| r5 | 1->3 | 1 | 1 | True | True | (1,2,0), (2,4,1), (4,3,0) | (1,2,1), (2,4,0), (4,3,1) |
| r6 | 2->3 | 2 | 1 | True | True | (2,4,1), (4,3,0) | (2,4,0), (4,3,1) |
| r7 | 4->3 | 2 | 2 | True | True | (4,3,0) | (4,3,1) |
| r8 | 2->4 | 4 | 2 | True | True | (2,4,1) | (2,4,0) |
| r9 | 0->1 | 1 | 1 | True | True | (0,1,0) | (0,1,1) |
| r10 | 5->3 | 4 | 2 | True | True | (5,4,1), (4,3,0) | (5,0,1), (0,1,1), (1,2,1), (2,4,0), (4,3,1) |

## Lightpath To Physical Edge Mapping
| layer | lightpath_mnk | requests | carried_load | physical_edge_ij | wavelength_w | distance |
| --- | --- | --- | --- | --- | --- | --- |
| service | (1,2,0) | r4, r5 | 2 | 1->2 | 0 | 3929.1937 |
| service | (2,4,1) | r3, r5, r6, r8 | 9 | 2->3 | 0 | 287.4529 |
| service | (2,4,1) | r3, r5, r6, r8 | 9 | 3->4 | 1 | 3929.1937 |
| service | (4,3,0) | r5, r6, r7, r10 | 9 | 4->3 | 1 | 3929.1937 |
| service | (5,4,1) | r2, r10 | 7 | 5->4 | 0 | 4290.2079 |
| service | (5,0,0) | r1, r4 | 2 | 5->0 | 0 | 3219.6518 |
| service | (0,1,0) | r1, r4, r9 | 3 | 0->1 | 0 | 4290.2079 |
| security | (1,2,1) | r2, r4, r5, r10 | 6 | 1->2 | 1 | 3929.1937 |
| security | (2,4,0) | r2, r3, r5, r6, r8, r10 | 8 | 2->3 | 1 | 287.4529 |
| security | (2,4,0) | r2, r3, r5, r6, r8, r10 | 8 | 3->4 | 0 | 3929.1937 |
| security | (4,3,1) | r5, r6, r7, r10 | 6 | 4->3 | 0 | 3929.1937 |
| security | (5,0,1) | r1, r2, r4, r10 | 6 | 5->0 | 1 | 3219.6518 |
| security | (0,1,1) | r1, r2, r4, r9, r10 | 7 | 0->1 | 1 | 4290.2079 |
