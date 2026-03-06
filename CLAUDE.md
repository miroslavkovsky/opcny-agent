# CLAUDE.md — Inštrukcie pre Claude Code

## Identita projektu

Toto je **opcny-agents** — multi-agent worker service pre [OptionsSimulator.com](https://optionssimulator.com). Beží ako samostatný Railway microservice, zdieľa PostgreSQL databázu s hlavnou FastAPI webovou appkou (repozitár `opcnysimulator`). Vlastník projektu je Miro (miroslavkovsky), solo developer zo Slovenska.

## Čo tento projekt robí

Tri AI agenti automatizujú marketing a analytiku pre edukačnú platformu o obchodovaní s opciami:

1. **ContentReviewAgent** — kontroluje gramatiku, tón, SEO a finančnú compliance obsahu pred publikáciou cez Claude API
2. **SocialMediaAgent** — generuje platformovo-špecifické príspevky (Discord, X/Twitter, Instagram) a publikuje ich podľa harmonogramu
3. **AnalyticsAgent** — sťahuje metriky z Google Analytics 4, generuje AI insights, posiela reporty

Agenti bežia na pozadí cez APScheduler (cron joby), nie sú request-driven. FastAPI server slúži len na health check a interné API endpointy (manuálne triggery z admin panelu hlavnej appky).

## Tech stack

- Python 3.12, FastAPI, Uvicorn
- APScheduler (AsyncIOScheduler) — cron-based scheduling
- SQLAlchemy 2.0 async (asyncpg) — zdieľaná PostgreSQL DB
- Anthropic Claude API (claude-sonnet-4-5-20250929) — generovanie a review obsahu
- Pydantic v2 + pydantic-settings — konfigurácia
- httpx — async HTTP klient
- Jinja2 — šablóny pre posty a notifikácie
- Docker — Railway deployment

### Externé API integrácie

- **Discord**: webhooky (posting), voliteľne discord.py (bot DM)
- **X/Twitter**: tweepy s OAuth 1.0a (posting), API v2
- **Instagram**: Meta Graph API v21.0 (business account required)
- **Google Analytics 4**: google-analytics-data (GA4 Data API, service account auth)
- **Telegram**: Bot API (alternatívny notifikačný kanál)

## Adresárová štruktúra

```
opcny-agents/
├── main.py                     # Entry point — FastAPI + scheduler startup
├── config/
│   ├── settings.py             # Pydantic Settings — VŠETKY env vars
│   └── persona.py              # Writing persóna, platform guidelines, review rules
├── models/
│   ├── base.py                 # SQLAlchemy engine, session factory, Base
│   └── tables.py               # Všetkých 5 tabuliek: ScheduledPost, ContentReview,
│                                #   AnalyticsSnapshot, AgentLog, AgentMemory
├── agents/
│   ├── base.py                 # BaseAgent ABC — logging, timing, error handling
│   ├── content_review.py       # ContentReviewAgent
│   ├── social_media.py         # SocialMediaAgent
│   └── analytics.py            # AnalyticsAgent
├── services/
│   ├── claude_service.py       # Anthropic Claude API wrapper
│   ├── discord_service.py      # Discord webhook posting + notifikácie
│   ├── twitter_service.py      # X/Twitter tweepy wrapper
│   ├── instagram_service.py    # Instagram Graph API wrapper
│   ├── ga4_service.py          # Google Analytics 4 Data API
│   └── memory_service.py       # Agent pamäť — deduplikácia tém cez Claude
├── tasks/
│   └── scheduler.py            # APScheduler setup, cron joby, job management
├── api/
│   └── routes.py               # Health check + manual trigger endpoints
├── utils/
│   └── notifications.py        # Notifikačný dispatcher (Discord/Telegram)
├── templates/                  # Jinja2 šablóny pre posty a reporty
│   ├── post_discord.j2
│   ├── post_twitter.j2
│   ├── post_instagram.j2
│   ├── analytics_report.j2
│   └── review_notification.j2
├── pyproject.toml
├── Dockerfile
├── railway.toml
└── .env.example
```

## Architektonické princípy

### Agent pattern

Každý agent MUSÍ dediť z `BaseAgent` (agents/base.py):

```python
class MojNovyAgent(BaseAgent):
    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "default")
        # ... logika ...
        return {"status": "success", "details": {...}}
```

- `execute()` je abstraktná metóda — implementuj ju, nie `run()`
- `run()` je wrapper volaný zo schedulera — pridáva timing, logging do DB, error handling
- Vždy vracaj `{"status": "success|error|skipped", "details": {...}}`
- Nikdy nevolaj `run()` z iného `run()` — používaj priamo `execute()` alebo deleguj cez `_helper()` metódy

### Databáza

- Zdieľaná PostgreSQL s hlavnou opcnysimulator appkou — NIKDY nemodifikuj tabuľky hlavnej appky
- Naše tabuľky: `scheduled_posts`, `content_reviews`, `analytics_snapshots`, `agent_logs`, `agent_memory`
- Používaj `async_session()` context manager pre všetky DB operácie
- Všetky ID sú UUID (okrem agent_logs ktorý je BIGSERIAL)
- Vždy použi `timezone=True` pre DateTime stĺpce
- Model zmeny vyžadujú Alembic migráciu (keď bude nastavený)

### Agent pamäť a deduplikácia

- `MemoryService` (`services/memory_service.py`) ukladá témy generovaných postov do `agent_memory` tabuľky
- Pri generovaní nového postu sa kontroluje duplicita cez `is_too_similar()` — porovnáva len proti **publikovaným** postom (INNER JOIN s `scheduled_posts` kde `status='published'`)
- Claude posudzuje sémantickú podobnosť (nie exact match)
- Kontext nedávnych tém sa pridáva do promptu aby sa agent neopakoval

### Konfigurácia

- VŠETKY env premenné musia ísť cez `config/settings.py` (Pydantic Settings)
- Nikdy nečítaj `os.environ` priamo — vždy `from config.settings import settings`
- Nová env premenná = pridaj do `Settings` triedy AJ do `.env.example`

### Claude API volania

- Vždy používaj `services/claude_service.py` — nikdy nevolaj Anthropic API priamo
- Pre JSON odpovede použi `response_format="json"` parameter — JSON inštrukcia sa automaticky pridá do **system promptu** (nie user message, aby sa neleak-ovala do obsahu)
- System prompt = persóna + pravidlá (z `config/persona.py`)
- Model: `claude-sonnet-4-5-20250929` (konfigurovateľné cez env)

### Notifikácie

- Všetky notifikácie Mirovi idu cez `utils/notifications.py` → `notify_miro()`
- V development mode sa iba logujú (neposielajú sa reálne)
- Podporované kanály: Discord webhook, Telegram Bot API

### Error handling

- `BaseAgent.run()` zachytáva všetky výnimky a loguje ich do `agent_logs`
- Services by mali propagovať výnimky hore (nech ich zachytí agent)
- Ak service zlyhá, vráť dict s `{"status": "error", ...}`, nie raise

## Kódové konvencie

### Python štýl

- Python 3.12+ — používaj `X | None` namiesto `Optional[X]`
- Ruff linter: `ruff check .` (pravidlá E, F, I, N, W, UP)
- Line length: 100
- Async-first — všetky I/O operácie musia byť async
- Type hints na všetkých verejných metódach
- Docstringy na triedach a verejných metódach (triple-quote, prvý riadok = summary)

### Import order

```python
# 1. stdlib
import json
import logging
from datetime import datetime

# 2. third-party
from sqlalchemy import select
import httpx

# 3. local
from agents.base import BaseAgent
from config.settings import settings
from models import async_session, ScheduledPost
```

### Komentáre a jazyk

- Docstringy a komentáre v kóde: **slovenčina** (hlavný jazyk projektu)
- Názvy premenných, tried, funkcií: **angličtina**
- Git commit messages: **angličtina**
- Logy: slovenčina je OK, ale error messages nech sú anglicky (pre debugging)

### Naming

- Triedy: PascalCase (`ContentReviewAgent`, `ScheduledPost`)
- Funkcie/metódy: snake_case (`_run_review`, `get_metrics`)
- Privátne metódy: prefix `_` (`_publish_to_platforms`)
- Konštanty: SCREAMING_SNAKE_CASE (`WRITING_PERSONA`, `PLATFORM_GUIDELINES`)
- Tabuľky: snake_case plural (`scheduled_posts`, `agent_logs`)

## Workflow a lifecycle príspevkov

### Auto-publish flow (z admin panelu, auto_publish=True)

```
[Admin panel: Generuj post]
        │
        ▼
  generate_post()               ← SocialMediaAgent
  + kontrola duplicity (MemoryService.is_too_similar)
  + uloženie do pamäte (agent_memory)
  status: "pending_review"
        │
        ▼
  _check_pending_content()      ← ContentReviewAgent (automaticky po generate)
  Kontrola: gramatika, tón, SEO, compliance
  status: "approved" | "needs_changes"
        │
        ├── approved → _publish_scheduled() → "published" | "failed"
        │
        └── needs_changes → Admin panel zobrazí post detail s akciami:
                │
                ├── Opraviť podľa review  → POST /agents/social-media/revise/{id}
                │   (agent prepíše obsah podľa feedbacku, hlavná appka uloží)
                │
                ├── Schváliť manuálne     → hlavná appka zmení status na "approved"
                ├── Publikovať teraz      → POST /agents/social-media/publish/{id}
                ├── Naplánovať            → hlavná appka nastaví scheduled_at
                ├── Upraviť manuálne      → hlavná appka edituje content_body
                └── Odmietnuť / Zmazať   → hlavná appka zmení status / zmaže
```

### Cron-based flow (na pozadí)

```
  _check_pending_content()      ← ContentReviewAgent (cron: každých 30 min)
  _publish_scheduled()          ← SocialMediaAgent (cron: 9:00, 13:00, 18:00)
  daily_report()                ← AnalyticsAgent (cron: denne 6:00)
  weekly_report()               ← AnalyticsAgent (cron: pondelok 7:00)
```

Status flow pre `scheduled_posts.status`:
`draft` → `pending_review` → `approved` / `needs_changes` → `scheduled` → `published` / `failed`

## Scheduler joby

Definované v `tasks/scheduler.py`, cron expressions v `config/settings.py`:

| Job ID | Agent | Cron | Default |
|--------|-------|------|---------|
| `content_review_check` | ContentReviewAgent | `review_check_cron` | `*/30 * * * *` |
| `social_media_publish` | SocialMediaAgent | `content_post_cron` | `0 9,13,18 * * *` |
| `analytics_daily` | AnalyticsAgent | `analytics_daily_cron` | `0 6 * * *` |
| `analytics_weekly` | AnalyticsAgent | `analytics_weekly_cron` | `0 7 * * 1` |

Timezone: `Europe/Bratislava`

## API Endpointy (interné)

Všetky endpointy sú pre internú komunikáciu s hlavnou appkou:

| Method | Path | Popis |
|--------|------|-------|
| GET | `/health` | Health check (Railway) |
| GET | `/status` | Stav scheduler jobov |
| POST | `/agents/social-media/generate` | Generovanie postu (auto-review + auto-publish) |
| POST | `/agents/social-media/publish/{post_id}` | Okamžitá publikácia jedného postu |
| POST | `/agents/social-media/revise/{post_id}` | Prepísanie postu podľa review feedbacku |
| POST | `/agents/content-review/review` | Review jedného obsahu |
| POST | `/agents/content-review/check-pending` | Spustenie kontroly pending |
| POST | `/agents/analytics/daily` | Denný analytics report |
| POST | `/agents/analytics/weekly` | Týždenný analytics report |
| POST | `/agents/analytics/custom` | Custom date range report |

### Generate endpoint response

`POST /agents/social-media/generate` vždy vracia `post_id` a `post_status` na top level v `details`:
```json
{
  "status": "success",
  "details": {
    "post_id": "uuid",
    "post_status": "needs_changes",
    "platforms": ["discord"],
    "review": {"reviewed_count": 1},
    "note": "Post vygenerovaný, review: needs_changes"
  }
}
```

### Revise endpoint

`POST /agents/social-media/revise/{post_id}` — agent prepíše obsah, **neukladá do DB** (to robí hlavná appka):
```json
// Request
{"content_body": {"discord": "..."}, "review_feedback": {"grammar_issues": [...], "summary": "..."}}
// Response
{"status": "success", "details": {"post_id": "uuid", "revised_content_body": {"discord": "..."}}}
```

V development mode je dostupný Swagger UI na `/docs`.

## Vzťah s hlavnou appkou (opcnysimulator)

- **Zdieľaná DB**: Obe appky čítajú/píšu do rovnakej PostgreSQL. Hlavná appka vlastní `blog_posts` tabuľku, my referencujeme `source_blog_id`.
- **Admin panel**: Hlavná appka volá naše API endpointy na triggering agentov a zobrazuje dáta z našich tabuliek (scheduled_posts, content_reviews, analytics_snapshots).
- **Autentifikácia**: Internal API key v headeri `X-API-Key` (zdieľaný secret).
- **Žiadne priame importy**: Medzi repozitármi nie sú spoločné Python packages — komunikácia iba cez DB a HTTP.

## Časté úlohy

### Pridanie nového agenta

1. Vytvor `agents/novy_agent.py` — dedí z `BaseAgent`
2. Implementuj `execute()` s action routing
3. Pridaj do `agents/__init__.py`
4. Pridaj cron job do `tasks/scheduler.py`
5. Pridaj manuálny trigger do `api/routes.py`
6. Pridaj cron expression do `config/settings.py` + `.env.example`

### Pridanie novej platformy (social media)

1. Vytvor `services/nova_platforma_service.py`
2. Pridaj platformu do `config/persona.py` → `PLATFORM_GUIDELINES`
3. Pridaj Jinja2 šablónu do `templates/post_nova_platforma.j2`
4. Aktualizuj `SocialMediaAgent._publish_to_platforms()` o novú platformu
5. Pridaj env vars do `config/settings.py` + `.env.example`
6. Pridaj service do `services/__init__.py`

### Pridanie novej DB tabuľky

1. Pridaj SQLAlchemy model do `models/tables.py`
2. Pridaj do `models/__init__.py` export
3. Vytvor Alembic migráciu (keď bude nastavený): `alembic revision --autogenerate -m "popis"`
4. Nezabudni na indexy pre často queryované stĺpce

### Pridanie nového API endpointu

1. Pridaj Pydantic request model (ak treba) do `api/routes.py`
2. Pridaj route funkciu s proper typing
3. Volaj agenta cez `agent.run(action="...", ...)` — nie priamo `execute()`

## Čo NEROBIŤ

- **Nemodifikuj tabuľky hlavnej appky** (blog_posts, users, atď.)
- **Nevolaj Anthropic API priamo** — vždy cez `ClaudeService`
- **Nepoužívaj sync I/O** — všetko musí byť async (asyncpg, httpx, nie requests)
- **Nepridávaj nové dependencies bez pyproject.toml** — žiadne pip install bez záznamu
- **Nepoužívaj hardcoded credentials** — vždy cez settings
- **Neloguj citlivé dáta** — žiadne API kľúče, tokeny, alebo osobné údaje v logoch
- **Nepoužívaj `print()`** — vždy `self.logger` alebo `logging.getLogger()`
- **Nepoužívaj `requests`** — vždy `httpx` (async)
- **Nepoužívaj `datetime.now()` bez timezone** — vždy `datetime.now(timezone.utc)`

## Testovanie

```bash
# Lint
ruff check .

# Type check
mypy .

# Testy (keď budú)
pytest -xvs

# Lokálne spustenie
cp .env.example .env
# Vyplň aspoň DATABASE_URL a ANTHROPIC_API_KEY
python main.py
```

Pre testovanie jednotlivého agenta:

```python
import asyncio
from agents import ContentReviewAgent

async def test():
    agent = ContentReviewAgent()
    result = await agent.run(
        action="review_single",
        target_type="blog_post",
        target_id="test-123",
        content="Your test content here...",
    )
    print(result)

asyncio.run(test())
```

## Deploy na Railway

```bash
# Railway CLI
railway login
railway link  # prepoj s projektom
railway up    # deploy

# Env vars nastav v Railway dashboarde:
# DATABASE_URL (rovnaký ako hlavná appka)
# ANTHROPIC_API_KEY
# DISCORD_WEBHOOK_URL
# ... ostatné podľa .env.example
```

Service beží na porte z `AGENT_API_PORT` (default 8001). Railway automaticky detekuje Dockerfile.

## Priorita implementácie (roadmap)

Aktuálny stav: **core funguje, agenti generujú a publikujú na Discord**

1. ✅ Projektová štruktúra, modely, base agent
2. ✅ ContentReviewAgent — plne funkčný s Claude API (auto-review)
3. ✅ SocialMediaAgent — generovanie + publikácia Discord + revízia podľa review
4. ✅ Discord service — webhook posting + notifikácie Mirovi
5. ✅ Admin panel integrácia v hlavnej appke (API volania, post detail s akciami)
6. ✅ Agent pamäť + deduplikácia tém (MemoryService)
7. 🔲 Alembic setup + migrácie
8. 🔲 AnalyticsAgent — GA4 Data API integrácia
9. 🔲 Twitter/X integrácia
10. 🔲 Instagram integrácia
11. 🔲 Testy (pytest-asyncio)
