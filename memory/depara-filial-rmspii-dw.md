---
name: depara-filial-rmspii-dw
description: De-para de filial RMSPII provado — pasta = empresa SLIN (001/001, 001/015, 001/016), tudo num CNPJ só no DW; e a MESMA instância SLIN alimenta MAQ, RPII e filial VAZIA no fato (fora do BI-RMSPII). 015/016 têm Protheus e CNPJ próprios (RMSPIII/RMSPIV) mas são EXIBIDAS como RMSPII por decisão de negócio de 18/ago/2026
metadata:
  type: reference
---

> **CONFLITO NOVO em 18/ago/2026, mesmo dia da "correção" abaixo.** O Luciano
> extraiu do DW `volumetriaLucios.csv` (4.583 linhas, últimos 30 dias por
> `DTHR_CONFIRM`, só entrada/Concluído). Nela, `NK_SLIN_FILIAL` `015` e `016`
> (1.465 linhas) vêm com `NK_FILIAL` (CNPJ) = **`06975242000268`** — não
> `06975242000187` como a correção abaixo diz que deveria ser. Só a pasta `001`
> pura (614 linhas) vem com `...187`. Ou seja: **o cadastro Protheus que a
> Maria trouxe hoje e o dado transacional que o Luciano extraiu hoje se
> contradizem** sobre o CNPJ de `015`/`016`. Nenhum dos dois foi invalidado —
> ficou em aberto, precisa confirmar com o Luciano qual dos dois o BI de fato
> usa. Ver [[volumetria-lucios-checagem]].

> **CORREÇÃO À CORREÇÃO, 18/ago/2026.** A tentativa de correção abaixo (mesmo
> dia) tinha dito que "no Protheus as três têm CNPJs distintos" **estava
> errado** — não estava. A Maria trouxe o print do cadastro Protheus real:
> `015` = 008002/`...0002-68` (RMSPIII), `016` = 008003/`...0003-49` (RMSPIV),
> cada uma com código e CNPJ próprios, exatamente como o parágrafo original
> abaixo já dizia. O que muda não é o cadastro — é uma **decisão de negócio**:
> a Maria confirmou que `001`/`015`/`016` são **consideradas RMSPII** na
> exibição do projeto, replicando a visão da controladoria (já registrada em
> [[filiais-catering-poc]] desde 30/jul/2026, só nunca tinha sido aplicada). O
> de-para que a migration `0018_corrige_sigla_rmspii` aplicou (015/016 →
> RMSPII) **continua correto** — só a justificativa documentada nela e em
> `backend/services/filiais_datahub.py` foi corrigida para refletir isso.

> **Conflito do Luciano — contexto, não bloqueio.** A extração dele
> (`volumetriaLucios.csv`) mostra `015` **e** `016` vindo com CNPJ
> `06975242000268` — bate com o CNPJ real de `015`, mas não explica por que
> `016` aparece com o mesmo CNPJ em vez do seu próprio `...0003-49`. Isso é
> uma pendência de investigação sobre o comportamento do DW, não uma
> contradição da decisão de negócio acima (que é sobre como o Nuvem IA
> **exibe** as três, não sobre qual CNPJ o DW usa por baixo). Ver
> [[volumetria-lucios-checagem]].

Provado em 10/ago/2026 com `fato.csv`, `filiais.csv` (MID_D_CROSS_REF), o
cadastro Protheus (`Empresas Grupo Superfrio 5(Filiais Ativas).csv`) e a coluna
`Empresa` da `SAIDA_MERCADORIAS` (3,3 mi de linhas).

- **Lado fonte:** cada pasta do galho RMSPII tem UMA empresa SLIN — `001` =
  `001/001`, `015` = `001/015`, `016` = `001/016`. Nenhuma outra empresa aparece
  dentro das pastas.
- **Lado DW:** tudo vira o CNPJ `06975242000187` (Log Frio 0001-87) via
  instância `SLIN_RMSPII_PRD` (`NK_WMS_FILIAL` = `NK_QLS_FILIAL` = `RMSPII`).
