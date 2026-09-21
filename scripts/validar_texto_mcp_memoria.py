"""Recorte sobre texto MCP em memória; não substitui extração ou gate autenticado.

Recebe blocos por HTTP somente em loopback. Não grava payload, log ou fixture.
Confere hash/contagem e chama a taxonomia da worktree sobre cada texto integral.
"""
import hashlib
import json
import re
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.services.taxonomia_documental import propor_especie
from app.schemas.entrada_semantica import FalecimentoDeclarado
from app.services.identidade_observacao import localizar_trecho
from app.services.motor_cartorario import qualificar_representacao


def recorte(texto, especie):
    """Checks on actual text, using application schemas; no mocked LLM output."""
    result = {}
    if especie == "certidao_matricula":
        # CNM separates registry identity from the registration number.
        cnm = re.search(r"(\d{6})\.2\.(\d{7})-\d{2}", texto)
        result["identidade_numero_serventia"] = [cnm[1], str(int(cnm[2]))] if cnm else None
    if especie == "comprovante_situacao_cadastral_cpf":
        ano = re.search(r"Ano de [óo]bito:\s*(\d{4})", texto, re.I)
        consulta = re.search(r"Comprovante emitido.*?dia (\d{2})/(\d{2})/(\d{4})", texto)
        declaracao = FalecimentoDeclarado(sujeito="pessoa_documentada", ano=int(ano[1]) if ano else None,
            data_consulta=date(int(consulta[3]), int(consulta[2]), int(consulta[1])) if consulta else None,
            trecho=texto, posicao_inicio=0)
        localizar_trecho(texto, declaracao.trecho, declaracao.posicao_inicio)
        result["schema_falecimento_ano_e_consulta"] = declaracao.ano is not None and declaracao.data_consulta is not None
        result["data_exata_nao_inferida"] = declaracao.data is None
    if especie == "contrato_servico_documental":
        result["espolio_e_inventariante_expressos"] = bool(re.search(r"esp[óo]lio", texto, re.I) and re.search(r"inventariante", texto, re.I))
        result["referencia_judicial_literal"] = bool(re.search(r"\d{7}-\s*\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", texto))
        result["representacao"] = qualificar_representacao(especie=especie, alcance=None,
            inicio=None, fim=None, representado="espolio_documentado", data_referencia=None)
    return result


class Receiver(BaseHTTPRequestHandler):
    buffers = {}

    def log_message(self, *_args):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        key = payload["id"]
        if payload.get("first"):
            self.buffers[key] = []
        self.buffers.setdefault(key, []).append(payload["text"])
        result = {"id": key, "buffered": True}
        if payload.get("last"):
            texto = "".join(self.buffers.pop(key))
            digest = hashlib.sha256(texto.encode("utf-8")).hexdigest()
            if digest != payload["sha256"]:
                self.send_error(422, "Hash mismatch")
                return
            result = {"id": key, "sha256": digest, "chars": len(texto),
                      "bytes": len(texto.encode("utf-8")),
                      "especie": str(propor_especie(texto, payload["document_type"]))}
            result["recorte"] = recorte(texto, result["especie"])
        data = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 0), Receiver)
    print(json.dumps({"port": server.server_port, "storage": "memory_only"}), flush=True)
    server.serve_forever()
