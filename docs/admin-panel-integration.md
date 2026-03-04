# Admin Panel Integrácia — opcnysimulator × opcny-agents

## Kontext

Tento dokument je návod pre programovacieho agenta, ktorý má priamy prístup do repozitára `opcnysimulator` (hlavná FastAPI webová appka). Cieľom je implementovať admin panel stránky, ktoré komunikujú s microservice `opcny-agents` cez HTTP API a čítajú zdieľané DB tabuľky.

**opcny-agents** beží ako samostatný Railway service na vlastnej URL (napr. `https://opcny-agents-production.up.railway.app`). Komunikácia prebieha cez interné API endpointy chránené `X-API-Key` headerom.

---

## Architektúra komunikácie

```
┌──────────────────────┐         HTTP + X-API-Key         ┌──────────────────────┐
│   opcnysimulator     │ ──────────────────────────────→  │   opcny-agents       │
│   (hlavná appka)     │                                   │   (agent worker)     │
│                      │                                   │                      │
│   Admin Panel UI     │         Zdieľaná PostgreSQL       │   3 AI agenti        │
│   Blog Management    │ ←──────────────────────────────→  │   APScheduler        │
│   User Auth          │         (čítanie + zápis)         │   Claude API         │
└──────────────────────┘                                   └──────────────────────┘
```

- Hlavná appka **volá API endpointy** agent workera na manuálne spúšťanie úloh
- Obe appky **čítajú/píšu** do rovnakých 4 tabuliek v PostgreSQL
- Hlavná appka **nikdy neimportuje** Python kód z agent workera

---

## Env premenné potrebné v hlavnej appke

```
AGENT_WORKER_URL=https://opcny-agents-production.up.railway.app
INTERNAL_API_KEY=rovnaky-kluc-ako-v-agent-workeri
```

---

## HTTP klient pre komunikáciu s agent workerom

Vytvor `services/agent_client.py` (alebo pridaj do existujúceho service modulu):

```python
import httpx
from config import settings  # prispôsob importu hlavnej appky

class AgentClient:
    """HTTP klient pre komunikáciu s opcny-agents worker service."""

    def __init__(self):
        self.base_url = settings.AGENT_WORKER_URL.rstrip("/")
        self.headers = {"X-API-Key": settings.INTERNAL_API_KEY}
        self.http = httpx.AsyncClient(timeout=120)  # agenti môžu trvať dlhšie

    async def health(self) -> dict:
        r = await self.http.get(f"{self.base_url}/health")
        return r.json()

    async def scheduler_status(self) -> dict:
        r = await self.http.get(f"{self.base_url}/status", headers=self.headers)
        return r.json()

    async def generate_post(self, topic: str, platforms: list[str],
                            source_blog_id: int | None = None) -> dict:
        r = await self.http.post(
            f"{self.base_url}/agents/social-media/generate",
            headers=self.headers,
            json={"topic": topic, "platforms": platforms,
                  "source_blog_id": source_blog_id},
        )
        return r.json()

    async def review_content(self, target_type: str, target_id: str,
                             content: str) -> dict:
        r = await self.http.post(
            f"{self.base_url}/agents/content-review/review",
            headers=self.headers,
            json={"target_type": target_type, "target_id": target_id,
                  "content": content},
        )
        return r.json()

    async def check_pending_reviews(self) -> dict:
        r = await self.http.post(
            f"{self.base_url}/agents/content-review/check-pending",
            headers=self.headers,
        )
        return r.json()

    async def analytics_daily(self) -> dict:
        r = await self.http.post(
            f"{self.base_url}/agents/analytics/daily",
            headers=self.headers,
        )
        return r.json()

    async def analytics_weekly(self) -> dict:
        r = await self.http.post(
            f"{self.base_url}/agents/analytics/weekly",
            headers=self.headers,
        )
        return r.json()

    async def analytics_custom(self, start_date: str, end_date: str) -> dict:
        r = await self.http.post(
            f"{self.base_url}/agents/analytics/custom",
            headers=self.headers,
            json={"start_date": start_date, "end_date": end_date},
        )
        return r.json()
```

---

## Zdieľané DB tabuľky — SQLAlchemy modely

Agent worker vytvoril 4 tabuľky. Hlavná appka potrebuje **read-only modely** (iba čítanie) + **write** iba na `scheduled_posts.status` a `scheduled_posts.scheduled_at` (Miro schvaľuje/plánuje posty).

### Tabuľka: `scheduled_posts`

