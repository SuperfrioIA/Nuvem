# V1 Nuvem IA — Direcionamento de Produto, Arquitetura e Execução

## 1. Objetivo

Este documento passa a ser a principal orientação para a construção da **V1 de produção da Nuvem IA**.

A POC foi concluída. A partir deste ponto, o projeto não deve mais ser tratado como prova de conceito.

A V1 deve transformar o que já foi comprovado em uma solução de produção capaz de:

- conectar-se a fontes corporativas;
- catalogar fontes diferentes;
- padronizar conceitos entre WMSs e sistemas distintos;
- explorar dados de forma controlada;
- descobrir oportunidades de indicadores e insights;
- transformar análises aprovadas em KPIs determinísticos;
- oferecer um cockpit único para diretoria e CEO;
- permitir análise por período, filial e cliente;
- manter rastreabilidade, qualidade e governança.

---

## 2. Estado atual

O repositório já possui FastAPI, PostgreSQL, Alembic, Docker Compose, autenticação administrativa, upload manual, modelos de importação versionados, medidas recebidas, medidas canônicas, linhagem, catálogo semântico inicial, motor de scores, conexão somente leitura com o SharePoint DataHub, sincronização manual, inventário, leitura de `ENTRADA_MERCADORIAS`, KPIs auditáveis, resumo determinístico e a página da Nuvem do DataHub.

Antes de alterar código, leia obrigatoriamente:

1. `README.md`
2. `MEMORY.md`
3. `docs/POC_ATUAL.md`
4. `docs/PLANO.md`
5. `docs/ARQUITETURA.md`
6. `docs/DIAGNOSTICO.md`
7. `docs/FONTES_DATAHUB.md`
8. `docs/PILOTO.md`
9. `docs/DEPLOY.md`
10. `memory/decisoes-fechadas.md`
11. `memory/projeto-nuvem-ia.md`

Analise também os commits mais recentes relacionados aos lotes P4, P5, P5.5 e à série histórica.

---

## 3. Mudança oficial de fase

Registrar nos documentos relevantes:

> A POC da integração SharePoint DataHub foi concluída com sucesso. A partir desta etapa, o projeto entra na construção da V1 de produção da Nuvem IA.

Evitar nas telas ativas:

- “KPIs da POC”;
- “resumo da POC”;
- “tela da POC”;
- nomenclaturas temporárias.

A documentação histórica deve permanecer disponível, mas separada do plano ativo.

Criar:

```text
docs/V1_ESCOPO.md
docs/V1_PLANO.md
docs/V1_CRITERIOS_ACEITE.md
docs/V1_ARQUITETURA.md
```

`docs/V1_PLANO.md` deve ser a fonte única do status da V1.

---

## 4. Visão do produto

```text
Nuvem IA
├── Fontes e Catálogo
├── Laboratório de Insights
├── Métricas Governadas
└── Cockpit Executivo
```

### Fontes e Catálogo

Conexões, pastas, arquivos, tabelas, APIs, campos, conceitos, unidades, granularidades, qualidade, regras de agregação e comparabilidade.

### Laboratório de Insights

Seleção de fontes, perfil dos dados, perguntas, sugestões, feedback, salvamento de análise candidata e preparação de especificação.

### Métricas Governadas

Definições oficiais, fórmulas, dimensões, unidades, granularidade, agregações, versões, linhagem, validação e publicação.

### Cockpit Executivo

KPIs oficiais, fontes compatíveis, filtros, séries históricas, comparações, leitura executiva, qualidade e cobertura.

---

## 5. Decisões fixadas

### 5.1 Cadastro de produtos fora do escopo

Não criar, corrigir, sanear ou depender de:

- cadastro de produtos;
- embalagem por produto;
- caixa por unidade;
- peso por unidade;
- quantidade por embalagem;
- paletização;
- unidade comercial por SKU;
- conversão baseada em cadastro;
- correção de cadastros do WMS ou ERP.

Registrar:

> A V1 não realizará saneamento cadastral e não criará conversões dependentes de cadastro de produto. Quando a compatibilidade de medidas não for conhecida com segurança, o sistema não consolidará os valores.

### 5.2 Somar apenas medidas compatíveis

Permitido:

```text
kg + kg
tonelada convertida para kg
grama convertida para kg
libra convertida para kg
```

Proibido:

```text
caixa + kg
unidade + palete
caixa + unidade
volume sem unidade conhecida
```

Quando não houver compatibilidade:

