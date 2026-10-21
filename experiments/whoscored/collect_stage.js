// Run inside a whoscored.com page:
//   agent-browser eval -b <base64 of this file with __STAGE__ replaced>
// Returns the three Overall section payloads for one stage.
(async () => {
  const site = require.config.params.site;
  const stageId = __STAGE__;
  const sections = ["all", "defensive", "offensive"];
  const out = { stageId, sections: {} };
  for (const section of sections) {
    const q = new URLSearchParams({
      category: "summaryteam",
      subcategory: section,
      statsAccumulationType: "0",
      field: "Overall",
      tournamentOptions: "",
      timeOfTheGameStart: "",
      timeOfTheGameEnd: "",
      teamIds: "",
      stageId: String(stageId),
      sortBy: section === "defensive" ? "tacklePerGame" : "shotsPerGame",
      sortAscending: "false",
      page: "",
      numberOfTeamsToPick: "",
      isCurrent: "true",
      formation: "",
      incPens: "",
      against: "",
    });
    const r = await fetch(`/statisticsfeed/1/getteamstatistics?${q}`, {
      headers: {
        Accept: "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        [site.gSiteHeaderName]: site.gSiteHeaderValue,
      },
    });
    const txt = await r.text();
    try {
      const d = JSON.parse(txt);
      out.sections[section] = {
        rows: d.teamTableStats.length,
        cols: d.statColumns,
        first: d.teamTableStats[0]
          ? `${d.teamTableStats[0].teamId}:${d.teamTableStats[0].teamName}`
          : null,
      };
    } catch (e) {
      out.sections[section] = { error: `status ${r.status}`, head: txt.slice(0, 40) };
    }
  }
  return out;
})()
