// Fora de Cartao.tsx: arquivo de componente só exporta componente (#433).
/** As iniciais do nome: "Marina Costa" → "MC"; sem nome, "#". */
export function iniciais(nome?: string | null) {
  const p = (nome || '').replace(/[^\p{L}\p{N}\s]/gu, ' ').trim().split(/\s+/).filter(Boolean)
  return ((p[0]?.[0] || '') + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase() || '#'
}
