# Decisões e recomendações — identidade e linhagem do DataHub

**Data:** 02/08/2026  
**Contexto:** reestruturação não anunciada da árvore do SharePoint DataHub entre 29 e 31/07/2026.

---

## 0. O que foi efetivamente construído (02/ago/2026)

> Este documento é a **análise** que originou o lote de correção, preservada como
> registro do raciocínio. O que foi implementado é um recorte dele. Onde os dois
> divergirem, vale o código e o `docs/V1_PLANO.md`.

**Aceito e implementado** (migration `0008_identidade_datahub`):

- seção 3.1/3.3 — a identidade do arquivo deixa de ser o nome e passa a ser o
  `item_id` do Graph; caminho e nome viram atributos mutáveis;
- seção 2.1 — o de-para passa a ser chaveado por unidade + código, na forma
  qualificada `RMSPII/001` (**sem** a coluna `unidade_origem` da seção 3.2: o campo
  `armazem_na_fonte` já é texto livre);
- seção 2.5 — todo arquivo da família termina com um estado explícito; a RJ deixou
  de sumir em silêncio (padrão de nome aceita hífen);
- seção 2.4 — o escopo da remoção de órfãs ficou correto **sem redesenho**, porque o
  armazém já distingue as unidades, mais uma guarda que aborta a rodada em colisão;
- seção 10 — critérios de aceite 1 a 8 e 11.

**Cortado, com o motivo:**

- **Seções 6 e 9/P3 (invalidação, incidente `INC-DATAHUB-*`, máquina de eventos,
  compensação)** — não há histórico a reparar. A VM está em `0004_catalogo_metricas`,
  as migrations do Bloco C nunca subiram e "Processar arquivos" nunca rodou em
  produção: a contaminação era risco a prevenir, não dano ocorrido. A premissa da
  seção 6.4 ("pode não ser possível provar a origem linha a linha") também não se
  sustenta — cada recebida aponta para uma execução que grava o caminho completo.
- **Seção 3.2, tabela `arquivo_datahub`** — `item_id` já existia como coluna, e a
  separação arquivo × execução já existe (`execucoes` guarda o histórico de rodadas;
  `processamentos_datahub` guarda o estado corrente). `hash_conteudo` e `ativo`
  resolvem problemas que não são o defeito de hoje.
- **Seção 2.3, família na partição lógica** — só uma família emite estas métricas, e
  a `ENTRADA_MERCADORIAS (UA)` não casa no padrão de nome. Fica registrado no código
  que uma segunda família emitindo as mesmas métricas exige a dimensão do produtor.
- **Seção 2.6, leitor da variante RJ de 18 colunas** — a RJ não tem de-para e isso é
  decisão humana pendente; construir o leitor antes seria construir para um caso
  talvez não autorizado. O bloqueador real era o silêncio, e esse foi resolvido.
- **Seção 7, allowlist + dry-run + snapshot** — arnês para processar *antes* da
  correção. Como a correção veio primeiro, não há a execução de risco que ele
  protegeria.
- **Critérios de aceite 9 e 10** — caem junto com a seção 6.

**Bloco E** — mantido o bloqueio da seção 5, com o critério mais fino: o impedimento é
consumir a **série persistida**; o Laboratório lê o arquivo direto e não passa por
`medidas`. Condição obrigatória: o contexto enviado à IA carrega **unidade junto da
filial**, nunca só "filial 001".

---

## 1. Resumo executivo

A reestruturação da origem invalidou a premissa de que existe apenas um arquivo por combinação de filial e competência, identificável unicamente pelo nome.

O defeito atual permite que arquivos fisicamente distintos, pertencentes a unidades diferentes, disputem o mesmo registro de processamento, apaguem resultados um do outro e contaminem de forma permanente a tabela append-only de auditoria `medidas_recebidas`.

A decisão recomendada é:

> O nome do arquivo deixa de ser sua identidade. Cada arquivo passa a ter uma identidade técnica própria, preferencialmente correlacionada ao `item_id` do Microsoft Graph. Unidade, família, filial e competência tornam-se atributos explícitos da partição lógica de negócio e passam a compor o escopo de de-para, substituição, limpeza e reconciliação.

A correção deve ser concluída antes da liberação do Bloco E sobre dados reais.

---

## 2. Diagnóstico

O encadeamento identificado está correto:

1. `processamentos_datahub` possui `UNIQUE(arquivo)`, usando apenas o nome como chave.
2. Arquivos com o mesmo nome em unidades diferentes disputam o mesmo registro.
3. `_ja_processado` compara `modificado_em` contra esse registro compartilhado.
4. Como os metadados dos dois arquivos diferem, nenhum permanece reconhecido como inalterado.
5. Os arquivos são reprocessados a cada rodada.
6. `_remover_celulas_orfas` atua sobre um escopo que não distingue corretamente a origem.
7. Cada processamento pode remover células emitidas pelo outro.
8. `medidas_recebidas`, por ser append-only, preserva linhas da CWB3 atribuídas incorretamente ao armazém da RMSPII.
9. A ordenação por caminho mascara o defeito por um efeito acidental de `last-write-wins`.

