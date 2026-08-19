---
name: volumetria-lucios-checagem
description: Checagem do volumetriaLucios.csv (Desktop, extração do Luciano em 18/ago/2026) — estrutura ok, sem duplicidade/negativo; achado pendente é 016 vir com o CNPJ de 015 no DW (não bloqueia o de-para de exibição, já decidido)
metadata:
  type: reference
---

`C:\Users\maria.watanabe\Desktop\volumetriaLucios.csv` — extração nova do
Luciano direto do DW, tabela `FATO_VOL_REC_CAT` (nome novo, não é a
`FATO_VOLUMETRIA` de [[fato-volumetria-dw]]). 4.583 linhas, 36 colunas,
UTF-8 correto (o terminal do Claude que não rendeririza os acentos — bytes
conferidos, sem corrupção real).

**O achado que importa:** ver [[depara-filial-rmspii-dw]] — `015`/`016` vêm
com CNPJ `06975242000268`, conflitando com o cadastro Protheus que a Maria
trouxe hoje (que diz que deveriam ser `06975242000187`, igual à `001`).

**O resto, checado e sem problema:**
- `PK_FATO_VOL_REC_CAT` sem duplicata (4.583 de 4.583).
- Sem valor negativo em nenhuma medida; só 4 linhas com `QTDE_VLR = 0`
  (devolução sem NF, plausível).
- Líquido > bruto em **1 linha só** (RMSPIV-SANCA, GEM 0000001532: 200 kg
  líquido contra 20 kg bruto — parece casa decimal trocada; 1 de 4.583, baixa
  materialidade).
- `NUM_GEM` repete em 411 guias (linha por guia × tipo de estoque quando a
  guia mistura, ex. CONGELADO + SECO) — esperado, não é erro.
- `STATUS_PROCESSO` é **só "Concluído"** — a tabela não traz cancelada; e
  `DESCR_OPER_WMS` só tem tipos de **entrada** (é só recebimento, apesar do
  nome genérico do arquivo).
- Cada `CNPJ_CPF_CLI` bate com uma `RAZ_SOCIAL` só (zero conflito); as
  grafias duplicadas de nome (GR SERVIÇOS E ALIMENTOS/ALIMENTAÇÃO,
  HORTIFRUTI/HORTIFRÚTI) são o mesmo problema de sempre, CNPJ resolve.
- RMRJ (`06975242000420`, pasta `004/003`) bate exatamente com a convenção de
  pasta que já usamos — e aqui **vem com cliente**, coisa que o export do
  DataHub da RJ não tem (ver [[layout-entrada-por-unidade]]). Pode ser uma
  fonte alternativa pro buraco de cliente da RMRJ.
- Vazamento de instância (MAQ, 181 linhas, pasta `001/022`) confirma
  [[depara-filial-rmspii-dw]], mas o CNPJ aqui é `57046955000105` contra
  `57046955000369` registrado antes — checar qual dos dois está certo.
- "Últimos 30 dias" é por `DTHR_CONFIRM` (19/jul–18/ago, bate exato), não por
  `DATA_SOLIC` — 522 linhas (11,4%) foram solicitadas em dia diferente da
  confirmação, a mais antiga em maio/2026. Não é erro, é só outra régua de
  data — ver [[nao-ler-mes-parcial]] pelo motivo de a régua importar.
- Novidade boa: tem `NUM_GEM` (grão de guia), que a `FATO_VOLUMETRIA` velha
  não tinha — pode destravar a conciliação guia a guia que
  [[fato-volumetria-dw]] registrava como impossível.

> **Atualização de 18/ago/2026 (mesmo dia):** o "conflito de CNPJ" citado
> abaixo não é mais bloqueio pra nada — a Maria confirmou por print que `015`
> e `016` **têm mesmo** CNPJ próprio no Protheus (RMSPIII/RMSPIV), e decidiu
> que a exibição do projeto trata as três como RMSPII por decisão de negócio,
> não por elas serem tecnicamente RMSPII. Ver [[depara-filial-rmspii-dw]]. O
> que sobra em aberto é mais estreito: por que a extração do Luciano mostra
> `016` com o CNPJ de `015` (`...0002-68`) em vez do próprio (`...0003-49`) —
> isso é uma pendência sobre o comportamento do DW, não sobre o de-para do
> Nuvem IA.

**Why:** primeira olhada pedida pela Maria pra saber se dava pra confiar na
extração antes de qualquer uso; o conflito de CNPJ parecia contradizer uma
decisão do mesmo dia, então valeu mais investigar do que os itens menores.
**How to apply:** os itens menores (GEM duplicado, 1 linha líquido>bruto,
régua de data) não bloqueiam nada, só registrar. A pendência real que sobra é
técnica (por que `016` aparece com o CNPJ de `015` no DW) — não afeta o
de-para de exibição do Nuvem IA, que já está decidido.
