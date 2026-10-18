import json
from collections import Counter, defaultdict

d = json.load(open("samples/match_1914253.json"))

print("== match meta ==")
for k in ["score", "htScore", "ftScore", "statusCode", "startDate", "venueName", "attendance", "referee"]:
    print(f"  {k}: {d.get(k)}")

print("\n== event types (displayName -> value, count) ==")
tc = Counter()
tval = {}
for e in d["events"]:
    t = e["type"]["displayName"]
    tc[t] += 1
    tval[t] = e["type"]["value"]
for t, c in tc.most_common():
    print(f"  {tval[t]:>4}  {t:<22} {c}")

print("\n== outcome types ==")
oc = Counter()
ov = {}
for e in d["events"]:
    o = e["outcomeType"]["displayName"]
    oc[o] += 1
    ov[o] = e["outcomeType"]["value"]
for o, c in oc.most_common():
    print(f"  {ov[o]:>4}  {o:<22} {c}")

print("\n== qualifiers grouped by event type ==")
qby = defaultdict(Counter)
qvals = defaultdict(lambda: defaultdict(set))
for e in d["events"]:
    t = e["type"]["displayName"]
    for q in e.get("qualifiers") or []:
        name = q["type"]["displayName"]
        qby[t][name] += 1
        if len(qvals[t][name]) < 4:
            qvals[t][name].add(str(q.get("value"))[:30])
for t, _ in tc.most_common():
    if not qby[t]:
        continue
    print(f"  {t}:")
    for name, c in qby[t].most_common():
        print(f"      {name:<20} n={c:<5} e.g. {sorted(qvals[t][name])}")

print("\n== team stats: scalar vs per-minute ==")
hs = d["home"]["stats"]
for k, v in hs.items():
    if isinstance(v, dict):
        print(f"  {k:<22} per-minute dict[{len(v)}] e.g. {dict(list(v.items())[:3])}")
    elif isinstance(v, list):
        print(f"  {k:<22} list[{len(v)}]")
    else:
        print(f"  {k:<22} {type(v).__name__} = {v}")

print("\n== player stats fields (GK vs outfield) ==")
for label, pl in [("GK", next(p for p in d["home"]["players"] if p["position"] == "GK")),
                  ("outfield", next(p for p in d["home"]["players"] if p["position"] != "GK"))]:
    print(f"  {label} {pl['name']} ({pl['position']}): {sorted(pl['stats'].keys())}")

print("\n== player metadata keys ==")
print(" ", sorted(d["home"]["players"][0].keys()))
print("\n== home.shotZones keys ==")
print(" ", list(d["home"]["shotZones"].keys()))
print("== home.formations[0] keys ==", sorted(d["home"]["formations"][0].keys()))
print("== home.scores ==", d["home"]["scores"])
print("== incidentEvents[0] ==", json.dumps(d["home"]["incidentEvents"][:1], ensure_ascii=False)[:400])
print("== expandedMinutes ==", {k: (v if not isinstance(v, list) else f"list[{len(v)}]") for k, v in d["expandedMinutes"].items()})
