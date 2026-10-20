# Robô SDR no SMS (Dialpad) e no e-mail (support@)

Dono, 20/10: "esse robô precisa ler o Dialpad para atender por lá e e-mail também". Decisões dele:
**envio automático, igual ao Instagram**; e-mail **só a support@ e só lead**; o SMS chega **pelo VPS**
(o Heroku antigo não existe mais).

O robô é o mesmo do Instagram (persona, rotas, preço da tabela, oferta de call, 12 idiomas). O painel é
quem recebe, filtra, envia e guarda a conversa. **Tudo começa desligado.**

## O que ele faz e o que ele nunca faz

| Situação | O robô |
|---|---|
| Lead manda SMS para o número da empresa | responde em balões curtos, pelo número da empresa |
| Lead escreve para support@ | responde na mesma conversa, num e-mail curto, assinado "Chase, URACE" |
| "Oi" e "quanto custa" logo em seguida | espera 8 s e responde uma vez só |
| Objeção, pronto para fechar, já compete, pede pessoa | oferece a call (ou a frase de espera) e a conversa entra em **Precisa de atenção** |
| "pare" / STOP / unsubscribe | confirma uma vez e nunca mais escreve para o contato |
| Cliente do painel ou oportunidade com o closer | **não responde**: é da equipe |
| E-mail automático, newsletter, lista, resposta de férias, @urace.us, já marcado por filtro do Gmail | **ignora** |
| Uma pessoa da equipe responde à mão (SMS pelo Dialpad ou e-mail na conversa) | **pausa o robô naquele contato** por 72 h; para voltar: `POST /ops/api/sdr/canais/{id}` com `reativar` |
| Nível do robô em Observar ou Organizar | não envia nada |
| Follow-up por SMS ou e-mail | **não existe nesta fase** (SMS de follow-up é solicitação pela lei da Flórida) |

## Ligar, passo a passo (VPS, uma linha por vez)

1. **Código no ar** (as duas partes):
   `cd ~/Uraceagent && git pull origin claude/commandcenter-vps && sudo systemctl restart sales-bridge && bash adminai/deploy/command_center/servir_command_center.sh`
2. **Assinatura de SMS no Dialpad** (só lê o dialpad.env, nunca mostra chave):
   `python3 adminai/deploy/dialpad_sms.py` para ver, depois `python3 adminai/deploy/dialpad_sms.py --criar`.
   Voltar atrás: `python3 adminai/deploy/dialpad_sms.py --apagar ID`.
3. **Primeiro SMS de teste, com o robô ainda desligado**: mande "oi" de um celular para o número da empresa e
   confira o evento como chegou: `sudo head -c 1500 /root/.urace/dialpad-webhook-ultimo.json`. É ele que
   confirma o nome dos campos do SMS (o painel aceita as variações conhecidas).
4. **Ligar só para o seu celular e um e-mail de teste** (o papel da tag `teste-sdr`):
   `printf 'SDR_CANAL_SMS=1\nSDR_CANAL_EMAIL=1\nSDR_CANAL_SO_PARA=+1SEUNUMERO,seu.email@exemplo.com\n' > ~/.urace/sdr-canais.env && chmod 600 ~/.urace/sdr-canais.env`
   O painel lê o arquivo na hora (sem reiniciar). Se o SMS não sair pelo número da empresa, acrescente
   `DIALPAD_SMS_FROM=+1NUMERODAEMPRESA` em `~/.urace/dialpad.env` e reinicie o painel.
5. **Teste**: SMS "Oi, quanto custa?" do seu celular; e-mail para support@ do seu e-mail. Confira a conversa:
   `GET /ops/api/sdr/canais` (ou peça a mim).
6. **Liberar para todos os leads**: apague a linha `SDR_CANAL_SO_PARA` de `~/.urace/sdr-canais.env`.

## Desligar

- Um canal: troque `SDR_CANAL_SMS=1` (ou `EMAIL`) por `0` em `~/.urace/sdr-canais.env`. Vale na hora.
- Tudo: nível do robô em **Organizar** no painel.

## Ajustes (no `~/.urace/sdr-canais.env`)

| Linha | Padrão | O que faz |
|---|---|---|
| `SDR_CANAL_PAUSA_HORAS` | 72 | quanto tempo o robô fica fora depois que uma pessoa responde |
| `SDR_CANAL_EMAIL_MIN` | 3 | de quantos em quantos minutos ele lê a support@ |
| `SDR_CANAL_RAJADA_SEG` | 8 | quanto ele espera mensagens seguidas no SMS antes de responder |
