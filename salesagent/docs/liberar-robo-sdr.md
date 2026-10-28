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
   leads, card fechado, funil fora do SDR e conversa com a IA pausada.

Liberado em 27/10 (a linha foi comentada, `#SDR_ATENDER_SO_TAG=teste-sdr`, com backup em `bridge.env.bak-AAAA-MM-DD`).

## Quando uma pessoa assume a conversa (regra de ouro)

O robô **não sabe** quando alguém da equipe escreve no chat. Antes de responder um lead à mão, faça **uma** destas:

- clicar em **Pausar IA** no chat do Kommo, ou na página Robô SDR → "Conversas com a IA pausada".

Desde 27/10 (#403) mover o card para ATENDIMENTO **não** para o robô: ele responde em qualquer etapa. Só Pausar IA
(ou fechar o card) tira o robô da conversa.

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
