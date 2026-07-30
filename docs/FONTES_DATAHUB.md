# Fontes do SharePoint DataHub

Levantamento de **29/jul/2026**, feito com o token do próprio app (`nuvem-ia`) via
Microsoft Graph — não é print de tela nem export manual, é o que o sistema vê.

Este documento é o inventário da pasta. A decisão de arquitetura que ele provocou está
em `memory/decisoes-fechadas.md` (entrada de 29/jul/2026).

---

## 1. O vínculo

```
Site        https://superfrioarmazens.sharepoint.com/sites/DataHub
Site ID     superfrioarmazens.sharepoint.com,b4983714-59fa-4dc3-8923-d57953e602d1,aca8eb22-e0ea-4cf1-bba4-6c96d4a8af69
Biblioteca  Documentos Compartilhados (biblioteca padrão → `/drive` no Graph)
Pasta       00.Dados/00.Bronze/00.Dados_Sistemicos
App         nuvem-ia  ·  AppId 7324ef4d-54e4-4fc9-9179-00a5c95b8855
Permissão   Sites.Selected (aplicação) + concessão `read` no site DataHub
```

O conector endereça pelo caminho, não pelo GUID — mais legível e não quebra se o
site for recriado:

```
GET /sites/superfrioarmazens.sharepoint.com:/sites/DataHub:/drive/root:/00.Dados/00.Bronze/00.Dados_Sistemicos:/children
```

Credenciais no `.env` (`GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`,
`GRAPH_SITE_PATH`, `GRAPH_PASTA`). Nomes documentados em `.env.example`; valores nunca
vão pro git.

**O acesso é somente leitura por construção.** O papel é `read`: qualquer escrita é
recusada pelo Graph, não por disciplina do código. O app também não tem nenhuma
permissão delegada — nunca age em nome de usuário, não aparece em histórico de edição.

**Escopo real:** `read` vale para o site DataHub inteiro. O Graph não tem escopo por
pasta em permissão de aplicação. Se isso virar problema, a saída é mover as bases para
biblioteca/site dedicado.

### Histórico do destravamento (para não repetir a via-crúcis)

O pedido enviado à infra está em `docs/configuracao_graph_api.docx` — **parcialmente
superado**: ele instrui a criar um app do zero, e no fim reaproveitamos o `nuvem-ia`
de 16/jul. Sequência real dos bloqueios, todos com o mesmo HTTP 403 e causas
diferentes:

1. Conta da Maria não tem Application/Cloud Application Administrator → não consegue
   clicar em "Conceder consentimento do administrador". Resolvido por terceiro.
2. `GET` no Graph Explorer com a conta da Maria → falta o escopo delegado
   `Sites.Read.All`. **Não precisa resolver** — era atalho para achar o Site ID, e o
   Site ID sai sem Graph nenhum por `/_api/site/id` + `/_api/web/id` no navegador.
3. `POST /sites/{id}/permissions` → exige `Sites.FullControl.All` **e** papel
   SharePoint Administrator no usuário logado (o Graph intersecta escopo do app com
   permissão do usuário). Executado pelo Carlos (`carlos.rvsilva`).

Armadilhas que custaram tempo: consentir escopo no Graph Explorer não atualiza o token
da sessão (precisa Reload/relogar); `PnP.PowerShell` exige PowerShell 7+; o SDK
`Microsoft.Graph.Sites` roda no 5.1 mas trava em `ExecutionPolicy=AllSigned`; e o
`Client Secret` do Azure tem duas colunas parecidas — vale a **Value**, não a
**Secret ID** (GUID de 36 caracteres dá `AADSTS7000215`).

---

## 2. Inventário

**228 arquivos, 711 MB.** Todas as abas se chamam `SLIN` — são exports do WMS SLIN,
não do DW.

| Área | Arquivos | MB |
|---|---:|---:|
| SAIDA | 70 | 463 |
| ENTREGAS | 70 | 196 |
| ESTOQUE | 54 | 38 |
| ENTRADA | 34 | 14 |

