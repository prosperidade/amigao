"""Dívidas #255 e #256: tabela local do LiteLLM, sem download no import e sem preço desconhecido.

Em 21/09/2026 o download do mapa de modelos expirou em dev e o gpt-5.6-luna ficou
sem provider (jobs 161 e 162). Estes testes travam as duas pontas: todo modelo
configurado está na tabela local, com provider e preço; e importar o app força
o mapa embutido, sem rede.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from app.core.config import Settings
from app.core.litellm_tabela import modelos
from app.core.model_matrix import build_agent_model_matrix

ROOT = Path(__file__).resolve().parents[2]
# Priced elsewhere: transcription is billed by duration (ADR-060).
SEM_TABELA = {"AUDIO_TRANSCRIPTION_MODEL"}


def _configurados():
    defaults = Settings.model_construct()
    found = {name: getattr(defaults, name) for name in Settings.model_fields
             if name.endswith("_MODEL") and name not in SEM_TABELA}
    render = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    for service in render.get("services", []):
        for var in service.get("envVars", []):
            if var.get("key", "").endswith("_MODEL") and var["key"] not in SEM_TABELA and var.get("value"):
                found[f"render:{var['key']}"] = var["value"]
    for agent, row in build_agent_model_matrix(defaults).items():
        for provider, model in row:
            found[f"matriz:{agent}:{provider}"] = model
    from app.services.ocr_pdf import OPENAI_VISION_MODEL
    found["ocr:OPENAI_VISION_MODEL"] = OPENAI_VISION_MODEL
    return found


def test_every_configured_model_has_provider_and_price_in_the_local_table():
    table = modelos()
    missing = {origin: model for origin, model in _configurados().items()
               if not all(table.get(model, {}).get(key) is not None
                          for key in ("litellm_provider", "input_cost_per_token", "output_cost_per_token"))}
    assert not missing, f"Modelos sem provider/preço em app/core/litellm_modelos.json: {missing}"


def test_import_forces_the_embedded_map_and_new_models_resolve_offline():
    code = """
import json
import app  # sets the environment before litellm is imported
from app.core.litellm_tabela import carregar
from litellm.litellm_core_utils.get_model_cost_map import get_model_cost_map_source_info
litellm = carregar()
info = get_model_cost_map_source_info()
print(json.dumps({"source": info.get("source") if isinstance(info, dict) else getattr(info, "source", None),
                  "luna": litellm.get_llm_provider("gpt-5.6-luna")[1],
                  "luna_price": litellm.get_model_info("gpt-5.6-luna")["output_cost_per_token"],
                  "gemini": litellm.get_llm_provider("gemini/gemini-3.7-flash")[1]}))
"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("LITELLM_")}
    # A download attempt, if any, would hit a closed port and silently fall back: the source must say local.
    env["LITELLM_MODEL_COST_MAP_URL"] = "http://127.0.0.1:9/model_prices_and_context_window.json"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                         timeout=180, check=True).stdout.strip().splitlines()[-1]
    result = json.loads(out)
    assert result == {"source": "local", "luna": "openai", "luna_price": 1.2e-06, "gemini": "gemini"}
