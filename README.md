# Consultor de IPCA — RAG com LLM local

Chatbot que responde perguntas sobre o IPCA usando **apenas fontes oficiais brasileiras**,
com busca vetorial (RAG) e um modelo de linguagem rodando **na própria máquina**.
Nenhum dado sai do computador e nenhuma API de IA paga é usada.

---

## Parte 1 — Como rodar no Windows

### 1. Instalar o Python

Baixe o Python 3.11 ou 3.12 em <https://www.python.org/downloads/windows/>.

> Na primeira tela do instalador, **marque a caixa "Add python.exe to PATH"**.
> Sem isso, os comandos abaixo não funcionam.

Confira no PowerShell:

```powershell
python --version
```

### 2. Instalar o Ollama (o LLM local)

Baixe e instale o **Ollama para Windows** em <https://ollama.com/download/windows>.

Depois de instalar, ele já sobe sozinho como serviço. Confira:

```powershell
ollama --version
```

### 3. Baixar o modelo de linguagem

```powershell
ollama pull llama3.2
```

São cerca de 2 GB. Para confirmar que baixou:

```powershell
ollama list
```

> **Modelos alternativos**, se a máquina for mais fraca ou mais forte:
> `ollama pull llama3.2:1b` (mais leve) ou `ollama pull llama3` (mais pesado, 4,7 GB).
> O aplicativo detecta sozinho quais modelos existem e deixa você escolher na barra lateral.

### 4. Abrir a pasta do projeto

```powershell
cd "C:\caminho\para\RAG_IPCA"
```

### 5. Criar e ativar o ambiente virtual

```powershell
python -m venv .venv
.venv\Scripts\activate
```

O prompt passa a mostrar `(.venv)` no início da linha.

> Se o PowerShell bloquear a ativação com erro de *execution policy*, rode:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` e tente de novo.

### 6. Instalar as bibliotecas

```powershell
pip install -r requirements.txt
```

### 7. Construir o índice vetorial (a ingestão do RAG)

```powershell
python ingest.py
```

Este passo:

1. busca a série do IPCA na API do IBGE/SIDRA;
2. busca as projeções na API do Banco Central (Focus);
3. baixa as páginas oficiais do IBGE e da FGV IBRE;
4. quebra tudo em pedaços, gera os embeddings e grava a pasta `vector_db/`.

> Na **primeira execução** ele baixa também o modelo de embeddings (cerca de 80 MB).
> Isso acontece uma vez só.

Precisa rodar de novo só quando quiser atualizar os dados (o IBGE divulga o IPCA
uma vez por mês; o Focus é semanal).

### 8. Abrir o aplicativo

```powershell
python -m streamlit run app.py
```

O navegador abre em <http://localhost:8501>. Para encerrar, `Ctrl + C` no PowerShell.

---

### Resumo: do zero ao ar

```powershell
cd "C:\caminho\para\RAG_IPCA"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
ollama pull llama3.2
python ingest.py
python -m streamlit run app.py
```

### Nas próximas vezes (com tudo já instalado)

```powershell
cd "C:\caminho\para\RAG_IPCA"
.venv\Scripts\activate
python -m streamlit run app.py
```

---

### Arquivos do projeto

| Arquivo | Para que serve |
|---|---|
| `app.py` | O aplicativo: gráficos, calculadora e chatbot. **É este que você roda.** |
| `ingest.py` | Coleta as fontes e constrói o índice vetorial |
| `ipca_fontes.py` | Acesso às APIs oficiais e cálculo do reajuste composto |
| `requirements.txt` | Lista de bibliotecas |
| `README.md` | Este arquivo |
| `vector_db/` | O índice vetorial, gerado pelo `ingest.py` |

---

### Se der problema

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `python não é reconhecido` | Python fora do PATH | Reinstalar marcando "Add python.exe to PATH" |
| `Nenhum modelo local encontrado no Ollama` | Modelo não baixado | Rodar `ollama pull llama3.2` e recarregar a página |
| `Falha ao consultar o modelo local` | Serviço parado | Rodar `ollama serve` em outro PowerShell |
| Erro de certificado SSL ao buscar dados | Rede corporativa com inspeção de tráfego | Usar uma rede doméstica ou pedir liberação de `ibge.gov.br`, `portalibre.fgv.br` e `bcb.gov.br` |
| `ollama pull` falha com `max retries exceeded: EOF` | Rede corporativa bloqueia o download | Baixar o modelo em outra rede; os modelos ficam em `C:\Users\<você>\.ollama\models` e essa pasta pode ser copiada |
| Chat responde, mas sem dados | Ingestão não executada | Rodar `python ingest.py` |


**"Por que similaridade de cosseno e não distância euclidiana?"**
Cosseno compara a direção dos vetores e ignora a magnitude, então documentos longos e
curtos competem em pé de igualdade. É o padrão para busca semântica de texto.