### Consequências adicionais

#### 2.1. O problema não se limita à filial `001`

O de-para atual já não representa o domínio real.

A chave:

```text
conector + código_filial
```

deixa de ser válida quando o mesmo código pode existir em unidades distintas.

A chave mínima passa a ser:

```text
conector + unidade_origem + código_filial
```

#### 2.2. Unidade, filial e competência não identificam um arquivo físico

A combinação:

```text
unidade + filial + competência
```

identifica uma partição lógica de dados, não necessariamente um arquivo.

Podem existir:

- reenvios;
- correções;
- versões simultâneas;
- arquivos parciais;
- duplicatas;
- recriações do mesmo conteúdo;
- múltiplas famílias na mesma filial e competência.

Portanto, essa combinação não deve ser usada isoladamente como identidade única do arquivo.

#### 2.3. A família deve entrar no escopo lógico

A partição lógica recomendada é:

```text
conector + unidade + família + filial + competência
```

Sem a família, processamentos de origens semanticamente diferentes ainda podem interferir entre si.

#### 2.4. `_remover_celulas_orfas` precisa ser redesenhado

A remoção não deve ocorrer apenas por:

```text
métrica + armazém + competência
```

Ela deve ser restrita à contribuição anterior do mesmo produtor ou da mesma partição lógica.

Caso contrário, arquivos legítimos e complementares podem apagar resultados uns dos outros.

#### 2.5. Arquivos fora do regex não podem desaparecer silenciosamente

Todo arquivo inventariado deve terminar em um estado explícito:

- processado;
- pendente de de-para;
- layout incompatível;
- nome incompatível com família conhecida;
- ignorado por regra explícita;
- desconhecido;
- erro de processamento.

“Não casou no regex” não pode equivaler a “não existe”.

#### 2.6. A variante da RJ exige tratamento formal de layout

A diferença entre 18 e 20 colunas não deve ser tratada apenas relaxando o filtro.

Devem existir variantes de layout reconhecidas, por exemplo:

```text
ENTRADA_MERCADORIAS v1
- 20 colunas
- inclui Cliente
- inclui Cliente CNPJ

ENTRADA_MERCADORIAS v2-RJ
- 18 colunas
- não inclui Cliente
- não inclui Cliente CNPJ
```

A leitura deve ser orientada por rótulos semânticos ou por um esquema versionado, não por posição absoluta sem validação.

---

## 3. Decisão arquitetural

### 3.1. Opção escolhida

Adotar a opção **(c)** como direção de domínio, ampliada por uma identidade técnica própria para o arquivo.

A opção (c) não deve ser usada isoladamente como identidade física.

### 3.2. Modelo recomendado

#### Arquivo físico

```text
arquivo_datahub
- id
- conector_id
- item_id_graph
- caminho_atual
- nome_atual
- unidade_origem
- familia
- filial_origem
- competencia
- tamanho
- modificado_em
- hash_conteudo
- ativo
- criado_em
- atualizado_em
```

#### Execução de processamento

```text
processamento_datahub
- id
- arquivo_datahub_id
- iniciado_em
- concluido_em
- status
- versao_leitor
- fingerprint_processado
- erro
```

#### Partição lógica

```text
conector_id
+ unidade
+ familia
+ filial
+ competencia
```

#### De-para de filial

```text
conector_id
+ unidade_origem
+ filial_origem
```

### 3.3. Papel de cada identificador

#### `item_id` do Graph

Usar como identificador externo preferencial para acompanhar:

- movimentação;
- renomeação;
- mudança de caminho.

Não usar como único conceito de negócio.

#### Caminho completo

Usar como:

- atributo observável;
- informação de diagnóstico;
- fallback temporário;
- apoio à reconciliação.

Não usar como identidade arquitetural definitiva.

#### Hash de conteúdo

Usar como apoio para:

- detectar recriações;
- identificar duplicatas;
- reconciliar item novo com conteúdo já conhecido;
- diferenciar versões.

O hash não precisa ser calculado obrigatoriamente em toda listagem, mas deve estar disponível em fluxos de reconciliação e ingestão.

---

## 4. Motivos para rejeitar as demais opções isoladas

### 4.1. Caminho completo

Vantagem:

- resolve rapidamente a colisão atual.

Problemas:

- muda quando a origem reorganiza a árvore;
- transforma movimentação em arquivo novo;
- causa reprocessamento integral;
- dificulta continuidade histórica;
- pode gerar duplicações;
- acopla o domínio à organização física da fonte.

