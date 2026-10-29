# Suits · Alpha Line — guia para operar com o Claude

> **Para quem é:** o Lucas, e o Claude que trabalha com ele.
> **Como usar:** cole este arquivo inteiro nas instruções de um Projeto do Claude (claude.ai ›
> Projetos › Instruções do projeto), ou salve como `CLAUDE.md` na pasta em que você abre o Claude
> Code. A partir daí, o Claude sabe como a aba Suits funciona, o que pode fazer sozinho e o que
> tem de perguntar antes.
>
> Atualizado em 22/10/2026 (issue #382, as travas do fluxo e a entrega direta ao cliente; antes, #313 e #195).

---

## 1. O que é a aba Suits

A aba **Suits · Alpha Line** do Command Center (`https://ops.urace.us/ops/suits`; no menu lateral, na área
**Pedidos e compras**) é onde vive
todo pedido de **macacão de kart personalizado**, do primeiro contato até a entrega. Ela
substituiu o quadro SUITS do Asana, que já foi importado para lá.

O macacão é **100% personalizado**: medidas, design, cores, logos e a posição de cada logo são
feitos para aquele cliente. Nada é padrão. Por isso um pedido só anda quando tem duas coisas:
as **29 medidas** do piloto e o **design** aprovado.

Quem trabalha em cada pedido:

| Papel | Quem é | O que recebe |
|---|---|---|
| Cliente | quem comprou (às vezes o pai ou a mãe do piloto) | boas-vindas, manual de medidas, a arte para aprovar |
| Designer | **Mateus** (`carvalhovisual1@gmail.com`) | **só o design**, com a referência "Suits #id". Nunca nome completo, e-mail, telefone, endereço, valor ou pagamento do cliente. O e-mail a ele é **preparado** pela IA e **enviado por uma pessoa** |
| Fornecedor | o escolhido no pedido ou o marcado como **atual** em **Contatos** (hoje o Usman) | o pedido de produção (as 29 medidas e a arte final **aprovada**, sem endereço); depois do OK nas fotos, o endereço do cliente. Manda as fotos pelo WhatsApp e despacha **direto ao cliente** |
| A URACE com o cliente | assina como **George** | — |

### Como a tela mostra cada um (#313)

As três listas usam o cartão do painel inteiro (o "padrão D", playbook geral, seção 3):

- **Pedidos:** em cima, a **etapa** (Standby, Awaiting Measurements…) ou *descartado*; as iniciais do piloto, o nome do
  pedido, o produto, a quantidade e o fornecedor; no **bloco grande, o dia do pedido**; embaixo, **teste** (pedido de
  teste), **IA desligada** e quantas **notas** ele tem. Toque em qualquer lugar do cartão para abrir o pedido.
- **Leads:** a situação (*aberto*, *virou pedido*, *perdido*), o nome, o e-mail e o telefone, a nota; embaixo,
  **Virar pedido** (azul), **Perdido**, **Card do cliente** e **Ver pedido**.
- **Contatos** (#490): os **fornecedores** e os **designers**, cada um com o e-mail fixo e o **Contexto para a IA** (o que
  ele faz, como falar com ele), que vai junto para a IA em cada pedido. O endereço antigo `/suits/fornecedores` leva para cá.
  Nos fornecedores: *atual* em verde em cima, se tem FIA, **quantos pedidos** no bloco grande, os dados (contato,
  valor, frete, prazo…) na lista e **Editar** (gerente).

### A página de um pedido (#464)

- Em cima, as **4 fases**: *Medidas e design* (Standby → Design Under Client Review), *Aprovação* (Approved),
  *Produção* (enviado ao fornecedor → Checked) e *Entrega* (endereço → Delivered). A fase atual diz a etapa e
  quantas faltam nela ("Design Pending · 3 de 4"); passar o dedo/mouse mostra as etapas da fase. Com o pedido
  ligado a um cliente, aparece **Card do cliente #n ↗**.
- **Agora**: o próximo passo do pedido, numa frase.
- No computador, duas colunas: à esquerda Agora, **Nova nota**, a aprovação final, os e-mails preparados e a
  **linha do tempo**; à direita o pedido e o cliente, as medidas, o design, as conversas ligadas (ponte de e-mail,
  WhatsApp, fornecedor) e "Como estava no Asana". No celular, tudo numa coluna.
- A **linha do tempo** vem do mais novo para o mais antigo, **separada por dia**, com filtro **Tudo · Notas ·
  E-mails · WhatsApp · Etapas · IA** (o número ao lado é quantos de cada).

---

## 2. Conectar o Claude ao painel (uma vez)

Você precisa de um **usuário seu no Command Center** com papel **OPERATOR** ou acima. Quem cria é
o dono, na tela **Usuários**. Ninguém manda senha pelo chat.

**No app do Claude (claude.ai, celular ou computador):**
1. Configurações › **Conectores** › **Adicionar conector personalizado**.
2. Nome: `URACE Command Center`. URL: `https://ops.urace.us/ops/mcp`
3. Clique em **Conectar**, entre com o **seu** usuário do painel, marque
   **"Também operar o painel como você"** se quiser que ele opere (desde 21/10 a caixa vem desmarcada)
   e clique em **Autorizar**.

**No terminal (Claude Code):**
```
claude mcp add --transport http urace https://ops.urace.us/ops/mcp
```
Depois, dentro do Claude Code, digite `/mcp`, escolha **urace** e **Authenticate**. Entre com o
seu usuário e marque **"Também operar o painel como você"**.

Sem a caixa marcada, o Claude só lê, mesmo com papel ADMIN: o papel e o conector são travas
separadas. Em **Equipe › Conectar o Claude**, a lista **Seus conectores** mostra cada um como
**Leitura** ou **Operar** e o motivo; se estiver **Leitura**, desconecte e conecte de novo marcando
a caixa. Tudo o que ele faz fica na auditoria do painel com o **seu**
nome.

**Ferramentas que aparecem para o Claude:**
- `urace_operacoes`: lista as operações do painel. Filtre com a palavra `suits`.
- `urace_api`: executa uma operação (método, caminho, corpo). É exatamente o mesmo que clicar no
  botão do painel.
- `urace_resumo` e `urace_atencao`: o panorama e o que precisa de gente hoje.
- `urace_cliente_pedidos` e `urace_cliente_pagamentos` com o `client_id` (número do card): os pedidos
  (Suits incluídos) e os pagamentos só daquele cliente, sem trazer dado de outro.

**Confirmação:** o que manda algo para fora (e-mail, rascunho no Gmail, QuickBooks, Asana) não
acontece na primeira chamada. O painel devolve o que vai fazer. O Claude mostra para você e só
repete com `confirmar: true` depois do seu "pode mandar".

---

## 3. As etapas (desde 22/10, com a entrega direta ao cliente)

O código entre crases é o que vai no campo `status`. Dono, 22/10: *"o envio sera direto ao cliente sem
precisar enviar para a urace ... o fornecedor nos envia fotos dos suit no whats app conferimos e passamos o
endereço para o envio"*.

| # | Etapa | Código | Quando | Trava |
|---|---|---|---|---|
| 1 | Standby | `standby` | pedido criado | — |
| 2 | Awaiting Measurements | `awaiting_measurements` | boas-vindas enviadas (com o manual), esperando as medidas | — |
| 3 | Design Pending | `design_pending` | com as ideias de design: o designer trabalha | — |
| 4 | Design Under Client Review | `design_review` | o cliente está olhando a arte | — |
| 5 | Approved | `approved` | aprovação final escrita do cliente | exige a **aprovação final válida**; sem ela, só o **administrador** libera, com o motivo (#448) |
| 6 | Order sent to supplier | `sent_to_supplier` | pedido de produção enviado ao fornecedor | exige a aprovação válida |
| 7 | Accepted by supplier | `supplier_accepted` | o fornecedor confirmou | — |
| 8 | In Production | `in_production` | o fornecedor está fazendo | — |
| 9 | Photos received | `photos_received` | as fotos do WhatsApp foram subidas como nota | só a equipe |
| 10 | Checked | `checked` | a equipe conferiu as fotos: OK | só a equipe; exige foto |
| 11 | Address sent to supplier | `address_sent` | o endereço do cliente foi ao fornecedor | só a equipe; só depois de Checked |
| 12 | In Transit | `in_transit` | o fornecedor despachou direto ao cliente | exige o rastreio |
| 13 | Delivered | `delivered` | entregue: o pedido fecha e vai para o Histórico | — |
| — | Canceled | `canceled` | cancelado: fecha e vai para o Histórico (reabre em Standby) | — |

**Só as transições permitidas.** De cada etapa o pedido vai para a próxima, volta quando faz sentido
(Approved volta para revisão, Checked volta para Photos received) ou é cancelado. Pular etapa é
recusado com o motivo (`GET /ops/api/suits/etapas` devolve `transicoes`). Pedido novo nasce entre Standby
e Design Under Client Review, ou cancelado.

Cada troca de etapa fica na **linha do tempo** do pedido, com quem trocou e quando.

**Mover à mão (#482).** Quando algo aconteceu fora do Command Center (o cliente aprovou pessoalmente, o pedido já foi
para a produção pelo WhatsApp), o **administrador** escolhe qualquer etapa na Nota do pedido. Se a ordem das etapas ou
uma trava impediria, o botão vira **Mover à mão para …**: escreva o motivo na nota e salve. O motivo fica na linha do
tempo e na auditoria, com o nome. Operador, gerente e a IA continuam com as travas; pela IA, isso vira cartão de aprovar.

---

## 4. As 29 medidas

Vão no campo `medidas.valores`, com a unidade em `medidas.unidade` (`cm` ou `in`) e o peso em
`medidas.unidade_peso` (`kg` ou `lb`). **Grave o número exatamente como o cliente mandou**, na
unidade dele. O painel mostra as duas unidades no e-mail do fornecedor. O tamanho do pé é texto
(`"42 EUR"`, `"9 US"`): não existe conversão exata, então nunca converta.

| # | Chave | Medida |
|---|---|---|
| 1 | `head` | Head circumference |
| 2 | `forehead_neck` | Distance from forehead to neck |
| 3 | `neck` | Neck circumference |
| 4 | `chin_neck` | Distance from chin to neck |
| 5 | `shoulder` | Shoulder width |
| 6 | `chest` | Chest circumference |
| 6bis | `bust` | Bust circumference (só para mulheres) |
| 7 | `waist` | Waist circumference |
| 8 | `hip` | Hip circumference |
| 9 | `neck_back` | Distance from neck to back |
| 10 | `neck_tailbone` | Distance from neck to tail bone |
| 11 | `arm` | Arm length |
| 12 | `elbow_wrist` | Distance from elbow to wrist |
| 13 | `biceps` | Biceps circumference |
| 14 | `elbow` | Elbow circumference |
| 15 | `forearm` | Forearm circumference |
| 16 | `wrist` | Wrist circumference |
| 17 | `thigh` | Thigh circumference |
| 18 | `knee` | Knee circumference |
| 19 | `calf` | Calf circumference |
| 20 | `ankle` | Ankle circumference |
| 21 | `waist_ankle` | Distance from waist to ankle |
| 22 | `groin_ankle` | Distance from groin to ankle |
| 23 | `knee_ankle` | Distance from knee to ankle |
| 24 | `trapezius_ankle` | Distance from trapezius to ankle |
| 25 | `trapezius_floor` | Distance from trapezius to floor |
| 26 | `nipple_ankle` | Distance from nipple to ankle |
| 27 | `height` | Height |
| 28 | `weight` | Weight |
| 29 | `foot` | Foot size (texto) |

Ao abrir um pedido, o painel devolve `faltam_medidas`: a lista do que ainda não chegou. Para
apagar uma medida gravada errada, mande a chave com valor vazio.

**O estado de cada medida** (`estado_medidas`, #382): `preenchida` (chegou), `conferida` (a equipe olhou) ou
`suspeita` (o número parece errado, com o motivo). A IA só marca **suspeita**; conferir é da equipe. Medida
suspeita ou não conferida **trava a aprovação final**. Mudou o valor, a medida volta para `preenchida`.

**Design** (campo `design`): `ideia`, `cores`, `logos`, `posicao_logos`, `nome` (o nome que vai
no macacão), `bandeira`, `observacoes`.

---

## 5. De onde vem um pedido

1. **Venda no site.** Chega o e-mail "[Urace]: You've got a new order" com um macacão. A ponte
   abre o pedido sozinha (origem `site`, com o número do pedido do site) e a IA manda as
   boas-vindas. No site, o cliente chega aos macacões pelo menu **Store ⌄ › Suits** (#394), que
   abre a categoria *Custom kart suits* da loja.
2. **E-mail de cliente.** Um e-mail com o marcador **Suits** do Gmail **só vira candidato** quando
   o assunto ou o texto **falam de macacão** (suit, race suit, macacão, mono de karting,
   combinaison…) e o remetente **não é robô** (noreply, cobrança, recibo, newsletter, aviso).
   Mesmo assim, o pedido só é criado quando a IA lê a conversa e vê que é **alguém querendo
   comprar um macacão**: orçamento, medidas ou design para encomendar, confirmação ou pagamento.
3. **À mão**, pelo botão **Registrar novo pedido** ou pela API, sempre com **"Vincular ao
   cliente"** quando a pessoa já tem card no painel.
4. **Lead que virou pedido** (aba Leads › Virar pedido).

### O que NÃO é pedido de macacão

Nunca abra pedido, e descarte se aparecer um:
- fatura, recibo ou cobrança (Stripe, OpenAI, Anthropic, QuickBooks…);
- newsletter, propaganda, ofertas de milhas, agência de vídeo;
- homologação/FIA, frete, nota fiscal, conversa com fornecedor sem pedido de cliente;
- e-mail da própria equipe (`@urace.us`);
- conversa sobre outro serviço (aula, aluguel, horário de treino);
- dúvida geral sem intenção de comprar. **Na dúvida, não crie.**

Exemplo de 13/10: os pedidos #153 a #163 (faturas, newsletters, propaganda e conversa da equipe)
foram abertos por engano pela versão antiga da ponte, só por causa do marcador. Foram
**descartados**.

---

## 6. A ponte de e-mail (a IA trabalhando sozinha)

**Designers, fornecedores e as conversas do pedido (#481).** Na aba **Suits › Contatos** ficam os fornecedores e os
**designers** (nome, e-mail fixo e o contexto para a IA; o gerente cadastra; um é o **atual**). A IA recebe, em cada
pedido, quem são o designer e o fornecedor dele, com esse contexto. Na **Ponte de e-mail** de cada
pedido você vê o e-mail do cliente e **escolhe o designer e o fornecedor** numa lista — o e-mail vem do cadastro
("vai para …"); sem escolha, vale o atual. **Puxar conversas do Gmail** procura e liga as conversas que faltam: com o
cliente (pelo e-mail dele, a que fala de macacão), com o designer (a que cita "#número do pedido") e com o fornecedor
(a que traz o nome do piloto no assunto). Na primeira vez que o pedido abre sem a conversa do cliente, ele procura
sozinho. Só lê o Gmail: nada sai. A ponte reconhece e-mail de **qualquer** designer da lista, e o cliente nunca vê
nome nem e-mail de nenhum deles.

A cada 15 minutos a ponte lê o Gmail `urace@urace.us` e, para cada novidade, chama a IA do
painel com o pedido e o e-mail (anexos baixados para a pasta do pedido):

| Chegou | A IA faz |
|---|---|
| venda de macacão no site | preenche o pedido, manda as boas-vindas com o manual de medidas (PDF), move para `awaiting_measurements` |
| resposta do cliente | grava medidas e design que vieram, pede **só o que falta**, marca medida estranha como suspeita; com design suficiente, **prepara** o briefing ao designer e move para `design_pending` |
| resposta do designer | pergunta: leva ao cliente com as palavras da URACE; arte entregue: marca a **arte final**, manda ao cliente pedindo aprovação e move para `design_review` |
| arte final marcada e medidas conferidas | manda o **e-mail de aprovação final** (versão, arte anexada, medidas e a política: não retornável, não reembolsável) |
| o cliente aprova **por escrito essa versão final** | registra a aprovação (id do e-mail, trecho, data) e o pedido vai para `approved`. "Gostei" ou o ok de uma versão anterior **não contam** |
| e-mail do fornecedor | anota; confirmou, `supplier_accepted`; produzindo, `in_production`; despachou, `in_transit` com o rastreio. Fotos, Checked e endereço são da equipe |
| reclamação, reembolso, troca, cancelamento, preço, algo estranho | **não responde**: chama a equipe com a nota "Precisa de alguém da equipe: …" na linha do tempo do pedido |

**A chave "IA neste pedido".** Todo pedido tem, no topo, uma chave que liga e desliga a IA só
naquele pedido (ligada por padrão). Desligada, a IA não responde, não manda e-mail, não altera e
não anota nada ali, e não dá para simular nem "Pedir à IA" pela nota. O e-mail que chegar fica
guardado (com os anexos), aparece na linha do tempo como "Precisa de alguém da equipe" e quem
responde é a equipe. Use quando o cliente pede atendimento humano, quando a negociação está
delicada, ou quando o pedido é tratado por fora. Ligou de novo, a ponte volta a tratar os e-mails
novos. Na lista, o pedido aparece com a etiqueta **IA desligada**.

**Simulação ou envio de verdade.** Com o **envio automático desligado** (o padrão), nada sai: o
e-mail que a IA mandaria aparece na linha do tempo do pedido para a equipe conferir. Só um
gerente liga o envio automático, em Suits › Ponte de e-mail.

**Quem recebe é o painel que decide**, nunca o modelo: o e-mail só vai para o cliente, o designer
ou o fornecedor **daquele** pedido.

**As travas da ponte (#382):**
- **Um pedido por evento.** Num evento, a IA só lê e mexe no pedido dele; outro id é recusado, e ela não tem as
  ferramentas gerais do painel (clientes, Atenção, QuickBooks, Gmail, web).
- **Designer passa por uma pessoa.** O e-mail ao designer vira um item **preparado** no pedido (seção "Para o
  designer"), com o texto e os anexos já limpos. OPERATOR ou acima confere e clica **Enviar ao designer**. Vale mesmo
  com o envio automático ligado.
- **Boas-vindas só com o manual.** Sem o PDF do manual de medidas carregado, as boas-vindas não saem.
- **Arquivo que não se limpa não sai.** Ao cliente, só PNG, JPG, WEBP e PDF, sem metadados. AI, EPS e SVG entram
  pelo e-mail e vão ao designer (dono, 22/10), sem os metadados e sem dado do cliente; ao cliente, não. Limpeza que
  falha ou outro tipo (HEIC…): bloqueia e avisa.
- **Sem adivinhar o pedido.** E-mail que casa com mais de um pedido aberto (o mesmo cliente com dois pedidos, o
  assunto do fornecedor que serve para dois) não entra em nenhum: vira "Precisa de alguém da equipe".
- **Sem repetir.** O mesmo e-mail (mesmo pedido, papel, assunto, corpo e anexos) não sai duas vezes; se o servidor
  caiu no meio, a ponte confere no Gmail antes de reenviar. O e-mail recebido só conta como lido depois de tratado;
  falhou 3 vezes, vai para a equipe.
- **Saúde.** O topo da aba mostra a última rodada (quando, eventos, erros, simulação); cada pedido mostra a última
  tentativa, o último sucesso, o último erro, simulação ou envio real e a **próxima ação esperada**.

**Pedido de teste e IA desligada desde o início.** No **Registrar novo pedido** há duas caixas: "Nascer com a IA
desligada" (a ponte não age nem um instante) e "Pedido de teste": o de teste **nunca manda e-mail real**, em papel
nenhum (vira nota de simulação), e não entra nas contagens nem na Atenção. Pela API: `"ia_ligada": false`,
`"is_test": true`.

### Os grupos do ateliê no WhatsApp (#383)

Dono, 22/10: o OpenClaw da VPS fica logado num **número interno da URACE** e lê **só dois grupos**:
**Macacão design Urace** (o designer) e **Urace Suits - Usman** (o fornecedor). Conversa individual é
desligada; mensagem de outro grupo ou pessoa nem chega ao painel. A lista é configurável (outros grupos
virão). O agente que opera nos grupos é o mesmo da ponte de e-mail.

| No grupo | O que acontece |
|---|---|
| **design** — pedido novo com design suficiente | a IA manda o briefing ao grupo (só o design e "Suits #id": nunca nome completo, e-mail, telefone, endereço ou pagamento do cliente) e move para `design_pending` |
| **design** — o designer manda PDF/imagem | o arquivo vai para a pasta do pedido certo; a IA leva ao cliente **por e-mail** pedindo aprovação e move para `design_review`; o ajuste do cliente volta ao grupo |
| **fornecedor** — o pedido de produção | continua **por e-mail** (o rascunho de sempre, em "Pedido ao fornecedor") |
| **fornecedor** — fotos do suit pronto | ficam no pedido e a IA chama a equipe. Na seção *WhatsApp do ateliê*, **Usar como foto do suit** vira a nota com foto e move para `photos_received`; a equipe confere e move para `checked` (#382). Só então aparece **Mandar o endereço ao fornecedor**: o endereço vai ao grupo, com o pedido do rastreio, e o pedido passa a `address_sent` |
| **fornecedor** — código de rastreio | a IA grava no pedido (campo Rastreio) e, de `address_sent`, move para `in_transit` (pela tabela de etapas); a equipe passa ao cliente |
| PDF de medidas ou instruções extras | a IA lê, grava as medidas e as **Instruções extras ao fornecedor** (campo novo do Design); o e-mail ao fornecedor já sai com elas |
| o que está em aberto há mais de 20 h | o painel **cobra uma vez por dia** por pedido e por grupo (09h–18h, segunda a sábado): a arte no grupo de design; a produção e o rastreio no do fornecedor |

**De qual pedido é?** Só com evidência clara: resposta citando uma mensagem nossa, o **"#número"**
do pedido, ou o nome do piloto / do design de **um** pedido aberto. Se puder ser de mais de um, ou não
disser de qual é e tiver arquivo, vai para **Suits › WhatsApp › Sem pedido** e para "Precisa de
atenção": alguém da equipe liga ao pedido certo. Ninguém adivinha.

**Ao grupo de design, sempre com uma pessoa** (#382: o designer passa por uma pessoa): a mensagem ao designer é
sempre rascunho, mesmo com o envio automático ligado. Pedido de teste nunca manda nada aos grupos (vira nota).

**O que vai ao grupo do fornecedor segue a mesma chave "envio automático" da ponte.** Desligada (o padrão), cada
mensagem vira um **rascunho** no pedido (seção *WhatsApp do ateliê*, e a lista em Suits › WhatsApp), com
**Aprovar e enviar** (dá para corrigir o texto antes). Ligada, sai sozinho. E nada sai antes de o dono
ligar `WA_GRUPOS_APLICAR=1` na VPS. A chave **IA neste pedido** vale aqui também: desligada, a IA não
escreve nos grupos e não cobra; a mensagem que chegar fica para a equipe. No pedido também dá para
**escrever no grupo** à mão (sai na hora, com as mesmas travas) e gravar o rastreio.

### A política dos macacões (vai nas boas-vindas)

- três rodadas de revisão do design antes da produção, sem custo;
- macacão personalizado não tem devolução voluntária nem reembolso;
- erro da URACE: corrigido sem custo;
- erro de medida do cliente que inutilize o macacão: 50% de desconto na troca;
- erro do design fornecido pelo cliente que exija macacão novo: 33% de desconto na troca.

Tudo sujeito aos termos da compra e aos direitos do cliente. Conflito com isso sobe para a equipe.
**Nunca prometa preço, prazo ou desconto que não esteja no pedido ou nesta política.**

---

## 7. As operações (o que o Claude chama com `urace_api`)

WhatsApp do ateliê (#383), em `/ops/api/atelie` (Op.): `GET /pedidos/{id}` (mensagens e rascunhos do
pedido), `POST /saidas/{id}/aprovar` (`{"texto": "…"}` opcional) e `/saidas/{id}/descartar`,
`POST /pedidos/{id}/escrever` (`{"papel": "design|fornecedor", "texto": "…"}`),
`POST /pedidos/{id}/endereco` (só em `checked`; move para `address_sent`), `POST /mensagens/{id}/foto-do-suit` (`{"nome": "foto.jpg"}`;
move para `photos_received`), `POST /pedidos/{id}/rastreio` (`{"codigo", "transportadora"}`),
`GET /whatsapp/sem-pedido` e `POST /mensagens/{id}/vincular` (`{"order_id": 12}`).

Todos os caminhos começam com `/ops/api/suits`. "Op." é OPERATOR, "Ger." é MANAGER.

### Ler

| Para | Método e caminho | Papel |
|---|---|---|
| quantos por etapa | `GET /ops/api/suits/resumo` | Op. |
| a lista | `GET /ops/api/suits` com consulta `estado` = `abertos`, `fechados` ou `descartados`; `status` = código da etapa; `q` = nome, piloto ou e-mail; `limit`, `offset` | Op. |
| um pedido inteiro (cliente, medidas, `faltam_medidas`, design, notas, o que a IA respondeu) | `GET /ops/api/suits/{id}` | Op. |
| os arquivos que chegaram por e-mail | `GET /ops/api/suits/{id}/anexos` | Op. |
| o e-mail ao fornecedor já montado (e o que falta para montar) | `GET /ops/api/suits/{id}/email-fornecedor` | Op. |
| o que o cadastro do cliente já tem (para puxar ao pedido) | `GET /ops/api/suits/cliente/{client_id}` | Op. |
| as etapas, as medidas e os campos de design | `GET /ops/api/suits/etapas` | Op. |
| leads de macacão | `GET /ops/api/suits/leads` (consulta `estado` = `aberto`, `convertido`, `perdido`) | Op. |
| fornecedores | `GET /ops/api/suits/fornecedores` | Op. |
| a configuração da ponte | `GET /ops/api/suits/ponte` | Op. |
| a saúde da ponte (última rodada, simulação, preparados, pedidos com erro) | `GET /ops/api/suits/ponte/saude` | Op. |
| a mensagem com o endereço ao fornecedor (e o que falta) | `GET /ops/api/suits/{id}/endereco-fornecedor` | Op. |

O pedido (`GET /ops/api/suits/{id}`) também traz `aprovacao` (estado `valida` / `desatualizada` / `nenhuma`, o que
trava e a versão), `arte_final`, `estado_medidas`, `preparados` (e-mails ao designer), `saude_ponte` e
`proxima_acao`.

Para achar o card do cliente: `GET /ops/api/clients` com consulta `q` = nome.

### Fazer

| Para | Método e caminho | Corpo (exemplo) | Papel |
|---|---|---|---|
| registrar pedido | `POST /ops/api/suits` | `{"customer_name": "Rui Inventado", "customer_email": "rui@exemplo.com", "client_id": 584, "driver_name": "Rui Jr.", "nota": "pediu orçamento pelo WhatsApp"}` | Op. |
| atualizar dados | `PATCH /ops/api/suits/{id}` | `{"customer_phone": "+1 916 555 0148", "ship_address": "..."}` | Op. |
| gravar medidas | `PATCH /ops/api/suits/{id}` | `{"medidas": {"valores": {"head": 59, "chest": 92, "weight": 54, "foot": "42 EUR"}, "unidade": "cm", "unidade_peso": "kg"}}` | Op. |
| gravar design | `PATCH /ops/api/suits/{id}` | `{"design": {"cores": "preto e vermelho", "logos": "URACE no peito", "nome": "RYAN"}}` | Op. |
| mudar a etapa (com o motivo) | `PATCH /ops/api/suits/{id}` | `{"status": "design_pending", "nota": "cliente mandou medidas e logos"}` | Op. |
| anotar na linha do tempo | `PATCH /ops/api/suits/{id}` | `{"nota": "cliente pediu para trocar o azul por verde"}` | Op. |
| ligar a conversa do Gmail ao pedido | `PATCH /ops/api/suits/{id}` | `{"gmail_thread_cliente": "<link da conversa no Gmail>"}` (também `gmail_thread_designer`, `gmail_thread_fornecedor`) | Op. |
| rastreio | `PATCH /ops/api/suits/{id}` | `{"status": "in_transit", "tracking": "1Z999..."}` (só depois de `address_sent`) | Op. |
| marcar a arte final | `POST /ops/api/suits/{id}/arte-final` | `{"nome": "mockup-v3.png", "final": true}` | Op. |
| estado das medidas | `POST /ops/api/suits/{id}/medidas/estado` | `{"chaves": ["head", "neck"], "estado": "conferida"}` ou `{"chaves": ["waist"], "estado": "suspeita", "motivo": "..."}` | Op. |
| registrar a aprovação final à mão | `POST /ops/api/suits/{id}/aprovacao` | `{"trecho": "I approve the final version", "message_id": "<id do e-mail>", "data": "2026-10-22"}` | Op. |
| enviar ou descartar o e-mail preparado ao designer | `POST /ops/api/suits/{id}/preparados/{item}/enviar` · `.../descartar` | — (pede confirmação) | Op. |
| rascunho com o endereço ao fornecedor | `POST /ops/api/suits/{id}/endereco-fornecedor/rascunho` | — (só depois de `checked`; pede confirmação) | Op. |
| **descartar** (não é pedido de macacão) | `POST /ops/api/suits/{id}/descartar` | `{"motivo": "fatura da OpenAI"}` | Op. |
| restaurar um descartado | `POST /ops/api/suits/{id}/restaurar` | — | Op. |
| ligar ou desligar a IA neste pedido | `POST /ops/api/suits/{id}/ia` | `{"ligada": false}` | Op. |
| simular o próximo passo da IA (nada sai) | `POST /ops/api/suits/{id}/ponte/simular` | — | Op. |
| rascunho do pedido ao fornecedor no Gmail (com a arte final aprovada anexada) | `POST /ops/api/suits/{id}/email-fornecedor/rascunho` | — (exige a aprovação válida; pede confirmação) | Op. |
| guardar um lead | `POST /ops/api/suits/leads` | `{"name": "...", "email": "...", "notes": "..."}` | Op. |
| lead vira pedido | `POST /ops/api/suits/leads/{id}/pedido` | — | Op. |
| rodar a ponte agora | `POST /ops/api/suits/ponte/rodar` | — | Ger. |
| ligar/desligar a ponte e o envio automático, designer, assinatura, política | `PUT /ops/api/suits/ponte` | `{"envio_automatico": false}` | Ger. |
| fornecedores e o modelo do e-mail ao fornecedor | `POST`/`PATCH /ops/api/suits/fornecedores…`, `PUT /ops/api/suits/modelo` | — | Ger. |

**Nota com arquivo** (#447): o botão **Anexar arquivo** da nota aceita qualquer tipo, até 25 MB. Imagem (PNG, JPG,
WEBP) vira foto na linha do tempo, comprimida e sem EXIF: o screenshot para a IA entender, ou as **fotos do fornecedor**
que chegaram pelo WhatsApp. Outro arquivo (PDF, planilha, arte em AI/PSD, ZIP, vídeo curto) vai para os **Arquivos do
pedido**, aparece na nota com o link e sai só com sessão, sempre como download. A IA recebe o caminho do arquivo junto
com a nota. Só pelo painel; pelo Claude, a nota é só texto.

---

## 8. Rotinas prontas

### Toda manhã (5 minutos)
1. `GET /ops/api/suits/resumo`: quantos pedidos em cada etapa.
2. Nos pedidos abertos, procure as notas que começam com "Precisa de alguém da equipe": é a ponte
   pedindo gente (reclamação, dúvida, algo estranho). Também vale olhar `urace_atencao`.
3. `GET /ops/api/suits` com `estado=abertos`: para cada pedido parado há mais de 3 dias na mesma
   etapa, diga qual é o próximo passo e quem deve dar.
4. Algum pedido que **não é de macacão** na lista? Mostre ao Lucas e, com o OK dele, descarte.

### Cliente mandou medidas por WhatsApp ou foto
1. Abra o pedido (`GET /ops/api/suits/{id}`).
2. Grave as medidas **como vieram**, na unidade que o cliente usou.
3. Anote de onde vieram (`"nota": "medidas recebidas pelo WhatsApp em 13/10"`).
4. Conte o que ainda falta pelo `faltam_medidas` e diga ao Lucas.

### Aprovação final e produção
1. Abra o pedido e veja `aprovacao.bloqueios`: arte final marcada? medidas conferidas? nenhuma suspeita?
2. Faltou conferir medida: mostre ao Lucas; com o OK dele, `POST /ops/api/suits/{id}/medidas/estado` com
   `"estado": "conferida"`.
3. O cliente aprovou **por escrito a versão final** (o e-mail de aprovação final mostra a versão): a ponte registra
   sozinha. Se ele aprovou por outro caminho, registre à mão (`POST .../aprovacao`) com o trecho exato e a data.
   "Gostei" de uma versão anterior não vale.
4. `POST /ops/api/suits/{id}/email-fornecedor/rascunho` (o painel pede confirmação: mostre ao Lucas antes). O
   rascunho fica no Gmail do `urace@`, **já com a arte final aprovada anexada** e sem o endereço.
5. **Humano**: conferir e enviar o rascunho. Depois, mover para `sent_to_supplier`.

### Fotos do fornecedor e endereço
1. O fornecedor manda as fotos pelo **WhatsApp**: no painel, suba cada foto como nota com anexo, na etapa
   **Photos received**.
2. Conferiu e está certo: mova para **Checked** (só a equipe; exige foto).
3. Na seção **Endereço ao fornecedor**, crie o rascunho no Gmail ou copie a mensagem para o WhatsApp do fornecedor.
   Enviou: mova para **Address sent to supplier**. O endereço **nunca** vai ao designer.

### Fornecedor avisou que despachou
`PATCH` com `{"status": "in_transit", "tracking": "<código>", "nota": "Usman avisou pelo WhatsApp em 13/10"}`.

### Entregue
`PATCH` com `{"status": "delivered"}`. O pedido vai para o Histórico.

### Cliente pediu para falar com uma pessoa
1. Desligue a IA no pedido: `POST /ops/api/suits/{id}/ia` com `{"ligada": false}`.
2. Anote o motivo (`PATCH` com `{"nota": "cliente pediu atendimento humano"}`).
3. Daí em diante, a equipe responde. Para devolver à IA, ligue a chave de novo.

**Para o Claude:** se um pedido estiver com `ia_ligada = 0`, não proponha e-mail nem mudança de
etapa por conta própria. Mostre ao Lucas o que chegou e pergunte o que fazer.

### Achou um pedido que não é de macacão
1. Confirme lendo o pedido: remetente, assunto, notas.
2. Mostre ao Lucas o que achou.
3. Com o OK: `POST /ops/api/suits/{id}/descartar` com o motivo. Nada é apagado: o pedido some
   das listas, a ponte para de ler aquela conversa, e dá para restaurar.

### Frases que o Lucas pode usar com o Claude
- "Como estão os Suits hoje?"
- "O que falta no pedido do Rui Inventado?"
- "O cliente do pedido 171 mandou estas medidas em polegadas: …. Grave."
- "Move o 171 para Design Pending com a nota: cliente mandou logos."
- "Tem algum pedido em Suits que não é de macacão?"
- "Monta o rascunho do pedido do 171 para o fornecedor."

---

## 9. Regras que nunca mudam

1. **NO FAKE DATA.** Nunca invente medida, e-mail, telefone, endereço, data ou valor. Faltou, pergunte.
2. **O designer nunca recebe dado do cliente** (nome completo, e-mail, telefone, endereço,
   pagamento). **O cliente nunca recebe o nome ou o contato do designer.** O Mateus é designer,
   não fabricante: nunca diga ao cliente quem desenha nem quem fabrica.
3. **Nunca ponha informação de um cliente no pedido ou no card de outro.**
4. **Na dúvida, não crie pedido e não responda o cliente**: chame a equipe.
5. **Não prometa** preço, prazo ou desconto fora do pedido ou da política.
6. **Nada se apaga.** O que não serve é **descartado** (reversível), nunca excluído.
7. **E-mail que sai** (rascunho ao fornecedor, envio ao cliente, envio ao designer) só depois do "pode mandar" do Lucas.
11. **Produção só com a aprovação final escrita** da versão atual; **endereço ao fornecedor só depois do OK nas fotos**.
8. **Senha, token ou chave nunca no chat.** O login é pelo navegador.
9. **Horário da Flórida** (America/New_York) em tudo.
10. Não usar Turo nem Hostaway para nada.

---

## 10. Quando algo dá errado

| Sintoma | O que fazer |
|---|---|
| "este acesso é só de leitura" | conecte de novo e marque "Também operar o painel como você" |
| "isto é do papel MANAGER" | peça a um gerente ou ao dono |
| "precisa_confirmar" | mostre ao Lucas o que vai acontecer e repita com `confirmar: true` só depois do OK |
| pedido aparece com nome de empresa, banco ou newsletter | não é pedido de macacão: descarte (seção 8) |
| a IA não respondeu um cliente | abra o pedido: a nota da IA mostra o que ela fez ou o erro. Se a ponte estiver em simulação, o e-mail ficou na linha do tempo e não saiu |
| a ponte não roda | em Suits › Ponte de e-mail: a ponte precisa estar ligada e a IA no motor novo |
| "Falta … para montar o pedido ao fornecedor" | complete o que a mensagem diz (medida, fornecedor atual, e-mail do fornecedor, arte final, aprovação final) |
| "Sem a aprovação final escrita do cliente…" | a aprovação não existe ou ficou desatualizada (mudou a arte ou uma medida): peça ao cliente a aprovação da versão atual |
| Administrador e o cliente aprovou fora do e-mail (WhatsApp, telefone) | na nota, escolha **mover para Approved**, escreva o motivo e clique em **Liberar para Approved** (#448). Fica na linha do tempo e na auditoria com o seu nome. Operador e gerente não liberam; a IA só propõe, e uma pessoa clica. O **pedido ao fornecedor continua pedindo a aprovação registrada**: registre o trecho em "Registrar aprovação" antes de mandar à produção |
| "De … o pedido não vai para …" | a etapa pulou: siga a ordem da seção 3 |
| "não deu para limpar" / "este tipo de arquivo não é limpo" | peça o arquivo exportado em PNG, JPG ou PDF |
| "casa com mais de um pedido aberto" (em Precisa de atenção) | ligue a conversa ao pedido certo em Ponte de e-mail › Ligar conversas |
| o e-mail ao designer "não saiu" | ele está em **Para o designer**, esperando alguém clicar **Enviar ao designer** |

---

*Processo completo, com o histórico das decisões: `brain/10_PROCESSOS/Pedido de macacão.md`.*
