# Mio × Command Center: contexto técnico do conector

Pedido do dono (21/10, #372): entregar ao Mio o contexto técnico que faltava para concluir a
integração. Aqui não entra senha, token nem chave. O cliente é citado só pelo número do card.

## 1. Versão implantada e endpoint

- **Endpoint MCP**: `https://ops.urace.us/ops/mcp`. É um único servidor;
  `https://urace-bridge.duckdns.org/ops/mcp` chega no mesmo processo.
  - Transporte *streamable HTTP*, só POST, JSON-RPC.
  - Login OAuth do próprio painel, anunciado em `/.well-known/oauth-*`.
- **O que está no ar** (21/10): o deploy do bloco #362–#365, que entrou pelo merge `9d2e9cb`.
  O CI desse commit está verde (tag `ci-verde/9d2e9cb…`). O branch pode ter commits mais novos
  de outros assuntos. Para saber o commit exato, na VPS: `git -C ~/Uraceagent log -1 --oneline`.
  A rota `GET /ops/api/system/update` também mostra, mas é só para ADMIN.
- **A partir do #372**, o próprio MCP diz o commit:
  - `initialize` devolve `serverInfo.version = "1.1.0+<commit>"`;
  - `GET /ops/mcp` com login devolve `{"versao", "commit", "ferramentas": <n>}`.
  - Antes do #372, a versão era fixa em `1.0.0`. Por isso nada no protocolo avisava o cliente
    de que o catálogo tinha mudado.

## 2. O catálogo que o servidor publica

`tools/list` devolve **o mesmo catálogo para todo mundo**. Ele não muda com papel, escopo ou
cliente OAuth: leitura ou operação é decidida na chamada, não na lista. São **21 ferramentas**.

As cinco em questão:

| ferramenta | obrigatório | parâmetros (todos `integer`, salvo indicado) |
|---|---|---|
| `urace_cliente_reservas` | `client_id` | `client_id` (número do card) · `limit` (padrão 20, teto 100) · `offset` (padrão 0) |
| `urace_cliente_pedidos` | `client_id` | idem |
| `urace_cliente_pagamentos` | `client_id` | idem |
| `urace_invoices` | — | `client_id` (opcional, só as do card) · `status` (`string`: paid, sent, overdue) · `limit` (padrão 80, teto 300) · `offset` · `limite` (nome antigo de `limit`). Devolve `total`, `limit`, `offset` e, por linha, `client_id` e `atualizado_em` (#374) |
| `urace_corridas` | — | `client_id` (opcional: só as corridas para que o card foi convidado, com a situação do convite) · `limit` (padrão 40, teto 200) · `offset` · `limite` (nome antigo). Devolve `total`, `limit`, `offset`; com card, cada linha traz `client_id` (#374) |

Todos os schemas têm `additionalProperties: false`.

**O servidor recusa parâmetro que o schema não declara.** A resposta é o erro
`-32602 "parâmetro que não existe: …"`. Então mandar `client_id` para uma versão antiga não
traria dado de outro cliente: a chamada voltaria com erro. A cautela de não mandar filtro não
declarado continua certa, mas o risco de vazamento silencioso não existe nesse caso.

## 3. Por que o ChatGPT não via as ferramentas: separar publicação, cache e conexão

O que já se sabe, sem presumir:

| hipótese | como verificar | o que já se sabe |
|---|---|---|
| **Publicação** (o servidor não serve o catálogo novo) | Faça login em `https://ops.urace.us/ops/` no navegador e abra `https://ops.urace.us/ops/mcp`. O campo `ferramentas` tem que dar **21**; o catálogo antigo dava 18. Depois do #372, o campo `commit` também aparece. | Em 21/10, o conector do Claude, no mesmo endpoint, recebeu as 21 ferramentas, com `client_id` em `urace_invoices`. A sessão do Mio recebeu `por_que` (#362) e `waiver_fluxo` (#364), que só existem no código novo. **O servidor que respondeu ao Mio é o novo.** |
| **Cache do cliente** (o ChatGPT guardou a lista antiga) | Em Configurações › Apps e conectores › o app: **Atualizar** (Refresh). Se a lista continuar antiga, apague o app e crie de novo com a mesma URL. Abra sempre uma **conversa nova**, porque a conversa em andamento mantém o catálogo com que começou. | Bate com o observado: as respostas são novas, mas a lista é velha. O servidor anuncia `listChanged: false` e, antes do #372, a versão era fixa. Por isso o cliente não tinha sinal para buscar a lista de novo. |
| **Conexão** (o app aponta para outro lugar ou é outro app) | Confira se a URL do app é exatamente `https://ops.urace.us/ops/mcp`. Confira também se não há **dois apps** parecidos ("URACE Ops" e "URACE Command Center"), um velho e outro novo, com a conversa usando o velho. | Não verificado do lado do ChatGPT. |

**Critério de pronto:** numa conversa nova, o catálogo lista `urace_cliente_reservas`,
`urace_cliente_pedidos` e `urace_cliente_pagamentos`, e `urace_invoices` declara `client_id`.

**Versão e sincronia sem depender do ChatGPT (#374):** `urace_resumo` traz:
- `servidor`: `nome`, `versao` e `commit`;
- `sincronia`: para cada integração, `status`, `ultima_ok`, `ultima_tentativa`, `erros_seguidos` e `ultimo_erro` (até 200 caracteres).

## 4. De onde vem cada dado

| ferramenta · fonte (`fonte` na linha) | onde mora | de onde vem | quando atualiza | `atualizado_em` (#372) |
|---|---|---|---|---|
| reservas · `agendamento_site` | `bookings` (local) | site e portal do cliente; o card vem da conta ou do piloto do portal ligados a ele | na hora em que acontece | `updated_at` |
| reservas · `corrida` | `race_invites` + `races` (local) | convite feito no painel | na hora | `invited_at` |
| reservas · `sessao_do_carrinho` | `store_order_items` (local) | sessão paga no carrinho que ainda não virou agendamento | na hora | `created_at` |
| pedidos · `loja` | `store_orders` (local) | checkout do site (Stripe) | na hora, pelo webhook do Stripe; o laço de 15 min repesca o que faltou | `updated_at` |
| pedidos · `plano` | `plan_orders` (local) | plano mensal comprado no site | na hora | `updated_at` |
| pedidos · `suit` | `suit_orders` (local) | pedido de macacão aberto pela venda ou pela ponte | na hora | `updated_at` |
| pagamentos · `invoice_qbo` | `invoices` (**espelho do QuickBooks**) | QuickBooks | a cada 15 min (`CC_AUTOSYNC_MIN`), janela de 365 dias, até 1.000 por rodada | `synced_at` (a última sincronia) |
| pagamentos · `mensalidade` | `monthly_invoices` (local) | mensalidade agendada pelo gerente e enviada pelo QuickBooks | na hora; o envio no dia 1, às 01:00 de Orlando | `updated_at` |
| pagamentos · `invoice_pecas` | `parts_invoices` (local, com cópia no QuickBooks) | balcão dos mecânicos | na hora | `qbo_synced_at` ou `sent_at` |
| pagamentos · `stripe` | `store_orders` (local) | Stripe | como `loja` | `updated_at` |
| pagamentos · `deposito_reembolso` | `store_deposit_refunds` (local) | reembolso no Stripe pelo clique do gerente | na hora | `done_at` |

**Limites de cobertura:**
- **A invoice do QuickBooks é ligada ao card na sincronia**, pelo e-mail de cobrança ou pelo
  nome do responsável. A ligação não é feita na consulta. Invoice que não casou fica com
  `client_id` vazio e **não aparece em nenhum card**: isso é "não ligada", não "não existe".
- O espelho cobre 365 dias. Invoice mais antiga pode não estar no painel.
- O **Asana** (tarefas e serviços) não entra nestas três. Os serviços aparecem em `urace_cliente`.
- O **Kommo** não tem filtro por card. As `urace_kommo_*` buscam por lead, funil ou texto, e
  chamam a API do Kommo ao vivo.
- O **DocuSign** aparece só como estado da waiver em `urace_cliente` (`waivers`, `waiver_fluxo`).
  O estado vem da sincronia de 15 min e da verificação de integrações às 07:00 e 22:00.
- O campo `fora` de cada resposta lista o que ficou de fora e por quê.

## 5. Como ler a resposta e provar que toda linha é do card

- `total`: quantas linhas o card tem somando todas as fontes. É igual à soma de `por_fonte`.
- `limit`: quantas linhas vieram nesta página (teto 100).
- `offset`: quantas foram puladas. A próxima página é `offset + limit`. Quando
  `offset + linhas ≥ total`, acabou.
- `por_fonte`: a contagem de cada fonte, inclusive as que deram zero.
- `fora`: as tabelas que **não** entram e o motivo. Serve para não confundir "não junta" com
  "não tem".
- `como_junta`: a regra da junção. É sempre pelo `client_id`, nunca por nome ou e-mail.

**Conferência linha a linha (depois do #372):** cada linha traz `client_id`.
1. Toda linha tem que ter `client_id` igual ao card pedido.
2. A soma das linhas de todas as páginas tem que ser igual a `total`.
3. Teste negativo: um card que não existe volta `isError` com "cliente N não existe". Uma
   chamada sem `client_id` volta o erro "faltou informar: client_id".

Antes do #372 as linhas não traziam `client_id`, e a conferência linha a linha não era possível.

O CI tranca o isolamento com dois cards fictícios (`command_center/tests/test_mcp_por_card.py`).
O teste cobre dois casos: um pedido de um card feito com o e-mail do outro, e um piloto de um
card dentro da conta do portal do outro.

## 6. Card 584: o que deve aparecer

Contagens lidas em 21/10, por volta das 10h de Orlando. Os valores e as descrições ficam fora
deste arquivo, que é público.

| ferramenta | `total` | `por_fonte` |
|---|---|---|
| `urace_cliente_reservas` | 8 | `agendamento_site` 8 · `corrida` 0 · `sessao_do_carrinho` 0 |
| `urace_cliente_pedidos` | 1 | `loja` 1 · `plano` 0 · `suit` 0 |
| `urace_cliente_pagamentos` | 1 | `stripe` 1 · as outras 0 |

Esses números podem crescer se alguém usar o card de teste.

**Lista vazia não prova isolamento.** No card 584 só três fontes têm linha: `agendamento_site`,
`loja` e `stripe`. Nessas três, o isolamento se prova conferindo o `client_id` de cada linha.
Nas fontes com zero, o card 584 não prova nada; quem prova é o teste do CI com os dois cards
fictícios. Para provar uma dessas fontes em produção, é preciso um card de teste com linha nela.
Criar essa linha é escrita, e fica para a rodada de escrita.

## 7. Funções: leitura, escrita e o que não está exposto

| tipo | funções |
|---|---|
| **só leitura** (19), banco aberto em `mode=ro` | `urace_resumo`, `urace_atencao`, `urace_estoque`, `urace_estoque_item`, `urace_clientes`, `urace_cliente`, `urace_invoices`, `urace_corridas`, `urace_cliente_reservas`, `urace_cliente_pedidos`, `urace_cliente_pagamentos`, `urace_auditoria`, `urace_precos_cobrados`, `urace_kommo_conta`, `urace_kommo_funis`, `urace_kommo_leads`, `urace_kommo_lead`, `urace_kommo_conversa`, `urace_kommo_chats` |
| **lista do que dá para operar** (lê) | `urace_operacoes`: responde com `opera` e `por_que` |
| **escrita** | `urace_api` com método diferente de GET. Exige o escopo de operar no conector **e** o papel da rota. O que vai para fora ou cobra pede duas chamadas: a primeira devolve `precisa_confirmar` e nada acontece; a segunda leva `confirmar=true`. Toda escrita fica na auditoria como `mcp.call`. |
| **não exposto ao Mio** | login, senhas e chaves (`/ops/api/auth`); área do cliente (`/ops/api/portal`); os laços automáticos e as rotinas de horário (só o liga/desliga das regras, que é rota de gerente); credenciais de integração |
| **não implementado** | filtro por card no Kommo; uma ferramenta própria de "cobrar a equipe" (hoje seria `urace_api POST /ops/api/equipe/canais/{id}/mensagens`, que é escrita); convite de renovação do plano mensal |

## 8. O que continua bloqueado (sem mudança)

Escrita só depois de:
- autorização específica do Ítalo para ampliar o acesso;
- destinatário interno de teste;
- invoice exata, quando houver;
- efeito esperado, escrito antes;
- prova de que a primeira chamada (`precisa_confirmar`) não fez nada;
- evidência na auditoria;
- conferência de que repetir não duplica;
- sessão OPERATOR autorizada para o teste de recusa por papel.

O card 584 é de produção, não é sandbox. O plano completo está em
`brain/10_PROCESSOS/Mio - papel em cada fluxo.md`.
