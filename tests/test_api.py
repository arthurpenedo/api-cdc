import json

import pytest
from fastapi.testclient import TestClient

from api_cdc.app import app, create_app
from api_cdc.busca import BM25, Article, load_articles, tokenize
from api_cdc.busca import DATA as ARTIGOS

PERGUNTAS = ARTIGOS.parent / "perguntas_avaliacao.jsonl"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_saude(client):
    r = client.get("/saude")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["status"] == "ok" and corpo["artigos"] > 100


def test_buscar_arrependimento_acha_art_49(client):
    r = client.get("/buscar", params={"q": "desistir de compra feita pela internet", "k": 3})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total"] == len(corpo["resultados"]) <= 3
    assert "49" in [x["artigo"] for x in corpo["resultados"]]
    notas = [x["nota"] for x in corpo["resultados"]]
    assert notas == sorted(notas, reverse=True)


def test_buscar_valida_parametros(client):
    assert client.get("/buscar").status_code == 422
    assert client.get("/buscar", params={"q": "x"}).status_code == 422
    assert client.get("/buscar", params={"q": "boleto indevido", "k": 0}).status_code == 422
    assert client.get("/buscar", params={"q": "boleto indevido", "k": 21}).status_code == 422


def test_buscar_sem_resultado_devolve_lista_vazia(client):
    r = client.get("/buscar", params={"q": "zzzqqq xyzxyz"})
    assert r.status_code == 200 and r.json() == {"pergunta": "zzzqqq xyzxyz", "total": 0, "resultados": []}


def test_artigo_existente_e_inexistente(client):
    r = client.get("/artigos/49")
    assert r.status_code == 200 and r.json()["titulo"] == "Art. 49"
    r = client.get("/artigos/99999")
    assert r.status_code == 404 and "99999" in r.json()["detail"]


def test_openapi_documenta_as_rotas(client):
    spec = client.get("/openapi.json").json()
    assert {"/saude", "/buscar", "/artigos/{numero}"} <= set(spec["paths"])
    assert spec["info"]["title"] == "api-cdc"


def test_create_app_com_artigos_proprios():
    artigos = [Article("1", "Consumidor tem direito a troca do produto com defeito."),
               Article("2", "Fornecedor responde pelo vício do serviço prestado.")]
    c = TestClient(create_app(artigos))
    assert c.get("/saude").json()["artigos"] == 2
    topo = c.get("/buscar", params={"q": "troca de produto com defeito"}).json()["resultados"][0]
    assert topo["artigo"] == "1"


def test_tokenize_remove_acento_stopword_e_plural():
    assert tokenize("As Cobranças indevidas") == ["cobranca", "indevida"]


def test_bm25_acerta_pelo_menos_metade_das_perguntas_no_top3():
    """Trava de regressão: no cdc-rag o BM25 faz 56,9% de hit@3; aqui exigimos >= 50%."""
    indice = BM25(load_articles())
    perguntas = [json.loads(linha) for linha in PERGUNTAS.read_text(encoding="utf-8").splitlines() if linha.strip()]
    acertos = sum(
        any(h.article.artigo in p["artigos"] for h in indice.search(p["pergunta"], k=3))
        for p in perguntas
    )
    assert acertos / len(perguntas) >= 0.5
