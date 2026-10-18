/* A data que o cliente lê ("Oct 17, 2026"), sempre no dia da Flórida (America/New_York).
 * Data sem hora (AAAA-MM-DD, como a validade da waiver) é o dia do calendário: vira meio-dia **UTC**, que cai no
 * mesmo dia em Nova York. Com meio-dia local, um navegador em UTC+9 ou mais (Tóquio, Auckland) passava da meia-noite
 * de Nova York para trás e mostrava a véspera (revisão do #332). Data com hora segue o instante. */
export const dataUS = (iso: string | null | undefined): string => iso
  ? new Date(iso.length === 10 ? iso + 'T12:00:00Z' : iso)
    .toLocaleDateString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric' })
  : '—'
