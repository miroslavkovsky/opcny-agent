"""
Abstraktná base trieda pre všetkých agentov.
Poskytuje logging, error handling, a DB session management.
"""

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from models import async_session, AgentLog
from utils.notifications import notify_miro

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), trim_blocks=True,
                         lstrip_blocks=True)


class BaseAgent(ABC):
    """
    Každý agent dedí z BaseAgent a implementuje `execute()`.

    Poskytuje:
    - Automatický logging do DB (agent_logs tabuľka)
    - Error handling s notifikáciou
    - Session management
    """

    def __init__(self):
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(f"agent.{self.name}")

    @abstractmethod
    async def execute(self, **kwargs) -> dict[str, Any]:
        """
        Hlavná logika agenta. Musí vrátiť dict s výsledkami.

        Returns:
            {"status": "success|error|skipped", "details": {...}}
        """
        ...

    async def run(self, **kwargs) -> dict[str, Any]:
        """
        Wrapper okolo execute() — pridáva logging, timing, error handling.
        Volá sa zo schedulera.
        """
        start = time.monotonic()
        action = kwargs.get("action", "default")
        self.logger.info(f"Spúšťam akciu: {action}")

        try:
            result = await self.execute(**kwargs)
            duration_ms = int((time.monotonic() - start) * 1000)

            await self._log(
                action=action,
                status=result.get("status", "success"),
                details=result.get("details"),
                duration_ms=duration_ms,
            )

            self.logger.info(f"Akcia {action} dokončená za {duration_ms}ms")
            return result

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            self.logger.error(f"Chyba v akcii {action}: {e}", exc_info=True)

            await self._log(
                action=action,
                status="error",
                error_message=str(e),
                duration_ms=duration_ms,
            )

            try:
                await notify_miro(
                    title=f"Agent {self.name} — chyba",
                    message=f"Akcia `{action}` zlyhala: {e}",
                    level="error",
                )
            except Exception:
                self.logger.warning("Nepodarilo sa odoslať error notifikáciu")

            return {"status": "error", "error": str(e)}

    async def _log(
        self,
        action: str,
        status: str,
        details: dict | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
    ):
        """Uloží log záznam do databázy."""
        try:
            async with async_session() as session:
                log = AgentLog(
                    agent_name=self.name,
                    action=action,
                    status=status,
                    details=details,
                    error_message=error_message,
                    duration_ms=duration_ms,
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            self.logger.warning(f"Nepodarilo sa zapísať log: {e}")

    def _render_template(self, template_name: str, **context: Any) -> str:
        """Renderuje Jinja2 šablónu z templates/ adresára."""
        template = _jinja_env.get_template(template_name)
        return template.render(**context)
