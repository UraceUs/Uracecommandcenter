# Campanha 10DLC do robô no SMS (Dialpad)

Dono, 22/10: "registrar uma campanha 10DLC que declare resposta automática". A campanha atual do número do escritório
(CKO11QL, tipo UCAAS_LOW, "conversational, low volume") não diz que há resposta automática. O robô agora responde
todo lead por SMS, então a operadora precisa ver isso declarado. Quem registra é o dono (ou a extensão logada no
Dialpad): este arquivo traz o texto pronto e o prompt.

Antes de enviar: a política de privacidade com a seção de SMS (seção 8 de
<https://ops.urace.us/legal/privacy.html>) precisa estar no ar. Ela sobe com o deploy normal do painel.

## O que preencher

| Campo | Valor |
|---|---|
| Marca | a já registrada da URACE.US INC (não criar outra) |
| Caso de uso | **Customer Care** (se o Dialpad só oferecer "Mixed", usar Mixed com Customer Care + Account Notification) |
| Número | o do escritório (407) 250-2291 |
| Links no texto | sim (páginas de urace.us) |
| Telefone no texto | sim |
| Conteúdo por idade, empréstimo, afiliado | não |
| Resposta automática / IA | **sim** |

**Descrição da campanha**

> URACE.US INC is a kart racing school in Orlando, FL. This campaign covers replies to customers and prospective
> customers who text our business line, (407) 250-2291, with questions about our classes, track sessions, prices and
> scheduling. Replies may be written by an automated AI assistant; our staff monitor every conversation and can take
> over at any time. We do not send marketing or promotional campaigns by text.

**Como a pessoa entra (opt-in / message flow)** (se o número também aparece no Google ou no Instagram, acrescente; só o que for verdade)

> Consumers start the conversation by texting our business number, which is published on our website urace.us.
> Their first message is their consent to
> receive replies about that conversation; we only reply to people who texted us first. Message frequency varies with
> the conversation. Message and data rates may apply. Reply STOP to opt out, HELP for help. Privacy policy (section 8,
> Text messages): https://ops.urace.us/legal/privacy.html

**Mensagens de exemplo**

1. `Hi! This is Chase from URACE, the karting school in Orlando. Is the racing for you or for someone else, and how old is the driver?`
2. `Our Academy is a coached program at Orlando Kart Center. Want the schedule for this week? Reply STOP to opt out.`
3. `Got it! A team member will call you today to set up the first session.`

**Palavras-chave e respostas** (o Dialpad trata sozinho; conferir se o texto bate)

| Palavra | Resposta |
|---|---|
| STOP | `URACE: you're unsubscribed and won't receive more texts. Reply START to resubscribe.` |
| HELP | `URACE: for help call (407) 250-2291 or email support@urace.us. Msg & data rates may apply. Reply STOP to opt out.` |
| START | `URACE: you're subscribed to replies from URACE. Msg frequency varies. Msg & data rates may apply. Reply HELP for help, STOP to opt out.` |

## Prompt para a extensão logada no Dialpad

```
Você está logado no Dialpad da URACE (admin). Tarefa: registrar ou atualizar a campanha 10DLC do número do escritório
(407) 250-2291 para declarar que há resposta automática (IA) aos clientes que mandam SMS.

Regras: NÃO mande SMS para ninguém. NÃO apague a marca nem a campanha atual (CKO11QL) antes da nova estar aprovada.
NÃO mexa em usuários, números, roteamento ou outras configurações. NÃO copie nem mostre chave de API ou segredo.

1. Abra Admin Settings > Office "Urace.us" > Messaging / 10DLC (ou "SMS compliance"). Anote: marca, campanha atual,
   tipo, status e se o Dialpad deixa editar a campanha ou criar outra.
2. Se der para criar/editar: use a marca existente, caso de uso "Customer Care" (ou "Mixed" se for o único que
   aceita IA/resposta automática), marque que há resposta automática/IA, e preencha descrição, message flow,
   exemplos e respostas de STOP/HELP/START exatamente com os textos do arquivo
   salesagent/docs/dialpad-10dlc-campanha.md (colados abaixo). Associe só o número (407) 250-2291.
3. Antes de enviar, abra https://ops.urace.us/legal/privacy.html e confirme que existe a seção "8. Text messages (SMS)".
   Se não existir, PARE e avise.
4. Envie. Se aparecer taxa, anote o valor. Se o Dialpad pedir chamado no suporte em vez de formulário, abra o chamado
   com os mesmos textos.
5. Relate: o que existia, o que foi enviado, ID da nova campanha (ou do chamado), status, taxa e prazo de aprovação.

[cole aqui as seções "O que preencher", "Descrição", "Como a pessoa entra", "Mensagens de exemplo" e
"Palavras-chave e respostas"]
```

Depois da aprovação: a campanha antiga sai do número quando a nova estiver ativa (o Dialpad faz a troca; não apagar
antes).
