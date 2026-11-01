import json

import pytest
from fastapi.testclient import TestClient

from api_cdc.app import app, create_app, normalizar_numero
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


@pytest.mark.parametrize("escrito, esperado", [
    ("49", "49"), ("art. 49", "49"), ("Artigo 49", "49"), ("49º", "49"), ("54a", "54-A"),
    ("54 - b", "54-B"), ("104-C", "104-C"), ("abc", "abc"),
])
def test_normalizar_numero(escrito, esperado):
    assert normalizar_numero(escrito) == esperado


def test_artigo_aceita_numero_como_o_consumidor_escreve(client):
    assert client.get("/artigos/49º").json()["artigo"] == "49"
    assert client.get("/artigos/54a").json()["artigo"] == "54-A"
    assert client.get("/artigos/abc").status_code == 404


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


def test_load_articles_ignora_linhas_em_branco(tmp_path):
    arq = tmp_path / "a.jsonl"
    arq.write_text('{"artigo": "1", "texto": "Um."}\n\n   \n{"artigo": "2", "texto": "Dois."}\n', encoding="utf-8")
    assert [a.artigo for a in load_articles(arq)] == ["1", "2"]


def test_stem_nao_corta_palavra_curta_e_troca_sufixo():
    assert tokenize("mes") == ["mes"]
    assert tokenize("obrigações") == ["obrigacao"]


def test_bm25_respeita_k_e_nao_devolve_nota_zero():
    artigos = [Article(str(i), f"produto com defeito numero{i}") for i in range(6)] + [Article("x", "outro assunto")]
    indice = BM25(artigos)
    hits = indice.search("produto defeito", k=2)
    assert len(hits) == 2
    todos = indice.search("produto defeito", k=20)
    assert "x" not in [h.article.artigo for h in todos] and all(h.score > 0 for h in todos)


def test_bm25_acerta_pelo_menos_metade_das_perguntas_no_top3():
    """Trava de regressão: no cdc-rag o BM25 faz 56,9% de hit@3; aqui exigimos >= 50%."""
    indice = BM25(load_articles())
    perguntas = [json.loads(linha) for linha in PERGUNTAS.read_text(encoding="utf-8").splitlines() if linha.strip()]
    acertos = sum(
        any(h.article.artigo in p["artigos"] for h in indice.search(p["pergunta"], k=3))
        for p in perguntas
    )
    assert acertos / len(perguntas) >= 0.5
