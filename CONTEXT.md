# Context: Whoscored data

The ubiquitous language for this project. Definitions only — decisions live in
`docs/adr/`, and the scraping plan lives in `plans/`.

## Domain

**Region**
A geographic grouping of tournaments in the source, identified by a numeric id and
a slug (`206`, `spain`). The top of the hierarchy, and the only level that is not
discoverable from the site's HTML.

**Tournament**
A competition within a region, identified by a globally unique numeric id
(`LaLiga` = 4, `Copa del Rey` = 14, `Segunda División` = 63). *Prefer* over
"competition", which the source uses loosely for the same thing.

**Season**
One edition of a tournament, labelled by the two years it spans in the source
(`2026/2027`). Identified by a season path id (`11213`) that is unique per
tournament, and by a canonical `season_key` we derive (`2026-2027`). Two
tournaments in the same region can share both a label and a `season_key`, so a
season is only ever identified by a tournament **and** a season.

**Stage**
The period of a season that statistics are actually reported against, identified by
`stage_id` (`25662`). A season has one or more stages. Every statistics request is
keyed by stage, not by season, and the stage id appears nowhere except inside a
stage's own page.

**Season key**
Our canonical, human-readable label for a season, `2026-2027`, derived from the
source's `2026/2027`. Half of a season's identity; the tournament completes it.

## Statistics

**Team statistics page**
A stage's team statistics view. Treated as a shell: it renders itself from the
statistics feed, so we read the feed rather than the page.

**Statistics feed**
The single endpoint family behind a team statistics page. Parameterised by
category, subcategory, view and stage.

**Category / Subcategory**
The feed's two-part selector for what is being requested. The subcategories in scope
are the ones behind the Summary, Defensive and Offensive sections.

**Section**
One of the page's top-level tab panels within the team statistics family — in scope:
**Summary**, **Defensive**, **Offensive**. Each section is a distinct request and
carries its own set of metrics. *Prefer* over "tab" (UI framing) and "table family"
(the original plan's term).

**View**
The venue split applied to a section: **Overall**, **Home**, **Away**. Orthogonal to
section, so a (section, view) pair is one request and one set of columns.

**statColumns**
The field list the feed returns alongside its rows, naming the metrics that response
contains. Authoritative for a (section, view): sections do not share a field list.

**Team row**
One team's figures for one (section, view): a `teamId`, a `ranking`, a `rating`, and
one value per entry in that response's `statColumns`.

**Wide row**
Our storage shape: one row per team per season, with every section's and view's
metrics as columns, each prefixed by its section and view
(`defensive_rating`, `offensive_rating`, `summary_rating`).

**ranking**
A team's position in the table, an integer (`1`). Resets per section and view,
because each section sorts by its own metric. **Not** `rating`.

**rating**
The team's performance score, a float (`7.22`). The same team has the same `rating`
in every section. **Not** `ranking`.

## Source behaviour

**Gate**
The source's anti-automation response: HTTP 200 carrying a short HTML page instead
of the requested data. A falsy success, so the body must be inspected before it is
parsed. Distinct from a **block**, which is an outright refusal to serve the page.

**Slug**
The trailing readable segment of a source path (`spain-segunda-división`). Option
values are entity-escaped and percent-encoded on top of each other, so a slug must
be unescaped twice before use.
