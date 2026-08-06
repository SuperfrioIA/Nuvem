---
name: filiais-catering-poc
description: De-para das filiais 001/015/016 do DataHub (CNPJ, código Protheus, sigla oficial RMSPII/III/IV) — confirmado pela Maria em 30/jul/2026; desde 02/ago/2026 a chave é qualificada pela unidade (RMSPII/001)
metadata:
  type: reference
---

Filiais que aparecem nos exports do DataHub (`ENTRADA_MERCADORIAS`, `GUIAS_ENTRADA`,
`CORTES_PRODUTOS`, `GUIAS_SAIDA`, `SAIDA_MERCADORIAS`, `ESTOQUE_POR_LOTE`):

| Filial (nome do arquivo) | CNPJ | Protheus | Sigla oficial (`armazens.sigla`) | Observação |
|---|---|---|---|---|
| `001` | 06.975.242/0001-87 | 008001 | `RMSPII` | — |
| `015` | 06.975.242/0002-68 | 008002 | `RMSPIII` | SECO da Sodexo — **operação encerrada no mês anterior a 30/jul/2026**. Só existe na base pra trás; não deve aparecer em competências a partir de agosto/2026 em diante. |
| `016` | 06.975.242/0003-49 | 008003 | `RMSPIV` | Apelido interno "Rodoanel" (não é o `nome`/`sigla` oficial, só referência de conversa) — é a filial de maior volumetria da POC (concentração da SAPORE, ver [[concentracao-sapore-016]]). |

Os códigos batem **exatamente** com o de-para oficial já existente em
`backend/seed_depara.py` (Lote 7) — mesma raiz de CNPJ (`06.975.242`), filiais-filha
`0001`/`0002`/`0003`. Isso resolve a inconsistência que estava registrada em
`docs/FONTES_DATAHUB.md` §6: `GUIAS_ENTRADA_001` traz `Estoque = CONGELADO_RMSPII`
porque **`001` já é `RMSPII`**, não `RMSP` puro.

**A controladoria enxerga as três juntas como `RMSPII`** (mesmo WMS/sigla usado em
`docs/PILOTO.md`). **Decisão de 30/jul/2026:** para esta POC e para a
estruturação/exposição de dados, as três filiais ficam **separadas**, mesmo sendo
essa a visão normal da controladoria. As siglas oficiais (`RMSPII`/`RMSPIII`/
`RMSPIV`) não mudam — "Rodoanel" não vira nome oficial, é só referência de conversa.

**Correção de 30/jul/2026 em `backend/seed_depara.py`:** o seed do Lote 7 tinha
`RMSPIII` como `ativo: True` e `RMSPIV` como `ativo: False` — invertido em relação à
realidade confirmada pela Maria (015 parou, 016 é a mais ativa da POC). Corrigido no
código **e** aplicado com `UPDATE` manual no Postgres local (o seed é
`ON CONFLICT DO NOTHING`, insert-only — não sobrescreve linha já existente sozinho).
**Pendente**: aplicar o mesmo `UPDATE` na VM de produção quando o deploy for pra lá —
rebuildar a imagem lá não corrige a linha já seedada, precisa do `UPDATE` manual
também (mesmo comando: `UPDATE armazens SET ativo = false WHERE sigla = 'RMSPIII';
UPDATE armazens SET ativo = true WHERE sigla = 'RMSPIV';`).

**Mudança de chave (02/ago/2026, migration `0008_identidade_datahub`):** o código de
filial sozinho **deixou de identificar armazém**. Depois da reestruturação da fonte
([[reestruturacao-datahub-4-unidades]]) o `001` existe em RMSPII **e** em CWB3, em
armazéns diferentes. A chave do de-para (`depara_armazem.armazem_na_fonte` sob o
conector `sharepoint_datahub`) passou a ser o **código de origem qualificado pela
unidade**: `RMSPII/001`, `RMSPII/015`, `RMSPII/016`. O campo já era texto livre, então
não houve coluna nova — mudou a semântica e o dado. Só essas três estão semeadas;
`RMSPII/002`, `CWB3/*`, `SANCA/025` e `RJ/004-*` aparecem como pendência visível.

**Pendente**: filial `002` (usada por `DADOS_GERAIS` e `OCORRENCIAS_ENTREGAS`) não
foi coberta nesta confirmação — de-para dela continua em aberto. Decisão da Maria em
02/ago/2026: **fica pendente por enquanto**, exibindo só o código `002`.

