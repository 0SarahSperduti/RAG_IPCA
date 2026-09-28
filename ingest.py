"""
Ingestão do RAG: coleta as fontes oficiais, quebra em chunks, gera embeddings
locais e persiste o índice vetorial em vector_db/.

Rodar antes do chatbot:
    python3 ingest.py

Não usa nenhum serviço de IA na nuvem: os embeddings são gerados localmente pelo
modelo ONNX (all-MiniLM-L6-v2) que acompanha o ChromaDB.
"""

from __future__ import annotations

from pathlib import Path

import chromadb

import ipca_fontes as fontes

DB_DIR = "vector_db"
COLECAO = "ipca_oficial"

TAMANHO_CHUNK = 1000
SOBREPOSICAO = 200

# Janelas usadas em reajuste de locação (Lei 8.245/91: reajuste no mínimo anual).
JANELAS_REAJUSTE = [6, 12, 24, 36]


def dividir_em_chunks(
    texto: str, tamanho: int = TAMANHO_CHUNK, sobreposicao: int = SOBREPOSICAO
) -> list[str]:
    """Janela deslizante com sobreposição, para não separar um número do seu contexto."""
    passo = max(1, tamanho - sobreposicao)
    pedacos = [texto[i : i + tamanho].strip() for i in range(0, len(texto), passo)]
    return [p for p in pedacos if len(p) > 80]


def documentos_da_serie(serie: list[dict]) -> list[dict]:
    """Transforma a série numérica do SIDRA em texto recuperável pelo RAG."""
    documentos = []

    for mes in serie:
        partes = [f"IPCA de {mes['mes']}, segundo o IBGE (tabela SIDRA 1737)."]
        if mes.get("mensal") is not None:
            partes.append(f"Variação mensal: {mes['mensal']:.2f}%.")
        if mes.get("no_ano") is not None:
            partes.append(f"Variação acumulada no ano: {mes['no_ano']:.2f}%.")
        if mes.get("em_12_meses") is not None:
            partes.append(
                f"Variação acumulada em 12 meses: {mes['em_12_meses']:.2f}%. "
                f"Um contrato de aluguel indexado ao IPCA com aniversário em {mes['mes']} "
                f"seria reajustado em {mes['em_12_meses']:.2f}%."
            )

        documentos.append(
            {
                "id": f"sidra-{mes['codigo']}",
                "texto": " ".join(partes),
                "fonte": "IBGE — API SIDRA, tabela 1737",
                "url": fontes.SIDRA_URL,
                "tipo": "serie_oficial",
            }
        )

    ultimo = serie[-1]
    linhas = [
        "Resumo oficial do IPCA para reajuste de contratos de locação (fonte: IBGE/SIDRA tabela 1737).",
        f"Mês de referência mais recente divulgado: {ultimo['mes']}.",
    ]
    for janela in JANELAS_REAJUSTE:
        calculo = fontes.calcular_reajuste(1000.0, janela, serie)
        linhas.append(
            f"IPCA acumulado nos últimos {calculo['meses_considerados']} meses "
            f"({calculo['periodo_inicio']} a {calculo['periodo_fim']}): {calculo['percentual']:.2f}%. "
            f"Um aluguel de R$ 1.000,00 passaria a R$ {calculo['valor_reajustado']:.2f}."
        )
    linhas.append(
        "O acumulado é composto: multiplicam-se os fatores (1 + variação mensal / 100) de cada mês, "
        "nunca se somam os percentuais."
    )

    documentos.append(
        {
            "id": "sidra-resumo-reajuste",
            "texto": " ".join(linhas),
            "fonte": "IBGE — API SIDRA, tabela 1737",
            "url": fontes.SIDRA_URL,
            "tipo": "resumo_reajuste",
        }
    )

    tabela = "; ".join(
        f"{m['mes']}: {m['mensal']:.2f}%" for m in serie[-12:] if m.get("mensal") is not None
    )
    documentos.append(
        {
            "id": "sidra-ultimos-12",
            "texto": f"Variação mensal do IPCA nos últimos 12 meses divulgados (IBGE): {tabela}.",
            "fonte": "IBGE — API SIDRA, tabela 1737",
            "url": fontes.SIDRA_URL,
            "tipo": "serie_oficial",
        }
    )

    return documentos


