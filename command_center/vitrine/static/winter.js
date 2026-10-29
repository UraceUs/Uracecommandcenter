/* Race the Winter 2027 (#505): o que a página /winter/ faz no navegador. Nosso, sem nada de fora, sem eval, sem nada
 * inline. Sem este script a página continua inteira: as três origens, as sete provas, as oito peças, as classes da
 * SKUSA, o formulário (cai em Vendas pelo contato.js ou pelo POST normal) e a diária de cada kart.
 *
 * - "Racing from": fica a frase da origem escolhida; o formulário acompanha (e o contrário).
 * - O filtro do calendário (home track, optional, to confirm).
 * - "Part 8 of the kart": o link abre a peça.
 * - O localizador de categoria: a idade de corrida em 1º de janeiro de 2027 e as classes abertas; a idade e o peso vão
 *   para o formulário, à vista (a pessoa muda se quiser; o que ela digitou lá não é trocado).
 * - O plano: fins de semana, dias de teste dentro da estadia, semanas na Flórida e os avisos (as regras de hoje).
 * - A estimativa: a diária do kart (do painel, no `data-preco` do botão) × os dias de teste. O resto não vira número.
 * - O link personalizado de hoje (?driver=Nome&from=europe|north|other) continua valendo.
 * Nada se mexe sozinho: só texto e atributos mudam, então prefers-reduced-motion não tem o que desligar aqui. */
