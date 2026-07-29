# Direcionamento de execução — POC Nuvem IA + organização do projeto

## 1. Contexto obrigatório

Você está trabalhando no repositório:

`SuperfrioIA/Nuvem`

Antes de alterar qualquer código, leia obrigatoriamente:

1. `CLAUDE.md` (governa as sessões de IA — precisa ser atualizado junto com o plano)
2. `README.md`
3. `MEMORY.md`
4. `docs/PLANO.md`
5. `docs/ARQUITETURA.md`
6. `docs/DIAGNOSTICO.md`
7. `docs/FONTES_DATAHUB.md`
8. `docs/PILOTO.md`
9. `docs/DEPLOY.md` (runbook de deploy e de testes — a suíte roda via Docker/WSL)
10. `memory/decisoes-fechadas.md`
11. `memory/projeto-nuvem-ia.md`

O projeto já possui uma base funcional com FastAPI, PostgreSQL, Alembic, testes, upload manual, modelos de importação versionados, catálogo semântico, linhagem e scores.

A integração com o SharePoint DataHub via Microsoft Graph já foi validada externamente com:

- `Sites.Selected`;
- concessão `read`;
- token de aplicação;
- acesso ao site `/sites/DataHub`;
- leitura da pasta configurada;
- inventário de arquivos já documentado.

Entretanto, a integração ainda precisa ser incorporada de forma reproduzível ao fluxo da aplicação.

---

# 2. Direção atual do projeto

## Como este marco se encaixa no projeto

Existe **uma** POC: catering na família RMSP (docs/PILOTO.md), alimentada por **dois
canais de fonte** que convergem na mesma camada fina:

1. **SharePoint DataHub** — exports do WMS SLIN (que são justamente os clientes de
   catering da POC);
2. **Arquivos locais do Pentaho/DW** — os 5 modelos de importação já construídos
   (Lotes 8/R1.1), via upload manual.

Os lotes P0–P6 deste documento são o **marco que prova o canal DataHub de ponta a
ponta** com um KPI de amostra. A integração durável das famílias do DataHub na camada
fina (cabeçalho configurável, mapeamento por posição, concatenação `_f1/_f2/_f3`)
vem depois, como incremento do caminho dos modelos de importação — este marco não o
substitui.

## Objetivo imediato

Construir uma prova pequena, visual e demonstrável de que a aplicação consegue:

1. Conectar-se ao SharePoint DataHub;
2. Consultar uma pasta configurada;
3. Listar arquivos e subpastas;
4. Exibir um resumo da conexão;
5. Atualizar o inventário ao clicar em **Sincronizar agora**;
6. Ler uma planilha selecionada;
7. Calcular poucos KPIs confiáveis;
8. Gerar um resumo textual simples sobre os indicadores.

## História que a demonstração deve contar

Durante a apresentação:

1. A tela mostra a conexão ativa com o DataHub;
2. A quantidade atual de pastas e arquivos é exibida;
3. Uma nova pasta ou arquivo é adicionado manualmente no SharePoint;
4. O usuário clica em **Sincronizar agora**;
5. A nova pasta ou arquivo aparece na contagem;
6. O usuário abre a tela de KPIs;
7. A aplicação mostra indicadores calculados com dados reais de uma planilha;
8. Um pequeno resumo textual explica o que foi encontrado.

## Ambiente da demo

- **Fase 1 (a demo em si):** máquina da Maria (Docker/WSL), `.env` local com os
  `GRAPH_*`. Nada precisa subir pra VM antes da apresentação.
- **Fase 2 (pós-apresentação):** subir pra VM (porta 8002) para outras pessoas da
  rede verem. Checklist da subida (pendência pós-demo, não é lote): aplicar as
  migrations 0002–0004 (R1–R3 ainda não deployados na VM), repassar os `GRAPH_*`
  no docker-compose/`.env` da VM e confirmar a liberação de saída HTTPS da VM para
  os endpoints da Microsoft (passo 7 do pedido à infra).

## Princípio central

A IA não calcula números e não interpreta a planilha bruta de forma livre.

O fluxo correto é:

```text
SharePoint
    ↓
Leitura e validação determinística
    ↓
Organização dos metadados
    ↓
Cálculo dos KPIs em código
    ↓
Resumo estruturado
    ↓
Resumo textual por template (determinístico)
```

