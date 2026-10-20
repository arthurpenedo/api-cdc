"""Mede a API em processo (TestClient): tempo de resposta de /buscar e hit@3 nas 58 perguntas.

Uso: python scripts/medir.py
O tempo inclui a camada HTTP do FastAPI (roteamento, validação, JSON), mas não a rede.
"""

import json
import statistics
import time

from fastapi.testclient import TestClient

from api_cdc.app import app
from api_cdc.busca import DATA

PERGUNTAS = DATA.parent / "perguntas_avaliacao.jsonl"


def main() -> None:
    client = TestClient(app)
    perguntas = [json.loads(linha) for linha in PERGUNTAS.read_text(encoding="utf-8").splitlines() if linha.strip()]
    client.get("/saude")  # aquece
    tempos, acertos = [], 0
    for p in perguntas:
        t0 = time.perf_counter()
        r = client.get("/buscar", params={"q": p["pergunta"], "k": 3})
        tempos.append((time.perf_counter() - t0) * 1000)
        acertos += any(x["artigo"] in p["artigos"] for x in r.json()["resultados"])
    tempos.sort()
    print(f"perguntas: {len(perguntas)}")
    print(f"hit@3: {acertos / len(perguntas):.1%}")
    print(f"tempo /buscar: mediana {statistics.median(tempos):.1f} ms, "
          f"p95 {tempos[int(len(tempos) * 0.95) - 1]:.1f} ms, máx {tempos[-1]:.1f} ms")


if __name__ == "__main__":
    main()
