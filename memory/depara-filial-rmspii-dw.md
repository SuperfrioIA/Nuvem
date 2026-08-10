---
name: depara-filial-rmspii-dw
description: De-para de filial RMSPII provado — pasta = empresa SLIN (001/001, 001/015, 001/016), tudo num CNPJ só no DW; e a MESMA instância SLIN alimenta MAQ, RPII e filial VAZIA no fato (fora do BI-RMSPII)
metadata:
  type: reference
---

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
