# Proposta V2 — Volumetria integrada, Cockpit visual e Laboratório ao final

**Projeto:** Nuvem  
**Data:** 05/08/2026  
**Objetivo deste documento:** registrar uma proposta de V2 para revisão técnica antes de implementar.  
**Status:** proposta para crítica/revisão, não implementação aprovada.

---

## 1. Contexto

A V1 estabilizou a base técnica do DataHub, incluindo:

- ingestão governada da família `ENTRADA_MERCADORIAS`;
- persistência de série histórica;
- de-para por origem qualificada;
- correção da identidade do arquivo por `item_id`;
- pendências visíveis para origens sem de-para;
- Cockpit inicial;
- Laboratório de Insights;
- linhagem;
- controles básicos de produção.

Apesar disso, o Cockpit atual ficou visualmente aquém do esperado para substituir ou competir com os Power BIs existentes.

Os prints dos Power BIs atuais de volumetria mostram que o usuário espera uma experiência com:

- evolução temporal clara;
- comparativo com ano anterior e/ou budget;
- ranking por unidade;
- decomposição por cliente/operação;
- tabela evolutiva com meses nas colunas;
- drill-down;
- leitura executiva rápida.

A expectativa não é copiar o Power BI visualmente, mas preservar a mesma mensagem de negócio e evoluir com o diferencial da IA.

---

## 2. Diagnóstico de produto

O Cockpit atual entrega uma base analítica, mas ainda não entrega a densidade visual de um dashboard executivo.

O Laboratório atual entrega análise textual, mas ainda não produz gráficos visuais úteis nem componentes que possam virar parte do Cockpit.

Além disso, a volumetria atual olha essencialmente para **entradas**. Para disputar a leitura dos Power BIs, a V2 precisa tratar volumetria como movimento logístico completo:

```text
entrada
saída
total movimentado
saldo entrada - saída
```

Portanto, esta proposta trata a V2 como uma evolução de produto e arquitetura, não como um ajuste cosmético.

---

## 3. Objetivo da V2

Construir uma camada analítica visual capaz de responder:

1. quanto entrou;
2. quanto saiu;
3. qual foi a volumetria total;
4. como evoluiu no tempo;
5. como compara com ano anterior e budget;
6. quais unidades puxaram o resultado;
7. quais clientes puxaram o resultado;
8. quais operações explicam a movimentação;
9. onde há crescimento, queda, concentração ou desvio;
10. quais dados estão pendentes, incompletos ou fora de cobertura;
11. qual número pode ser auditado até a origem;
12. posteriormente, qual visual a IA sugere para uma pergunta do usuário.

Frase-guia:

> Primeiro construir uma camada visual confiável de volumetria integrada, com entrada, saída, comparação e escala. Depois usar o Laboratório para explorar e gerar gráficos em cima dessa base já governada.

---

## 4. Decisão importante: Laboratório fica para o final da V2

A V2 **não** deve começar pelo Laboratório.

Motivo:

- se o Laboratório gerar gráficos antes de existir uma base visual e endpoints governados, ele vira um caminho paralelo e frágil;
- a IA não deve inventar dados nem montar cálculos livres;
- os gráficos do Laboratório devem consumir os mesmos endpoints e contratos do Cockpit;
- o maior ganho imediato para o usuário está no Cockpit visual e na integração de saídas.

Ordem revisada:

```text
1. Base de dados escalável
2. Integração de saídas
3. Volumetria integrada
4. Cockpit visual forte
5. Comparação com Power BI
6. Performance/operação
7. Laboratório com gráficos
```

---

## 5. Premissas da V2

### 5.1. Cockpit nunca lê Excel

Regra de ouro:

```text
Excel é ingestão.
Cockpit é consulta.
Laboratório visual é consulta governada.
```

O Cockpit deve consultar somente camada persistida/agregada.

### 5.2. IA não calcula número oficial

A IA pode:

- explicar;
- sugerir gráfico;
- sugerir investigação;
- destacar anomalia;
- montar narrativa.

A IA não pode:

- inventar número;
- somar coluna não governada;
- usar Excel bruto para gráfico;
- gerar visual a partir de dado não validado;
- substituir cálculo governado do backend.

### 5.3. Volumetria precisa de direção

A V2 precisa representar:

```text
direcao = entrada | saida
```

Essa dimensão será central para todos os gráficos.

### 5.4. Escalabilidade é requisito de primeira ordem

A ferramenta deve ser preparada para crescer em:

- número de arquivos;
- número de unidades;
- número de clientes;
- histórico mensal;
- quantidade de gráficos;
- consultas simultâneas;
- volume de dados persistidos.

