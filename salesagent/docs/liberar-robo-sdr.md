# Liberar o robô SDR para todos os leads (e como voltar atrás)

Decisão D-2026-10-13. O robô hoje só responde card com a tag `teste-sdr` (`SDR_ATENDER_SO_TAG`).
Este roteiro é para tirar essa trava, com a segurança de poder desligar em um minuto.

## Antes de liberar (10 minutos)

1. **Pré-voo.** No VPS: `cd ~/Uraceagent && git pull` e depois o script abaixo, com o mesmo Python que roda a
   ponte. Ele não escreve nada, não manda mensagem e não imprime chave. Corrija toda linha `FALHA`.
   ```
   python3 salesagent/tools/sdr_preflight.py
   ```
2. **Teste no painel.** `ops.urace.us/ops/sdr` → "Testar o robô": "Oi, quanto custa?", "É meu filho, 8 anos",
   "Nunca andou de kart", "Faria se fosse mais barato", "Quero fechar", "Agora não". Confira tom curto, uma
   pergunta por vez, sem nome de ninguém do time e a oferta de call no fim.
3. **Teste no Instagram** com um lead novo com a tag `teste-sdr`: "Oi" e "Quanto custa?" em seguida deve
   gerar **uma** resposta só.

## Liberar

1. No VPS, abra `~/.urace/bridge.env` e **apague a linha** `SDR_ATENDER_SO_TAG=teste-sdr`.
2. `sudo systemctl restart sales-bridge && systemctl is-active sales-bridge`
3. A partir daí o robô responde todo lead do Instagram e do Facebook com card aberto nos funis Urace e Comercial,
   **em qualquer etapa, inclusive as da equipe** (dono, 27/10, #403: "responde imediatamente"). Não recebe: Incoming
   conversa com a IA pausada e card fechado com a tag `opt_out`. **Desde 30/10 (#530) o robô responde em todo funil
   do Kommo e em Incoming leads** (dono: "conectado em todos os lugares p responder todos"); card de Pós Venda ou
   Operacional Vendas é atendido como aluno. A organização do card (etapa, tags) continua só em Urace e Comercial.
   **Card fechado que volta a falar (dono, 28/10, #428):** o robô responde; o perdido volta para Comercial >
   ENTRADA com a tag `sdr:reaberto`, e o ganho (cliente) fica como está, com a tag `sdr:cliente-voltou`.

Liberado em 27/10 (a linha foi comentada, `#SDR_ATENDER_SO_TAG=teste-sdr`, com backup em `bridge.env.bak-AAAA-MM-DD`).

## Um robô só, do jeito certo em cada interação (dono, 30/10, #523)

O Chase é o mesmo no Instagram, no Facebook, no WhatsApp, no SMS e no e-mail. Comentário em foto ou post e DM
são do robô; aluno e cliente também. Cada interação tem a sua resposta:

| Chega | O robô |
|---|---|
| Menção ou resposta em story ("Mentioned you in their story") | um obrigado curto, uma vez por dia, sem venda e sem follow-up |
| Reação ou curtida | nada |
| Comentário curto ou emoji ("Racing🤩", "10/10") | uma frase de social media, sem triagem, sem preço e sem link |
| Aluno ou cliente (disse que já é aluno, card ganho, cliente do painel no SMS e no e-mail) | atende sem triagem, sem call de venda e sem link de reserva; agenda e pagamento vão para o time; sem trilha de follow-up |
| Pergunta de lead novo | como sempre: responde, qualifica e leva à call |

Uma resposta tem no máximo 3 balões, e a espera só cita o que é pergunta. Os bots nativos do Kommo (menu
"URACE - Atendimento inicial DM" e "Agente qualificador de leads") ficam desligados nas DMs: dois robôs não
respondem a mesma pessoa.

## Quando uma pessoa assume a conversa (regra de ouro)

O robô **não sabe** quando alguém da equipe escreve no chat. Antes de responder um lead à mão, faça **uma** destas:

- clicar em **Pausar IA** no chat do Kommo, ou na página Robô SDR → "Conversas com a IA pausada".

Desde 27/10 (#403) mover o card para ATENDIMENTO **não** para o robô: ele responde em qualquer etapa. Só Pausar IA
tira o robô da conversa: fechar o card não, porque desde 28/10 (#428) mensagem nova em card fechado reabre.

Se não fizer, o robô e a pessoa podem responder juntos. Para voltar a automatizar: "Reativar IA".

## Primeira hora depois de liberar

- Painel Robô SDR → "O que o robô decidiu": veja as decisões entrando.
- No VPS: `sudo journalctl -u sales-bridge --since "1 hour ago" --no-pager | grep -iE "error|429|nota|fallback" | tail -30`
  - `429`: o Kommo limitou as chamadas (cada balão é um disparo do bot de entrega). Avise e baixe o nível.
  - `resposta gravada como nota, não entregue`: a entrega falhou naquele lead; uma pessoa responde à mão.
- Um lead ficou sem resposta? `GET /ops/api/sdr/rastro/{lead_id}` (ou peça ao Claude) diz por quê: a trava
  (IA pausada, card fechado, Incoming leads, já respondido por SMS, não é lead) ou o erro (#414).
- Tags para filtrar no Kommo: `followup:1-call`, `followup:2-reativacao`, `followup:sem-resposta-24h`,
  `sdr:agora-nao`, `sdr:handoff`.

## Voltar atrás

- **Parar de responder, mantendo a organização dos cards:** painel Robô SDR → nível **Organizar**.
- **Parar tudo:** nível **Observar**.
- **Uma conversa só:** Pausar IA nela.
- **Voltar ao escopo de teste:** recoloque `SDR_ATENDER_SO_TAG=teste-sdr` em `~/.urace/bridge.env` e reinicie a ponte.

## O que o robô faz sozinho (resumo)

- Responde em balões curtos, uma pergunta por vez, sem link na primeira resposta, sem nome de ninguém do time.
- Preço só o da tabela (taxa da pista sempre à parte). Nunca desconto, nunca confirma data.
- Qualificado (idade, experiência, objetivo) ou com objeção ou pronto para fechar ou já competindo: oferece a
  call de 15 min com o nosso time e avisa a equipe.
- "Agora não": agradece, não insiste, tarefa em 7 dias. "Pare de mandar": confirma e fecha o card como perdido.
- Sem resposta: ~1h30 sugere a call, 23 h depois faz um check-in, e para (janela de 24 h da Meta). Nada sai
  entre 21h e 8h de Orlando.