```sql
CREATE TABLE scheduled_posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(255) NOT NULL,
    content_body    JSONB NOT NULL,      -- {"discord": "...", "twitter": "...", "instagram": "..."}
    source_blog_id  INTEGER,             -- FK na blog_posts.id (ak bol post generovaný z blogu)
    platforms       TEXT[] NOT NULL,      -- {"discord", "twitter", "instagram"}
    status          VARCHAR(50) DEFAULT 'draft',
    scheduled_at    TIMESTAMPTZ,
    published_at    TIMESTAMPTZ,
    engagement_data JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
-- Indexy: idx_scheduled_posts_status, idx_scheduled_posts_scheduled_at
```

**Status flow:**
```
draft → pending_review → approved / needs_changes → scheduled → published / failed
```

- `draft` — ručne vytvorený, ešte neprešiel review
- `pending_review` — čaká na ContentReviewAgent (automaticky po generate_post)
- `approved` — agent schválil, Miro môže naplánovať publikáciu
- `needs_changes` — agent našiel problémy, Miro vidí detaily v content_reviews
- `scheduled` — Miro nastavil `scheduled_at` dátum (admin panel)
- `published` — úspešne publikovaný na platformy
- `failed` — publikácia zlyhala, viď `error_message`

**Admin panel akcie na tejto tabuľke:**
1. **Zobraziť zoznam** — filtruj podľa status (all, pending_review, approved, needs_changes, published)
2. **Detail postu** — zobraz content_body per platform, review výsledky, engagement data
3. **Schváliť post** — zmeň status z `needs_changes` → `approved` (Miro override agenta)
4. **Naplánovať post** — nastav `scheduled_at` + zmeň status na `scheduled`
5. **Zmazať post** — len ak status je draft/needs_changes

### Tabuľka: `content_reviews`

```sql
CREATE TABLE content_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type     VARCHAR(50) NOT NULL,   -- "blog_post" | "social_post"
    target_id       VARCHAR(255) NOT NULL,  -- UUID scheduled_post alebo blog_post ID
    review_result   JSONB NOT NULL,
    agent_notes     TEXT,
    status          VARCHAR(50) DEFAULT 'pending',  -- "pending" | "approved" | "needs_changes"
    reviewed_by     VARCHAR(50) DEFAULT 'agent',    -- "agent" | "miro"
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- Index: idx_content_reviews_target (target_type, target_id)
```

**`review_result` JSON štruktúra (vrátená z Claude API):**
```json
{
    "grammar_issues": [
        {"text": "original text", "suggestion": "fix", "severity": "low|medium|high"}
    ],
    "tone_assessment": "ok | needs_adjustment",
    "tone_notes": "Voliteľný komentár k tónu",
    "accuracy_issues": ["..."],
    "seo_score": 85,
    "seo_suggestions": ["Add meta description", "..."],
    "compliance_ok": true,
    "compliance_notes": "",
    "overall_status": "approved | needs_changes",
    "summary": "Stručné zhrnutie pre Mira"
}
```

**Admin panel:**
- Zobraziť review detail pre konkrétny post (JOIN na scheduled_posts)
- Zobraziť históriu reviewov (filtruj podľa target_type, status)

### Tabuľka: `analytics_snapshots`

```sql
CREATE TABLE analytics_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    period_type     VARCHAR(20) NOT NULL,   -- "daily" | "weekly" | "custom"
    metrics         JSONB NOT NULL,
    insights        TEXT,                    -- AI-generované insights
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- Index: idx_analytics_snapshots_period (period_start, period_type)
```

**`metrics` JSON štruktúra:**
```json
{
    "overview": {
        "sessions": 1234,
        "pageviews": 5678,
        "active_users": 890,
        "new_users": 456,
        "avg_session_duration": 125.5,
        "bounce_rate": 45.2,
        "engaged_sessions": 678
    },
    "top_pages": [
        {"page_path": "/blog/what-are-options", "pageviews": 234}
    ],
    "traffic_sources": [
        {"source": "google", "medium": "organic", "sessions": 456}
    ]
}
```

**Admin panel:**
- Dashboard s najnovším daily/weekly snapshotom
- Graf metrík za posledných 30 dní (sessions, pageviews)
- Zoznam insights (AI text)
- Tlačidlo "Generuj report" → volá `analytics_daily` alebo `analytics_custom`

### Tabuľka: `agent_logs`

```sql
CREATE TABLE agent_logs (
    id              BIGSERIAL PRIMARY KEY,
    agent_name      VARCHAR(100) NOT NULL,   -- "ContentReviewAgent", "SocialMediaAgent", "AnalyticsAgent"
    action          VARCHAR(255) NOT NULL,   -- "check_pending", "generate_post", "daily_report"
    status          VARCHAR(50) NOT NULL,    -- "success" | "error" | "skipped"
    details         JSONB,
    error_message   TEXT,
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- Index: idx_agent_logs_agent (agent_name, created_at)
```

