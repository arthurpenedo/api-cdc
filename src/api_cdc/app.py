"""API REST de busca no Código de Defesa do Consumidor (FastAPI).

Rotas:
- GET /saude            : verificação de saúde (usada pelo HEALTHCHECK do Docker);
- GET /buscar?q=&k=     : artigos mais relevantes para a pergunta, com a nota BM25;
- GET /artigos/{numero} : texto de um artigo pelo número.

A documentação interativa (OpenAPI) sai sozinha em /docs e o JSON em /openapi.json.
"""

import re

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from . import __version__
from .busca import BM25, Article, load_articles

DESCRICAO = (
    "Busca por palavra (BM25) nos artigos do Código de Defesa do Consumidor "
    "(Lei 8.078/1990). Sem chave de API, sem modelo, sem custo."
)


def normalizar_numero(numero: str) -> str:
    """Aceita como o consumidor escreve ('art. 49', '49º', '54a', '54 - b') e devolve o formato do corpus ('49', '54-A')."""
    limpo = re.sub(r"^\s*art(igo)?\.?\s*", "", numero.strip(), flags=re.IGNORECASE)
    m = re.fullmatch(r"(\d+)\s*[ºo°.]?\s*-?\s*([a-zA-Z])?", limpo)
    if not m:
        return numero.strip()
    return m.group(1) + (f"-{m.group(2).upper()}" if m.group(2) else "")


class ArtigoOut(BaseModel):
    artigo: str = Field(description="Número do artigo, como '49' ou '6'.", examples=["49"])
    titulo: str = Field(examples=["Art. 49"])
    texto: str


class ResultadoOut(ArtigoOut):
    nota: float = Field(description="Nota BM25: maior é mais relevante.")


class BuscaOut(BaseModel):
    pergunta: str
    total: int
    resultados: list[ResultadoOut]


class SaudeOut(BaseModel):
    status: str = "ok"
    versao: str
    artigos: int


def create_app(articles: list[Article] | None = None) -> FastAPI:
    """Fábrica da aplicação; os testes passam artigos próprios."""
    artigos = articles if articles is not None else load_articles()
    indice = BM25(artigos)
    por_numero = {a.artigo: a for a in artigos}

    app = FastAPI(title="api-cdc", version=__version__, description=DESCRICAO)

    @app.get("/saude", response_model=SaudeOut, tags=["infra"])
    def saude() -> SaudeOut:
        return SaudeOut(versao=__version__, artigos=len(artigos))

    @app.get("/buscar", response_model=BuscaOut, tags=["busca"])
    def buscar(
        q: str = Query(min_length=2, max_length=300, description="Pergunta em linguagem natural."),
        k: int = Query(5, ge=1, le=20, description="Quantos artigos devolver."),
    ) -> BuscaOut:
        hits = indice.search(q, k=k)
        resultados = [ResultadoOut(artigo=h.article.artigo, titulo=f"Art. {h.article.artigo}",
                                   texto=h.article.texto, nota=h.score) for h in hits]
        return BuscaOut(pergunta=q, total=len(resultados), resultados=resultados)

    @app.get("/artigos/{numero}", response_model=ArtigoOut, tags=["busca"])
    def artigo(numero: str) -> ArtigoOut:
        a = por_numero.get(normalizar_numero(numero))
        if a is None:
            raise HTTPException(status_code=404, detail=f"Artigo {numero} não encontrado")
        return ArtigoOut(artigo=a.artigo, titulo=f"Art. {a.artigo}", texto=a.texto)

    return app


app = create_app()
