---
name: v3-recomeca-nao-refatora
description: 24/ago/2026 — a V3 nasce como aplicação nova (fonte DW Oracle, tela = filtros + Matriz + planilha) em vez de refatorar a V1/V2; o motivo é o grão da tabela de fato, não gosto por código novo
metadata:
  type: project
---

Em 24/ago/2026 a Maria decidiu migrar o artefato de análise (o radar publicado
em 21/ago, ver [[radar-recebimento-fonte-dw]]) para uma aplicação lendo o **DW
Oracle** `pdwgener`, sem vínculo com o SharePoint DataHub. A pergunta dela foi
"queria apagar tudo e fazer do zero, ou é melhor reaproveitar?" — e a resposta
mudou depois de medir o que existe. Status e contrato completo em
[`docs/V3_PLANO.md`](../docs/V3_PLANO.md).

**Decisão: aplicação nova, não refatoração.** Mas *nada é apagado agora* — o
código da V2 fica no repo como implementação de referência e só sai quando o
novo provar o mesmo número.

**Why:** dois argumentos técnicos, não estéticos. Guardar porque a Maria vai
precisar repetir isso para outras pessoas.

1. **O grão do fato está errado.** O fato publicado da V1/V2 é livro-caixa
   mensal em formato longo — `medidas` tem `UNIQUE (metrica_id, armazem_id,
   competencia)` e `medidas_recebidas` empurra o resto para um JSONB. Uma linha
   por medida, por mês. O artefato precisa do oposto: grão de **dia**, 13
   medidas na mesma linha, seis dimensões. Uma linha do artefato viraria ~7
   linhas ali e toda consulta viraria pivô sobre JSONB. Serviço, teste e
   consulta do cockpit se apoiam nesse grão — refatorar é trocar a fundação com
   a casa em cima.
2. **A arquitetura responde uma pergunta morta.** Conector plugável, de-para de
   nome de filial, `item_id` como identidade, máquina de estado por arquivo
   (`ok`/`erro`/`sem_dado`), leitor da variante de 18 colunas da RJ, três
   tabelas de pendência — tudo isso existe porque a fonte era uma pasta de
   planilhas inconsistentes. O DW dá coluna tipada, PK, esquema estável e sigla
   pronta em `NK_WMS_FILIAL`. Manter a maquinaria é carregar defesa contra um
   inimigo que saiu da sala.

Medido em 24/ago para sustentar isso: backend 11.245 linhas em 54 arquivos, 33
deles citando datahub/sharepoint/graph/`item_id`; **8.570 das 10.879 linhas de
teste (79%) acopladas ao DataHub**; 25 tabelas e 18 migrations, 5 delas cicatriz
de de-para; e **nenhuma conexão com o DW existe hoje** — `requirements.txt` só
tem `psycopg2`, tudo do DW sempre veio como CSV.

**How to apply:**
1. **O artefato é a especificação.** Divergência entre aplicação e artefato é
   bug da aplicação. É a primeira vez no projeto que a visão foi acordada antes
   de codar — a V1 e a V2 foram escritas descobrindo regra no caminho, e é daí
   que vem o retrabalho delas. Vale também [[modo-laboratorio-poc]]: a regra só
   virou backend depois de estabilizar.
2. **Escopo da tela é pequeno de propósito:** filtros + Matriz + planilha aberta
   (100 linhas) + download do recorte. O resto do artefato não entra na V3.
3. **O acesso ao DW é o último passo, não o primeiro.** Os dois CSVs de 21/ago
   já são o contrato de colunas, então schema, carregador, tela, login e deploy
   se constroem antes da credencial existir — desde que o carregador nasça
   partido em `extrair()` (a única parte que conhece a fonte) e
   `transformar()`+`carregar()`. Assim o conector Oracle é um adaptador no fim,
   não uma reescrita. Isso tirou o impedimento do caminho crítico.
4. **Reaproveitar por cópia e teste novo, nunca por `import` do código antigo.**
   Salva: infra (Docker, alembic, pytest, `auth.py`, `database.py`, deploy) e
   regra pura sem fonte (`tipo_estoque.py`, `mascaramento.py`,
   `compatibilidade_medidas.py`). Não salva: os 2.847 linhas de arquivos
   `*_datahub*` nem os testes acoplados — mas ler os testes antigos como
   catálogo de bug real já encontrado.
5. **Escopo do negócio: catering = instâncias SLIN.** Isso corrige uma leitura
   errada minha de 21/ago: eu tratei o volume `DISTROMAQ_PRD` que falta no MAQ
   (75%) e no CWBIII (48%) como defeito. Não é — é outro negócio, fora de
   escopo por definição. Declarar na tela para ninguém comparar a página com
   número de grupo do BI. Ver [[depara-filial-rmspii-dw]].
6. **Admin e linhagem são parqueados, não apagados**, e saem da VM só depois da
   tela nova de pé — senão perde-se a única forma de consertar o que ainda está
   em uso.
