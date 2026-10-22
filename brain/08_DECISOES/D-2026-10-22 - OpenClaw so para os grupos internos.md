---
tipo: decisao
data: 2026-10-22
area: SISTEMAS
fonte: dono (mensagem de 22/10)
issue: "#383"
status: ativo
---

# OpenClaw no WhatsApp só para a VPS acessar os grupos internos

**Dono, 22/10:** *"vamos usar o openclaw somente para dar a vps acesso aos grupos internos da urace"*.

Liga com: [[VPS e OpenClaw]] · [[Sistemas]]

## O que vale

- O canal de WhatsApp do OpenClaw entra pelo WhatsApp Web (login por QR, `openclaw channels login --channel
  whatsapp`). Não é a API oficial da Meta, e o número logado corre risco de banimento. Por isso ele serve
  **só** para a VPS acessar os **grupos internos** da URACE.
- **Nunca o número de cliente.** O atendimento de cliente continua no Kommo; nada sai para cliente por esse canal.
- Conversa individual (DM) fica desligada; só os grupos da lista entram.
- O handoff do SDR por WhatsApp (#228) continua **pausado**; esta decisão não o retoma.
- O WhatsApp da equipe pela API oficial (`command_center/providers/whatsapp.py`) segue como está, em simulação.

## Em aberto (perguntas da #383)

Número que fica logado, nomes dos grupos, se a VPS só lê ou também escreve, e o que o painel faz com o que lê.
