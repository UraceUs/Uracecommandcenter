// Fora de Portal.tsx: arquivo de componente só exporta componente (#433).
/** #164: o endereço das páginas do site (Arrive and Drive, início). No próprio site é o mesmo host;
 * no my.urace.us e no ops.urace.us, até a troca do DNS do urace.us, é o novo.urace.us. */
export function siteUrl(caminho = '/') {
  const h = typeof location !== 'undefined' ? location.hostname : ''
  return (h === 'my.urace.us' || h === 'ops.urace.us' ? 'https://novo.urace.us' : '') + caminho
}