### Convenção de nomes

```
NOME_{filial}_{AAMM}[_f{parte}].xlsx        mensal
ESTOQUE_POR_LOTE_{filial}_{AAMMDD}.xlsx     foto diária
ESTOQUE_POR_LOTE_{CLIENTE}_{TEMP}_{AAMMDD}.xlsx
PALLETS_EXCEDENTES_{CLIENTE}_{TEMP}_{AAMM}.pdf
```

- **filial**: `001`, `002`, `015`, `016` — códigos numéricos, **de-para pendente**
- **competência**: `2601`…`2607` (jan a jul/2026), série completa em todas as famílias
- **parte** (`_f1`, `_f2`, `_f3`): o export estourou e foi partido. Uma competência =
  vários arquivos que precisam ser concatenados
- **TEMP**: `CONGELADO`, `SECO`, `HORTIFRUTI`

### As 8 famílias

| Família | Pasta | Arq | Filiais | Partes | Cabeçalho |
|---|---|---:|---|---|---|
| `ENTRADA_MERCADORIAS` | ENTRADA/ENTRADA MERCADORIAS | 20 | 001, 015, 016 | — | **linha 1** |
| `GUIAS_ENTRADA` | ENTRADA/GUIAS ENTRADA | 14 | 001, 016 | — | linha 2 |
| `DADOS_GERAIS` | ENTREGAS/DADOS GERAIS | 28 | 002, 016 | f1, f2 | linha 3 |
| `OCORRENCIAS_ENTREGAS` | ENTREGAS/OCORRENCIAS ENTREGAS | 42 | 002, 016 | f1, f2, f3 | linha 2 |
| `CORTES_PRODUTOS` | SAIDA/CORTES PRODUTOS | 14 | 001, 016 | — | linha 5 |
| `GUIAS_SAIDA` | SAIDA/GUIAS SAIDA | 14 | 001, 016 | — | linha 2 |
| `SAIDA_MERCADORIAS` | SAIDA/SAIDA MERCADORIAS | 42 | 001, 015, 016 | f1, f2 | **linha 6** |
| `ESTOQUE_POR_LOTE` | ESTOQUE/ESTOQUE POR LOTE UA | 16 | 001 (diário) | — | linha 5 |
| `ESTOQUE_POR_LOTE` segregado | ESTOQUE/… SEGREGADO/{cliente} | 21 | por cliente × temp | — | linha 5 |
| `PALLETS_EXCEDENTES` | ESTOQUE/PALLETS EXCEDENTES/{cliente} | 17 | por cliente × temp | — | **PDF** |

Clientes nas pastas segregadas: `CONVIDA`, `CUCINARE`, `FLV`, `LC`, `NOVITA`, `OG`,
`PIMENTA VERDE`, `SAPORE` — são os clientes de catering da POC. O recorte da pasta
bate com o recorte do piloto, por outro caminho.

---

## 3. Colunas por família

Rótulos literais da linha de cabeçalho, na ordem do arquivo.

**`ENTRADA_MERCADORIAS`** — 20 colunas, cabeçalho na linha 1

```
Cliente · Cliente CNPJ · GEM · Devolução · Solicitação · NF Entrada · Código ·
Descrição · Volume · EMB · Fração · EMB · Peso Líquido · Peso Bruto ·
Vlr. Unitário · Vlr. Total · Qtde UA · Código Estoque · Nome Estoque · Operação
```

**`GUIAS_ENTRADA`** — 27 colunas, cabeçalho na linha 2 (linha 1 = "Confirmação de Entrada")

```
Número · Agenda · DV · Cliente · Depositante · Estoque · NF GEM ·
NF Acobertamento · Pedido · Data NF · Solicitação · Status · UAs · UAs Palletizadas · …
```

**`DADOS_GERAIS`** — 59 colunas, cabeçalho na linha 3 (linha 2 é faixa de agrupamento
"Pedido / NF" × "Entrega")

