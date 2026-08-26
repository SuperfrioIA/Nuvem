# A fonte de dados da volumetria: por que copiar em vez de ler o DW ao vivo

> **Escrito em** 26/ago/2026, durante o V3.5, quando a leitura do DW passou a ser
> real. **Motivo:** a pergunta "por que vocês não leem direto do DW?" é legítima,
> vai aparecer, e merece resposta com número em vez de opinião.
>
> **Escopo:** a volumetria de catering da V3. O raciocínio vale para qualquer
> tela nova que leia do DW, e é por isso que este documento não tem "V3" no nome.
>
> **O que é medição e o que é estimativa está marcado em cada número.** O que eu
> não medi está na seção 11, dito com essas palavras.

---

## 1. A pergunta, escrita como quem questiona escreveria

*"O dado já existe no DW. Vocês construíram um segundo banco na nuvem, uma carga
agendada, uma marca de água e uma migration de identidade para manter uma cópia.
Por que não apontar a tela direto para o DW e acabar com essa camada toda?"*

A pergunta é boa. A resposta curta: **porque a tela e o DW têm padrões de acesso
incompatíveis**, e porque o dado do DW **muda debaixo de quem lê** — as duas
coisas medidas neste projeto, não supostas.

A resposta longa é o resto do documento.

---

## 2. O nome disso, que não é invenção nossa

O que a V3 faz tem nome, e nomear ajuda: é um **data mart de consumo** (também
chamado *read model*, ou *ODS de aplicação*) alimentado por **ETL incremental com
marca de água**.

É o desenho padrão para "aplicação analítica sobre DW compartilhado", pelo mesmo
motivo em toda parte: **o DW é otimizado para carga e para consulta ad-hoc de
analista; a tela precisa de resposta em milissegundos, repetida, no ritmo de quem
clica.** Não são o mesmo problema, e resolver os dois na mesma instância é
escolher qual dos dois vai sofrer.

Quem quiser o nome técnico do que está em `catering/carga/`: extração por janela
incremental (`WHERE DW_DATA_ALTERACAO > :desde`), sem `DELETE`, com `UPSERT` por
chave natural e registro de linhagem por rodada em `cat_cargas`.

---

## 3. As cinco alternativas consideradas

| # | Alternativa | Por que caiu (ou ficou) |
|---|---|---|
| A | **Tela lê o DW ao vivo** (passthrough) | Carga no DW proporcional ao uso da tela; tela cai quando o DW está em manutenção; número não reproduzível (seção 8.3); credencial de produção dentro do processo que atende HTTP |
| B | **Cópia no Postgres da aplicação** | **Escolhida.** Custo medido: 242 MB e cerca de 2,5 min de carga para todo o histórico (seções 5 e 6) |
| C | **Ler ao vivo + cache de resultado** | Resolve latência e nada mais: a primeira consulta de cada recorte ainda vai ao DW, e a expiração do cache é uma cópia com prazo curto e sem linhagem. Complexidade de cópia, benefício de meia cópia |
| D | **View materializada dentro do DW** | Tecnicamente boa, e a melhor alternativa à B. Cai por governança, não por engenharia: exige objeto novo, `REFRESH` agendado e índice em **produção alheia** — mudança que passa pelo time do DW a cada ajuste nosso de coluna ou de índice |
| E | **Réplica física do DW** | Resolveria de vez, e é caro em licença, infra e operação para um data mart de 242 MB. Desproporcional |

**A B não foi escolhida por ser a mais fácil.** Ela é a que tem mais código:
fonte, transformação, destino, marca de água, migration de identidade e suíte. A
C é a mais barata de escrever e a que dá o pior resultado no ano seguinte.

---

## 4. O que decidiu: padrão de acesso, não volume

Este é o argumento central, e é o único que sozinho justifica a decisão.

**A carga da cópia é limitada e previsível:**

- **2 leituras por dia** (07h05 e 15h05), 30 minutos depois das rodadas do
  processo do DW, que roda a cada 2h entre 06h35 e 23h35;
- as duas são **incrementais**: leem só o que mudou desde a marca de água. A
  rodada de teste de 25/ago às 18h03 leu **zero linha** e registrou `sem_dado` —
  o resultado normal quando o DW não mexeu em nada;
- o pior caso é uma recarga completa: **433 mil linhas em cerca de 2,5 minutos**,
  e mesmo isso o DW entrega streamando em lotes de 1.000.

**A carga da leitura ao vivo é proporcional ao uso — e o uso é justamente o que
se quer que cresça.** Cada troca de filtro na Matriz é uma agregação nova: mudar
o mês, abrir uma unidade, trocar a lente, trocar a faixa, baixar a planilha. Uma
sessão de análise de verdade são dezenas de interações.

