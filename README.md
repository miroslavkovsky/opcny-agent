# OpcnySimulator — Agent Worker Service

Multi-agent systém pre automatizáciu sociálnych sietí, content review a analytics
pre [OptionsSimulator.com](https://optionssimulator.com).

## Architektúra

```
┌─────────────────────────────────────────────────────────┐
│                    RAILWAY CLOUD                         │
│                                                          │
│  ┌──────────────────┐     ┌───────────────────────────┐ │
│  │  opcnysimulator   │     │  opcny-agents (NOVÝ)      │ │
│  │  (existujúci)     │     │                           │ │
│  │                   │     │  ┌─────────────────────┐  │ │
│  │  FastAPI Web App  │     │  │   Agent Scheduler    │  │ │
│  │  ┌─────────────┐ │     │  │   (APScheduler)      │  │ │
│  │  │ Admin Panel  │◄├─────┤──┤                      │  │ │
│  │  │ + Agent UI   │ │ DB  │  │  ┌───────────────┐   │  │ │
│  │  └─────────────┘ │     │  │  │Content Review  │   │  │ │
│  │  ┌─────────────┐ │     │  │  │Agent           │   │  │ │
│  │  │ Blog CMS    │ │     │  │  └───────────────┘   │  │ │
│  │  │ (Editor.js)  │ │     │  │  ┌───────────────┐   │  │ │
│  │  └─────────────┘ │     │  │  │Social Media    │   │  │ │
│  │  ┌─────────────┐ │     │  │  │Agent           │   │  │ │
│  │  │ Public Site  │ │     │  │  └───────────────┘   │  │ │
│  │  └─────────────┘ │     │  │  ┌───────────────┐   │  │ │
│  └──────────────────┘     │  │  │Analytics Agent │   │  │ │
│           │                │  │  └───────────────┘   │  │ │
│           │                │  └─────────────────────┘  │ │
│           │                │           │               │ │
│           ▼                │           ▼               │ │
│  ┌──────────────────┐     │  ┌─────────────────────┐  │ │
│  │   PostgreSQL      │◄────┤──│  Claude API         │  │ │
│  │   (zdieľaná DB)   │     │  │  Discord Webhooks   │  │ │
│  └──────────────────┘     │  │  X (Twitter) API     │  │ │
│                            │  │  Instagram Graph API │  │ │
│                            │  │  GA4 Data API        │  │ │
│                            │  └─────────────────────┘  │ │
│                            └───────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Agenti

| Agent | Zodpovednosť | Schedule |
|-------|--------------|----------|
| **ContentReviewAgent** | Kontrola gramatiky, tónu, SEO. Komunikácia s Mirom cez Discord/admin. | On-demand + pred publikáciou |
| **SocialMediaAgent** | Generovanie a publikovanie postov na Discord, X, Instagram. | Podľa content kalendára (2-3x denne) |
| **AnalyticsAgent** | Sťahovanie GA4 dát, vyhodnocovanie trendov, reporty. | Denne o 6:00 + týždenný súhrn |

## Tech Stack

- **Runtime:** Python 3.12 + FastAPI (lightweight API pre health checks + admin komunikáciu)
- **Scheduler:** APScheduler (AsyncIOScheduler)
- **AI:** Anthropic Claude API (claude-sonnet-4-5-20250929)
- **DB:** PostgreSQL (zdieľaná s hlavnou appkou)
- **Social APIs:** discord.py / webhooks, tweepy (X), Meta Graph API (Instagram)
- **Analytics:** google-analytics-data (GA4)
- **Notifications:** Discord DM / Telegram Bot

## Štruktúra projektu

```
opcny-agents/
├── README.md
├── pyproject.toml              # Dependencies + project config
├── Dockerfile                  # Railway deployment
├── railway.toml                # Railway service config
├── .env.example                # Premenné prostredia
│
├── config/
│   ├── __init__.py
│   ├── settings.py             # Pydantic Settings — všetky env vars
│   └── persona.py              # Definícia writing persóny pre agentov
│
├── models/
│   ├── __init__.py
│   ├── base.py                 # SQLAlchemy base + session
│   ├── scheduled_post.py       # Naplánované príspevky
│   ├── content_review.py       # Review záznamy
│   ├── analytics_snapshot.py   # GA4 snapshoty
│   └── agent_log.py            # Logy agentov
│
├── agents/
│   ├── __init__.py
│   ├── base.py                 # BaseAgent abstraktná trieda
│   ├── content_review.py       # ContentReviewAgent
│   ├── social_media.py         # SocialMediaAgent
│   └── analytics.py            # AnalyticsAgent
│
├── services/
│   ├── __init__.py
│   ├── claude_service.py       # Claude API wrapper
│   ├── discord_service.py      # Discord posting + notifikácie
│   ├── twitter_service.py      # X/Twitter API
│   ├── instagram_service.py    # Instagram Graph API
│   └── ga4_service.py          # Google Analytics 4
│
├── tasks/
│   ├── __init__.py
│   └── scheduler.py            # APScheduler setup + job definitions
│
├── api/
│   ├── __init__.py
│   └── routes.py               # Health check + internal API endpoints
│
├── utils/
│   ├── __init__.py
│   └── notifications.py        # Notifikačný systém (Discord DM / Telegram)
│
├── templates/
│   ├── post_discord.j2         # Jinja2 šablóna pre Discord posty
│   ├── post_twitter.j2         # Šablóna pre X/Twitter
│   ├── post_instagram.j2       # Šablóna pre Instagram caption
│   ├── analytics_report.j2     # Šablóna pre denný/týždenný report
│   └── review_notification.j2  # Šablóna pre review notifikáciu
│
└── main.py                     # Entry point — spustí scheduler + FastAPI
```

## Rýchly štart

```bash
# 1. Klonovanie
git clone https://github.com/miroslavkovsky/opcny-agents.git
cd opcny-agents

# 2. Env premenné
cp .env.example .env
# Vyplniť API kľúče...

# 3. Lokálny vývoj
pip install -e ".[dev]"
python main.py

# 4. Deploy na Railway
railway up
```

## Workflow

```
[Blog článok / Nový obsah]
         │
         ▼
 ContentReviewAgent
 ├── Kontrola gramatiky (Claude)
 ├── Kontrola tónu (persóna)
 ├── SEO analýza
 └── → Notifikácia Mirovi
         │
    [Miro schváli / upraví]
         │
         ▼
  SocialMediaAgent
  ├── Generuje varianty pre platformy (Claude)
  ├── Discord: embed s obrázkom
  ├── X: thread alebo single tweet
  └── Instagram: carousel / single post
         │
         ▼
   AnalyticsAgent
   ├── Sleduje engagement
   ├── Koreluje s návštevnosťou webu
   └── → Týždenný report Mirovi
```

## DB Schéma (nové tabuľky)

Tieto tabuľky sa pridajú do existujúcej PostgreSQL databázy:

```sql
-- Naplánované príspevky
CREATE TABLE scheduled_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    content_body JSONB NOT NULL,        -- { discord: "...", twitter: "...", instagram: "..." }
    source_blog_id INTEGER REFERENCES blog_posts(id),
    platforms VARCHAR[] NOT NULL,        -- {'discord', 'twitter', 'instagram'}
    status VARCHAR(50) DEFAULT 'draft', -- draft, pending_review, approved, published, failed
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    engagement_data JSONB,              -- { likes, shares, comments... }
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Content review záznamy
CREATE TABLE content_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type VARCHAR(50) NOT NULL,   -- 'blog_post', 'social_post'
    target_id UUID NOT NULL,
    review_result JSONB NOT NULL,       -- { grammar: [...], tone: "ok", seo_score: 85 }
    agent_notes TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, approved, needs_changes
    reviewed_by VARCHAR(50) DEFAULT 'agent', -- 'agent' alebo 'miro'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Analytics snapshoty
CREATE TABLE analytics_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    period_type VARCHAR(20) NOT NULL,   -- 'daily', 'weekly', 'monthly'
    metrics JSONB NOT NULL,             -- { pageviews, sessions, bounce_rate, top_pages... }
    insights TEXT,                       -- AI-generované insights
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent activity logy
CREATE TABLE agent_logs (
    id BIGSERIAL PRIMARY KEY,
    agent_name VARCHAR(100) NOT NULL,
    action VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,        -- 'success', 'error', 'skipped'
    details JSONB,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexy
CREATE INDEX idx_scheduled_posts_status ON scheduled_posts(status);
CREATE INDEX idx_scheduled_posts_scheduled_at ON scheduled_posts(scheduled_at);
CREATE INDEX idx_content_reviews_target ON content_reviews(target_type, target_id);
CREATE INDEX idx_analytics_snapshots_period ON analytics_snapshots(period_start, period_type);
CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_name, created_at);
```
