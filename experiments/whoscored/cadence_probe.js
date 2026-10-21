// One cadence probe. Run inside a WhoScored stage page:
//   agent-browser eval -b <base64 of this file>
// Returns a compact fingerprint of the standings (3 views) and the 9 feed payloads.
// The caller logs one JSON object per interval; the first changed hash after a
// final whistle is the publication-lag observation.
(async () => {
  const site = require.config.params.site;
  const stageId = Number(location.pathname.match(/stages\/(\d+)/)?.[1] ?? 0);
  const table = () => document.querySelector('table[id^="standings-"]');
  const splitLink = (source) => {
    const t = table();
    if (!t) return null;
    let best = null;
    let bestDistance = Infinity;
    for (const a of document.querySelectorAll(`a.option[data-source="${source}"]`)) {
      const d = Math.abs(a.getBoundingClientRect().top - t.getBoundingClientRect().top);
      if (d < bestDistance) {
        bestDistance = d;
        best = a;
      }
    }
    return best;
  };
  const read = () => {
    const t = table();
    if (!t) return [];
    return [...t.querySelectorAll("tbody tr")].map((tr) => {
      const cell = tr.cells[0];
      const values = [...tr.cells].slice(1).map((td) => td.textContent.trim());
      return [
        Number(tr.getAttribute("data-team-id")),
        Number(cell.querySelector("span")?.textContent.trim() ?? 0),
        Number(values[0]), Number(values[1]), Number(values[2]), Number(values[3]),
        Number(values[4]), Number(values[5]), Number(values[6]), Number(values[7]),
        values[8] ?? "",
      ];
    });
  };
  const splits = {};
  for (const source of ["overall", "home", "away"]) {
    splitLink(source)?.click();
    await new Promise((r) => setTimeout(r, 700));
    splits[source] = read();
  }
  const encoder = new TextEncoder();
  const sha = async (text) => {
    const bytes = new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(text)));
    return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  };
  const standingsHash = await sha(JSON.stringify(splits));

  const headers = {
    Accept: "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    [site.gSiteHeaderName]: site.gSiteHeaderValue,
  };
  const feedParts = [];
  for (const section of ["summary", "defensive", "offensive"]) {
    for (const view of ["Overall", "Home", "Away"]) {
      const q = new URLSearchParams({
        category: "summaryteam",
        subcategory: section === "summary" ? "all" : section,
        statsAccumulationType: "0",
        field: view,
        tournamentOptions: "",
        timeOfTheGameStart: "",
        timeOfTheGameEnd: "",
        teamIds: "",
        stageId: String(stageId),
        sortBy: "Rating",
        sortAscending: "false",
        page: "",
        numberOfTeamsToPick: "",
        isCurrent: "true",
        formation: "",
        incPens: "",
        against: "",
      });
      const r = await fetch(`/statisticsfeed/1/getteamstatistics?${q}`, {
        headers,
        cache: "no-store",
      });
      feedParts.push(await r.text());
    }
  }
  const feedHash = await sha(feedParts.join("\n"));
  const leader = splits.overall[0];
  return {
    t: new Date().toISOString(),
    stageId,
    standingsHash,
    feedHash,
    teams: splits.overall.length,
    leader: leader ? { team_id: leader[0], rank: leader[1], played: leader[2], points: leader[9] } : null,
    feedBytes: feedParts.reduce((a, b) => a + b.length, 0),
  };
})()
