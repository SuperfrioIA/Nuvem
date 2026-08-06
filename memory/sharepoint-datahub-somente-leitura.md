---
name: sharepoint-datahub-somente-leitura
description: Regra da Maria (06/ago/2026) — nada é alterado no SharePoint do DataHub, inclusive por escrita no sistema de arquivos
metadata:
  type: feedback
---

Maria, 06/08/2026: "não devemos alterar nada no sharepoint do datahub".

**Why:** o DataHub é fonte operacional da controladoria do catering, mantida por outras
pessoas — a Nuvem IA lê e não escreve. A garantia técnica já existe no caminho da
aplicação (`Sites.Selected` + concessão `read`, e a seção "guarda de somente-leitura" de
`tests/test_graph_datahub.py` reprova qualquer `put`/`patch`/`delete` ou `POST` fora da
troca de token), mas ela cobre só o cliente Graph.

O risco real é por fora: a listagem de 06/08 encontrou uma pasta `.claude` na raiz da
fonte, com `scheduled_tasks.lock` e `settings.local.json` dentro. Alguém rodou o Claude
Code com o diretório de trabalho dentro da pasta sincronizada do SharePoint — e daí
qualquer escrita em arquivo chega ao DataHub sem passar pelo Graph.

**How to apply:** script de investigação da fonte só faz `GET` (listar e baixar), e mora
no scratchpad, nunca no repositório. Nunca rodar com o cwd dentro da pasta sincronizada
do DataHub. A limpeza daquela pasta `.claude` é decisão da Maria, pelo SharePoint — não
apagar por conta própria.
