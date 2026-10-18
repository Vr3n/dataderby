# dataderby

WhoScored scraper toolkit: a working HTTP client and reverse-engineering notes.

- **API & site analysis:** [`docs/whoscored-api.md`](docs/whoscored-api.md)
- **Client:** `src/dataderby/client.py`
- **Example:** `uv run python examples/team_season_stats.py`

```python
from dataderby.client import get_team_statistics, session

s = session()
rows = get_team_statistics(s, stage_id=25662)["teamTableStats"]  # La Liga 2026/27
```

Requires `curl_cffi` (Chrome TLS impersonation) — plain `requests` gets HTTP 403.
