/* O menu em dropdown e as animações do site (#394). Pouco JS, sem biblioteca.
 *
 * - Menu do computador: cada grupo abre no hover (com um pequeno atraso para não piscar), no clique do ⌄ e no
 *   teclado (Enter/Espaço no botão; Esc fecha e devolve o foco); clique fora fecha. Sem este script, o CSS abre
 *   a caixa no hover e no foco, e o menu do celular (um <details>) funciona do mesmo jeito.
 * - Topo: sobre a foto do topo, a barra fica transparente; ao rolar, volta o fundo escuro.
 * - Seções que surgem ao rolar (uma vez), só as que começam abaixo da tela; sem IntersectionObserver ou com
 *   prefers-reduced-motion, nada é escondido.
 * - Carrossel dos campeões no celular: setas além do arrastar (scroll-snap). */
(function () {
  'use strict'
  var calmo = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches

  // ------------------------------------------------------------- menu do computador
  var menu = document.querySelector('[data-menu]')
  if (menu) {
    menu.classList.add('menu-js')
    var grupos = [].slice.call(menu.querySelectorAll('[data-grupo]'))
    var abre = function (g, sim) {
      clearTimeout(g._t)
      if (!sim) g._hover = false
      g.classList.toggle('aberto', sim)
      g.querySelector('.grupo-abre').setAttribute('aria-expanded', sim ? 'true' : 'false')
    }
    var fechaOutros = function (g) { grupos.forEach(function (o) { if (o !== g) abre(o, false) }) }
    grupos.forEach(function (g) {
      var botao = g.querySelector('.grupo-abre')
      g.addEventListener('pointerenter', function (ev) {
        if (ev.pointerType !== 'mouse') return
        clearTimeout(g._t)
        g._t = setTimeout(function () { fechaOutros(g); abre(g, true); g._hover = true }, 90)
      })
      g.addEventListener('pointerleave', function (ev) {
        if (ev.pointerType !== 'mouse') return
        clearTimeout(g._t)
        g._t = setTimeout(function () { abre(g, false) }, 220)
      })
      botao.addEventListener('click', function () {
        // aberto pelo hover, o clique no ⌄ não fecha na cara de quem chegou com o mouse: deixa aberto
        var sim = g._hover || !g.classList.contains('aberto')
        g._hover = false
        fechaOutros(g)
        abre(g, sim)
      })
      g.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape' && g.classList.contains('aberto')) {
          abre(g, false)
          botao.focus()
        } else if (ev.key === 'ArrowDown' && ev.target === botao) {
          ev.preventDefault()
          abre(g, true)
          var primeiro = g.querySelector('.grupo-itens a')
          if (primeiro) primeiro.focus()
        }
      })
      g.addEventListener('focusout', function (ev) {
        if (!ev.relatedTarget || !g.contains(ev.relatedTarget)) abre(g, false)
      })
    })
    document.addEventListener('click', function (ev) {
      if (!menu.contains(ev.target)) grupos.forEach(function (g) { abre(g, false) })
    })
  }

  // ------------------------------------------------------------- menu do celular: Esc fecha
  var cel = document.querySelector('.menu-cel')
  if (cel) {
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && cel.open) {
        cel.open = false
        cel.querySelector('summary').focus()
      }
    })
    cel.addEventListener('click', function (ev) {
      if (ev.target.closest && ev.target.closest('a')) cel.open = false     // link da mesma página (#âncora)
    })
  }

  // ------------------------------------------------------------- topo transparente sobre a foto
  var topo = document.querySelector('[data-topo]')
  var temHas = window.CSS && CSS.supports && CSS.supports('selector(:has(*))')
  if (topo && temHas && document.querySelector('body > main > .hero:first-child')) {
    var pedido = false
    var marca = function () {
      pedido = false
      topo.classList.toggle('sobre-foto', window.scrollY < 24)
    }
    marca()
    window.addEventListener('scroll', function () {
      if (!pedido) { pedido = true; window.requestAnimationFrame(marca) }
    }, { passive: true })
  }

  // ------------------------------------------------------------- a busca da loja pelo ícone (/store/#loja-s)
  if (window.location.hash === '#loja-s') {
    var busca = document.getElementById('loja-s')
    if (busca) busca.focus({ preventScroll: true })
  }

  // ------------------------------------------------------------- o destaque leve do "Book now"
  if (!calmo) document.querySelectorAll('.btn-reservar').forEach(function (b) { b.classList.add('pulsa') })

  // ------------------------------------------------------------- seções que surgem ao rolar
  if (!calmo && 'IntersectionObserver' in window) {
    var olho = new IntersectionObserver(function (vistos) {
      vistos.forEach(function (v) {
        if (v.isIntersecting) { v.target.classList.add('visto'); olho.unobserve(v.target) }
      })
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 })
    var alto = window.innerHeight || document.documentElement.clientHeight
    document.querySelectorAll('main > section').forEach(function (s) {
      if (s.getBoundingClientRect().top > alto) { s.classList.add('surge'); olho.observe(s) }
    })
  }

  // ------------------------------------------------------------- carrossel dos campeões
  document.querySelectorAll('.campeoes').forEach(function (fila, i) {
    if (!fila.id) fila.id = 'campeoes-' + (i + 1)
    var setas = document.createElement('div')
    setas.className = 'carrossel-setas pronto'
    var seta = function (rotulo, texto, lado) {
      var b = document.createElement('button')
      b.type = 'button'
      b.className = 'carrossel-seta'
      b.setAttribute('aria-label', rotulo)
      b.setAttribute('aria-controls', fila.id)
      b.textContent = texto
      b.addEventListener('click', function () {
        fila.scrollBy({ left: lado * Math.max(fila.clientWidth * 0.8, 160), behavior: calmo ? 'auto' : 'smooth' })
      })
      setas.appendChild(b)
      return b
    }
    var volta = seta('Previous', '‹', -1)
    var vai = seta('Next', '›', 1)
    var marca = function () {
      volta.disabled = fila.scrollLeft <= 2
      vai.disabled = fila.scrollLeft + fila.clientWidth >= fila.scrollWidth - 2
    }
    fila.addEventListener('scroll', marca, { passive: true })
    window.addEventListener('resize', marca)
    fila.parentNode.insertBefore(setas, fila)
    marca()
  })
})()
