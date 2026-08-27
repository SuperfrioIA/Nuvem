---
name: contrato-vale-so-na-janela-medida
description: Nulabilidade e unicidade medidas em 2026 nao valem para 2023-2025 -- ampliar a janela da carga e ampliar o contrato inteiro (V3.8.1)
metadata:
  type: project
---

Ampliar o piso da carga da V3 (`DW_ANO_MINIMO`) e ampliar o **contrato inteiro**,
nao so o periodo. Duas vezes na mesma semana uma propriedade medida sobre 2026
deixou de valer sobre 2023-2025:

- **unicidade** (25/ago/2026): a chave de seis colunas era unica em 36.300/36.300
  linhas de 2026 e repetia em 27.834 no historico -- `num_gem` se recicla por
  ano. Virou chave de sete colunas na migration 0023;
- **nulabilidade** (27/ago/2026): as 29 colunas obrigatorias estavam preenchidas
  em 100% de 2026, e no historico **1** linha de 2025 (`ACERTO DE ESTOQUE - SEM
  CUSTO`) vinha sem `sk_cliente` e sem `nk_wms_cliente`. Derrubou a carga do
  historico da expedicao inteira. Migration 0024 soltou as duas.

**Why:** a carga para na PRIMEIRA linha ruim, entao o erro nomeia uma coluna e
nao diz quantas nem se ha outras -- descobrir por tentativa e erro custa uma
janela de deploy por coluna. E generalizar de uma amostra de um ano para a serie
inteira foi, nas duas vezes, falha de raciocinio e nao de codigo.

**How to apply:** antes de mexer no piso, rodar
`python -m catering.carga --fonte oracle --sondar` (a Maria roda -- a IA nao
conecta no DW) e exigir que as **duas** secoes saiam certas: `identidade` com
`chave de hoje -> UNICA` e `preenchimento` com `nenhuma coluna obrigatoria vem
vazia`. A secao de preenchimento existe desde o V3.8.1 exatamente porque a trava
anterior provava identidade e liberou uma carga que morreu. Para decidir se uma
coluna deve ser obrigatoria: obrigatoria e a que identifica a linha (as sete da
chave natural), a que a tela agrega (`nk_calendario`) e a marca d'agua
(`dw_data_alteracao`); fora dessas, vazio na fonte e fato, e derrubar a rodada
por uma celula que nenhuma tela le troca um dado ausente pela indisponibilidade
de tudo. Ver [[recorte-por-dia-e-coluna-parcial]] e [[v3-em-producao]].