(function () {
  'use strict'
  var DIA = 864e5
  var $ = function (sel, raiz) { return (raiz || document).querySelector(sel) }
  var $$ = function (sel, raiz) { return Array.prototype.slice.call((raiz || document).querySelectorAll(sel)) }
  var ms = function (iso) { var p = String(iso || '').split('-'); return Date.UTC(+p[0], +p[1] - 1, +p[2]) }
  var usd = function (v) {
    var n = Math.round(v * 100) / 100
    return '$' + n.toLocaleString('en-US', n % 1 ? { minimumFractionDigits: 2, maximumFractionDigits: 2 } : {})
  }
  var plural = function (n, um, varios) { return n + ' ' + (n === 1 ? um : varios) }
  var mostra = function (els) { els.forEach(function (el) { el.hidden = false }) }
  var aperta = function (botoes, escolhido) { botoes.forEach(function (b) { b.setAttribute('aria-pressed', String(b === escolhido)) }) }
  var com = function (lista, attr, valor) { return lista.filter(function (x) { return x.getAttribute(attr) === valor })[0] || null }
  var estado = { idade: null, kartDaPessoa: false, testesDaPessoa: null }

  // ------------------------------------------------------------- de onde a pessoa vem
  var botoesOrigem = $$('[data-origem-botoes] [data-origem]')
  var linhasOrigem = $$('[data-origem-linha]')
  var selOrigem = $('[data-origem-select]')
  function poeOrigem(o) {
    if (!com(botoesOrigem, 'data-origem', o)) o = 'europe'
    aperta(botoesOrigem, com(botoesOrigem, 'data-origem', o))
    linhasOrigem.forEach(function (l) { l.hidden = l.getAttribute('data-origem-linha') !== o })
    var op = selOrigem && com($$('option', selOrigem), 'data-origem', o)
    if (op) selOrigem.value = op.value
  }
  if (botoesOrigem.length) {
    mostra($$('[data-origem-botoes]'))
    $$('[data-origem-linha] dt').forEach(function (dt) { dt.hidden = true })
    botoesOrigem.forEach(function (b) { b.addEventListener('click', function () { poeOrigem(b.getAttribute('data-origem')) }) })
    if (selOrigem) {
      selOrigem.addEventListener('change', function () {
        var op = selOrigem.options[selOrigem.selectedIndex]
        if (op) poeOrigem(op.getAttribute('data-origem'))
      })
    }
  }

  // ------------------------------------------------------------- o filtro do calendário
  var filtro = $('[data-filtro]')
  if (filtro) {
    var botoesFiltro = $$('[data-f]', filtro)
    var provas = $$('[data-provas] > li')
    filtro.hidden = false
    botoesFiltro.forEach(function (b) {
      b.addEventListener('click', function () {
        var f = b.getAttribute('data-f')
        aperta(botoesFiltro, b)
        provas.forEach(function (li) { li.hidden = !(f === 'all' || li.getAttribute('data-tipo') === f) })
      })
    })
  }

  // ------------------------------------------------------------- "Part 8 of the kart": o link abre a peça
  function abrePeca(hash) {
    var m = /^#(kart-part-\d)$/.exec(hash || '')
    var d = m && document.getElementById(m[1])
    if (d) d.open = true
  }
  $$('a[href^="#kart-part-"]').forEach(function (a) {
    a.addEventListener('click', function () { abrePeca(a.getAttribute('href')) })
  })
  window.addEventListener('hashchange', function () { abrePeca(location.hash) })
  abrePeca(location.hash)

  // ------------------------------------------------------------- o localizador de categoria
  var campoIdade = $('[data-idade-campo]')
  var campoPeso = $('[data-peso-campo]')
  ;[campoIdade, campoPeso].forEach(function (c) {
    if (c) c.addEventListener('input', function () { c.setAttribute('data-tocado', '1') })
  })
  var calc = $('[data-categoria]')
  if (calc) {
    var dob = $('[data-dob]', calc)
    var peso = $('[data-peso]', calc)
    var pesoUn = $('[data-peso-un]', calc)
    var altura = $('[data-altura]', calc)
    var alturaUn = $('[data-altura-un]', calc)
    var saida = $('[data-idade]', calc)
    var dica = $('[data-dica]', calc)
    var dica2 = $('[data-dica2]', calc)
    var classes = $$('[data-classes] > li', calc)
    var DICA = dica.textContent
    mostra($$('[data-so-js]', calc))
    calc.addEventListener('submit', function (ev) { ev.preventDefault() })
    var categoria = function () {
      // idade de corrida = a idade em 1º de janeiro de 2027 (não a do dia da prova)
      var p = dob.value.split('-').map(Number)
      var idade = p.length === 3 && p[0] ? 2027 - p[0] - ((p[1] > 1 || (p[1] === 1 && p[2] > 1)) ? 1 : 0) : null
      estado.idade = idade
      calc.classList.toggle('com-idade', idade !== null)
      var abertas = classes.filter(function (li) {
        var ok = idade !== null && idade >= +li.getAttribute('data-min') && idade <= +li.getAttribute('data-max')
        li.classList.toggle('aberta', ok)
        return ok
      })
      var nomes = abertas.map(function (li) { return $('strong', li).textContent })
      saida.textContent = idade === null ? '–' : String(idade)
      var pv = parseFloat(peso.value)
      var lb = isNaN(pv) ? null : (pesoUn.value === 'kg' ? pv / 0.4536 : pv)
      var hv = parseFloat(altura.value)
      var cm = isNaN(hv) ? null : (alturaUn.value === 'in' ? hv * 2.54 : hv)
      var partes = []
      if (idade === null) {
        dica.textContent = DICA
      } else {
        if (!abertas.length) {
          dica.textContent = idade < 7
            ? 'Under 7 on 1 January: too young for the SKUSA Winter classes. We can still run a winter programme on track.'
            : 'No SKUSA Winter class at this racing age. We set the right series with you.'
        } else if (abertas.length === 1) {
          dica.textContent = nomes[0] + ' is the class open at this racing age.'
        } else {
          dica.textContent = abertas.length + ' classes open: ' + nomes.join(', ') + '. We pick one on the scales and the stopwatch.'
        }
        if (lb !== null && abertas.length) {
          var minimo = Math.min.apply(null, abertas.map(function (li) { return +li.getAttribute('data-peso-lb') }))
          partes.push('Driver in gear: ' + Math.round(lb) + ' lb / ' + Math.round(lb * 0.4536) + ' kg. The kart makes up the rest of the ' +
            minimo + ' lb minimum; we check it on the scales and add ballast if needed.')
        }
        if (cm !== null) partes.push('Height: ' + Math.round(cm) + ' cm. It does not set the class; we use it to fit the seat, pedals and wheel (kart parts 1–3).')
      }
      dica2.textContent = partes.join(' ')
      if (campoIdade && !campoIdade.hasAttribute('data-tocado')) campoIdade.value = idade === null ? '' : String(idade)
      if (campoPeso && !campoPeso.hasAttribute('data-tocado')) campoPeso.value = isNaN(pv) ? '' : pv + ' ' + pesoUn.value
      desenha()
    }
    ;[dob, peso, pesoUn, altura, alturaUn].forEach(function (el) {
      el.addEventListener('input', categoria)
      el.addEventListener('change', categoria)
    })
  }

  // ------------------------------------------------------------- o plano (o formulário "Build your winter")
  var fins = $('[data-fins]')
  var chegada = $('[data-chegada]')
  var volta = $('[data-volta]')
  var piloto = $('[data-piloto]')
  var janelas = fins ? (fins.getAttribute('data-janelas') || '').split(' ').filter(Boolean).map(function (j) { return j.split('/') }) : []
  var diaDe = function (sel) { var op = sel && sel.options[sel.selectedIndex]; return op ? ms(op.getAttribute('data-dia')) : NaN }
  function plano() {
    var A = diaDe(chegada)
    var D = diaDe(volta)
    var avisos = []
    if (D < A) avisos.push('Fly-home date is before arrival. Check your dates.')
    var marcadas = fins ? $$('input[type="checkbox"]:checked', fins) : []
    var fora = false
    var tbc = false
    var casa = 0
    var motores = []
    marcadas.forEach(function (c) {
      if (ms(c.getAttribute('data-inicio')) < A || ms(c.getAttribute('data-fim')) > D + DIA) fora = true
      var m = c.getAttribute('data-motor')
      if (m && motores.indexOf(m) < 0) motores.push(m)
      if (c.getAttribute('data-tipo') === 'tbc') tbc = true
      if (c.getAttribute('data-tipo') === 'home') casa++
    })
    var testes = 0
    janelas.forEach(function (j) {
      var a = Math.max(ms(j[0]), A)
      var b = Math.min(ms(j[1]), D)
      if (b >= a) testes += Math.round((b - a) / DIA) + 1
    })
    if (motores.length > 1) {
      avisos.push('Mixed engines (' + motores.map(function (m) { return m.toUpperCase() }).join(' + ') + '). We will tell you if it is worth running both.')
    }
    if (fora) avisos.push('Some weekends fall outside your stay. Stretch the dates or drop them.')
    if (tbc) avisos.push('Rotax Winter Trophy dates not confirmed yet. We will keep you posted.')
    if (fins && !casa) avisos.push('No home-track rounds in the plan. We build the winter around the four SKUSA rounds at our track.')
    return {
      fins: marcadas.length,
      testes: testes,
      semanas: Math.max(0, Math.round((D - A) / (7 * DIA) + 0.15)),
      avisos: avisos,
      extras: $$('[data-extra]').filter(function (c) { return c.checked }).map(function (c) { return c.getAttribute('data-extra') }),
      nome: (piloto && piloto.value.trim()) || 'Your driver'
    }
  }
  var resumo = $('[data-resumo]')
  function desenhaResumo(p) {
    if (!resumo) return
    resumo.hidden = false
    $('[data-n-fins]', resumo).textContent = p.fins
    $('[data-n-testes]', resumo).textContent = p.testes
    $('[data-n-semanas]', resumo).textContent = p.semanas
    var ul = $('[data-alertas]', resumo)
    ul.textContent = ''
    p.avisos.forEach(function (a) {
      var li = document.createElement('li')
      li.textContent = a
      ul.appendChild(li)
    })
    ul.hidden = !p.avisos.length
  }

  // ------------------------------------------------------------- a estimativa: diária do kart do painel × dias de teste
  var est = $('[data-estimativa]')
  var karts = est ? $$('[data-kt]', est) : []
  var regua = est && $('[data-testes]', est)
  if (est) {
    mostra($$('[data-so-js]', est))
    est.addEventListener('submit', function (ev) { ev.preventDefault() })
    karts.forEach(function (b) {
      b.addEventListener('click', function () {
        estado.kartDaPessoa = true
        aperta(karts, b)
        desenha()
      })
    })
    if (regua) {
      regua.addEventListener('input', function () {
        estado.testesDaPessoa = +regua.value
        desenha()
      })
    }
  }
  function kartEscolhido() {
    // sem a pessoa escolher, a idade de corrida decide: abaixo de 7, o baby kart; senão, o 2-stroke da SKUSA
    if (!estado.kartDaPessoa && estado.idade !== null) {
      var auto = com(karts, 'data-kt', estado.idade < 7 ? 'baby' : '2s')
      if (auto) aperta(karts, auto)
    }
    return com(karts, 'aria-pressed', 'true')
  }
  function desenhaEstimativa(p) {
    if (!est) return
    var k = estado.testesDaPessoa === null ? Math.min(p.testes, 6) : Math.min(estado.testesDaPessoa, p.testes)
    if (regua) {
      regua.max = String(p.testes)
      regua.value = String(k)
      $('[data-testes-v]', est).textContent = k
      $('[data-testes-dica]', est).textContent = p.testes
        ? plural(p.testes, 'testing day falls', 'testing days fall') + ' inside your stay.'
        : 'No testing windows inside your stay yet. Stretch the dates in chapter 05.'
    }
    var kart = kartEscolhido()
    var nome = kart ? kart.getAttribute('data-nome') : ''
    var nota = $('[data-kt-nota]', est)
    if (nota && kart) nota.textContent = kart.getAttribute('data-nota')
    $('[data-sub-corrida]', est).textContent = plural(p.fins, 'race weekend', 'race weekends') + (nome ? ' · ' + nome : '') +
      ' · kart prep and trackside support'
    var linha = $('[data-linha-testes]', est)
    var preco = kart ? parseFloat(kart.getAttribute('data-preco')) : NaN
    if (linha) {
      linha.hidden = isNaN(preco)
      if (!isNaN(preco)) {
        $('[data-sub-testes]', est).textContent = k + ' × ' + usd(preco) + ' · ' + nome + ' · kart, maintenance, coach'
        $('[data-total-testes]', est).textContent = usd(k * preco)
      }
    }
    $$('[data-extra-sub]', est).forEach(function (s) {
      s.textContent = (p.extras.indexOf(s.getAttribute('data-extra-sub')) >= 0 ? 'In your plan' : 'Available on request') + s.getAttribute('data-resto')
    })
    $('[data-total]', est).textContent = isNaN(preco) || !k ? '–' : usd(k * preco)
    $('[data-total-nota]', est).hidden = !p.fins
    $('[data-quem]', est).textContent = p.nome + (nome ? ' · ' + nome : '') + ' · ' + plural(p.fins, 'race weekend', 'race weekends') + ' · ' +
      plural(k, 'testing day', 'testing days')
  }

  function desenha() {
    var p = plano()
    desenhaResumo(p)
    desenhaEstimativa(p)
  }
  var form = fins && fins.form
  if (form) {
    form.addEventListener('change', desenha)
    form.addEventListener('input', desenha)
  }

  // ------------------------------------------------------------- o link personalizado de hoje: ?driver=Nome&from=north
  var q = typeof URLSearchParams === 'function' ? new URLSearchParams(location.search) : null
  var paraQuem = q && (q.get('driver') || '').trim().slice(0, 40)
  if (paraQuem) {
    if (piloto && !piloto.value) piloto.value = paraQuem
    var preparado = $('[data-preparado]')
    if (preparado) {
      preparado.textContent = 'Prepared for ' + paraQuem + ' · Winter Season 2027'
      preparado.hidden = false
    }
  }
  if (botoesOrigem.length) poeOrigem((q && q.get('from')) || 'europe')
  desenha()
})()