```
CNPJ Cliente · Cliente · Pedido · NF · Entrega · Programação · Tipo Movimento ·
EMP GSM · GSM · Status WMS · Status Baixa · Peso Liq. · Peso Bruto · Operação · …
```

**`OCORRENCIAS_ENTREGAS`** — 31 colunas, cabeçalho na linha 2

```
Cliente · Destinatário · Código Destinatário · Operação · Pedido · NF ·
Peso Bruto Entrega · Peso Bruto Ocorrência · Cidade · UF · Bairro ·
Ocorrência · Motivo · Descrição Origem · …
```

**`ESTOQUE_POR_LOTE`** — 41 colunas, cabeçalho na linha 5

```
Localização · PK Fixo · Tipo Endereço · Código · Descrição · EMB EST · EMB NF ·
Status · Bloqueado · UA · SEQ · Volume · EMB · Fração · EMB · Peso Líquido ·
Peso Bruto · Peso Liq. Faixa · Fabricação · Validade · Vida Útil · … (41 no total)
```

**`CORTES_PRODUTOS`** — 23 colunas, cabeçalho na linha 5

```
Cliente CNPJ · Cliente · Estoque · GSM · Data Solicitação · Data Saída ·
Confirmação · Item · Pedido · Código Destinatário · Destinatário · Código ·
Descrição · EMB · Tipo Peso · Volume Análise · Peso Líq. Análise · Volume Processado · …
```

**`GUIAS_SAIDA`** — 31 colunas, cabeçalho na linha 2 (linha 1 = "Confirmação de Saída")

```
Número · AGRUP · Cliente · Depositante · Estoque · Prioridade · Solicitação ·
Saída · Status Separação · NF Retorno · Liberado PK RF · Status Picking ·
COMPL · Corte Contábil · …
```

**`SAIDA_MERCADORIAS`** — 36 colunas, cabeçalho na **linha 6** (confirmado em 30/jul/2026
lendo o xlsx cru de `016_2607_f1/f2`, `001_2607_f1` e `015_2607_f1` — o mesmo em todas).
A linha 5 **não** é o cabeçalho: é a faixa de agrupamento (`GSM` · `Produto` ·
`Solicitado pelo Cliente` · `Atendido pelo Estoque` · `Separado Fisicamente` ·
`Dados de Separação`), mesmo padrão da faixa `Pedido / NF` × `Entrega` do `DADOS_GERAIS`.

```
Cliente · Cliente CNPJ · Estoque · Empresa · GSM · Operação · Data Solicitação ·
Data Saída · Status Separação · Item · Código · Descrição · Pedido · Destinatário ·
Volume · EMB · Fração · EMB · Peso Liquido · Peso Bruto ·        (solicitado pelo cliente)
Volume · EMB · Fração · EMB · Peso Liquido · Peso Bruto ·        (atendido pelo estoque)
Volume · EMB · Fração · EMB · Peso Liquido · Peso Bruto ·        (separado fisicamente)
Corte Físico · Início · Final · Separador
```

Atenção: os seis rótulos de medida (`Volume`, `EMB`, `Fração`, `EMB`, `Peso Liquido`,
`Peso Bruto`) se repetem **três vezes**, uma por faixa. Aqui mapear por nome não
desambigua — quem somar peso/volume desta família tem que escolher a faixa **por
posição** (obstáculo 2). `Peso Liquido` também vem sem acento, diferente do
`Peso Líquido` de `ENTRADA_MERCADORIAS`.

---

## 4. O que dá para calcular

