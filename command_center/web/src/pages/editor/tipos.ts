/* Editor do site como o Canva (#315): os tipos do modelo, o mesmo que o servidor guarda (vitrine/editor.py). */
export type Tipo = 'titulo' | 'texto' | 'imagem' | 'botao' | 'lista' | 'espaco' | 'karts' | 'produtos' | 'cartoes' | 'faq'
export interface Faq { pergunta: string; resposta: string }
export interface W { id: string; tipo: Tipo; texto?: string; nivel?: number; tamanho?: string; cor?: string; alinhar?: string; html?: string
  src?: string; alt?: string; forma?: string; largura?: number; altura?: number; legenda?: string; link?: string; estilo?: string
  itens?: (string | Faq)[]; categoria?: string; quantos?: number; pagina?: string }
export interface Secao { id: string; tipo: 'secao'; fundo: string; espaco: string; colunas: number; itens: W[][] }
/** A faixa da página do código. `textos` (etapa 4): as trocas do texto dela, pela chave da folha
 *  (`<tag>.<n>:<hash8>`, a que a prévia põe em `data-ed-t`). */
/** `ancora` (revisão do #337): o que acha a faixa na página do código (o `id` ou o `aria-labelledby` dela), não a
 *  posição; `indice` -1 é a faixa que saiu da página (fica no lugar, sem desenho, e as trocas dela são órfãs). */
export interface Original { id: string; tipo: 'original'; indice: number; oculto: boolean; ancora?: string; textos?: Record<string, string> }
export type Item = Secao | Original
export interface Conteudo { itens: Item[] }
/** Os dados da página (fora da prévia): o título da aba, a descrição e o endereço. */
export interface Seo { title: string; description: string; path: string }
/** O que o desfazer guarda: a página e os dados dela. */
export interface Doc { c: Conteudo; seo: Seo }
export interface Pagina { id: number; path: string; base: string | null; title: string; description: string; draft: Conteudo
  published: Conteudo | null; estado: 'rascunho' | 'publicada' | 'mudou'; published_at: string | null; updated_at: string | null; rev: number }
export interface Saida { pagina: Pagina; problemas: string[]; originais: string[]; previa: string
  erros?: Record<string, string>; secoes?: { id: string; html: string }[]
  /** As trocas de texto das faixas originais que não acham mais o texto (a página do código mudou). */
  orfaos?: Record<string, string[]> }
/** O que está selecionado: um elemento (`w`), uma seção, nova ou original (`s`), ou um texto de uma faixa original
 *  (`t`, com o id `<faixa>/<chave>`, ex.: `o0/h1.0:1a2b3c4d`). */
export type Sel = { tipo: 'w' | 's' | 't'; id: string } | null
/** Onde um elemento cai: numa coluna de uma seção (antes do índice `i`), ou numa seção nova na posição `i` da página. */
export type Destino = { tipo: 'col'; sid: string; c: number; i: number } | { tipo: 'nova'; i: number }
