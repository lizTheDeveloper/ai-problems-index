#!/usr/bin/env python3
"""[RETIRED — the front-page scoreboard was replaced by the Risk Atlas scorecard.]
Render the threat scoreboard into index_live.html from the school-owned
`risk_scoreboard` DB table. The DB is the source of truth; this only injects
the SCORE array between the /*SCOREBOARD-START*/.../*SCOREBOARD-END*/ markers."""
import json, os, subprocess, sys

SQL = ("SELECT json_agg(json_build_object("
       "'name',name,'state',state,'trend',trend,'conf',conf,'go',go_tab,'why',why) "
       "ORDER BY ord) FROM risk_scoreboard;")
raw = subprocess.check_output([
    "ssh", os.environ.get("AIPI_SSH_HOST","hetzner"),
    "docker exec -i %s psql -U %s -d %s -At -c \"%s\"" % (
        os.environ["AIPI_PG_CONTAINER"], os.environ.get("AIPI_PAGES_ROLE","school"),
        os.environ["AIPI_DB"], SQL)
], text=True).strip()
rows = json.loads(raw)
assert rows and len(rows) >= 10, "unexpected row count: %r" % (len(rows) if rows else 0)

# Build a compact, valid JS literal (JSON is valid JS; keeps quoting safe).
lines = ["  var SCORE = ["]
for r in rows:
    lines.append("    " + json.dumps({
        "name": r["name"], "state": r["state"], "trend": r["trend"],
        "conf": r["conf"], "go": r["go"], "why": r["why"]
    }, ensure_ascii=False) + ",")
lines.append("  ];")
block = "\n".join(lines)

path = "index_live.html"
html = open(path, encoding="utf-8").read()
a = html.index("/*SCOREBOARD-START*/") + len("/*SCOREBOARD-START*/")
b = html.index("/*SCOREBOARD-END*/")
new = html[:a] + "\n" + block + "\n  " + html[b:]
open(path, "w", encoding="utf-8").write(new)
print("injected %d scenarios (%d bytes)" % (len(rows), len(new)))