A POC não usa IA em nenhuma etapa (decisão de 29/jul/2026): o resumo é gerado por
template determinístico. A camada de IA narradora continua fora de escopo, como já
estava registrado na memória, e é candidata a primeiro incremento pós-demo.

---

# 3. O que não deve ser construído agora

Não ampliar o escopo para:

- scheduler;
- sincronização automática recorrente;
- Celery;
- Redis;
- filas;
- workers adicionais;
- banco vetorial;
- RAG;
- chatbot;
- agentes;
- camada de IA para redigir o resumo (cortada da POC em 29/jul/2026 — candidata a
  incremento pós-demo);
- leitura genérica de qualquer planilha;
- processamento das oito famílias do DataHub;
- leitura de PDFs;
- “nuvem de bolinhas” completa;
- motor genérico de insights;
- autenticação corporativa completa;
- novo data lake;
- cópia integral do DataHub para o PostgreSQL;
- reescrita do backend;
- framework abstrato de conectores;
- arquitetura de microsserviços.

A entrega deve ser uma **primeira prova funcional**, não o produto completo.

---

# 4. Diagnóstico da organização atual

## O que está adequado

A divisão principal do código deve ser preservada:

```text
backend/
frontend/
alembic/
tests/
docs/
memory/
```

Também devem ser preservados:

- FastAPI;
- PostgreSQL;
- Alembic;
- Docker Compose;
- estrutura atual de ingestão;
- modelos versionados;
- catálogo semântico;
- linhagem;
- testes existentes.

Não realizar uma reorganização grande apenas por preferência estética.

## O que está confuso

A principal confusão não está na separação técnica do backend. Ela está na documentação e no direcionamento do projeto.

Atualmente:

- `docs/PLANO.md` mistura lotes históricos, pendências humanas, produto futuro e POC;
- o antigo Lote 2 ainda descreve SharePoint como conector genérico e opcional;
- a decisão atual é que o DataHub é uma fonte permanente;
- há conteúdo repetido entre `README.md`, `MEMORY.md`, `docs/PLANO.md`, `docs/DIAGNOSTICO.md` e `memory/`;
- existem descrições antigas dizendo que a POC roda apenas com upload local;
- a visão grande do cockpit corporativo pode induzir a execução prematura de módulos fora da POC;
- arquivos históricos e documentos operacionais ficam misturados com documentos que deveriam orientar o desenvolvimento atual;
- informações sensíveis de infraestrutura não devem ficar excessivamente expostas ou repetidas.

## Diretriz de limpeza

A limpeza deve:

1. Criar uma fonte de verdade clara para a POC atual;
2. Separar planejamento ativo de histórico;
3. Atualizar referências que ficaram superadas;
4. Evitar apagar decisões importantes;
5. Não remover arquivos sem avaliar dependências e valor histórico;
6. Não alterar schema ou código funcional apenas para “arrumar pastas”.

---

# 5. Estrutura alvo recomendada

Use esta estrutura como referência, adaptando com mínimo movimento possível:

