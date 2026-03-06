"""
Claude API wrapper — centralizované volania pre všetkých agentov.
"""

import logging

from anthropic import AsyncAnthropic

from config.settings import settings

logger = logging.getLogger("service.claude")


class ClaudeService:
    """Async wrapper pre Anthropic Claude API."""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens

    async def generate(
        self,
        user_message: str,
        system_prompt: str = "",
        response_format: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Vygeneruje odpoveď cez Claude API.

        Args:
            user_message: Prompt pre Claude
            system_prompt: System prompt (persóna, pravidlá)
            response_format: "json" ak chceš JSON odpoveď
            max_tokens: Override pre max tokens
            temperature: Kreativita (0.0 = deterministický, 1.0 = kreatívny)

        Returns:
            Text odpovede od Claude
        """
        if response_format == "json":
            # JSON inštrukcia ide do system promptu, nie do user message,
            # aby sa neleak-ovala do generovaného obsahu
            system_prompt += (
                "\n\nIMPORTANT: Respond ONLY with a valid JSON object. "
                "No markdown, no backticks, no explanation — just pure JSON."
            )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature,
                system=system_prompt or "Si pomocný asistent.",
                messages=[{"role": "user", "content": user_message}],
            )

            text = response.content[0].text

            # Očisti JSON odpoveď od prípadných markdown backticks
            if response_format == "json" and text.startswith("```"):
                text = text.strip("`").removeprefix("json").strip()

            logger.debug(
                f"Claude response: {len(text)} chars, "
                f"usage: {response.usage.input_tokens}+{response.usage.output_tokens} tokens"
            )

            return text

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
