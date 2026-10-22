"""Client LLM unique : OpenAI ou Ollama (API compatible OpenAI)."""
from __future__ import annotations

PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "base_url": None,
        "default_model": "gpt-4o-mini",
    },
    "ollama": {
        "label": "Ollama (local)",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.1",
    },
}


class LLMError(RuntimeError):
    """Erreur lors de l'appel au modèle."""


class LLMClient:
    def __init__(
        self,
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        if provider not in PROVIDERS:
            raise LLMError(f"Fournisseur inconnu : {provider}")
        cfg = PROVIDERS[provider]
        self.provider = provider
        self.model = model or cfg["default_model"]
        base_url = base_url or cfg["base_url"]

        if provider == "openai" and not api_key:
            raise LLMError("Clé API OpenAI manquante (voir la barre latérale ou le fichier .env).")
        if provider == "ollama":
            api_key = api_key or "ollama"  # valeur factice requise par le SDK

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError("Le paquet 'openai' n'est pas installé (pip install -r requirements.txt).") from exc

        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=120)

    def chat(self, system: str, user: str, json_mode: bool = False, temperature: float = 0.4) -> str:
        """Envoie un message et retourne le texte de la réponse."""
        kwargs = dict(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as first_error:
            if not json_mode:
                raise LLMError(str(first_error)) from first_error
            # Certains modèles locaux ne supportent pas le mode JSON : on réessaie sans.
            kwargs.pop("response_format")
            try:
                resp = self._client.chat.completions.create(**kwargs)
            except Exception as exc:
                raise LLMError(str(exc)) from exc
        return resp.choices[0].message.content or ""