> **Estimativa, não medição** — a conta é minha, e o multiplicador é o número de
> pessoas usando: 10 pessoas × 30 interações = **300 agregações/dia** contra as
> **2 leituras** da carga. Não medi quantas interações uma sessão real tem; a
> ordem de grandeza é o que importa aqui, não o número exato.

A diferença que importa não é 2 contra 300. É que **um dos dois números é
previsível e o outro é uma função do sucesso do produto.** Um DW compartilhado
por integrações, agendamentos, relatórios e APIs absorve 300 agregações hoje; a
questão é quem responde quando forem 3.000, e o que se corta nesse dia.

---

## 5. Quanto custa em disco (medido)

Medido em 26/ago/2026 no Postgres local, com a carga real de 2026 dentro —
tabela, índices e TOAST somados (`pg_total_relation_size`):

| tabela | linhas | disco | heap | índices | por linha |
|---|---|---|---|---|---|
| `cat_fato_recebimento` | 36.678 | 20,3 MB | 13,4 MB | 6,9 MB | **582 B** |
| `cat_fato_expedicao` | 42.726 | 24,0 MB | 17,4 MB | 6,5 MB | **589 B** |
| dimensões + `cat_cargas` | 64 | 128 KB | — | — | — |
| **total (janela de 2026)** | **79.404** | **44,3 MB** | | | **585 B** |

Contagem no DW, da sondagem de 25/ago às 16h19 — a tabela inteira, desde
2023-01-02:

| tabela do DW | linhas | fator sobre 2026 |
|---|---|---|
| `DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01` | 201.848 | 5,50x |
| `DM_VOLUMETRIA.FATO_VOL_EXP_CAT_V01` | 231.886 | 5,43x |
| **total** | **433.734** | **5,46x** |

**Aplicando os 585 B/linha medidos:**

- **todo o histórico de 2023 em diante: cerca de 242 MB** (0,24 GB);
- **crescimento: cerca de 120 mil linhas/ano, 70 MB/ano.** Duas contas
  independentes fecham: 79.404 linhas em 236 dias de 2026 dá 122,8 mil/ano; e
  433.734 linhas em 3,65 anos dá 118,8 mil/ano;
- **uma década inteira fica abaixo de 1 GB.** Se a operação de catering dobrar de
  tamanho, cerca de 1,7 GB em 2036.

**Conclusão desta seção: volume não é critério de decisão neste caso.** Quem
argumentar contra a cópia por custo de armazenamento está discutindo 242 MB. O
projeto guarda só a janela de 2026 por decisão de produto (`DW_ANO_MINIMO`), não
por limite técnico — trazer 2023 em diante é mudar uma variável de ambiente e
rodar uma carga completa.

---

## 6. O que a carga custa em memória e tempo (medido)

**Memória: constante, e por construção.** O carregador não acumula resultado —
streama da fonte e grava em lotes de 1.000 linhas (`destino.PAGINA`). Medido com
`tracemalloc` sobre o mesmo arquivo cortado em três volumes:

```
exp,   5.000 linhas -> pico 4,31 MB
exp,  20.000 linhas -> pico 3,91 MB
exp,  42.318 linhas -> pico 3,91 MB
```

Se o processo acumulasse, 42 mil linhas custariam cerca de 34 MB. **O pico
depende do tamanho do lote, não do volume da tabela** — trazer 433 mil linhas não
muda a memória da carga em nada.

**Tempo:** a carga completa de 25/ago levou **12s** (36.678 linhas) e **15s**
(42.726 linhas), cerca de 2.700 linhas/s incluindo a rede até o DW. Extrapolando
para as 433.734 linhas do histórico completo: **cerca de 2,5 minutos, uma vez.**
As rodadas diárias são incrementais e leem quase nada.

---

## 7. O que a cópia entrega na tela (medido)

Medido no Postgres local sobre a janela de 2026, mediana de 5 a 7 execuções:

| consulta | tempo |
|---|---|
| agregação de 6 medidas por filial e mês (36.678 linhas) | **21,6 ms** |
| Matriz completa, recebimento (a função real da tela) | **36,5 ms** |
| Matriz completa, expedição | **62,0 ms** |

O plano de execução é a parte interessante:

```
HashAggregate  (actual time=22.871..22.896 rows=40)
  ->  Seq Scan on cat_fato_recebimento  (actual time=0.009..13.334 rows=36678)
        Buffers: shared hit=1721        <- 100% cache, zero leitura de disco
```

A consulta **varre a tabela inteira** e ainda assim responde em 22 ms, porque a
tabela cabe no cache do Postgres (`shared_buffers` = 128 MB). Não há índice
esperto envolvido: há dado local e pequeno.