Conclusão:

> Aceitável apenas como hotfix temporário ou fallback.

### 4.2. Apenas `item_id` do Graph

Vantagens:

- permanece estável em movimentações;
- permanece estável em renomeações.

Problemas:

- muda quando o arquivo é recriado;
- não expressa unidade, filial, família ou competência;
- não resolve o de-para;
- não define o escopo da limpeza;
- pode não existir em outras fontes futuras.

Conclusão:

> Deve integrar a identidade técnica, mas não substituir o modelo de domínio.

### 4.3. Apenas unidade + filial + competência

Problemas:

- não diferencia famílias;
- não diferencia reenvios;
- não diferencia correções;
- não diferencia arquivos parciais;
- não diferencia versões ou duplicatas;
- confunde arquivo físico com partição lógica.

Conclusão:

> Deve ser ampliada com família e conector e usada como escopo lógico, não como chave física única.

---

## 5. Relação com o Bloco E

A correção deve acontecer antes da liberação do Bloco E sobre dados reais.

### Motivo

O Bloco E aumenta a superfície de consumo e a confiança aparente nos dados.

Com a situação atual, o chat pode:

- atribuir dados de Curitiba à RMSPII;
- comparar unidades contaminadas;
- justificar respostas com uma linhagem falsa;
- apresentar como fato uma série aparentemente correta;
- propagar o erro em resumos, análises e exportações.

### Classificação

- identidade e colisão: bloqueador de integridade;
- RJ ignorada silenciosamente: bloqueador de completude;
- layout de 18 colunas: bloqueador de ingestão correta;
- linhagem contaminada: bloqueador de auditabilidade.

### Trabalho do Bloco E que pode continuar

Pode avançar de forma isolada em:

- interface;
- roteamento;
- contratos;
- testes com fixtures;
- prompts;
- infraestrutura;
- dados sintéticos.

Não deve ser liberada consulta sobre o DataHub real antes da correção e da reconciliação.

---

## 6. Tratamento de `medidas_recebidas`

Como `medidas_recebidas` é append-only e representa auditoria e linhagem, as linhas antigas não devem ser alteradas silenciosamente.

### 6.1. Estratégia recomendada

Adotar invalidação explícita e compensação.

Exemplo:

```text
medida_recebida_invalidacao
- id
- medida_recebida_id
- invalidada_em
- motivo
- incidente_id
- substituida_por_id
- execucao_corretiva_id
```

Alternativa baseada em eventos:

```text
tipo_evento
- RECEBIDA
- INVALIDADA
- SUBSTITUIDA
```

### 6.2. Processo corretivo

1. Identificar as linhas afetadas.
2. Registrar invalidação explícita.
3. Associar a invalidação a um incidente de dados.
4. Reprocessar os arquivos sob a identidade correta.
5. Inserir novas linhas append-only com a origem e o armazém corretos.
6. Reconstruir as projeções materializadas usando apenas eventos válidos.
7. Relacionar, quando possível, cada linha inválida à sua substituição.

### 6.3. Evidências para localizar contaminação

Usar o máximo de informações disponíveis:

- nome do arquivo;
- caminho;
- unidade;
- competência;
- filial;
- horário da execução;
- lote;
- `processamento_id`;
- quantidade de linhas;
- tamanho;
- data de modificação;
- hash;
- valores registrados.

### 6.4. Caso não seja possível provar a origem linha a linha

Se a tabela não guarda informações suficientes, invalidar todo o conjunto ambíguo:

```text
família: ENTRADA_MERCADORIAS
filial: 001
competências: 2601 a 2607
execuções: intervalo afetado
```

Depois, reconstruir o conjunto a partir das fontes.

É preferível invalidar e reconstruir um conjunto maior do que manter linhas cuja proveniência não pode ser provada.

### 6.5. Registro formal do incidente

Criar um identificador de incidente, por exemplo:

```text
INC-DATAHUB-2026-07-UNIDADES
```

Associar ao incidente:

- migrations;
- arquivos envolvidos;
- linhas invalidadas;
- execuções corretivas;
- período afetado;
- decisões técnicas;
- relatório de reconciliação.

---

## 7. Recorte operacional mínimo seguro

### Decisão imediata

> Não executar `processar_todos` na árvore atual com o código existente.

### 7.1. Recorte permitido

Executar apenas uma allowlist explícita:

```text
unidade:
- RMSPII

filiais:
- 001
- 002
- 015
- 016

famílias:
- somente as homologadas antes da reestruturação

família bloqueada:
- ENTRADA_MERCADORIAS
```

### 7.2. Controles obrigatórios

