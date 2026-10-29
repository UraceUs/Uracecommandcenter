/* #460: as medidas do piloto (as chaves da área do cliente) e a idade, usadas no card do cliente e no do serviço */
import { tr } from '../i18n'

export const TAMANHOS: [string, string][] = [['suit_size', tr("Macacão")], ['helmet_size', tr("Capacete")], ['glove_size', tr("Luva")], ['shoe_size', tr("Sapato")]]
export const CORPO: [string, string, string][] = [['height_in', tr("Altura"), 'in'], ['weight_lb', tr("Peso"), 'lb'], ['chest_in', tr("Peito"), 'in'],
  ['waist_in', tr("Cintura"), 'in'], ['hips_in', tr("Quadril"), 'in'], ['inseam_in', tr("Entreperna"), 'in'], ['sleeve_in', tr("Manga"), 'in']]

export function idade(dob?: string | null) {
  if (!dob) return null
  const d = new Date(dob.slice(0, 10) + 'T12:00:00Z'); if (isNaN(d.getTime())) return null
  const h = new Date(); let a = h.getFullYear() - d.getFullYear()
  if (h.getMonth() < d.getMonth() || (h.getMonth() === d.getMonth() && h.getDate() < d.getDate())) a--
  return a
}

export const CHAVES_MEDIDAS = [...TAMANHOS, ...CORPO.map(([k, rot]) => [k, rot] as [string, string])]