---

## 6. Fontes candidatas para volumetria

### Entrada

Fonte já integrada:

```text
ENTRADA_MERCADORIAS
```

Possível fonte complementar:

```text
GUIAS_ENTRADA
```

### Saída

Fontes candidatas:

```text
SAIDA_MERCADORIAS
GUIAS_SAIDA
CORTES_PRODUTOS
```

A V2 precisa decidir qual família de saída será a fonte oficial inicial.

Recomendação inicial:

```text
Entrada oficial:
- ENTRADA_MERCADORIAS

Saída oficial inicial:
- SAIDA_MERCADORIAS
```

Essa escolha precisa ser validada contra as colunas reais, cobertura, granularidade e proximidade com o Power BI.

---

## 7. Modelo conceitual recomendado

A V2 deve introduzir, pelo menos conceitualmente, um modelo comum de movimento logístico.

```text
movimento_logistico
- direcao
- unidade_origem
- filial_origem
- armazem_id
- cliente_id
- competencia
- data_movimento
- operacao
- peso_bruto
- peso_liquido
- valor_mercadoria
- quantidade_registros
- familia_origem
- arquivo_origem
- execucao_id
```

Não necessariamente é preciso criar essa tabela exata no primeiro commit, mas a arquitetura deve convergir para essa semântica.

Dimensões mínimas para gráficos:

```text
direcao
familia
unidade
filial/armazem
cliente
operacao
competencia
```

---

## 8. Decisão técnica em aberto: como persistir entrada/saída

### Opção A — Métricas separadas

Criar métricas diferentes:

```text
peso_bruto_entrada
peso_bruto_saida
valor_mercadoria_entrada
valor_mercadoria_saida
```

Vantagens:

- menor mudança de schema;
- mais rápido de implementar;
- encaixa no modelo atual de `medidas`.

Problemas:

- explode catálogo de métricas;
- dificulta total/saldo;
- dificulta reaproveitar filtros;
- tende a duplicar código entre entrada e saída.

### Opção B — Dimensão `direcao`

Manter métrica:

```text
peso_bruto_movimentado
valor_mercadoria_movimentada
registros_movimentacao
```

E diferenciar por:

```text
direcao = entrada | saida
```

Vantagens:

- modelo mais escalável;
- facilita entrada, saída, total e saldo;
- reduz duplicação de métricas;
- combina melhor com gráficos dinâmicos.

Problemas:

- exige migration;
- exige revisar constraints/índices;
- exige revisar consultas atuais;
- exige cuidado com compatibilidade do Cockpit e série.

Recomendação preliminar:

> Para a V2, preferir a Opção B, porque a V2 tem objetivo explícito de escalar. Se o custo de migration for alto demais, avaliar uma etapa intermediária, mas sem perder a direção arquitetural.

---

## 9. Agregação materializada

Para escalar, a V2 deve considerar uma camada agregada.

Exemplo:

```text
fato_volumetria_mensal
- competencia
- armazem_id
- cliente_id
- operacao
- direcao
- peso_bruto
- peso_liquido
- valor_mercadoria
- registros
- atualizado_em
```

Essa camada pode ser:

- uma tabela alimentada no processamento;
- uma materialized view;
- ou uma tabela derivada reconstruível.

Recomendação:

> Começar com tabela agregada reconstruível e alimentada por processamento, porque o Cockpit precisa responder rápido e o volume tende a crescer.

---

## 10. Índices mínimos

Índices candidatos:

```sql
(direcao, competencia)
(armazem_id, direcao, competencia)
(cliente_id, direcao, competencia)
(competencia, armazem_id)
(competencia, cliente_id)
(operacao, direcao, competencia)
```

Para `medidas`, caso `direcao` entre ali, avaliar também:

```sql
(metrica_id, direcao, competencia)
(metrica_id, armazem_id, direcao, competencia)
(metrica_id, cliente_id, direcao, competencia)
```

---

## 11. V2.1 — Fundação escalável de volumetria

Objetivo:

> Preparar a base para suportar volumetria integrada e consultas rápidas.

Inclui:

- definir onde a dimensão `direcao` será persistida;
- revisar `medidas`, `medidas_recebidas`, `processamentos_datahub` e agregações;
- criar ou preparar `fato_volumetria_mensal`;
- criar índices;
- garantir que o Cockpit não consulte Excel;
- garantir que gráficos usem apenas dados persistidos;
- manter linhagem até arquivo/execução;
- criar script readonly de verificação DataHub/volumetria em produção.

Entregáveis:

