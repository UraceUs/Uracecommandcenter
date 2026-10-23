/* A reserva do SIM2GRID (#392, #396): a hora de simulador, cobrada por hora, até N pessoas na mesma hora.
 *
 * Dono, 22/10: "sera um serviço um diferente das aulas de kart podendo agendar ate 5 pessoas para a mesma hora, o
 * valor do serviço é cobrado por hora". Dono, 23/10 (#396): "imagina vc indo ao cinema na hora de construir. pq esse
 * produto eh mais ou menos isso. tipo lan house era".
 *
 * Como um app de cinema: a faixa dos dias (rola para o lado, com a etiqueta do dia que o painel define), os horários
 * com os lugares livres (uma bolinha por simulador) e o preço, − / + pessoas e horas, "With coach" num interruptor e a
 * barra fixa embaixo com o total e "Book". O dia aberto mais próximo já vem escolhido: do topo, são três toques até o
 * carrinho (o dia, a hora, Book). Cada pessoa é um simulador e vira uma linha do carrinho (o piloto de cada uma é
 * escolhido lá). Preço, vaga e depósito, quem diz é o servidor: aqui só se mostra o que /ops/api/vitrine/sim2grid
 * mandou e se guarda a escolha. */
(function () {
  'use strict'
  var raiz = document.querySelector('.sim-agenda')
  if (!raiz) return
  var api = raiz.getAttribute('data-api')
  var paraCarrinho = raiz.getAttribute('data-carrinho') || '/cart/'
  var faixaDias = raiz.querySelector('.sim-dias')
  var topoDia = raiz.querySelector('.sim-dia-topo')
  var horasBox = raiz.querySelector('.sim-horas')
  var quantos = raiz.querySelector('.sim-quantos')
  var passoPessoas = raiz.querySelector('[data-passo="pessoas"]')
  var passoHoras = raiz.querySelector('[data-passo="horas"]')
  var amigos = raiz.querySelector('.sim-amigos')
  var chave = raiz.querySelector('.sim-coach-input')
  var aviso = raiz.querySelector('.agenda-aviso')
  var indisponivel = raiz.querySelector('.agenda-indisponivel')
  var indisponivelTxt = raiz.querySelector('.agenda-indisponivel-txt')
  var barra = document.querySelector('.sim-barra')
  var resumo = barra.querySelector('.agenda-resumo')
  var precoEl = barra.querySelector('.agenda-preco')
  var depositoEl = barra.querySelector('.agenda-deposito')
  var depositoValor = barra.querySelector('.agenda-deposito-valor')
  var botao = barra.querySelector('.agenda-carrinho')
  var ok = barra.querySelector('.carrinho-ok')
  var sorteio = document.querySelector('.sim-sorteio input')
  var AVISO = 'All times are Orlando local time.'
  var CAMPANHA = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid', 'ref']
  var daUrl = new URLSearchParams(window.location.search)
  var online = raiz.getAttribute('data-online') === '1'
  var dias = {}, ordem = [], dia = null, hora = null, cfg = null, formatos = [], comCarrinho = false, carregou = false
  var pessoas = 1, horas = 1
  var capacidadeHtml = Number(raiz.getAttribute('data-capacidade')) || 5

  // ---------------------------------------------------------------- a barra fixa: o chat e os cookies sobem acima dela
  var html = document.documentElement
  function medirBarra() { html.style.setProperty('--barra-altura', barra.offsetHeight + 'px') }
  html.classList.add('com-barra-sim')
  medirBarra()
  window.addEventListener('resize', medirBarra)
  if (window.ResizeObserver) new ResizeObserver(medirBarra).observe(barra)

  function usd(n) { return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 }) }
  function hh(h) { h = Number(h) % 24; return h === 0 ? 'Midnight' : h === 12 ? 'Noon' : (h % 12 || 12) + (h < 12 ? ' AM' : ' PM') }
  function data(iso, o) { return new Date(iso + 'T12:00:00').toLocaleDateString('en-US', o) }
  function dataLonga(iso) { return data(iso, { weekday: 'long', month: 'long', day: 'numeric' }) }
  function dataCurta(iso) { return data(iso, { weekday: 'short', month: 'short', day: 'numeric' }) }
  function capacidade() { return cfg ? cfg.capacity : capacidadeHtml }
  function formato() {
    var r = document.querySelector('input[name="formato"]:checked')
    if (!r || !r.value) return null
    var id = Number(r.value)
    return formatos.filter(function (f) { return f.id === id })[0] || null
  }
  /** A hora `h` do dia, ou null. */
  function daHora(iso, h) {
    var d = dias[iso]
    if (!d) return null
    return d.hours.filter(function (x) { return x.h === h })[0] || null
  }
  /** O preço desta hora no formato: número (vende), null (ligar) ou undefined (fechado). */
  function preco(x, f) { return x && f ? x.prices[String(f.id)] : undefined }
  /** Quantas horas seguidas cabem a partir de `h`, com `n` simuladores livres em cada uma. Só a hora de início
   *  precisa de preço: vale a tarifa de quando a sessão começa (dono, 22/10, #392). */
  function seguidas(iso, h, f, n) {
    var k = 0
    if (typeof preco(daHora(iso, h), f) !== 'number') return 0
    while (k < cfg.max_hours) {
      var x = daHora(iso, h + k)
      if (!x || x.spots < n) break
      k++
    }
    return k
  }
  /** Dá para começar aqui com `n` pessoas? */
  function cabe(iso, x, f, n) { return typeof preco(x, f) === 'number' && x.spots >= n && seguidas(iso, x.h, f, n) >= cfg.min_hours }
  function diaAberto(iso, f) {
    var d = dias[iso]
    return !!(d && f && d.hours.some(function (x) { return cabe(iso, x, f, 1) }))
  }
  function diaLigar(iso, f) {
    var d = dias[iso]
    return !!(d && f && d.hours.some(function (x) { return preco(x, f) === null }))
  }
  /** A etiqueta que vale nesta hora (a do dia inteiro ou a da faixa), ou null. */
  function etiquetaDaHora(iso, h) {
    var ts = (dias[iso] && dias[iso].tags) || []
    return ts.filter(function (t) { return t.start == null || (t.start <= h && h < t.end) })[0] || null
  }
  function faixaTxt(t) { return t.start == null ? '' : hh(t.start) + '–' + hh(t.end) }
  function rotulo(t) { return (t.icon ? t.icon + ' ' : '') + t.label }

  function total() {
    var f = formato()
    if (!f || !dia || hora == null) return null
    var p = preco(daHora(dia, hora), f)                      // a tarifa do início vale para todas as horas
    if (typeof p !== 'number') return null
    var soma = p * horas
    return { horas: horas, pessoas: pessoas, valor: soma * pessoas, porPessoa: soma, deposito: (Number(f.deposit) || 0) * pessoas }
  }

  // ---------------------------------------------------------------- − / + (pessoas e horas)
  function limites() {
    var f = formato(), x = dia && hora != null ? daHora(dia, hora) : null
    var maxP = x ? Math.max(1, Math.min(capacidade(), x.spots)) : capacidade()
    var minH = cfg ? cfg.min_hours : 1
    var maxH = cfg ? (x && f ? Math.max(minH, seguidas(dia, hora, f, pessoas)) : cfg.max_hours) : 1
    return { maxP: maxP, minH: minH, maxH: maxH }
  }
  function desenharPassos() {
    var l = limites()
    pessoas = Math.min(Math.max(1, pessoas), l.maxP)
    horas = Math.min(Math.max(l.minH, horas), l.maxH)
    ;[[passoPessoas, pessoas, 1, l.maxP], [passoHoras, horas, l.minH, l.maxH]].forEach(function (p) {
      p[0].querySelector('.sim-n').textContent = String(p[1])
      p[0].querySelector('.sim-menos').disabled = p[1] <= p[2]
      p[0].querySelector('.sim-mais').disabled = p[1] >= p[3]
    })
    passoHoras.hidden = l.minH === l.maxH && (!cfg || cfg.min_hours === cfg.max_hours)
    amigos.disabled = pessoas >= l.maxP
  }
  function passo(qual, d) {
    if (qual === 'pessoas') pessoas += d; else horas += d
    desenharPassos()
    if (qual === 'pessoas') desenharHoras()
    atualizar()
  }
  [[passoPessoas, 'pessoas'], [passoHoras, 'horas']].forEach(function (p) {
    p[0].querySelector('.sim-menos').addEventListener('click', function () { passo(p[1], -1) })
    p[0].querySelector('.sim-mais').addEventListener('click', function () { passo(p[1], 1) })
  })
  // "Bring friends": já com o máximo de lugares (a hora escolhida, ou todos os simuladores)
  amigos.addEventListener('click', function () { pessoas = limites().maxP; desenharPassos(); desenharHoras(); atualizar() })

  function atualizar() {
    var f = formato()
    // a página já veio sem venda (painel desligado ou banco fora): o botão fica escondido, como o servidor mandou
    var semVenda = !online || (carregou && (!cfg.online || !comCarrinho || !window.uraceCarrinho || !formatos.length))
    // o dia (ou o formato) que só se marca por telefone: o aviso com o contato, nunca um botão morto
    var soLigar = carregou && !!dia && !!f && !diaAberto(dia, f) && diaLigar(dia, f)
    if (indisponivel && carregou) {
      indisponivelTxt.textContent = !cfg.online || !formatos.length ? 'Online booking is not open right now. Call us and we book your session for you:'
        : !comCarrinho || !window.uraceCarrinho ? 'Online checkout is closed right now. Call us and we book your session for you:'
          : soLigar ? 'Sessions in this format on this day are booked by phone. Call our team for options:' : ''
      indisponivel.hidden = !(semVenda || soLigar)
    }
    var t = total()
    if (online) {
      resumo.textContent = !carregou ? 'Loading…' : !dia ? 'Pick a day'
        : dataCurta(dia) + (hora != null && t ? ' · ' + hh(hora) + '–' + hh(hora + t.horas) : ' · pick a time')
          + ' · ' + pessoas + (pessoas === 1 ? ' driver' : ' drivers') + (f && chave ? (chave.checked ? ' · coach' : '') : f ? ' · ' + f.titulo : '')
    }
    precoEl.textContent = t ? usd(t.valor) : ''
    if (depositoEl) { depositoEl.hidden = !(t && t.deposito); depositoValor.textContent = t && t.deposito ? usd(t.deposito / t.pessoas) : '' }
    var falta = !carregou || !dia ? 'dia' : hora == null ? 'hora' : null
    if (carregou && cfg.online && ordem.length) aviso.textContent = AVISO
    botao.hidden = semVenda
    botao.disabled = !!(falta || semVenda || !t)
    if (botao.disabled) botao.setAttribute('aria-disabled', 'true'); else botao.removeAttribute('aria-disabled')
    botao.textContent = falta === 'dia' ? 'Pick a day' : falta === 'hora' ? 'Pick a time'
      : t ? 'Book · ' + usd(t.valor) + (t.deposito ? ' + ' + usd(t.deposito) + ' deposit' : '') : 'Book'
    medirBarra()
  }

  // ---------------------------------------------------------------- o dia: a faixa e o topo do dia
  function desenharDias() {
    var f = formato()
    faixaDias.textContent = ''
    ordem.forEach(function (iso) {
      var aberto = diaAberto(iso, f), ligar = !aberto && diaLigar(iso, f)
      var t = (dias[iso].tags || [])[0]
      var b = document.createElement('button')
      b.type = 'button'
      b.className = 'sim-dia' + (aberto ? ' aberto' : '') + (ligar ? ' ligar' : '') + (t ? ' com-etiqueta' : '')
      b.disabled = !(aberto || ligar)
      b.setAttribute('aria-pressed', String(dia === iso))
      b.setAttribute('aria-label', dataLonga(iso) + (aberto ? ', available' : ligar ? ', book by phone' : ', not available')
        + (t ? ', ' + t.label : ''))
      ;[['sim-dia-sem', data(iso, { weekday: 'short' })], ['sim-dia-n', data(iso, { day: 'numeric' })],
        ['sim-dia-mes', data(iso, { month: 'short' })]].concat(t ? [['sim-dia-tag', rotulo(t)]] : []).forEach(function (p) {
        var s = document.createElement('span'); s.className = p[0]; s.textContent = p[1]; s.setAttribute('aria-hidden', 'true'); b.appendChild(s)
      })
      b.addEventListener('click', function () { dia = iso; hora = null; desenharDias(); desenharHoras(); atualizar() })
      faixaDias.appendChild(b)
    })
    faixaDias.hidden = !ordem.length
    // o dia escolhido fica à vista na faixa (rola só para o lado, nunca a página)
    var sel = faixaDias.querySelector('[aria-pressed="true"]')
    if (sel && (sel.offsetLeft < faixaDias.scrollLeft || sel.offsetLeft + sel.offsetWidth > faixaDias.scrollLeft + faixaDias.clientWidth)) {
      faixaDias.scrollLeft = Math.max(0, sel.offsetLeft - 16)
    }
    desenharTopo()
  }
  function desenharTopo() {
    topoDia.textContent = ''
    topoDia.hidden = !dia
    if (!dia) return
    var s = document.createElement('strong'); s.textContent = dataLonga(dia); topoDia.appendChild(s)
    ;(dias[dia].tags || []).forEach(function (t) {
      var e = document.createElement('span'); e.className = 'sim-etiqueta'
      e.textContent = rotulo(t) + (faixaTxt(t) ? ' · ' + faixaTxt(t) : '')
      topoDia.appendChild(e)
      if (t.note) { var n = document.createElement('span'); n.className = 'sim-etiqueta-nota'; n.textContent = t.note; topoDia.appendChild(n) }
    })
  }

  // ---------------------------------------------------------------- os horários, com os lugares livres
  function desenharHoras() {
    horasBox.textContent = ''
    var f = formato()
    if (!dia || !f) { horasBox.hidden = true; desenharPassos(); return }
    if (hora != null && !cabe(dia, daHora(dia, hora) || { prices: {} }, f, 1)) hora = null
    var cap = capacidade()
    dias[dia].hours.forEach(function (x) {
      var p = preco(x, f)
      if (p === undefined) return
      var pode = cabe(dia, x, f, hora === x.h ? 1 : pessoas)
      var t = etiquetaDaHora(dia, x.h)
      var b = document.createElement('button')
      b.type = 'button'; b.className = 'sim-hora'
      b.disabled = !pode
      b.setAttribute('aria-pressed', String(hora === x.h))
      var precoTxt = p === null ? 'Call us' : !x.spots ? 'Full' : usd(p)
      b.setAttribute('aria-label', hh(x.h) + ', ' + (p === null ? 'book by phone' : !x.spots ? 'full'
        : usd(p) + ' per hour, ' + x.spots + ' of ' + cap + ' seats free') + (t ? ', ' + t.label : ''))
      var h = document.createElement('span'); h.className = 'sim-hora-h'; h.textContent = hh(x.h) + (t && t.icon ? ' ' + t.icon : '')
      var v = document.createElement('span'); v.className = 'sim-hora-p'; v.textContent = precoTxt
      var pts = document.createElement('span'); pts.className = 'sim-pontos'; pts.setAttribute('aria-hidden', 'true')
      if (cap <= 10) {
        for (var i = 0; i < cap; i++) { var bola = document.createElement('i'); if (i < x.spots) bola.className = 'livre'; pts.appendChild(bola) }
      } else pts.textContent = x.spots + ' left'
      b.appendChild(h); b.appendChild(v); b.appendChild(pts)
      b.addEventListener('click', function () { hora = x.h; desenharHoras(); atualizar() })
      horasBox.appendChild(b)
    })
    horasBox.hidden = !horasBox.childNodes.length
    desenharPassos()
  }

  function escolherDia() {
    var f = formato()
    if (dia && (diaAberto(dia, f) || diaLigar(dia, f))) return
    dia = ordem.filter(function (iso) { return diaAberto(iso, f) })[0] || ordem.filter(function (iso) { return diaLigar(iso, f) })[0] || null
  }

  // ---------------------------------------------------------------- o formato: "With coach" ou os botões
  function mudouFormato() {
    if (!carregou) { atualizar(); return }
    escolherDia(); hora = null; desenharDias(); desenharHoras(); atualizar()
  }
  if (chave) {
    chave.addEventListener('change', function () {
      var id = chave.checked ? chave.getAttribute('data-coach') : chave.getAttribute('data-solo')
      var r = document.querySelector('input[name="formato"][value="' + id + '"]')
      if (r) r.checked = true
      mudouFormato()
    })
  }
  ;[].slice.call(document.querySelectorAll('input[name="formato"]')).forEach(function (r) { r.addEventListener('change', mudouFormato) })

  botao.addEventListener('click', function () {
    var f = formato(), t = total()
    if (!f || !t || !window.uraceCarrinho) return
    var querSorteio = !!(sorteio && sorteio.checked)
    for (var i = 0; i < t.pessoas; i++) {
      // uma linha por pessoa (um simulador cada): o piloto de cada uma é escolhido no carrinho
      if (!window.uraceCarrinho.por({ tipo: 'sessao', servico: f.id, data: dia, hora: hora, horas: t.horas, sorteio: querSorteio, pessoa: true })) {
        ok.textContent = 'Your cart is full. '
        var ver = document.createElement('a'); ver.href = paraCarrinho; ver.textContent = 'View cart and pay'
        ok.appendChild(ver)
        medirBarra()
        return
      }
    }
    if (window.uraceMedicao) {
      window.uraceMedicao.push({ event: 'add_to_cart', ecommerce: { currency: 'USD', value: t.valor,
        items: [{ item_id: 'sim-' + f.id, item_name: f.name, item_category: 'simulador', price: t.porPessoa, quantity: t.pessoas }] } })
    }
    ok.textContent = 'Added to your cart. Taking you there…'
    var q = []
    CAMPANHA.forEach(function (c) { var v = daUrl.get(c); if (v) q.push(c + '=' + encodeURIComponent(v.slice(0, 120))) })
    window.location.assign(paraCarrinho + (q.length ? '?' + q.join('&') : ''))
  })

  atualizar()
  if (!online) return
  fetch(api, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    .then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.json() })
    .then(function (d) {
      cfg = d.config; formatos = d.formatos || []; comCarrinho = !!d.cart
      d.dias.forEach(function (x) { dias[x.date] = x; ordem.push(x.date) })
      carregou = true
      horas = cfg.min_hours
      if (!ordem.length) { aviso.textContent = 'No dates open for booking right now. Please check back soon or call us.'; atualizar(); return }
      escolherDia()
      quantos.hidden = false
      desenharDias()
      desenharHoras()
      atualizar()
    })
    .catch(function () { aviso.textContent = 'We could not load the times. Please refresh the page or call us.'; resumo.textContent = 'Book by phone' })
})()