1. não somar;
2. separar por unidade ou categoria;
3. informar a limitação;
4. não inventar conversão;
5. não usar cadastro de produto;
6. não apresentar “volume total” misturando unidades.

### 5.3 “Volume” não é conceito corporativo único

Uma coluna `Volume` pode significar caixas, unidades, peso, cubagem, embalagens, UAs, LPNs, paletes ou frações.

Nenhum campo chamado apenas “volume” poderá ser consolidado sem unidade, definição e regra semântica.

Categorias mínimas:

- massa;
- quantidade;
- embalagem;
- estrutura logística;
- cubagem;
- desconhecida.

Essa classificação é metadado técnico-semântico, não cadastro de produto.

### 5.4 Catálogo semântico como fundamento

Campos diferentes podem representar o mesmo conceito:

```text
SLIN.Peso Bruto
BlueYonder.GROSS_WGT
OutraFonte.PESO_TOTAL
```

podem mapear para:

```text
peso_bruto_movimentado
```

somente quando definição, unidade, granularidade, transformação e agregação forem compatíveis e aprovadas.

Não espalhar regras `if fonte == ...` pelo código. Os mapeamentos devem ser configuráveis e versionados.

### 5.5 Laboratório separado do cockpit

O Laboratório é exploratório. O Cockpit é oficial.

Fluxo curto:

```text
Exploração
    ↓
Aprovado para implementação
    ↓
Publicado
```

Também pode existir `Descartado`.

A IA nunca publica diretamente no cockpit.

### 5.6 IA não calcula KPI oficial

A IA pode sugerir perguntas, explicar dados, apontar oportunidades, propor análises e ajudar a estruturar métricas candidatas.

A IA não pode publicar KPI, substituir cálculo determinístico, inventar unidade, inventar causa, somar medidas incompatíveis, decidir sozinha uma anomalia ou transformar hipótese em verdade oficial.

### 5.7 Dimensões obrigatórias

A V1 deve permitir análise por:

- mês;
- ano;
- intervalo personalizado;
- uma, várias ou todas as filiais;
- um, vários ou todos os clientes;
- combinações de período, filial e cliente.

Filtros globais:

```text
Período: [início] até [fim]
Filiais: [uma, várias ou todas]
Clientes: [um, vários ou todos]
```

Atalhos:

- mês atual;
- últimos 3 meses;
- últimos 6 meses;
- ano atual;
- últimos 12 meses;
- período personalizado.

---

## 6. Modelo semântico mínimo

Cada campo de fonte deve possuir, quando aplicável:

- fonte;
- família;
- arquivo, tabela ou endpoint;
- nome original;
- descrição funcional;
- conceito canônico;
- tipo de dado;
- unidade original;
- unidade canônica;
- categoria da unidade;
- transformação;
- regra de agregação;
- granularidade original;
- dimensão temporal;
- dimensão filial;
- dimensão cliente;
- obrigatório ou opcional;
- status do mapeamento;
- versão;
- vigência;
- observações;
- responsável pela validação.

Exemplo:

```yaml
fonte: WMS_SLIN
familia: ENTRADA_MERCADORIAS
campo_original: Peso Bruto
descricao: Peso bruto da movimentação de entrada
conceito_canonico: peso_bruto_movimentado
unidade_original: kg
unidade_canonica: kg
categoria_unidade: massa
transformacao: valor direto
agregacao: soma
granularidade: filial x cliente x competência
dimensoes:
  - competencia
  - filial
  - cliente
status: aprovado
```

---

## 7. Modelo de KPI governado

Cada KPI deve declarar:

- nome e código;
- pergunta de negócio;
- descrição executiva;
- conceitos;
- fontes permitidas;
- fórmula;
- unidade canônica;
- granularidade;
- dimensões;
- agregação temporal;
- agregação por filial;
- agregação por cliente;
- tipo aditivo, semi-aditivo ou não aditivo;
- filtros e exclusões;
- qualidade;
- comparabilidade;
- versão e vigência;
- status;
- aprovação;
- linhagem;
- testes esperados.

Exemplo aditivo:

```yaml
kpi: peso_bruto_movimentado
unidade: tonelada
granularidade: filial x cliente x mês
agregacao_temporal: soma
agregacao_filial: soma
agregacao_cliente: soma
tipo: aditivo
```

Exemplo semi-aditivo:

```yaml
kpi: ocupacao_percentual
unidade: percentual
granularidade: filial x data
agregacao_temporal: última fotografia válida ou média ponderada
agregacao_filial: média ponderada pela capacidade
agregacao_cliente: não permitido sem regra específica
tipo: semi-aditivo
```