**Resolvido em 06/ago/2026** (Maria), para as famílias de volumetria: `CWB3/001 → CWBIII`,
`SANCA/025 → RMSPV` (008009, CNPJ 06.975.242/0009-34) e `RJ/004-003 → RMRJ`. As três
siglas já existiam ativas em `backend/seed_depara.py:97,106,136` — é só cadastro, sem
código. Continuam pendentes **`RMSPII/002`, `RJ/004-001` e `RJ/005-001`**, que só
aparecem em `DADOS_GERAIS`/`OCORRENCIAS_ENTREGAS` (famílias não integradas). Ver
[[volumetria-v2-decisoes]] e [[historico-datahub-por-familia]].

## Conferência do cadastro de Curitiba/Ribeirão (03/ago/2026)

A Maria conferiu contra o cadastro oficial e três coisas do Lote 7 estavam erradas:

| Filial | Achado | O que foi feito |
|---|---|---|
| `CWBI` | pré-operacional de verdade: sem CNPJ, sem volumetria, fora do cadastro de ativas. Só existe no cadastro de **capacidade** do DW (filial 74, uma câmara de congelado) | `ativo=False`; apelido `001995` removido |
| `001995` | **não é código Protheus válido.** Vem de uma linha pela metade da tabela de de-para do DW (`filiais.csv`, registro 2940 de 20/11/2020: `ERP PROTHEUS FILIAL=001995` com `WMS JDA WH ID` em branco, cluster "New Stores"). O pareamento com `CWBI` foi inferência do Lote 7, não dado da fonte | removido do seed e do banco |
| `CWBIV` | faltava no cadastro do projeto: `001034`, CNPJ 02.060.862/0034-01, São José dos Pinhais/PR, ATIVA (situação operacional "SEM OPERAÇÃO") | cadastrada, ativa |
| `RPIII` | **não é pré-operacional** como o Lote 7 supôs: filial real **desativada** — `001006`, CNPJ 02.060.862/0006-40, Ribeirão Preto/SP, situação cadastral INATIVO. O DW tem o de-para completo dela (`001006 ↔ RPIII`, segmento SEMENTES) e a exclui do KPI de ocupação | `ativo=False`, CNPJ como apelido, `nome` corrigido (era o placeholder "RPIII") |

Como o seed é insert-only (`ON CONFLICT DO NOTHING`, pra não sobrescrever ajuste manual
do admin), corrigir o seed não alcança banco que já tem as linhas — por isso a
**migration `0009_cadastro_filiais`** faz o `UPDATE`/`DELETE`/`INSERT`. Foi a lição do
`ativo` das filiais RMSPIII/RMSPIV, que ficou como passo manual pendente na VM de 30/jul
a 03/ago: migration não esquece. A `CWBIV` é exceção proposital — sigla nova, então o
próprio seed a insere no startup; duplicar isso na migration criaria duas fontes de
verdade pro mesmo cadastro.

Total passou de 34 para **35 armazéns**, e os ativos de 32 para **31** (inativas: MRS,
RMSPIII, CWBI e RPIII). Reflete em `docs/DEPLOY.md` (passo 6) e no teste de sanidade do
seed em `tests/test_ingestao.py`.

Consequência declarada de marcar CWBI e RPIII inativas: elas saem de toda tela que
filtra por armazém ativo — é o que "inativa" significa. O histórico delas continua no
banco e consultável.

**Why:** o de-para de filial estava bloqueando qualquer exibição amigável (nome de
armazém em vez de código numérico) e tinha uma inconsistência não resolvida sobre se
`001` era `RMSP` ou `RMSPII`. O `ativo` errado também distorcia qualquer tela que
filtre por armazém ativo (`backend/routers/admin.py`, listagem de armazéns).
**How to apply:** ao mostrar filial na UI ou ao interpretar competências futuras da
filial `015`, usar esta tabela. Desde o V1.0 (31/jul/2026) o de-para de **exibição**
está construído em `backend/services/filiais_datahub.py` (fonte única
`SIGLA_POR_CODIGO`; exposto como `filial_sigla` em `/kpis` e `/nuvem`, rótulo
`016 · RMSPIV` nas telas e `016 (RMSPIV)` no resumo). Desde o V1.3 (31/jul/2026)
o MESMO mapa é semeado em `depara_armazem` sob o conector `sharepoint_datahub`
(`backend/seed_datahub.py`) e é o de-para real da ingestão da série histórica.
**Desde 02/ago/2026 as chaves desse mapa são qualificadas** — `sigla()` recebe
`(unidade, código)`, nunca só o código, e a unidade sai do primeiro segmento do
caminho do inventário (`inventario_datahub.unidade_do_caminho`). Origem sem de-para
vira pendência visível no admin (painel DataHub, "Série histórica") e **não é nem
baixada**; pra destravar, basta a Maria confirmar a sigla e criar o de-para. Ver
também [[chaves-nf-entrada-datahub]].
