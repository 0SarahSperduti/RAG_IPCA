"""
Camada de coleta de dados oficiais sobre o IPCA.

Fontes (todas públicas e oficiais, conforme a regulamentação brasileira):
  - IBGE / SIDRA, tabela 1737 — série histórica oficial do IPCA (API pública).
  - IBGE — página oficial do Índice Nacional de Preços ao Consumidor Amplo.
  - FGV IBRE — índices de preços, Monitor da Inflação, Boletim Macro (projeções),
    expectativa de inflação dos consumidores e IVAR (aluguéis residenciais).

Este módulo NÃO usa nenhum serviço de IA. Ele só busca, normaliza e calcula.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import certifi
import requests
from bs4 import BeautifulSoup

# Tabela 1737 do SIDRA: variação mensal (63), acumulada no ano (69) e em 12 meses (2265).
SIDRA_URL = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/63,69,2265/p/last%2048"

IBGE_IPCA_URL = (
    "https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/"
    "9256-indice-nacional-de-precos-ao-consumidor-amplo.html"
)

# Expectativas de Mercado (pesquisa Focus) do Banco Central: a projeção oficial de IPCA.
# baseCalculo=0 usa as respostas dos últimos 30 dias.
FOCUS_BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
FOCUS_MENSAL_URL = (
    FOCUS_BASE + "ExpectativaMercadoMensais?$top=500&$format=json"
    "&$filter=Indicador%20eq%20'IPCA'%20and%20baseCalculo%20eq%200"
    "&$orderby=Data%20desc"
)
FOCUS_ANUAL_URL = (
    FOCUS_BASE + "ExpectativasMercadoAnuais?$top=100&$format=json"
    "&$filter=Indicador%20eq%20'IPCA'%20and%20baseCalculo%20eq%200"
    "&$orderby=Data%20desc"
)

FONTES_WEB = [
    ("IBGE — Índice Nacional de Preços ao Consumidor Amplo (IPCA)", IBGE_IPCA_URL),
    ("FGV IBRE — Índices de Preços", "https://portalibre.fgv.br/indices-de-precos"),
    ("FGV IBRE — Monitor da Inflação", "https://portalibre.fgv.br/monitor-da-inflacao"),
    ("FGV IBRE — Boletim Macro (projeções)", "https://portalibre.fgv.br/boletim-macro"),
    (
        "FGV IBRE — Indicador de Expectativa de Inflação dos Consumidores",
        "https://portalibre.fgv.br/indicador-de-expectativa-de-inflacao-dos-consumidores",
    ),
    (
        "FGV IBRE — IVAR, Índice de Variação de Aluguéis Residenciais",
        "https://portalibre.fgv.br/indice-de-variacao-de-alugueis-residenciais",
    ),
]

USER_AGENT = "Mozilla/5.0 (compatible; RAG-IPCA/1.0; projeto academico)"

VARIAVEIS = {
    "IPCA - Variação mensal": "mensal",
    "IPCA - Variação acumulada no ano": "no_ano",
    "IPCA - Variação acumulada em 12 meses": "em_12_meses",
}


def preparar_ca_bundle() -> None:
    """Em rede corporativa com inspeção SSL, junta o certifi às raízes do keychain do macOS."""
    if sys.platform != "darwin" or os.environ.get("REQUESTS_CA_BUNDLE"):
        return

    bundle = Path(tempfile.gettempdir()) / "ipca_ca_bundle.pem"
    if not bundle.exists():
        partes = [Path(certifi.where()).read_text(encoding="utf-8")]
        for keychain in (
            "/System/Library/Keychains/SystemRootCertificates.keychain",
            "/Library/Keychains/System.keychain",
        ):
            resultado = subprocess.run(
                ["security", "find-certificate", "-a", "-p", keychain],
                capture_output=True,
                text=True,
                check=False,
            )
            partes.append(resultado.stdout)
        bundle.write_text("\n".join(partes), encoding="utf-8")

    os.environ["REQUESTS_CA_BUNDLE"] = str(bundle)
    os.environ["SSL_CERT_FILE"] = str(bundle)
    os.environ["CURL_CA_BUNDLE"] = str(bundle)


def _buscar(url: str) -> requests.Response:
    preparar_ca_bundle()
    resposta = requests.get(url, timeout=45, headers={"User-Agent": USER_AGENT})
    resposta.raise_for_status()
    return resposta


def coletar_serie_ipca() -> list[dict]:
    """
    Série oficial do IPCA na API do SIDRA/IBGE, um registro por mês, em ordem cronológica.

    Cada item: {"mes", "codigo", "mensal", "no_ano", "em_12_meses"} com valores em %.
    """
    payload = _buscar(SIDRA_URL).json()
    if not payload or len(payload) < 2:
        raise RuntimeError("A API do SIDRA/IBGE retornou uma resposta vazia.")

    meses: dict[str, dict] = {}
    for item in payload[1:]:  # a primeira linha é o cabeçalho descritivo
        campo = VARIAVEIS.get(item.get("D2N"))
        codigo = item.get("D3C")
        if not campo or not codigo:
            continue

        registro = meses.setdefault(codigo, {"codigo": codigo, "mes": item.get("D3N")})
        try:
            registro[campo] = float(item.get("V"))
        except (TypeError, ValueError):
            registro[campo] = None

    return [meses[c] for c in sorted(meses)]


def coletar_paginas_oficiais() -> list[dict]:
    """Baixa o texto das páginas oficiais do IBGE e da FGV IBRE."""
    paginas = []
    for titulo, url in FONTES_WEB:
        try:
            html = _buscar(url).text
        except requests.RequestException as exc:
            print(f"  [aviso] falhou: {titulo} ({exc})")
            continue

        sopa = BeautifulSoup(html, "html.parser")
        for tag in sopa(["script", "style", "noscript"]):
            tag.decompose()

        texto = re.sub(r"\s+", " ", sopa.get_text(" ")).strip()
        if len(texto) < 500:
            print(f"  [aviso] conteúdo curto demais, ignorado: {titulo}")
            continue

        paginas.append({"titulo": titulo, "url": url, "texto": texto})
        print(f"  [ok] {titulo} ({len(texto)} caracteres)")

    return paginas


def coletar_projecoes_focus() -> dict:
    """
    Projeção oficial do IPCA: mediana das expectativas de mercado coletadas pelo
    Banco Central na pesquisa Focus (relatório semanal).

    Retorna {"data_pesquisa", "mensais": [...], "anuais": [...]}.
    """
    mensais_bruto = _buscar(FOCUS_MENSAL_URL).json().get("value", [])
    if not mensais_bruto:
        raise RuntimeError("A API de Expectativas do Banco Central retornou vazia.")

    data_pesquisa = max(item["Data"] for item in mensais_bruto)

    mensais = []
    for item in mensais_bruto:
        if item["Data"] != data_pesquisa or item.get("Mediana") is None:
            continue
        mes, ano = item["DataReferencia"].split("/")
        mensais.append(
            {
                "codigo": f"{ano}{mes}",
                "mes": item["DataReferencia"],
                "mediana": float(item["Mediana"]),
                "respondentes": item.get("numeroRespondentes"),
            }
        )
    mensais.sort(key=lambda item: item["codigo"])

    anuais_bruto = _buscar(FOCUS_ANUAL_URL).json().get("value", [])
    data_anual = max((item["Data"] for item in anuais_bruto), default=None)
    anuais = sorted(
        (
            {"ano": item["DataReferencia"], "mediana": float(item["Mediana"])}
            for item in anuais_bruto
            if item["Data"] == data_anual and item.get("Mediana") is not None
        ),
        key=lambda item: item["ano"],
    )

    return {"data_pesquisa": data_pesquisa, "mensais": mensais, "anuais": anuais}


def ipca_acumulado(variacoes_mensais: list[float]) -> float:
    """
    Acumula variações mensais de forma composta, como manda a correção monetária:
    fator = Π (1 + i_m/100); resultado em %.
    Somar os percentuais seria errado (ignora os juros sobre juros da inflação).
    """
    fator = 1.0
    for variacao in variacoes_mensais:
        fator *= 1 + variacao / 100
    return (fator - 1) * 100


def calcular_reajuste(valor_atual: float, meses: int, serie: list[dict]) -> dict:
    """Aplica o IPCA acumulado dos últimos N meses sobre um valor (ex.: aluguel)."""
    janela = [m for m in serie if m.get("mensal") is not None][-meses:]
    if not janela:
        raise ValueError("Não há meses com variação disponível na série do IBGE.")

    percentual = ipca_acumulado([m["mensal"] for m in janela])
    valor_reajustado = valor_atual * (1 + percentual / 100)

    return {
        "meses_considerados": len(janela),
        "periodo_inicio": janela[0]["mes"],
        "periodo_fim": janela[-1]["mes"],
        "percentual": percentual,
        "valor_atual": valor_atual,
        "valor_reajustado": valor_reajustado,
        "diferenca": valor_reajustado - valor_atual,
        "detalhe_mensal": janela,
    }


def serie_combinada(serie: list[dict], projecoes: dict) -> list[dict]:
    """
    Linha do tempo única: meses já divulgados pelo IBGE seguidos dos meses
    projetados pelo Focus/BCB, com o acumulado de 12 meses móvel em cada ponto.
    """
    combinada = [
        {
            "codigo": mes["codigo"],
            "mes": mes["mes"],
            "variacao": mes["mensal"],
            "tipo": "realizado",
        }
        for mes in serie
        if mes.get("mensal") is not None
    ]

    ultimo_realizado = combinada[-1]["codigo"]
    for projetado in projecoes["mensais"]:
        if projetado["codigo"] > ultimo_realizado:
            combinada.append(
                {
                    "codigo": projetado["codigo"],
                    "mes": projetado["mes"],
                    "variacao": projetado["mediana"],
                    "tipo": "projetado",
                }
            )

    for posicao, item in enumerate(combinada):
        if posicao >= 11:
            janela = [c["variacao"] for c in combinada[posicao - 11 : posicao + 1]]
            item["acumulado_12m"] = ipca_acumulado(janela)
        else:
            item["acumulado_12m"] = None

    return combinada
