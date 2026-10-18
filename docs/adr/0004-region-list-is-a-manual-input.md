# 0004. The region list is a manual input

Status: Accepted (2026-10-08)

## Context

Everything below a region is discoverable from server-rendered HTML, but the list
of regions is not: on a LaLiga page there is no `select#regions`, no `regionId`,
and the only `/regions/` links all point back at region 206, while the control that
would enumerate them is React-rendered and absent from the HTML.

## Decision

Treat the region list as a maintained input (one entry per region, id plus slug)
and discover everything below it — tournaments, seasons, stage ids — from the
region's server-rendered pages.

## Consequences

- The pipeline stays browser-free, which is what keeps `Patchright` out of the
  design.
- The region list is the one piece of Whoscored data we maintain by hand, and it
  will drift silently if the site adds or renames a region.
- Reaching a new region is a config change, not a code change.