| Fonte | KPI |
|---|---|
| `ENTRADA_MERCADORIAS` | volumetria de entrada por cliente/competência (peso, volume, UAs), valor movimentado |
| `SAIDA_MERCADORIAS` | volumetria de expedição — espelho da entrada, e a maior fonte (451 MB) |
| `ESTOQUE_POR_LOTE` | **ocupação física por UA, com foto diária**; estoque vencido/avariado (`Status`, `Bloqueado`); aging por `Validade`/`Vida Útil` |
| `ESTOQUE_POR_LOTE` segregado | o mesmo já no grão cliente × temperatura — é o grão do Lote 9.5 |
| `CORTES_PRODUTOS` | ruptura e nível de atendimento (`Volume Análise` vs `Volume Processado`, por motivo) |
| `OCORRENCIAS_ENTREGAS` | qualidade de entrega e devoluções por `Ocorrência`/`Motivo`, com peso e geografia |
| `DADOS_GERAIS` | SLA de entrega (`Programação` vs `Entrega`, `Status WMS`, `Status Baixa`) |
| `GUIAS_ENTRADA` / `GUIAS_SAIDA` | lead time e produtividade de separação (`Status Separação`, `UAs`, `UAs Palletizadas`) |

**O achado mais valioso:** o `ESTOQUE_POR_LOTE` tem fotos diárias já acumulando
(260720 a 260729). Isso ataca o item aberto do Lote 0 — "confirmar se ocupação tem
histórico retroativo; se não, começa a acumular agora". Aqui já está acumulando, e
com grão de UA.

---

## 5. Obstáculos técnicos conhecidos

1. **Cabeçalho fora da linha 1, variando por família** (1, 2, 3, 5 ou 6). As linhas
   acima trazem título do relatório e um bloco `Empresa: 001/016`. O modelo de
   importação precisa de parâmetro de linha do cabeçalho, que hoje não existe.
2. **Nomes de coluna repetidos.** `EMB` aparece duas vezes em `ENTRADA_MERCADORIAS`
   (posições 10 e 12) e como `EMB EST`/`EMB NF` no estoque. Mapeamento por nome é
   ambíguo — tem que ser por **posição**.
3. **Arquivos partidos** (`_f1`/`_f2`/`_f3`): uma competência = vários arquivos a
   concatenar antes de agregar.
4. **`PALLETS EXCEDENTES` são PDF** (17 arquivos, por cliente × temperatura). Sem
   extração de tabela de PDF, ficam fora.
5. **Volume**: 711 MB no total. O conector não pode baixar tudo a cada rodada —
   precisa ser incremental, por `lastModifiedDateTime` ou por competência.
6. **Número de nota fiscal truncado — contagem de NF não é possível** (conferido em
   30/jul/2026 lendo o xlsx cru da 016/2607). `NF Entrada` em `ENTRADA_MERCADORIAS` é
   cortada em **10 caracteres**: 308 valores terminam em `-` no meio do número, e 10
   valores não são nota nenhuma (`FATURADO`, `SECO 1235-`, `HORTI 02.0`, `CAIXA-0`,
   `DEV-0`, `AJUSTEDEPA`, `RETIRADA-0`, cobrindo 581 linhas e R$ 494.784). `NF GEM` em
   `GUIAS_ENTRADA` é uma **concatenação** de várias notas separadas por `/`, cortada em
   **99 caracteres** — perde as notas além da 10ª. As duas colunas só coincidem em 310
   de 1.484 valores: são espaços de numeração diferentes, unir e contar infla o número.
   A chave confiável é o **`GEM`** (10 dígitos zero-padded), que é o mesmo campo que
   `Número` em `GUIAS_ENTRADA` e casou 100% (1.275 de 1.275). Agregar por `GEM`, nunca
   prometer quantidade de notas.
7. **Guia cancelada não tem linha de item.** Em `GUIAS_ENTRADA` da 016/2607 há 115 guias
   com `Status = Cancelado` valendo R$ 9,8 mi, com zero interseção com
   `ENTRADA_MERCADORIAS`. Quem agrega pelos itens já exclui cancelado; quem usar
   `GUIAS_ENTRADA` sozinho **precisa filtrar `Status`**, senão infla ~26%.

