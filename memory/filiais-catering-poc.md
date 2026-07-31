---
name: filiais-catering-poc
description: De-para das filiais 001/015/016 do DataHub (CNPJ, código Protheus, sigla oficial RMSPII/III/IV) — confirmado pela Maria em 30/jul/2026, ativo corrigido no seed
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

**Pendente**: filial `002` (usada por `DADOS_GERAIS` e `OCORRENCIAS_ENTREGAS`) não
foi coberta nesta confirmação — de-para dela continua em aberto.

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
Filial `002` segue sem de-para — quando um arquivo dela for processado, vira
pendência visível no admin (painel DataHub, "Série histórica"); pra destravar,
basta a Maria confirmar a sigla e criar o de-para. Ver também
[[chaves-nf-entrada-datahub]].
