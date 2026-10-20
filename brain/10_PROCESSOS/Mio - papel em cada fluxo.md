---
tipo: processo
tipo_info: CONTEXT
data: 2026-10-20
fonte: dono
responsavel: Italo Silveira
status: ativo
---

# 🤖 Mio: papel em cada fluxo do painel

[[Processos]] · issue #365

O dono pediu em 20/10: *"mapear os fluxos já ativos no painel e definir onde Mio apenas observa,
onde cobra a equipe e onde prepara uma ação para aprovação"*.

O **Mio** é o robô do Ítalo no ChatGPT. Até 08/10 ele não falava com o painel: o contexto dele
foi passado à mão para a ponte dos macacões (#156). Desde 20/10 ele entra pelo conector
`https://ops.urace.us/ops/mcp`, com o usuário de quem conectou, e tudo o que faz fica na
auditoria (`mcp.call`) com o nome dessa pessoa.

## Os três níveis

| Nível | O que o Mio faz | Precisa de | Fala com cliente? |
|---|---|---|---|
| **Observa** | Lê pelas ferramentas `urace_*`, junta no resumo do dia e aponta o que está fora do normal. Não muda nada. | Conector só de leitura (já funciona hoje) | Nunca |
| **Cobra a equipe** | Avisa **a pessoa responsável** no chat da equipe (`/equipe`): o que está parado, desde quando e qual o próximo passo. Na rodada seguinte confere se andou. | Conector com "Também operar o painel como você" e papel OPERATOR ou acima. Enquanto não tiver, a cobrança vai no resumo do dia para o Ítalo repassar. | Nunca |
| **Prepara para aprovação** | Monta a chamada `urace_api`. O painel devolve `precisa_confirmar` com o que vai acontecer. O Mio mostra isso na conversa e **só manda `confirmar=true` depois do "pode" explícito** de uma pessoa ali. | Conector com operar e o papel que a rota exige (o mesmo do botão do painel) | Só pelo que a pessoa aprovou |

**O Mio nunca:**
- liga ou desliga uma regra de Automação;
- muda o nível do SDR, liga o envio automático dos macacões ou a venda automática do site;
- une ou apaga card;
- mexe em chave ou credencial;
- passa `confirmar=true` sem aprovação na conversa;
- põe serviço de um cliente no card de outro. Diagnóstico de um cliente é **pelo número do card**: ver #363.

## Fluxo a fluxo

O inventário é de 20/10 e está no branch do VPS. "Proteção hoje" é o que o painel já garante,
com ou sem o Mio.

| # | Fluxo (onde) | Proteção hoje | Mio observa | Mio cobra a equipe | Mio prepara para aprovação |
|---|---|---|---|---|---|
| 1 | Sincronia dos espelhos (`rotas._sync_thread`, a cada 15 min) | automático, só lê | atraso ou falha da sincronia | — | — |
| 2 | Motor de eventos da IA (`motor.processar_eventos`) | regras ligadas + política por ação | o que a IA fez sozinha | aprovação parada em Atenção há mais de 1 dia → gerente | — |
| 3 | Waiver anexada na tarefa do Asana (`motor.anexar_waiver_na_tarefa`) | automático | ✔ | — | — |
| 4 | Pagamento confirmado → Asana (`motor.marcar_pagamento_no_asana`) | automático | ✔ | — | — |
| 5 | Mensalidade do dia 1 pela IA (`motor.eventos_do_dia_1`) | envio pede aprovação | ✔ | aprovação do dia 1 parada → gerente | — |
| 6 | Mensalidade agendada (`providers/mensalidades.enviar_devidas`) | o agendamento do gerente é a aprovação | ✔ | falhou as 3 tentativas → gerente | — |
| 8 | Lembrete de invoice em aberto (`api/lembretes.rodar`, 09:00) | o gerente escolhe a invoice | lembretes que saíram | — | ligar o lembrete de uma invoice vencida (`/qbo/...lembrete`) |
| 9 | Invoice vencida (Atenção "invoice-vencida") | humano | ✔ | vencida sem lembrete → gerente | o lembrete, como no 8 |
| 10 | Triagem de e-mail (`providers/triagem.py`, 07/13/21h) | rascunho nunca envia | ✔ | e-mail que pede resposta parado → responsável; parceria e financeiro → dono | — |
| 11 | Varredura de clientes (06:00) | só lê | ✔ | — | — |
| 12 | Sondagem das integrações (07:00/22:00) | só lê | ✔ | integração caída → admin | — |
| 13 | Rate Card → preço no QBO (segunda 07:30) | mapa revisado; peça nunca muda | ✔ | item fora do mapa → gerente | — |
| 14 | Conferência do chat Kommo (08:10) | não escreve no Kommo | ✔ | mensagem que não chegou ao painel → vendas | — |
| 15 | Pedido incompleto (`providers/pendencias.rodada`) | push para quem pediu | ✔ | ainda incompleto no 2º dia → quem pediu | — |
| 16 | Agendamento do site → cobrança + waiver (`providers/cobranca_agenda`) | a equipe aceita a vaga; `auto_sell` desligado | ✔ | vaga esperando aceite; corrida em 3 dias sem pagamento ou sem waiver → equipe | aceitar a vaga (`/agendamentos/...`) |
| 17 | Agendamento → tarefa no Asana (`providers/agenda_asana`) | automático | ✔ | — | — |
| 18 | Checkout Stripe do site (`providers/stripe_loja`, webhook) | só com a chave do Stripe | ✔ | pedido pago sem entrega ou sem baixa no estoque → equipe | — |
| 19 | Reembolso do security deposit (`providers/deposito_site`) | só no clique | ✔ | depósito a devolver depois da corrida → gerente | o reembolso |
| 20 | Conta do site (`providers/conta_site`) | automático | ✔ | — | — |
| 21 | Ponte dos macacões (`providers/suits_ponte`) | `envio_automatico` desligado (simulação) | o e-mail que a IA mandaria | e-mail simulado esperando conferência; "precisa de alguém" → equipe Suits | — (ligar o envio é do dono) |
| 22 | SDR WhatsApp/Instagram/Kommo (`salesagent/bridge`) | `SDR_MODO` (padrão `observar`); troca só ADMIN | ✔ | lead com handoff sem resposta → responsável no Kommo | — |
| 23 | SDR por SMS e e-mail (`providers/sdr_canais`) | desligado por padrão | ✔ | — | — |
| 24 | Chat do Kommo no painel (`crm.empurrar_fila`) | resposta só humana | ✔ | lead sem resposta → vendas | o texto da resposta, para a pessoa aprovar e mandar (`/crm/*`) |
| 25 | Compras e estoque (`compras_email`, `compras_asana`) | pedir é OPERATOR, comprar é gerente | ✔ | compra atrasada, entregue sem entrada, repor, contar → responsável | o pedido de compra |
| 26 | Balcão / invoice do mecânico (`api/balcao.py`) | invoice criada sem envio; envio é gerente | ✔ | invoice do balcão esperando revisão → gerente | o envio da invoice revisada |
| 27 | Peças usadas → cobrança (`estoque.cobrancas`) | entra na próxima invoice | ✔ | peça usada sem invoice → gerente | — |
| 28 | Estimate de pré-corrida (`rotas.invite_estimate`) | só prévia, não cria nada no QBO | ✔ | — | a prévia para a equipe revisar |
| 29 | Convite e renovação de waiver (`providers/convite_waiver`) | clique da equipe; nativa desligada | ✔ | waiver vencendo em 30 dias sem convite → equipe | o convite |
| 30 | Lembrete de waiver no DocuSign (`adminai/mcp/docusign_mcp`) | 3 dias ou 1 dia antes, no máximo 2 | ✔ | — | o lembrete |
| 31 | Varredura diária de waivers (timer `urace-waivers`) | só relatório | ✔ | — | — |
| 32 | Status do Asana Shipping (`adminai/asana_status_sync.py`) | simulação sem `--aplicar` | ✔ | — | — |
| 33 | Backup do banco (local 03:15, Drive 04:00) | automático | ✔ | backup falhou → admin | — |
| 34 | Biblioteca (03:40) | automático | ✔ | — | — |
| 35 | Google Calendar dos closers (`providers/google_agenda`) | OAuth de cada pessoa | ✔ | — | — |
| 36 | Push e chat da equipe (`api/push`, `/equipe`) | sem o texto da mensagem | — | **é o canal da cobrança** | — |
| 37 | Atenção do dia (`api/atencao.coletar`) | só lista | **fonte principal do resumo** | cada item com o seu responsável | — |
| 38 | Fechar venda (`acoes_painel.venda_fechar`) | pede confirmação | ✔ | — | o fechamento (card, invoice, waiver, Asana, Kommo) |

A linha 7 não existe: não há convite de renovação do plano mensal no código. A renovação de
waiver está no 29.

**Pausados, onde o Mio não age:** handoff pelo WhatsApp (#228), Google Chat (#134), app (#74),
troca de domínio (#173) e waiver nativa (só depois dos dois modelos, do selo e do advogado).

## Onde estamos (teste do Mio em 20/10)

- **Observa: pronto.** As consultas já servem para o resumo do dia.
- **Cobra e prepara: falta escrita.** O conector foi autorizado só para leitura. Por isso o ADMIN
  apareceu com `opera=false`: o papel deixa operar, mas o conector não. A #362 deixa essa
  diferença clara no painel e no MCP.
- **Diagnóstico por cliente:** a #363 filtra reservas, pedidos e pagamentos pelo número do card.
- **Waiver:** no card de teste o DocuSign está selecionado e a nativa aparece desabilitada porque
  faltam os dois modelos. Isso não é falha do DocuSign. A #364 mostra os pré-requisitos de cada
  provedor.

## Antes de liberar a escrita para o Mio

Os testes de aceite são **no card de teste (#584)** e cada um é aprovado pelo dono:

- [ ] Reconectar o Mio marcando "Também operar o painel como você" e conferir em
      `urace_operacoes` que `opera=true`.
- [ ] **Cobrar:** o Mio escreve no chat da equipe sobre um item de Atenção do card de teste, e a
      mensagem aparece para a pessoa certa.
- [ ] **Preparar:** o Mio monta o lembrete de uma invoice do card de teste. A primeira chamada
      volta `precisa_confirmar` e nada sai. Só depois do "pode" ele confirma, e a auditoria mostra
      `mcp.call` com `confirmado=true`.
- [ ] **Recusa:** o Mio tenta uma rota de gerente com um usuário OPERATOR e o painel recusa.
- [ ] **Card errado:** pedir os pagamentos do card de teste não traz nada de outro card.

Só com essas cinco marcadas o Mio passa de "observa" para "cobra" e "prepara" em produção.
