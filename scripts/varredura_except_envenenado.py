"""Varredura da classe "except que escreve em sessão possivelmente abortada".

Por que existe
--------------
A Frente K achou UM caso: o `except` da consolidação lia `current_user.
tenant_id` numa sessão que o `DataError` já havia abortado, e morria de
`PendingRollbackError` antes de registrar a auditoria. Um caso achado por
leitura não diz nada sobre os outros. Este script procura a CLASSE.

Ele nasceu como script de sessão e a auditoria de 12/09 reprovou isso com
razão: "afirmação de varredura sistemática sem instrumento na árvore não é
reproduzível". Está aqui para ser rodado, contestado e melhorado.

    python scripts/varredura_except_envenenado.py            # tabela
    python scripts/varredura_except_envenenado.py --json     # para diff

O QUE ELE PROCURA (duas regras, explícitas)
-------------------------------------------
R1 — socorro que grava na sessão que caiu.
    Um `try` que toca a sessão (`db.flush/commit/add/query/execute/...`, ou uma
    função que RECEBE `db` como argumento — o caso transitivo) cujo `except`
    escreve no ORM (`db.flush/commit/add`, ou atribuição a atributo) sem
    `rollback()` antes. É o desenho exato do caso da Frente K.

R2 — erro de banco engolido, sessão devolvida ao chamador.
    Uma função que RECEBE `db`/`session`, cujo `try` toca a sessão e cujo
    `except` NÃO re-levanta, NÃO faz rollback e devolve o controle. Quem chamou
    segue com uma sessão que pode estar abortada e só descobre no commit
    seguinte — longe da causa. Foi assim que `_preferencias_ia` (audio_tasks)
    apareceu, e essa regra não existia na primeira passagem da frente.

O QUE ELE NÃO COBRE — a fronteira, dita em voz alta
---------------------------------------------------
* Só enxerga UM arquivo por vez: não segue a cadeia de chamadas. Um `try` que
  chama `servico(x)` sem passar `db` mas cujo serviço abre a própria sessão
  passa despercebido.
* Não avalia decorators, context managers próprios nem hooks do Celery.
* Não distingue erro de banco de erro de rede dentro do `try`: sinaliza o
  desenho, e o julgamento de cada achado continua sendo humano — foi assim que
  cinco dos dez candidatos da Frente L foram descartados (render de PDF, fila
  Celery, Redis, download de storage ×2).
* `rollback()` em QUALQUER lugar do `except` já conta como tratado, mesmo se
  vier depois da escrita. Aceitável porque a escrita seguinte reaproveitaria a
  sessão saneada; imperfeito se houver dois blocos aninhados.
* `begin_nested()` NÃO conta como tratamento, e isso foi medido, não suposto
  (12/09, Postgres de dev): depois de um flush falho dentro do savepoint a
  sessão continua exigindo `rollback()` — `no_autoflush` e `expire` não
  recuperam. Uma versão anterior deste script isentava o `try` que usasse
  savepoint, e isso teria escondido o próprio defeito que a Frente L tinha
  acabado de introduzir em `legislation_service`.

Portanto: **isto reduz o espaço de busca e torna o resultado reproduzível; não
prova ausência.** Achado novo desta classe é bem-vindo e provavelmente existe.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ALVO = RAIZ / "app"

# Métodos de sessão que ESCREVEM (flush pode falhar e abortar a transação).
ESCRITAS = {"flush", "commit", "add", "add_all", "delete", "merge"}
# Métodos que só tocam a sessão — um erro neles também aborta a transação.
TOQUES = ESCRITAS | {"execute", "query", "scalar", "scalars", "get", "refresh"}


def _e_sessao(expr: str) -> bool:
    return expr == "db" or expr.endswith(".db") or "session" in expr.lower()


def _toca_sessao(no: ast.AST) -> list[str]:
    """Chamadas que tocam a sessão, incluindo o caso transitivo."""
    achados: list[str] = []
    for n in ast.walk(no):
        if not isinstance(n, ast.Call):
            continue
        if (isinstance(n.func, ast.Attribute) and n.func.attr in TOQUES
                and _e_sessao(ast.unparse(n.func.value))):
            achados.append(f"db.{n.func.attr}")
        for arg in list(n.args) + [k.value for k in n.keywords]:
            if isinstance(arg, ast.Name) and arg.id in ("db", "session"):
                achados.append(f"{ast.unparse(n.func)}(db)")
    return sorted(set(achados))


def _tem_rollback(no: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "rollback"
        for n in ast.walk(no)
    )


def _escreve_no_orm(no: ast.AST) -> bool:
    for n in ast.walk(no):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ESCRITAS and _e_sessao(ast.unparse(n.func.value))):
            return True
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Attribute) for t in n.targets):
            return True
        if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Attribute):
            return True
    return False


def _relevanta(handler: ast.ExceptHandler) -> bool:
    """O handler devolve o erro a quem chamou (raise nu, raise x, ou retry)?"""
    return any(isinstance(n, ast.Raise) for n in ast.walk(handler))


def _funcoes_com_sessao(arvore: ast.AST) -> dict[int, str]:
    """Linha inicial -> nome, para funções que RECEBEM db/session."""
    saida: dict[int, str] = {}
    for n in ast.walk(arvore):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nomes = {a.arg for a in n.args.args} | {a.arg for a in n.args.kwonlyargs}
            if nomes & {"db", "session"}:
                saida[n.lineno] = n.name
    return saida


def varrer() -> list[dict]:
    achados: list[dict] = []
    for arquivo in sorted(ALVO.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8-sig"))
        except SyntaxError as exc:
            print(f"AVISO: {arquivo} não parseia ({exc})", file=sys.stderr)
            continue

        recebem_sessao = _funcoes_com_sessao(arvore)
        escopos: list[tuple[int, int, str]] = []
        for n in ast.walk(arvore):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno in recebem_sessao:
                fim = max((getattr(x, "lineno", n.lineno) for x in ast.walk(n)), default=n.lineno)
                escopos.append((n.lineno, fim, n.name))

        for n in ast.walk(arvore):
            if not isinstance(n, ast.Try):
                continue
            corpo = ast.Module(body=n.body, type_ignores=[])
            toques = _toca_sessao(corpo)
            if not toques:
                continue
            for h in n.handlers:
                handler = ast.Module(body=h.body, type_ignores=[])
                if _tem_rollback(handler):
                    continue

                rel = str(arquivo.relative_to(RAIZ)).replace("\\", "/")
                if _escreve_no_orm(handler):
                    achados.append({
                        "regra": "R1",
                        "arquivo": rel, "linha_except": h.lineno, "linha_try": n.lineno,
                        "try_toca": toques[:3],
                        "detalhe": "except escreve no ORM sem rollback e sem savepoint",
                    })
                    continue

                if not _relevanta(h):
                    dentro = next(
                        (nome for ini, fim, nome in escopos if ini <= h.lineno <= fim), None
                    )
                    if dentro:
                        achados.append({
                            "regra": "R2",
                            "arquivo": rel, "linha_except": h.lineno, "linha_try": n.lineno,
                            "try_toca": toques[:3],
                            "detalhe": f"`{dentro}` recebe a sessão, engole o erro e devolve "
                                       "o controle sem rollback",
                        })
    return achados


def main() -> int:
    ap = argparse.ArgumentParser(description="Varredura da classe do except envenenado")
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    args = ap.parse_args()

    achados = varrer()
    if args.json:
        print(json.dumps(achados, ensure_ascii=False, indent=1))
        return 0

    print(f"{len(achados)} candidato(s) — julgamento humano obrigatório em cada um\n")
    for a in achados:
        print(f"[{a['regra']}] {a['arquivo']}:{a['linha_except']}  (try@{a['linha_try']})")
        print(f"      try toca: {a['try_toca']}")
        print(f"      {a['detalhe']}\n")
    if not achados:
        print("Nenhum candidato. Isso NÃO é prova de ausência — leia a fronteira\n"
              "declarada no topo deste arquivo antes de concluir qualquer coisa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