- **No Protheus as três têm CNPJs distintos** — RMSPII=008001 (0001-87),
  RMSPIII=008002 (0002-68), RMSPIV=008003 (0003-49), RMSPV=008009 (0009-34) —
  mas 0002-68 e 0003-49 **não existem no fato**: o DW colapsa as três filiais
  físicas no 0001-87. O de-para "um CNPJ ↔ três pastas" está certo; a chave real
  é a **instância**, não o CNPJ.
- **Descoberta (P-10):** a MESMA instância `SLIN_RMSPII_PRD` gera linhas no fato
  para outras filiais DW, fora do "RMSPII" do BI e fora das pastas: **MAQ**
  (57046955000369 = CEFRI Mairinque/MAQII; SODEXO 9.226,7 t + ANGA ALIMENTAÇÃO
  6.550,2 t em jan–jun/26), **RPII** (02060862000569 = SuperFrio Ribeirão Preto;
  SAPORE 11.107,4 t) e **22 linhas com filial VAZIA** (SODEXO 668,4 t,
  mai–jun/26). ~27,5 kt/semestre que uma comparação "tudo da RMSPII" acharia.
- A raiz 06975242 é compartilhada com a RMRJ (0420) — filtrar por raiz de CNPJ
  de filial mistura RJ com RMSPII; filtrar sempre pelo CNPJ completo ou pela
  instância.

**Why:** o de-para era a pendência 4 da conciliação; sem ele cada passada
rediscutia o que "RMSPII" significa em cada sistema.
**How to apply:** no `fato.csv`, RMSPII do BI = `NK_FILIAL = '06975242000187'`.
Movimento da instância fora desse CNPJ existe e é legítimo (overflow/operação
para outras empresas do grupo) — não somar no RMSPII, registrar à parte. Ver
[[fato-volumetria-dw]], [[filiais-catering-poc]] e
[[confirmar-sigla-antes-de-citar-filial]].

---

**RESOLVIDO em 21/ago/2026, pelas bases novas do DW.** As extrações
`dm_volumetriaRecebimento.csv` e `dm_volumetriaExpedicao.csv` (36.221 + 41.922
linhas, jan–ago/26, processo `catering_to_dw_volumetry_v01`) trazem a coluna
`NOME_UND`, que não existia no `fato.csv`. Com ela:

- **MAQ e RPII não são "filial em instância errada": são unidades próprias.**
  `MAQ` = `001/022` = **MAIRINQUE**; `RPII` = `001/024` = **SF RPII -
  RIBEIRAO**. As duas têm `NOME_UND` próprio e volume comparável ao de uma
  unidade (Mairinque 8,0 kt de recebimento em jan–ago; Ribeirão 4,7 kt, e ela
  para de movimentar depois de abr/26). O P-10 estava certo no fato — aquele
  movimento não é RMSPII — mas errado na conclusão: não é resíduo, é unidade.
- **`NOME_UND` é o nível do BI.** "RMSPII - BARUERI" já reúne 001+015+016 num
  valor só, sem de-para externo. Usar `NOME_UND` como unidade e
  `NK_INSTANCIA` + `NK_SLIN_FILIAL` como armazém.
- **Nunca usar a filial SLIN sozinha:** `001/001` aparece em DUAS unidades
  (RMSPII - BARUERI e UNIDADE CURITIBA) e só a instância separa.
- **O conflito do CNPJ de 015/016 ficou do lado do dado transacional:** nas duas
  bases novas, `015` e `016` vêm com `NK_FILIAL = 06975242000268` em todas as
  linhas, e só `001` vem com `...187` — o mesmo que o `volumetriaLucios.csv`
  mostrou. Ou seja, três extrações independentes contra o cadastro Protheus que
  a Maria trouxe. Consequência prática: **agrupar por CNPJ não separa 015 de
  016**, e a RMSPII do BI por CNPJ exige `...187` + `...268` juntos.
- A mesma unidade pode vir em duas instâncias: a SANCA aparece em
  `SLIN_RMSPIV_PRD` e também em `SLIN_RMSPII_PRD` (131 linhas). Agrupando por
  `NOME_UND` as duas somam certo; por instância, parece faltar.

Ver [[radar-recebimento-fonte-dw]].