8. **`DADOS_GERAIS`: `_f1` e `_f2` são o MESMO conteúdo — metade da competência não
   está publicada** (conferido em 30/jul/2026, comparação linha a linha das 60 colunas).
   Não é semelhança: são idênticos, linha por linha, na mesma ordem, nos três arquivos
   testados — `016_2607` (12.805 = 12.805 linhas), `016_2606` (14.849) e `002_2607`
   (6.844). Duas consequências:
   - **Falta metade do mês.** O `DADOS_GERAIS_016_2607` só cobre `Programação` de
     **01 a 15/07**, enquanto `OCORRENCIAS_ENTREGAS` da mesma filial/competência cobre
     01 a 29/07. O `_f2` deveria trazer a segunda quinzena e traz uma cópia do `_f1`.
     Medido pelo cruzamento com `OCORRENCIAS_ENTREGAS`: o casamento por dia é 98–100%
     até 15/07 e cai para 0–3% de 16/07 em diante.
   - **Concatenar `_f1 + _f2` duplica 100% das linhas** — qualquer soma sobre essa
     família dobra.

   **O defeito é só do `DADOS_GERAIS`.** As outras famílias partidas estão corretas:
   `OCORRENCIAS_ENTREGAS` f1/f2/f3 são fatias reais e disjuntas (01–10, 11–20,
   21–29/07, interseção zero) e `SAIDA_MERCADORIAS` f1/f2 também (interseção zero,
   266.910 linhas somadas na 016/2607). Enquanto isso não for corrigido na origem,
   **ler só o `_f1` do `DADOS_GERAIS`** e tratar a família como meia competência.
   Pendência humana no item 4 da seção 6.

Para validar valor de forma independente, cruzar a soma de `Vlr. Total` dos itens contra
`Vlr. Total NF` das guias **concluídas**, por `GEM`. Na 016/2607 fecham em −1,76%
(R$ 36.649.308,72 contra R$ 37.305.066,49) — a diferença residual é arredondamento e um
punhado de guias com valor de NF zerado.

---

## 5.1 Junções validadas entre famílias

Três chaves de junção **conferidas cruzando os arquivos reais** da 016/2607 (baixados do
Graph, lidos com `openpyxl` fora do backend), não inferidas por semelhança de nome de
coluna. Mesmo método usado para validar o `GEM` (obstáculo 6). Junção não listada aqui
**não foi verificada** — não desenhar como se fosse.

| # | Junção | Chave | Casamento |
|---|---|---|---|
| A | `SAIDA_MERCADORIAS` → `GUIAS_SAIDA` | `GSM` = `Número` | **100%** (847/847 chaves; 266.910/266.910 linhas) |
| B | `OCORRENCIAS_ENTREGAS` → `DADOS_GERAIS` | (`Pedido`, `NF`) | **100%** na janela coberta (12.015/12.015 pares) |
| C | `DADOS_GERAIS` → `GUIAS_SAIDA` | `GSM` = `Número` | **98,97%** (287/290), só com `EMP GSM` = filial do arquivo |

**A. `SAIDA_MERCADORIAS.GSM` = `GUIAS_SAIDA.Número`** — é o espelho exato do par
`GEM`/`Número` da entrada. Formatos diferentes, mesma numeração: `GSM` vem como
`NNNN/AAAA` (`4971/2026`) e `Número` como 10 dígitos zero-padded (`0000004971`);
normalizar pegando a parte antes da `/` e removendo zeros à esquerda.

- Só contra o arquivo de guias de julho: 812 de 847 = 95,87%. **Os 35 faltantes são
  borda de competência**, não falha da chave: são guias solicitadas em junho com saída
  em 01/07 — o item cai no arquivo de julho e a guia no de junho. Os 35 estão em
  `GUIAS_SAIDA_016_2606` (35/35). Unindo junho+julho: **847/847 = 100%**, cobrindo
  as 266.910 linhas de item.