Percentuais nunca devem ser somados diretamente.

---

## 8. Persistência e série histórica

O fluxo atual que lê apenas o arquivo mais recente e calcula KPIs em memória não atende à V1.

Usar a camada existente:

```text
execuções
    ↓
medidas_recebidas
    ↓
medidas canônicas
    ↓
consultas do cockpit
```

Granularidade mínima recomendada:

```text
competência × filial × cliente × métrica
```

Quando a fonte não tiver cliente:

- não inventar;
- manter ausente;
- restringir análises dependentes de cliente.

A solução deve suportar:

- série mensal;
- consolidação anual;
- comparação mês contra mês;
- comparação com período anterior quando houver histórico;
- acumulado do ano;
- ranking de filiais;
- ranking de clientes;
- participação por cliente;
- visão consolidada.

---

## 9. Laboratório de Insights

### 9.1 Objetivo

Permitir exploração controlada antes da construção de KPIs definitivos e evitar análises isoladas em ferramentas externas sem rastreabilidade.

### 9.2 Fluxo

```text
Selecionar fontes
    ↓
Gerar perfil determinístico
    ↓
Apresentar contexto do catálogo
    ↓
Escolher mensagem sugerida ou escrever pergunta
    ↓
Executar análise controlada
    ↓
Responder no chat
    ↓
Avaliar
    ↓
Salvar, descartar ou aprovar
```

### 9.3 Seleção

Permitir:

- uma ou várias pastas;
- um ou vários arquivos;
- uma família;
- uma ou várias filiais;
- um ou vários clientes;
- um intervalo de competências.

Aplicar limites de tamanho, quantidade e tempo.

### 9.4 Perfil determinístico

Antes da IA, calcular:

- colunas;
- tipos;
- nulos;
- distintos;
- mínimo;
- máximo;
- soma apenas quando permitida;
- unidades;
- categorias;
- duplicidades;
- chaves candidatas;
- cobertura temporal;
- filiais;
- clientes;
- granularidade provável;
- qualidade;
- limitações;
- amostra segura.

A IA não deve descobrir esses números livremente.

### 9.5 Mensagens sugeridas opcionais

**Entender os dados**

- Explique de forma simples o que estes arquivos contêm.
- Identifique as principais dimensões e medidas.
- Avalie a qualidade e as limitações.
- Identifique unidades e possíveis incompatibilidades.

**Descobrir indicadores**

- Sugira KPIs úteis para uma visão executiva.
- Sugira indicadores comparáveis entre filiais.
- Sugira indicadores analisáveis por cliente.
- Identifique quais indicadores podem ser consolidados.
- Indique quais dados não devem ser somados.

**Comparar**

- Mostre a evolução mensal.
- Compare o período atual com o anterior.
- Compare as filiais selecionadas.
- Compare os clientes selecionados.
- Mostre o acumulado do ano.
- Identifique concentração por cliente.

**Validar**

- Este indicador é confiável para diretoria?
- Há risco de dupla contagem?
- As unidades podem ser somadas?
- Quais validações faltam?
- Quais limitações devem aparecer no cockpit?

O usuário pode editar ou escrever livremente.

### 9.6 Rastreabilidade

Salvar:

- usuário;
- data;
- fontes e arquivos;
- versões ou datas de modificação;
- filtros;
- perfil;
- mensagens e respostas;
- modelo;
- parâmetros;
- feedback;
- status;
- insight candidato;
- decisão final.

### 9.7 Feedback

Permitir:

- gostei;
- não gostei;
- pedir ajuste;
- pedir comparação;
- acrescentar contexto;
- descartar;
- aprovar para implementação.

---

## 10. Promoção de insight para KPI

Ao aprovar uma análise, gerar especificação com:

- nome;
- pergunta de negócio;
- fontes;
- campos;
- conceitos;
- fórmula;
- unidade;
- granularidade;
- dimensões;
- filtros;
- exclusões;
- agregações;
- riscos;
- evidências;
- limitações;
- exemplos;
- histórico da conversa.

A especificação não publica o KPI automaticamente.

```text
Insight aprovado
    ↓
Especificação técnica
    ↓
Implementação
    ↓
Testes
    ↓
Validação
    ↓
Publicação
```

---

## 11. Cockpit executivo

### 11.1 Objetivo

Entregar visão única independentemente da origem: SLIN, Blue Yonder, outro WMS, banco, SharePoint, API, upload ou Pentaho.

### 11.2 Filtros globais

- período;
- filial;
- cliente.

Todos os cards, gráficos, tabelas e resumos devem obedecer aos filtros.

