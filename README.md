# Consultor de IPCA para Imóveis — RAG com LLM local

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

---

## Parte 2 — Fala de apresentação

> Roteiro de 4 a 5 minutos. Os números mudam a cada divulgação —
> **confira os valores na tela antes de apresentar**.

---

### Abertura

"Quem trabalha com imóveis convive com uma pergunta que se repete todo mês:
de quanto vai ser o reajuste deste contrato?

A resposta está no IPCA, mas ela está espalhada. O índice oficial está no site do IBGE,
as projeções estão no Banco Central, os estudos sobre aluguel estão na FGV. E o corretor
acaba recorrendo ao Google ou a um ChatGPT da vida, que inventa número com uma confiança
impressionante — ou repete um dado de dois anos atrás.

Foi esse problema que eu resolvi."

### O que é o projeto

"Eu construí um **chatbot de consulta ao IPCA voltado para o mercado imobiliário**,
usando a arquitetura RAG — *Retrieval-Augmented Generation*.

A diferença para um chatbot comum é que o meu modelo **não responde com o que ele aprendeu
no treinamento**. Ele responde com o que foi recuperado, naquele instante, de fontes oficiais.
Se a informação não está nas fontes, ele é instruído a dizer que não sabe."

### A arquitetura, nas três letras do RAG

"O RAG tem três etapas, e eu implementei cada uma delas:

**R, de Retrieval — recuperação.** Eu coleto as fontes oficiais, quebro os textos em pedaços
de mil caracteres com duzentos de sobreposição, e transformo cada pedaço em um vetor de
384 dimensões usando um modelo de embeddings que roda na própria máquina. Quando o usuário
pergunta algo, a pergunta também vira vetor, e eu busco os trechos mais próximos por
**similaridade de cosseno**. Hoje são 196 documentos indexados.

**A, de Augmentation — aumento de contexto.** Aqui está a decisão técnica de que eu mais
me orgulho. A busca vetorial sozinha tem uma fraqueza: os documentos mensais do IPCA são
quase idênticos entre si — muda só o mês e o número. O modelo de embeddings confunde
'março de 2027' com 'março de 2026'. Então, além dos trechos recuperados, eu injeto um
bloco de fatos montado **de forma determinística**, direto da API: a data de hoje, o último
índice divulgado, os acumulados e a tabela de reajuste projetado mês a mês. Assim o número
do presente e do futuro chega correto **independentemente de a busca vetorial acertar**.

**G, de Generation — geração.** Um LLM local, servido pelo Ollama, apenas **redige** a
resposta a partir desse contexto. Ele não faz conta e não busca nada. O prompt de sistema
proíbe inventar números e manda sempre citar o mês de referência e a fonte."

### As fontes

"Todas as fontes são oficiais e públicas:

- **IBGE** — a página oficial do IPCA e a API do SIDRA, tabela 1737, com a série histórica;
- **FGV IBRE** — Índices de Preços, Monitor da Inflação, Boletim Macro, o Indicador de
  Expectativa de Inflação e o IVAR, que é o índice de variação de aluguéis residenciais;
- **Banco Central** — a pesquisa Focus, que é a projeção oficial de IPCA do país.

E aqui vale uma justificativa técnica: nem o IBGE nem a FGV publicam projeção de IPCA em
formato consultável por máquina. A FGV divulga isso em PDF, dentro do Boletim Macro.
Como eu precisava de projeção estruturada, recorri à API de Expectativas de Mercado do
Banco Central — que é a referência oficial de projeção no Brasil e é usada pela própria
política monetária."

### Demonstração

"Na tela inicial eu mostro **dois cenários**, em abas.

O primeiro é o **cenário atual**, com o que já foi fechado pelo IBGE: a variação do último
mês, o acumulado no ano e o acumulado em doze meses, com o gráfico dos últimos 24 meses.

O segundo é o **cenário projetado**, com a mediana da pesquisa Focus: quanto o mercado
espera de inflação para os próximos meses e para os próximos anos.

*(abrir as duas abas e ler os números da tela)*

