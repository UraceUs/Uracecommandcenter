/* O contador regressivo das páginas por blocos (#502): dias, horas, minutos e segundos até `data-alvo`. Sem JavaScript,
 * a página mostra a data por extenso (o rótulo embaixo do contador). Só texto muda: nada se move. */
(function () {
  'use strict'
  var contadores = document.querySelectorAll('.contador[data-alvo]')
  if (!contadores.length) return
  function pinta() {
    var agora = Date.now()
    Array.prototype.forEach.call(contadores, function (el) {
      var alvo = new Date(el.getAttribute('data-alvo')).getTime()
      if (isNaN(alvo)) return
      var s = Math.max(0, Math.floor((alvo - agora) / 1000))
      var v = { d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60), s: s % 60 }
      Object.keys(v).forEach(function (k) {
        var n = el.querySelector('[data-n="' + k + '"]')
        if (n) n.textContent = String(v[k])
      })
    })
  }
  pinta()
  setInterval(pinta, 1000)
})()