### 11.3 Visões obrigatórias

- consolidado;
- série histórica;
- comparação de filiais;
- comparação de clientes;
- ranking;
- participação;
- acumulado;
- variação mensal;
- qualidade e cobertura;
- drill-down;
- origem e linhagem.

### 11.4 KPIs iniciais

Começar somente com métricas confiáveis:

- peso bruto movimentado em toneladas;
- valor movimentado;
- quantidade de clientes;
- participação do maior cliente;
- quantidade de operações quando semanticamente válida;
- indicadores aprovados no Laboratório.

Não manter “volume total” com unidades incompatíveis.

### 11.5 Peso

A unidade executiva é tonelada.

Card:

```text
4,3 mil t
```

Detalhamento:

```text
4.281,7 toneladas
```

### 11.6 Qualidade e origem

Separar da área principal:

- arquivo;
- fonte;
- atualização;
- linhas processadas;
- linhas válidas e descartadas;
- cobertura;
- unidade;
- status do mapeamento;
- limitações.

---

## 12. Segurança e governança da IA

Antes de enviar dados:

- validar provedor aprovado;
- validar política corporativa;
- definir retenção e mascaramento;
- impedir envio de segredo;
- limitar dados pessoais e de clientes;
- limitar tamanho;
- preferir agregados;
- preferir perfil estruturado;
- usar amostra reduzida;
- registrar o que foi enviado;
- registrar modelo e parâmetros.

Fluxo preferencial:

```text
Backend calcula perfil e agregados
    ↓
IA recebe metadados, estatísticas e amostra segura
```

Proteger contra:

- prompt injection em células;
- conteúdo externo malicioso;
- HTML não escapado;
- URLs arbitrárias;
- comandos escondidos;
- exposição de token;
- acesso indevido;
- resposta da IA tratada como dado confiável.

---

## 13. Estrutura recomendada

Preservar a estrutura atual e fazer mudanças aditivas.

```text
backend/
├── catalogo/
│   ├── conceitos.py
│   ├── campos.py
│   ├── unidades.py
│   └── metricas.py
├── services/
│   ├── catalogo_semantico.py
│   ├── compatibilidade_medidas.py
│   ├── perfil_dados.py
│   ├── laboratorio_insights.py
│   ├── promocao_kpi.py
│   └── cockpit.py
├── routers/
│   ├── catalogo.py
│   ├── laboratorio.py
│   └── cockpit.py

frontend/
├── admin.html
├── nuvem.html
├── laboratorio.html
└── cockpit.html
```

Não mover arquivos apenas por estética. Não criar microsserviços nem framework frontend novo agora.

---

## 14. Macro-lotes

Ao final de cada macro-lote:

1. rodar suíte completa;
2. validar migrations;
3. informar arquivos;
4. informar decisões e riscos;
5. atualizar `docs/V1_PLANO.md`;
6. fazer commit isolado;
7. gerar relatório de verificação;
8. aguardar validação antes do próximo bloco.

### V1.0 — Transição para produto

- criar documentação;
- atualizar README e MEMORY;
- separar histórico;
- corrigir status da Nuvem;
- remover textos de POC das telas;
- ajustar peso para toneladas;
- reorganizar resumo executivo;
- separar qualidade e origem;
- revisar filial 016/RMSPIV;
- limpeza técnica.

### V1.1 — Catálogo semântico

- conceitos canônicos;
- campos de fonte;
- descrições;
- unidades e categorias;
- granularidade e dimensões;
- agregação e transformação;
- comparabilidade;
- versão, vigência e status;
- tela administrativa;
- migrations, seeds e testes.

### V1.2 — Compatibilidade de medidas

- conversões seguras;
- regras de compatibilidade;
- bloqueio de soma;
- mensagens;
- separação por unidade;
- unidade desconhecida;
- auditoria;
- testes.

Fora: cadastro de produto e conversões por SKU/embalagem.

### V1.3 — Persistência e série histórica

- processar competências históricas;
- persistir agregados;
- usar medidas recebidas e canônicas;
- preservar linhagem;
- suportar filial e cliente;
- consultas por intervalo;
- consolidação mensal e anual;
- idempotência;
- prevenção de dupla contagem;
- reprocessamento.

### V1.4 — Laboratório: seleção e perfil

- tela;
- seleção de fontes;
- filtros e limites;
- perfil determinístico;
- qualidade;
- unidades;
- duplicidades;
- período, filiais e clientes;
- chaves candidatas;
- prévia segura;
- sessão;
- testes.

