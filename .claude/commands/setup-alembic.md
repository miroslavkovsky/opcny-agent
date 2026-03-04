Nastav Alembic pre databázové migrácie v tomto projekte.

Kroky:
1. Over že alembic je v pyproject.toml dependencies (už by mal byť)
2. Spusti `alembic init alembic` na vytvorenie adresárovej štruktúry
3. Uprav `alembic/env.py`:
   - Importuj `models.base.Base` a `models.tables` (všetky modely)
   - Nastav `target_metadata = Base.metadata`
   - Nakonfiguruj async engine z `config.settings.settings.database_url`
   - Použi `run_async_migrations()` pattern pre async SQLAlchemy
4. Uprav `alembic.ini`:
   - Nastav `sqlalchemy.url` na prázdny string (bude z env.py)
5. Vytvor prvú migráciu: `alembic revision --autogenerate -m "initial agent tables"`
6. Over migračný súbor — skontroluj že sú tam všetky 4 tabuľky a indexy

DÔLEŽITÉ: Nepouži sync SQLAlchemy driver — tento projekt používa asyncpg. Alembic env.py musí použiť `async_engine_from_config` alebo `run_sync` pattern.
