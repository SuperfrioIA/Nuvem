---
name: vm-nuvem-ia
description: IP interno da VM onde a Nuvem IA roda em produção — acesso ao /admin
metadata:
  type: reference
---

Admin da Nuvem IA em produção: `http://172.31.49.141:8002/admin`.

Mesma VM do Conciliador (porta 80) e do Hub (porta 8001) — rede interna
SuperFrio, não é público. Útil pra validar deploy (checar `/api/admin/*` via
navegador logado ou `curl` com cookie de sessão) sem precisar SSH na VM.

**Why:** a Maria passou o IP pra eu poder checar o resultado do deploy do R1/R1.1
diretamente, sem redigitar toda vez.
**How to apply:** usar esse host em vez de `localhost` quando o objetivo for
validar algo no ambiente de produção (não local/WSL). Ver [[projeto-nuvem-ia]]
e [[decisoes-fechadas]] pro contexto da porta 8002 e da VM compartilhada.