- migration de base;
- documentação de arquitetura;
- testes de compatibilidade;
- script de verificação somente leitura;
- critérios de aceite.

Critérios de aceite:

1. entrada e saída podem coexistir sem duplicar métrica desnecessariamente;
2. consultas por período/unidade/cliente/direção são indexadas;
3. camada agregada pode ser reconstruída;
4. Cockpit consulta camada persistida/agregada;
5. linhagem segue preservada;
6. não há leitura de Excel em endpoint de dashboard.

---

## 12. V2.2 — Integração das saídas

Objetivo:

> Parar de olhar apenas entradas e trazer a primeira fonte oficial de saída.

Fase de diagnóstico:

- perfilar `SAIDA_MERCADORIAS`;
- perfilar `GUIAS_SAIDA`;
- perfilar `CORTES_PRODUTOS`;
- identificar aba, cabeçalho, colunas, competência, cliente, CNPJ, operação, peso bruto, peso líquido e valor;
- identificar diferenças por unidade;
- identificar se RJ/CWB3/SANCA têm layout diferente;
- comparar com Power BI para escolher fonte oficial inicial.

Entregável documental:

```text
docs/FONTES_DATAHUB_SAIDAS.md
```

Implementação:

- criar leitor controlado da família escolhida;
- usar `item_id`;
- derivar unidade pelo caminho;
- resolver de-para antes do download;
- registrar pendência visível;
- validar cabeçalho;
- não auto-cadastrar cliente;
- gravar direção `saida`;
- preservar execução e arquivo de origem;
- criar testes com fixtures.

Critérios de aceite:

1. fonte oficial de saída escolhida e documentada;
2. arquivo sem de-para vira pendência antes do download;
3. layout incompatível vira erro claro;
4. saída grava na mesma semântica da entrada;
5. saída aparece nos agregados mensais;
6. saída não contamina entrada.

---

## 13. V2.3 — Volumetria integrada

Objetivo:

> Criar as consultas de negócio para entrada, saída, total e saldo.

Métricas/visões:

```text
peso_bruto_entrada
peso_bruto_saida
peso_bruto_total
saldo_peso_bruto
valor_entrada
valor_saida
valor_total
registros_entrada
registros_saida
clientes_atendidos
participacao_unidade
participacao_cliente
variacao_vs_ano_anterior
```

Observação:

Mesmo que a persistência use `direcao`, os retornos dos endpoints podem expor campos como `entrada`, `saida`, `total` e `saldo`.

Critérios de aceite:

1. consulta retorna entrada e saída por mês;
2. consulta retorna total movimentado;
3. consulta retorna saldo entrada - saída;
4. consulta retorna comparação com ano anterior;
5. consulta retorna ranking por unidade;
6. consulta retorna ranking por cliente;
7. consulta declara limitações de dados pendentes.

---

## 14. V2.4 — Cockpit visual de Volumetria

Objetivo:

> Substituir o Cockpit curto atual por uma tela visualmente forte, inspirada na mensagem dos Power BIs, mas sem copiar visualmente.

### 14.1. Filtros globais

```text
Unidade
Direção: Entrada | Saída | Total | Entrada x Saída
Cliente
Operação
Ano
Mês
Visão: Mensal | Acumulado
Comparativo: Atual | Ano anterior | Budget
```

### 14.2. Cards executivos

```text
Entrada
Saída
Total movimentado
Saldo
Variação vs ano anterior
Clientes atendidos
Unidades com movimento
Pendências de dados
```

### 14.3. Gráfico principal — evolução temporal

Tipo:

```text
linha ou área
```

Séries:

```text
Atual
Ano anterior
Budget, se existir
Entrada
Saída
Saldo
```

Modos:

```text
Mensal
Acumulado
```

Mensagem:

> A volumetria está subindo ou caindo? Está acima ou abaixo do ano anterior? Entrada e saída estão equilibradas?

### 14.4. Ranking por unidade

Tipo:

```text
barras horizontais ou verticais
```

Dimensões:

```text
unidade
```

Medidas:

```text
entrada
saida
total
saldo
participacao
variacao
```

Mensagem:

> Quais unidades puxam o resultado?

### 14.5. Ranking por cliente

Tipo:

```text
barras horizontais ou Pareto
```

Com:

```text
Top N
Outros agregado
participação %
variação vs ano anterior
```

Mensagem:

> Quais clientes explicam a maior parte da volumetria?

### 14.6. Entrada x Saída

Tipo:

```text
barras agrupadas, linhas ou combo
```

Mensagem:

> A operação está equilibrada? Há mais entrada que saída? Em qual mês?