**Extrapolando linearmente para o histórico completo** (`Seq Scan` e
`HashAggregate` são ambos lineares no número de linhas): cerca de 120 ms de
agregação e 200 a 340 ms de Matriz. Nesse ponto o heap somado (cerca de 168 MB)
passa do `shared_buffers` atual e começaria a haver leitura de disco. Se um dia
incomodar, as saídas são conhecidas e baratas: subir `shared_buffers`, criar
índice por `nk_calendario`, ou particionar por ano. **Não é problema de hoje** —
é o tipo de problema que se resolve quando aparece, no nosso banco, com uma
migration.

O que a leitura ao vivo custaria na tela eu **não medi** (seção 11). O que se sabe
sem medir: ela paga latência de rede até o DW na AWS, mais a fila do DW, mais a
agregação na CPU dele — e paga isso **em cada clique**, não uma vez por turno.

---

## 8. Os quatro argumentos que não são sobre performance

Estes valem mais que os três anteriores, e são os que costumam decidir a discussão
quando alguém tenta reabri-la.

### 8.1 Mudança na fonte: aconteceu, e a cópia absorveu

**Em 25/ago/2026 o DW reconstruiu as duas tabelas de catering no meio do dia.**
Elas tinham só 2026 (cerca de 70 mil linhas nas duas) e passaram a ter 2023 em
diante (433.734 linhas). Junto veio a descoberta de que o `num_gem` se recicla
por ano, o que quebrou a chave natural de seis colunas com que o projeto havia
sido construído.

O que aconteceu **com a cópia no meio**: a carga falhou (`ON CONFLICT DO UPDATE
command cannot affect row a second time`), registrou `status='erro'` em
`cat_cargas` com o motivo, e a tela continuou servindo o dado da última carga boa.
Ninguém viu número errado. A correção foi uma migration (`0023`) e uma recarga, no
nosso tempo.

O que aconteceria **lendo ao vivo**: o dado da tela mudaria de tamanho no meio do
expediente, sem aviso e sem registro — e a quebra apareceria como erro na cara de
quem estivesse com a tela aberta.

**Isso não é hipótese defensiva. É o que este projeto viveu no dia anterior a este
documento.**

### 8.2 Disponibilidade: o DW parar não derruba a tela

DW em janela de manutenção, mudança de rede, credencial expirada, instância
reiniciando — com cópia, a tela serve o dado da última carga e `cat_cargas` diz
qual é e quando entrou. Com leitura ao vivo, a tela para junto, e a
disponibilidade do nosso produto passa a ser, no máximo, a disponibilidade do DW.

### 8.3 O número tem que ser reproduzível — e o DW revisa o passado

Este é o argumento mais forte, e o mais fácil de subestimar.

**O DW revisa dado antigo.** Medido em 26/ago/2026, comparando a carga real contra
as extrações em CSV de 21/ago (mesmo período, mesma agregação):

- 9 das 10 medidas conferem **byte a byte** em `Decimal`, e jan–jul bate em
  **0,00%** em linhas e em peso;
- **`qtde_vlr_separado` mudou em 306 de 38.827 linhas** (+391.943,152), com **zero
  chave natural sem par** — não entraram nem saíram linhas, o valor delas mudou;
- a distribuição cresce com a proximidade (jan 9, fev 4, mar 10, abr 42, mai 57,
  jun 86, jul 98), coerente com valor de separação amadurecendo depois do fato.

Consequência para quem lê ao vivo: **duas consultas do mesmo mês em dias diferentes
devolvem números diferentes, e não há como explicar a diferença.** Um número que
vai para reunião de diretoria precisa de resposta para "por que este relatório
mostra outro valor?".

Com a cópia, a resposta existe e é curta: *"é a carga das 07h05 de tal dia, marca
de água tal"* — e a rodada anterior está registrada ao lado, em `cat_cargas`. A
mesma propriedade faz o download da planilha casar com a tela: os dois leem o
mesmo estado, não duas fotos do DW tiradas em momentos diferentes.

### 8.4 Superfície de segurança

Leitura ao vivo exige credencial válida do DW **dentro do processo que atende
requisição HTTP** — um app com login web, exposto. Com cópia, a credencial existe
só no processo de carga, que não escuta porta nenhuma, roda duas vezes por dia e
morre. O código da fonte é somente leitura por construção, com duas guardas na
suíte: uma estática, sobre a árvore sintática, e uma de runtime, que recusa
qualquer comando que não comece por `SELECT`.

---

## 9. O que a cópia custa (os contras, que também são fatos)

Documento de respaldo sem os contras é panfleto — e quem questiona acha o furo
antes de você.