**Admin panel:**
- Zoznam posledných logov (filtrovateľný podľa agent_name, status)
- Error monitoring — zvýraznené záznamy so status "error"
- Priemerný duration_ms per agent (performance monitoring)

---

## API endpointy agent workera — referencie

### Verejné (bez API key)

| Method | Path | Popis | Response |
|--------|------|-------|----------|
| `GET` | `/health` | Health check | `{"status": "healthy", "service": "opcny-agents", "timestamp": "..."}` |

### Chránené (vyžadujú `X-API-Key` header)

| Method | Path | Request Body | Popis |
|--------|------|-------------|-------|
| `GET` | `/status` | — | Stav scheduler jobov |
| `POST` | `/agents/social-media/generate` | `{"topic": "...", "platforms": ["discord","twitter"], "source_blog_id": null}` | Vygeneruj nový post |
| `POST` | `/agents/content-review/review` | `{"target_type": "blog_post", "target_id": "123", "content": "..."}` | Review jedného obsahu |
| `POST` | `/agents/content-review/check-pending` | — | Skontroluj všetky pending_review posty |
| `POST` | `/agents/analytics/daily` | — | Denný GA4 report |
| `POST` | `/agents/analytics/weekly` | — | Týždenný GA4 report |
| `POST` | `/agents/analytics/custom` | `{"start_date": "2026-01-01", "end_date": "2026-01-31"}` | Custom period report |

### Štandardný response formát

Všetky POST endpointy vracajú:
```json
{
    "status": "success | error | skipped",
    "details": { ... },
    "error": "error message (iba ak status=error)"
}
```

Príklad úspešného generate_post:
```json
{
    "status": "success",
    "details": {
        "post_id": "a1b2c3d4-...",
        "platforms": ["discord", "twitter"],
        "status": "pending_review"
    }
}
```

---

## Admin panel stránky — čo implementovať

### 1. Dashboard (`/admin/agents/`)

- Stav agent workera (volaj `GET /health`)
- Stav scheduler jobov (volaj `GET /status`)
- Posledné 3 agent_logs per agent (query DB)
- Quick stats: počet postov podľa statusu, posledný analytics snapshot

### 2. Scheduled Posts (`/admin/agents/posts/`)

- Tabuľka so zoznamom scheduled_posts
- Filtre: status, platform, date range
- Akcie per post:
  - **Detail** — zobraz content per platform + review výsledky
  - **Schváliť** — zmena status na `approved`
  - **Naplánovať** — nastavenie `scheduled_at` + status `scheduled`
  - **Odmietnuť** — zmena status na `needs_changes` s poznámkou
  - **Zmazať** — len draft/needs_changes
- Tlačidlo **"Generuj nový post"** — modal s topic input → volá `POST /agents/social-media/generate`

### 3. Content Reviews (`/admin/agents/reviews/`)

- Tabuľka so zoznamom content_reviews (JOIN na scheduled_posts pre title)
- Detail review: zobraz grammar_issues, tone, SEO score, compliance
- Tlačidlo **"Spustiť review"** — volá `POST /agents/content-review/check-pending`

### 4. Analytics (`/admin/agents/analytics/`)

- Posledný daily + weekly snapshot z DB
- Metrics overview (sessions, pageviews, users, bounce rate)
- Top stránky tabuľka
- AI insights text
- Tlačidlá: "Denný report", "Týždenný report", "Custom report" (date picker)

### 5. Agent Logs (`/admin/agents/logs/`)

- Tabuľka agent_logs (posledných 100)
- Filtre: agent_name, status, date range
- Zvýraznenie errorov (červené)
- Detail: details JSON + error_message

---

## Dôležité pravidlá

1. **Nikdy nemodifikuj tabuľky agenta** okrem:
   - `scheduled_posts.status` (schválenie/plánovanie/odmietnutie)
   - `scheduled_posts.scheduled_at` (nastavenie dátumu publikácie)
   - `scheduled_posts.updated_at` (automaticky pri update)
2. **Nikdy priamo nevkladaj** do `content_reviews`, `analytics_snapshots`, `agent_logs` — to robí iba agent worker
3. **API volania na agent worker môžu trvať 30-120 sekúnd** (Claude API generovanie) — použi async a loading indikátor
4. **INTERNAL_API_KEY musí byť rovnaký** v oboch services
5. **Timezone**: agent worker pracuje v `Europe/Bratislava`, v admin paneli zobrazuj časy v rovnakom timezone
6. **UUID formát**: scheduled_posts.id a content_reviews.id sú UUID v4, agent_logs.id je BIGSERIAL