### 14.7. Matriz evolutiva

Linhas:

```text
Unidade
Cliente
Operação
```

Colunas:

```text
jan/26
fev/26
mar/26
...
Total
Var. vs ano anterior
Var. %
```

Funcionalidades:

```text
expandir unidade -> cliente -> operação
ordenar por total
ordenar por variação
heatmap leve
exportar CSV
abrir linhagem
```

Critérios de aceite:

1. tela passa a mensagem de evolução;
2. tela passa a mensagem de comparação;
3. tela mostra decomposição por unidade;
4. tela mostra decomposição por cliente;
5. tela tem matriz de conferência;
6. filtros globais afetam todos os visuais;
7. visual não depende de Excel ao vivo;
8. performance aceitável com histórico real.

---

## 15. V2.5 — Comparação com Power BI

Objetivo:

> Validar se a Nuvem se aproxima da leitura do Power BI atual e explicar diferenças.

Escopo:

- escolher um período de referência;
- comparar total mensal;
- comparar acumulado;
- comparar ranking por unidade;
- comparar ranking por cliente;
- comparar entrada/saída quando houver;
- registrar diferenças conhecidas.

Diferenças aceitáveis podem vir de:

```text
fonte diferente
filtro diferente
competência diferente
cliente sem de-para
unidade sem de-para
família ainda não integrada
layout rejeitado
campo de peso diferente
critério diferente de competência
```

Entregável:

```text
docs/CONCILIACAO_POWERBI_V2.md
```

Critérios de aceite:

1. há tabela de comparação Nuvem x Power BI;
2. diferenças relevantes têm explicação;
3. diferenças sem explicação viram pendência;
4. números não precisam bater 100%, mas precisam ser rastreáveis.

---

## 16. V2.6 — Performance, operação e escala

Objetivo:

> Garantir que a ferramenta continue usável conforme o volume crescer.

Inclui:

- cache de consultas pesadas;
- TTL curto para dashboard;
- invalidação após processamento;
- top N com bucket `Outros`;
- paginação da matriz;
- drill-down sob demanda;
- logs de tempo de consulta;
- limites de resposta;
- script readonly pós-deploy;
- monitoramento de health;
- backup externo validado;
- teste de restore documentado.

Possível estratégia de cache inicial:

```text
cache em memória por filtro/período
TTL: 5 a 15 minutos
limitação documentada: não serve múltiplos workers de forma compartilhada
```

Evolução futura:

```text
Redis ou cache externo
```

Critérios de aceite:

1. ranking não retorna milhares de clientes de uma vez;
2. matriz é paginada ou limitada;
3. consultas lentas são logadas;
4. cache é invalidado quando processa novos dados;
5. existe verificação readonly pós-deploy;
6. backup/restore tem evidência operacional.

---

## 17. V2.7 — Laboratório com gráficos

Objetivo:

> Só depois do Cockpit e dos endpoints estabilizados, permitir que a IA sugira e renderize gráficos governados.

### 17.1. Contrato de visualização

A IA pode sugerir:

```text
tipo de gráfico
métrica
dimensão
filtros
comparativo
ordenação
título
explicação
```

Mas o backend deve validar.

Exemplo conceitual:

```json
{
  "tipo": "barra_ranking",
  "metrica": "peso_bruto",
  "direcao": "saida",
  "dimensao": "unidade",
  "comparativo": "ano_anterior",
  "periodo": {
    "de": "2026-01",
    "ate": "2026-08"
  },
  "ordenar_por": "variacao_abs",
  "limite": 10
}
```

### 17.2. Tipos permitidos no início

```text
linha_temporal
barra_ranking
barra_comparativa
entrada_saida
matriz
pareto_cliente
```

### 17.3. Fluxo esperado

```text
Usuário pergunta
IA interpreta intenção
IA sugere visualização
Backend valida contrato
Backend consulta endpoint governado
Frontend renderiza com ECharts
Usuário pode fixar ou abrir no Cockpit
```

### 17.4. Botões úteis

```text
Fixar no Cockpit
Abrir no Cockpit
Abrir matriz
Abrir linhagem
Comparar com ano anterior
Comparar entrada x saída
```

Critérios de aceite:

1. IA não inventa número;
2. visual usa endpoint governado;
3. visualização inválida é recusada;
4. o usuário consegue ver gráfico no Laboratório;
5. gráfico pode ser aberto no Cockpit;
6. insight aprovado pode virar widget no Cockpit, se essa parte for incluída.

---

## 18. Endpoints sugeridos

### Resumo

```text
GET /api/admin/cockpit/volumetria/resumo
```

Parâmetros:

