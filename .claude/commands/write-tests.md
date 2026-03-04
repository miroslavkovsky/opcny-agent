Napíš testy pre agenta $AGENT_NAME.

Kroky:
1. Ak neexistuje `tests/` adresár, vytvor ho s `conftest.py` obsahujúcim:
   - pytest-asyncio fixtures
   - Mock async_session (SQLAlchemy)
   - Mock ClaudeService (nikdy nevolaj reálne API v testoch)
   - Mock notification service
2. Vytvor `tests/test_$AGENT_NAME.py`
3. Napíš testy pre každú action ktorú agent podporuje:
   - Test úspešného prípadu (happy path)
   - Test prázdneho vstupu / žiadna práca (status: skipped)
   - Test error handling (service zlyhá)
   - Test správneho volania Claude API (správny system prompt, správny formát)
4. Použi `unittest.mock.AsyncMock` pre mockovanie async metód
5. Použi `pytest.mark.asyncio` na všetkých async testoch
6. Spusti `pytest -xvs tests/test_$AGENT_NAME.py` a over že všetky testy prechádzajú

Vzor pre mock:
```python
@pytest.fixture
def mock_claude():
    with patch("agents.content_review.ClaudeService") as mock:
        instance = mock.return_value
        instance.generate = AsyncMock(return_value='{"overall_status": "approved", "summary": "OK"}')
        yield instance
```

DÔLEŽITÉ: Nikdy nevolaj reálne externé API (Claude, Discord, Twitter, GA4) v testoch — vždy mockuj.
