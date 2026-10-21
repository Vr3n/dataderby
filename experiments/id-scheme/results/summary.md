# id scheme — measured results

DuckDB 1.5.6 · Python 3.12.13 · scale 500 observations

| test | A-derived | B-ulid | B-null |
|---|---|---|---|
| T01 first observation | PASS 1 | PASS 1 | PASS 1 |
| T02a identical publish is a no-op | PASS no_change | PASS no_change | PASS no_change |
| T02b no rows written on no-change | PASS [1, 20, 1, 'da9105976402deba3e09e6d5eb06d9ee29eec4d5f78886ffb15284ceeef3cb61'] | PASS [1, 20, 1, 'da9105976402deba3e09e6d5eb06d9ee29eec4d5f78886ffb15284ceeef3cb61'] | PASS [1, 20, 1, 'da9105976402deba3e09e6d5eb06d9ee29eec4d5f78886ffb15284ceeef3cb61'] |
| T03 revert A->B->A is recorded | PASS 3 | PASS 3 | PASS 3 |
| T04a rollback leaves no partial rows | PASS [1, 20] | PASS [1, 20] | PASS [1, 20] |
| T04b killed process leaves no committed rows | PASS 0 | PASS 0 | PASS 0 |
| T05 stale checkpoint cannot duplicate an existing edge | PASS 2 | PASS 2 | PASS 2 |
| T06a rebuild reproduces the same ids | PASS True | FAIL False | FAIL False |
| T06b a report pinned to the original id resolves after rebuild | PASS 20 | FAIL 0 | FAIL 0 |
| T06c a report pinned to (stage, observed_at) resolves after rebuild | PASS 20 | PASS 20 | PASS 20 |
| T07 same content under a different parent is a new row | PASS 2 | PASS 2 | PASS 2 |
| T08 root edge deduped by the database | PASS 1 | PASS 1 | FAIL 2 |
| T09 second writer is refused | PASS True | PASS True | PASS True |
| T10 500 observations -> 500 distinct ids | PASS 500 | PASS 500 | PASS 500 |
| T10b no id collisions | PASS 500 | PASS 500 | PASS 500 |
| T11 ids independent of process/hash seed | PASS True | FAIL False | FAIL False |
| T12a latest state returns 20 rows | PASS 20 | PASS 20 | PASS 20 |
| T12b latest state values are correct | PASS 10138 | PASS 10138 | PASS 10138 |
| T13a delta equals 1 for every consecutive pair | PASS 0 | PASS 0 | PASS 0 |
| T13b first observation has no delta | PASS 20 | PASS 20 | PASS 20 |
| T14 orphan fact row is rejected | PASS True | PASS True | PASS True |
| T16a a missing value is stored as NULL | PASS None | PASS None | PASS None |
| T16b exactly one NULL cell, never a zero | PASS 1 | PASS 1 | PASS 1 |
| T15 id collision-free over 1000 | PASS 1000 | PASS 1000 | PASS 1000 |

| metric | A-derived | B-ulid | B-null |
|---|---|---|---|
| duckdb | 1.5.6 | 1.5.6 | 1.5.6 |
| python | 3.12.13 | 3.12.13 | 3.12.13 |
| scale | 500 | 500 | 500 |
| insert_ms_total | 37748.8 | 55056.8 | 44839.8 |
| insert_ms_p50 | 70.6 | 94.936 | 81.506 |
| insert_ms_p95 | 102.688 | 182.784 | 128.902 |
| noop_ms_p50 | 4.932 | 6.132 | 4.45 |
| latest_query_ms_p50 | 5.813 | 6.827 | 9.249 |
| delta_query_ms_p50 | 9.219 | 10.869 | 12.046 |
| db_bytes | 5779456 | 6041600 | 6041600 |
| id_length | 37 | 26 | 26 |
| id_ascending_ratio | 0.492 | 0.513 | 0.51 |
| snapshots | 500 | 500 | 500 |
| fact_rows | 10000 | 10000 | 10000 |
