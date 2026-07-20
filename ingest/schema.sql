-- News ingester staging queue. Nothing here is live until merged into real_issues.score_cases.
CREATE TABLE IF NOT EXISTS news_queue (
  id           serial PRIMARY KEY,
  url          text NOT NULL,
  url_hash     text NOT NULL UNIQUE,      -- canonicalized-url sha1, dedupe key
  title        text,
  blurb        text,
  source       text,                      -- feed/domain
  published    text,                      -- freeform date from feed
  -- stage 1 (qwen first pass)
  qwen_risk    text,                      -- risk id or 'none'
  qwen_pol     text,                      -- better|worse|neutral
  qwen_why     text,
  qwen_model   text,
  -- stage 2 (opus relevance gate)
  opus_verdict text,                      -- keep|drop|null(pending)
  opus_reason  text,
  norm         jsonb,                     -- normalized {title,when,what,pol} ready for score_cases
  -- lifecycle
  status       text NOT NULL DEFAULT 'new',  -- new|classified|reviewed|approved|published|rejected|dropped
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS news_queue_status_idx ON news_queue(status);
CREATE INDEX IF NOT EXISTS news_queue_risk_idx   ON news_queue(qwen_risk);