- filtrar por allowlist, não por blacklist;
- bloquear `ENTRADA_MERCADORIAS`;
- executar dry-run antes da gravação;
- emitir inventário completo do que seria processado;
- falhar ao encontrar arquivos fora do recorte esperado;
- não ignorar arquivos desconhecidos silenciosamente;
- desabilitar remoção de órfãs em escopos não isolados;
- criar snapshot do banco antes da execução;
- guardar snapshot do inventário da árvore;
- registrar o commit e a configuração usados na execução.

### 7.3. Por que bloquear também RMSPII/ENTRADA_MERCADORIAS

Mesmo processando apenas RMSPII, o banco continuaria consolidando uma identidade errada baseada no nome.

Quando CWB3 fosse processada no futuro, a disputa reapareceria.

A família só deve ser liberada depois de um hotfix mínimo de identidade e isolamento por unidade.

---

## 8. Hotfix mínimo, caso o processamento não possa esperar

Antes da migration definitiva, aplicar uma chave temporária que diferencie a origem física.

Exemplos:

```text
UNIQUE(conector_id, unidade_origem, caminho_relativo)
```

ou, como solução ainda mais temporária:

```text
UNIQUE(conector_id, caminho_completo)
```

### Alterações mínimas associadas

- `_ja_processado` deve consultar pela nova chave;
- o processamento deve receber `unidade_origem` explicitamente;
- o de-para deve considerar unidade;
- CWB3 não pode resolver para o armazém da RMSPII;
- `_remover_celulas_orfas` deve ser desabilitado para a família ou restringido por partição lógica;
- RJ deve permanecer bloqueada até o leitor de 18 colunas estar homologado;
- colisões entre unidades devem abortar a execução.

Esse hotfix reduz o risco imediato, mas não substitui a migration definitiva.

---

## 9. Ordem recomendada de execução

### P0 — impedir dano

- bloquear `processar_todos`;
- criar allowlist de RMSPII;
- bloquear `ENTRADA_MERCADORIAS`;
- detectar colisões entre unidades;
- abortar em colisão;
- impedir ignorados silenciosos.

### P1 — corrigir o modelo

- criar identidade técnica do arquivo;
- persistir `item_id` do Graph;
- introduzir unidade e família;
- separar arquivo, execução e partição lógica;
- alterar o de-para para unidade + filial;
- revisar `_remover_celulas_orfas`.

### P2 — corrigir a ingestão

- aceitar códigos de filial compostos;
- transformar ausência de de-para em pendência explícita;
- implementar layout RJ de 18 colunas;
- classificar todos os arquivos inventariados;
- adicionar validação semântica de cabeçalhos.

### P3 — reparar o histórico

- mapear linhas afetadas;
- registrar incidente;
- invalidar eventos contaminados;
- reprocessar fontes;
- reconstruir projeções;
- emitir relatório de reconciliação.

### P4 — liberar Bloco E

Liberar apenas depois de:

- testes de colisão;
- testes de completude;
- testes de isolamento entre unidades;
- testes de reprocessamento;
- testes de linhagem;
- reconciliação do histórico.

---

## 10. Critérios de aceite

A correção deve demonstrar que:

1. Dois arquivos com o mesmo nome em unidades diferentes possuem identidades distintas.
2. Movimentar ou renomear um arquivo no SharePoint não cria uma nova entidade quando o `item_id` permanece igual.
3. Recriar um arquivo não sobrescreve silenciosamente o histórico anterior.
4. O mesmo código de filial pode existir em unidades diferentes sem colisão de de-para.
5. `_ja_processado` reconhece corretamente arquivos inalterados.
6. Um processamento não remove células pertencentes a outra unidade ou partição.
7. Arquivos da RJ aparecem como processados, pendentes ou rejeitados, nunca invisíveis.
8. O layout de 18 colunas é identificado explicitamente.
9. Linhas contaminadas de `medidas_recebidas` permanecem auditáveis, mas são marcadas como inválidas.
10. As projeções atuais podem ser reconstruídas deterministicamente.
11. `processar_todos` aborta diante de colisão ou arquivo não classificado.
12. O Bloco E consulta apenas dados cuja linhagem esteja válida.

---

## 11. Decisão final

### Arquitetura

> A identidade técnica de um arquivo não será mais seu nome. Cada item terá uma chave interna e, quando disponível, será correlacionado pelo `item_id` do Microsoft Graph. Unidade, família, filial e competência serão atributos obrigatórios da partição lógica e integrarão o escopo de de-para, substituição, limpeza e reconciliação. Caminho e nome serão atributos mutáveis de apresentação e diagnóstico.

### Operação imediata

> Não executar o histórico completo na VM com o código atual. Executar somente uma allowlist da árvore legada RMSPII, excluindo `ENTRADA_MERCADORIAS`, ou aguardar o hotfix de identidade e isolamento por unidade.

### Bloco E

> Não liberar consultas sobre o DataHub real antes da correção estrutural, da invalidação das linhas contaminadas e da reconciliação do histórico.
