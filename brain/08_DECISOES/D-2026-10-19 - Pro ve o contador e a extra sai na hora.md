---
tipo: decisao
data: 2026-10-19
area: AGENDA
fonte: dono (mensagens de 19/10, com print da área do cliente do card #584)
issue: "#340"
status: ativo
complementa: "D-2026-10-16 - Academy recorrente, pacote e sessao extra"
---

# Piloto pro vê o contador, marca só o serviço do plano e a extra sai na hora

**Dono, 19/10:** *"verifica para mim como esta a marcação dos pilotos pro, ela deve ser diferente pois eles ja
pagam mensal, entao precisa mostrar tanto para nos quanto para eles a quantidade de sessões que eles tem pagas ou
em aberto, e nao cobrar na marcação e sim na invoice pelo QuickBooks."*

Com o print da área do cliente do card #584 (a tela "Book a session" de cliente novo, com os 5 serviços do
Arrive and Drive com preço e o calendário de um dia só): *"esse cliente é pro e quando ele vai marcar na area do
cliente dele ainda aparece assim; precisaria aparecer a quantidade de sessões que ele tem paga p pode marcar,
permitir ele marcar mais de uma sessão de uma vez, e se ele selecionar mais do que ele tem paga ja gerar a
invoice e enviar das sessões a mais; no print mostra todos os serviços disponiveis"*.

Sobre o "pagas ou em aberto": *"sessões do pacote usadas e ainda livres; em aberto = sessões que possam ter sido
feitas mas não foram pagas ainda, isso precisa ser contabilizado pelas invoices do cliente e pelos serviços
prestados"*. Sobre a mensalidade do mês em aberto (o pro continua podendo marcar?): *"pode"*. Sobre os serviços
do plano: *"deixe os add ons disponiveis tb"*.

Liga com: [[D-2026-10-16 - Academy recorrente, pacote e sessao extra]] · [[Urace Academy]]

## Por que o card #584 via a tela de cliente novo

O card #584 é ★ Pro Racing Driver, mas a Mensalidade estava vazia (sem sessões por mês, sem valor mensal, sem
tipo mensal). A regra 8 de [[D-2026-10-16 - Academy recorrente, pacote e sessao extra]] diz que o pro sem mensal
no card não é recorrente — então a área do cliente o tratava como cliente novo (preço, carrinho, um dia).

## O que vale agora

- **O contador vai para o cliente** (muda a de 01/10, *"não deixa o cliente ter essa informação"*, e a regra 1
  de 16/10). No Dashboard e em Book sessions, por piloto: *"This month: X of Y sessions used · Z left · resets
  on the 1st"*, a **mensalidade do mês** pelo espelho do QuickBooks (Paid, Open com o link de pagar, ou "—"
  sem invoice), as **extras do mês** com a situação da invoice delas e o **em aberto**. A equipe vê o mesmo no
  card (Mensalidade e contrato › "O que o cliente vê") e na lista de Agendamentos.
- **Em aberto** = sessão já feita (agendamento do site com data passada e não cancelado; tarefa do Asana do mês
  que conta no card) que não está coberta por invoice paga: a do pacote pela mensalidade do mês dela, a extra e a
  avulsa pela invoice dela. Valor = saldo das invoices abertas ligadas a essas sessões; sem invoice, "not invoiced
  yet", **sem valor** (NO FAKE DATA). Olha os últimos 3 meses. A equipe vê quais sessões e quais invoices.
- **Mensalidade em aberto não trava a marcação** (dono: *"pode"*): só aparece.
- **Pro sem mensalidade no card** → item em **Precisa de atenção** ("Piloto pro sem mensalidade no card: preencha
  sessões por mês e valor mensal") e aviso no card. O painel **não inventa** sessões nem valor. Enquanto isso, na
  área do cliente: *"Your monthly plan is being set up by our team"*, sem preço e **sem carrinho**; o pedido vai
  para a equipe e o Aceitar **não** cria invoice pelo preço da tabela. Preenchida a Mensalidade, a rodada
  seguinte aloca no pacote (ou extra) e cobra certo.
- **O pro nunca vai para o Stripe** (nem a avulsa): o carrinho do site recusa a sessão dele.
- **Só o serviço do plano:** o recorrente vê só o serviço do kart do plano (o Plano mensal do card ou o plano do
  site; "Academy 4 stroke" → Arrive and Drive 4-stroke). Os outros ficam atrás de "Book as a regular session".
  Plano sem kart no nome mostra todos.
- **Add-ons continuam** (dono: *"deixe os add ons disponiveis tb"*): hoje o Lead and Follow, com o preço do
  painel, por dia. Nunca no Stripe: entra na invoice do QuickBooks do pedido, junto com as extras; pedido só do
  pacote com add-on gera uma invoice só com os add-ons.
- **A extra sai na hora:** no pedido (um ou vários dias), a invoice do QuickBooks das extras e dos add-ons é
  **criada e enviada na marcação**, sem esperar a equipe aceitar a vaga: uma invoice por pedido, sem depósito.
  Pedido só do pacote, sem add-on, não cria invoice. Falha do QuickBooks fica escrita no agendamento e a rodada
  seguinte tenta de novo (até 3 vezes) com a **mesma requestid**: o QuickBooks não cria a segunda.
- **Cancelar** a extra (ou a sessão com add-on) com a invoice já enviada → **Precisa de atenção**; a equipe ajusta
  no QuickBooks. O painel não mexe sozinho no QuickBooks.

## As escolhas do Claude (a confirmar com o dono)

1. Enquanto o card do pro não tem Mensalidade, ele **pode pedir** a sessão (vai para a equipe), sem preço e sem
   carrinho; a cobrança espera a Mensalidade (nunca o preço da tabela).
2. "Só o serviço do plano" depende do **kart no nome do plano**. O card #584 precisa, além de sessões e valor, do
   **Plano mensal** (ex.: "Academy 4 stroke"); sem ele, a tela mostra todos os serviços (como antes).
3. Com a invoice da extra saindo na marcação, a regra 9 de 16/10 (a extra ainda não cobrada vira do plano quando
   uma do pacote é cancelada) só vale quando a invoice falhou e ainda não saiu.
4. O "em aberto" olha os últimos 3 meses.
5. A sessão do pacote com add-on continua do pacote (confirma como antes); só o add-on é cobrado.

## Onde está no sistema

- Regra: `command_center/providers/contrato.py` (`contador`, `em_aberto`, `mensalidade_do_mes`, `pro_sem_mensal`,
  `servicos_do_plano`); cobrança na marcação: `providers/cobranca_agenda.py` (`cobrar_pedido`); pedido:
  `providers/agenda_lote.py`; área do cliente: `GET /ops/api/portal/plan` (`counter`), `web/src/portal/Contador.tsx`.
- Playbooks: `docs/playbooks/playbook-vendas.md` ("Piloto pro") e `playbook-geral.md` (Mensalidade e contrato).

## O que a equipe faz no card #584

Preencher a Mensalidade (sessões por mês e valor mensal, os combinados com o cliente) e o Plano mensal (o kart).
