#!/usr/bin/env python3
"""Collapse same-event / same-paper duplicates after classification.

Design lesson (learned the hard way): the model's qwen_event_key is ADVISORY, not reliable.
For news it works (many outlets, one event -> one key). For research it does NOT: the model
keys papers by their PUBLISHER, so ten unrelated essays from the Center on Long-Term Risk all
came back keyed "center long risk term". Trusting the key would drop nine real papers.

So this pass does NOT merge on the key at all. A duplicate is confirmed only from the items' own
titles: strong title overlap (same event reworded by two outlets, or the same paper reposted),
with a veto when an ordinal / year / model-version differs ("first" vs "second" hackathon, 2024
vs 2025 index, GPT-4 vs GPT-5 card are different events). A research backfill has very few true
dups, so the bias is precision: when unsure, keep both — they both reach the Opus gate, which is
the semantic-dedup backstop.

Nothing is deleted; losers get status='duplicate' and stay for audit.

  python3 dedup_events.py --dry     # report, change nothing
  python3 dedup_events.py
"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import psql, psql_stdin, sq

TITLE_JACCARD = 0.60       # title similarity that confirms "same event / same paper"
AGG = re.compile(r"(news\.google|bing\.com|/rss/|feedproxy|flipboard|msn\.com)", re.I)

# words too common to count as evidence two items are the same story
STOP = set("the a an of to in on for and or with by from at as is are be ai model models llm llms "
           "new study research paper report how why what when who will can could new using use "
           "case cases risk risks safety human humans about into over more most our your their "
           "this that these those it its was were has have had they them then than".split())


def _content_words(*texts):
    toks = re.findall(r"[a-z0-9]+", " ".join(texts).lower())
    # light stemming so hack/hacked/hacking, breach/breaches match
    stem = lambda w: re.sub(r"(ed|ing|es|s)$", "", w) if len(w) > 4 else w
    return frozenset(stem(t) for t in toks if len(t) > 2 and t not in STOP)


# Tokens that distinguish INSTANCES of an otherwise-identical (often templated) title. Corporate
# announcements and newsletters reuse a template and vary only the payload — "Introducing gpt-oss"
# vs "Introducing gpt-oss-safeguard", "data residency in Europe" vs "in Asia", "Disinfo Update
# 15/07" vs "24/06". Jaccard sees the shared template as evidence, so a DIFFERENCE on any of these
# discriminators must veto the merge.
_ORD = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
        "fifth": 5, "5th": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}
# region/jurisdiction — the most common payload swap in corporate/policy posts
_REGION = {"uk", "us", "usa", "eu", "europe", "european", "asia", "asian", "australia", "australian",
           "china", "chinese", "india", "indian", "africa", "african", "america", "american",
           "britain", "british", "japan", "japanese", "korea", "korean", "germany", "german",
           "france", "french", "canada", "canadian", "uae", "singapore", "brazil", "russia"}
# product-variant suffixes that make a different release
_VARIANT = {"codex", "safeguard", "mini", "pro", "turbo", "nano", "lite", "plus", "max", "base",
            "instruct", "vision", "audio", "preview", "flash", "opus", "sonnet", "haiku", "thinking"}
def _discriminators(title):
    t = title.lower()
    words = re.findall(r"[a-z0-9]+", t)
    ords = {_ORD[w] for w in words if w in _ORD}
    years = set(re.findall(r"\b(?:19|20)\d{2}\b", t))
    vers = set(re.findall(r"\b(?:v|gpt-?|claude-?|llama-?|gemini-?|o)(\d+(?:\.\d+)?)\b", t))
    dates = set(re.findall(r"\b\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b", t))  # 15/07/2026, 24-06
    regions = {w for w in words if w in _REGION}
    variants = {w for w in words if w in _VARIANT}
    return ords, years, vers, dates, regions, variants


def load():
    rows = psql(
        "SELECT id||E'\\t'||coalesce(qwen_event_key,'')||E'\\t'||coalesce(qwen_risk,'')||E'\\t'||"
        "status||E'\\t'||coalesce(url,'')||E'\\t'||replace(coalesce(title,''),E'\\t',' ')||E'\\t'||"
        "replace(left(coalesce(blurb,''),200),E'\\t',' ') "
        "FROM news_queue WHERE status IN ('classified','enriched') AND qwen_risk<>'none'").splitlines()
    out = []
    for r in rows:
        p = r.split("\t")
        if len(p) < 6:
            continue
        blurb = p[6] if len(p) > 6 else ""
        out.append(dict(id=int(p[0]), key=p[1], risk=p[2], status=p[3], url=p[4], title=p[5],
                        words=_content_words(p[5], blurb),
                        titlewords=_content_words(p[5]),
                        disc=_discriminators(p[5])))
    return out


def _same_story(a, b):
    """A duplicate must be evidenced by the items' OWN titles overlapping strongly — the same
    event reworded by two outlets, or the same paper reposted. The model's event_key is NOT used
    to merge: it groups research papers by publisher, which produced false merges of ten distinct
    essays. A research backfill has very few true dups, so the correct bias here is precision:
    when unsure, keep both (they both go to the Opus gate, which is the semantic-dedup backstop).

    Threshold note: the news pair "OpenAI model hacks Hugging Face" /
    "Hugging Face hacked by rogue AI model" scores Jaccard 0.6 after stopword+stem — the floor."""
    ta, tb = a["titlewords"], b["titlewords"]
    if not (ta and tb):
        return False
    # veto: templated titles that differ on a discriminator are different instances.
    # disc = (ords, years, vers, dates, regions, variants)
    oa, ya, va, da, ra, xa = a["disc"]; ob, yb, vb, db, rb, xb = b["disc"]
    # ordinal/year/version/date: veto only when BOTH title carries one and they differ
    # (a title that simply omits the year may still be the same story)
    if (oa and ob and oa != ob) or (ya and yb and ya != yb) or \
       (va and vb and va != vb) or (da and db and da != db):
        return False
    # region/product-variant: veto on ANY difference, incl. asymmetric — "X" and "X-Codex",
    # "blueprint" and "EU blueprint" are different releases even when one side omits the token
    if ra != rb or xa != xb:
        return False
    jac = len(ta & tb) / len(ta | tb)
    if jac >= TITLE_JACCARD:
        return True
    # one title's distinctive words almost entirely inside the other (same paper, longer subtitle)
    cont = len(ta & tb) / min(len(ta), len(tb))
    return cont >= 0.85 and min(len(ta), len(tb)) >= 3


def cluster(items):
    """Union-find within a risk. A merge requires _same_story() evidence, so an over-broad key
    (e.g. a publisher name shared by ten different papers) cannot collapse them."""
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    by_risk = {}
    for idx, it in enumerate(items):
        by_risk.setdefault(it["risk"], []).append(idx)
    for idxs in by_risk.values():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                if _same_story(items[idxs[a]], items[idxs[b]]):
                    parent[find(idxs[a])] = find(idxs[b])

    clusters = {}
    for idx in range(len(items)):
        clusters.setdefault(find(idx), []).append(idx)
    return [c for c in clusters.values() if len(c) > 1]


def rank(it):
    # higher is better → survives
    return (1 if it["status"] == "enriched" else 0,
            0 if AGG.search(it["url"]) else 1,
            len(it["title"]),
            -it["id"])


def main():
    dry = "--dry" in sys.argv
    items = load()
    clusters = cluster(items)
    dupes, kept_preview = [], []
    for c in clusters:
        members = sorted((items[i] for i in c), key=rank, reverse=True)
        keep, drop = members[0], members[1:]
        kept_preview.append((keep, drop))
        dupes += [d["id"] for d in drop]

    print(f"classified items: {len(items)} | clusters with dups: {len(clusters)} | "
          f"rows to mark duplicate: {len(dupes)}")
    for keep, drop in kept_preview[:20]:
        print(f"\n  [{keep['risk']}] KEEP #{keep['id']}: {keep['title'][:76]}")
        for d in drop:
            print(f"        dup #{d['id']}: {d['title'][:72]}")

    if dry or not dupes:
        print("\n[dry] nothing changed" if dry else "\nno duplicates found")
        return
    ids = ",".join(str(i) for i in dupes)
    psql_stdin("BEGIN;\nUPDATE news_queue SET status='duplicate', updated_at=now() "
               f"WHERE id IN ({ids});\nCOMMIT;\n")
    print(f"\n✓ marked {len(dupes)} rows status='duplicate' "
          f"({len(items)-len(dupes)} distinct events remain)")


if __name__ == "__main__":
    main()
