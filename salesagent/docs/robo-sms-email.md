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
| SMS só com STOP, PARE, UNSUBSCRIBE, CANCEL… | **não responde** (o Dialpad confirma e bloqueia o contato) e nunca mais escreve; UNSTOP devolve |
| SMS só com HELP / INFO | **não responde**: o Dialpad manda a mensagem de ajuda do escritório |
| "pare de mandar mensagem", "unsubscribe" no e-mail | confirma uma vez e nunca mais escreve para o contato |
| Cliente do painel, oportunidade com o closer, card do Kommo fora das etapas do robô ou com tag de passagem | **não responde**: é da equipe |
| Conversa que o robô já passou para a equipe | **fica quieto** até alguém marcar resolvido |
| Falhou o envio (Dialpad ou Gmail recusou) | vira **Precisa de atenção** |
| Canal ligado depois de dias desligado | **não responde e-mail velho** (só o que chegou nos últimos 30 min) |
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
   O painel lê o arquivo na hora (sem reiniciar). Para o SMS sair pelo número da empresa (e não pela linha pessoal do usuário), acrescente
   `DIALPAD_SMS_GRUPO=office:6037417788784640` (o escritório Urace.us) em `~/.urace/dialpad.env` e reinicie o painel.
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
| `SDR_CANAL_LOTE_MIN` | 60 | de quantos em quantos minutos ele responde (uma volta por hora cheia); `0` = na hora |
| `SDR_CANAL_HORARIO` | 8-18 | expediente de Orlando: voltas das 8h às 18h (a das 18h fecha o dia); fora dele, a mensagem espera a manhã |
| `SDR_CANAL_DIAS` | 1-7 | dias do expediente (1 = segunda … 7 = domingo); `1-5` = só dias úteis, `1-6` = até sábado |
| `SDR_CANAL_ESPERA_MIN` | 10 | SMS que chegou há menos que isso fica para a volta seguinte (a pessoa ainda está escrevendo) |
| `SDR_CANAL_FILA_HORAS` | 72 | SMS mais velho que isso não é respondido pela volta (cobre o fim de semana) |
| `SDR_CANAL_EMAIL_IDADE_H` | 72 | e-mail mais velho que isso (cabeçalho Date) que o robô nunca viu não é respondido: fica com a equipe |
| `SDR_CANAL_EMAIL_MIN` | 3 | só com `SDR_CANAL_LOTE_MIN=0`: de quantos em quantos minutos ele lê a support@ |
| `SDR_CANAL_RAJADA_SEG` | 8 | só com `SDR_CANAL_LOTE_MIN=0`: quanto ele espera mensagens seguidas no SMS antes de responder |

**Expediente também na hora (dono, 22/10).** Com `SDR_CANAL_LOTE_MIN=0` o robô responde na hora, mas só no
expediente (`SDR_CANAL_HORARIO`, `SDR_CANAL_DIAS`). O que chega fora dele (SMS e formulário do site) espera a
abertura do dia seguinte: logo na abertura, uma volta responde tudo. O formulário fora do expediente
recebe a confirmação de sempre na hora e o follow-up do robô na abertura. Para responder sempre:
`SDR_CANAL_HORARIO=0-24` e `SDR_CANAL_DIAS=1-7`.

**Ritmo (dono, 21/10).** "Fazer por loop, horário comercial e de hora em hora, porque não parece automação quando
leva um tempinho para responder." O robô não responde na hora: a cada hora cheia do expediente ele responde, de uma
vez, o SMS e o e-mail que esperam; o que chega à noite sai na volta das 8h. Restart do serviço no expediente faz uma volta cerca de um minuto depois. STOP, HELP, o eco do robô e "a pessoa
assumiu" continuam valendo na hora em que chegam. O formulário do site continua respondendo na hora (quem preenche
espera a confirmação).

## Onde está a configuração

`GET /ops/api/sdr/canais` mostra o caminho do `sdr-canais.env` que o painel está lendo e se o arquivo existe. Ele fica
na mesma pasta do `bridge.env` (a `URACE_DIR` do serviço). Se aparecer `existe: false`, o arquivo foi criado em outra
pasta.

## Formulário do site (dono, 20/10: "ele monta o e-mail para follow up")

Com o e-mail ligado, quem preenche o formulário de contato recebe o follow-up **escrito pelo robô**, saindo da
support@, no lugar da confirmação genérica. A oportunidade nova em Vendas (NOVO, sem closer) é lead para o robô; a
resposta da pessoa cai na support@ e segue com ele. Quando um closer pega a oportunidade (ou ela passa de NOVO), o
robô sai. Se o robô não conseguir responder, sai a confirmação de sempre. A equipe continua avisada como antes.

## Tela

Painel → Robô SDR → **Robô no SMS e no e-mail**: as conversas, o que está ligado, e os botões Ver conversa,
Pausar, Reativar e Resolvido.

## Em aberto

- **10DLC (trava do SMS)**: sem campanha A2P **Registered**, as operadoras bloqueiam SMS do número da empresa
  para celulares dos EUA. Conferir em Admin Portal → Company Settings → SMS Management → SMS Registration
  (`dialpad.com/campaignregistration`, só Company Admin). A campanha precisa marcar mensagem **automatizada e
  conversacional**, ter 2+ exemplos com "URACE", objetivo e "Reply STOP to opt out", e o site precisa da política
  de SMS (dado de celular não é compartilhado para marketing). Aprovação leva ~3 semanas. O Dialpad já trata
  STOP, UNSTOP e HELP sozinho. **Só ligar `SDR_CANAL_SMS` com a campanha Registered**; o e-mail não depende disso.
