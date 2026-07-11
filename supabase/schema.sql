-- ============================================================
-- SpyGlass schema (Supabase / Postgres)
-- Designed from the real Apify actor outputs:
--   LinkedIn  harvestapi/linkedin-profile-posts
--   Instagram apify/instagram-post-scraper
--   X         parseforge/x-com-scraper
-- Strategy: unified `posts` table (common normalized metrics for
-- cross-platform ranking + AI brief) + `raw` jsonb that preserves
-- EACH platform's unique details separately. No data lost.
-- ============================================================

-- 1) The competitor entity (a brand/company/person we track)
create table if not exists competitors (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  added_by      text,                         -- Slack user id who ran /setcomp
  slack_channel text,                         -- channel to send alerts to
  created_at    timestamptz default now()
);

-- 2) Each social handle for a competitor (1 competitor : many socials)
--    Holds the incremental cutoff so we never re-scrape old posts.
create table if not exists competitor_socials (
  id              uuid primary key default gen_random_uuid(),
  competitor_id   uuid references competitors(id) on delete cascade,
  platform        text not null,              -- linkedin | instagram | twitter | website
  handle_url      text not null,              -- profile / company / handle URL
  website_url     text,                       -- derived from LinkedIn (Firecrawl) for context
  last_scraped_at timestamptz,                -- incremental cutoff (null = never scraped)
  active          boolean default true,
  created_at      timestamptz default now(),
  unique (platform, handle_url)
);

-- 3) Unified posts across all platforms
create table if not exists posts (
  id            uuid primary key default gen_random_uuid(),
  social_id     uuid references competitor_socials(id) on delete cascade,
  competitor_id uuid references competitors(id) on delete cascade,
  platform      text not null,
  post_url      text not null unique,         -- dedup key
  external_id   text,                         -- platform's own post id
  content       text,                         -- text / caption
  media_type    text,                         -- image | video | carousel | document | text
  media_urls    jsonb,                        -- array of media URLs
  posted_at     timestamptz,                  -- when the competitor posted it
  -- normalized engagement (for cross-platform ranking + the daily brief)
  likes         integer,
  comments      integer,
  shares        integer,                      -- reposts / retweets
  views         integer,                      -- video views / impressions (nullable)
  engagement_total integer,                   -- likes + comments + shares (quick rank)
  raw           jsonb,                         -- FULL platform-specific payload (details kept separately)
  first_seen    timestamptz default now(),
  -- AI analysis (filled by the single daily AI pass)
  hook          text,
  hook_type     text,
  content_type  text,
  strategy      text,
  analysis      jsonb
);

-- 4) Engagement over time (weekly re-sync -> growth: strategy or luck?)
create table if not exists metric_snapshots (
  id          uuid primary key default gen_random_uuid(),
  post_id     uuid references posts(id) on delete cascade,
  captured_at timestamptz default now(),
  likes       integer,
  comments    integer,
  shares      integer,
  views       integer
);

-- 5) Daily AI briefs sent to Slack (history + "ask about competitor" + dedup)
create table if not exists daily_briefs (
  id           uuid primary key default gen_random_uuid(),
  brief_date   date default current_date,
  competitor_ids jsonb,                        -- competitors covered
  summary      text,                           -- the brief message text
  docx_path    text,                           -- generated Word doc
  slack_ts     text,                           -- Slack message timestamp
  created_at   timestamptz default now()
);

-- Indexes
create index if not exists idx_socials_competitor on competitor_socials(competitor_id);
create index if not exists idx_posts_social       on posts(social_id);
create index if not exists idx_posts_competitor   on posts(competitor_id);
create index if not exists idx_posts_posted_at    on posts(posted_at);
create index if not exists idx_snapshots_post     on metric_snapshots(post_id);
