# V1 — Escopo

Criado em 30/jul/2026 (Bloco A / V1.0). Origem: `docs/V1_NUVEM_IA_DIRECIONAMENTO.md`
(o direcionamento completo da V1 — este documento é o resumo operacional do escopo;
em divergência, vale o direcionamento). Status vivo dos macro-lotes:
`docs/V1_PLANO.md` (fonte única).

## Mudança de fase

> A POC da integração SharePoint DataHub foi concluída com sucesso. A partir desta
> etapa, o projeto entra na construção da V1 de produção da Nuvem IA.

O projeto não é mais prova de conceito. O que a POC provou (balanço em
`docs/ENTREGA_POC.md`) vira base de uma solução de produção.

## O que a V1 entrega

```
Nuvem IA
├── Fontes e Catálogo        (conexões, famílias, campos, conceitos, unidades, qualidade)
├── Laboratório de Insights  (exploração controlada com IA, rastreável, nunca publica KPI)
├── Métricas Governadas      (definições oficiais, fórmulas, versões, linhagem, publicação)
└── Cockpit Executivo        (KPIs oficiais, filtros de período/filial/cliente, séries)
```

- Conectar-se a fontes corporativas e catalogar fontes diferentes;
- padronizar conceitos entre WMSs e sistemas distintos (catálogo semântico);
- explorar dados de forma controlada e descobrir oportunidades de indicadores;
- transformar análises aprovadas em KPIs determinísticos;
- cockpit único para diretoria e CEO, com análise por período, filial e cliente;
- rastreabilidade, qualidade e governança em tudo.

## Decisões fixadas (não rediscutir sem a Maria)

1. **Cadastro de produtos fora do escopo.** A V1 não cria, corrige, saneia nem
   depende de cadastro de produto, embalagem, peso por unidade, paletização ou
   conversão por SKU. Quando a compatibilidade de medidas não for conhecida com
   segurança, o sistema **não consolida** os valores.
2. **Somar apenas medidas compatíveis.** kg+kg (e conversões seguras de massa) sim;
   caixa+kg, unidade+palete, volume sem unidade conhecida, **não**. Sem
   compatibilidade: não somar, separar por unidade/categoria, informar a limitação,
   nunca inventar conversão.
3. **"Volume" não é conceito corporativo único.** Nenhum campo chamado só "volume"
   é consolidado sem unidade, definição e regra semântica. Categorias mínimas:
   massa, quantidade, embalagem, estrutura logística, cubagem, desconhecida.
4. **Catálogo semântico como fundamento.** Campos diferentes mapeiam pro mesmo
   conceito canônico só quando definição, unidade, granularidade, transformação e
   agregação forem compatíveis e aprovadas. Mapeamentos configuráveis e
   versionados — nada de `if fonte == ...` espalhado.
5. **Laboratório separado do cockpit.** Exploração → aprovado para implementação →
   publicado (ou descartado). A IA nunca publica diretamente no cockpit.
6. **IA não calcula KPI oficial.** Pode sugerir, explicar, apontar oportunidade e
   estruturar métrica candidata. Não pode publicar KPI, substituir cálculo
   determinístico, inventar unidade/causa, somar incompatíveis nem transformar
   hipótese em verdade oficial.
7. **Dimensões obrigatórias.** Análise por mês, ano e intervalo personalizado; uma,
   várias ou todas as filiais; um, vários ou todos os clientes; e combinações.
   Atalhos: mês atual, últimos 3/6 meses, ano atual, últimos 12 meses, personalizado.

## Fora do escopo da V1

- Saneamento cadastral de WMS/ERP e conversões dependentes de cadastro de produto;
- microsserviços, framework frontend novo, reescrita do backend;
- "volume total" misturando unidades incompatíveis;
- KPI calculado ou publicado por IA;
- alertas estatísticos sem histórico suficiente;
- processamento automático de todas as famílias do DataHub de uma vez;
- exposição pública de planilha bruta.

## Macro-lotes e blocos

| Bloco | Macro-lotes | Tema |
|---|---|---|
| A | V1.0 | Transição para produto (docs, telas, limpeza) |
| B | V1.1 + V1.2 | Catálogo semântico + compatibilidade de medidas |
| C | V1.3 | Persistência e série histórica |
| D | V1.4 | Laboratório: seleção e perfil determinístico |
| E | V1.5 + V1.6 | Laboratório: chat + promoção de insight |
| F | V1.7 | Cockpit executivo |
| G | V1.8 | Produção e entrega |

Um bloco por vez; verificação independente e validação da Maria entre blocos.
Detalhe de cada macro-lote: `docs/V1_NUVEM_IA_DIRECIONAMENTO.md`, seção 14.
