// Fora de Contador.tsx: arquivo de componente só exporta componente (#433).
import type { Contador } from './api'

/** A linha que o dono pediu: "This month: X of Y sessions used · Z left · resets on the 1st". */
export const linhaDoMes = (k: Contador) =>
  `This month: ${k.used} of ${k.sessions_per_month} session${k.sessions_per_month === 1 ? '' : 's'} used · ${k.left} left · resets on the 1st`
