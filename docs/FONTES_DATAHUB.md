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
| `SAIDA_MERCADORIAS` | SAIDA/SAIDA MERCADORIAS | 42 | 001, 015, 016 | f1, f2 | linha 5 (não confirmado) |
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

**`SAIDA_MERCADORIAS`** — 36 colunas, cabeçalho não confirmado (provável linha 5)

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

1. **Cabeçalho fora da linha 1, variando por família** (1, 2, 3 ou 5). As linhas
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

---

## 6. Pendências que dependem de gente

1. **De-para dos códigos numéricos de filial.** Os arquivos usam `001`, `002`, `015`,
   `016`; o projeto usa siglas WMS (`RMSP`, `RMSPII`, …) em `armazens`/`depara_armazem`.
   Há uma inconsistência a esclarecer: `GUIAS_ENTRADA_001` traz
   `Estoque = CONGELADO_RMSPII`, o que não fecha se `001` fosse RMSP. A sigla aparece
   embutida no valor da coluna `Estoque` (`CONGELADO_RMSPII`, `HORTI_RMSPII`) — pode
   ser a via de resolução, mas precisa de confirmação humana.
2. **Quem publica e com que cadência.** Os arquivos de julho foram modificados em 13,
   17, 20, 22, 28 e 29/jul — parece republicação da competência corrente. Se for isso,
   o conector busca por padrão de nome e reprocessa a competência aberta, em vez de
   depender de nome fixo.
3. **Atualizar as 5 fontes do DW.** Os exports que alimentaram o catálogo (Lote 8.5)
   são de jul/2026 e precisam ser renovados para conviver com esta pasta.
