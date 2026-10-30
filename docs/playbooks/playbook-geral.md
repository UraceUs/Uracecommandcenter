# Playbook geral do Command Center — URACE

> **Para quem é:** para todo mundo da URACE que usa o Command Center, e para o Claude de cada
> pessoa.
> **Como usar:**
> - **Pessoa:** leia uma vez de ponta a ponta. Depois, volte à seção de que precisar.
> - **IA (Claude):** cole este arquivo inteiro nas instruções de um Projeto do Claude
>   (claude.ai › Projetos › Instruções do projeto) ou salve como `CLAUDE.md` na pasta em que você
>   abre o Claude Code. A partir daí, o Claude sabe como o painel funciona, o que pode fazer
>   sozinho e o que tem de perguntar antes.
>
> Pedido do dono, 13/10/2026: *"um playbook de como operar dentro do Command Center, que seja
> entendido tanto por IA quanto por um humano, para eu poder estar passando isso para o time"*.
>
> Este é o playbook **geral**. Os detalhes de cada área estão nos outros:
>
> | Área | Playbook |
> |---|---|
> | Vendas (oportunidades, agenda, Kommo, fechamento) | [playbook-vendas.md](playbook-vendas.md) |
> | Box (mecânicos e coaches: Meu dia, checklists, balcão, estoque) | [playbook-mecanicos-e-coaches.md](playbook-mecanicos-e-coaches.md) |
> | Suits · Alpha Line (macacões) | [../suits-guia-do-lucas.md](../suits-guia-do-lucas.md) |
> | Conectar o Claude ao painel (MCP) | [../command-center-mcp-operar.md](../command-center-mcp-operar.md) |
>
> Todos os guias também estão no painel, em **Administrativo › Como usar**, para ler ou baixar; lá fica
> também o **MD para a sua IA**, que junta tudo num arquivo só.
>
> Atualizado em 29/10/2026 (#455, a tarefa do Asana por dentro fica **espelhada** no painel: descrição, subtarefas, comentários e anexos, com **Atualizar do Asana**; antes, #430, a busca de cliente aceita o **Client ID**; antes, #420, a **IA do painel opera** o Command Center inteiro, como quem pediu; antes, #410, o **Editar** do card corrige nome, e-mail, telefone, piloto e nascimento; antes, #394, o menu em dropdown do site e as animações; antes, #355, o aluno do plano marca **"Training Day X/Y"**; antes, #340, o **piloto pro** marca pelo pacote: o contador do mês para o cliente e para a
> equipe, só o serviço do plano, add-ons e a invoice das extras na hora da marcação; antes, #115, o **pacote de prova** da waiver para o advogado; antes, #117, conferir o documento da
> waiver no balcão e o nascimento travado, e #313, o
> cartão do padrão D em todo o painel, e #312, a inserção sempre no topo e o **Adicionar serviço** com a página do site). Tudo aqui foi conferido no código do
> painel. Se a tela mudar e este texto não, vale a tela; avise quem cuida do painel para corrigir aqui.

---

## Sumário

1. [Para que serve o Command Center](#1-para-que-serve-o-command-center)
2. [Entrar e quem vê o quê](#2-entrar-e-quem-vê-o-quê)
3. [Mapa das telas](#3-mapa-das-telas)
4. [Rotinas do dia](#4-rotinas-do-dia)
5. [Clientes e pilotos](#5-clientes-e-pilotos)
6. [Cada área, em poucas linhas](#6-cada-área-em-poucas-linhas)
7. [A IA no painel](#7-a-ia-no-painel)
8. [Operar pelo Claude (MCP)](#8-operar-pelo-claude-mcp)
9. [Regras que nunca mudam](#9-regras-que-nunca-mudam)
10. [Quando algo dá errado](#10-quando-algo-dá-errado)
11. [Glossário](#11-glossário)
12. [Bloco para a IA](#12-bloco-para-a-ia)

---

## 1. Para que serve o Command Center

O Command Center é a **mesa de operação** da URACE. Ele junta num lugar só o que está espalhado
em Asana, DocuSign, Gmail, QuickBooks e Kommo, e mostra o que precisa de gente.

Três ideias explicam o painel inteiro:

1. **Nada é inventado.** A tela mostra o que foi lido das fontes. Se uma fonte não respondeu, a
   tela diz isso. Não preenche com palpite.
2. **A IA faz o trabalho interno e a pessoa decide o que sai da empresa.** Enviar invoice,
   e-mail, apagar ou anular espera um clique de alguém. Exceções que o dono abriu: a waiver e o
   **lembrete de invoice em aberto** saem sozinhos.
3. **Tudo fica registrado.** Login, comando, aprovação e mudança ficam na **Auditoria**, com o
   nome de quem fez. Esse registro não se apaga.

---

## 2. Entrar e quem vê o quê

### Entrar

1. Abra **https://ops.urace.us/ops/**
2. Entre com o **seu** e-mail e a **sua** senha. Quem cria o usuário é um administrador, na tela
   **Usuários**.
3. "Manter conectado por 30 dias" é opcional. Sem isso, a sessão dura 12 horas.

| Situação | O que acontece |
|---|---|
| Errou a senha 5 vezes em 15 minutos | o acesso trava por alguns minutos ("Too many attempts") |
| De que IP o sistema diz que veio (#120) | o IP que o Caddy viu chegar, o mesmo no bloqueio de senha, na Auditoria e na trilha da waiver assinada no próprio site. Um cabeçalho `X-Forwarded-For` inventado pelo navegador não muda esse IP |
| Esqueceu a senha | não há autoatendimento: um administrador redefine em **Usuários** |
| Quer trocar a senha | menu do seu nome (canto de cima) › **Minha conta e senha**. Trocar a senha encerra todas as suas sessões |
| Celular | o mesmo endereço. Embaixo aparece a barra de abas |

**Nunca mande senha pelo chat**, nem para colega, nem para a IA.

### Papéis

Todo usuário tem um **papel**. O papel diz o que a pessoa alcança. O servidor confere o papel em
cada ação; o menu só esconde o que não é seu.

| Papel (na tela) | Alcança | Não alcança |
|---|---|---|
| **Acesso livre** | tudo, sem cargo. É a conta do dono | — |
| **Administrador** (`ADMIN`) | tudo: usuários, políticas da IA, integrações, atualizar o sistema | — |
| **Gerente** (`MANAGER`) | tudo do operador + financeiro (QuickBooks, invoices), auditoria e biblioteca | usuários e políticas da IA |
| **Operador** (`OPERATOR`) | o dia a dia **e as vendas**: clientes, serviços, waivers, e-mails, chat, corridas, oportunidades, Suits, balcão e a IA. Aprova o que a IA propõe nesses módulos | financeiro (invoice e QuickBooks), auditoria, usuários, políticas |
| **Leitura** (`VIEWER`) | vê o que a tela mostra | não muda nada |

**Quem vende é operador.** Não existe papel "vendas" (dono, 17/09).

### Cargos do box

Mecânico e coach têm papel de operador, mas com um **cargo** que corta o resto (#92). O cargo
mostra só o que é do box.

| Cargo | Telas |
|---|---|
| **Mecânico** (`MECANICO`) | Meu dia, Balcão, Checklists, Estoque, Pedidos, Compras, Clientes (o card sai sem valores), Equipe, Minha conta |
| **Coach** (`COACH`) | as mesmas do mecânico, por enquanto |

Fora dessas telas, o painel mostra "Esta área não é do seu acesso". Rota nova do sistema nasce
**fechada** para o box: só abre se alguém incluir na lista.

A trava do cargo vale nas três portas: navegador, Claude conectado e chave de API (#201). Por
enquanto, o conector do Claude fica **fechado** para mecânico e coach, porque as ferramentas de
leitura dele alcançam partes do painel que não são do box.

O detalhe do dia do box está no [playbook de mecânicos e coaches](playbook-mecanicos-e-coaches.md).

### Outros endereços

| Endereço | Para quê |
|---|---|
| `ops.urace.us/ops/` | o painel da equipe |
| `parts.urace.us` | **só** o balcão do celular (leitor de peças). Qualquer outra tela responde "Este endereço é só do balcão." No painel, **Balcão › "Abrir o balcão do celular"** abre esse endereço já com o seu login (#311): um acesso de uso único, que vale 30 segundos e nunca aparece no endereço. Sair do painel tira você do balcão também |
| `/ops/portal` | a **área do cliente** (outra porta, outro login). Não é o painel da equipe |
| `/cart/` (site novo) | o **carrinho** do cliente (#236): sessões e produtos, um pagamento só no Stripe. **Toda compra pede a conta do site** (#248): sem conta, o carrinho pede os dados, o piloto (só o nome) e a senha, e a conta nasce no Checkout com o e-mail de boas-vindas (#305). Chave English/Português no topo |
| `novo.urace.us/services/` | a **página de programas** do site (*Programs*). Desde 29/10 (#507) é a do urace.us: uma seção por degrau da escada — **Sim 2 Grid**, **Arrive and Drive**, **URACE Academy**, **Racing Team** e **Birthday party / Corporate Events** — com as perguntas de cada um (abrem no toque) e, no Sim 2 Grid, os **programas mensais do painel** (Site › Cartões das páginas). Termos, reembolso e preço de cada programa ficam na página dele. Desde 15/10 (#254), **Kart School** é a **URACE Academy** e **Professional Coaching** é o **Arrive and Drive**; os dois endereços antigos redirecionam para quem herdou. O que a equipe vende por cada nome está no [playbook de vendas](playbook-vendas.md) |
| `/order/<código>/` (site novo) | a **página do pedido** do cliente (#245), link pessoal: pago, processando, pagamento não passou (Try again) ou checkout expirado (Restore cart), com os dados do cliente da conta; em inglês ou português (#248). A equipe copia o link em Site › Pedidos do site |

**Endereço do urace.us de hoje** (#252): todo endereço que o site antigo publica abre no site novo —
a mesma página ou um 301. Quem manda um link antigo para um cliente (`/urace-academy/`,
`/book-online/`, `/product/<slug>/`, `/product-category/...`, `/shop/`, `/my-account/`, um artigo do
blog) pode mandar: ninguém cai em "Page not found". A lista e as regras estão em
`docs/site-publico/comparacao-urace-us.md`, e a comparação
completa dos dois sites (passo a passo da compra, o que falta no novo, peso e velocidade) também.
As **landings de campanha** (#506) abrem como páginas próprias, com o texto do urace.us de 29/10 (até então
eram 301): `/kart-lessons-for-beginners/`, `/kart-driving-school/`, `/kart-training-packages/`,
`/professional-kart-team-racing-team/`, `/the-driver-factory/` (com o obrigado,
`/the-driver-factory-thank-you-page/`) e as três do Arrive & Drive, fora do Google:
`/arrive-and-drive-karting-experience/` (formulário), `/arrive-and-drive-karting-booking/` (leva à reserva do site)
e `/arrive-and-drive-karting-thank-you/`. O formulário delas cai em Vendas (playbook de vendas, "O que o site vende").

---

## 3. Mapa das telas

O menu tem grupos. Um número ao lado do item é um contador (coisas esperando). Fechado, o menu
vira um trilho de ícones; **⌘K** (ou Ctrl+K) abre a busca, que também pergunta à IA.

"Quem usa" é quem vê o item no menu. Uma pessoa de **Leitura** vê alguns itens que, ao abrir,
pedem acesso de operador.

### Menu da equipe (todos menos o box)

| Grupo | Tela | Endereço | Para que serve | Quem usa |
|---|---|---|---|---|
| Hoje | **Hoje** | `/ops/` | a abertura do dia: pista de hoje, o que precisa de gente, o que espera aprovação, waivers abertas, próximos 7 dias, sistemas | todos |
| Hoje | **Precisa de atenção** | `/ops/attention` | a fila do que a IA não resolveu sozinha, do mais grave para o menos | todos |
| Hoje | **Calendário** | `/ops/meu-dia` | o dia, a semana e o mês do box: serviços do Asana, corridas, sessões do site e checklists. Mostra **só o ativo**: serviço cancelado ("CANCELLED - …") ou excluído não aparece. Tudo em **cards**: o treino é o card do cliente; a corrida é um card geral com um card por cliente inscrito | todos |
| Comercial | **Oportunidades** | `/ops/sales` | o quadro de vendas por etapa | operador+ |
| Comercial | **Agenda de vendas** | `/ops/sales/agenda` | os retornos marcados em cada ligação; o cartão **Google Calendar** liga o calendário Google de cada pessoa (os retornos vão para lá e os compromissos dela aparecem aqui). Passo a passo no [playbook de vendas](playbook-vendas.md), 4.8 | operador+ |
| Comercial | **Chat do Kommo** | `/ops/crm/chat` | a conversa do lead dentro do painel | todos |
| Comercial | **Funil do Kommo** | `/ops/crm/funil` | as etapas do funil do Kommo, espelhadas | todos |
| Comercial | **Robô SDR** | `/ops/sdr` | o robô de vendas no Kommo: ligar, instruir, relatar erro | todos |
| Comercial | **Clientes** | `/ops/clients` | um card por pessoa; o card abre em `/ops/clients/<n>` | todos |
| Site | **Painel do site** | `/ops/site` | as métricas do site público (#306, dono 16/10: *"do site um dashboard com as métricas dele"*): recebido pelo site (loja, carrinho, planos e as sessões da área do cliente pagas pela invoice), pedidos pagos, conversão do pagamento, visitas, o caminho do site ao pagamento, os mais vendidos, as páginas mais vistas, de onde as pessoas entraram, as campanhas, as contas novas e a saúde do site. Período de 7, 30 ou 90 dias, comparado com o anterior. Detalhes na seção 6, "Painel do site" | operador+ |
| Site | **Pedidos do site** | `/ops/site/pedidos` | carrinho e loja em todo estado do pagamento, com o link da página do pedido | operador+ |
| Site | **Agendamentos** | `/ops/site/agendamentos` | os pedidos de sessão do site e da área do cliente: aceitar, confirmar, recusar, cancelar (era `/ops/site` até o #306) | operador+ |
| Site | **Disponibilidade** | `/ops/site/disponibilidade` | a agenda que abre e fecha: semana, horários, regras e bloqueios | operador+ (mudar: gerente+) |
| Site | **Serviços e preços** | `/ops/site/servicos` | **Adicionar serviço** em cima, escolhendo **em qual página do site** ele entra (#312); o preço, o depósito (com **Security deposit obrigatório**, #317) e o item do QuickBooks de cada serviço, com o **cartão do kart no site**, o **kart novo** (#297) e **onde cada um aparece hoje no site** | operador+ (mudar: gerente+) |
| Site | **Cartões das páginas** | `/ops/site/cartoes` | os planos e preços da Academy, do Pro Team, do For Beginners e os **programas mensais do SIM2GRID** (#297, #392); **Adicionar cartão** em cima (#312) | operador+ (mudar: gerente+) |
| Site | **Sim2Grid** | `/ops/site/sim2grid` | a hora de simulador do SIM2GRID (#392): as **regras** (vender online, simuladores por hora, horas mínimas e máximas, horizonte, antecedência, abertura, datas fechadas, idade, waiver, aviso e sorteio), as **faixas de preço por hora** de cada formato (com coach, sem coach; preço vazio = "ligue para nós"), a **etiqueta do dia** (🏁 Pilot day × 🎮 Fun night, #396) e as **reservas** que vêm do site, com o card de cada piloto. Detalhes na seção 6, "SIM2GRID" | operador+ (mudar: gerente+) |
| Site | **Produtos da loja** | `/ops/site/produtos` | título, preço, fotos, texto, opções, estoque, **frete** e **depósito** de cada produto (#298), e **Como vendemos** (dropshipping ou em estoque, #309) | operador+ (mudar: gerente+) |
| Site | **Estoque do site** | `/ops/site/estoque` (um produto: `/ops/site/estoque/<endereço>`) | o que é **dropshipping** e o que é **em estoque** (interno: o cliente nunca vê), o item do Estoque ligado a cada produto ou opção e **quanto tem** em cada local (*Galpão 5 · Pista 3*); ligar, criar o item a partir do produto e contar um local por vez (#309) | operador+ (contar); ligar, desligar e mudar o marcador: gerente+ |
| Site | **Security deposit** | `/ops/site/deposito` | cada depósito pago no site, **devolver pelo Stripe** com o valor escolhido (parcial vale) e conferir no Stripe; e o **valor do depósito** que o site cobra, por sessão (com **Obrigatório**) e por produto (#317) | operador+ (devolver e mudar: gerente+) |
| Site | **Editor do site** | `/ops/site/editor` (uma página: `/ops/site/editor/<n>`) | muda as páginas do site **como no Canva**: a prévia da página é a área de trabalho; clica, escreve no lugar, arrasta e solta, no computador (Celular 390 px ou Computador 1280 px reduzido para caber) e no celular; **?** mostra os atalhos (#300, #315; seção 6, "Editor do site") | operador+ (mudar e publicar: gerente+) |
| Site | **Blog** | `/ops/site/blog` | os artigos do blog do site (`/blog/`): **Novo artigo** em cima, rascunho, capa, texto com links e fotos, prévia, publicar e as versões; o artigo abre em `/ops/site/blog/<n>` (#172; seção 6, "Blog do site") | operador+ (publicar e tirar do ar: **só o ADMIN** ou o acesso livre) |
| Site | **Contas de clientes** | `/ops/site/contas` | as contas da área do cliente e o card de cada uma: ligar, criar o card, desligar | operador+ |
| Site | **Waiver** | `/ops/site/waiver` | a waiver assinada no próprio site: ligar (a chave geral; cada card pode escolher outro fluxo no switch Waiver do card, #348), o **selo digital e carimbo de tempo** (#110), modelos, o **aviso do §744.301(3)** e as **versões dos modelos** (#116), assinadas com a **Trilha** de eventos (#111), o **Pacote de prova** (#115) e **Anular** (#109) | gerente+ |
| Logística | **Corridas** | `/ops/races` | as corridas (coluna RACES do Asana) e o convite aos ★ Pro | todos (criar: operador+) |
| Logística | **Balcão** | `/ops/balcao` | de cima para baixo (dono, 20/10): **o cliente** (pilotos de hoje, nome ou QR), **COBRAR/GUARDAR**, **a peça** (o campo abre o teclado no celular e sugere do estoque e do QuickBooks enquanto digita; "Só o leitor" para o coletor; câmera), e embaixo o que já foi lançado. Peça que não existe abre **Registrar peça nova** e já vai para o cliente (GUARDAR: na lista; COBRAR: no rascunho). No GUARDAR a peça fica em **"Guardando para …"** (pendente, no servidor, só deste card) até **Confirmar N peça(s)**, que põe tudo no estoque do cliente de uma vez; no cliente aberto, **Waiver · Conferir documento** (#117) e o **Rascunho de invoice** (#341/#346: peças do estoque, do inventário do QuickBooks ou linha livre, com o preço da linha; montar e **Criar invoice** é operador+; a do mecânico fica **aguardando revisão do gerente**, que confirma ou altera a mesma invoice no QuickBooks antes de enviar ou cobrar; item novo vai para a categoria Parts; código que não bate mostra o mais parecido; #350: cobra mesmo **sem saldo** no estoque, e a peça vai para "vendida(s) sem saldo: recontar" em Precisa de atenção) | operador+ |
| Logística | **Estoque** | `/ops/estoque` | uma fileira por prateleira; contar, assinalar peça para cliente; o selo **à venda no site** na peça que a loja do site também vende (mesmo saldo, #309) | todos |
| Logística | **Checklists** | `/ops/checklists` | os checklists do dia, do kart e os trimestrais | operador+ |
| Pedidos e compras | **Pedidos** | `/ops/pedidos` | a lista do que a equipe **precisa** que se compre | todos |
| Pedidos e compras | **Suits · Alpha Line** | `/ops/suits` | os pedidos de macacão sob medida, do contato à entrega direta ao cliente (aprovação final, fotos do WhatsApp, endereço ao fornecedor) | operador+ |
| Pedidos e compras | **Compras** | `/ops/compras` | o que a URACE comprou: pedido, envio, chegada. Os e-mails de compra entram sozinhos | todos |
| Pedidos e compras | **Planejamento** | `/ops/planejamento` | peças e corridas: o que vai faltar, e quando | todos |
| IA e inserções manuais | **AI Command** | `/ops/ai` | a conversa com a IA, e o quadro "Falta completar" | todos (mandar comando: operador+) |
| IA e inserções manuais | **Aprovações** | `/ops/approvals` | o que a IA propôs e espera uma pessoa decidir | todos (decidir: operador+) |
| IA e inserções manuais | **Automação e memória** | `/ops/automation` | as rotinas automáticas e o que a IA aprendeu | todos |
| IA e inserções manuais | **Manual dos marcadores** | `/ops/gmail/manual` | como marcar e-mail à mão para a triagem da IA aprender | todos |
| IA e inserções manuais | **O que a IA pode fazer** | `/ops/ai/capabilities` | cada ferramenta da IA e a política dela, lido do código | todos |
| IA e inserções manuais | **Atividade da IA** | `/ops/activity` | tudo o que a IA fez, em ordem | todos |
| Equipe | **Equipe** | `/ops/equipe` | o chat interno (direto ou em grupo), "Conectar o Claude" e o aviso no celular | todos |
| Equipe | **Biblioteca** | `/ops/biblioteca` | os documentos de cada cliente, com o PDF; cópia no Drive | gerente+ |
| Administrativo | **Como usar** | `/ops/como-usar` | os guias do painel para ler ou baixar (.md e PDF) e o **MD para a sua IA**, que junta tudo para o Claude operar o painel com o seu usuário | todos |
| Administrativo | **QuickBooks** | `/ops/quickbooks` | invoices e pagamentos. A IA prepara; enviar pede aprovação | todos veem a tela; financeiro é gerente+ |
| Administrativo | **DocuSign** | `/ops/docusign` | as waivers. Entregue não é assinada; devolvida é e-mail errado | todos |
| Administrativo | **Gmail** | `/ops/gmail` | o que a triagem da IA não decidiu | todos |
| Administrativo | **Asana** | `/ops/asana` | o **espelho** do quadro U-RACE: agenda (TUESDAY a SUNDAY), RACES e Finished Services. A tarefa por dentro (descrição, subtarefas, comentários, anexos) fica guardada no painel igual ao Asana (#455): abre rápido e aparece mesmo com o Asana fora; **↻ Atualizar do Asana** relê na hora. Tarefa excluída no Asana sai daqui na sincronia seguinte (até 15 min) e fica no card do cliente como "excluída no Asana" | todos |
| Administrativo | **Integrações** | `/ops/integrations` | o estado de cada sistema; "Verificar agora"; atualizar o sistema | todos (atualizar: administrador) |
| Administrativo | **Auditoria** | `/ops/audit` | o registro imutável de tudo | gerente+ |
| Administrativo | **Políticas da IA** | `/ops/policies` | o que a IA faz sozinha, o que pede confirmação, aprovação ou está bloqueado | administrador |
| Administrativo | **Usuários** | `/ops/users` | criar, desativar, mudar papel e cargo; chaves de API | administrador |
| Administrativo | **Cofre** | `/ops/cofre` | logins e senhas da URACE, cifrados. A IA não tem acesso | só acesso livre |
| (menu do nome) | **Minha conta** | `/ops/account` | trocar a própria senha; quem vende também conecta o próprio Google Calendar aqui | todos |

### Menu do box (mecânico e coach)

Meu dia (é a tela inicial) · Balcão · Checklists · Estoque · Pedidos · Clientes · Equipe.
Detalhe no [playbook de mecânicos e coaches](playbook-mecanicos-e-coaches.md).

### A barra de cima (em toda tela)

Quatro cápsulas mostram o estado da operação. Cada uma leva para onde se resolve:

| Cápsula | Diz | Leva para |
|---|---|---|
| **Espelho** | há quanto tempo os dados foram lidos das fontes | Hoje |
| **Sistemas** | quantos sistemas estão respondendo | Integrações |
| **Atenção** | quantos itens precisam de gente, e quantos críticos | Precisa de atenção |
| **IA** | quantas ações esperam você | Aprovações |

Se aparecer **Offline**, o aparelho está sem internet. **Servidor fora**: o painel não respondeu.

### Criar, novo, adicionar: sempre em cima (#312)

Dono, 16/10: *"essas coisas de inserção fiquem sempre por cima, assim que abrir"*. Em toda tela que cria alguma coisa,
o botão de criar fica **em cima da lista** (que cresce), e não no fim dela. Ele abre o formulário logo abaixo, com o
cursor já no primeiro campo; **Fechar** ou **Esc** fecham e o cursor volta ao botão. O formulário é o de sempre: os
mesmos campos e o mesmo "Criar".

| Tela | Botão em cima | Antes ficava |
|---|---|---|
| Site › Serviços e preços | **Adicionar serviço** (com a página do site; veja a seção 6, "Serviços e cartões do site") | depois de todos os serviços |
| Site › Cartões das páginas | **Adicionar cartão** | depois das três páginas de cartões |
| Site › Produtos da loja | **Novo produto** | depois dos produtos e da paginação |
| Site › Editor do site | **Adicionar página**: uma página nova ou **Abrir uma página do site** | depois das páginas no editor |
| Site › Disponibilidade | **Bloquear datas** | na 3ª seção, depois do calendário e da semana |
| Usuários | **Novo usuário** (e, na seção Chaves de API, **Nova chave**) | na coluna da direita, que no celular caía para baixo da tabela |
| Robô SDR | **Pausar a IA numa conversa**, **Nova instrução** e **Novo relato**, cada um em cima da sua lista | depois de cada lista |
| Oportunidade (`/ops/sales/<n>`) | a **Anotação (interna)**, sempre aberta | depois do Histórico |
| Card do cliente › Mensalidade e contrato | **Adicionar contrato** (o PDF) | no fim da seção do contrato |
| Card do cliente › ★ Equipamento › catálogo | **Novo chassi**, **Novo motor**, **Nova peça** | a linha "Novo" depois de cada tabela |
| Checklists › Editar | a linha **Novo item** (Adicionar item), sempre aberta (o item entra no fim da lista) | depois dos itens |
| Corridas › a corrida | **Convidar**, sempre aberto | depois dos pilotos da corrida |

Ficam onde estão: o **chat** (Chat do Kommo, chat da Equipe, Testar o robô, IA), que escreve embaixo como todo chat; e
as listas curtas dentro de um formulário que já está aberto (**+ Opção** e **Subir foto** do produto, **+ item** da
compra, **+ Pergunta** do editor), em que o novo entra no fim e o botão fica onde ele vai aparecer. O **Novo artigo** do
Blog, o **+ Novo cliente**, a **Nova oportunidade**, a **+ Nova corrida** e os do Estoque, Compras, Suits, Cofre, Equipe e
Automação já estavam em cima.

Nenhum desses formulários cria um registro de pessoa sem dono: o **Vincular ao cliente** (seção 5) continua onde
sempre esteve. O contrato e o equipamento nascem no card aberto; a anotação, na oportunidade (que já tem o cliente); o
convite da corrida é o próprio card do piloto ★ Pro. Serviço, cartão, produto, página, bloqueio, usuário, chave,
instrução e relato não são de um cliente.

### O cartão de cada registro: o padrão D (#313)

Dono, 16/10: *"Todo tipo de card que tiver precisa ser um design bom, centralizadinho, bem intuitivo"*; das opções
mostradas, *"perfeito siga com a opção D"*. Todo registro que aparece como cartão no painel (um agendamento, uma conta, um
pedido, uma oportunidade…) usa o mesmo cartão, lido sempre de cima para baixo:

1. **A pílula da situação**, em cima, com a cor do estado: verde (feito, em dia), amarelo (esperando alguém), vermelho
   (deu errado, atrasado, anulado), azul (informação) e cinza (desligado, escondido).
2. **As iniciais** de quem é (ou a foto do produto, a capa do artigo), o **nome** e, embaixo, a linha que explica (o
   serviço, o piloto, o e-mail).
3. **O bloco grande**: o número que importa naquele registro — a data e o turno do agendamento, o total do pedido, o
   valor da oportunidade, o que segue retido do depósito, quanto tem no estoque.
4. **A barra de progresso**, só quando o painel tem o dado (no agendamento aceito: aceito, pago e waiver em dia).
5. **A lista** do que já aconteceu, uma linha por coisa, com o ícone da situação; quando a linha tem o que fazer, o
   botão fica nela (o driver de uma conta: **Vincular a este**).
6. **As ações**, embaixo, em grade de dois: a principal em **azul** (Aceitar, Vincular, Salvar), a que desfaz ou recusa
   com **contorno vermelho** (Recusar, Cancelar, Anular) e as outras em cinza. O botão **vermelho cheio** fica só para a
   ação da tela (Nova oportunidade, Adicionar serviço…), um por tela.

Cada parte só aparece quando o painel tem o dado: o cartão não inventa campo. Com muitas colunas no computador, a lista
continua **tabela** (Clientes, as tarefas do Asana, os envelopes do DocuSign, as invoices do QuickBooks); no celular,
cada linha dela vira o mesmo cartão, com a pílula em cima, o nome centrado, o número principal no bloco (o próximo
serviço, a data, o saldo) e o resto em linhas. As listas simples (`Bloqueios`, os modelos da waiver, as
leituras do balcão, os pedidos esperando compra, a Biblioteca) ficam em linhas com o mesmo acabamento. Funciona no tema claro e no escuro, sem rolar para o lado no celular.

| Tela | O bloco grande mostra | As ações |
|---|---|---|
| Site › Agendamentos | o dia e o turno | **Recusar**, **Aceitar**, **Confirmar mesmo assim** (gerente); confirmada: **Cancelar** |
| Site › Contas de clientes | — (a lista mostra os pilotos, a sugestão e o card) | **Vincular a este** ou **Criar cliente**; **Vincular** ao escolhido em *Outro cliente*; ligada: **Desvincular** (gerente) |
| Site › Pedidos do site | o total, com o nº do pedido e a hora | **Resolvido** (sem estoque), **Página do pedido ↗**, **Copiar o link**, **Venda** |
| Site › Security deposit | o que segue retido | **Conferir no Stripe**, **Devolver pelo Stripe** (gerente) |
| Site › Waiver › Assinadas aqui | o dia em que assinou e até quando vale ("selada · carimbo de tempo", #110) | **Card**, **PDF**, **Trilha** (abre a trilha de eventos dentro do cartão), **Pacote de prova** (ZIP para o advogado, gerente), **Anular** (gerente) |
| Site › Serviços e preços / Cartões das páginas | o preço | **Salvar**, **Desativar**/**Reativar** (ou **Esconder**/**Mostrar**, ↑ ↓) |
| Site › Produtos da loja | o preço | **Editar** |
| Site › Estoque do site | quanto tem (Galpão + Pista) | **Passar a dropshipping**/**em estoque**, **Abrir o produto** |
| Site › Editor do site / Blog | o endereço da página | **Editar** / **Abrir**, **Ver no site ↗** |
| Oportunidades (quadro) | o valor | o cartão inteiro abre a oportunidade |
| Card do cliente › Conta no site | — (a lista mostra as medidas) | **Client ID** do piloto que tem outro card |
| Meu dia (serviço e corrida) | na corrida, quantos pilotos; no serviço, a barra **Checklists feitos** | **Card**, **Peças**, **Excluir** (gerente); os checklists, um por linha |
| Balcão › invoice de peças | o total | **Tentar de novo**, **Enviar invoice por e-mail** (gerente), **Cobrar no cartão** |
| Balcão › Rascunho de invoice (#341/#346) | o total do rascunho; linha **preço digitado** e **sem preço** marcadas | **Adicionar linha** (Estoque, QuickBooks, Linha livre), **Criar invoice** (operador+; cria o item que falta no QuickBooks, em Parts, sem duplicar), **Conferir no QuickBooks** (gerente, quando o QuickBooks não respondeu), **Descartar rascunho** |
| Balcão › invoice aguardando revisão (#346) | o total; "aguardando revisão do gerente" | **Revisar** (gerente): mudar preço/quantidade, remover/adicionar linha, **Confirmar a invoice**; só depois **Enviar** e **Cobrar no cartão**. Aparece também em Precisa de atenção |
| Balcão › Revisão | o preço da peça; a barra **Pronta para cobrar** | **Cobrar**, **Guardar para o cliente**, **Usar a do cliente**, **Descartar** |
| Estoque (a prateleira) | quanto tem, com a foto no lugar das iniciais | o cartão inteiro abre a peça; a lixeira fica no canto da foto |
| Pedidos | para quando a peça é precisa | **Comprar** (marca para a compra, gerente), **cancelar**, **entreguei** |
| Compras | o total (ou a previsão de entrega) | o cartão inteiro abre a compra |
| Checklists › Modelos | quantos itens | **Começar hoje**, **Editar** (gerente; aberto, o cartão ocupa a linha inteira) |
| Corridas (e os pilotos dentro da corrida) | a data | o cartão abre a corrida; o piloto convidado tem a situação e **✦ Prévia de custo** |
| Precisa de atenção (e Hoje, compacto) | — (os fatos do aviso na lista) | o que abrir (**Abrir cliente**, **Ver aprovações**…), o sistema de origem ↗, **✦ Instruir a IA**, **ocultar** |
| Suits › Pedidos / Leads / Fornecedores | o dia do pedido / — / quantos pedidos | o pedido abre inteiro; **Virar pedido**, **Perdido**; **Editar** |
| Funil do Kommo | o valor do lead | o cartão inteiro abre a conversa |
| Equipe › Pessoas | — | o cartão inteiro abre a conversa com a pessoa |
| Cofre | — (o usuário e, depois de **Ver senha**, a senha na lista, cada uma com **Copiar**) | **Ver senha**, **Editar**, **Arquivar** |
| Integrações | há quanto tempo o sistema respondeu | o erro em vermelho e os detalhes técnicos dentro do cartão |

Ficam no jeito delas, porque ali o cartão atrapalharia: as **conversas** (Chat do Kommo, chat da Equipe, a IA), que são
lista de mensagens; as **linhas do tempo** e a **Agenda de vendas**, que andam pela hora; os **calendários** (a semana e o
mês do Meu dia, o mês das Corridas); os **números** do Hoje e dos painéis; e as janelas de formulário.

### Endereços antigos

`/ops/vendas` vai para `/ops/sales`; `/ops/crm` e `/ops/kommo` vão para o Chat do Kommo;
`/ops/tasks` para Asana; `/ops/waivers` para DocuSign; `/ops/emails` para Gmail.

---

## 4. Rotinas do dia

### O que o sistema faz sozinho

Estes são os horários **padrão**, no fuso da Flórida. Um administrador pode ligar e desligar
cada rotina em **Automação e memória**.

| Quando | Rotina |
|---|---|
| a cada 15 minutos | o espelho lê de novo as fontes (Asana, DocuSign, Gmail, QuickBooks) |
| a cada 15 minutos | a ponte de e-mail dos Suits lê o Gmail `urace@` (ver o [guia de Suits](../suits-guia-do-lucas.md)) |
| a cada 15 minutos | os grupos do ateliê no WhatsApp: a IA trata as mensagens novas e, das 09h às 18h, a cobrança do dia (#383) |
| 06:00 | varre Gmail e DocuSign de cada cliente ativo e liga o que achar ao card |
| 07:00, 13:00, 21:00 | triagem do Gmail pela IA: marca e move para o marcador principal |
| 07:00, 22:00 | testa cada integração com uma chamada real |
| 07:30 | lê a Rate Card no Drive e aplica os preços no QuickBooks |
| 08:10 | confere a conversa de cada lead no Kommo contra a do painel |
| 09:00 | lembrete das invoices em aberto que têm lembrete ligado e dia chegado |
| 09:00, 16:00 | aviso no celular de cada pessoa com o que ela ainda precisa completar ("Falta completar") |
| 03:15 | **backup do banco** na VPS: cópia conferida, 30 dias + a primeira de cada mês por 12 meses (#299) |
| 04:00 | **cópia cifrada do backup no Google Drive** (`Command Center/Backup do banco`), com o mesmo histórico (#299) |

### Abertura (equipe)

1. **Hoje** (`/ops/`): pista de hoje, "Precisa de gente", "Esperando você", waivers abertas.
   Se o aviso "Espelho antigo" aparecer, clique em **↻ Sincronizar** (operador+).
2. **Precisa de atenção**: comece pelo crítico. Cada item tem um botão para abrir a origem
   (cliente, inbox, estoque, compras, agenda, aprovações...) e **✦ Instruir a IA**.
3. **Aprovações**: decida o que a IA propôs. Cada proposta mostra a prévia do que vai acontecer.
4. **AI Command › Falta completar**: registros que a IA criou com informação faltando e que você
   pediu. Complete e toque em **Completei**.
5. **Equipe**: mensagens não lidas (o número no menu).
6. Vendas: **Agenda de vendas** do dia. Detalhe no [playbook de vendas](playbook-vendas.md).

### Abertura (box)

**Meu dia** é a tela inicial do mecânico e do coach: os serviços, as corridas e as sessões
marcadas pelo site no dia, com o checklist de cada um. Detalhe no
[playbook de mecânicos e coaches](playbook-mecanicos-e-coaches.md).

### Durante o dia

| Aconteceu | Onde |
|---|---|
| cliente novo, ou cliente que já existe | **Clientes** (ver seção 5) |
| peça usada ou entregue | **Balcão** |
| falta peça | **Pedidos** (o pedido); quem compra junta em **Compras** |
| lead conversando | **Chat do Kommo** |
| pedido de macacão | **Suits · Alpha Line** |
| pedido de sessão pelo site | **Site › Agendamentos** |
| como o site está indo (vendas, visitas, conversão) | **Site › Painel do site** |
| preciso que a IA faça algo | **AI Command**, ou **✦ Instruir a IA** no item de atenção |
| conversa com colega | **Equipe** (o que é de cliente fica no Chat do Kommo) |

### Fechamento (sugestão de conferência)

O painel não tem um botão de "fechar o dia". Antes de sair, vale conferir:

1. **Precisa de atenção** sem crítico esquecido.
2. **Aprovações** sem proposta sua parada.
3. **Falta completar** com o que você já conseguiu completar marcado como **Completei**.
4. Box: os checklists do dia preenchidos em **Meu dia**.
5. Vendas: os retornos de amanhã na **Agenda de vendas**.

---

## 5. Clientes e pilotos

### O card do cliente

Clientes (`/ops/clients`) tem **um card por pessoa**, do serviço mais recente para o mais
antigo. **Ativo** é quem teve serviço nos últimos 6 meses. O **piloto** aparece em destaque; o
**responsável** (quem paga e assina) fica ao lado.

Dentro do card (`/ops/clients/<n>`), logo abaixo dos números (próximo serviço, último serviço, serviços e em
aberto), vem o quadro **Dados do cliente** (#460): piloto e irmãos, nascimento e idade (menor em destaque),
**classe** (a do card ou, sem ela, a do tamanho do chassi), **waiver** (com o link **ver waivers**, que abre a aba, e o
**✉ Convite por e-mail** quando não há assinada), **responsável** e **parentesco** (o do card ou o da waiver), e-mail,
telefone, Client ID, **tamanhos** (macacão, capacete, luva, sapato) e **medidas** em polegadas/libras com o métrico ao
lado. As medidas vêm da área do cliente; a equipe corrige em **Editar dados** (parentesco, classe e "Medidas e
tamanhos"), e o quadro diz de onde veio cada uma. Plano mensal, etapa e empresa ficam em **Plano e origem**.

Depois vêm as abas, nesta ordem:

| Aba | O que tem |
|---|---|
| Linha do tempo | **por visita**: o serviço com as subtarefas, o checklist do box, o **último comentário do Asana** e as **peças do balcão daquele dia**; **Abrir o serviço** (operador+) leva ao card do serviço e **Anotar neste serviço** grava um comentário na tarefa do Asana com o seu nome. Também waiver enviada/assinada, ação da IA, invoice |
| Serviços | as tarefas do Asana do cliente (o nome abre o card do serviço): **Renomear** (operador+), **Mover** (gerente+) |
| Waivers | os envelopes do DocuSign e as assinadas no sistema, com o PDF assinado; no topo, o switch **Waiver: fluxo deste card** (DocuSign ou nativa, abaixo) e o **Convite da waiver por e-mail** (abaixo). A assinada no sistema tem **Anular** (gerente+, abaixo) |
| E-mails | os e-mails ligados ao card |
| Mensalidade e contrato | plano mensal e contrato da Academy (valor: gerente+). #314: também o **valor** e o **item do QuickBooks** da sessão extra (acima do pacote do mês); vazio, vale o do plano ou o mensal ÷ sessões. #340: **"O que o cliente vê"** — o contador do mês (usadas de Y, livres, zera no dia 1), a mensalidade do mês pelo QuickBooks (paga, aberta, sem invoice), as extras do mês e o **em aberto** (sessões já feitas sem invoice paga, com quais sessões e quais invoices). O cliente vê o mesmo contador no Dashboard e em Book sessions. **Piloto pro sem mensalidade** (★ Pro e Mensalidade vazia): aviso no topo do card e em Precisa de atenção — preencha sessões por mês, valor mensal e o Plano mensal (o kart); até lá ele não vai para o carrinho e nenhuma invoice sai pelo preço da tabela. #355: o aluno do plano (e o pro em montagem) marca **"Training Day X/Y"** (a próxima sessão do pacote no mês: "Training Day 2/4"; acima do pacote, "Training Day · extra $X"; sem Mensalidade, só "Training Day") em vez da lista do Arrive and Drive, e o agendamento fica com esse nome em Agendamentos, Asana e e-mails. Detalhes no [playbook de vendas](playbook-vendas.md), "Piloto pro" |
| ★ Equipamento e ★ Corridas | só para Pro Racing Driver |
| Peças | o QR que o mecânico lê no balcão e as peças do cliente |
| Conta no site | a conta da área do cliente ligada ao card |
| Invoices | só gerente e administrador (para os outros, aparece 🔒) |
| IA | o que a IA propôs para este cliente |

### O card do serviço (#460)

`/ops/servicos/<n>` é a tarefa do Asana dentro do Command Center, igual ao Asana (o espelho do #455): descrição,
subtarefas, comentários e anexos, e ao lado o **cliente** (idade, classe, waiver e tamanhos), as **peças do balcão do
dia** (valor só para gerente+), o **checklist do box** e os campos do Asana. Abre pela linha do tempo do card do
cliente, pela aba Serviços e pelo **Abrir o card do serviço** da tarefa na tela Asana (operador+).
- **Anotar** grava um comentário na tarefa do Asana, com o seu nome na frente ("Nome (Command Center): …"), e o
  card relê na hora.
- **Concluir** numa subtarefa aberta conclui no Asana. Não existe desconcluir por aqui.
- Tarefa do ADM URACE ou de "Matt tasks" é recusada (a regra do Asana continua valendo).
- **↻ Atualizar do Asana** relê a tarefa na hora; **Asana ↗** abre a tarefa lá.

O box vê o card **sem valores**: não aparecem mensalidade, corridas, conta no site, e-mails,
invoices nem IA.

#### Editar o card: nome, e-mail, telefone (#410)

**Editar** (operador+) corrige os dados da pessoa, não só status, etapa e notas: **Responsável**
(quem paga e assina), **Piloto** (vazio = o próprio responsável), **Nascimento do piloto**,
**E-mail**, **E-mail alternativo**, **Telefone** e **Empresa**. **Salvar** grava só o que mudou.

- O responsável não fica vazio. E-mail precisa ser válido; o telefone sai no formato da casa
  (`407-555-0100`). Nascimento não pode ser no futuro. Campo opcional vazio apaga o valor.
- **E-mail de outro card é recusado**: aparece "O e-mail … já está no card N". Se é a mesma pessoa,
  use **⋯ › Unir com outro card**; se é irmão, o card do irmão já aceita o e-mail do responsável.
- A sincronia do Asana e do QuickBooks **não desfaz** a correção: ela só preenche campo vazio.
- A auditoria guarda o valor de antes e o de depois.

#### Waiver por card: DocuSign ou nativa (#348)

Dono, 19/10: *"Um switch para escolher dentro do card de cada cliente se vamos usar o fluxo pelo DocuSign ou pela
waiver nativa."*

- **Onde:** card › aba **Waivers** › **Waiver: fluxo deste card**. Todos veem; só **gerente ou acima** muda.
- **Padrão (geral: …)**: segue a chave geral de **Site › Waiver** (o nome entre parênteses diz qual vale hoje).
  É como todo card nasce.
- **DocuSign**: a próxima waiver deste card sai sempre pelo DocuSign, mesmo com a chave geral ligada. A área do
  cliente não oferece **Sign now** para o piloto deste card.
- **Nativa**: o piloto deste card assina na área do cliente (ou pelo convite por e-mail), mesmo com a chave geral
  desligada; a cobrança da sessão não manda o DocuSign. Só dá para escolher com o **selo digital configurado** e os
  dois modelos importados (Site › Waiver): sem isso o botão fica desligado e diz por quê. Se o selo deixar de estar
  configurado depois, o card **cai para o DocuSign** na hora de enviar e aparece em **Precisa de atenção**.
- O switch só decide a **próxima** waiver: a já assinada (de qualquer fluxo) continua valendo. Vale por card: o irmão
  ou outro piloto da mesma conta segue o switch do card dele. Piloto sem card segue a chave geral.
- Cada mudança fica na Auditoria (`client.waiver_flow`, com antes, depois e quem).

**Pré-requisitos por provedor (#364).** Dono, 20/10: *"Waiver pronta para uso: mostrar os pré-requisitos por
provedor. No teste, DocuSign está selecionado; a opção nativa está desabilitada por falta dos dois templates. Isso
não indica falha no DocuSign."* Debaixo do switch, cada provedor tem a sua lista, com ✓ (ok) ou ✗ (falta) e, no que
falta, como resolver:

| Provedor | Pré-requisito | Como resolver quando falta |
|---|---|---|
| DocuSign | **DocuSign conectado** (a última sondagem de Integrações) | Integrações › **Verificar agora**; se continuar, conferir a credencial do DocuSign no servidor |
| DocuSign | **Modelos de waiver definidos** (adult e parental) | os dois modelos têm de estar definidos no sistema |
| Nativa | **Os 2 modelos importados** do DocuSign (mostra "N de 2 importados") | Site › Waiver › **Importar do DocuSign** (ADMIN; só lê os modelos, nada muda no DocuSign) |
| Nativa | **Selo digital (PAdES) configurado** | configurar o selo no servidor (`selo-waiver`; veja Site › Waiver) |
| Nativa | **Chave geral ligada** (opcional no card) | só conta para os cards em **Padrão**; escolher **Nativa** no card não depende dela |

- Ao lado do nome do provedor aparece **pronto** ou **não pronto** (pronto = todos os obrigatórios com ✓).
- A nativa indisponível diz o porquê numa frase só, por exemplo: *"Nativa indisponível: faltam os 2 modelos
  importados. Isso não é falha do DocuSign."* A lista do DocuSign continua com ✓: a falta é da nativa.
- O "conectado" do DocuSign não chama o DocuSign ao abrir o card: lê o estado de **Integrações** (sondagem de manhã
  e à noite, ou **Verificar agora**).
- O conector (MCP) lê o mesmo: `urace_cliente` traz `waiver_fluxo` com a escolha, o fluxo que vale e
  `prerequisites` (`docusign` e `nativa`, cada um com `pronto` e os itens `{chave, rotulo, ok, como_resolver}`).
- Rota: `GET /clients/{id}/waiver-flow` (a mesma do switch) devolve `prerequisites` junto.

#### Convite da waiver por e-mail (#135)

Dono, 14/10: *"vai ser por e-mail para o adulto ou para o responsável assinar aquela waiver. Tanto
para adulto quanto para responsável, o e-mail que tiver no card vai receber isso."*

1. No card, aba **Waivers** (ou o botão **✉ Convite por e-mail** no quadro Waiver do topo).
2. O quadro diz **para quem vai**: piloto com **18 anos ou mais** (pela data de nascimento do
   piloto no card) assina a **própria** waiver (adult); **menor**, o **responsável** (o nome do
   card) assina por ele (parental, pai ou mãe). O e-mail é sempre o **e-mail do card**.
3. **Enviar convite da waiver por e-mail** → a janela mostra nome e e-mail → **Enviar**.
4. A pessoa recebe um link **pessoal**, que vale **uma vez** e vence em **72 horas**. Ele abre a
   assinatura do próprio sistema **sem conta e sem login**, já presa àquele card e piloto. Na hora
   de assinar chega um **código de 6 dígitos** no mesmo e-mail.
5. Assinou: a waiver aparece na aba Waivers como as outras ("área do cliente"), com o PDF e o
   certificado, e o convite fica **assinado**.

Situação de cada convite: **enviado** · **aberto** (a pessoa abriu o link) · **assinado** ·
**expirado** (passou das 72 h) · **substituído** (você reenviou; o link velho não vale mais) ·
**não saiu** (o Gmail não mandou: tente de novo). **Reenviar** manda um link novo. Tudo fica na
Auditoria (`waiver.invite.*`).

O botão fica **desligado, com o motivo escrito**, quando: o card não tem e-mail; o card não tem a
data de nascimento do piloto; o piloto é menor e o card não tem o responsável; o e-mail é da URACE;
ou o card está no DocuSign (o switch **Waiver** do card, ou a chave geral de Site › Waiver no Padrão). Se o card mudar
de e-mail ou de data de nascimento depois do envio, o link para de valer: reenvie.

**Renovação (#354).** Dono, 20/10: *"as novas waivers entram quando as atuais forem vencendo"*.
- Com uma waiver **valendo** no card ou no piloto (a do sistema ou a do DocuSign, que vale 1 ano da assinatura), o botão
  fica desligado e diz até quando ela vale e em que dia a renovação libera.
- Nos **últimos 30 dias** dela o convite libera, como **renovação**. Em **Precisa de atenção** aparece "*piloto*: a
  waiver vence em N dia(s)", com o botão **✉ Mandar convite de renovação** (mostra para quem vai e pede confirmação).
  Nada sai sozinho: só com o clique de alguém da equipe.
- A parental que vale até a véspera dos 18 não renova pelo convite: no aniversário o próprio piloto assina a dele.
- A cobrança da sessão marcada pelo site continua mandando a waiver só quando não há uma válida no dia da sessão.
- A área do cliente mostra as waivers dos pilotos daquela conta: quem tem o piloto ligado vê também a waiver que o
  responsável (o e-mail do card) assinou pelo convite. Fica assim (dono, 20/10).

#### Como o cliente assina: revisar antes do clique final (#112)

Vale para a área do cliente (**Drivers › Sign now**) e para o link do convite. A Flórida (§668.50(10))
deixa a pessoa desfazer uma assinatura feita por erro quando o sistema não deu chance de evitá-lo
(assinou pelo piloto errado, digitou outro nome). Por isso são **dois passos**, e o servidor exige os dois:

1. **Formulário.** O cliente lê o PDF inteiro (as caixas só se liberam depois), marca as caixas, diz o
   parentesco (pelo menor: pai ou mãe), digita o nome completo e desenha a assinatura. Na área do
   cliente, o e-mail da conta é confirmado por código uma vez. Toca **Review before signing**.
2. **Resumo ("Review and sign").** O servidor confere tudo, menos o código, e mostra: documento, piloto,
   quem assina, parentesco e declaração, o nome digitado e o nome do cadastro, a assinatura desenhada e
   até quando vale. Aqui ele pede o **código de 6 dígitos** do e-mail. O botão final é **I agree — sign
   the waiver**, com a frase de efeito legal logo acima ("…the same legal effect as a handwritten
   signature"). **Go back** volta ao formulário sem perder nada.

- **Nome diferente do cadastro** (acento, maiúscula e espaço repetido não contam): o resumo avisa *"The
  name you typed (…) is different from the name on file (…)"* e só assina depois da caixa **Yes, sign with
  the name I typed**. O nome do cadastro é o da conta (área do cliente) ou o do convite (adulto: o piloto;
  menor: o responsável do card). Os dois nomes ficam na trilha e no certificado.
- **O resumo vale uma vez, por 30 minutos, e só com o mesmo conteúdo.** Mudou o nome, a assinatura, o
  parentesco ou a leitura depois do resumo: *"Something changed after the review. Review the summary
  again before signing."* Passou de 30 min: *"The review expired."* Nos dois casos, **Go back** e
  **Review before signing** de novo. Sem resumo não há assinatura, nem pela tela nem pela API.
- **Na trilha e no certificado:** o passo **revisou o resumo**, com a hora, antes do código; e a hora da
  confirmação, que é a da assinatura. No PDF: *"Reviewed the summary: … · Confirmed and signed: …"* e a
  frase que estava ao lado do botão.
- **Se o cliente disser "assinei e não foi":** ele parou no resumo. Falta pedir o código, digitar e tocar
  **I agree — sign the waiver**.

#### Cópia por e-mail e as waivers na área do cliente (#114)

- **Logo depois de assinar** (pela área do cliente ou pelo convite), sai um e-mail **do noreply@** para **quem
  assinou**, com o **PDF assinado anexado** (o mesmo arquivo do download, conferido pelo hash). A resposta do
  cliente cai no **support@** (Reply-To). A tela de "Signed" diz para onde a cópia foi (mascarado).
- **Para quem:** sempre o e-mail que assinou (o da conta, confirmado por código, ou o do convite). Nem o cliente
  nem a equipe escolhem outro destino; se o card mudou de e-mail depois, a cópia continua indo para o que assinou.
- **Se o Gmail falhar** (recusa, rede caída ou lenta), a assinatura **vale do mesmo jeito**: fica registrado "a
  cópia por e-mail não saiu" e dá para reenviar. O PDF que não bate mais com o hash gravado não sai.
- **Na trilha** (Site › Waiver › Trilha): **cópia por e-mail**, com a hora, para quem e o **message-id** do Gmail;
  ou **a cópia por e-mail não saiu**, com o motivo. Nada disso entra no PDF nem muda a waiver.
- **Reenviar:**
  - o cliente, em **Drivers › Signed waivers** (`/ops/portal/waivers`), botão **Email me a copy** (10 min depois
    da última cópia que **saiu**; se a automática falhou, pode pedir na hora; até 3 por dia por waiver). Se quem
    pede é outra conta que vê a waiver (o piloto dela, assinada pelo convite), a cópia vai do mesmo jeito para
    quem assinou, e a trilha registra que o pedido veio daquela conta;
  - a equipe, no card › aba **Waivers** (operador+) ou em **Site › Waiver › Assinadas aqui** (gerente+), botão
    **✉ Reenviar cópia**: a janela mostra o e-mail que assinou antes de mandar (uma por minuto, até 10 por dia).
    O card e a lista mostram a última cópia ("cópia por e-mail para m•••@… em …" ou "não saiu").
  - A **anulada** não se reenvia; o PDF dela continua para baixar.
- **Signed waivers** (área do cliente): todas as waivers assinadas no próprio sistema pelos pilotos da conta,
  **vigentes, vencidas e anuladas** (a parental aparece vencida quando o piloto faz 18), das mais novas para as
  mais velhas, 10 por página, cada uma com **Download PDF** e a última cópia. Só a própria conta vê e baixa.
  Quem assinou pelo convite (sem conta) tem a cópia no e-mail, que fica depois que o link vence em 72 h.

#### Conferir o documento no balcão e o nascimento travado (#117)

Dono, 06/10: *"sim, no check-in"*. A equipe confere o documento com foto de quem assinou.

- **Onde:** **Balcão** › abrir o cliente (QR, pilotos de hoje ou nome) › quadro **Waiver · Conferir documento**
  (operador+, mecânico e coach também). Aparecem as waivers que valem **para aquele card**: a assinada no sistema e a
  do DocuSign (só waiver de verdade, adult ou parental: um envelope como o Membership Agreement não conta); nunca a de
  outro card. A parental de quem já fez 18 não aparece (não vale mais): pela data gravada na própria waiver ou, na do
  DocuSign, pela do card. A assinada por um piloto da área do cliente **segue o piloto**: religado a outro card, ela vai
  junto; vínculo feito à mão pela equipe (aba Waivers do card) vale mais. Card VIP sem waiver: o quadro diz que dispensa.
- **O que se grava:** o tipo de documento (carteira de motorista, passaporte, State ID ou outro documento oficial com
  foto), se o nome confere e, pelo menor, se a idade confere com o nascimento declarado. **Nem foto nem número do
  documento.** Vira o evento **documento conferido no balcão** (ou **documento não conferiu no balcão**) na trilha da
  waiver (Site › Waiver › Trilha, depois de assinar; não entra no PDF selado nem muda a waiver) e a Auditoria
  `waiver.id_check`.
- **Não conferiu:** registra e alerta. Aparece em **Precisa de atenção** ("o documento com foto não conferiu com a
  waiver", com o link do balcão do cliente) e **nada é bloqueado sozinho**: a equipe decide (conferir de novo, anular
  e pedir outra, ou seguir). O aviso fica no card a que a waiver vale **agora** (religada, card unido ou piloto
  religado: vai junto). Sai da lista quando a conferência seguinte bate, e sai sozinho (fica em "Mostrar ocultos",
  com o motivo) quando a waiver é anulada, ocultada, fica sem card ou deixa de valer.
- **Nascimento travado:** com a waiver assinada no sistema **valendo**, o cliente não muda a data de nascimento do
  piloto (ela decidiu entre parental e adult e está no documento assinado). A área do cliente mostra o campo travado
  com a explicação; se tentar, o servidor recusa (409) e a tentativa fica na Auditoria
  (`portal.driver.birth_date_locked`). O resto do piloto continua editável. Se a data está errada, um **gerente anula**
  a waiver (abaixo) e o cliente corrige a data e assina outra. Vencida ou anulada, a data volta a mudar.

#### Waiver assinada no próprio sistema: nunca se apaga, se anula (#109)

Dono, 06/10: *"nunca apagar"*. A waiver assinada na área do cliente ou pelo convite é o registro
legal, e não há cópia no DocuSign.

- **Não muda.** O próprio banco recusa mudar a linha dela (quem assinou, datas, hash, trilha, PDF) e
  recusa apagá-la. Continuam livres só o vínculo com o card (unir, soltar, vincular à mão) e o
  "ocultar" da lixeira, que a tela e a IA recusam para ela. O PDF fica só leitura no servidor.
- **A trilha vai também para a Auditoria** (`waiver.signed.trail`), no mesmo instante da assinatura.
- **Não vai para a lixeira**, nem pela tela DocuSign (o botão 🗑 não aparece para ela) nem pela IA.
- **Anular** (gerente ou acima), no card › aba **Waivers** ou em **Site › Waiver**: escreva o motivo
  (pelo menos 10 letras) e confirme. A waiver **continua** no card, na lista e no backup do Drive,
  marcada **anulada**, com quem anulou, quando e por quê, e a linha do tempo do card ganha "Waiver
  anulada". Ela deixa de valer: o piloto aparece sem waiver e o cliente pode assinar outra. A anulação
  fica na Auditoria (`waiver.void`) e **não se desfaz**.
- **Backup:** a Biblioteca leva toda assinada, inclusive a oculta e a anulada (com "(anulada)" no
  título). Se o PDF no servidor não bater mais com o hash gravado na assinatura, ela não sobe, a cópia
  do Drive fica como estava e o erro aparece na Biblioteca e na Auditoria
  (`biblioteca.waiver.hash_divergente`).

#### Site › Waiver: versões do modelo e o aviso do §744.301(3) (#116)

- **Versões dos modelos.** Cada vez que o ADMIN clica **Importar do DocuSign** e o texto de um modelo
  mudou lá, entra uma **versão nova** (versão 1, 2…) e ela passa a ser a **atual**. A anterior **não se
  apaga nem muda** (o próprio banco recusa): continua na lista **Versões dos modelos**, com o **PDF**
  como foi importado, quando entrou, quem importou e quantas assinaturas usaram aquela versão.
  Importar o mesmo PDF de novo não cria outra versão. Cada assinatura guarda o hash e a identificação
  da versão que valia (**Template version ID**, no certificado): as próximas usam a nova, as já feitas
  ficam com a delas. Se o PDF de uma versão mudar no servidor, o botão **PDF** dá erro (não bate com o
  hash); importar o modelo de novo devolve o original.
- **Aviso do §744.301(3) (parental).** Pelo menor, a waiver só vale com o aviso que a lei da Flórida
  pede, em maiúsculas e com letra maior que o resto. O sistema confere o modelo parental: o texto
  aprovado **inteiro**, em **maiúsculas**, com a letra pelo menos **5 pt maior** que a do corpo (é o
  que o PDF deixa ler; o advogado confirma o texto e a regra).
  - **O texto do aviso não está no sistema.** Quem dá é o advogado. Enquanto ele não aprova, o quadro
    diz **"aviso: esperando o advogado"**: a conferência **só informa** e nada é barrado.
  - Quando o advogado aprovar, o texto vai, como ele aprovou, para o arquivo
    `~/.urace/waivers/aviso-744.txt` no servidor (ou o caminho em `CC_WAIVER_AVISO_744`). O quadro
    mostra o texto e se o parental atual **confere**. A partir daí, o parental que **não confere**
    não é importado (o atual continua valendo), a assinatura **não liga** e a parental **não se assina
    online** (pela área do cliente ou pelo convite); a adult segue normal. Arquivo que não abre ou
    vazio também barra.

#### Site › Waiver: selo digital e carimbo de tempo (#110)

Antes, a única prova de que o PDF assinado não mudou era o hash guardado no nosso próprio banco. Agora o PDF
sai **selado**, como o "tamper-evident seal" do DocuSign:

- **O selo** é uma assinatura digital (PAdES, SHA-256) com o certificado de selo da URACE, que **certifica** o
  documento ("nenhuma alteração"). Mudar **1 byte** do arquivo quebra o selo.
- **O carimbo de tempo** vem de uma autoridade externa (RFC 3161), não do relógio do servidor: DigiCert e, se ela
  não responder em 10 s, FreeTSA (a lista fica em `CC_WAIVER_TSA`, no `adminai.env`). O carimbo vai dentro do
  PDF e também na tabela `waiver_timestamps`, que não muda nem se apaga.
- **Só vale carimbo de autoridade conhecida.** Logo depois de selar, o sistema confere o carimbo: a autoridade tem
  de vir de uma **raiz de TSA aceita** e a hora dela tem de estar a até **5 minutos** do relógio da VPS. Senão,
  tenta a próxima da lista (e, sem nenhuma, a assinatura não acontece). As raízes aceitas são a **DigiCert Trusted
  Root G4** (já vem com o sistema, conferida pela impressão SHA-256 `55:2F:7B:DC:…:C8:99:88`) e os arquivos `.pem`
  da pasta `~/.urace/waivers/selo/tsa/` (ou `CC_WAIVER_TSA_ROOTS`): é lá que entra a raiz da **FreeTSA** (passo 2
  abaixo). Outra autoridade em `CC_WAIVER_TSA` só vale com a raiz dela nessa pasta.
- **Dono, 06/10:** certificado próprio da URACE + carimbo gratuito. No **Adobe**, o selo aparece com a identidade
  **desconhecida** (o certificado é nosso, não está na lista do Adobe); a integridade e o carimbo aparecem
  válidos. O certificado pago reconhecido pelo Adobe fica para depois.
- **Na tela** (Site › Waiver › **Selo digital e carimbo de tempo**, gerente+): **selo configurado** (com a
  impressão SHA-256 da raiz e a validade do certificado) ou **selo não configurado** (com o motivo). Em
  **Assinadas aqui**, cada waiver diz **"selada · carimbo de tempo"** com a hora da autoridade.
- **Sem o selo, não liga.** O botão **Ligar** fica desligado até o selo estar configurado. Se o selo sumir com a
  assinatura ligada, ou se as duas autoridades estiverem fora do ar, o cliente lê *"Online signing is temporarily
  unavailable. Please try again in a few minutes, or sign the waiver in person at the track."*, **nada é gravado**
  e o **código do e-mail continua valendo** (ele tenta de novo com o mesmo código). A falha fica na Auditoria
  (`waiver.seal_failed`, com o motivo).
- **A página de certificado** (a última do PDF) é desenhada antes de selar: ela descreve o selo e o carimbo, não o
  resultado. O que veio depois de assinar continua só na Trilha.

**Configurar (uma vez, na VPS, pelo administrador)**

1. `cd ~/Uraceagent && ~/.urace/cc-venv/bin/python -m command_center.manage selo-waiver criar`: gera a raiz e o
   certificado de selo em `~/.urace/waivers/selo/` (`seal-key.pem` só para o dono do processo, `seal-cert.pem`,
   `root-cert.pem`) e mostra a **impressão SHA-256 da raiz**: anote. Nunca sobrescreve: se já existe, avisa e
   não muda nada. A chave da raiz **não é guardada** (ninguém emite outro selo com ela).
2. A raiz pública da FreeTSA, baixada do site dela (o repositório não a traz porque não deu para conferir a
   original daqui):
   `mkdir -p ~/.urace/waivers/selo/tsa && curl -fsS -o ~/.urace/waivers/selo/tsa/freetsa-cacert.pem https://freetsa.org/files/cacert.pem && openssl x509 -in ~/.urace/waivers/selo/tsa/freetsa-cacert.pem -noout -subject -fingerprint -sha256`
   Confira que o assunto é o da FreeTSA e compare a impressão SHA-256 com a que a FreeTSA publica no site dela
   (`https://freetsa.org`); anote a impressão junto com a da raiz do selo.
   Sem esse arquivo, a FreeTSA não vale e só a DigiCert carimba.
3. `~/.urace/cc-venv/bin/python -m command_center.manage selo-waiver conferir`: sela um PDF de teste com a
   autoridade de verdade, valida (o selo pela raiz da URACE e o carimbo pelas raízes de TSA) e diz se o relógio
   da VPS bate com o dela. Mostra também as raízes de TSA aceitas.
4. `timedatectl`: tem de dizer `System clock synchronized: yes` e `NTP service: active`. A hora da assinatura no
   certificado é a do servidor; a do carimbo é a da autoridade, e as duas têm de bater.

**Backup da chave do selo.** A pasta `~/.urace/waivers/selo/` **não vai no backup do banco** (#299) nem no Drive.
Guarde uma cópia dela **fora da VPS** (no gerenciador de senhas do dono, como o `adminai.env`), por exemplo:
`tar -czf ~/selo-waiver-$(date +%F).tgz -C ~/.urace/waivers selo`, baixe o arquivo para o computador do dono,
guarde no gerenciador de senhas e **apague a cópia da VPS** (`rm ~/selo-waiver-*.tgz`). Nunca no repositório,
nunca por e-mail ou chat. Se a chave se perder, os PDFs já assinados continuam conferíveis pela raiz pública
(`root-cert.pem`, que também vai dentro de cada PDF); para assinar de novo, restaure a cópia na mesma pasta
(`chmod 600 seal-key.pem`) ou, sem cópia, gere um selo novo com `selo-waiver criar` numa pasta vazia (a raiz muda:
guarde a antiga para conferir os PDFs de antes).

**Conferir um PDF assinado:** abra no Adobe Reader (painel **Assinaturas**: "o documento não foi modificado" e o
carimbo de tempo) ou, na VPS, `~/.urace/cc-venv/bin/python -m command_center.manage selo-waiver conferir <arquivo.pdf>`
(só lê). Ele diz se o arquivo está **íntegro**, se o selo é **da URACE** (o certificado tem de vir da raiz do selo:
uma assinatura de outra empresa, mesmo de uma autoridade conhecida, não vale) e se o carimbo é de uma autoridade
aceita, com a hora batendo com a do selo. **Depois de trocar o selo**, os PDFs de antes se conferem com a raiz
antiga: `… selo-waiver conferir <arquivo.pdf> --raiz <root-cert.pem antigo>`.

#### Trilha de eventos da waiver assinada no próprio sistema (#111)

Como o certificado do DocuSign (enviado, visto, assinado), cada passo de quem assina fica registrado
com **hora, IP e aparelho**, e nenhum se muda nem se apaga (o próprio banco recusa):

| Passo | Quem registra |
|---|---|
| convite enviado por e-mail (só pelo convite) | o servidor |
| abriu a tela de assinar | a tela (área do cliente) ou o servidor (convite) |
| recebeu o PDF | o servidor |
| leu todas as páginas | a tela |
| revisou o resumo (#112: o passo 1, com o nome digitado e o do cadastro; acima) | o servidor |
| código enviado · código confirmado | o servidor |
| assinou (o clique final, com a hora da revisão e a da confirmação) | o servidor |

- **No PDF assinado**, o certificado lista esses passos em **Event history**, com a hora da Flórida e
  em UTC, IP e aparelho, e o hash do último passo. Com muitos passos ele **continua na página seguinte**
  ("continued"), sem cortar.
- **Recarregar não enche a trilha.** Cada passo da tela (abrir, receber o PDF, ler) entra no máximo **30 vezes
  por hora**, por conta (ou convite), piloto e modelo; no certificado, o mesmo passo repetido vira **uma linha só**
  ("×N", com a hora do primeiro e a do último). Irmãos abertos em duas abas: cada certificado leva os passos do
  seu piloto.
- **Depois de assinar** (cópia por e-mail, com o message-id, ou a falha (#114); PDF baixado pelo cliente ou
  pela equipe; anulada; documento conferido, ou que não conferiu, no balcão (#117); **pacote de prova exportado**,
  com o hash do ZIP (#115)) **não** entra no PDF, que não muda: fica na trilha e no certificado avulso do pacote de prova.
- **IP da equipe (#354).** Dono, 20/10: *"mostrar o IP do servidor de onde o sistema opera"*. Nos passos da equipe
  (convite enviado, PDF baixado, anulada, documento conferido, cópia reenviada, pacote exportado), desde 20/10 a trilha
  grava o **IP público do servidor** (a VPS, variável `CC_SERVER_IP` no `~/.urace/adminai.env`) e o aparelho
  "URACE Command Center (staff)"; o nome de quem fez continua. Os passos antigos não mudam (a cadeia não pode
  quebrar), mas no pacote de prova o certificado avulso e o `audit_logs.json` mostram o IP do servidor nas linhas da
  equipe; o `events.json` fica como foi gravado. O IP e o aparelho de **quem assina** não mudam: são a prova.
- **Onde ver:** Site › Waiver › Assinadas aqui › **Trilha** (gerente+): os passos de antes, a assinatura e
  o que veio depois, e se a trilha inteira está **íntegra** (cada passo leva o hash do anterior; uma linha
  mexida aparece como "trilha com linha mexida no evento #n").

#### Site › Waiver: pacote de prova para o advogado (#115)

Para defender a waiver num tribunal, o advogado precisa de uma explicação de **como** a assinatura foi parar no
documento e da declaração de quem guarda os registros (o **custodiante**: Italo Jorge da Silveira, decisão do dono de
06/10). O pacote de prova junta tudo num arquivo só.

- **Onde:** Site › Waiver › **Assinadas aqui** › no cartão da waiver, **Pacote de prova** (gerente ou acima; o
  operador não vê nem baixa). Baixa um ZIP `URACE-waiver-<n>-evidence.zip`. A anulada também tem pacote (a anulação
  vai junto). A waiver do DocuSign não tem: ela se prova pelo certificado do DocuSign.
- **O que vai no ZIP** (em inglês, porque é para o advogado e o tribunal):
  - `signed.pdf` (o PDF assinado e selado, exatamente o do servidor), `audit.json` (a trilha gravada na assinatura) e
    `waiver.json` (a linha da waiver e a anulação, se houver);
  - `events.json` e `events.csv`: a **Trilha** inteira, com o hash de cada passo refeito e a cadeia conferida;
  - `audit_logs.json`: o que a Auditoria tem da waiver e da conta (o cadastro e a confirmação do e-mail; login,
    código e leitura só da sessão desta assinatura, desde a assinatura anterior da conta e no máximo 24 h antes do
    primeiro passo; a assinatura; o cadastro do piloto desta waiver) ou do convite. **Nunca** vai senha, cookie, token,
    link do convite, corpo de e-mail ou caminho de pasta do servidor. A waiver do irmão não aparece no pacote desta;
  - `template.pdf` e `template.json`: a versão do modelo que valia (#116);
  - `timestamp.tst` e `timestamp.json` (o carimbo de tempo), `seal-cert.pem`, `seal-root.pem` e `tsa/tsa-root.pem`
    (os certificados **públicos**; a chave do selo nunca sai do servidor);
  - `certificate-of-completion.pdf`: o certificado avulso com **todos** os passos, inclusive os de depois de assinar
    (cópia por e-mail, documento conferido no balcão, PDF baixado, anulada);
  - `system-description.md`: a descrição do sistema (`docs/waiver-esign-system.md`), com o commit em execução;
  - `declaration-DRAFT.md`: a declaração (FRE 902(11)/(13) e Fla. Stat. §90.902(11)) já preenchida com os dados da
    waiver, marcada **"DRAFT — for attorney review — not to be signed"**. **Não assine:** o texto final é do advogado
    (ele também confirma o cargo do custodiante, o tribunal e a forma, declaração ou affidavit);
  - `VERIFY.md`, `verify_events.py` e `SHA256SUMS`: o passo a passo para conferir (o `sha256sum -c`, o Adobe ou o pyHanko, o
    `selo-waiver conferir` no servidor e o `openssl ts -verify` do carimbo) e o hash de cada arquivo.
- **O mesmo registro, na mesma versão do sistema (o commit), dá o mesmo ZIP**, byte a byte: baixar de novo sem nada
  ter mudado dá o mesmo hash. Por isso as exportações anteriores não entram no ZIP. Se algo mudou na waiver depois (uma
  cópia por e-mail, o balcão, a anulação), o ZIP novo traz isso e o hash muda; depois de uma atualização do sistema, a
  descrição do sistema e a declaração mudam e o hash do ZIP também (os registros, não).
- **A trilha é conferida contra o que foi gravado na assinatura**, não só contra ela mesma: se alguém mexer num passo
  direto no banco e refizer o hash dele, o pacote mostra **INTEGRITY WARNING** no topo do certificado avulso, no
  `VERIFY.md` e na declaração, com o passo que não bate (por exemplo "chain broken between #4 and #5"). O
  `verify_events.py` do pacote faz a mesma conferência no computador do advogado.
- **Fica registrado:** cada download vira o passo **pacote de prova exportado** na Trilha (com o hash do ZIP e quem
  baixou) e a Auditoria `waiver.evidence_export`.
- **Se o PDF no servidor não bater com o hash gravado na assinatura**, o pacote não sai (a tela mostra o erro):
  restaure o PDF da Biblioteca (o backup do Drive) e baixe de novo.
- **Para o advogado:** mande o ZIP inteiro, sem abrir nem mudar nada (mudar qualquer arquivo faz o `SHA256SUMS` não
  conferir). Pelo e-mail da empresa ou pasta compartilhada só com ele: o pacote tem dado do cliente.

### Um card por piloto

Dono, 01/10 (#65): **cada driver tem o seu card.** Irmãos costumam ter o mesmo responsável,
e-mail e telefone; mesmo assim, cada um tem o próprio card. O painel recusa unir cards ligados a
drivers diferentes do site ("Esses dois cards não se unem: são de drivers diferentes no site").

**Card de irmão** (#204, dono, 14/10: *"sim, é para criar um card de um irmão"*): o **+ Novo
cliente** com o e-mail do irmão abriria o card dele. Para o irmão, use **Clientes › + Novo cliente ›
"É irmão de um cliente? Criar card de irmão"** (ou, no card do irmão, **⋯ › + Card de irmão**):
em **"Irmão de — vincular ao cliente"** escolha o card que já existe, e escreva o piloto. O
responsável, o e-mail e o telefone vêm de lá. O card mostra **irmão(s)** no topo; os dois nunca se
unem (nem a sincronia, nem o Unir: "são irmãos: cada piloto tem o seu card"), e o serviço de um não
vai para o outro.

### Nunca pôr serviço de um cliente no card de outro

Dono, 22/09: *"Nunca colocar serviço de outro cliente em card de outro cliente."* Na dúvida, card
próprio. Para confirmar que é a mesma pessoa, use **e-mail, telefone ou responsável iguais**.
Primeiro nome parecido é só suspeita.

| Caso | O que fazer |
|---|---|
| serviço caiu no card errado | no card, aba Serviços › **Mover** (gerente+) e escolha o cliente certo |
| serviço que não devia estar no calendário | Calendário › no serviço, **Excluir** (gerente+ e acesso livre), com o motivo. Some do calendário, do balcão, dos contadores e dos avisos, e a IA não age mais nele. No card, aba Serviços, continua como **excluído** (quem, quando, por quê), com **Restaurar**. No Asana nada muda; a auditoria guarda `task.deleted` e `task.restored` (#219) |
| dois cards da mesma pessoa | Clientes › **⧉ Unir dois clientes**. Tudo do card que sai vai junto (serviços, waivers, e-mails, invoices, ligações, mensalidade, balcão, estoque, pedidos do site, Suits…); se algo falhar no meio, nada muda. O registro unido fica guardado e auditado |
| pares com nome quase igual | Clientes › **Possíveis duplicados**; dá para pedir o parecer da IA. A decisão é humana |

### "Vincular ao cliente" em toda inserção manual

Dono, 08/10 (#158): todo formulário que cria registro à mão tem o seletor de cliente. Ele grava o
vínculo e **puxa do cadastro** o que já existe (nome, e-mail, telefone, piloto, endereço,
medidas). Hoje o seletor aparece, por exemplo, em:

- **Suits** › Registrar novo pedido: "Vincular ao cliente (puxa os dados do cadastro)";
- **Oportunidades** › nova oportunidade: "Já é cliente? Vincular ao cliente";
- **Balcão**, **Estoque** e **Pedidos**: o cliente dono da peça, ou "para o kart de".

Regra prática: **antes de digitar dados de alguém, procure o card.** Se existir, vincule. Se não
existir, crie o cliente em Clientes › **+ Novo cliente** (o painel avisa quando ele já existe e
abre o card dele).

**Pelo Client ID (#430, dono, 28/10).** Toda busca de cliente também aceita o número do card: `621`,
`#621` ou `id 621`. Vale no filtro de **Clientes**, no seletor **Vincular ao cliente** (e no **Unir dois
clientes**), na busca de cima (**⌘K**: o card daquele número vem primeiro e o Enter abre) e no Claude
(`urace_clientes`). O número busca já com 1 dígito; o seletor mostra o `#número` de cada card.

---

## 6. Cada área, em poucas linhas

| Área | Em uma frase | Onde ir |
|---|---|---|
| **Vendas** | oportunidade por etapa, ligação registrada, retorno na agenda, fechamento numa tela só (cliente, invoice, waiver, Asana, Kommo) | [playbook-vendas.md](playbook-vendas.md) |
| **Box** | Meu dia, checklists com foto, balcão (cobrar ou guardar peça), estoque, pedidos e compras | [playbook-mecanicos-e-coaches.md](playbook-mecanicos-e-coaches.md) |
| **Suits · Alpha Line** | pedido de macacão sob medida, das 29 medidas e do design até a entrega, com a ponte de e-mail | [../suits-guia-do-lucas.md](../suits-guia-do-lucas.md) |
| **Corridas** | a coluna RACES do Asana; convidar os ★ Pro, que ficam na corrida até confirmar | tela Corridas |
| **Site** (#306) | uma seção só do site público no menu, com uma subseção por painel: o **Painel do site** (as métricas), os pedidos, os agendamentos, a agenda, os serviços e preços, os cartões, a loja e o **estoque do site**, o editor, o blog, as contas, a waiver e o security deposit | menu Site · esta seção, "Painel do site" |
| **Serviços e cartões do site** (#297, #312) | tudo o que o site mostra com preço sai do painel: o cartão de cada kart do Arrive and Drive (nome, linha de baixo, aviso, kart próprio, preço, depósito) e os cartões da Academy, do Pro Team e do For Beginners. Criar, mudar, esconder (não apaga) e reordenar; `{kart}` no preço é o menor preço de kart do painel, ao vivo — e o "Starting at" das outras páginas também. **Adicionar serviço**, em cima, começa por **"Em qual página do site?"** (Arrive and Drive, Academy, Pro Team, For Beginners ou Só na área do cliente) e, quando a página tem dois jeitos, **"Como ele entra na página?"**: no Arrive and Drive, **kart** (reserva online) ou **add-on do dia** (Lead and Follow); na Academy, **plano mensal** ou **cartão de preço**; no Pro Team e no For Beginners, cartão de preço. A tela mostra o que já está naquela página hoje (na Academy com plano ativo, os cartões aparecem como **escondidos pelo plano ativo**, porque a página mostra os planos); o kart que já tem serviço ativo aparece com o nome do serviço de hoje e não se escolhe de novo (dois serviços com o mesmo kart tiram o kart do site); com um add-on ativo, o segundo não se cria. A mesma trava vale no card de edição (o seletor **Kart do site** mostra o kart ocupado e não deixa escolher), no **Reativar** (travado, com o nome de quem já usa a chave) e no servidor: a API e o Claude recebem a recusa com o que fazer. Dois repetidos que já existam continuam editáveis, para dar para desativar um. Cada serviço da lista diz onde aparece hoje: **no site: Arrive and Drive · kart 4-stroke**, **Academy · plano mensal**, **só na área do cliente** ou, em vermelho, **fora do site** (com o motivo) | Site › Serviços e preços · Cartões das páginas |
| **Produtos da loja** (#298) | os produtos da loja do site ficam no banco e se mudam no painel: nome, preço e promoção, fotos (WebP sem a localização do celular), texto, opções, estoque e categorias. **Frete fixo por unidade** cobrado no Stripe com "Ship to me" (vazio = combinar à parte; 0 = grátis) e **depósito de segurança** por unidade. Esconder não apaga | Site › Produtos da loja · [playbook-vendas.md](playbook-vendas.md), seção 5.3 |
| **Estoque do site** (#309) | cada produto da loja é **dropshipping** (o padrão: o fornecedor envia e o site segue a caixa "Em estoque") ou **em estoque** (o box envia). Em estoque, o produto (ou cada tamanho) liga a **um item do Estoque**: um saldo só, o mesmo do Balcão, da contagem e de Compras, contado no Galpão e na Pista (o trailer fica fora). Sem saldo, o site mostra "Out of stock" sozinho; a venda paga no site **sai do estoque sozinha**; sem saldo na hora de pagar, o pagamento entra e o pedido vira **"Resolver: sem estoque"**. O cliente nunca vê o marcador nem a quantidade | Site › Estoque do site · [playbook-vendas.md](playbook-vendas.md), seção 5.3 |
| **Editor do site** (#300, #315) | a página do site abre numa prévia de verdade e é ali que se mexe, como no Canva: clicar seleciona, clicar de novo escreve no lugar, a barra em cima da peça muda o resto, arrastar move, a paleta põe título, texto, imagem, botão, lista, espaço, perguntas, e os karts, produtos e cartões do painel. Página nova ou uma que já existe (as faixas dela se movem, se escondem e têm o texto escrito no lugar, com preço, plano, kart e reserva travados porque vêm do painel); desfazer e refazer, Camadas para quem usa teclado, **?** com todos os atalhos, no computador em 390 ou 1280 px (reduzido para caber) e no celular com a peça sempre acima da barra de baixo, rascunho que salva sozinho, publicar conferindo as regras do site, versões para voltar | Site › Editor do site · seção 6, "Editor do site" |
| **Blog do site** (#172) | os artigos do `/blog/` ficam no banco e se escrevem no painel: título, categoria, endereço, resumo, o que o Google mostra, capa (WebP sem a localização do celular) e texto com títulos, listas, links e fotos, com prévia no visual do site. O operador escreve o rascunho; **só o ADMIN** (ou o acesso livre) publica e tira do ar. Cada publicação guarda uma versão | Site › Blog · seção 6, "Blog do site" |
| **Backup do banco** (#299) | todo dia: cópia conferida na VPS (03:15) e cópia cifrada no Google Drive (04:00), 30 dias + 1 por mês por 12 meses; aviso em Integrações quando falha ou falta | seção 10.1 |
| **Aluno recorrente** (#314) | Academy (Kart School) com plano: marca na área do cliente sem pagar a sessão do pacote do mês; acima do pacote, a **sessão extra** sai numa invoice do QuickBooks (mensal ÷ sessões ou o valor combinado, sem depósito). O cliente vê "Included in your plan" ou "Extra session" e, desde 19/10 (#340), o contador do mês (usadas, livres, mensalidade, extras, em aberto). A invoice das extras (e dos add-ons) sai na hora da marcação; o recorrente vê só o serviço do plano; o piloto pro nunca vai para o carrinho. Marca **vários dias num pedido** (até 12: "Every Wed", "This weekend"…), e as extras do pedido saem numa invoice só. **Cliente novo** paga no Stripe (carrinho) com o Stripe ligado; o carrinho recusa a sessão do aluno recorrente | [playbook-vendas.md](playbook-vendas.md), seção 5, "Aluno recorrente" |
| **Carrinho do site** (#236) | o cliente junta sessões da agenda e produtos da loja e paga tudo de uma vez no Stripe; a sessão entra paga em Site › Agendamentos e a venda entra GANHO em Vendas, com o pedido e as linhas | [playbook-vendas.md](playbook-vendas.md), seção 5.1 |
| **Loja do site** (#261) | `/store/` acha produto por texto, por código (SKU), por faixa de preço, ordenado e em páginas de 24, tudo resolvido no servidor (funciona sem JavaScript). Para mandar ao cliente, copie o link **do produto** (`/store/p/…/`), não o da busca | [playbook-vendas.md](playbook-vendas.md), seção 5.2 |
| **Página do pedido** (#245, #248) | cada resultado do Stripe tem a sua página no site (pago, processando, não passou, expirou), em inglês ou português, com os dados do cliente da conta; **sempre** um e-mail para o cliente, um aviso para `support@` e um registro na Linha do tempo do card ("Pagamento no site"), uma vez só; "Try again" e "Restore cart" recalculam preço e vaga. Toda compra no site pede a conta. A equipe vê e copia o link em Site › Pedidos do site | [playbook-vendas.md](playbook-vendas.md), seção 5.1 |
| **Waivers** | DocuSign: baixar PDF assinado, reenviar corrigindo e-mail, lixeira. Entregue não é assinada. **Convite por e-mail** para assinar no próprio sistema, do card do cliente. A assinada no próprio sistema não vai para a lixeira: o gerente **anula com motivo** (#109) | tela DocuSign · card › Waivers |
| **Gmail** | a IA marca e move 3 vezes ao dia; o que ela não decidiu fica aqui. Ela só usa marcador do manual confirmado | tela Gmail |
| **Financeiro** | invoices, lembretes e catálogo no QuickBooks. A conta é do **responsável**, nunca do piloto | tela QuickBooks (gerente+) |
| **Medição de campanha no site** (#260, #171) | o site público mede a campanha paga (Tag Manager, Analytics e pixel do Meta) **só depois do Accept no banner de cookies**; o painel e a área do cliente continuam sem script de fora | esta seção, abaixo |
| **Chat do site** (#170) | o balão do Kommo no site público; a conversa cai no Chat do Kommo | esta seção, abaixo |
| **Menu do site** (#394) | o menu em dropdown do site público (o da KartSport) e as animações do urace.us | esta seção, abaixo |

### Menu do site e as animações (#394)
Dono, 22/10: *"gosto do layout desse menu em dropdown ... incorpore no nosso site ... e tb coloque algumas animações
assim como tinhamos no urace.us"*. Em toda página do site:

| No topo | Abre (⌄) |
|---|---|
| **URACE Academy** | Academy · Racing Team · Arrive and Drive |
| **For Beginners** | Sim 2 Grid (a página do SIM2GRID) · Plan Your Career |
| **Store** | Engines · Chassis · Tires · Parts · Apparel · Suits — só a categoria que **tem produto** na loja; categoria vazia some do menu sozinha e volta quando um produto entra nela (Site › Produtos da loja) |
| **About** | About URACE · Blog · Contact us |
| ícones | **conta** (área do cliente), **busca da loja** (leva ao campo de busca da Store) e **carrinho** (com o número de itens) |
| **Book now** | o botão vermelho: a reserva do Arrive and Drive |

- **Computador:** o título leva à página do grupo; a setinha ⌄ abre a caixa com o mouse em cima, no clique ou no
  teclado (Tab até a setinha e Enter; Esc fecha). Sobre a foto do topo a barra é transparente; ao rolar, fica escura.
- **Celular:** o ☰ abre o menu em tela cheia; cada grupo abre e fecha no toque. Conta e busca da loja ficam no fim da lista.
- **Our Services** saiu do topo e continua no rodapé e nas páginas. Nenhum link de antes sumiu do site.
- **Powered by e parceiros** (#511): antes do rodapé, em toda página, a faixa do urace.us de 29/10 com o logo do
  Orlando Kart Center e os parceiros (ILX Group, AZ Car Rental, CANOTOPS e Allure Global Events), sem link. Parceiro que
  entra ou sai muda pelo desenvolvimento (`conteudo.PARCEIROS`, com o logo em `static/img`).
- **Animações:** botão sobe 2 px e cartão sobe 4 px com sombra (mouse em cima); as seções surgem ao rolar, uma vez;
  os campeões da Career são um carrossel no celular (arrastar ou as setas ‹ ›); o "Book now" pulsa de leve três vezes
  e para. Quem pediu ao celular/computador **menos movimento** (prefers-reduced-motion) vê tudo parado e à mostra.

### SIM2GRID: a hora de simulador (#392)

Dono, 22/10: *"na pagina do sim2grid eu preciso replicar essa lp ... ali dentro sera um serviço um diferente das
aulas de kart podendo agendar ate 5 pessoas para a mesma hora, o valor do serviço é cobrado por hora. monte assim
como montou o arrive and drive com todas as configurações ajustaveis"*.

- **A página** (#396, dono 23/10: *"imagina vc indo ao cinema na hora de construir ... tem que virar um point"*):
  `novo.urace.us/sim2grid-racing-simulator/` (o mesmo endereço do urace.us de hoje), feita para o celular como um app de
  cinema. A **1ª tela** é a foto do cockpit, uma frase e o botão; logo embaixo, a **reserva**: a faixa dos **dias** (rola
  para o lado, com a etiqueta do dia), os **horários** (a hora, o preço e uma bolinha verde por simulador livre), **Drivers
  − 1 +**, o atalho **Bring friends** (já com o máximo de pessoas) e o interruptor **With coach** (troca
  o formato sem coach ↔ com coach). A **barra preta fixa embaixo** mostra o dia, a hora, as pessoas, o total e **Book**: o
  dia aberto mais próximo já vem escolhido, então do topo são 3 toques até o carrinho (o dia, a hora, Book). O balão do
  chat e o banner de cookies sobem acima da barra. Depois da reserva, curto: os **programas mensais** num cartão, o
  caminho **Simulator → Arrive & Drive → Academy → Racing Team** numa linha e **5 perguntas** fechadas (o que inclui,
  preço, amigos, criança, cancelamento), com o endereço. No celular a página inteira cabe em ~4 telas (antes eram 13).
  **Vários horários de uma vez** (dono, 23/10: *"precisa permitir a multi seleção de horas"*): cada toque num horário
  põe ou tira aquela hora; horas **seguidas** viram uma sessão só, cobrada pela tarifa da hora de início (3 PM + 4 PM =
  uma sessão de 2 h), e horas **soltas** viram sessões separadas, cada uma com a sua tarifa. Não há mais o − / + de
  horas: as horas são os horários tocados, até o máximo de horas seguidas das Regras. No carrinho, uma linha por sessão e
  por pessoa.
  O menu (**Sim 2 Grid**), a página de programas (`/services/`) e a Career levam para ela.
- **Etiqueta do dia: dia de piloto × dia de diversão** (#396; Site › Sim2Grid, "Etiqueta do dia"): o selo que aparece no
  dia da faixa do calendário e no topo do dia escolhido, ex.: **🏁 Pilot day** (dia de treino) ou **🎮 Fun night** (noite
  de levar os amigos). Cada etiqueta tem **ícone** (um emoji), **rótulo** curto em inglês (até 24 letras), **quando**
  (**dias da semana** ou **uma data**), **de / até** (vazio = o dia todo; com horário, o ícone aparece só nas horas da
  faixa) e um **texto curto do dia** opcional (ex.: *Coaches on site*). A data vem antes do dia da semana. **Nasce vazia**:
  a equipe decide quais dias são de piloto e quais de diversão. Desativar tira do site e não apaga. Gerente e admin
  mudam; operador vê.
- **Formatos** são serviços de **Site › Serviços e preços** com o tipo **Hora de simulador (SIM2GRID)**: hoje, *sem
  coach* e *com coach*. Ali mudam o nome, o **nome no site**, a linha de baixo, o texto, o **depósito** (com
  "obrigatório") e o **item do QuickBooks**; desativar tira o formato da página. **Adicionar serviço → SIM2GRID →
  Formato da hora de simulador** cria um formato novo (as faixas dele vêm depois, em Site › Sim2Grid).
- **Faixas de preço** (Site › Sim2Grid): para cada formato, os **dias**, **de / até** (hora cheia; 24 = meia-noite) e o
  **US$ por hora**. Preço **vazio** = *"Call our team for options"*: o horário aparece, mas não se vende online. Vale a
  primeira faixa da lista que cobre o horário. **Vale o horário de início** (dono, 22/10): a hora final da faixa também
  serve de início (7h–17h aceita começar às 17h, pela tarifa diurna) e a sessão inteira sai pela tarifa do início.
  Desativar não apaga.
- **Regras**: **Simuladores** (pessoas na mesma hora, 5), **horas mínimas e máximas seguidas**, **mostra até** (dias),
  **antecedência**, **abre a partir de** (a inauguração, 01/11/2026), **datas fechadas**, **idade mínima** (vazio: o site
  não diz e pede para ligar antes de reservar para criança), **waiver obrigatória**, o **aviso** perto do botão e o texto
  do **sorteio do mês** (vazio: sem a caixa). **Vender online** desligado: a página mostra preços e telefone, sem botão.
- **Como a pessoa reserva**: dia → hora de início (cada hora mostra os simuladores livres em bolinhas) → quantas pessoas e
  quantas horas (−/+) → **Book** na barra de baixo → carrinho → conta → Stripe, o mesmo caminho do Arrive and Drive. **Cada pessoa é um simulador e uma
  linha do carrinho**, com o piloto dela (cada piloto no seu card). O preço é a soma das horas pela faixa de cada uma.
  O horário fica **segurado** enquanto o Checkout do Stripe vale (31 min); pago, vira **reserva paga** no card do piloto,
  com a venda **GANHO** em Vendas e, com a waiver ligada, a waiver do piloto. Se a hora encheu entre o checkout e o
  pagamento, a linha fica **sem vaga** no pedido (Precisa de atenção) para a equipe remarcar ou devolver.
- **Reservas** (Site › Sim2Grid, embaixo): as pagas e as que estão no pagamento, da mais próxima para a frente, com o card
  de cada piloto, o sorteio e a waiver. A hora de simulador **não** ocupa a agenda do kart (Disponibilidade).
- **Os programas mensais** (3x, 2x, 1x por semana) são cartões da página em **Cartões das páginas › SIM2GRID**; o botão
  abre o contato com o programa já escrito (assunto *SIM2GRID racing simulator*).

### Race the Winter 2027 (#505)

`novo.urace.us/winter/` é a página da temporada de inverno, com o texto do urace.us de hoje, capítulo a capítulo: a
janela (as cinco fases do inverno), o calendário (as sete provas, com filtro: casa, opcionais, a confirmar), o kart peça a
peça (as oito peças abrem uma a uma; "Part 8 of the kart" abre o capacete), o motor e o **localizador de categoria**
(data de nascimento → idade de corrida em 1º/01/2027 → as classes da SKUSA abertas), o formulário **Build your winter**
(cai em Vendas, playbook de vendas, seção 5), o pacote dentro e fora da pista e a **estimativa**:
a diária do kart de *Site › Serviços e preços* × os dias de teste que cabem na estadia (o resto é "quoted per event" ou
"quoted separately"). O que a página de hoje tinha e saiu: o circuito em 3D e os três vídeos curtos (moram no WordPress;
a vitória continua no link do Instagram). O que lá está escondido também não sai aqui ("We bring everything", a ficha da
temporada e o "Next step"). Sem JavaScript a página mostra tudo; com "menos movimento" nada se mexe.

### Painel do site (#306)

Dono, 16/10: *"uma sessão dedicada exclusiva somente para o site … uma seção com subseções de cada painel de lá …
E aí também do site um dashboard com as métricas dele"*.

**Onde:** no menu, a seção **Site**. A primeira subseção é o **Painel do site** (`/ops/site`); as outras são os painéis
que já existiam (pedidos, agendamentos, disponibilidade, serviços e preços, cartões, loja, estoque do site, editor, blog,
contas, waiver e security deposit), cada
um com o seu endereço (`/ops/site/pedidos`, `/ops/site/agendamentos`…). Os agendamentos, que eram `/ops/site`, agora
ficam em `/ops/site/agendamentos`.

**O que o painel mostra** (período de 7, 30 ou 90 dias, no horário da Flórida, comparado com o período anterior):

| Bloco | De onde vem |
|---|---|
| **Recebido pelo site** | os pedidos pagos no Stripe (loja e carrinho, com o depósito dentro), a mensalidade paga dos planos (nunca o contrato inteiro) e as sessões da área do cliente pagas pela invoice do QuickBooks |
| **Pedidos pagos** e **ticket médio** | os pedidos do site com o pagamento confirmado no período |
| **Conversão do pagamento** | de todos que foram ao Stripe no período (carrinho e Buy now), quantos pagaram |
| **Visitas** e **Visitas por dia** | contadas pelo próprio servidor, a cada página do site aberta por um navegador (robôs e bibliotecas não contam). **Sem IP, sem cookie, sem saber quem é**: só o endereço, o dia e de onde a pessoa entrou. A conta fica na memória e vai ao banco a cada 30 s. Quem volta a uma página em menos de 5 minutos vê a cópia do navegador, e essa não conta. Começa no dia do deploy do #306: enquanto o período anterior não foi medido inteiro, o painel diz "sem base" em vez de comparar |
| **Do carrinho ao pagamento** | abriram o carrinho → foram ao Stripe pelo carrinho → pagaram; o Buy now da loja (direto do produto ao Stripe) aparece à parte |
| **Produtos mais vendidos** e **Sessões vendidas no carrinho** | os itens dos pedidos pagos, pelo valor do item (sem o depósito que volta, o frete e o add-on); e os agendamentos do site e da área do cliente (marcados, cancelados, por vir) |
| **Páginas mais vistas** e **De onde as pessoas entraram** | as visitas; a entrada é a campanha (`utm_source`), o site ou o app que mandou (Google, Instagram, Gmail…) ou "direto". Navegar dentro do site e voltar do Stripe não é entrada nova. Passou de 40 fontes num dia, o resto entra como "outras fontes" |
| **Campanhas das vendas e dos contatos** | o `utm` que cada venda ou contato guardou, uma vez por venda (o agendamento e a oportunidade que um pedido gera não contam de novo) |
| **Contas e contatos** | as contas novas da área do cliente e as oportunidades com origem Site (ganhas e perdidas) |
| **Saúde do site** | as páginas servidas, os erros do servidor e a página mais lenta desde o último reinício |
| a faixa de **atenção** | qualquer que seja o período: dos últimos 30 dias, os pagos sem vaga ainda sem agendamento, os **pagos sem estoque** ainda não marcados **Resolvido** (#309) e os avisos por e-mail que não saíram (pago, processando, não passou, expirou e planos); e o que está aberto agora: agendamentos esperando e contas sem card ligado (a mesma conta de Contas de clientes) |

Número zerado é zero de verdade; o que ainda não tem dado diz "sem dado" (NO FAKE DATA). As vendas feitas pela equipe
(invoice do QuickBooks fora do site) estão em Vendas, não aqui.

### Endereço, remarcação e horário da pista no site (#527)

Dono, 30/10: *"não informe isso de cara assim, somente na confirmação de agendamento isso será passado"*; remarcação
*"48h"*; o horário da pista *"é regulado pelo command center"*.

- **Endereço:** as páginas, o rodapé, o schema do Google e a resposta automática do contato dizem só
  **10724 Cosmonaut Blvd, Orlando, FL 32824**, sem o Box.
- **O Box vai só no que o cliente recebe depois de marcar ou comprar:**
  - **Box 3**: o e-mail "You're confirmed" da sessão de kart e o e-mail de pagamento do carrinho com uma sessão
    marcada (linha "Where");
  - **Box 3**: a retirada da loja (e-mail e página do pedido);
  - **Box 5**: a hora de SIM2GRID paga.
  - Mudou o Box? Troque em `BOX`, no `vitrine/conteudo.py`.
- **Remarcação:** em todo o site é com **48 horas** de antecedência. Com menos que isso, há a taxa de US$ 95 (termos,
  FAQ da Academy, reembolso e a letra miúda das landings).
- **Horário da pista no formulário das landings:** a opção "A" diz os dias e os horários **abertos na agenda do painel**
  (Site › Disponibilidade: dias da semana, manhã e tarde, e os horários de cada período). Abriu ou fechou um período
  no painel, o formulário muda sozinho. Com nada aberto, a opção sai sem horário.

### Editor do site (#300, #315)

Dono, 16/10: *"no site público a gente tenha é, como alterar o design, layout, puxando e arrastando e soltando de uma
forma bem simples e conseguir editar por lá como se fosse realmente um WordPress"*. E depois, no mesmo dia (#315): *"o
editor do site ele abre uma mini visualização de como é o site público. E dali a pessoa consegue, por ali, clicar no que
ela precisa editar. Ela edita, ela puxa, ela arrasta, ela solta, ela insere alguma coisa com o mouse, por exemplo, usando
o mouse e teclado, sem precisar de preencher cards para aquilo ali. … É como se fosse um Canva."*

**Onde:** Site › **Editor do site** (`/ops/site/editor`; uma página: `/ops/site/editor/<n>`). Ver é do operador; criar,
mudar, publicar e voltar versão é do gerente (tudo na auditoria). O operador vê a prévia, as Camadas, a aba Página e a
ajuda dos atalhos, sem mudar nada. A aba do navegador diz o nome da página aberta (*Summer Camp · Editor do site*).

**Como ficou** (o #315 entrou em 5 partes, uma por PR):
1. **A lona e a seleção**: a prévia de verdade é a área de trabalho; clicar seleciona, a barra muda o resto, as Camadas
   substituem os cards, o rascunho salva sozinho e duas pessoas não apagam o que a outra fez.
2. **Texto no lugar e histórico**: escrever direto na prévia, colar limpo, foto por clique ou soltando o arquivo,
   desfazer e refazer, os atalhos.
3. **Arrastar e soltar**: na prévia, da paleta para a prévia e no celular (tocar e segurar, "toque onde quer pôr").
4. **O texto das faixas originais**: a página que já existia também se escreve no lugar, com o dado do painel travado,
   os textos órfãos e o preço escrito à mão como pendência.
5. **O fechamento**: o modo Computador reduzido para caber, a ajuda **?**, no celular a peça escolhida sempre acima da
   barra de baixo, o movimento da tela e o título da aba.

**A tela**
- No meio, a **prévia** (a lona): a página do site de verdade, desenhada do rascunho (o cabeçalho, o rodapé, as fotos, os
  preços do painel). É nela que se trabalha.
- No computador, **Celular** mostra a página com 390 px e **Computador** com 1280 px de verdade (o site muda de desenho
  como muda para quem visita), **reduzida para caber** na prévia. Reduzida, tudo continua no lugar: o clique, a barra, o
  arrastar e a linha azul caem onde o mouse está, e o contorno da seleção fica mais grosso para não sumir. A seleção
  tem um anel branco por dentro do azul, para aparecer também no fundo vermelho e no escuro.
- Do lado (no computador) ou nas folhas de baixo (no celular), três abas: **Inserir** (a paleta), **Camadas** (a página em
  lista) e **Página** (título da aba, descrição, endereço, pendências, versões e **Atalhos do teclado (?)**).
- Em cima: **← Páginas**, o nome da página, o estado (rascunho, no ar, no ar com mudanças), **salvo / salvando… / não
  salvou**, **↶ Desfazer** e **↷ Refazer**, **?** (a ajuda dos atalhos), Celular/Computador, as pendências e **Publicar**.

**Clicar, escrever e mudar (sem formulário)**
- **Clique** numa peça da prévia para selecionar: ela ganha o contorno azul e a **barra** aparece em cima dela (no celular, a
  barra fica presa embaixo da tela; veja "No celular"). Clique no fundo de uma seção para selecionar a seção. **Esc**
  sobe da peça para a seção e depois tira a seleção. A barra acompanha a peça quando a prévia rola; se a peça sai da
  prévia (rolou para cima ou para baixo), a barra fica na borda da prévia, à mão.
- **Clique de novo** (ou duplo clique, ou **Enter**, ou **Escrever** na barra) para **escrever no lugar**: o título, o
  texto, o texto do botão, os itens da lista (Enter cria o próximo), a pergunta e a resposta das perguntas frequentes e a
  legenda da foto. **Esc**, **Enter** (fora do texto longo) ou **Pronto** saem do texto. O que se cola vira texto limpo
  (só negrito, itálico, lista e link passam no texto longo). Escrever num texto que já existia não apaga os links nem as
  fotos que ele tinha.
- A **barra** muda o resto, com botões: no título, o **nível H1/H2/H3** (o H1 fica desligado quando a página já tem um),
  **tamanho P/M/G** (com o painel em inglês, S/M/L), **cor** (padrão, vermelho da marca, cinza suave) e **alinhamento**; no texto, também **negrito,
  itálico, lista e link** (marque o texto antes); no botão, **Cheio/Contorno** e **Link** (caminho do site como
  `/contact/`, `https://`, `tel:` ou `mailto:`); na imagem, **Trocar foto**, **Descrição** (obrigatória para publicar),
  **Legenda** e o formato; nas perguntas, **+ Pergunta / − Pergunta** (com a pergunta em edição, ela sai da edição para
  a prévia mostrar a lista nova; clique de novo para escrever); em produtos, a categoria e quantos; em cartões, a
  página. Em toda peça: **↑ ↓** (sobe e desce; no começo ou no fim da coluna passa para a seção vizinha), **← →** (muda de
  coluna), **Duplicar** e **Apagar**.
- Na **seção**: **fundo** (claro, escuro, vermelho, cinza), **espaço** P/M/G, **1, 2 ou 3 colunas** (no celular viram
  uma só), ↑ ↓, Duplicar e Apagar. Na **faixa original**: **Esconder/Mostrar** e ↑ ↓; no **texto da faixa
  original**, **Escrever** e **Voltar ao texto da página** (veja "O texto das faixas originais", abaixo).
- **Karts e preços**, **Produtos da loja** e **Cartões de uma página** vêm do painel e não se escrevem na prévia: a barra
  leva para **Serviços e preços**, **Produtos da loja** ou **Cartões das páginas**, onde se mudam (NO FAKE DATA, uma fonte
  só). Sem nada para mostrar, a prévia mostra um marcador tracejado dizendo de onde vem; no site, não aparece nada.
- Tamanho, cor e alinhamento são escolhas da paleta do site, não cores soltas: o contraste fica sempre legível.

**Arrastar, soltar e inserir**
- **No computador**: arraste uma peça da prévia para outro lugar (na mesma coluna, para a outra coluna ou para outra
  seção) e uma seção inteira para cima ou para baixo; a **linha azul** mostra onde vai cair e a prévia rola sozinha perto
  da borda (o cabeçalho do site, que fica preso em cima, conta como borda: parar em cima dele rola para cima, e a peça
  cai no que aparece logo embaixo dele, com a linha azul à vista). Ir com ↓ ou pelas Camadas até uma seção mais alta
  que a prévia mostra o começo dela, logo embaixo do cabeçalho. Arraste
  uma peça da aba **Inserir** até a prévia, ou **clique** nela para pôr logo depois do que está selecionado. Uma peça
  solta em cima de uma faixa original vira uma seção nova antes ou depois dela.
- **Fotos**: solte um arquivo do computador direto na prévia (vira uma imagem ali) ou em cima de uma imagem (troca a foto
  dela). A foto sobe em WebP de até 1600 px, sem a localização do celular; a barra da foto já abre a **descrição** para
  escrever.
- **Camadas** faz tudo isso com botões, para quem usa teclado ou leitor de tela: escolher (escolher de novo escreve),
  ↑ ↓ (desligados quando não há para onde ir), ← →, Esconder e Apagar. O foco fica na peça mesmo quando ela muda de
  coluna ou de seção. O leitor de tela ouve onde cada peça foi parar, e o mesmo aviso duas vezes seguidas também é lido.

**No celular** (e em tela de até 900 px)
- A prévia ocupa a largura toda; nada rola para o lado em 360 e 390 px e todo botão tem pelo menos 40 px.
- **Toque** para selecionar; a **barra fica presa embaixo**. A página **rola sozinha para a peça tocada ficar inteira
  acima da barra**, também quando a barra cresce (o balão do link, a descrição da foto, um aviso) e quando o teclado
  abre para escrever; uma peça mais alta que o espaço fica com o começo à vista.
- **Toque e segure** uma peça para arrastá-la. Para inserir, **+ Inserir**, toque na peça e **toque na página onde quer
  pôr** (Cancelar desiste). Sem tocar (teclado, ou mouse numa tela estreita), o botão do aviso, **Pôr depois do
  selecionado** (ou **Pôr no fim da página**, sem nada selecionado), põe a peça.
- As folhas de Inserir, Camadas e Página fecham com **Esc** ou no **✕**, e o foco volta para o botão que as abriu.

**Atalhos** — **?** (fora de um texto em edição; no teclado brasileiro também com AltGr) ou o botão **?** de cima abre a **ajuda dos atalhos**, com a lista
completa; **Esc**, **✕** ou **Entendi** fecham e o foco volta para onde estava (o Esc da ajuda não mexe na seleção).
- Com uma peça escolhida: **↑ ↓** a anterior e a próxima · **Enter** escreve (na seção, vai para a primeira peça) ·
  **Esc** sobe um nível · **Alt+↑ ↓** move · **Alt+← →** muda de coluna · **Ctrl+D** duplica · **Delete** (ou
  Backspace) apaga (a faixa original esconde).
- Escrevendo: **Esc** sai do texto · **Enter** sai do texto curto (no texto longo é parágrafo novo; na lista, o próximo
  item) · **Ctrl+B / I** negrito e itálico no texto longo · **Ctrl+K** link no texto marcado.
- Sempre: **Ctrl+Z** desfaz · **Ctrl+Shift+Z** (ou Ctrl+Y) refaz · **Ctrl+S** salva já · **Esc** fecha a folha do
  celular e cancela o "toque onde quer pôr". No Mac, ⌘ no lugar de Ctrl.
- Desfazer guarda até 100 passos; a digitação seguida no mesmo lugar é um passo só. Com a peça escolhida, o **Tab** chega
  na barra antes dos links da prévia; ali as setas não trocam a peça, e Duplicar, Apagar e ↑ ↓ deixam o foco na barra.
  ↓ nas peças diz o nome, o que ela mostra e onde está (seção, coluna, posição).

**Movimento**: a barra, as folhas e a ajuda entram com um esmaecer curto (só transparência e deslocamento, nas durações
padrão do painel); com **"reduzir movimento"** ligado no aparelho, nada se mexe, nem a rolagem suave da prévia.

**Página nova:** em **Adicionar página** (em cima da lista, #312) › **Nova página**, o título da aba e o endereço (ex.: `/summer-camp/`; vazio, sai do título). Ela já
nasce com um título nível 1 e um botão. O endereço não muda depois de publicada. Endereços do sistema (`/ops/`,
`/store/`, `/blog/`, `/cart/`, `/legal/`…) e de páginas que já existem não podem. Os artigos do blog não nascem aqui: são da tela **Site › Blog** (seção 6, "Blog do site"), sempre em
`/blog/<endereço>/`, e lá `category`, `page` e `img` são reservados (`/blog/category/…`, `/blog/page/…` e `/blog/img/…`
são caminhos do próprio blog).

**Página que já existe** (home, Arrive and Drive, Academy, Pro Team, For Beginners, Career, About, os serviços…): em
**Adicionar página › Abrir uma página do site**, as faixas dela viram **Faixa original 1, 2, 3…**. Elas continuam vivas (preço do painel,
agenda, cartões): movem, **escondem** (na prévia ficam apagadas, no site somem) e ganham seções novas entre elas. Sem
mexer, a página sai igual à de antes, byte a byte.

**O texto das faixas originais** (#315, etapa 4)
- O texto de dentro da faixa também se escreve no lugar: **clique** num título (H1, H2, H3), num parágrafo, num item de
  lista, numa pergunta ou resposta das perguntas frequentes, numa legenda ou no texto de um botão para selecionar (a barra
  diz **Texto da faixa original N**); **clique de novo** (ou **Enter**, ou **Escrever**) para escrever. Só texto (o que se
  cola vira uma linha), **até 400 letras**. **Desfazer** e **Refazer** valem como nos elementos; **Voltar ao texto da
  página** (na barra) desfaz a troca daquele texto. Nas Camadas, a faixa diz quantos textos foram trocados.
- O título, o nível e a ordem dos títulos não mudam: o H1 trocado continua sendo o H1 da página (as pendências contam
  ele; uma seção nova com outro H1 trava o Publicar). A pergunta frequente trocada também vai para o que o Google lê da
  página (os dados estruturados).
- **O que vem do painel fica travado** (NO FAKE DATA, uma fonte só): os **planos e cartões** (Academy, Pro Team, For
  Beginners e o título de cada grupo de planos), todo **preço** (o "From" dos cartões da home, o "From … per driver" e o
  "Investment", qualquer texto com `$`), a **reserva** do Arrive and Drive (os karts e a agenda), os **artigos do blog**
  da home, os **produtos da loja**, **formulários** e as palavras e nomes de **pessoas de verdade** (depoimentos e
  campeões). Na prévia o mouse mostra que não se escreve ali; clicar seleciona a faixa e a barra diz **de onde vem e onde
  se muda** (Serviços e preços, Cartões das páginas, Site › Blog, Produtos da loja). O servidor também recusa.
- **Texto órfão**: se a página do código mudar o texto que foi trocado (o time mudou o site), a troca não entra mais (o
  site mostra o texto novo do código) e vira pendência **"texto(s) órfão(s)"**. Em **Página**, **Descartar os textos
  órfãos** tira a troca; escreva de novo, se quiser, no texto novo.
- **Preço só do painel**: um texto escrito com preço (`$99`, `US$ 99`, `USD 99`, `99 dollars`), numa faixa original ou
  num título, texto, botão, lista ou pergunta, salva no rascunho mas vira pendência: *"O preço vem de Serviços e preços /
  Loja; escreva sem o valor"*. Os karts, produtos e cartões que mostram o preço do painel não contam.
- **Cada faixa tem a sua âncora** (o `id` ou o título dela), não a posição: quando o banco tira uma faixa da página (a
  home sem artigo no ar perde a faixa do blog), as outras continuam com as trocas e o "escondido" delas. A faixa que
  saiu aparece nas Camadas como **Faixa que saiu da página do código**, no mesmo lugar, e volta sozinha quando o dado
  volta; se ela tinha texto trocado, ele vira texto órfão até voltar ou ser descartado.
- O que o Google lê da página (os dados estruturados) segue o texto trocado da pergunta frequente e do H1 (o nome do
  serviço e o da trilha); um parágrafo igual em outra faixa, ou o texto de cima do H1, não mexe nisso.

**Rascunho, salvar e publicar**
- Tudo **salva sozinho no rascunho** ("salvando…" vira "salvo"); a prévia troca só a seção que mudou, sem recarregar.
  Ninguém de fora vê o rascunho. O meio do caminho salva (um título vazio, um botão ainda sem link); o que não pode ir
  para o ar aparece nas **pendências**.
- **Duas pessoas na mesma página**: se outra pessoa (ou outra aba) salvou antes, a tela para de salvar e avisa
  **"Outra pessoa salvou esta página"**, com **Recarregar**. Nada do que a outra fez é apagado. Vale também para
  **Voltar a esta versão**: a tela que ficou para trás não troca o rascunho da outra pessoa pela versão antiga.
- **Não salvou** (internet caiu, link que não vale): a tela avisa, com **Tentar de novo**, e o **Publicar fica parado**.
  Publicar só funciona com tudo salvo, sem erro e sem pendência: o que vai para o ar é sempre o que a tela mostra.
- As **pendências** (o número ao lado de Publicar e a aba **Página**) dizem o que falta:
  - um título nível 1 só;
  - título sem pular nível (depois do nível 1 vem o 2; os cartões de karts e planos já têm o nível 3 dentro);
  - nenhum título vazio, botão com texto e link, pergunta com a resposta;
  - imagem com a foto e com a descrição;
  - nenhum texto órfão nas faixas originais (a página do código mudou: descarte em Página);
  - nenhum preço escrito à mão (o preço vem de Serviços e preços ou da Loja);
  - título da aba de 10 a 70 letras e descrição de 50 a 170.
- Cada publicação vira uma **versão**: em Página › **Versões publicadas**, **Voltar a esta versão** traz uma antiga para o
  rascunho (e tira os erros do rascunho de antes). Confira e publique de novo. Com o salvar ainda em andamento, a tela
  pede para tentar de novo em um instante.
- **Voltar ao original** (página que já existia) tira o editor do ar e o site volta à página de sempre. **Tirar do ar**
  (página nova) tira a página. O rascunho e as versões ficam. **Recarregar a prévia** (em Página) desenha a prévia de novo.
- A prévia fica fora do Google e sem medição (quem edita não conta como visita do site).

### Blog do site (#172)

Pedido na issue #172, e dono, 16/10: *"editor do blog, pode seguir"*. Os artigos do blog do site (`/blog/`) passaram do
arquivo para o banco **sem mudar o endereço**: os 7 que vieram do WordPress continuam em `/blog/<o mesmo endereço>/`,
iguais, e os endereços antigos do urace.us (`/<artigo>/`, `/category/<categoria>/`) continuam levando a eles.

**Onde:** Site › **Blog** (`/ops/site/blog`). Cada artigo abre no próprio endereço (`/ops/site/blog/<n>`).

**Quem faz o quê**

| | Operador e gerente | ADMIN ou acesso livre |
|---|---|---|
| ver, criar, escrever, subir capa e fotos, salvar o rascunho, voltar uma versão para o rascunho | sim | sim |
| **publicar** e **tirar do ar** | não (salve o rascunho e avise o administrador) | sim |

Tudo vai para a auditoria: `blog.post.create`, `update`, `photo`, `publish`, `unpublish` e `restore` (só o nome dos campos
mudados; o texto do artigo não vai para o log).

**Escrever**
1. Em cima, **Novo artigo**: o título (em inglês, o leitor lê) e a categoria → **Criar e abrir**. Nasce como **rascunho**,
   fora do ar.
2. No artigo: **Título do artigo** (o título grande da página), **Categoria** (Getting Started, Kart Setup, Racing Gear ou
   Training & Racing), **Endereço** (sai do título; dá para mudar até a primeira publicação), **Resumo** (o texto do cartão
   no blog, até 400 letras), **Descrição para o Google** (50 a 155 letras, o texto embaixo do título no Google) e, se quiser,
   **Título para o Google** (até 70; vazio, vale o título do artigo).
3. **Capa:** **Subir a capa** (sai WebP de até 1600 px, sem a localização do celular, com o tamanho de verdade) e a
   **Descrição da capa** (o que a foto mostra; é obrigatória para publicar uma capa subida aqui). Foto de até
   **60 megapixels** (a de 48–50 MP de um celular passa); acima disso a tela diz "foto com pixels demais": diminua e
   suba de novo.
4. **Texto:** negrito, itálico, lista, subtítulo, parágrafo, **Link** (`https://…`, uma página do site como `/academy/`,
   a home `/`, `mailto:` ou `tel:`) e **Imagem** (sobe a foto e põe onde o cursor está, pedindo a descrição). **Enter**
   abre um parágrafo novo, e o texto **colado** de uma página chega com os parágrafos separados. Tabelas e citações que
   já estão no texto ficam como estão (a tabela de preços do artigo "Getting Started in Kart Racing" é uma delas).
   Script, `onerror`, `javascript:` e companhia somem ao salvar. O texto vai até 60.000 caracteres, contando a formatação.
5. **Salvar rascunho.** A **Prévia** mostra o rascunho salvo no visual do site, em **Celular** (390 px) ou **Computador**,
   fora do Google. Ninguém de fora vê o rascunho.

**Publicar (ADMIN)**
- **Publicar** confere antes: título, descrição para o Google de 50 a 155 letras, texto, categoria e a descrição da capa
  subida. Enquanto faltar algo, a lista **Antes de publicar, falta** diz o quê e o botão fica parado. Salve o rascunho
  antes (o botão espera).
- **Só vai ao ar o que você viu.** Se alguém salvou outro texto depois que você abriu o artigo, **Publicar** não publica:
  a tela avisa "O rascunho mudou depois que você abriu o artigo", recarrega o texto e a prévia, e você confere e clica
  **Publicar** de novo.
- Publicado, o artigo entra **na hora**, no servidor, no blog, na categoria, na home (os 3 mais novos), no **mapa do site**
  (`/sitemap.xml`) e no **JSON-LD** (com a data de publicação e a da última mudança, `dateModified`). Sem nenhum artigo no
  ar, a faixa do blog ("Read before you race") some da home.
- **"Na hora" vale para o servidor.** Quem já abriu a página guarda a cópia no navegador **até 5 minutos**; o mapa do site
  fica **até 24 horas** no cache (do navegador e de quem o lê, como o Google). Publicou e não viu? Espere ou recarregue.
- **O endereço trava na primeira publicação** e não destrava ao tirar do ar: o Google e quem salvou o link já têm ele.
- Mudou um artigo que está no ar? O cartão mostra **mudado depois de publicar**: o site continua com o que está no ar até
  **Publicar as mudanças**.
- Cada publicação guarda uma **versão**. Em **Versões publicadas**, **Voltar a esta versão** traz uma antiga para o
  rascunho (o site não muda até publicar de novo). Os 7 do site antigo já têm a versão **original** ("site antigo", com
  a data de lá): o texto do WordPress sempre pode voltar.

**Tirar do ar (ADMIN)**
- **Tirar do ar** faz o endereço dar **404** e tira o artigo do blog, da categoria e do mapa do site. O rascunho, o
  endereço e as versões ficam.
- Os **7 artigos que vieram do site antigo** já estão no Google: a tela pergunta antes, com esse aviso. Prefira corrigir e
  publicar de novo a tirar do ar.
- Categoria sem nenhum artigo no ar sai do mapa do site e do menu de categorias; o endereço dela continua abrindo, com
  "No articles here yet".

**Bom saber**
- O artigo "Getting Started in Kart Racing" tem os preços **escritos à mão** na tabela ($719, $819, $899, $500). Mudou o
  preço em Site › Serviços e preços? Mude a tabela do artigo também.
- As capas e fotos do blog ficam na mesma pasta das fotos do editor do site (`~/.urace/site-fotos`), que o backup do banco
  não copia (seção 10.1).

### Vigia do urace.us até a troca do DNS (#529)

Dono, 30/10: *"monitore o que for alterado lá, muita gente mexe"*. Até a troca do DNS, o urace.us de hoje (WordPress)
continua sendo editado. O que mudar lá precisa vir para o site novo, senão se perde na troca.

- **Como funciona:** o workflow **Vigia do urace.us** (GitHub › Actions) roda a cada 3 horas. Ele lê a data de
  alteração das páginas, posts e produtos (a API pública do WordPress; nenhuma senha) e compara com
  `docs/site-publico/urace-us-conferido.json`, o que já foi trazido.
- **Mudou alguma coisa:** abre a issue **"urace.us mudou: trazer para o site novo"**, com cada página nova, mudada ou
  que saiu do ar, e a hora (GMT). Se essa issue já está aberta, comenta nela, sem repetir o que já avisou.
- **Trouxe a mudança:** no mesmo PR, rode `python -m command_center.vitrine.vigia_urace_us --conferir`, comite o
  `urace-us-conferido.json` e feche a issue.
- **Pilotos e depoimentos ficam de fora:** o endereço tem o nome da pessoa, e o repositório é público.
- **Depois da troca do DNS:** o workflow sai, porque o urace.us passa a ser o site novo.

### Medição de campanha no site (#260)

Dono, 15/10, para *"o site novo não tem GTM, Analytics nem pixel do Meta — campanha paga fica cega;
ponho os mesmos ids do site antigo?"*: **"sim pfvr"**. É o que mede quanto cada anúncio vendeu.

- **O que entra:** o **Google Tag Manager** `GTM-59CCNDC` (o Analytics entra por dentro dele) e o
  **pixel do Meta** `380948601336488` — os mesmos ids que o `urace.us` de hoje publica.
- **Os ids não estão no código.** Eles ficam em `~/.urace/adminai.env` na VPS, em `SITE_GTM_ID` e
  `SITE_META_PIXEL_ID`. **Sem a variável, nada carrega**: nenhum script, nenhuma requisição ao
  Google ou ao Meta, e o site funciona igual. Id com formato errado também não carrega.
- **Onde a medição entra:** só nas **páginas públicas** — início, serviços, Academy, Pro Team,
  iniciantes, carreira, sobre, acessibilidade, blog, loja, página de produto, contato, 404 — e na
  página de obrigado do pagamento (é o único lugar que sabe que o pagamento deu certo).
- **Onde NÃO entra:** no **painel** (`/ops`) e na **área do cliente** (`/ops/portal`), em `/cart/`
  (mostra o nome e o e-mail de quem está conectado) e no link pessoal do pedido (`/order/<token>/`).
- **O que é medido:** página vista, `add_to_cart` (loja e agenda) e `purchase` no pedido pago, com
  **valor, moeda, número do pedido e o item do catálogo**. **Nunca** nome, e-mail, telefone,
  endereço, medida ou piloto — nem no `dataLayer`, nem em endereço. Isso tem teste travando
  (`command_center/tests/test_medicao.py`).
- **De onde veio o contato:** o formulário de contato e o de pedido da loja gravam a campanha
  (`utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, `gclid`, `fbclid`, `fbp`,
  `fbc`, `campaign_id`, `adset_id`) junto com a mensagem. Quem vende vê isso em **Vendas › a
  oportunidade › "De onde veio"**.
- **Banner de cookies** (#171, dono 15/10: *"Sim, banner simples"*): na primeira visita o site
  mostra, embaixo, *"We use cookies to measure our ads…"* com **Decline** e **Accept**. **Antes do
  Accept nada do Google nem do Meta carrega** (nem o Tag Manager, nem o pixel). Accept liga a
  medição; Decline deixa desligada. A escolha vale 180 dias (cookie `urace_consent`). O link
  **Cookie settings**, no rodapé, abre o banner de novo para mudar de ideia.

### Chat do site (Kommo, #170)

- O balão de chat do site é o **mesmo widget do Kommo** do `urace.us` de hoje: a conversa cai no
  Kommo como lead, como sempre, e aparece no **Chat do Kommo** do painel (`/ops/crm/chat`).
- O chat **não depende** do banner de cookies: é atendimento, não medição de anúncio.
- O id e o hash do widget ficam em `~/.urace/adminai.env` na VPS, em `SITE_KOMMO_ID` e
  `SITE_KOMMO_HASH`. **Sem as variáveis, o balão não aparece** e o site funciona igual.
- O chat aparece nas páginas públicas; **não** aparece no painel, na área do cliente, em `/cart/`
  nem no link pessoal do pedido.
- O balão fica **no canto inferior direito** da tela (#293, dono 16/10), não onde o Kommo põe por padrão.
- Enquanto o banner de cookies está aberto, o balão do chat fica **acima** dele; fechado o banner, ele
  volta ao canto (#284). Para o balão ter forma, o site libera **estilo** inline quando o chat está
  ligado — script inline continua proibido.

### Suits: os grupos do ateliê no WhatsApp (#383)

- **Suits › WhatsApp** (`/ops/suits/whatsapp`): o estado da ligação com os grupos "Macacão design Urace" e
  "Urace Suits - Usman", os **rascunhos para aprovar** de todos os pedidos e as mensagens **sem pedido**
  (ou que podem ser de mais de um), para ligar ao pedido certo pelo número.
- No pedido, a seção **WhatsApp do ateliê**: as mensagens dos grupos com os arquivos, os rascunhos com
  **Aprovar e enviar** (o texto pode ser corrigido), **Escrever no grupo** (sai na hora), **Usar como foto do suit**
  (vira a foto da etapa Photos received), **Mandar o endereço ao fornecedor** (só em Checked; move para Address sent)
  e **Gravar rastreio**.
- Na lista de pedidos, a etiqueta **WhatsApp para aprovar** mostra quantos rascunhos esperam.
- Ao designer, sempre rascunho (#382). Ao fornecedor, segue a chave **envio automático** da ponte (desligada = rascunho); pedido de teste nunca manda; e nada sai
  antes de `WA_GRUPOS_APLICAR=1` na VPS. Cobrança: uma por dia por pedido e por grupo, das 09h às 18h.

Detalhe e rotinas no [guia de Suits](../suits-guia-do-lucas.md).

### Suits: duas novidades

- **"Não é pedido de suit"**: botão no pedido para **descartar** o que não é pedido de macacão
  (fatura, newsletter, conversa com fornecedor...). Nada é apagado: o pedido sai das listas, a
  ponte para de ler aquela conversa, e dá para **restaurar**.
- **Chave "IA neste pedido"** (#198, 13/10): liga e desliga a IA só
  naquele pedido. Desligada, a IA não responde, não manda e-mail e não mexe no pedido; o e-mail
  que chegar aparece como "Precisa de alguém da equipe" e quem responde é a equipe. Use quando o
  cliente pede atendimento humano ou a negociação está delicada.

### Suits: as travas do fluxo (#382, 22/10)

- **Produção só com a aprovação final escrita do cliente** (vale por e-mail), amarrada à arte final marcada e às
  medidas conferidas. Mudou a arte ou uma medida, a aprovação cai e o pedido volta para revisão.
- **Medidas** com estado: preenchida, conferida ou suspeita. Suspeita ou não conferida trava a aprovação.
- **Designer passa por uma pessoa**: a IA prepara o e-mail; quem é operador ou acima clica **Enviar ao designer**.
- **Entrega direta ao cliente**: aceito pelo fornecedor → em produção → **fotos recebidas** (a equipe sobe as fotos do
  WhatsApp como nota) → **conferido** (OK da equipe, exige foto) → **endereço enviado ao fornecedor** → em trânsito
  (com rastreio) → entregue. O endereço nunca vai ao designer nem no pedido de produção.
- **Pedido de teste** e **IA desligada desde o início**: duas caixas no Registrar novo pedido.
- O topo da aba mostra a **saúde da ponte** (última rodada, erros, simulação); cada pedido, a próxima ação esperada.

Detalhe e rotinas no [guia de Suits](../suits-guia-do-lucas.md).

---

## 7. A IA no painel

### Onde falar com a IA

| Lugar | Como |
|---|---|
| **AI Command** (`/ops/ai`) | uma conversa contínua, por pessoa. Enter envia; Shift+Enter quebra a linha; microfone dita; **Ouvir** lê a resposta |
| **✦ Instruir a IA** | em cada item de **Precisa de atenção**. Dá para marcar "guardar na memória da IA" |
| **⌘K** | a busca de cima também pergunta à IA |
| dentro de uma oportunidade, de uma tarefa do Asana ou de um pedido de Suits | a caixa da IA age só naquele registro |

Mandar comando à IA exige papel de operador ou acima.

### O que a IA faz sozinha e o que espera você

| Tipo | Exemplos | O que acontece |
|---|---|---|
| **Ler** | QuickBooks, Asana, Gmail, DocuSign, Kommo, o painel, a web, o cérebro da empresa | faz direto |
| **Trabalho interno** | tarefa, comentário e seção no Asana; cliente, item, invoice e estimate no QuickBooks **sem enviar**; rascunho de e-mail; marcador no Gmail; **operar o painel** (#420): editar o card do cliente (responsável, piloto, nascimento, e-mail, telefone, status, notas), estoque, compras, agenda, checklists, Suits, vendas | faz direto e registra como ação feita |
| **Sai da empresa ou não volta atrás** | enviar invoice, lembrete de invoice já paga ou e-mail; apagar; anular; unir cards; mudar preço do catálogo; pagamento; recorrência | **não executa**: vira um "aprovar" de um clique em **Aprovações** |
| **Bloqueado pela política** | o que estiver como `BLOCKED` em Políticas da IA | não roda, nem com aprovação |

A **waiver** é a exceção que o dono abriu: enquanto a política dela estiver em "sozinha" (SAFE),
ela sai na hora. O **convite da waiver por e-mail** (`painel_waiver_convite`, #135) **não** é
exceção: pela IA ele espera o aprovar; pelo painel, é o clique de quem manda (com a confirmação). A política de cada ação está em **Políticas da IA** (administrador muda) e em
**O que a IA pode fazer** (todos veem). **Não decore**: a política pode mudar; confira lá.

O **lembrete de invoice** também sai sozinho (dono, 14/10, #230): quando a IA manda o lembrete e o
QuickBooks, lido na hora, mostra a invoice **em aberto** (com saldo), o lembrete vai sem clique, e o
painel marca o próximo dia. Se a invoice já está paga, se não há como conferir ou se a política do
lembrete foi apertada em Políticas da IA, volta o clique.

**A IA opera o painel inteiro (#420, dono, 28/10: *"ela tem autonomia para fazer tudo ali dentro, não é só
ler"*).** No AI Command ela usa a **mesma rota do botão**, **como a pessoa que pediu**: o papel e o cargo de
quem pediu valem (a IA de um operador não faz o que é do gerente), a tela valida igual (ex.: o e-mail de outro
card é recusado) e a auditoria sai no nome da pessoa. Editar e organizar rodam na hora; o que **sai para fora,
cobra ou apaga** no painel (invoice, waiver, e-mail, Kommo, Asana, mensalidade, lixeira) vira o **aprovar** de
um clique, e quem aprova executa com o papel dele. Login, chaves, o **cofre** e a área do cliente ficam fora;
**atualizar o servidor** pela IA também pede o clique (#438). Também viram o clique (29/10) o que a regra do
módulo reserva a uma pessoa: **ligar** pelo Dialpad, escrever ou aprovar rascunho nos **grupos do WhatsApp do
ateliê**, **ligar conta ou driver do site ao card**, registrar à mão a **aprovação final do macacão**, **conferir
medida** e mover o macacão para fotos recebidas, conferido ou endereço enviado. **Aprovar ou recusar o que a IA
propõe e mudar Políticas da IA a IA nunca faz**, nem com o clique: é de você, na tela. Para desligar,
ponha `painel_api` em `BLOCKED` em Políticas da IA. Rotina automática (sem pessoa por trás) continua só lendo o painel.

Ação proposta com ferramenta que não existe, com campo que a ferramenta não aceita ou sem o campo obrigatório
**não vira cartão** (29/10): a IA recebe o motivo e corrige, e a conversa mostra "recusada" com o porquê.

Ação que não tem política própria pede confirmação. Qualquer ação com "apagar", "excluir",
"remover" no nome tem, no mínimo, a política de "apagar qualquer coisa": o sistema erra para o
lado de perguntar.

### Quem aprova

| Papel | Decide |
|---|---|
| Acesso livre, administrador, gerente | tudo |
| Operador | o que é dos módulos dele (inclui vendas). **Invoice e QuickBooks, não** |
| Leitura | nada |

Aprovar executa na hora e fica na auditoria. Recusar registra o motivo.

### "Falta completar" (pedido incompleto)

Dono, 12/10 (#185): a IA **não trava** por falta de informação.

1. Procura antes: painel, QuickBooks, Kommo, Gmail e o cérebro.
2. **Cria com o que tem** e deixa a lacuna visível no próprio registro ("horário: a confirmar").
   Nunca inventa o que falta.
3. Registra uma **pendência**: o que criou, onde está, o que falta e o contato que achou.
4. Avisa você: "Criei X. Falta: A, B. Contato para pedir: …".
5. A pendência aparece no topo do **AI Command** ("Falta completar") e em **Precisa de atenção**,
   e você recebe aviso no celular às 09:00 e 16:00 até completar.
6. Mande o dado na conversa ou complete no registro e toque em **Completei**. E-mail, telefone,
   nome ou nascimento do piloto **fecham sozinhos** quando alguém preenche o card.

A IA só para sem criar quando criar causaria dano: cobrar ou enviar sem o valor ou o
destinatário certo, ou quando não dá para saber de quem é o pedido.

### Para ligar o aviso no celular

**Equipe** › **Ligar notificação neste aparelho**. No iPhone, antes, instale o painel na tela
inicial (Compartilhar › Adicionar à Tela de Início) e abra por esse ícone.

---

## 8. Operar pelo Claude (MCP)

Cada pessoa pode ligar o **próprio** Claude ao painel. O Claude passa a agir **como você**, com o
**seu** papel, e tudo fica na auditoria com o seu nome. O passo a passo também está no painel, em
**Equipe › Conectar o Claude**. Detalhe em [command-center-mcp-operar.md](../command-center-mcp-operar.md).

### Conectar (uma vez)

**No app do Claude (claude.ai, celular ou computador):**

1. Configurações › **Conectores** › **Adicionar conector personalizado**.
2. Nome: `URACE Command Center`. URL: `https://ops.urace.us/ops/mcp`
3. **Conectar**, entre com o **seu** usuário do painel, marque
   **"Também operar o painel como você"** se quiser que ele opere (desde 21/10 a caixa vem desmarcada:
   sem marcar, o acesso é só de leitura) e clique em **Autorizar**.

**No terminal (Claude Code):**

```
claude mcp add --transport http urace https://ops.urace.us/ops/mcp
```

Depois, no Claude Code, digite `/mcp`, escolha **urace** e **Authenticate**. Entre e marque
**"Também operar o painel como você"**.

Sem a caixa marcada, o Claude **só lê**. Ninguém copia senha, token ou chave para o chat: o login
é pelo navegador.

### Leitura ou Operar: por quê (#362)

São **duas travas separadas**, e o conector só opera com as duas abertas:

1. **O seu papel** no painel: OPERATOR, MANAGER e ADMIN podem operar; VIEWER só lê.
2. **O que o conector recebeu** quando você clicou em **Autorizar**: com a caixa
   **"Também operar o painel como você"** marcada, operar; sem ela, só leitura.

Em **Equipe › Conectar o Claude** aparece **"Seu papel: X"** e a lista **Seus conectores**: cada
conector que você autorizou (Claude, ChatGPT…), com **Leitura** ou **Operar**, a data e o motivo.
Só os seus; token e segredo nunca aparecem. O `urace_operacoes` devolve o mesmo, separado em
`papel_permite_operar`, `conector_permite_operar`, `opera` e `por_que`.

| Situação | O que fazer |
|---|---|
| Papel ADMIN (ou OPERATOR/MANAGER), conector **Leitura** | No app do Claude ou ChatGPT, desconecte o conector e conecte de novo marcando **"Também operar o painel como você"** |
| Papel VIEWER | Peça a um ADMIN que mude o seu papel para OPERATOR ou acima (tela **Usuários**); depois conecte de novo marcando a caixa |
| Papel que opera e conector **Operar** | Já opera: o que vai para o cliente ou cobra pede confirmação antes |

### As ferramentas

| Ferramenta | Para quê |
|---|---|
| `urace_resumo` | o panorama |
| `urace_atencao` | o que precisa de gente hoje |
| `urace_clientes`, `urace_cliente`, `urace_corridas`, `urace_estoque`, `urace_invoices`, `urace_precos_cobrados`, `urace_auditoria`, `urace_kommo_*` | leituras prontas |
| `urace_cliente_reservas`, `urace_cliente_pedidos`, `urace_cliente_pagamentos` | **diagnóstico de um cliente pelo card**: pedem o `client_id` (número do card) e só trazem as linhas dele (agendamentos e corridas; loja, planos e Suits; invoices, mensalidades, peças, Stripe e reembolso do depósito), paginadas com `limit` (padrão 20, teto 100), `offset` e `total`. Cada linha traz o `client_id` do card e `atualizado_em` (#372), para conferir uma por uma. `urace_invoices` e `urace_corridas` também aceitam `client_id` e paginam com `limit`/`offset` + `total` (#374). `urace_resumo` mostra a versão do servidor e a última sincronia de cada integração |
| `urace_operacoes` | lista **as operações que o seu papel alcança**. Filtre com uma palavra: `venda`, `waiver`, `invoice`, `suits`... |
| `urace_api` | executa uma operação (método, caminho, corpo). É a **mesma rota** do botão do painel |

### Confirmação antes de mandar para fora

O que vai para o cliente ou cobra (invoice, waiver, depósito, e-mail, QuickBooks, DocuSign, Asana,
Kommo — inclusive o chat do Kommo em `/crm/…`: responder, anotar, etapa, tags —, agendamento do
site) **não acontece na primeira chamada**. O painel devolve `precisa_confirmar`
com o que vai fazer e um código de `aprovacao`. O Claude mostra para você e só repete com
`confirmar: true` e esse código depois do seu "pode mandar". A prévia traz um código de `aprovacao` (#378): ele vale só para aquele pedido exato, por 15 min e uma vez. Mudou destinatário, valor ou caminho, o código não serve; repetir a mesma chamada devolve o resultado da primeira, sem executar de novo.

Ficam fora do MCP: login, senha e chaves (`/ops/api/auth/*`) e a área do cliente
(`/ops/api/portal/*`).

---

## 9. Regras que nunca mudam

Regras do dono. Valem para pessoa e para IA, em toda tela e em todo canal.

1. **Não destruir dados.** Não apagar banco, cliente ou registro. O que não serve é **ocultado**,
   **descartado** ou vai para a **lixeira**, sempre reversível. Risco real de perda ou de sistema
   fora do ar: pedir autorização antes.
2. **Nunca pedir nem mandar senha, token, PIN ou chave pelo chat.** O login é pelo navegador.
3. **Segredo nunca no código nem no repositório.**
4. **Nunca pôr serviço de um cliente no card de outro.** Na dúvida, card próprio.
5. **NO FAKE DATA.** Nunca inventar nome, e-mail, telefone, valor, data, id ou link. Faltou:
   procure; não achou, diga que não achou e pergunte.
6. **Não usar Turo nem Hostaway** para nada.
7. **Tudo no fuso da Flórida** (America/New_York).
8. **Na dúvida, perguntar.** A pergunta não trava o resto: o item fica em espera e o trabalho
   segue. Item em espera com prazo chegando volta a ser alertado.
9. **Inserção manual sempre com "Vincular ao cliente".**
10. **O que sai da empresa passa por uma pessoa**, conforme a política da ação.

---

## 10. Quando algo dá errado

| Sintoma (o que aparece) | O que quer dizer | O que fazer |
|---|---|---|
| "Esta área não é do seu acesso" / "Ela exige acesso de … ou acima" | a tela pede um papel acima do seu | peça a quem tem o papel, ou fale com o administrador |
| "Ela não faz parte do acesso do box" | mecânico/coach fora das telas do box | use as telas do box; se precisa de outra, fale com o administrador |
| "You don't have permission to do this." | a ação pede um papel acima do seu | peça a um gerente ou administrador |
| "Your session has expired." | a sessão acabou (12 h, ou 30 dias com "manter conectado") ou a senha foi trocada | entre de novo |
| "Invalid email or password." | e-mail ou senha errados | confira; esqueceu, peça ao administrador para redefinir |
| "Too many attempts. Try again in a few minutes." | 5 erros em 15 minutos | espere alguns minutos |
| "Invoice e QuickBooks são decisão do gerente ou do administrador." | operador tentando aprovar proposta financeira | peça a um gerente |
| "This action is blocked by policy and cannot be approved." | a política da ação é BLOCKED | não há como aprovar; fale com o dono se for o caso de mudar a política |
| "Esses dois cards não se unem: …" | cards de drivers ou contas diferentes do site | não una; cada driver tem o seu card |
| "Esses dois cards não se unem: os dois cards têm um rascunho aberto no balcão" (ou "a mensalidade do mesmo mês") | só cabe um por card | feche um dos rascunhos no Balcão (ou cancele a mensalidade repetida) e una de novo |
| Venda do site com **Resolver:** "a vaga sumiu…" ou e-mail "Site · PAGO · SEM VAGA" | o cliente pagou no carrinho, mas a vaga acabou antes do pagamento; o pagamento está guardado e a sessão não entrou na agenda | quem vende liga, remarca (ou combina o reembolso com o gerente) e anota na venda |
| E-mail "Site · PAGAMENTO FALHOU: pedido #N" | o pagamento que confirma depois (transferência) não passou; nada foi cobrado e nenhuma vaga ficou presa | Site › Pedidos do site › **Copiar o link** e mande ao cliente (botão Try again); sem e-mail do cliente, ligue |
| E-mail "Site · PROCESSANDO O PAGAMENTO" ou "Site · CHECKOUT EXPIROU" | o cliente pagou com um meio que confirma depois, ou saiu do checkout sem pagar; ele já recebeu o e-mail com o link | nada a fazer no processando; no expirou, um contato ajuda a fechar (link em Pedidos do site) |
| "Pagamento no site" não aparece no card | a conta do site ou o piloto ainda não está ligado a um card | Site › Contas de clientes: ligue a conta e o driver ao card certo |
| "Essa recorrência já está vinculada ao card de outro cliente." | tentativa de ligar a mensalidade de um cliente ao card de outro | confira o cliente certo |
| "Security deposit obrigatório: informe o valor do depósito…" | o serviço está marcado como depósito obrigatório e o valor ficou vazio ou 0 | ponha o valor (ex.: 400) ou desmarque "obrigatório" em Site › Serviços e preços ou Site › Security deposit |
| "Resolver: sem estoque: … pediu 2, tinha 1" em Site › Pedidos do site (#309) | o produto em estoque foi pago, mas o box não tinha tudo no Galpão + Pista (outra venda, Balcão, contagem errada). O pagamento entrou e saiu o que tinha | separe o que tem, confira a prateleira e conte em Site › Estoque do site; falta peça: combine com o cliente (prazo ou devolução pelo Stripe). Resolvido, toque em **Resolvido** no pedido: sai do *Pagos sem estoque* do Painel do site |
| "a opção … está ligada ao estoque … e não dá para saber qual é o nome novo dela" | várias opções ligadas mudaram de nome de uma vez, fora da tela do produto | mude o nome de uma opção por vez, ou desligue em Site › Estoque do site antes |
| "a opção … está ligada ao item …: desligue … antes de tirá-la do produto" · "o produto inteiro está ligado ao item …" | tirar uma opção ligada, ou criar opções num produto ligado inteiro, soltaria a ligação | desligue em Site › Estoque do site, salve o produto e ligue de novo cada opção |
| "… ainda está ligado a … (dropshipping): desligue lá" | o item ligado a um produto que passou a dropshipping | no cartão do produto, em Site › Estoque do site, toque em **Desligar** |
| "Resolver: sem estoque ligado: … baixe à mão no Estoque" | o produto está marcado "em estoque", mas a opção vendida não tem item ligado | baixe a saída em Estoque › Quantidade e ligue a opção em Site › Estoque do site |
| "We don't have that many in stock right now" (o cliente conta) | ele pediu mais do que o box tem de um produto em estoque; o site não diz o número | conte de novo em Site › Estoque do site, ou ofereça a quantidade que tem |
| Cartão "Devolução pendente" em Site › Security deposit | a resposta do Stripe não chegou na hora da devolução; o valor fica reservado | toque em **Conferir no Stripe** depois de alguns minutos |
| Publiquei o artigo do blog e o site (ou o sitemap) ainda mostra o de antes | a página fica até 5 min no navegador de quem já abriu, e o sitemap até 24 h | recarregue a página; o Google relê o sitemap sozinho |
| "Antes de publicar, falta: …" (Site › Blog) | o rascunho não tem tudo o que o Google e quem lê precisam | complete o que a lista diz, **Salvar rascunho** e publique |
| "o endereço não muda depois de publicado" (Site › Blog) | o artigo já foi ao ar uma vez: o Google tem o endereço | deixe o endereço; mude o título se precisar |
| "Este endereço é só do balcão." | você está em `parts.urace.us` | para o resto do painel, use `ops.urace.us/ops/` |
| "O acesso automático venceu. Entre com a senha." | o botão do balcão abriu o `parts.urace.us` mas não entrou: passou de 30 s, o painel saiu antes, a conta foi desativada ou o mesmo acesso foi usado duas vezes (aí a sessão que nasceu dele cai, por segurança) | entre com a senha ali, ou volte ao painel e toque no botão de novo. A auditoria guarda `auth.passe.*` |
| Cápsula **Espelho** em amarelo/vermelho ou "Espelho antigo" | dados não lidos há tempo | Hoje › **↻ Sincronizar** |
| Cápsula **Sistemas** com problema | uma integração não respondeu | Integrações › **Verificar agora**; se persistir, avise o administrador |
| **Backup do banco** em vermelho ou amarelo (Integrações) | vermelho: a cópia do dia na VPS falhou ou faltou; amarelo: só a cópia cifrada do Drive falhou ou faltou (o motivo aparece na linha) | o administrador vê a seção 10.1; "sem permissão de ESCRITA no Drive" pede `python3 adminai/google_auth.py --conta urace` na VPS |
| **Offline** / **Servidor fora** | sem internet / painel não respondeu | confira a internet; se for o servidor, avise o administrador |
| Notificação não chega no celular | permissão negada ou iPhone sem o painel na tela inicial | Equipe › ligar notificação; siga o aviso da tela |
| **Pelo Claude:** "este acesso é só de leitura" | conectou sem marcar a caixa | conecte de novo e marque "Também operar o painel como você" |
| **Pelo Claude:** "isto é do papel MANAGER ou acima; você é OPERATOR" | a rota pede papel acima do seu | peça a um gerente |
| **Pelo Claude:** `precisa_confirmar` | vai sair da empresa ou cobrar | mostre à pessoa e repita o mesmo pedido com `confirmar: true` e o código de `aprovacao` só depois do "pode mandar" |
| **Pelo Claude:** "… não existe no painel (veja urace_operacoes)" | caminho errado | procure a operação certa com `urace_operacoes` |
| **Pelo Claude:** "login, chaves e área do cliente não são operados pelo MCP" | rota fora do MCP | faça pelo painel |
| Chave de API: "Esta chave é só de leitura" | a chave está como só leitura | o administrador, em Usuários › Chaves de API, toca em **Liberar para operar** (a chave continua a mesma; #209) |
| "O kart 2-stroke já é vendido por "…": dois serviços ativos com o mesmo kart tiram o kart do site. Desative aquele antes ou escolha outro kart." (ou "O add-on … já é vendido por …") | criar, trocar o kart ou reativar um serviço deixaria dois ativos com a mesma chave (#312) | Site › Serviços e preços: desative o serviço de hoje daquele kart e depois crie, troque ou reative o novo; ou escolha outro kart (ou **Novo kart…**) |
| No site/reserva: "… is not open for online booking right now", ou um kart que desapareceu da página | nenhum serviço ativo com aquele **Kart do site**, ou dois com o mesmo (ambíguo) | Site › Serviços e preços: ative o serviço daquele kart e confira o seletor **Kart do site** — um serviço por kart (#263). O serviço ambíguo mostra, em vermelho, **fora do site: a chave … também está em …** (#312): desative um dos dois |
| No SIM2GRID: "This time is booked by phone" / um dia em laranja que só mostra "Call us" | a faixa daquele formato e horário está **sem preço** (ligar), que alguém deixou sem preço | é de propósito; para vender online, ponha o preço da faixa em Site › Sim2Grid |
| No SIM2GRID: "This time is full" ou "0 simulators left" | as reservas pagas e as que estão no pagamento já somam os simuladores daquela hora | outra hora, ou mais simuladores em Site › Sim2Grid › Regras (se houver simulador de verdade) |
| No SIM2GRID: "Online booking is not open right now" | **Vender online** desligado, nenhum formato ativo, ou o Stripe fora | ligue em Site › Sim2Grid, ative um formato em Serviços e preços, ou confira o Stripe |
| No site/reserva: "Online booking is closed right now" | **nenhum** serviço ativo em Serviços e preços: não há o que vender online | ative um serviço; enquanto isso o site manda a pessoa falar com a gente, e nenhuma vaga é prometida |
| No calendário do site: "Pick a time to continue" | o dia está escolhido e falta o turno (Morning/Afternoon) | escolha o turno; é o próprio site pedindo o que falta (#253) |

### 10.1 Backup e restauração do banco (#299)

Dono, 16/10: *"eu preciso que dados de clientes como e-mails, nomes, informações de contatos, sejam armazenados em
um banco de dados … conectado à VPS"*. Decisão: **SQLite + backup diário**. O banco é o arquivo
`~/.urace/command-center.sqlite` da VPS. Ele fica fora do repositório (o repositório é público).

**O que roda sozinho, todo dia**
- **03:15, na VPS:** cópia consistente (`VACUUM INTO`, sem parar o painel), aberta e conferida antes de contar,
  comprimida, em `~/.urace/backups/`. Ficam 30 dias de cópias e, antes disso, a primeira de cada mês por 12 meses.
- **04:00, fora da VPS:** a cópia mais nova vai **cifrada** (AES-256-GCM) para o Google Drive, em
  `Command Center/Backup do banco`, com o mesmo histórico. A pasta é privada: não compartilhe.
- **Em Integrações (Sistemas)**, a linha **Backup do banco** fica vermelha quando a cópia do dia falhou ou faltou e
  amarela quando só a do Drive falhou. O motivo aparece na linha.

**A chave da cópia do Drive** é a `CC_BACKUP_CHAVE` do `~/.urace/adminai.env` (o deploy cria uma vez e nunca mostra).
**Guarde uma cópia desse arquivo fora da VPS** (no gerenciador de senhas do dono): sem a chave, a cópia do Drive não
abre, e perder a VPS é justamente o dia em que ela faz falta. O mesmo arquivo guarda a chave do cofre (#162).

**Restaurar** (só o administrador, na VPS, e só com autorização do dono: põe outro banco no lugar do atual)

1. Ver as cópias: `python3 adminai/backup_banco.py --listar` (na VPS) ou `python3 adminai/backup_drive.py --listar` (no Drive).
2. Da VPS: escolha o arquivo e confira sem mexer em nada:
   `python3 adminai/backup_banco.py --restaurar ~/.urace/backups/<arquivo> ` (sem `--aplicar` ele só confere).
3. Do Drive (a VPS nova, ou a cópia local estragada): `python3 adminai/backup_drive.py --baixar <nome do arquivo>`.
   Ele baixa, decifra com a chave do `adminai.env`, confere e diz o comando do passo 4.
4. Pôr no lugar: `python3 adminai/backup_banco.py --restaurar <arquivo> --aplicar`. **O banco atual é guardado antes**
   (`command-center.sqlite.antes-de-restaurar-<data>`): restaurar por engano tem volta.
5. `sudo systemctl restart urace-command-center` e confira em Clientes.

Este caminho inteiro (baixar do Drive, decifrar, conferir, restaurar e os clientes voltarem) é testado em cada
mudança (`test_backup_fora_da_vps.py`).

---

### Provar o site e a venda de ponta a ponta (pacote de fotos)

Dono, 15/10 (#253): *"me de um bloco para a extensão testar todo o site e processo de vendas criando
uma conta fictícia para testar de ponta a ponta"* e *"de o comando para a extensão capturar tela a
cada passo"*. No servidor, **uma linha**:

```bash
bash adminai/deploy/command_center/testar_tudo.sh
```

Na primeira vez ele pede o **venv do teste** — e isso é de propósito: dependência de teste nunca
entra no venv da produção, que é o do serviço no ar (#264). O próprio script imprime as três
linhas para criar `~/.urace/teste-venv`.

Ele roda num **banco descartável** e numa porta própria (a operação não é tocada, o banco de
produção não é aberto) e **para na hora** se achar chave real no ambiente. No fim imprime, em
destaque, o caminho de **um pacote** (`~/.urace/teste-<data>.tar.gz`) com:

- **`RESUMO.md`** em português: uma linha por passo (o que foi feito, o que o sistema respondeu, qual
  foto, PASSOU/FALHOU), o total e a lista de telas com rolagem lateral ou alvo de toque pequeno;
- as **fotos numeradas** de cada passo da venda e de **cada tela do painel**, em `390/` (celular) e
  `1280/` (computador);
- o log inteiro do teste.

**O que o pacote prova:** o site abre; kart, dia e turno viram sessão com o preço do painel; a conta
fictícia é criada no próprio site; o carrinho soma sessão + depósito + produto; o checkout fecha num
pagamento só; a volta mostra o pedido pago; e o painel registra a venda GANHO, a sessão em
Site › Agendamentos e o card do piloto. **O que ele não prova:** cobrança de verdade no Stripe
(chave real), e-mail de verdade saindo, e Asana, QuickBooks, DocuSign ou Google de verdade — tudo
isso é falso ali, de propósito. Deu FALHOU em algum passo: mande o pacote para o Claude; a foto do
estado do erro está dentro.

---

## 11. Glossário

| Termo | O que é |
|---|---|
| **Card** | a ficha de um cliente no painel (`/ops/clients/<n>`) |
| **Piloto / driver** | quem pilota. Cada driver tem o seu card |
| **Responsável** | quem paga e assina (às vezes o pai ou a mãe do piloto). A conta do QuickBooks é dele |
| **Pro Racing Driver (★ Pro)** | piloto pronto para competir; libera equipamento e corridas no card |
| **Serviço** | uma tarefa do quadro U-RACE no Asana (coaching, academy, trackside...) |
| **Waiver** | o termo de responsabilidade do DocuSign. Parental se o piloto é menor; adulto se não. Sem ela assinada, o piloto não entra na pista |
| **Invoice** | a cobrança no QuickBooks |
| **Estimate** | o orçamento no QuickBooks (ex.: preparação de corrida) |
| **Security deposit** | o depósito de segurança do serviço que pede (ex.: Arrive and Drive, US$ 400, devolvido em até 5 dias úteis sem incidente). Vai na mesma invoice do serviço, na venda manual ou automática (dono, 14/10) |
| **Rate Card** | a tabela de preços oficial; manda acima do catálogo e atualiza o catálogo do QuickBooks toda segunda |
| **Preço da tabela** | no Fechar venda, o preço do item do catálogo do QuickBooks, nunca o valor da venda. Fora dele, a invoice espera o gerente |
| **Liberar invoice** | o gerente ou o dono confere o valor de uma invoice de venda fora da tabela e libera o envio (#204) |
| **Card de irmão** | o card próprio do irmão, com o mesmo responsável, e-mail e telefone; os dois nunca se unem |
| **Oportunidade** | uma venda em andamento. Não é cliente até fechar |
| **Lead** | contato que chegou pelo Kommo |
| **Closer** | quem fecha a venda. Não é um papel do sistema: é operador |
| **Balcão** | a tela de ler QR do cliente e das peças: cobrar (vai para a invoice de peças do dia, não é enviada sozinha) ou guardar (estoque do cliente) |
| **Ponte (de e-mail)** | a rotina que lê o Gmail a cada 15 minutos e leva cada novidade de Suits para a IA |
| **Espelho** | a cópia, no painel, do que está nas fontes (Asana, DocuSign, Gmail, QuickBooks, Kommo) |
| **Precisa de atenção** | a fila do que a IA não resolveu sozinha |
| **Aprovação** | proposta da IA que espera uma pessoa decidir |
| **Pendência / Falta completar** | registro criado com informação faltando, até alguém completar |
| **Política** | a regra de cada ação da IA: sozinha (SAFE), confirmação, aprovação ou bloqueada |
| **Box** | mecânicos e coaches |
| **Meu dia** | a tela inicial do box: serviços, corridas e sessões do dia, com checklist |
| **Área do cliente / portal** | o site do cliente (`/ops/portal`), separado do painel da equipe |
| **Cérebro** | a memória da empresa (`brain/` no repositório): processos, clientes, regras |
| **MCP** | o jeito de ligar o Claude de cada pessoa ao painel |
| **Auditoria** | o registro imutável de tudo o que foi feito, e por quem |

---

## 12. Bloco para a IA

> Esta seção é para o Claude. Uma pessoa pode pular.

### Quem você é aqui

Você trabalha com uma pessoa da URACE (kart racing em Orlando) e opera o Command Center **como
ela**, com o papel dela, pelo MCP `https://ops.urace.us/ops/mcp`. Tudo o que você faz fica na
auditoria com o nome dela.

### Como trabalhar

1. **Comece pelo panorama:** `urace_resumo` e `urace_atencao`.
   Para diagnosticar **um** cliente, consulte pelo card: `urace_cliente_reservas`,
   `urace_cliente_pedidos` e `urace_cliente_pagamentos` com o `client_id` (não traz dado de outro cliente).
2. **Descubra antes de agir:** `urace_operacoes` com uma palavra (`clients`, `sales`, `suits`,
   `waiver`, `invoice`...). Ela só lista o que o papel da pessoa alcança. Não chute rota.
3. **Leia antes de perguntar:** procure o cliente (`GET /ops/api/clients?q=…`), o pedido, a
   oportunidade. Muitas vezes só o nome basta para achar e-mail e telefone.
4. **Antes de criar, procure o card.** Achou, use o `client_id`. Nunca grave dado de uma pessoa
   no registro de outra.
5. **O que sai da empresa ou cobra:** a primeira chamada devolve `precisa_confirmar`. Mostre à
   pessoa o que vai acontecer e só repita com `confirmar: true` depois do "pode mandar" dela.
   Não procure outro caminho para pular a confirmação.
6. **Erro de papel:** diga qual papel precisa e pare. Não tente outra rota para contornar.
7. **Faltou dado:** não invente. Diga o que falta, de forma curta, e o que você já fez.
8. **Responda em português do Brasil, direto, frases curtas.** No fim: o que você fez (uma linha
   por coisa, com link quando houver) e o que ficou esperando a pessoa.

### Rotas que você vai usar com frequência

Todas com prefixo `/ops/api`. Papel mínimo entre parênteses ("logado" = qualquer papel).

| Para | Método e caminho |
|---|---|
| panorama do dia | `GET /dashboard` (logado) |
| fila de atenção | `GET /needs-attention` (logado) |
| instruir a IA do painel sobre um item | `POST /needs-attention/instruct` (operador) |
| ocultar / restaurar um aviso (não apaga a origem) | `POST /needs-attention/dismiss` · `POST /needs-attention/restore` (operador) |
| buscar | `GET /search?q=…` (logado) |
| listar / abrir cliente | `GET /clients?q=…` · `GET /clients/{id}` (logado) |
| criar cliente (se já existir, devolve o existente) | `POST /clients` (operador) |
| editar cliente | `PATCH /clients/{id}` (operador) |
| unir dois cards | `POST /client-merge` (operador; recusa drivers diferentes do site) |
| mover serviço para o card certo | `POST /tasks/{id}/cliente` (gerente, pelo botão "Mover" do card) |
| criar serviço (tarefa do Asana pelo modelo oficial) | `POST /tasks` (operador) |
| enviar waiver avulsa | `POST /waivers/send` (operador) |
| convite da waiver por e-mail: para quem vai e os já mandados | `GET /clients/{id}/waiver-invite` (operador) |
| mandar / reenviar o convite | `POST /clients/{id}/waiver-invite` com `{"email": "<o e-mail do card>"}` (operador; o e-mail confere com o card) |
| versões do modelo da waiver nativa e o PDF de cada uma (#116) | `GET /site/waiver-nativa/versoes?kind=&limit=&offset=` · `GET /site/waiver-nativa/versoes/{id}/pdf` (gerente) |
| trilha de eventos de uma waiver assinada no sistema e se a cadeia está íntegra (#111) | `GET /site/waiver-nativa/{id}/eventos` (gerente) |
| reenviar a cópia por e-mail de uma waiver assinada no sistema, ao e-mail que assinou (#114) | `POST /waivers/{id}/copy` (operador) |
| dia do box | `GET /meu-dia` (operador; é a tela inicial do mecânico e do coach) |
| mandar comando à IA do painel | `POST /ai/commands` (operador) |
| propostas esperando decisão | `GET /ai/actions?status=PROPOSED` (logado) |
| aprovar / recusar proposta | `POST /ai/actions/{id}/approve` · `POST /ai/actions/{id}/reject` (operador; financeiro só gerente+) |
| pendências "Falta completar" | `GET /ai/pendencias` (logado; `todas=true` para gerente) |
| marcar pendência como completa | `POST /ai/pendencias/{id}/resolver` (operador; quem pediu ou gerente) |
| o que a IA pode fazer e a política | `GET /ai/capabilities` (logado) |
| blog do site: listar / abrir um artigo | `GET /site/blog?q=&estado=&categoria=&limit=&offset=` · `GET /site/blog/{id}` (operador) |
| blog: criar / mudar o rascunho | `POST /site/blog` com `{"title", "category"}` · `PATCH /site/blog/{id}` (operador) |
| blog: publicar / tirar do ar | `POST /site/blog/{id}/publicar` com `{"visto": "<updated_at do artigo que você leu>"}` (null nos 7 que nunca mudaram; mudou depois → 409: leia de novo) · `POST /site/blog/{id}/despublicar` com `{"confirmar": true}` (só ADMIN ou acesso livre; os 7 do site antigo pedem `confirmar`) |
| Suits: descartar / restaurar | `POST /suits/{id}/descartar` com `{"motivo": "…"}` · `POST /suits/{id}/restaurar` (operador) |
| Suits: ligar/desligar a IA no pedido (#198) | `POST /suits/{id}/ia` com `{"ligada": false}` (operador) |
| Suits: aprovação final, arte final e medidas (#382) | `POST /suits/{id}/aprovacao` com `{"trecho", "message_id", "data"}` · `POST /suits/{id}/arte-final` com `{"nome", "final"}` · `POST /suits/{id}/medidas/estado` com `{"chaves", "estado", "motivo"}` (operador) |
| Suits: e-mail preparado ao designer, endereço ao fornecedor, saúde da ponte (#382) | `POST /suits/{id}/preparados/{item}/enviar` ou `/descartar` · `GET`/`POST /suits/{id}/endereco-fornecedor[/rascunho]` · `GET /suits/ponte/saude` (operador) |

As rotas de vendas, do box e de Suits estão nos playbooks de cada área (links no topo).

### Limites que você respeita sempre

- Você **não** tem acesso ao Cofre, a login, senha e chaves, nem à área do cliente.
- Você **nunca** pede senha, token, PIN ou chave. Se a pessoa colar um, diga para não fazer isso
  e não repita o valor.
- Você **nunca** apaga. Para tirar algo do caminho: ocultar, descartar ou lixeira, e só com o OK
  da pessoa.
- Pedido de Suits com a IA desligada (`ia_ligada = 0`): não proponha e-mail nem mudança de etapa
  por conta própria; mostre o que chegou e pergunte.
- Datas e horas em America/New_York.
- Nada de Turo nem Hostaway.
- Resposta 200 de uma API externa não é prova de que algo aconteceu: confira no registro.

### Onde ler mais

- Processos da empresa: `brain/10_PROCESSOS/` (índice em `Processos.md`).
- Decisões do dono e o porquê: `brain/08_DECISOES/`.
- Manual técnico: `docs/manual-do-command-center.md`.
