-- Alignment/safety organization registry.
--
-- This table does double duty, which is the whole point of the design:
--   1. It is the data behind the public "who's working on what" directory page.
--   2. It is the SOURCE REGISTRY for the research feed — research_feeds.py iterates
--      rows with feed_kind='rss' to pull new alignment research.
-- Add an org here and it appears on the page AND starts being ingested. One spine.

CREATE TABLE IF NOT EXISTS alignment_orgs (
  id            serial PRIMARY KEY,
  slug          text NOT NULL UNIQUE,       -- stable id, used by the page + feed
  name          text NOT NULL,
  acronym       text,
  url           text,                       -- homepage
  feed_url      text,                       -- RSS/Atom, or a publications listing page
  feed_kind     text DEFAULT 'none',        -- rss | page | none
  country       text,
  org_type      text,                       -- technical-lab|academic-center|policy-thinktank|
                                            -- government|advocacy|funder|field-building|community
  founded       text,
  focus         text,                       -- one specific sentence, no marketing language
  risk_vectors  text[] DEFAULT '{}',        -- real_issues.id values this org actually publishes on
  confirmed     boolean DEFAULT false,      -- did discovery actually fetch and verify the site
  notes         text,
  discovered_by text,                       -- which discovery slice found it (provenance)

  -- feed health, maintained by research_feeds.py
  feed_status     text,                     -- ok | http_<code> | parse_error | empty | unchecked
  feed_checked_at timestamptz,
  feed_items_seen integer DEFAULT 0,

  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS alignment_orgs_type_idx  ON alignment_orgs(org_type);
CREATE INDEX IF NOT EXISTS alignment_orgs_feed_idx  ON alignment_orgs(feed_kind);
CREATE INDEX IF NOT EXISTS alignment_orgs_rv_idx    ON alignment_orgs USING gin(risk_vectors);

-- Coverage view: which risk vectors have how many orgs working on them.
-- This is the bridge from the org directory to the per-risk scorecard —
-- a risk with zero orgs is a genuine finding, not a gap in our data collection.
CREATE OR REPLACE VIEW risk_org_coverage AS
SELECT i.id            AS risk_id,
       i.title         AS risk_title,
       i.score_state,
       i.score_threat,
       count(o.id)     AS org_count,
       array_agg(o.name ORDER BY o.name) FILTER (WHERE o.id IS NOT NULL) AS orgs
FROM real_issues i
LEFT JOIN alignment_orgs o ON i.id = ANY(o.risk_vectors)
GROUP BY i.id, i.title, i.score_state, i.score_threat;