```text
Nuvem/
├── backend/
│   ├── main.py
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── migracao.py
│   ├── armazenamento.py
│   ├── ingestao.py
│   ├── motor.py
│   ├── versoes.py
│   │
│   ├── conectores/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── upload_manual.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── graph_datahub.py
│   │   ├── inventario_datahub.py
│   │   └── kpis_poc.py
│   │
│   └── routers/
│       ├── __init__.py
│       ├── admin.py
│       └── datahub.py
│
├── frontend/
│   ├── admin.html
│   ├── datahub.html
│   ├── kpis.html
│   └── assets/
│
├── alembic/
├── tests/
│   ├── (testes existentes permanecem — 44 testes hoje)
│   ├── test_graph_datahub.py
│   ├── test_inventario_datahub.py
│   └── test_kpis_poc.py
│
├── docs/
│   ├── POC_ATUAL.md
│   ├── ARQUITETURA.md
│   ├── FONTES_DATAHUB.md
│   ├── DEPLOY.md
│   ├── historico/
│   └── referencia/
│
├── memory/
├── README.md
├── MEMORY.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

Observações:

- **A árvore é aditiva**: tudo que existe hoje e não está listado (ex.:
  `backend/seed_*.py`, os testes existentes em `tests/`, `alembic.ini`,
  `pytest.ini`, `requirements-dev.txt`) permanece onde está. Nada é movido ou
  removido para "bater com o desenho".
- O cliente Graph fica em `backend/services/graph_datahub.py` — é serviço de
  infraestrutura, **não** implementa a interface `Conector` de
  `backend/conectores/base.py`. O conector `sharepoint_excel` real (formato
  canônico + modelos de importação) fica para depois da POC.
- Não criar `services/` se isso exigir mover grande parte do código existente.
- Para os novos componentes da POC, `services/` é recomendável porque evita colocar regra de negócio dentro de `routers/admin.py`.
- Não mover arquivos antigos de forma massiva sem confirmar referências.
- O arquivo `backend/config.py` é recomendado para centralizar leitura e validação das variáveis de ambiente, mas deve ser simples.

---

# 6. Fonte de verdade do projeto

Criar:

```text
docs/POC_ATUAL.md
```

Esse documento passa a ser a fonte principal para o escopo ativo da POC.

Ele deve conter:

- objetivo;
- fluxo da demonstração;
- escopo incluído;
- escopo excluído;
- lotes atuais;
- critérios de aceite;
- decisões técnicas;
- status atualizado;
- próximo lote autorizado.

Atualizar `CLAUDE.md`, `README.md` e `MEMORY.md` para apontarem claramente para
`docs/POC_ATUAL.md`.

**Dono único do status (decisão de 29/jul/2026):** `docs/POC_ATUAL.md` é o único
arquivo que carrega escopo ativo, lotes P0–P6, status e próximo lote autorizado.
Nenhum outro documento mantém status dos lotes da POC.

O `docs/PLANO.md` **fica onde está, sem mover e sem reescrever**. Ele ganha apenas
um aviso no topo:

> Plano ativo da POC: docs/POC_ATUAL.md. Este arquivo é o histórico do plano de
> produto — nenhum lote daqui está autorizado automaticamente.

Isso preserva todos os links existentes (CLAUDE.md, memória e DIAGNOSTICO.md apontam
para ele) e mantém o histórico dos Lotes 0–R3 intacto.

**Destino deste documento:** ao final do Lote P0, quando `docs/POC_ATUAL.md` existir,
este DIRECIONAMENTO congela — marcar no topo como "Superado por docs/POC_ATUAL.md em
<data> — não usar para execução" (ou mover para `docs/historico/`). Nenhuma sessão
futura deve executá-lo no lugar do POC_ATUAL.

Não apagar o histórico de decisões.

---

# 7. Limpeza obrigatória antes da POC

## 7.1 Inventário

Antes de excluir ou mover qualquer arquivo, produzir um inventário com:

- caminho;
- finalidade;
- se está referenciado;
- classificação:
  - ativo;
  - histórico;
  - referência;
  - gerado;
  - dado sensível;
  - candidato à remoção;
- ação proposta:
  - manter;
  - mover;
  - consolidar;
  - remover;
  - revisar.

O inventário deve separar **rastreado no Git** (`git ls-files`) de **presente só no
disco**. Regra inegociável: nada em `docs/Analise/` e `data/` é movido, renomeado ou
removido — essas pastas já estão no `.gitignore`, existem só na máquina da Maria
(irrecuperáveis se apagadas) e `docs/Analise/` é a base analítica da POC. Classificar
como "local (fora do Git)" e parar aí.

Salvar o inventário em:

```text
docs/ORGANIZACAO_REPOSITORIO.md
```

## 7.2 Regras de remoção

Só remover um arquivo quando:

- ele for comprovadamente gerado;
- estiver duplicado;
- não estiver referenciado;
- não contiver decisão histórica relevante;
- não for necessário para testes;
- não for necessário para deploy;
- a suíte de testes continuar verde.

Não apagar automaticamente:

- migrations;
- seeds;
- testes;
- documentos de decisão;
- arquivos de deploy;
- modelos canônicos;
- histórico que explique escolhas técnicas.

## 7.3 Dados e arquivos inadequados no Git

Estado já verificado (29/jul/2026): `docs/Analise/` e `data/` estão no `.gitignore` —
as planilhas reais, CSVs, cópias com `(2)` e outputs de análise existem **no disco,
não no Git** (ver regra da seção 7.1). A verificação abaixo vale para o que está
**rastreado** (`git ls-files`); o único binário rastreado hoje é
`docs/configuracao_graph_api.docx` (conferido: sem credenciais — é o pedido à infra,
valor histórico).

Verificar se existem **no Git**:

- planilhas reais;
- CSVs reais;
- PDFs de operação;
- dumps;
- arquivos temporários;
- cópias com `(2)`;
- outputs de análise;
- credenciais;
- IPs expostos em documentos de leitura geral;
- documentos binários antigos sem necessidade operacional.

Caso existam dados reais versionados:

1. Não os apagar silenciosamente;
2. Registrar os achados;
3. Avaliar substituição por fixtures anonimizadas;
4. Garantir que testes usem dados sintéticos ou anonimizados;
5. Atualizar `.gitignore`;
6. Não reescrever histórico Git sem autorização explícita.

## 7.4 Documentação contraditória

Regra de mecanismo: **entrada datada nunca é editada** — corrigir um texto superado é
adicionar uma nota nova datada ("29/jul/2026: superado — ver X"), nunca reescrever o
registro original. Vale para docs/PLANO.md, memory/ e qualquer nota histórica.

Corrigir textos que ainda afirmam:

- SharePoint fora do caminho crítico;
- POC baseada apenas em upload local;
- DataHub como conector opcional;
- lotes já concluídos como ainda pendentes;
- estruturas de banco antigas;
- quantidade antiga de tabelas;
- ausência de Alembic ou testes;
- próximo lote incompatível com a decisão atual.

---

# 8. Plano de execução em lotes

Execute um lote por vez.

Ao terminar cada lote:

1. Rodar testes;
2. Informar arquivos alterados;
3. Informar decisões tomadas;
4. Informar riscos encontrados;
5. Atualizar `docs/POC_ATUAL.md`;
6. Atualizar o status do lote;
7. Fazer commit isolado;
8. Não iniciar o próximo lote sem autorização da Maria.

---

## Lote P0 — Diagnóstico e organização segura

### Objetivo

Entender e organizar o repositório sem alterar comportamento funcional.

### Entregas

- Criar `docs/POC_ATUAL.md` (dono único do escopo/status — ver seção 6);
- Criar `docs/ORGANIZACAO_REPOSITORIO.md`;
- Mapear arquivos ativos, históricos e redundantes (separando Git × disco — seção 7.1);
- Atualizar `CLAUDE.md`;
- Atualizar `README.md`;
- Atualizar `MEMORY.md`;
- Adicionar o aviso no topo de `docs/PLANO.md` (sem mover o arquivo — seção 6);
- Registrar a decisão em `memory/decisoes-fechadas.md` (entrada datada de 29/jul/2026:
  lotes P0–P6 como marco do canal DataHub, uma POC com dois canais de fonte, IA do
  resumo cortada, `docs/POC_ATUAL.md` como dono único do status);
- Marcar este DIRECIONAMENTO como superado (ou mover para `docs/historico/`) — seção 6;
- Reorganizar apenas documentos claramente históricos;
- Corrigir referências quebradas (grep por `PLANO.md` em `docs/`, `memory/`,
  `CLAUDE.md` e `README.md` — corrigir todos os apontadores afetados);
- Identificar dados reais ou sensíveis **rastreados no Git** (seção 7.3);
- Atualizar `.gitignore` quando necessário;
- Não alterar lógica funcional;
- Não tocar em `docs/Analise/` nem em `data/` (seção 7.1).

### Como rodar os testes

A suíte (44 testes) exige Postgres real e roda via Docker/WSL — runbook em
`docs/DEPLOY.md`. Não rodar `pytest` direto no Windows. Se o ambiente Docker não
estiver disponível, reportar como bloqueio e aguardar — não pular a etapa nem
concluir que algo quebrou.

### Critério de aceite

- Existe uma fonte de verdade clara para a POC;
- Um desenvolvedor novo entende o objetivo atual em poucos minutos;
- Não há documentação principal contradizendo a direção atual;
- Nenhuma funcionalidade foi quebrada;
- Testes existentes continuam verdes.

### Commit sugerido

```text
docs: organiza fonte de verdade e escopo da poc datahub
```

---

## Lote P1 — Configuração e cliente mínimo do Microsoft Graph

### Objetivo

Transformar a conexão já validada em componente reproduzível da aplicação.

### Entregas

Criar ou ajustar:

```text
backend/config.py
backend/services/graph_datahub.py
tests/test_graph_datahub.py
.env.example        (os GRAPH_* já existem — conferir/ajustar, não recriar)
docker-compose.yml  (repassar os GRAPH_* ao container nuvem-app)
requirements.txt
```

O cliente Graph é serviço de infraestrutura: **não** implementa a interface
`Conector` de `backend/conectores/base.py` (o formato canônico
`{metrica, armazem_na_fonte, competencia, valor}` não se aplica a listar arquivos).
O conector `sharepoint_excel` real fica para depois da POC.

### Responsabilidades mínimas do cliente

```python
obter_token()
testar_conexao()
listar_itens()
```

O download de arquivo pode entrar neste lote ou no P3, dependendo do acoplamento encontrado.

### Requisitos

- Utilizar Client Credentials;
- Utilizar as variáveis `GRAPH_*`;
- Nunca registrar segredo em log;
- Usar timeout;
- Tratar 401, 403, 404, 429 e falha de rede;
- Respeitar paginação por `@odata.nextLink`;
- Não aceitar livre navegação de pasta enviada pelo frontend;
- Usar exclusivamente a pasta configurada no backend;
- Manter acesso somente leitura;
- Não persistir todos os arquivos no banco;
- Não depender de usuário logado no Microsoft 365.

### Dependência HTTP

Escolher uma solução simples:

- `httpx`, preferencialmente; ou
- biblioteca já existente no projeto, se houver.

Não adicionar SDK grande do Microsoft Graph sem necessidade.

### Testes

Mockar respostas HTTP. Cobrir:

- token válido;
- credencial inválida;
- acesso negado;
- lista vazia;
- uma página;
- múltiplas páginas;
- timeout;
- resposta malformada.

### Critério de aceite

A aplicação consegue executar um teste de conexão e listar os itens configurados sem script externo.

### Commit sugerido

```text
feat: adiciona cliente graph somente leitura para o datahub
```

---

## Lote P2 — Tela DataHub e sincronização manual

### Objetivo

Construir a primeira parte visual da demonstração.

### Entregas

Criar rota dedicada, preferencialmente:

```text
backend/routers/datahub.py
```

Endpoints mínimos:

```text
GET  /api/admin/datahub/status
POST /api/admin/datahub/sincronizar
GET  /api/admin/datahub/resumo
```

Pode haver simplificação para dois endpoints, caso o desenho fique mais limpo.

### Comportamento

Ao abrir a tela:

- mostrar conexão ativa ou erro;
- mostrar a pasta configurada;
- mostrar a data da última consulta;
- mostrar quantidade de arquivos;
- mostrar quantidade de pastas;
- mostrar arquivos por extensão;
- mostrar pastas encontradas;
- mostrar arquivos mais recentes.

Ao clicar em **Sincronizar agora**:

- consultar novamente o Graph;
- reconstruir o inventário;
- atualizar os indicadores;
- mostrar horário da sincronização;
- refletir novas pastas e novos arquivos.

A listagem deve ser **recursiva**: o endpoint `children` do Graph é por pasta — para
contar os arquivos das famílias é preciso descer nas subpastas, senão o teste de
demonstração (nova pasta/arquivo → contagem incrementa) só funciona no primeiro nível.

### Persistência

Para a POC, escolher a solução mais simples entre:

1. inventário em **cache em memória do processo** (variável do módulo, reconstruído
   a cada "Sincronizar agora" — não "por requisição", senão a data da última
   sincronização se perde entre requests); ou
2. snapshot mínimo no PostgreSQL.

Preferência inicial: não criar tabela se não houver necessidade.

Persistir somente se isso melhorar claramente:

- comparação entre sincronizações;
- última sincronização;
- demonstração;
- rastreabilidade.

Não copiar o conteúdo integral do DataHub.

### Serviço de inventário

Criar:

```text
backend/services/inventario_datahub.py
```

Responsabilidades:

- contar arquivos;
- contar pastas;
- agrupar extensões;
- identificar arquivos mais recentes;
- calcular tamanho total;
- identificar famílias por nome quando possível;
- identificar competências por convenção de nome;
- produzir resumo estruturado.

### Interface

A tela deve ser simples e profissional.

Elementos mínimos:

- status da conexão;
- botão `Sincronizar agora`;
- data e hora da última sincronização;
- cards de arquivos e pastas;
- lista de pastas;
- lista dos arquivos mais recentes;
- mensagem de erro clara;
- estado de carregamento.

Não construir dashboard visual complexo.

### Teste de demonstração

1. Abrir tela;
2. Registrar contagem atual;
3. Criar uma pasta de demonstração no SharePoint;
4. Clicar em `Sincronizar agora`;
5. Confirmar incremento da contagem;
6. Remover a pasta de demonstração após a apresentação, se aplicável.

### Critério de aceite

Uma alteração feita no SharePoint aparece na tela após sincronização manual.

### Commit sugerido

```text
feat: adiciona painel e sincronizacao manual do datahub
```

---

## Lote P3 — Leitura controlada de uma planilha

### Objetivo

Provar que a aplicação não apenas enxerga arquivos, mas consegue ler dados reais.

### Escopo

Escolher uma única família de arquivos.

Preferência:

```text
ENTRADA_MERCADORIAS
```

Motivos:

- cabeçalho na linha 1;
- estrutura mais simples;
- sem partes `_f1`, `_f2`, `_f3`;
- KPIs fáceis de validar.

Caso os arquivos reais mostrem outra família mais segura, registrar a decisão antes de implementar.

### Entregas

- Download de um arquivo via Graph;
- Seleção controlada do arquivo;
- Validação de nome e extensão;
- Limite de tamanho;
- Leitura com `openpyxl`;
- Validação das colunas esperadas;
- Tratamento de valores inválidos;
- Resultado estruturado;
- Sem ingestão genérica de todas as famílias.

### Metadados obrigatórios no resultado

- nome do arquivo;
- caminho;
- data de modificação;
- tamanho;
- competência inferida;
- filial inferida;
- quantidade de linhas lidas;
- quantidade de linhas válidas;
- quantidade de linhas descartadas;
- percentual de qualidade.

### Segurança

- Não permitir download de URL arbitrária;
- Utilizar `item_id` retornado pelo próprio Graph;
- Validar que o item pertence ao caminho configurado;
- Não executar macros;
- Não carregar arquivo ilimitado em memória;
- Não persistir arquivo além do necessário sem decisão explícita.

### Testes

Usar fixture sintética representativa.

Cobrir:

- arquivo correto;
- coluna ausente;
- valor inválido;
- arquivo vazio;
- planilha sem aba esperada;
- extensão inválida;
- arquivo acima do limite.

### Critério de aceite

A aplicação consegue ler um arquivo real selecionado no DataHub e devolver dados validados.

### Commit sugerido

```text
feat: le planilha controlada do datahub para a poc
```

---

## Lote P4 — KPIs da POC

### Objetivo

Calcular poucos indicadores claros e auditáveis.

### KPIs recomendados

Escolher entre três e cinco:

- quantidade de registros;
- quantidade de clientes;
- volume total;
- peso líquido total;
- peso bruto total;
- quantidade total de UAs;
- valor total movimentado.

Não implementar todos apenas porque existem colunas disponíveis.

Selecionar os KPIs mais confiáveis e fáceis de validar com o negócio.

### Serviço

Criar:

```text
backend/services/kpis_poc.py
```

O serviço deve receber dados já validados e produzir números determinísticos.

### Tela

Criar uma tela ou aba chamada:

```text
KPIs da POC
```

Exibir:

- arquivo utilizado;
- filial;
- competência;
- data de atualização;
- qualidade da leitura;
- cards com KPIs;
- uma tabela simples;
- no máximo um gráfico simples, se agregar valor;
- botão para atualizar os dados do arquivo.

### Auditoria

Cada KPI deve indicar:

- coluna ou regra utilizada;
- unidade;
- quantidade de registros válidos;
- fonte do arquivo.

### Critério de aceite

Os KPIs batem com uma conferência manual ou planilha de validação.

### Commit sugerido

```text
feat: adiciona kpis auditaveis da primeira fonte datahub
```

---

## Lote P5 — Resumo textual e acabamento da demonstração

### Objetivo

Traduzir os indicadores em uma leitura curta de negócio.

### Resumo por template (única versão da POC)

Implementar resumo determinístico por template.

Exemplo:

```text
O arquivo de julho de 2026 foi lido diretamente do DataHub.
Foram identificados X registros válidos e Y clientes.
O peso bruto total encontrado foi Z, com qualidade de leitura de W%.
```

### IA no resumo — cortada da POC

Decisão de 29/jul/2026: a camada opcional de IA para redigir o resumo **não entra na
POC** (mantém a decisão anterior de IA narradora fora de escopo). O resumo da POC é
somente o template determinístico acima. A camada de IA é candidata a primeiro
incremento pós-demo; se um dia for construída, as salvaguardas já ficam registradas:
enviar apenas o JSON de KPIs, nunca o segredo do Graph nem a planilha bruta, resposta
de poucas frases, sem inventar causas, texto marcado como gerado por IA, fallback
determinístico em qualquer falha.

### Acabamento

- revisar textos da interface;
- revisar estados de erro;
- revisar loading;
- revisar responsividade básica;
- incluir roteiro de demonstração;
- incluir checklist de preparação.

Criar:

```text
docs/DEMO_POC.md
```

### Critério de aceite

A demonstração completa pode ser realizada em aproximadamente cinco minutos.

### Commit sugerido

```text
feat: finaliza resumo e roteiro da poc datahub
```

---

## Lote P6 — Revisão final e limpeza pós-POC

### Objetivo

Consolidar a entrega sem carregar experimentos ou código morto.

### Entregas

- remover código temporário da integração;
- remover prints e logs de debug;
- remover endpoints de teste inseguros;
- garantir que segredos não estejam versionados;
- revisar dependências não utilizadas;
- revisar imports;
- revisar documentação;
- revisar scripts temporários;
- confirmar migrations;
- rodar suíte completa;
- validar Docker Compose;
- validar subida em banco novo;
- validar subida em banco existente;
- gerar relatório final.

Criar:

```text
docs/ENTREGA_POC.md
```

O relatório deve conter:

- objetivo comprovado;
- telas entregues;
- fonte utilizada;
- KPIs;
- limitações;
- riscos;
- próximos incrementos possíveis;
- itens explicitamente deixados para depois.

### Critério de aceite

A branch está limpa, documentada, reproduzível e pronta para demonstração.

### Commit sugerido

```text
chore: consolida e limpa entrega da poc datahub
```

---

# 9. Critérios técnicos gerais

## Testes

Não reduzir a cobertura existente.

A suíte roda via Docker/WSL, com Postgres real (runbook em `docs/DEPLOY.md`) — não
rodar `pytest` direto no Windows.

Novos testes não devem depender do SharePoint real.

Separar:

- testes unitários com mocks;
- teste manual de integração real;
- teste de demonstração.

## Banco

Não criar tabelas sem necessidade clara.

Caso seja necessário persistir sincronizações, propor antes:

- schema;
- finalidade;
- retenção;
- impacto;
- migration;
- testes.

## Logs

Registrar:

- início e fim da sincronização;
- quantidade de itens;
- duração;
- erro resumido;
- código HTTP;
- correlação da execução.

Nunca registrar:

- `GRAPH_CLIENT_SECRET`;
- access token;
- conteúdo integral de arquivo;
- dados pessoais sem necessidade.

## Frontend

Preservar a simplicidade.

Não criar componentes excessivos ou uma nova framework frontend apenas para a POC.

Se o projeto usa HTML/JavaScript simples, continuar assim.

## Compatibilidade

Preservar:

- porta 8002;
- Docker Compose;
- PostgreSQL atual;
- migrações existentes;
- upload manual atual;
- endpoints atuais;
- tela administrativa atual.

A nova POC deve entrar ao lado do que existe, não quebrar o fluxo anterior.

---

# 10. Regras de comunicação e execução

Antes de cada lote, apresentar:

1. diagnóstico do que será alterado;
2. arquivos previstos;
3. riscos;
4. critério de aceite;
5. o que ficará fora.

Ao final de cada lote, entregar:

1. resumo do que foi feito;
2. arquivos alterados;
3. testes executados;
4. resultados;
5. limitações;
6. pendências;
7. instruções de validação manual;
8. hash do commit.

Não começar o lote seguinte automaticamente.

Não tomar decisões de produto irreversíveis sem registrar a alternativa e pedir validação.

---

# 11. Primeira instrução de execução

Comece exclusivamente pelo **Lote P0 — Diagnóstico e organização segura**.

Não implemente o conector Graph ainda.

Primeiro:

1. Analise toda a árvore do repositório;
2. Liste redundâncias e contradições;
3. Proponha os movimentos;
4. Crie `docs/POC_ATUAL.md`;
5. Crie `docs/ORGANIZACAO_REPOSITORIO.md`;
6. Atualize os documentos de entrada;
7. Rode os testes;
8. Apresente o resultado para validação.

Aguarde autorização explícita para iniciar o Lote P1.
