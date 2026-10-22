/* A reserva do SIM2GRID (#392): a hora de simulador, cobrada por hora, até N pessoas na mesma hora.
 *
 * Dono, 22/10: "sera um serviço um diferente das aulas de kart podendo agendar ate 5 pessoas para a mesma hora, o
 * valor do serviço é cobrado por hora. monte assim como montou o arrive and drive com todas as configurações
 * ajustaveis".
 *
 * O caminho é o do Arrive and Drive (#262: "um caminho somente levando para o carrinho"): formato → dia → hora de
 * início → quantas horas e quantas pessoas → carrinho → conta → Stripe. Cada pessoa é um simulador e vira uma linha do
 * carrinho (o piloto de cada uma é escolhido lá, cada um no seu card). Preço, vaga e depósito, quem diz é o servidor:
 * aqui só se mostra o que /ops/api/vitrine/sim2grid mandou e se guarda a escolha. */
(function () {
  'use strict'
  var raiz = document.querySelector('.sim-agenda')
  if (!raiz) return
  var api = raiz.getAttribute('data-api')
  var paraCarrinho = raiz.getAttribute('data-carrinho') || '/cart/'
  var grade = raiz.querySelector('.agenda-grade')
  var mesBox = raiz.querySelector('.agenda-mes')
  var titulo = raiz.querySelector('.agenda-titulo')
  var horasBox = raiz.querySelector('.sim-horas')
  var opcoes = raiz.querySelector('.sim-opcoes')
  var selHoras = raiz.querySelector('select[name="horas"]')
  var selPessoas = raiz.querySelector('select[name="pessoas"]')
  var aviso = raiz.querySelector('.agenda-aviso')
  var indisponivel = raiz.querySelector('.agenda-indisponivel')
  var indisponivelTxt = raiz.querySelector('.agenda-indisponivel-txt')
  var resumo = raiz.querySelector('.agenda-resumo')
  var precoEl = raiz.querySelector('.agenda-preco')
  var depositoEl = raiz.querySelector('.agenda-deposito')
  var depositoValor = raiz.querySelector('.agenda-deposito-valor')
  var botao = raiz.querySelector('.agenda-carrinho')
  var ok = raiz.querySelector('.carrinho-ok')
  var sorteio = document.querySelector('.sim-sorteio input')
  var SEMANA = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  var AVISO = 'Days in grey are closed or full. All times are Orlando local time.'
  var CAMPANHA = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid', 'ref']
  var daUrl = new URLSearchParams(window.location.search)
  var online = raiz.getAttribute('data-online') === '1'
  var dias = {}, meses = [], mes = null, dia = null, hora = null, cfg = null, formatos = [], comCarrinho = false, carregou = false

  function usd(n) { return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 }) }
  function hh(h) { h = Number(h) % 24; return h === 0 ? 'Midnight' : h === 12 ? 'Noon' : (h % 12 || 12) + (h < 12 ? ' AM' : ' PM') }
  function dataLonga(iso) { return new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }) }
  function radios() { return [].slice.call(document.querySelectorAll('input[name="formato"]')) }
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
  /** Dá para começar aqui? Preço online e pelo menos uma vaga. */
  function vende(x, f) { var p = preco(x, f); return typeof p === 'number' && x.spots > 0 }
  /** Quantas horas seguidas cabem a partir de `h`, com `pessoas` simuladores livres em cada uma. */
  function seguidas(iso, h, f, pessoas) {
    var n = 0
    while (n < cfg.max_hours) {
      var x = daHora(iso, h + n)
      if (!x || typeof preco(x, f) !== 'number' || x.spots < pessoas) break
      n++
    }
    return n
  }
  function diaAberto(iso, f) {
    var d = dias[iso]
    return !!(d && f && d.hours.some(function (x) { return vende(x, f) && seguidas(iso, x.h, f, 1) >= cfg.min_hours }))
  }
  function diaLigar(iso, f) {
    var d = dias[iso]
    return !!(d && f && d.hours.some(function (x) { return preco(x, f) === null }))
  }

  function preencher(sel, de, ate, atual) {
    sel.textContent = ''
    for (var i = de; i <= ate; i++) sel.appendChild(new Option(String(i), String(i)))
    sel.value = String(Math.min(Math.max(atual || de, de), ate))
  }

  function total() {
    var f = formato()
    if (!f || !dia || hora == null) return null
    var horas = Number(selHoras.value) || 1, pessoas = Number(selPessoas.value) || 1, soma = 0
    for (var i = 0; i < horas; i++) { var p = preco(daHora(dia, hora + i), f); if (typeof p !== 'number') return null; soma += p }
    return { horas: horas, pessoas: pessoas, valor: soma * pessoas, porPessoa: soma, deposito: (Number(f.deposit) || 0) * pessoas }
  }

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
    resumo.textContent = (dia ? dataLonga(dia) + (hora != null && t ? ' · ' + hh(hora) + '–' + hh(hora + t.horas) : '') + ' · ' : '')
      + (f ? f.titulo : '') + (t ? ' · ' + t.pessoas + (t.pessoas === 1 ? ' driver' : ' drivers') : '')
    precoEl.textContent = t ? usd(t.valor) : ''
    if (depositoEl) { depositoEl.hidden = !(t && t.deposito); depositoValor.textContent = t && t.deposito ? usd(t.deposito / t.pessoas) : '' }
    var falta = !carregou || !dia ? 'dia' : hora == null ? 'hora' : null
    if (carregou && cfg.online) aviso.textContent = falta === 'hora' ? 'Now pick a start time.' : AVISO
    botao.hidden = semVenda
    botao.disabled = !!(falta || semVenda || !t)
    if (botao.disabled) botao.setAttribute('aria-disabled', 'true'); else botao.removeAttribute('aria-disabled')
    botao.textContent = falta === 'dia' ? 'Pick a day to continue' : falta === 'hora' ? 'Pick a start time to continue'
      : t ? 'Add to cart · ' + usd(t.valor) + (t.deposito ? ' + ' + usd(t.deposito) + ' deposit' : '') : 'Add to cart'
  }

  function opcoesDaHora() {
    var f = formato()
    if (!f || !dia || hora == null) { opcoes.hidden = true; return }
    var x = daHora(dia, hora)
    var maxPessoas = Math.max(1, Math.min(cfg.capacity, x ? x.spots : 1))
    preencher(selPessoas, 1, maxPessoas, Number(selPessoas.value) || 1)
    var cabem = seguidas(dia, hora, f, Number(selPessoas.value) || 1)
    preencher(selHoras, cfg.min_hours, Math.max(cfg.min_hours, cabem), Number(selHoras.value) || cfg.min_hours)
    opcoes.hidden = false
  }

  function desenharHoras() {
    horasBox.textContent = ''
    var f = formato()
    if (!dia || !f) { horasBox.hidden = true; opcoes.hidden = true; return }
    dias[dia].hours.forEach(function (x) {
      var p = preco(x, f)
      if (p === undefined) return
      var b = document.createElement('button')
      b.type = 'button'; b.className = 'agenda-turno sim-hora'
      var pode = typeof p === 'number' && x.spots > 0 && seguidas(dia, x.h, f, 1) >= cfg.min_hours
      b.disabled = !pode
      b.setAttribute('aria-pressed', String(hora === x.h))
      b.innerHTML = '<span></span><small></small>'
      b.firstChild.textContent = hh(x.h)
      b.lastChild.textContent = p === null ? 'Call us' : !x.spots ? 'Full' : usd(p) + ' · ' + x.spots + (x.spots === 1 ? ' simulator left' : ' simulators left')
      b.addEventListener('click', function () { hora = x.h; desenharHoras(); opcoesDaHora(); atualizar() })
      horasBox.appendChild(b)
    })
    horasBox.hidden = !horasBox.childNodes.length
    if (hora != null && !(daHora(dia, hora) && vende(daHora(dia, hora), f))) { hora = null }
    opcoesDaHora()
  }

  function desenharMes() {
    grade.textContent = ''
    var f = formato()
    SEMANA.forEach(function (s) { var x = document.createElement('span'); x.className = 'ds'; x.textContent = s; grade.appendChild(x) })
    var a = Number(mes.slice(0, 4)), m = Number(mes.slice(5, 7))
    var primeiro = new Date(a, m - 1, 1).getDay(), n = new Date(a, m, 0).getDate()
    for (var i = 0; i < primeiro; i++) grade.appendChild(document.createElement('span'))
    for (var k = 1; k <= n; k++) {
      var iso = mes + '-' + (k < 10 ? '0' : '') + k
      var aberto = diaAberto(iso, f), ligar = !aberto && diaLigar(iso, f)
      var b = document.createElement('button')
      b.type = 'button'; b.className = 'agenda-dia' + (aberto || ligar ? ' aberto' : '') + (ligar ? ' ligar' : '')
      b.textContent = k; b.disabled = !(aberto || ligar)
      b.setAttribute('aria-pressed', String(dia === iso))
      b.setAttribute('aria-label', dataLonga(iso) + (aberto ? ', available' : ligar ? ', book by phone' : ', not available'))
      if (aberto || ligar) b.addEventListener('click', (function (x) {
        return function () { dia = x; hora = null; desenharMes(); desenharHoras(); atualizar() }
      })(iso))
      grade.appendChild(b)
    }
    titulo.textContent = new Date(mes + '-15T12:00:00').toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    var i0 = meses.indexOf(mes)
    mesBox.querySelector('[data-ir="-1"]').disabled = i0 <= 0
    mesBox.querySelector('[data-ir="1"]').disabled = i0 >= meses.length - 1
  }

  mesBox.addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-ir]')
    if (!b || b.disabled) return
    mes = meses[meses.indexOf(mes) + Number(b.getAttribute('data-ir'))]
    desenharMes()
  })
  radios().forEach(function (r) {
    r.addEventListener('change', function () {
      if (!carregou) return
      if (dia && !diaAberto(dia, formato()) && !diaLigar(dia, formato())) dia = null
      hora = null; desenharMes(); desenharHoras(); atualizar()
    })
  })
  selPessoas.addEventListener('change', function () { opcoesDaHora(); atualizar() })
  selHoras.addEventListener('change', atualizar)

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
      d.dias.forEach(function (x) { dias[x.date] = x })
      meses = d.dias.reduce(function (acc, x) { var m = x.date.slice(0, 7); if (acc.indexOf(m) < 0) acc.push(m); return acc }, [])
      carregou = true
      if (!meses.length) { aviso.textContent = 'No dates open for booking right now. Please check back soon or call us.'; atualizar(); return }
      mes = meses[0]
      for (var i = 0; i < d.dias.length; i++) { if (diaAberto(d.dias[i].date, formato())) { mes = d.dias[i].date.slice(0, 7); break } }
      mesBox.hidden = false
      aviso.textContent = AVISO
      desenharMes()
      atualizar()
    })
    .catch(function () { aviso.textContent = 'We could not load the calendar. Please refresh the page or call us.' })
})()
