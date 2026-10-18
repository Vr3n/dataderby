# 0002. Store the feed's own float precision

Status: Accepted (2026-10-08)

## Context

The team statistics page rounds every figure to one decimal place, while the feed
sends full float precision. Storing the rounded value would be simpler to read and
would match what a human sees on the site, but the precision is free in the
response and is not recoverable afterwards without re-scraping the season.

## Decision

Store the value exactly as the feed sends it, unrounded, and leave formatting to
whoever reads the store.

## Consequences

- `shotsPerGame = 21.428571428571427` and `possession = 0.6872857142857143` are what
  land on disk, so stored values look noisy and two sources will disagree at the
  sixth decimal.
- Nothing is lost to rounding, and derived per-90 or per-match figures can be
  computed without error carried from a display string.
- A presentational layer, not the extractor, owns rounding.
