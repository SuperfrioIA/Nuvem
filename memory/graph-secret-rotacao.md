---
name: graph-secret-rotacao
description: Data de criação/expiração do client secret do Microsoft Graph (app nuvem-ia) e o processo de rotação — registrado no Bloco G / G1
metadata:
  type: project
---

O client secret do Graph (`GRAPH_CLIENT_SECRET`, app `nuvem-ia` no Entra ID) foi
**criado em 15/jul/2026** e **expira em 15/jul/2027**. Confirmado pela Maria em
03/ago/2026, ao mapear o Bloco G — antes disso a data não estava registrada em
lugar nenhum do repositório, só o prazo de 12 meses (`docs/DEPLOY.md`).

Processo de rotação (também documentado em `docs/DEPLOY.md`, seção do Passo
4.1): gerar um novo secret em Entra ID → App registrations → `nuvem-ia` →
Certificates & secrets → New client secret; copiar o **Value** (nunca o Secret
ID — é um erro recorrente, o Secret ID é um GUID de 36 caracteres que não
funciona como credencial); atualizar `GRAPH_CLIENT_SECRET` no `.env` da VM via
`nano` (nunca heredoc/echo, pra não sobrar no `bash_history`); `docker compose
up -d` (**nunca** `restart` — `restart` reaproveita o ambiente antigo e a troca
não pega, mesma armadilha da primeira configuração); confirmar no painel do
DataHub (Sincronizar agora) antes de apagar o secret antigo no Azure.

**Why:** o secret não é recuperável do Azure depois de criado — se vencer sem
rotação, a sincronização do DataHub para com 401 sem aviso prévio
(`docs/ENTREGA_POC.md` já registrava isso como risco aberto, sem processo
definido). Ter a data exata permite agendar a rotação com antecedência em vez
de descobrir por incidente.

**How to apply:** revisar esta data antes de 15/jul/2027; se rotacionar antes
disso (por qualquer motivo), atualizar a data aqui e em `docs/DEPLOY.md`.