| Custo | Tamanho real | O que mitiga |
|---|---|---|
| **Defasagem** | até cerca de 8h, entre as rodadas de 07h05 e 15h05 | Volumetria é análise de dia e de mês fechado, não operação em tempo real. **Se o negócio passar a exigir tempo real, a cópia é a arquitetura errada** — ver seção 10 |
| **Dado em dois lugares** | dois lugares podem divergir | `cat_cargas` registra cada rodada, e a conferência célula por célula da seção 8.3 é reprodutível quando alguém duvidar |
| **Contrato de colunas para manter** | coluna renomeada no DW quebra a carga | Quebra **alto e cedo**: a leitura confere os nomes contra o contrato antes da primeira linha, e a carga falha em vez de gravar dado torto |
| **Mais código** | fonte, destino, marca de água, migration, suíte | É o custo real da opção B, e é exatamente o que a alternativa C economiza — ao preço da seção 8 inteira |

---

## 10. Quando reconsiderar (os gatilhos, escritos antes de precisar)

A decisão é boa **hoje** e para o volume de hoje. Ela deve ser reaberta se:

1. **o negócio passar a exigir dado de tempo real** — volumetria de hoje, dentro
   do turno. Aí a discussão é a alternativa C ou uma janela de carga muito mais
   curta, e é decisão de produto antes de ser de arquitetura;
2. **o time do DW oferecer uma view ou API própria, com contrato e SLA** — isso
   muda a alternativa D de "mexer em produção alheia" para "consumir um
   contrato", e ela passa a ser a melhor;
3. **o volume mudar de ordem de grandeza** — dezenas de milhões de linhas em vez
   de centenas de milhares. Aí a conversa é particionamento ou outro motor, não
   passthrough;
4. **a defasagem começar a causar erro de decisão de verdade** — não incômodo,
   erro. Nesse caso o registro em `cat_cargas` é a evidência de quanto ela custou.

---

## 11. Limite desta evidência

- **Não medi o custo de uma agregação dentro do DW**, e não vou medir: o DW é
  produção e a política do projeto é que a IA não conecta nele. Onde este
  documento fala do custo da leitura ao vivo, ele argumenta padrão de acesso
  (seção 4), não tempo medido;
- **as 300 agregações/dia da seção 4 são estimativa**, com a conta à vista. Não
  medi interações por sessão;
- **as projeções das seções 5, 6 e 7 são extrapolação linear** de medições reais.
  A de disco é a mais confiável (bytes por linha é estável); a de tempo de
  consulta perde precisão exatamente no ponto em que o cache estoura, e está dito
  onde;
- **os números do DW são da sondagem de 25/ago às 16h19.** A tabela pode ter
  mudado depois — ela mudou uma vez, no dia anterior;
- **as medições locais são de um container Postgres 16 em WSL num notebook**, não
  da VM. Servem para bytes por linha e para ordem de grandeza de tempo; não são
  medição de produção.

---

## 12. Como reproduzir as medições

Tudo abaixo é leitura, e nada disso toca no DW.

Espaço em disco por tabela, com índices:

```powershell
$env:DATABASE_URL = "postgresql://nuvem:teste@localhost:5433/nuvem_teste"
python -c "import os, psycopg2; cur = psycopg2.connect(os.environ['DATABASE_URL']).cursor(); [print(t, [cur.execute(q, p) or cur.fetchone()[0] for q, p in ((f'select count(*) from {t}', None), ('select pg_total_relation_size(%s)', (t,)))]) for t in ('cat_fato_recebimento', 'cat_fato_expedicao')]"
```

Contagem e janela no DW — **este é o único comando que fala com o DW, e quem roda
é a Maria** (ver `docs/EXECUCAO_LOCAL.md`):

```powershell
python -m catering.carga --fonte oracle --sondar
```

O plano de execução da agregação da tela sai de um `EXPLAIN (ANALYZE, BUFFERS)`
na consulta de `catering/consulta/matriz.py`. O pico de memória da carga sai de
`tracemalloc` em volta do laço de `catering/carga/__init__.py` — foi o que
produziu os três números da seção 6.

---

## Onde esta decisão está registrada

- `docs/V3_PLANO.md` — as decisões do V3.5 com o motivo de cada uma, e o aceite
  da carga real;
- `catering/carga/fonte_oracle.py` — o docstring explica por que o SELECT é gerado
  do contrato, por que `fetch_decimals` está ligado e por que o escopo continua
  sendo filtrado em Python;
- `alembic/versions/0023_identidade_ano_solic.py` — a história completa da chave
  natural que a reconstrução do DW quebrou;
- `memory/fato-volumetria-dw.md` — que o DW revisa retroativamente, nos dois
  sentidos.