Na barra lateral tem a **calculadora de reajuste**. O usuário digita o valor do aluguel e
escolhe a janela de tempo que quiser, de 1 a 48 meses. Eu deixei o período ajustável de
propósito: o reajuste anual é o caso comum, mas quem administra carteira precisa simular
contratos atrasados ou renegociações.

*(colocar em 12 meses e mostrar o resultado)*

E no chat eu posso perguntar em linguagem natural — por exemplo, o reajuste estimado para
um contrato que faz aniversário em março do ano que vem — e ele responde citando a fonte."

### A matemática

"Um detalhe que parece pequeno e não é: o acumulado do IPCA é **composto**, não somado.

$$i_{acumulado} = \left[ \prod_{m=1}^{n} \left(1 + \frac{i_m}{100}\right) - 1 \right] \times 100$$

Multiplicam-se os fatores de cada mês. Se eu somasse os percentuais, o reajuste sairia
menor que o devido e o locador perderia dinheiro.

Eu validei isso: o valor que a minha função calcula para doze meses bate **exatamente** com
o acumulado de doze meses publicado pelo IBGE. E o acumulado que eu projeto para dezembro
de 2027 bate com a mediana anual que o Focus publica para 2027. São duas conferências
independentes que fecham."

### Por que local

"Todo o processamento é local. Os embeddings rodam em ONNX na máquina, o banco vetorial é
um arquivo na pasta do projeto e o modelo de linguagem roda no Ollama.

Isso significa **zero custo de API**, funcionamento sem depender de serviço externo, e —
o ponto mais relevante para uma imobiliária — **nenhum dado de contrato ou de cliente sai
do computador**, o que conversa diretamente com a LGPD."

### Limitações (falar antes que perguntem)

"Sendo honesta sobre os limites:

O modelo de embeddings que eu uso é treinado principalmente em inglês, então ele perde
precisão em português — foi exatamente por isso que eu criei a camada determinística de
contexto, para o sistema não depender só dele.

A projeção é expectativa de mercado, não é índice fechado: ela muda toda semana e serve
para planejar, não para assinar contrato.

E o sistema é uma ferramenta de consulta acadêmica — o valor oficial deve sempre ser
conferido no IBGE antes de fechar negócio. Isso está escrito no próprio prompt do sistema."

### Fechamento

"Resumindo: eu peguei um problema real de quem trabalha com imóveis, liguei três fontes
oficiais do governo e da FGV, implementei o pipeline de RAG — chunking, embeddings, busca
vetorial e aumento de contexto — e coloquei um LLM local para conversar com o usuário,
sem alucinar número e sem mandar dado nenhum para fora.

Obrigada. Estou à disposição para as perguntas."

---

### Se a banca perguntar

**"Por que não usou LangChain?"**
Implementei o pipeline direto com ChromaDB para ter controle explícito de cada etapa —
chunking, embeddings, busca e montagem do prompt. Em um projeto de aprendizado, escrever
a lógica vale mais do que esconder tudo atrás de uma abstração.

**"Por que 1000 caracteres de chunk e 200 de sobreposição?"**
Mil caracteres é um parágrafo com contexto suficiente e ainda cabe folgado na janela do
modelo. A sobreposição de 200 evita que um número fique separado da frase que o explica,
exatamente na emenda de dois chunks.

**"Como você garante que ele não alucina?"**
Três camadas. O prompt de sistema proíbe inventar e manda citar a fonte. O contexto
determinístico entrega os números prontos, então o modelo não precisa calcular nada.
E a interface mostra os trechos recuperados com o score de similaridade, para o usuário
conferir de onde veio a resposta.

**"E se alguém colocar instrução maliciosa numa das páginas que você indexa?"**
Pensei nisso. Como o RAG ingere páginas da web, o prompt de sistema trata o contexto
como **dado, nunca como instrução**, e manda ignorar qualquer comando que apareça dentro
dele. É a defesa contra *prompt injection*.

**"Por que similaridade de cosseno e não distância euclidiana?"**
Cosseno compara a direção dos vetores e ignora a magnitude, então documentos longos e
curtos competem em pé de igualdade. É o padrão para busca semântica de texto.
