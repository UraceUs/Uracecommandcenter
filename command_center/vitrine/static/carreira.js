/* O simulador de carreira do /career/ (#528): o que a página faz no navegador. Nosso, sem nada de fora, sem eval, sem
 * nada inline. Sem este script a página continua inteira: as três rotas com a escada, as quatro respostas do "Find your
 * step" com a condição de cada uma e a lista de preços do plano.
 *
 * - "Select your career": os radios do destino; só a rota escolhida fica à vista e a frase dela é anunciada.
 * - "Find your step": as três perguntas; a resposta é a do `decide()` do urace.us (a mesma de `conteudo_carreira.decidir`).
 * - "My career plan": pôr e tirar, quantidade, os totais (avulso, por mês, a cotar), copiar e limpar. O preço é o
 *   `data-preco` de cada linha (vem do servidor); o plano fica só neste navegador (localStorage, como lá).
 * Nada se mexe sozinho: só texto e atributos mudam, então prefers-reduced-motion não tem o que desligar aqui. */
(function () {
  'use strict'
  var $ = function (sel, raiz) { return (raiz || document).querySelector(sel) }
  var $$ = function (sel, raiz) { return Array.prototype.slice.call((raiz || document).querySelectorAll(sel)) }
  var usd = function (v) {
    var n = Math.round(v * 100) / 100
    return '$' + n.toLocaleString('en-US', n % 1 ? { minimumFractionDigits: 2, maximumFractionDigits: 2 } : {})
  }
  $$('[data-so-js]').forEach(function (el) { el.hidden = false })

  // ------------------------------------------------------------- o destino
  var alvos = $('[data-car-alvos]')
  if (alvos) {
    var anuncio = $('[data-car-anuncio]')
    var mostraRota = function (chave, anunciar) {
      $$('[data-rota], [data-rota-degraus]').forEach(function (el) {
        el.hidden = (el.getAttribute('data-rota') || el.getAttribute('data-rota-degraus')) !== chave
      })
      var resumo = $('[data-rota="' + chave + '"]')
      if (anunciar && anuncio && resumo) anuncio.textContent = resumo.getAttribute('data-anuncio')
    }
    alvos.hidden = false
    var marcado = $('input[name="destino"]:checked', alvos)
    mostraRota(marcado ? marcado.value : 'f1', false)
    alvos.addEventListener('change', function (ev) {
      if (ev.target.name === 'destino') mostraRota(ev.target.value, true)
    })
  }

  // ------------------------------------------------------------- "Find your step"
  var perguntas = $('[data-car-localizador]')
  if (perguntas) {
    var respostas = $$('[data-resultado]')
    var decide = function (quem, idade, exp) {          // o decide() do urace.us
      if (!quem || !idade || !exp) return null
      if (exp === 'races') return 'team'
      if (exp === 'some') return 'academy'
      return parseInt(idade, 10) <= 6 ? 'ad' : 'sim'
    }
    var valor = function (nome) { var r = $('input[name="' + nome + '"]:checked', perguntas); return r ? r.value : null }
    perguntas.hidden = false
    $$('[data-se]').forEach(function (el) { el.hidden = true })
    respostas.forEach(function (el) { el.hidden = true })
    perguntas.addEventListener('change', function () {
      var res = decide(valor('who'), valor('age'), valor('exp'))
      respostas.forEach(function (el) { el.hidden = el.getAttribute('data-resultado') !== res })
    })
    perguntas.addEventListener('submit', function (ev) { ev.preventDefault() })
  }

  // ------------------------------------------------------------- "My career plan"
  var linhas = $$('[data-item]')
  if (!linhas.length) return
  var SO_UM = ['ac-1', 'ac-3', 'ac-6']                  // uma tarifa da Academy por vez (como lá)
  var CHAVE = 'urace-plan'
  var plano = {}
  try { plano = JSON.parse(window.localStorage.getItem(CHAVE) || '{}') || {} } catch (err) { plano = {} }
  var guarda = function () { try { window.localStorage.setItem(CHAVE, JSON.stringify(plano)) } catch (err) { /* sem armazenamento */ } }
  var linha = function (k) { return linhas.filter(function (l) { return l.getAttribute('data-item') === k })[0] }
  Object.keys(plano).forEach(function (k) {
    if (!linha(k) || !(plano[k] >= 1)) delete plano[k]
  })

  var conta = function () {
    var um = 0, mes = 0, cotar = 0, texto = []
    Object.keys(plano).forEach(function (k) {
      var l = linha(k), q = plano[k], rot = l.getAttribute('data-rotulo'), p = l.getAttribute('data-preco')
      if (p === '') { cotar++; texto.push('- ' + rot + ' (quote)'); return }
      var v = parseFloat(p) * q
      if (l.getAttribute('data-unidade') === 'month') { mes += v; texto.push('- ' + rot + ' x' + q + ' = ' + usd(v) + '/month') }
      else { um += v; texto.push('- ' + rot + ' x' + q + ' = ' + usd(v)) }
    })
    return { um: um, mes: mes, cotar: cotar, texto: texto }
  }

  var desenha = function () {
    linhas.forEach(function (l) {
      var k = l.getAttribute('data-item'), q = plano[k] || 0
      var por = $('[data-por]', l), qtd = $('[data-qtd]', l)
      por.setAttribute('aria-pressed', String(q > 0))
      $('[data-por-txt]', por).textContent = q > 0 ? '✓ Added' : 'Add'
      if (qtd) { qtd.hidden = !q; $('[data-n]', qtd).textContent = String(q || 1) }
    })
    var t = conta(), n = Object.keys(plano).length
    $('[data-tot-um]').textContent = usd(t.um)
    $('[data-tot-mes]').textContent = usd(t.mes)
    $('[data-tot-cotar-linha]').hidden = !t.cotar
    $('[data-tot-cotar]').textContent = t.cotar + (t.cotar === 1 ? ' item' : ' items')
    $('[data-plano-conta]').textContent = n ? n + (n === 1 ? ' item' : ' items') : 'Empty'
    $('[data-plano-copiar]').disabled = !n
    $('[data-plano-limpar]').disabled = !n
  }

  linhas.forEach(function (l) {
    var k = l.getAttribute('data-item')
    $('[data-por]', l).addEventListener('click', function () {
      if (plano[k]) delete plano[k]
      else {
        if (SO_UM.indexOf(k) > -1) SO_UM.forEach(function (o) { delete plano[o] })
        plano[k] = 1
      }
      guarda(); desenha()
    })
    $$('[data-q]', l).forEach(function (b) {
      b.addEventListener('click', function () {
        plano[k] = (plano[k] || 0) + (b.getAttribute('data-q') === '+' ? 1 : -1)
        if (plano[k] < 1) delete plano[k]
        guarda(); desenha()
      })
    })
  })

  $('[data-plano-limpar]').addEventListener('click', function () { plano = {}; guarda(); desenha() })
  $('[data-plano-copiar]').addEventListener('click', function (ev) {
    var botao = ev.currentTarget, t = conta()
    var txt = 'MY URACE CAREER PLAN\n\n' + t.texto.join('\n') + '\n\nOne-off: ' + usd(t.um) + '\nEvery month: ' + usd(t.mes) +
      '/mo\n\nTrack fees are charged separately by the circuit.'
    var feito = function (msg) { botao.textContent = msg; window.setTimeout(function () { botao.textContent = 'Copy my plan' }, 1800) }
    var reserva = function () {
      var ta = document.createElement('textarea')
      ta.value = txt; ta.className = 'escondido'; ta.setAttribute('readonly', '')
      document.body.appendChild(ta); ta.select()
      try { feito(document.execCommand('copy') ? 'Copied' : 'Select and copy') } catch (err) { feito('Select and copy') }
      ta.remove()
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(function () { feito('Copied') }, reserva)
    } else reserva()
  })
  desenha()
})()
