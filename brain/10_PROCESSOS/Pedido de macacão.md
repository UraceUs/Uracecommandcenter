---
tipo: processo
area: SUITS
fonte: humano
ditado_por: Italo Silveira
data: 2026-08-28
atualizado: 2026-10-22
asana_projeto: "1205661933760052"
tipo_info: PROCESS
responsavel: Italo Silveira
status: ativo
---

# Processo — pedido de macacão (SUITS)

[[URACE]] · [[Gmail]] · fornecedor atual: [[Usman]] · valores em [[PARAMETROS]]

O macacão é **100% personalizado**: medidas, design, cores, logos e a
posição de cada logo são feitos para aquele cliente. Nada é padrão.

O pedido vive na aba **Suits · Alpha Line** do Command Center (desde 08/10, #153). O quadro
SUITS do Asana foi importado para lá e **não é mais usado** (ver "Histórico", no fim).
Guia para operar Suits pelo Claude: `docs/suits-guia-do-lucas.md`.

## O caminho, do contato à entrega (como é desde 22/10, #382)

Dono, 22/10: *"o envio sera direto ao cliente sem precisar enviar para a urace ... o fornecedor
nos envia fotos dos suit no whats app conferimos e passamos o endereço para o envio"*.

| # | Etapa (código) | O que acontece | Quem move |
|---|---|---|---|
| 1 | Standby (`standby`) | venda no site ou contato: o pedido nasce | IA ou equipe |
| 2 | Awaiting Measurements (`awaiting_measurements`) | as boas-vindas saíram **com o manual de medidas (PDF)**; esperando as 29 medidas e o design | IA |
| 3 | Design Pending (`design_pending`) | o designer trabalha (recebe só o design) | IA |
| 4 | Design Under Client Review (`design_review`) | o cliente revisa; a equipe confere as medidas; a arte final é marcada | IA e equipe |
| 5 | Approved (`approved`) | **aprovação final escrita do cliente**, válida para a arte e as medidas de agora | IA (pelo e-mail) ou equipe |
| 6 | Order sent to supplier (`sent_to_supplier`) | pedido de produção ao fornecedor, com a arte final aprovada anexada — **sem endereço** | equipe (rascunho no Gmail) |
| 7 | Accepted by supplier (`supplier_accepted`) | o fornecedor confirmou | IA ou equipe |
| 8 | In Production (`in_production`) | produzindo | IA ou equipe |
| 9 | Photos received (`photos_received`) | o fornecedor mandou as **fotos pelo WhatsApp**; a equipe sobe cada foto como nota com anexo | **só a equipe** |
| 10 | Checked (`checked`) | a equipe conferiu as fotos e deu o OK (exige foto) | **só a equipe** (OPERATOR ou acima) |
| 11 | Address sent to supplier (`address_sent`) | o endereço do cliente foi ao **fornecedor** (só depois do OK) | **só a equipe** |
| 12 | In Transit (`in_transit`) | o fornecedor despachou **direto ao cliente** (exige rastreio) | IA ou equipe |
| 13 | Delivered (`delivered`) | entregue | IA ou equipe |
| — | Canceled (`canceled`) | cancelado (reabre em Standby) | equipe |

**Transições**: o painel só aceita as mudanças da tabela `TRANSICOES` (`providers/suits.py`): de
cada etapa, para a seguinte, para trás quando faz sentido (ex.: aprovado volta para revisão) ou
para cancelado. Pedido novo nasce antes da aprovação (Standby a Design Under Client Review) ou
cancelado. A mudança fora da tabela é recusada com o motivo, venha da tela, da nota ou da IA.

## As travas (#382)

**Aprovação final amarrada.** A aprovação escrita do cliente **vale por e-mail** (dono, 22/10).
- Antes, a arte final é **marcada** (o arquivo da versão a aprovar) e **todas as medidas
  conferidas** pela equipe. Medida **suspeita** ou não conferida trava a aprovação.
- A IA manda ao cliente o **e-mail de aprovação final** montado pelo painel: a versão (código
  curto), a arte final anexada, as medidas e a política (não retornável, não reembolsável).
- A IA só registra quando o cliente aprova **expressamente essa versão final**, e grava o id do
  e-mail, o trecho com o "aprovo" e a data. "Gostei" de um mockup ou o "ok" de uma versão
  anterior **não contam**.
- A aprovação guarda o hash da arte final e das medidas. **Mudou qualquer uma, ela fica
  desatualizada** (não some) e o pedido em `approved` volta para revisão.
- A equipe também registra à mão, na tela do pedido.

**Anexos obrigatórios.**
- As boas-vindas **não saem sem o manual de medidas** (PDF em Suits › Ponte de e-mail; o topo da
  aba avisa se falta).
- O rascunho ao fornecedor sai do **pacote aprovado**: a arte final e as medidas da aprovação,
  conferidas pelo hash, com a arte já anexada.

**Isolamento por pedido.**
- Num evento da ponte, a IA só lê e mexe **naquele pedido**. Outro id é recusado, e é proibido
  trazer dados de outros clientes.
- A IA da ponte **não** recebe as ferramentas gerais do painel (clientes, Atenção, QuickBooks,
  Gmail, web); lê só o cérebro e a pasta do pedido.
- O e-mail **ao designer** passa por uma pessoa: a IA **prepara** (assunto, corpo e anexos já
  limpos de metadados), e alguém da equipe confere e clica **Enviar ao designer**. Vale mesmo
  com o envio automático ligado.
- O designer nunca recebe nome completo, e-mail, telefone, endereço, valor ou pagamento do
  cliente; arquivo que contenha qualquer um deles não sai.

**Limpeza que não deixa passar** (revisão do Mio). Ao cliente só saem PNG, JPG, WEBP e PDF, sem metadados.
**AI, EPS e SVG** (dono, 22/10: *"deixa entrar pelo email tb"*) entram pelo e-mail e vão ao designer, sem os
metadados (comentários, título e autor) e sem e-mail, telefone, endereço ou nome do cliente; ao cliente, não.
Outro tipo (HEIC…) ou limpeza que falha: o arquivo **não sai**. Peça o arquivo exportado.

**E-mail ligado sem adivinhar** (revisão do Mio). Um e-mail só entra num pedido quando a conversa
é dele, ou quando o remetente bate com **um único** pedido aberto. Casou com mais de um (o cliente
com dois pedidos, o assunto do fornecedor que serve para dois, a mesma conversa em dois pedidos):
não liga a nenhum e vira "Precisa de alguém da equipe".

**Envio sem repetição** (revisão do Mio). Antes de mandar, a ponte grava "enviando" com uma chave
única (pedido + papel + assunto, corpo e anexos). Já enviado não sai de novo; "enviando" que ficou
para trás é conferido no Gmail antes de reenviar. O e-mail recebido só conta como lido **depois**
de tratado: falhou, volta no ciclo seguinte; depois de 3 tentativas, vai para a equipe.

**Pedido de teste e IA desligada desde o início.** O pedido pode nascer com a IA desligada (a
ponte não age nem um instante) ou marcado como **teste**: o de teste nunca manda e-mail real, em
papel nenhum (vira nota de simulação), e não entra nas contagens nem na Atenção.

**Saúde da ponte.** Cada pedido mostra a última tentativa, o último sucesso, o último erro, se foi
simulação ou envio real e a próxima ação esperada. O topo da aba mostra a última rodada (quando,
quantos eventos, erros) e se a ponte está em simulação.

## A ponte de e-mail (#153)

A ponte roda o fluxo que o Ítalo montou no ChatGPT (áudio de 08/10), a cada 15 minutos:
venda de macacão no site → a IA agradece, manda o manual de medidas e pede o design → o cliente
responde → a IA grava medidas e design e **prepara** o briefing ao designer (só o design) → o
designer pergunta ou entrega a arte → a IA leva ao cliente **sem os dados do designer** → a
aprovação final, como acima. Também lê o marcador `Suits` e as respostas do fornecedor.

**Marcador `Suits` não é pedido** (dono, 09/10, #182: *"quando for um pedido de suit, ele adiciona
lá"*). Conversa com o marcador de quem não tem pedido aberto vai para a IA **sem pedido criado**:
ela só cria (ou liga ao pedido aberto da pessoa) quando é alguém querendo comprar um macacão.
Fornecedor, homologação, nota, frete, propaganda, conversa da equipe (todo `@urace.us` é nosso) ou
dúvida: não cria nada. Na dúvida, não cria.

**Só e-mail que fala de macacão** (dono, 13/10, #195). O assunto ou o texto têm de falar de macacão
e o remetente não pode ser robô (noreply, cobrança, recibo, newsletter). Sem isso, o e-mail é lido
uma vez e esquecido.

**Descartar, nunca apagar** (#195). Pedido que não é de macacão é **descartado**: sai das listas, a
ponte não lê nem responde mais nada nele, e pode ser restaurado.

**A chave "IA neste pedido"** (dono, 13/10, #198). Desligada, a IA não responde, não manda e-mail
e não altera nada; o e-mail que chegar vira "Precisa de alguém da equipe".

**Simulação primeiro.** Com o "envio automático" desligado (o padrão), nada sai: o e-mail que a IA
mandaria aparece na linha do tempo. O envio automático continua desligado até passar um ciclo
completo no card de teste (#382).

Quem decide o destinatário é o painel (o cliente, o designer ou o fornecedor DAQUELE pedido),
nunca o modelo.

**Do robô do Ítalo (Mio, contexto de 08/10, #156)**:
- **Designer: Mateus.** É designer, **não** fabricante. Não se apresenta ao cliente, e o cliente
  nunca recebe o contato, a assinatura, o texto, a conversa ou os metadados dele.
- **Quem assina com o cliente: George**, com a assinatura da URACE trocando só o nome.
- **Política dos macacões**, sujeita aos termos da compra e aos direitos do cliente:
  - três rodadas de revisão do design antes da produção, sem custo;
  - personalizado não tem devolução voluntária nem reembolso;
  - erro da URACE: corrigido sem custo;
  - erro de medida do cliente que inutilize o macacão: 50% de desconto na troca;
  - erro do design fornecido pelo cliente: 33% de desconto na troca.

  Conflito com os termos ou os direitos do cliente sobe para a equipe.
- **Pedido do site #4738**: as boas-vindas (agradecimento + manual) saíram em 28/09, à mão.
  Não repetir nem mandar adendo de política.

## O e-mail ao fornecedor (o pedido de produção)

O modelo fica em Suits › E-mail ao fornecedor (editável pelo gerente). O formato que o fornecedor
já sabe ler:

- **Assunto:** `SUIT - {piloto}`
- **Anexo:** a arte final **aprovada** (a mesma do hash da aprovação).
- **Corpo:** as 29 medidas na ordem do formulário, em **dupla unidade** (cm / pés-polegadas; o
  `6bis` só para mulheres), cores e quantidade. **Sem o endereço do cliente**: ele vai depois, só
  após o OK das fotos, pela seção "Endereço ao fornecedor" (rascunho no Gmail ou texto para o
  WhatsApp).

```
Hi Usman,

We have a new order:

1 – Head circumference — 59 cm / 1'11"
...
29 – Foot size — 42 EUR / 9 US

The final mockup is attached.

Best regards,
{assinatura de quem envia}
```

O fornecedor atual é o marcado como **atual** em Suits › Fornecedores.

## Histórico (até 08/10/2026, quando o pedido vivia no Asana) — não vale mais

Até a aba Suits, o pedido era uma tarefa `New Order: {cliente}` no projeto SUITS do Asana (modelo
`1217959088745716`), com os status Standby, Awaiting Measurements, Design Pending, Design Under
Client Review, `Order sent to Usman`, In Production, In Transit, Delivered e Canceled. O gatilho
era "anexo do design final na tarefa + status `Order sent to Usman`", a IA mandava só o pedido do
formulário de medidas e o pedido de produção, e o fornecedor despachava para a URACE. Tudo isso
foi substituído pelo fluxo acima: a importação do Asana (`Importar do Asana`, só leitura) traz os
pedidos antigos para a aba com a etapa equivalente, e nada mais é feito no quadro.