def documentos_das_projecoes(projecoes: dict, combinada: list[dict]) -> list[dict]:
    """Projeções oficiais do Focus/BCB viram texto recuperável pelo RAG."""
    pesquisa = projecoes["data_pesquisa"]
    documentos = []

    anuais = "; ".join(f"{a['ano']}: {a['mediana']:.2f}%" for a in projecoes["anuais"])
    documentos.append(
        {
            "id": "focus-anuais",
            "texto": (
                f"Projeção oficial do IPCA — mediana das expectativas de mercado da pesquisa "
                f"Focus do Banco Central do Brasil, divulgada em {pesquisa}. "
                f"IPCA projetado por ano: {anuais}. "
                "É a projeção de referência usada pelo mercado e pela política monetária."
            ),
            "fonte": "Banco Central — Expectativas de Mercado (Focus)",
            "url": fontes.FOCUS_ANUAL_URL,
            "tipo": "projecao",
        }
    )

    mensais = "; ".join(
        f"{m['mes']}: {m['mediana']:.2f}%" for m in projecoes["mensais"][:18]
    )
    documentos.append(
        {
            "id": "focus-mensais",
            "texto": (
                f"Projeção mensal do IPCA (mediana Focus/BCB, pesquisa de {pesquisa}): {mensais}."
            ),
            "fonte": "Banco Central — Expectativas de Mercado (Focus)",
            "url": fontes.FOCUS_MENSAL_URL,
            "tipo": "projecao",
        }
    )

    # Reajuste estimado para contratos que fazem aniversário em meses futuros.
    for ponto in [p for p in combinada if p["tipo"] == "projetado"][:18]:
        if ponto["acumulado_12m"] is None:
            continue
        documentos.append(
            {
                "id": f"focus-reajuste-{ponto['codigo']}",
                "texto": (
                    f"Reajuste estimado para contrato de aluguel indexado ao IPCA com "
                    f"aniversário em {ponto['mes']}: {ponto['acumulado_12m']:.2f}% "
                    f"(acumulado de 12 meses combinando o IPCA já divulgado pelo IBGE com a "
                    f"projeção Focus/BCB de {pesquisa}). Estimativa, não valor oficial fechado."
                ),
                "fonte": "Banco Central (Focus) + IBGE/SIDRA",
                "url": fontes.FOCUS_MENSAL_URL,
                "tipo": "projecao",
            }
        )

    return documentos


def documentos_das_paginas(paginas: list[dict]) -> list[dict]:
    documentos = []
    for pagina in paginas:
        for indice, chunk in enumerate(dividir_em_chunks(pagina["texto"])):
            documentos.append(
                {
                    "id": f"web-{abs(hash(pagina['url']))}-{indice}",
                    "texto": chunk,
                    "fonte": pagina["titulo"],
                    "url": pagina["url"],
                    "tipo": "pagina_oficial",
                }
            )
    return documentos


def indexar(documentos: list[dict]) -> None:
    cliente = chromadb.PersistentClient(path=DB_DIR)
    if COLECAO in [c.name for c in cliente.list_collections()]:
        cliente.delete_collection(COLECAO)

    colecao = cliente.create_collection(COLECAO, metadata={"hnsw:space": "cosine"})

    lote = 100
    for inicio in range(0, len(documentos), lote):
        fatia = documentos[inicio : inicio + lote]
        colecao.add(
            ids=[d["id"] for d in fatia],
            documents=[d["texto"] for d in fatia],
            metadatas=[{"fonte": d["fonte"], "url": d["url"], "tipo": d["tipo"]} for d in fatia],
        )
        print(f"  indexados {min(inicio + lote, len(documentos))}/{len(documentos)}")


def main() -> None:
    print("1/5 Coletando a série oficial do IPCA (IBGE/SIDRA)...")
    serie = fontes.coletar_serie_ipca()
    print(f"  {len(serie)} meses, até {serie[-1]['mes']}")

    print("2/5 Coletando as projeções oficiais (Focus / Banco Central)...")
    projecoes = fontes.coletar_projecoes_focus()
    combinada = fontes.serie_combinada(serie, projecoes)
    print(f"  pesquisa de {projecoes['data_pesquisa']}, {len(projecoes['mensais'])} meses projetados")

    print("3/5 Coletando as páginas oficiais (IBGE e FGV IBRE)...")
    paginas = fontes.coletar_paginas_oficiais()

    print("4/5 Montando os documentos e quebrando em chunks...")
    documentos = (
        documentos_da_serie(serie)
        + documentos_das_projecoes(projecoes, combinada)
        + documentos_das_paginas(paginas)
    )
    print(f"  {len(documentos)} documentos")

    print("5/5 Gerando embeddings locais e gravando o índice vetorial...")
    indexar(documentos)

    print(f"\nPronto. Índice salvo em {Path(DB_DIR).resolve()}")
    print("Agora rode:  python3 -m streamlit run app.py")


if __name__ == "__main__":
    main()
