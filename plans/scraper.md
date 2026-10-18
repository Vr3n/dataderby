# Scraping the Whoscored data.

using the `Patchright` package. I have installed it with `uv` and also downloaded the `chromium` binary.

Here's the repository for reference if you need to check the internals and debug: `https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python`

Use the `headed` browser instead of `headless`.

> Superseded for team statistics: the API gives **more** than the HTML (23 fields per
> team against 7 rendered, at full float precision). Team statistics are read from
> the feed with `curl_cffi` and no browser is used. See
> `docs/adr/0001-read-the-statistics-feed-not-the-dom.md` and
> `plans/whoscored_competition_scraper.md`. Patchright remains available for pages
> that are genuinely render-only; the situation and pitch tables use a second
> endpoint and are deferred.

1. For whoscored scraping realated read the `plans/whoscored_competition_scraper.md`
