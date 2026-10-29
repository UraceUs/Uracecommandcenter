# Checklist da troca do urace.us (#173)

Dono, 09/10: troca do DNS *"quando eu decidir que esta pronto"*. Esta lista é para o dia da troca;
nada aqui roda sozinho. O passo a passo técnico está em `site-inteiro-2026-10-09.md`, seção
"Trocar o urace.us".

## Antes (pode fazer já)

- [ ] Na VPS, `~/.urace/adminai.env` tem `SITE_GTM_ID`, `SITE_META_PIXEL_ID`, `SITE_KOMMO_ID` e
      `SITE_KOMMO_HASH` (os mesmos do `urace.us` de hoje).
- [ ] No `novo.urace.us`: o banner de cookies aparece na primeira visita; **Accept** liga a medição,
      **Decline** não; **Cookie settings** no rodapé reabre o banner.
- [ ] O balão do chat aparece e uma mensagem de teste cai no Kommo (apague o lead de teste depois).
- [x] Container `GTM-59CCNDC` lido em 29/10 (#497): ele **já dispara o pixel do Meta `380948601336488`** (o mesmo
      que o plugin do WooCommerce injeta hoje, então o urace.us de hoje conta em dobro), além do GA4 `G-THWPYVX6K0`, do
      Google Ads `AW-10814335551` e do ChatGPT Ads ("oaiq"). Portanto, na VPS: **só `SITE_GTM_ID=GTM-59CCNDC`, sem
      `SITE_META_PIXEL_ID`** — o pixel vem pelo GTM, uma vez. HubSpot e Clarity do container ficam bloqueados pela
      política do site. Para a agência: os gatilhos de conversão do container usam eventos do WooCommerce e do Contact
      Form 7; no site novo os eventos são `purchase` (pedido pago) e `generate_lead` (contato e formulários); e o
      `init` do ChatGPT Ads está com `debug: true`.
- [ ] Reserva de ponta a ponta no `novo.urace.us`: data, kart, Lead and Follow, carrinho, conta,
      Stripe, página do pedido, e-mail.

- [ ] Dono revisa a **Política de Privacidade** (`/privacy/`) e os **Termos** (`/terms/`) do site (#488). Hoje o
      urace.us não tem nenhuma das duas; o `/legal/` é do app interno (Intuit) e continua como está.

## No dia (dono)

- [ ] Registro A de `urace.us` e `www.urace.us` → IP da VPS (como foi feito com `novo.urace.us`).
- [ ] Avisar o Claude: ele manda **um bloco** com as variáveis e o deploy (abaixo).

### O bloco do dia (#462)

As quatro variáveis vão no `~/.urace/adminai.env`. O deploy também as lê de lá (antes do #462 o
`CC_DOMINIOS_EXTRAS` só valia digitado no terminal, e o `urace.us` não entraria no Caddy):

```
CC_SITE_HOSTS=urace.us,www.urace.us,novo.urace.us
CC_SITE_PRINCIPAL=urace.us
CC_SITE_PREVIEW=0
CC_DOMINIOS_EXTRAS="ops.urace.us my.urace.us novo.urace.us parts.urace.us urace.us www.urace.us"
```

- Todo nome de `CC_SITE_HOSTS` vira bloco de **site** no Caddy (antes só o `novo.`: o `urace.us` cairia no
  bloco do painel, com a raiz levando ao login da equipe).
- `CC_SITE_PRINCIPAL` faz `www.urace.us` e `novo.urace.us` responderem **301 para `https://urace.us`** com o
  mesmo caminho e a mesma query (só GET/HEAD; a API `/ops/api/` não redireciona, para a página aberta antes da
  troca continuar funcionando). É também o endereço dos links que o servidor monta (pedido, editor, blog).
- Depois: `bash adminai/deploy/command_center/servir_command_center.sh`. Um nome cujo DNS ainda não aponta
  para a VPS é pulado pelo script; rodar de novo quando o DNS propagar.

## Depois (Claude confere e manda as fotos)

- [ ] `https://urace.us` abre o site novo com cadeado; `www.` e `novo.` levam a `urace.us` (301).
- [ ] `my.urace.us` continua abrindo a área do cliente (decisão de 07/10: aplicação separada).
- [ ] `docs/playbooks/` e o guia de Suits: trocar `novo.urace.us` por `urace.us` (PR do mesmo dia).
- [ ] As 10 páginas principais abrindo (início, Arrive and Drive, Academy, Pro Team, iniciantes,
      carreira, sobre, loja, blog, contato), sem rolar para o lado em 360 px e 390 px.
- [ ] Contato pelo site cai em Vendas com a campanha; chat cai no Kommo.
- [ ] `robots.txt` libera o site; `sitemap.xml` enviado no Search Console. (Dono, com o acesso dele.)
- [ ] WordPress na Hostinger fica guardado como está (decisão de 06/10: não mexer).
