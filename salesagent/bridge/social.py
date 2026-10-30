"""Rede social (Instagram, Facebook, WhatsApp pelo Kommo): o que é evento da rede e quem já é aluno.

Dono, 30/10 (#523), depois de ver o robô responder "Still working on the answer to "Mentioned you in
their story"" a um aluno de 13 anos: comentário em foto e DM são do robô, aluno e cliente também ("fala
tbm"), mas cada um do jeito certo.
- Menção em story: o Kommo entrega como mensagem ("Mentioned you in their story"). Não é pergunta: um
  obrigado curto, uma vez por dia, sem venda.
- Reação e curtida: nada a responder.
- Comentário curto ("10/10", "Racing🤩", "Cant wait!"): resposta de social media, sem qualificar.
- Aluno ou cliente: o robô atende, mas não qualifica nem vende; agenda e pagamento vão para o time.
"""
import re

_MENCAO = re.compile(
    r"^\W*(mentioned you in (their|his|her|a) (story|stories)|replied to your story|"
    r"te (mencionou|marcou)( n[oa]| em)? (seu |sua )?(story|stories|hist[óo]ria)|respondeu (ao|a) (seu|sua) "
    r"(story|hist[óo]ria)|te mencion[óo] en su historia|respondi[óo] a tu historia)\W*$", re.I)
_REACAO = re.compile(
    r"^\W*(reacted .{0,12} to your (message|story|post)|liked (a|your) (message|story|post)|"
    r"reagiu .{0,12} (a|à) (sua|uma) mensagem|curtiu (a|sua|uma) (mensagem|story|publica[cç][aã]o)|"
    r"reaccion[óo] .{0,12} a tu mensaje|le gust[óo] tu mensaje)\W*$", re.I)
_ALUNO = re.compile(
    r"(i (already )?(do|take|have) (coaching|classes|lessons|training) with you|"
    r"i('m| am) (already )?(a|your) (student|client|customer)|"
    r"(already|i) (train|race|practice|do coaching) with you|"
    r"j[aá] (fa[cç]o|treino|corro|sou)\b.{0,30}(com voc[eê]s|urace|alun[oa]|cliente)|"
    r"sou (alun[oa]|cliente)\b|"
    r"ya (entreno|soy alumn[oa]|soy cliente))", re.I)
_EMOJI_OU_SINAL = re.compile(r"^[\W\d_]*$")
_EMOJI = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]")
_ELOGIO = re.compile(
    r"\b(lol|lmao|haha+|kkk+|rs+|nice|cool|fire|sick|goat|wow|amazing|awesome|love( it)?|beautiful|insane|"
    r"can'?t wait|lets? go+|racing|bora+|top|show|massa|demais|incr[ií]vel|lindo|perfeito|que (top|massa|show)|"
    r"\d+\s*/\s*10|brutal|vamos+|qu[eé] (bueno|chido))\b", re.I)

AGRADECIMENTO_MENCAO = {
    "pt": "Valeu pela menção! 🙌🏁",
    "en": "Thanks for the shoutout! 🙌🏁",
    "es": "¡Gracias por la mención! 🙌🏁",
}

CONTEXTO_ALUNO = (
    "ESTA PESSOA JÁ É ALUNO OU CLIENTE DA URACE. Não faça triagem (idade, experiência, objetivo), não ofereça "
    "a call de vendas nem link de reserva ou de preço. Atenda como o time atende um aluno: curto, caloroso, "
    "sobre o que ela disse. Sessão marcada, agenda, troca de horário, pagamento ou invoice: diga que o time "
    "confirma por aqui e use [[escalate]]. Corrida ou treino que vem aí: torça junto.\n")

CONTEXTO_SOCIAL = (
    "ESTA MENSAGEM É REAÇÃO OU COMENTÁRIO CURTO (elogio, emoji, nota, \"can't wait\"), NÃO UMA PERGUNTA. "
    "Responda como o social media da URACE: uma frase curta e simpática sobre o que a pessoa disse, no tom "
    "dela. Sem perguntar idade, experiência ou para quem é, sem preço e sem link.\n")


def evento_da_rede(texto):
    """"mencao", "reacao" ou None (mensagem de verdade)."""
    t = (texto or "").strip()
    if _MENCAO.match(t):
        return "mencao"
    if _REACAO.match(t):
        return "reacao"
    return None


def diz_que_ja_e_aluno(texto):
    return bool(_ALUNO.search(texto or ""))


def curta(texto):
    """Comentário ou reação em texto: só emoji/sinal, ou até 5 palavras sem pergunta com emoji ou elogio
    ("Racing🤩", "10/10", "lol i could tell"). "Get a quote" e "Oi" não entram: são conversa."""
    t = (texto or "").strip()
    if not t:
        return False
    if _EMOJI_OU_SINAL.match(t):
        return True
    return "?" not in t and len(t.split()) <= 5 and bool(_EMOJI.search(t) or _ELOGIO.search(t))


def agradecimento(lang):
    return AGRADECIMENTO_MENCAO.get(lang, AGRADECIMENTO_MENCAO["en"])
