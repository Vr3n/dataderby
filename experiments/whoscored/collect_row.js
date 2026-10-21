// Run inside a whoscored.com page:
//   agent-browser eval -b <base64 of this file with __STAGE__ and __TEAM__ replaced>
// Pivots 9 feed payloads (3 sections x 3 splits) into the 60-column warehouse row.
(async () => {
  const site = require.config.params.site;
  const stageId = __STAGE__;
  const teamId = __TEAM__;
  const sections = { summary: "all", defensive: "defensive", offensive: "offensive" };
  const views = { overall: "Overall", home: "Home", away: "Away" };
  const row = {};

  for (const [warehouseSection, subcategory] of Object.entries(sections)) {
    for (const [viewKey, field] of Object.entries(views)) {
      const q = new URLSearchParams({
        category: "summaryteam",
        subcategory,
        statsAccumulationType: "0",
        field,
        tournamentOptions: "",
        timeOfTheGameStart: "",
        timeOfTheGameEnd: "",
        teamIds: "",
        stageId: String(stageId),
        sortBy: "Rating",
        sortAscending: "",
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
      const d = JSON.parse(await r.text());
      const t = d.teamTableStats.find((x) => x.teamId === teamId);
      if (!t) continue;
      row[`apps_${viewKey}`] = t.apps;
      row[`rating_${viewKey}`] = t.rating;
      row[`ranking_${warehouseSection}_${viewKey}`] = t.ranking;
      if (warehouseSection === "summary") {
        row[`shots_per_game_${viewKey}`] = t.shotsPerGame;
        row[`summary_${viewKey}_goal`] = t.goal;
        row[`summary_${viewKey}_yellow_card`] = t.yellowCard;
        row[`summary_${viewKey}_red_card`] = t.redCard;
        row[`summary_${viewKey}_possession`] = t.possession;
        row[`summary_${viewKey}_pass_success`] = t.passSuccess;
        row[`summary_${viewKey}_aerial_won_per_game`] = t.aerialWonPerGame;
      }
      if (warehouseSection === "defensive") {
        // source name is shotsConcededPerGame, not goals conceded
        row[`defensive_${viewKey}_shots_conceded`] = t.shotsConcededPerGame;
        row[`defensive_${viewKey}_tackles`] = t.tacklePerGame;
        row[`defensive_${viewKey}_interceptions`] = t.interceptionPerGame;
        row[`defensive_${viewKey}_fouls`] = t.foulsPerGame;
        row[`defensive_${viewKey}_offsides`] = t.offsideGivenPerGame;
      }
      if (warehouseSection === "offensive") {
        row[`offensive_${viewKey}_shots_on_target`] = t.shotOnTargetPerGame;
        row[`offensive_${viewKey}_dribbles_won`] = t.dribbleWonPerGame;
        row[`offensive_${viewKey}_fouls_given`] = t.foulGivenPerGame;
      }
    }
  }
  return { stageId, teamId, count: Object.keys(row).length, row };
})()
