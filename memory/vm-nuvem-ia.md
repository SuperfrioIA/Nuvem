---
name: vm-nuvem-ia
description: IP interno da VM onde a Nuvem IA roda em producao — a V3 na 8003, e a V2 fora do ar desde 26/ago/2026
metadata:
  type: reference
---

**Volumetria de catering (V3), em producao desde 26/ago/2026:**
`http://172.31.49.141:8003/` — cai no login; depois de entrar, `/` e a Matriz.
Administracao de usuarios e auditoria em `/administracao`.

**A V2 saiu do ar em 26/ago/2026** (lote V3.6). A porta **8002 nao responde
mais** — `/admin`, `/nuvem`, `/cockpit`, `/laboratorio` e `/linhagem` foram
desligados junto, e com eles a ingestao do DataHub (o "Sincronizar agora"
daquela tela). Decisao da Maria: nenhuma daquelas telas era usada.

O desligamento foi por **remocao de servico**, sem editar uma linha da V2:
`backend/`, `frontend/`, o volume `nuvem_db_data` e as tabelas da V1/V2
continuam intactos, e o bloco `nuvem-app` esta comentado no
`docker-compose.yml`. Reativar o laboratorio e descomentar e `docker compose
up -d`.

Mesma VM do Conciliador (porta 80) e do Hub (porta 8001) — rede interna
SuperFrio, nao e publico. Quatro projetos, times diferentes, no mesmo Docker.

**Why:** a Maria passou o IP para eu poder checar deploy sem redigitar, e a
porta mudou quando a V3 substituiu a V2 em producao. Citar 8002 hoje manda
qualquer pessoa para uma porta morta.

**How to apply:** usar `172.31.49.141:8003` quando o objetivo for a aplicacao em
producao. **A IA nao executa nada na VM** — os comandos sao montados aqui e a
Maria roda (ver [[nao-conectar-no-dw]] para a mesma regra no DW). Ao propor
comando de container nessa VM, resolver **por nome, item a item**: nunca
`prune`, nunca `docker stop $(docker ps -q)`, nunca `docker compose down` sem
conferir o diretorio. Ver [[projeto-nuvem-ia]], [[v3-em-producao]] e
[[decisoes-fechadas]].
