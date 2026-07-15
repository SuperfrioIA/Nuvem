# Arquitetura — Nuvem IA

Status: fechada em 15/jul/2026. Nenhum código construído ainda.

## Posição na infra

- App **separado** do Portal SuperFrio & IceStar (Receita 3 do CONTRIBUTING do Hub):
  repo, banco e deploy próprios; o Hub só cadastra um card (`tipo = url`, nova aba).
- Mesma VM do Conciliador (porta 80) e do Hub (8001). Nuvem IA: **porta 8002**.

## Containers (docker-compose próprio)

| Serviço | Conteúdo |
|---|---|
| `nuvem-app` | FastAPI (API + estáticos) + APScheduler embutido (rotina 1×/dia + execução manual pelo admin) |
| `nuvem-db` | Postgres 16, volume nomeado (a camada fina) |

Dockerfile faz `COPY backend/ frontend/` → mudou código = **rebuild**
(`docker compose up -d --build`). Frontend vanilla sem build step; ao mudar asset,
subir o `?v=` no HTML.

## Conectores (o coração)

Interface única que todo conector implementa:

```
conector.testar()            → ok/erro
conector.buscar(competencia) → [{metrica, valor_na_fonte, competencia, valor}]
conector.detalhar(...)       → opcional; reservado pra fontes com grão fino (Pentaho)
```

O motor só conhece o formato canônico — não sabe de onde o dado veio. Conector é
**registro** na tabela `conectores` (tipo + config JSONB + ativo); ligar/desligar é um
toggle no admin, não deploy.

| Conector | v1 | Nota |
|---|---|---|
| `upload_manual` | sim | tela de upload de xlsx no admin; entra pela mesma esteira |
| `sharepoint_excel` | sim (código) | Microsoft Graph; só funciona quando a TI criar o app registration (Entra ID, permissão `Sites.Selected`) — **caminho crítico externo**. Até lá, "testar conexão" acusa erro (esperado) |
| `pentaho_sql` | futuro | mais um conector; zero mudança em motor/tela/banco |

## Schema (camada fina, Postgres)

| Tabela | Grão | Nota |
|---|---|---|
| `conectores` | 1/fonte | tipo, config JSONB, `ativo` |
| `armazens` | 1/filial | a dimensão |
| `depara_armazem` | conector × valor_na_fonte | unique (conector, valor); editável no admin |
| `metricas` | 1/métrica | nome, unidade |
| `medidas` | métrica × armazém × mês | **o fato.** unique na chave → upsert idempotente |
| `scores` | métrica × armazém × mês | média/desvio/z da janela 12–24m + estado; derivado e recalculável (cache de leitura, não fonte de verdade) |
| `execucoes` | 1/rodada | início, fim, status, linhas lidas/gravadas, erro — exibido no admin |

Princípios: persistir o fato, derivar a interpretação; idempotência (rodar 2× não
corrompe); validação no boundary (Excel/config), confiança interna.

## Motor

Python puro, sem libs de ML: por métrica × armazém, média e desvio-padrão da janela de
12–24 meses (excluindo o mês em análise); z-score vira estado (dentro/fora do padrão).

## Frontend

- `index.html` — a nuvem (vanilla JS, mesmo padrão do mapa-ia do portal)
- `admin.html` — conectores (toggle/testar/executar agora), upload de xlsx, CRUD do
  de-para, log de execuções

## Auth

Senha única protegendo só o `/admin`. A nuvem em si aberta na rede interna. Evolução
futura: JWT padrão SuperFrio, sem retrabalho estrutural.

## Drill-down

Com fontes mensais, o detalhe da bolinha = série histórica da própria camada fina
(instantâneo). Consulta ao vivo na fonte só quando existir conector com grão fino —
a interface (`detalhar()`) já prevê, mas não se constrói antes da necessidade.

## Ordem de construção sugerida

1. **Pedido à TI** (app registration no Entra ID) — disparar cedo; é o caminho mais longo
2. **Congelar o contrato da planilha de ocupação** (aba/colunas fixas, com quem preenche)
3. Esqueleto: compose + banco + tabelas + admin com upload manual → primeiro dado real
4. Motor + scores
5. A nuvem (tela)

## Fora de escopo (por enquanto)

Previsão/sazonalidade; padrão de comportamento por cliente; alertas automáticos/e-mail;
IA narradora; integração Pentaho.
