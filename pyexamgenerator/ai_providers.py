# pyexamgenerator: A tool for generating exams from PDF files using AI.
# Copyright (C) 2024 Daniel Sánchez-García

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Uniform access to the AI providers supported for question generation.

* ``gemini``: Google Gemini API (the keys are created in Google AI Studio).
* ``openai``: OpenAI API (ChatGPT models).
* ``anthropic``: Anthropic API (Claude models).

Each provider SDK is imported only when it is used, so the package works
(including the manual, no-API workflow) even if some SDKs are not installed.
"""

import base64
import importlib
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .question_parsing import QUESTIONS_JSON_SCHEMA


class AIProviderError(Exception):
    """Base class for errors returned by an AI provider."""
    pass


class QuotaExceededError(AIProviderError):
    """The request limit or quota of the provider was exceeded (HTTP 429)."""
    pass


class ServiceOverloadedError(AIProviderError):
    """The provider servers are overloaded or temporarily unavailable (HTTP 5xx/529)."""
    pass


class InvalidAPIKeyError(AIProviderError):
    """The API key is missing, invalid or lacks permissions (HTTP 401/403)."""
    pass


class ModelNotFoundError(AIProviderError):
    """The requested model does not exist or is not available for the key (HTTP 404)."""
    pass


class ProviderNotAvailableError(AIProviderError, ImportError):
    """The SDK of the provider is not installed."""
    pass


@dataclass(frozen=True)
class ProviderSpec:
    """Static information about a provider (used by the API and by the GUI)."""
    key: str
    label: str
    env_vars: Tuple[str, ...]
    sdk_module: str
    install_hint: str
    default_models: Tuple[str, ...]
    api_key_url: str
    chat_name: str
    chat_url: str


PROVIDERS: Dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        key="gemini",
        label="Google Gemini (AI Studio)",
        env_vars=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        sdk_module="google.genai",
        install_hint="pip install google-genai",
        default_models=("gemini-flash-latest", "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-pro-latest"),
        api_key_url="https://aistudio.google.com/app/apikey",
        chat_name="Google AI Studio",
        chat_url="https://aistudio.google.com/prompts/new_chat",
    ),
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI (ChatGPT)",
        env_vars=("OPENAI_API_KEY",),
        sdk_module="openai",
        install_hint="pip install pyexamgenerator[openai]",
        default_models=("gpt-6.1-sol", "gpt-6-luna", "gpt-6-astra"),
        api_key_url="https://platform.openai.com/api-keys",
        chat_name="ChatGPT",
        chat_url="https://chatgpt.com/",
    ),
    "anthropic": ProviderSpec(
        key="anthropic",
        label="Anthropic (Claude)",
        env_vars=("ANTHROPIC_API_KEY",),
        sdk_module="anthropic",
        install_hint="pip install pyexamgenerator[anthropic]",
        default_models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"),
        api_key_url="https://console.anthropic.com/settings/keys",
        chat_name="Claude",
        chat_url="https://claude.ai/new",
    ),
}

DEFAULT_PROVIDER = "gemini"

_PROVIDER_ALIASES = {
    "gemini": "gemini",
    "google": "gemini",
    "google gemini": "gemini",
    "ai studio": "gemini",
    "aistudio": "gemini",
    "google ai studio": "gemini",
    "openai": "openai",
    "chatgpt": "openai",
    "gpt": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
}

#: Placeholder shown in the GUI when no key is configured.
API_KEY_PLACEHOLDER = "TU_CLAVE_API"


def resolve_provider(provider: Optional[str]) -> str:
    """
    Returns the canonical provider key ('gemini', 'openai' or 'anthropic').

    Accepts the canonical keys, the GUI labels and common aliases
    ('google', 'ai studio', 'chatgpt', 'claude'...). ``None`` means Gemini.
    """
    if provider is None or not str(provider).strip():
        return DEFAULT_PROVIDER
    text = str(provider).strip().lower()
    if text in _PROVIDER_ALIASES:
        return _PROVIDER_ALIASES[text]
    for key, spec in PROVIDERS.items():
        if text == spec.label.lower():
            return key
    raise ValueError(
        f"Proveedor de IA desconocido: {provider!r}. Use uno de: {', '.join(PROVIDERS)}."
    )


def get_provider_spec(provider: Optional[str]) -> ProviderSpec:
    """Returns the :class:`ProviderSpec` of a provider (aliases accepted)."""
    return PROVIDERS[resolve_provider(provider)]


def get_api_key_from_env(provider: Optional[str]) -> Optional[str]:
    """Returns the API key defined in the environment variables of the provider, if any."""
    for env_var in get_provider_spec(provider).env_vars:
        value = os.getenv(env_var)
        if value and value.strip():
            return value.strip()
    return None


def is_valid_api_key(api_key: Optional[str]) -> bool:
    """True if ``api_key`` looks like a real key (not empty nor the GUI placeholder)."""
    return bool(api_key and api_key.strip() and api_key.strip() != API_KEY_PLACEHOLDER)


def is_provider_installed(provider: Optional[str]) -> bool:
    """True if the SDK of the provider can be imported."""
    try:
        importlib.import_module(get_provider_spec(provider).sdk_module)
        return True
    except ImportError:
        return False


def _import_sdk(provider: str):
    spec = PROVIDERS[provider]
    try:
        return importlib.import_module(spec.sdk_module)
    except ImportError as exc:
        raise ProviderNotAvailableError(
            f"La librería de {spec.label} no está instalada. Instálala con:\n    {spec.install_hint}"
        ) from exc


def _status_code(exc: BaseException) -> Optional[int]:
    for attr in ("status_code", "code", "http_status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


_AUTH_ERROR_TEXTS = (
    "api key not valid", "api_key_invalid", "invalid x-api-key", "incorrect api key", "invalid api key",
    "could not resolve authentication",
)


def _is_auth_error(exc: BaseException) -> bool:
    """True for authentication problems (Gemini answers an invalid key with HTTP 400)."""
    if _status_code(exc) in (401, 403):
        return True
    lowered = str(exc).lower()
    return any(text in lowered for text in _AUTH_ERROR_TEXTS)


class BaseAIClient:
    """
    Common interface of the provider clients.

    Args:
        api_key (str): API key of the provider.
        model_name (str): Model identifier (e.g. 'gemini-flash-latest', 'gpt-6.1-sol', 'claude-opus-5-5').
        max_output_tokens (Optional[int]): Maximum length of the answer. ``None`` uses the
            provider default (Anthropic requires a value, so a default is applied).
        temperature (Optional[float]): Sampling temperature. ``None`` keeps the model default
            (recommended: reasoning models and the current Claude models reject other values).
        timeout (Optional[float]): Request timeout in seconds.
        structured_output (bool): Ask the API for JSON matching
            :data:`~pyexamgenerator.question_parsing.QUESTIONS_JSON_SCHEMA`. If the model or the
            installed SDK does not support it, it is disabled automatically and the answer is
            requested as plain text (the prompt already asks for JSON).
        sdk_client (Any): Already configured SDK client (useful for tests or proxies).
    """

    provider = ""

    def __init__(
            self,
            api_key: Optional[str],
            model_name: Optional[str] = None,
            *,
            max_output_tokens: Optional[int] = None,
            temperature: Optional[float] = None,
            timeout: Optional[float] = None,
            structured_output: bool = True,
            sdk_client: Any = None,
    ):
        if sdk_client is None and not is_valid_api_key(api_key):
            spec = PROVIDERS[self.provider]
            raise InvalidAPIKeyError(
                f"Falta la clave API de {spec.label}. Indícala en la aplicación o en la variable "
                f"de entorno {spec.env_vars[0]}."
            )
        self.api_key = api_key.strip() if api_key else None
        self.model_name = model_name
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.structured_output = structured_output
        self._sdk_client = sdk_client

    @property
    def spec(self) -> ProviderSpec:
        return PROVIDERS[self.provider]

    @property
    def sdk_client(self) -> Any:
        """The underlying SDK client (created on first use)."""
        if self._sdk_client is None:
            try:
                self._sdk_client = self._create_sdk_client()
            except AIProviderError:
                raise
            except Exception as exc:
                raise self.translate_error(exc) from exc
        return self._sdk_client

    def generate(self, prompt: str, attachments: Optional[Sequence[Dict[str, Any]]] = None) -> str:
        """
        Sends ``prompt`` (and optional attachments) to the model and returns the answer text.

        Args:
            prompt (str): The instructions.
            attachments (Optional[Sequence[Dict]]): Files as ``{"bytes", "mime_type", "name"}``;
                images (``image/*``) and PDF documents (``application/pdf``) are supported.

        Raises:
            QuotaExceededError, ServiceOverloadedError, InvalidAPIKeyError,
            ModelNotFoundError, ProviderNotAvailableError, AIProviderError.
        """
        if not self.model_name:
            raise AIProviderError(f"No se ha indicado el modelo de {self.spec.label}.")
        attachments = list(attachments or [])
        client = self.sdk_client
        try:
            return self._generate(client, prompt, attachments, self.structured_output)
        except AIProviderError:
            raise
        except Exception as exc:
            if not self._should_retry_without_structured_output(exc):
                raise self.translate_error(exc) from exc
            first_error = exc
        # The model (or an old SDK) rejected the structured-output option: plain text request.
        try:
            text = self._generate(client, prompt, attachments, False)
        except AIProviderError:
            raise
        except Exception as exc:
            raise self.translate_error(exc) from exc
        print(f"    Aviso: el modelo no admite salida JSON estructurada ({first_error}); "
              "se continúa sin ella.")
        self.structured_output = False
        return text

    def _should_retry_without_structured_output(self, exc: BaseException) -> bool:
        if not self.structured_output or _is_auth_error(exc):
            return False
        # 400: rejected by the API; TypeError/ValueError: unknown parameter in an old SDK.
        return _status_code(exc) == 400 or isinstance(exc, (TypeError, ValueError))

    def list_models(self) -> List[Dict[str, Any]]:
        """
        Lists the models available for text generation.

        Returns:
            List[Dict]: One dict per model with the keys ``name``, ``display_name``,
            ``version``, ``input_tokens``, ``output_tokens`` and ``description``.
        """
        try:
            return self._list_models(self.sdk_client)
        except AIProviderError:
            raise
        except Exception as exc:
            raise self.translate_error(exc) from exc

    def translate_error(self, exc: BaseException) -> AIProviderError:
        """Converts an SDK exception into an :class:`AIProviderError` with a helpful message."""
        label = self.spec.label
        code = _status_code(exc)
        message = str(exc)
        lowered = message.lower()
        lighter_model_hint = {
            "gemini": "un modelo 'Flash' (p. ej. 'gemini-flash-latest')",
            "openai": "un modelo más ligero (p. ej. 'gpt-6-luna')",
            "anthropic": "un modelo más ligero (p. ej. 'claude-haiku-5-5')",
        }[self.provider]

        if _is_auth_error(exc):
            code = code if code in (401, 403) else 401
        elif code is None:
            # No HTTP status available: infer it from the message.
            if any(text in lowered for text in ("resource_exhausted", "rate limit", "quota")):
                code = 429
            elif any(text in lowered for text in ("overloaded", "unavailable")):
                code = 503
            elif any(text in lowered for text in ("not_found", "model_not_found", "not found")):
                code = 404

        if code in (401, 403):
            return InvalidAPIKeyError(
                f"{label} ha rechazado la clave API (Error {code}).\n\n"
                f"Comprueba la clave o crea una nueva en {self.spec.api_key_url}\n\nDetalle: {message}"
            )
        if code == 429:
            billing = ""
            if getattr(exc, "code", None) == "insufficient_quota" or "insufficient_quota" in lowered \
                    or "credit balance" in lowered or "billing" in lowered:
                billing = ("\n3. Revisa el saldo o la facturación de tu cuenta: la API no tiene crédito "
                           "disponible (esperar no lo soluciona).")
            return QuotaExceededError(
                f"Has excedido el límite de solicitudes o la cuota de la API de {label} (Error 429).\n\n"
                "Sugerencias para solucionarlo:\n"
                "1. Espera unos minutos: los límites por minuto/día se reinician periódicamente.\n"
                f"2. Cambia de modelo: prueba {lighter_model_hint}, que es más rápido y económico."
                f"{billing}\n\nDetalle: {message}"
            )
        if code in (500, 502, 503, 504, 529):
            return ServiceOverloadedError(
                f"Los servidores de {label} para este modelo están saturados o no disponibles "
                f"(Error {code}).\n\n"
                "Sugerencias para solucionarlo:\n"
                f"1. Cambia de modelo: prueba {lighter_model_hint}.\n"
                "2. Espera unos minutos e inténtalo de nuevo."
                f"\n\nDetalle: {message}"
            )
        if code == 404:
            return ModelNotFoundError(
                f"El modelo '{self.model_name}' no existe o no está disponible para tu clave de {label}.\n"
                "Pulsa 'Cargar Modelos' y elige uno de la lista.\n\n"
                f"Detalle: {message}"
            )
        return AIProviderError(f"Error de {label}: {message}")

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.b64encode(data).decode("ascii")

    def _create_sdk_client(self) -> Any:
        raise NotImplementedError

    def _generate(self, client: Any, prompt: str, attachments: List[Dict[str, Any]], structured: bool) -> str:
        raise NotImplementedError

    def _list_models(self, client: Any) -> List[Dict[str, Any]]:
        raise NotImplementedError


class GeminiClient(BaseAIClient):
    """Client for the Google Gemini API (``google-genai``)."""

    provider = "gemini"
    _EXCLUDED_MODEL_WORDS = ("embedding", "tts", "native-audio", "live", "image", "aqa", "robotics")

    def _create_sdk_client(self) -> Any:
        genai = _import_sdk(self.provider)
        types_module = importlib.import_module("google.genai.types")
        http_options: Dict[str, Any] = {}
        if self.timeout:
            http_options["timeout"] = int(self.timeout * 1000)  # milliseconds
        if hasattr(types_module, "HttpRetryOptions"):
            # Without retry options the SDK makes a single attempt (no retry on 429/5xx).
            http_options["retry_options"] = types_module.HttpRetryOptions(attempts=4)
        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if http_options:
            kwargs["http_options"] = types_module.HttpOptions(**http_options)
        return genai.Client(**kwargs)

    def _generate(self, client: Any, prompt: str, attachments: List[Dict[str, Any]], structured: bool) -> str:
        types_module = importlib.import_module("google.genai.types")
        if attachments:
            contents: Any = [
                types_module.Part.from_bytes(data=item["bytes"], mime_type=item["mime_type"])
                for item in attachments
            ]
            contents.append(prompt)
        else:
            contents = prompt

        config_kwargs: Dict[str, Any] = {}
        if self.max_output_tokens:
            config_kwargs["max_output_tokens"] = self.max_output_tokens
        if self.temperature is not None:
            config_kwargs["temperature"] = self.temperature
        if structured:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_json_schema"] = QUESTIONS_JSON_SCHEMA
        config = types_module.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        response = client.models.generate_content(model=self.model_name, contents=contents, config=config)
        text = getattr(response, "text", None) or ""
        if not text:
            feedback = getattr(response, "prompt_feedback", None)
            candidates = getattr(response, "candidates", None) or []
            reason = getattr(feedback, "block_reason", None) or (
                getattr(candidates[0], "finish_reason", None) if candidates else None)
            print(f"    Aviso: Gemini no devolvió texto (motivo: {reason or 'desconocido'}).")
        return text

    def _list_models(self, client: Any) -> List[Dict[str, Any]]:
        models = []
        for model in client.models.list():
            name = getattr(model, "name", "") or ""
            if "gemini" not in name or any(word in name for word in self._EXCLUDED_MODEL_WORDS):
                continue
            actions = getattr(model, "supported_actions", None)
            if actions and "generateContent" not in actions:
                continue
            models.append({
                "name": name,
                "display_name": getattr(model, "display_name", None) or name,
                "version": getattr(model, "version", None) or "",
                "input_tokens": getattr(model, "input_token_limit", None) or "N/A",
                "output_tokens": getattr(model, "output_token_limit", None) or "N/A",
                "description": (getattr(model, "description", None) or "").replace("\n", " "),
            })
        return models


class OpenAIClient(BaseAIClient):
    """Client for the OpenAI API (``openai``), using the Responses API."""

    provider = "openai"
    _MODEL_PREFIXES = ("gpt-", "o1", "o3", "o4", "chatgpt-")
    _EXCLUDED_MODEL_WORDS = (
        "audio", "realtime", "tts", "transcribe", "image", "search", "embedding",
        "moderation", "instruct", "dall-e", "whisper", "babbage", "davinci", "sora", "codex",
    )

    def _create_sdk_client(self) -> Any:
        openai = _import_sdk(self.provider)
        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.timeout:
            kwargs["timeout"] = self.timeout
        return openai.OpenAI(**kwargs)

    def _generate(self, client: Any, prompt: str, attachments: List[Dict[str, Any]], structured: bool) -> str:
        content: List[Dict[str, Any]] = []
        for index, item in enumerate(attachments, start=1):
            mime_type = item["mime_type"]
            data_url = f"data:{mime_type};base64,{self._b64(item['bytes'])}"
            if mime_type.startswith("image/"):
                content.append({"type": "input_image", "detail": "auto", "image_url": data_url})
            else:
                content.append({
                    "type": "input_file",
                    "filename": item.get("name") or f"documento_{index}.pdf",
                    "file_data": data_url,
                })
        content.append({"type": "input_text", "text": prompt})

        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "input": [{"role": "user", "content": content}],
        }
        if self.max_output_tokens:
            kwargs["max_output_tokens"] = self.max_output_tokens
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if structured:
            kwargs["text"] = {"format": {
                "type": "json_schema", "name": "lote_preguntas", "schema": QUESTIONS_JSON_SCHEMA, "strict": True,
            }}
        response = client.responses.create(**kwargs)
        if getattr(response, "status", None) == "incomplete":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
            print(f"    Aviso: la respuesta de OpenAI está incompleta ({reason or 'límite de tokens'}); "
                  "se aprovecharán las preguntas completas.")
        return getattr(response, "output_text", None) or ""

    def _list_models(self, client: Any) -> List[Dict[str, Any]]:
        models = []
        for model in client.models.list():
            model_id = getattr(model, "id", "") or ""
            if not model_id.startswith(self._MODEL_PREFIXES) or \
                    any(word in model_id for word in self._EXCLUDED_MODEL_WORDS):
                continue
            shutdown_date = getattr(model, "shutdown_date", None)
            models.append({
                "name": model_id,
                "display_name": model_id,
                "version": "",
                "input_tokens": "N/A",
                "output_tokens": "N/A",
                "description": f"Retirada prevista: {shutdown_date}" if shutdown_date else
                f"Propietario: {getattr(model, 'owned_by', '') or 'openai'}",
                "_created": getattr(model, "created", None) or 0,
            })
        models.sort(key=lambda m: m["_created"], reverse=True)
        for model in models:
            del model["_created"]
        return models


class AnthropicClient(BaseAIClient):
    """Client for the Anthropic API (``anthropic``)."""

    provider = "anthropic"
    #: Anthropic requires an explicit maximum length for the answer.
    DEFAULT_MAX_OUTPUT_TOKENS = 16000

    def _create_sdk_client(self) -> Any:
        anthropic = _import_sdk(self.provider)
        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.timeout:
            kwargs["timeout"] = self.timeout
        return anthropic.Anthropic(**kwargs)

    def _generate(self, client: Any, prompt: str, attachments: List[Dict[str, Any]], structured: bool) -> str:
        content: List[Dict[str, Any]] = []
        for item in attachments:
            mime_type = item["mime_type"]
            block_type = "image" if mime_type.startswith("image/") else "document"
            content.append({
                "type": block_type,
                "source": {"type": "base64", "media_type": mime_type, "data": self._b64(item["bytes"])},
            })
        content.append({"type": "text", "text": prompt})

        # The temperature is not sent: the SDK has no such parameter and the current
        # Claude models reject non-default sampling values.
        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": self.max_output_tokens or self.DEFAULT_MAX_OUTPUT_TOKENS,
            "messages": [{"role": "user", "content": content}],
        }
        if structured:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": QUESTIONS_JSON_SCHEMA}}
        # Streaming avoids the SDK limit for long non-streaming requests.
        with client.messages.stream(**kwargs) as stream:
            message = stream.get_final_message()
        stop_reason = getattr(message, "stop_reason", None)
        if stop_reason == "max_tokens":
            print("    Aviso: la respuesta de Claude se cortó por el límite de tokens; "
                  "se aprovecharán las preguntas completas.")
        elif stop_reason == "refusal":
            print("    Aviso: Claude ha rechazado responder a esta petición.")
        return "".join(
            getattr(block, "text", "") for block in getattr(message, "content", [])
            if getattr(block, "type", None) == "text"
        )

    def _list_models(self, client: Any) -> List[Dict[str, Any]]:
        models = []
        for model in client.models.list(limit=100):
            if getattr(model, "lifecycle", "active") not in (None, "active"):
                continue
            model_id = getattr(model, "id", "") or ""
            created_at = getattr(model, "created_at", None)
            models.append({
                "name": model_id,
                "display_name": getattr(model, "display_name", None) or model_id,
                "version": "",
                "input_tokens": getattr(model, "max_input_tokens", None) or "N/A",
                "output_tokens": getattr(model, "max_tokens", None) or "N/A",
                "description": f"Publicado: {created_at:%Y-%m-%d}" if hasattr(created_at, "strftime") else "",
            })
        return models


_CLIENT_CLASSES = {
    "gemini": GeminiClient,
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
}


def create_ai_client(provider: Optional[str], api_key: Optional[str], model_name: Optional[str] = None,
                     **kwargs) -> BaseAIClient:
    """
    Creates the client of ``provider``.

    Args:
        provider (Optional[str]): 'gemini', 'openai' or 'anthropic' (aliases accepted).
        api_key (Optional[str]): API key; if empty, the provider environment variable is used.
        model_name (Optional[str]): Model identifier.
        **kwargs: Extra options for :class:`BaseAIClient` (``max_output_tokens``,
            ``temperature``, ``timeout``, ``structured_output``, ``sdk_client``).
    """
    key = resolve_provider(provider)
    if not is_valid_api_key(api_key):
        api_key = get_api_key_from_env(key)
    return _CLIENT_CLASSES[key](api_key, model_name, **kwargs)


def list_available_models(provider: Optional[str], api_key: Optional[str]) -> List[Dict[str, Any]]:
    """Lists the text-generation models available for ``api_key`` in ``provider``."""
    return create_ai_client(provider, api_key).list_models()