- Sentido inverso: 812 de 823 guias **concluídas** têm item (98,66%). Das 11 sem item,
  10 têm `Corte Contábil = 1` com `Volumes` e `Peso Líq.` zerados — **guia cortada
  integralmente não gera linha de item**; sobra 1 resíduo (guia 4160, de 05/06,
  republicada no arquivo de julho). As 58 **canceladas** não têm item, mesmo
  comportamento já documentado para `GUIAS_ENTRADA` (obstáculo 7).
- Conferência de conteúdo: o cliente da guia é igual ao cliente do item em 812 de 812.

**B. `OCORRENCIAS_ENTREGAS.(Pedido, NF)` = `DADOS_GERAIS.(Pedido, NF)`** — os valores
batem de verdade, não só o rótulo.

- Na janela que o `DADOS_GERAIS` efetivamente cobre (01–15/07, ver obstáculo 8):
  **12.015 de 12.015 pares distintos e 12.160 de 12.160 linhas = 100,00%**, resíduo zero.
- No mês inteiro cai para 54,47% — **culpa do export duplicado do `DADOS_GERAIS`**
  (obstáculo 8), não da chave. Medir a força dessa junção sobre o mês cheio subestima.
- Conferência de conteúdo: nos 12.035 pares casados, cliente igual em 12.035 e
  `Peso Bruto Entrega` igual a `Peso Bruto` (diferença < 1%) em 12.035 — é o mesmo
  evento nas duas famílias, com a ocorrência acrescentando `Ocorrência`/`Motivo`.
- `Pedido` sozinho e `NF` sozinha dão praticamente o mesmo resultado; o **par** é o
  mais seguro e é o que deve ser usado.

**C. `DADOS_GERAIS.GSM` = `GUIAS_SAIDA.Número`** (achado colateral, liga ENTREGAS a
SAIDA) — **287 de 290 = 98,97%** contra junho+julho, mas **só nas linhas cuja coluna
`EMP GSM` é a filial do próprio arquivo** (`001/016`). As 3.654 linhas do
`DADOS_GERAIS_016` com `EMP GSM = 001/001` casam apenas 9,95%: **o `GSM` é uma série
por empresa**, e comparar entre empresas diferentes produz colisão de número, não
junção. Sem esse filtro a medida cai para 55,23% e engana. Junção real, mas exige o
filtro — usar com essa ressalva escrita.

---

## 6. Pendências que dependem de gente

1. ~~**De-para dos códigos numéricos de filial.**~~ **Resolvido em 30/jul/2026** (de-para
   confirmado pela Maria) para as filiais `001`/`015`/`016` — ver
   `memory/filiais-catering-poc.md`. Explica a inconsistência antes registrada aqui
   (`GUIAS_ENTRADA_001` trazendo `Estoque = CONGELADO_RMSPII`): **`001` já é RMSPII**,
   não RMSP puro — as três filiais são CNPJs-filha do mesmo grupo e a controladoria as
   enxerga juntas como RMSPII, mas o projeto expõe cada uma separada. Segue pendente
   só o de-para da filial `002` (usada por `DADOS_GERAIS`/`OCORRENCIAS_ENTREGAS`) —
   não coberto na confirmação de 30/jul.
2. **Quem publica e com que cadência.** Os arquivos de julho foram modificados em 13,
   17, 20, 22, 28 e 29/jul — parece republicação da competência corrente. Se for isso,
   o conector busca por padrão de nome e reprocessa a competência aberta, em vez de
   depender de nome fixo.
3. **Atualizar as 5 fontes do DW.** Os exports que alimentaram o catálogo (Lote 8.5)
   são de jul/2026 e precisam ser renovados para conviver com esta pasta.
4. **Export quebrado do `DADOS_GERAIS`** (aberto em 30/jul/2026, ver obstáculo 8).
   Perguntar a quem publica por que o `_f2` é cópia do `_f1` em todas as competências
   testadas, e pedir a republicação com a segunda metade do mês. Enquanto isso não
   acontecer, metade das entregas de cada competência simplesmente não existe no
   DataHub — limitação a declarar em qualquer KPI de SLA de entrega.
