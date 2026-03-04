Vytvor nového agenta s názvom $AGENT_NAME.

Kroky:
1. Vytvor `agents/$AGENT_NAME.py` — trieda musí dediť z `BaseAgent`, implementovať `execute()` s action routing pattern (pozri existujúcich agentov ako vzor)
2. Pridaj export do `agents/__init__.py`
3. Pridaj cron job do `tasks/scheduler.py` — spýtaj sa na požadovaný cron schedule
4. Pridaj manuálny trigger endpoint do `api/routes.py` s Pydantic request modelom
5. Ak agent potrebuje novú env premennú, pridaj ju do `config/settings.py` aj `.env.example`
6. Ak agent potrebuje novú DB tabuľku, pridaj model do `models/tables.py` a export do `models/__init__.py`
7. Ak agent potrebuje nový service, vytvor ho v `services/` podľa existujúcich vzorov

Na konci spusti `ruff check .` a oprav prípadné problémy.