```text
de
ate
unidade
filial
cliente
direcao
operacao
comparativo
```

### Evolução

```text
GET /api/admin/cockpit/volumetria/evolucao
```

Retorna:

```text
mensal
acumulado
ano_anterior
budget
entrada
saida
saldo
```

### Ranking

```text
GET /api/admin/cockpit/volumetria/ranking
```

Parâmetros:

```text
dimensao=unidade|cliente|operacao
direcao=entrada|saida|total
limite=10|20|50
```

### Matriz

```text
GET /api/admin/cockpit/volumetria/matriz
```

Retorna:

```text
linhas
colunas_meses
totais
variacoes
paginacao
```

### Visualização do Laboratório

```text
POST /api/admin/laboratorio/visualizacao
```

Somente na V2.7.

---

## 19. Ajustes residuais da V1 que entram na V2

Além do redesign, aproveitar a V2 para endurecer pontos já identificados.

### 19.1. Script readonly DataHub/produção

Criar script que não grava nada e valida:

```text
alembic em head
constraint UNIQUE(item_id)
depara_armazem sem códigos nus para sharepoint_datahub
RMSPII/001, RMSPII/015, RMSPII/016 existentes
001/015/016 nus ausentes
última sincronização do DataHub
contagem de arquivos por unidade
candidatos de entrada e saída
pendências RJ/CWB3/SANCA/RMSPII/002 visíveis
nenhum processamento com unidade NULL, salvo arquivos raiz
```

### 19.2. Não expor `processar_arquivo` isolado sem guarda

Se no futuro houver botão para processar arquivo individual, ele deve passar por guarda de colisão.

### 19.3. Família nova/não integrada

Exibir estado explícito para famílias novas ou variantes não integradas, por exemplo:

```text
família conhecida não integrada
família nova detectada
layout não homologado
origem sem de-para
```

Isso inclui casos como `ENTRADA_MERCADORIAS (UA)`.

---

## 20. Backlog resumido

### V2.1 — Fundação escalável

- decidir persistência de `direcao`;
- criar migration;
- criar agregação mensal;
- índices;
- script readonly;
- documentação.

### V2.2 — Saídas

- perfilar famílias de saída;
- escolher fonte oficial;
- implementar leitor;
- persistir direção `saida`;
- testes.

### V2.3 — Volumetria integrada

- endpoints de entrada/saída/total/saldo;
- ano anterior;
- ranking;
- matriz.

### V2.4 — Cockpit visual

- cards;
- evolução;
- ranking unidade;
- ranking cliente;
- entrada x saída;
- matriz;
- filtros.

### V2.5 — Conciliação Power BI

- comparar números;
- explicar diferenças;
- registrar pendências.

### V2.6 — Escala/operação

- cache;
- paginação;
- top N;
- logs de performance;
- backup/restore;
- verificação pós-deploy.

### V2.7 — Laboratório com gráficos

- contrato de visualização;
- IA sugere;
- backend valida;
- frontend renderiza;
- fixar/abrir no Cockpit.

---

## 21. Perguntas para revisão do Claude

1. A V2 deve mesmo introduzir `direcao` como dimensão, ou é melhor começar com métricas separadas para reduzir risco?
2. A agregação mensal deve ser tabela física, materialized view ou consulta sobre `medidas` com índices?
3. Qual família de saída parece mais adequada como fonte oficial inicial: `SAIDA_MERCADORIAS`, `GUIAS_SAIDA` ou `CORTES_PRODUTOS`?
4. Vale criar um modelo genérico de `movimento_logistico` agora ou apenas preparar os contratos sem tabela nova?
5. Os endpoints sugeridos estão no lugar certo ou deveriam reaproveitar mais o `serie_datahub` atual?
6. O Cockpit deve substituir o atual `/cockpit` ou criar uma rota nova, por exemplo `/cockpit/volumetria`?
7. O que precisa ser bloqueador antes de processar saídas em produção?
8. Quais partes deste plano estão grandes demais para um primeiro lote?
9. Qual é o menor lote que já melhora muito a percepção visual do usuário?
10. O Laboratório no final da V2 faz sentido, ou há algum pedaço pequeno dele que deveria entrar antes?

---

## 22. Decisão preliminar

A decisão preliminar é:

> Tratar a V2 como uma evolução de volumetria integrada e visualização executiva, priorizando base escalável, saídas e Cockpit forte. O Laboratório com gráficos fica para o final, consumindo os mesmos contratos governados do Cockpit, para evitar caminhos paralelos e números inventados.

Nada deve ser implementado antes da revisão crítica deste plano.
