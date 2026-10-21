// Run inside a whoscored.com stage page (the `show` URL):
//   agent-browser eval -b <base64 of this file>
// Returns the league table for all three splits (Overall, Home, Away).
// The table is client-rendered: clicking a split re-renders the same 10-column
// table, so all three views must be read in sequence. `tr[data-team-id]` is the
// stable join key; the rank lives in a span inside the first cell, and the form
// string is one character per match played in that split.
(async () => {
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
    if (!t) return null;
    return [...t.querySelectorAll("tbody tr")].map((tr) => {
      const cell = tr.cells[0];
      const rankText = cell.querySelector("span")?.textContent.trim() ?? "";
      const link = cell.querySelector("a.team-link");
      const values = [...tr.cells].slice(1).map((td) => ({
        text: td.textContent.trim(),
        cls: td.className,
      }));
      const get = (name) => {
        const hit = values.find((v) => v.cls.split(/\s+/).includes(name));
        return hit ? hit.text : null;
      };
      const num = (name) => {
        const v = get(name);
        return v === null || v === "" ? null : Number(v);
      };
      return {
        team_id: tr.getAttribute("data-team-id") ? Number(tr.getAttribute("data-team-id")) : null,
        rank: rankText === "" ? null : Number(rankText),
        team_name: link ? link.textContent.trim() : cell.textContent.replace(/^\d+/, "").trim(),
        played: num("p"),
        won: num("w"),
        drawn: num("d"),
        lost: num("l"),
        goals_for: num("gf"),
        goals_against: num("ga"),
        goal_difference: num("gd"),
        points: num("pts"),
        form: get("form"),
      };
    });
  };
  const splits = {};
  for (const source of ["overall", "home", "away"]) {
    splitLink(source)?.click();
    await new Promise((r) => setTimeout(r, 700));
    splits[source] = read();
  }
  return {
    whoscored_stage_id: Number(location.pathname.match(/stages\/(\d+)/)?.[1] ?? 0),
    whoscored_url: location.href,
    captured_at: new Date().toISOString(),
    splits,
  };
})()
