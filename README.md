# api-cdc

[![CI](https://github.com/arthurpenedo/api-cdc/actions/workflows/ci.yml/badge.svg)](https://github.com/arthurpenedo/api-cdc/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> **API REST de busca no Código de Defesa do Consumidor**, feita com FastAPI, empacotada em Docker e publicada como imagem no GitHub Container Registry. Sem chave de API, sem modelo, sem custo.

## O problema

O [cdc-rag](https://github.com/arthurpenedo/cdc-rag) acha o artigo certo do CDC para uma pergunta em linguagem de consumidor, mas só roda como linha de comando. Para um site, um bot de atendimento ou outro sistema usar essa busca, ela precisa virar um **serviço HTTP** que qualquer um sobe com um comando.

## O que faz

| Rota | O que devolve |
|---|---|
| `GET /buscar?q=...&k=3` | os `k` artigos mais relevantes, com a nota BM25 (`k` de 1 a 20) |
| `GET /artigos/{numero}` | o texto de um artigo (404 se não existir); aceita `49`, `art. 49`, `49º` e `54a` (= `54-A`) |
| `GET /saude` | `{"status": "ok", "versao": ..., "artigos": N}` (usada pelo `HEALTHCHECK` do Docker) |
| `GET /docs` · `GET /openapi.json` | documentação interativa e contrato OpenAPI, gerados do código |

Parâmetros são validados pelo FastAPI/Pydantic: pergunta curta demais ou `k` fora da faixa devolve `422` com o motivo.

```bash
$ curl "http://localhost:8000/buscar?q=desistir+de+compra+pela+internet&k=2"
{"pergunta":"desistir de compra pela internet","total":2,"resultados":[{"artigo":"49", ... ,"nota":...}, ...]}
```

## Como rodar

```bash
# local
pip install -e ".[dev]"
uvicorn api_cdc.app:app --reload      # http://127.0.0.1:8000/docs

# Docker
docker build -t api-cdc .
docker run -p 8000:8000 api-cdc

# imagem pronta, publicada pelo workflow (depois do primeiro push na main)
docker run -p 8000:8000 ghcr.io/arthurpenedo/api-cdc:latest
```

## Números medidos

Medidos em 20/10/2026 com `python scripts/medir.py` (Windows, Python 3.13, FastAPI `TestClient`, 58 perguntas de consumidor):

- **Tempo de resposta de `/buscar`:** mediana **4,1 ms**, p95 4,8 ms, máximo 5,7 ms (inclui roteamento, validação e JSON do FastAPI; **não** inclui rede).
- **Qualidade da busca:** hit@3 de **56,9%**, igual ao BM25 do cdc-rag (a mesma implementação e as mesmas 58 perguntas). Há um teste que falha se cair abaixo de 50%.
- **Tamanho da imagem Docker:** **136 MB**, lido no log do job `docker` do [`ci.yml`](.github/workflows/ci.yml) (`docker images`, execução de 02/11/2026). O mesmo job testa `/saude` e `/buscar` dentro do contêiner.
- **Testes:** 9 testes (`pytest`), mais `ruff` no CI.

## Arquitetura

```
src/api_cdc/busca.py   BM25 do zero (só biblioteca padrão) sobre data/cdc_artigos.jsonl
src/api_cdc/app.py     create_app(): rotas, modelos Pydantic de resposta, OpenAPI
Dockerfile             python:3.13-slim, usuário sem privilégio, HEALTHCHECK em /saude
.github/workflows/     ci.yml (ruff, pytest, medição, build e teste da imagem)
                       imagem.yml (publica em ghcr.io/<dono>/api-cdc com GITHUB_TOKEN)
```

Decisões:
- **Só BM25 na API.** A busca por embeddings do cdc-rag melhora o hit@3 (63,8% na híbrida), mas traz numpy e um modelo na imagem. Aqui o foco é servir; a imagem fica pequena e sobe em instantes.
- **`create_app()` em vez de variável global só.** Os testes montam a API com artigos próprios, sem depender do texto da lei.
- **Imagem com usuário comum** (não root) e `HEALTHCHECK`.

## Limites honestos

- A busca é por palavra: não entende sinônimos ("nome sujo" não acha "cadastro de inadimplentes" sozinho). Por isso o hit@3 é 56,9%.
- Sem autenticação, limite de requisições nem cache: é um serviço de demonstração.
- Devolve o texto da lei, não aconselhamento jurídico.

## Licença

MIT. O texto do CDC (Lei 8.078/1990) é público.
