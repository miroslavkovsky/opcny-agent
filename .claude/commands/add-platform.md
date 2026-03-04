Pridaj novú sociálnu platformu $PLATFORM_NAME do systému.

Kroky:
1. Vytvor `services/$PLATFORM_NAME_service.py` — async trieda s metódami na posting, podľa vzoru existujúcich services (discord_service.py, twitter_service.py)
2. Pridaj platformu do `config/persona.py` → `PLATFORM_GUIDELINES` dict s max_length, style, hashtags, media settings
3. Vytvor Jinja2 šablónu `templates/post_$PLATFORM_NAME.j2`
4. Aktualizuj `SocialMediaAgent._publish_to_platforms()` v `agents/social_media.py` — pridaj elif vetvu
5. Pridaj nový service do `services/__init__.py`
6. Pridaj všetky potrebné env vars (API keys, tokens) do `config/settings.py` a `.env.example`
7. Aktualizuj `SocialMediaAgent.__init__()` — inicializuj nový service

Na konci spusti `ruff check .` a over, že nový service má lazy initialization ak závisí na optional dependencies.
