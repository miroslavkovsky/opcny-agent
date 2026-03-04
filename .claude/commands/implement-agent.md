Dokonči implementáciu agenta $AGENT_NAME tak, aby bol plne funkčný.

Prečítaj si CLAUDE.md pre kontext projektu. Potom:

1. Prečítaj aktuálny stav agenta v `agents/$AGENT_NAME.py`
2. Identifikuj čo chýba alebo je len kostra
3. Doimplementuj všetky metódy — reálna logika, nie placeholder
4. Over že service wrapery ktoré agent používa sú funkčné
5. Pridaj proper error handling na všetky externé volania
6. Pridaj meaningful log messages (self.logger)
7. Over Jinja2 šablóny — sú kompatibilné s dátami ktoré agent produkuje?
8. Napíš aspoň jeden integrovaný smoke test (mockované externé služby)
9. Spusti ruff check a oprav chyby
10. Vypiš súhrn čo bolo implementované a čo ešte zostáva

DÔLEŽITÉ: Nemodifikuj BaseAgent, settings štruktúru, ani DB modely pokiaľ to nie je absolútne nutné. Ak treba zmeny v týchto core súboroch, najprv ich navrhni a počkaj na potvrdenie.
