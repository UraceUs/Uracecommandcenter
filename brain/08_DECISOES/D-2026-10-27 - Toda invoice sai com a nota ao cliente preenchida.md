---
data: 2026-10-27
quem: Italo
issue: 402
---

# D-2026-10-27 — Toda invoice sai com a nota ao cliente preenchida

[[URACE]] · [[Invoice e estimate no QuickBooks]] · [[PARAMETROS]] · [[QuickBooks]]

## O que o dono disse

> *"Eu preciso as invoices que estão sendo enviadas pelo Command Center. Colocar ali no memo e nas
> instruções de pagamentos, se forem de partes, colocar que são de partes. O Command Center enviou
> uma invoice e não tinha nada escrito nela, então eu preciso que isso seja corrigido. Por exemplo,
> se for um training day, aí ela lê o que está nos itens da invoice e coloca lá no memo e no payment
> instructions do que é, qual a data. Para de agora em diante fazer isso em todas as invoices."*

E, no mesmo dia: *"sempre traga para aprovar e enviar daqui"*.

## A decisão

1. **Nenhuma invoice, estimate ou recorrência sai com a nota ao cliente vazia.** Invoice em branco é
   defeito, não é "faltou o memo".
2. Quando quem cria não escreve a nota, ela é **montada das próprias linhas**:
   - **peça** → `Parts | <as peças> | <piloto> | Service date: MM/DD/AAAA`
   - **serviço** → `<nome do serviço> | <piloto> | Service date: MM/DD/AAAA`
   - embaixo, a **instrução de pagamento** com o vencimento: *"Parts used on the service date above.
     Payment due by 10/29/2026."*
3. **"Memo on statement" continua igual à nota ao cliente** (regra do dono de 10/09).
4. **Inglês**, porque é o cliente que lê.
5. **O envio é pelo painel.** A IA traz a invoice para aprovação no Command Center e, aprovada, ela
   sai. A IA não manda o dono abrir o QuickBooks para clicar em enviar. Isto **substitui** a linha de
   31/08 em [[PARAMETROS]] ("e-mail de invoice sai pelo próprio QuickBooks").

## Por que

Uma invoice de peças emitida em 27/10 (o cliente está no card do painel) saiu com a nota
"Parts | Urace Academy": sem o piloto, sem a data do uso e sem dizer o vencimento. Pelo caminho
genérico do MCP a nota era **opcional** — quem criasse a invoice sem passar o texto mandava uma
invoice em branco para o cliente. O cliente recebe uma cobrança sem saber do que é.

## Onde isto virou código

`adminai/mcp/quickbooks_mcp.py`: `memo_das_linhas()` monta o texto, e `qbo_criar_invoice`,
`qbo_criar_e_enviar_invoice`, `qbo_criar_estimate` e `qbo_criar_recorrencia` a usam quando quem
chamou não mandou memo. As três primeiras ganharam `data_servico` e `piloto`. Teste:
`command_center/tests/test_qbo_memo.py`.

Os caminhos internos (balcão, peças do dia, mensalidades, cobrança pela agenda) já passavam a nota e
continuam mandando no texto; a montagem automática é a rede de segurança de todos os outros.

## Em aberto

- O QuickBooks **não tem** um campo de "payment instructions" por invoice: a API expõe só
  "Note to customer" (`CustomerMemo`) e "Memo on statement" (`PrivateNote`). Por isso a instrução de
  pagamento vai na segunda linha da nota ao cliente. O texto fixo de como pagar fica nas
  configurações da conta (Sales › Messages), que é global. [[PENDENTE DE VALIDAÇÃO]] se o dono quer
  também mudar esse texto global.
