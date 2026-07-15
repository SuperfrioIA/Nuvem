---
name: decisoes-fechadas
description: Decisões de arquitetura fechadas em 15/jul/2026 — não rediscutir sem a Maria pedir
metadata:
  type: project
---

- App separado do Portal (Receita 3 do CONTRIBUTING do Hub); o Hub só cadastra um card.
- Mesma VM do Conciliador (porta 80) e Hub (8001); nuvem-ia na **8002**, compose próprio
  com 2 containers: `nuvem-app` (FastAPI + APScheduler + frontend vanilla) e `nuvem-db`
  (Postgres, volume nomeado).
- **Conectores plugáveis** (interface `testar()`/`buscar()` → formato canônico
  `{metrica, valor_na_fonte, competencia, valor}`): `upload_manual` e `sharepoint_excel`
  na v1, alternáveis por toggle no admin; `pentaho_sql` no futuro sem mudar motor/tela.
- Graph API depende de app registration no Entra ID (`Sites.Selected`) — caminho crítico
  externo com a TI; o código fica pronto, credenciais entram depois.
- Auth: senha única protegendo só o `/admin`; nuvem aberta na rede interna.
- Camada fina: 7 tabelas (conectores, armazens, depara_armazem, metricas, medidas,
  scores, execucoes). `medidas` com unique (metrica, armazem, competencia) → upsert
  idempotente. Scores são derivados/recalculáveis (cache), não fonte de verdade.
- Motor: Python puro, score = desvio vs próprio histórico 12–24m. Sem libs de ML.

**Why:** decisões tomadas em conversa com a Maria em 15/jul/2026 — evita rediscutir do zero.
**How to apply:** detalhes em docs/ARQUITETURA.md. Mudar essas decisões só com OK
explícito dela. Ver [[projeto-nuvem-ia]].
