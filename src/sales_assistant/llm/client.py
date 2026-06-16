from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from pathlib import Path

import requests
import urllib3
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from sales_assistant.config import Settings


class LLMConfigurationError(RuntimeError):
    """Raised when the configured LLM cannot be created."""


@dataclass(frozen=True, slots=True)
class VertexModelFactory:
    settings: Settings

    def is_configured(self) -> bool:
        return bool(self.settings.google_cloud_project and self.settings.google_cloud_location)

    def build_chat_model(self):
        if not self.is_configured():
            raise LLMConfigurationError(
                "Falta configurar GOOGLE_CLOUD_PROJECT y GOOGLE_CLOUD_LOCATION para Vertex AI."
            )

        try:
            import google.auth
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as error:
            raise LLMConfigurationError(
                "Faltan dependencias para LangChain con Vertex AI. "
                "Instala langchain, langgraph, langchain-google-genai y google-genai."
            ) from error

        try:
            base_credentials, _ = google.auth.default()
        except Exception as error:  # pragma: no cover - depends on local credentials
            raise LLMConfigurationError(
                "No se encontraron credenciales ADC válidas para Vertex AI en este entorno."
            ) from error

        credentials, client_args = self._prepare_vertex_runtime(base_credentials)

        return ChatGoogleGenerativeAI(
            model=self.settings.vertex_model_fast,
            project=self.settings.google_cloud_project,
            location=self.settings.google_cloud_location,
            vertexai=True,
            temperature=0,
            credentials=credentials,
            client_args=client_args,
        )

    def _prepare_vertex_runtime(
        self,
        credentials: object,
    ) -> tuple[object, dict[str, object]]:
        try:
            request = Request()
            request.session.trust_env = False
            credentials.refresh(request)  # type: ignore[union-attr]
            return credentials, {"trust_env": False}
        except Exception as error:
            manual_credentials = self._build_insecure_authorized_user_credentials(error)
            return manual_credentials, {
                "trust_env": False,
                "verify": ssl._create_unverified_context(),
            }

    def _build_insecure_authorized_user_credentials(self, original_error: Exception) -> Credentials:
        adc_path = (
            Path.home()
            / "AppData"
            / "Roaming"
            / "gcloud"
            / "application_default_credentials.json"
        )
        if not adc_path.exists():
            raise LLMConfigurationError(
                "No fue posible refrescar ADC para Vertex AI y no existe el archivo "
                "application_default_credentials.json."
            ) from original_error

        data = json.loads(adc_path.read_text(encoding="utf-8"))
        if data.get("type") != "authorized_user":
            raise LLMConfigurationError(
                "No fue posible refrescar ADC para Vertex AI con el certificado actual."
            ) from original_error

        required_keys = {"client_id", "client_secret", "refresh_token"}
        if not required_keys.issubset(data):
            raise LLMConfigurationError(
                "El archivo ADC no contiene client_id, client_secret y refresh_token."
            ) from original_error

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        session = requests.Session()
        session.trust_env = False
        response = session.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": data["client_id"],
                "client_secret": data["client_secret"],
                "refresh_token": data["refresh_token"],
                "grant_type": "refresh_token",
            },
            verify=False,
            timeout=60,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise LLMConfigurationError(
                "No fue posible obtener un access token para Vertex AI desde las ADC locales."
            ) from error

        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise LLMConfigurationError(
                "La respuesta del refresh token no contiene access_token válido."
            )

        return Credentials(
            token=access_token,
            quota_project_id=self.settings.google_cloud_project,
        )