### V1.5 — Laboratório: chat

- provedor aprovado;
- mensagens sugeridas;
- campo livre;
- chat;
- contexto controlado;
- histórico;
- feedback;
- rastreabilidade;
- limites;
- fallback;
- proteção contra prompt injection;
- testes mockados.

### V1.6 — Insight aprovado

- aprovar ou descartar;
- gerar especificação;
- registrar regra, unidade, granularidade, dimensões, fontes, limitações e evidências;
- auditoria.

### V1.7 — Cockpit executivo

- filtros de período, filial e cliente;
- cards;
- série histórica;
- comparação de filiais e clientes;
- ranking;
- participação;
- acumulado;
- variação;
- resumo executivo;
- qualidade;
- drill-down;
- linhagem;
- peso em toneladas;
- segurança e testes.

### V1.8 — Produção e entrega

- acesso;
- auditoria;
- logs;
- backup;
- limites e timeouts;
- falhas;
- integração e regressão;
- migrations em banco novo e existente;
- deploy;
- runbook e rollback;
- documentação;
- verificação independente;
- checklist;
- relatório final.

---

## 15. Blocos acelerados

```text
Bloco A: V1.0
Bloco B: V1.1 + V1.2
Bloco C: V1.3
Bloco D: V1.4
Bloco E: V1.5 + V1.6
Bloco F: V1.7
Bloco G: V1.8
```

O executor pode trabalhar por mais tempo dentro de um bloco. Não executar todos sem checkpoints.

---

## 16. Verificação independente

Após cada bloco, um segundo contexto/modelo deve verificar:

- escopo;
- arquitetura;
- migrations;
- compatibilidade;
- segurança;
- cálculos;
- unidades;
- filtros;
- qualidade;
- testes;
- documentação;
- código morto;
- dependências;
- regressões;
- exposição de dados;
- erros;
- rastreabilidade.

Criar:

```text
docs/V1_RELATORIO_VERIFICACAO.md
```

Status:

```text
atendido
parcial
não atendido
bloqueado
```

Criar futuramente, quando útil:

```text
scripts/verificar_v1.py
```

para checar testes, migrations, arquivos, rotas, documentação, variáveis, segredos, imports, endpoints sem teste, schema sem migration, HTML externo sem escape e URLs arbitrárias.

---

## 17. Regras para o Claude

1. Não reescrever o projeto.
2. Preservar compatibilidade.
3. Não criar microsserviços.
4. Não criar framework frontend novo.
5. Não criar cadastro de produtos.
6. Não converter caixa, palete ou unidade por SKU.
7. Não somar medidas incompatíveis.
8. Não publicar resposta da IA como KPI.
9. Não criar indicador sem unidade.
10. Não criar comparação sem granularidade.
11. Não inventar dados.
12. Não corrigir duplicidade por suposição.
13. Não concatenar `_f1/_f2/_f3` sem regra validada.
14. Não processar todas as famílias automaticamente.
15. Não criar alertas estatísticos sem histórico.
16. Não expor planilhas brutas publicamente.
17. Não logar segredos.
18. Não avançar de bloco sem fechar o atual.
19. Não remover histórico sem inventário.
20. Atualizar documentação junto com o código.

---

## 18. Entrega por bloco

Ao terminar cada bloco, apresentar:

- resumo;
- arquivos alterados;
- migrations;
- testes;
- validação manual;
- decisões;
- riscos;
- itens fora;
- verificação independente;
- hash e mensagem do commit.

---

## 19. Primeira instrução de execução

Antes de programar:

1. Leia todos os documentos obrigatórios;
2. Analise o repositório real;
3. Compare este direcionamento com a arquitetura atual;
4. Crie ou atualize:
   - `docs/V1_ESCOPO.md`;
   - `docs/V1_PLANO.md`;
   - `docs/V1_CRITERIOS_ACEITE.md`;
   - `docs/V1_ARQUITETURA.md`;
5. Apresente diagnóstico curto com ajustes, riscos, migrations, dependências, arquivos e ordem;
6. Execute apenas o **Bloco A — V1.0**;
7. Rode a suíte completa;
8. Gere relatório de verificação;
9. Faça commit;
10. Aguarde autorização antes do Bloco B.

Não iniciar o Bloco B na primeira execução.

---

## 20. Mensagem de produto

> A Nuvem IA conecta fontes diferentes, entende suas estruturas, padroniza conceitos, permite explorar oportunidades com rastreabilidade e publica indicadores corporativos confiáveis em uma visão única por período, filial e cliente.
