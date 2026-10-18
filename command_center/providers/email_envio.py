"""Envio de e-mail pela API do Gmail, da caixa da URACE (#108).

Usado pelo código de verificação da área do cliente: confirmar o e-mail da conta e o código de
uma vez na hora de assinar a waiver. A caixa é a de `CC_EMAIL_REMETENTE`, por padrão `noreply`
(dono, 06/10: "uma caixa nova só para isso"), com o token gravado por
`python3 adminai/google_auth.py --conta noreply`, que só pede `gmail.send`.

Teste e end-to-end nunca mandam e-mail de verdade: com `CC_EMAIL_FAKE=<arquivo>` a mensagem vai
para esse arquivo (uma linha JSON por e-mail) e nada sai da máquina.

#114: com `anexos` (a cópia da waiver assinada), o e-mail vai como `multipart/mixed` pelo endpoint de upload
do Gmail (`message/rfc822`, até 35 MB), não pelo `raw` em JSON. No arquivo do teste ficam o nome, o tipo, o
tamanho e o SHA-256 de cada anexo (nunca o conteúdo). `responder_para` põe o Reply-To (a cópia sai do
noreply@ e a resposta cai no support@).
"""
import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from email.message import EmailMessage

CAIXAS = {"noreply": "noreply@urace.us", "support": "support@urace.us", "urace": "urace@urace.us"}


def remetente():
    conta = (os.environ.get("CC_EMAIL_REMETENTE") or "noreply").strip().lower()
    return conta if conta in CAIXAS else "noreply"


class ErroEnvio(RuntimeError):
    """O e-mail não saiu (sem token, sem rede, Gmail recusou). A mensagem não carrega segredo."""


GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_UPLOAD = "https://gmail.googleapis.com/upload/gmail/v1/users/me/messages/send?uploadType=media"
MAX_ANEXOS = 25 * 1024 * 1024        # o Gmail aceita 35 MB no upload; a mensagem em base64 cresce ~37%


def mensagem(para, assunto, texto, html=None, anexos=None, responder_para=None):
    """A mensagem MIME. `anexos`: [(nome do arquivo, bytes, tipo MIME)]."""
    conta = remetente()
    msg = EmailMessage()
    msg["From"] = f"URACE.US <{CAIXAS[conta]}>"
    msg["To"] = para
    msg["Subject"] = assunto
    if responder_para:
        msg["Reply-To"] = responder_para
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    if sum(len(b) for _n, b, _t in anexos or ()) > MAX_ANEXOS:
        raise ErroEnvio("anexo grande demais para o Gmail")
    for nome, dados, tipo in anexos or ():
        principal, _, sub = tipo.partition("/")
        msg.add_attachment(dados, maintype=principal, subtype=sub, filename=nome)
    return conta, msg


def enviar(para, assunto, texto, html=None, anexos=None, responder_para=None):
    """Manda um e-mail de texto. Devolve o id da mensagem no Gmail (ou do arquivo, no teste). #305: com `html`, vai
    também a versão com a identidade da URACE (`email_marca`); quem lê só texto recebe o texto. #114: `anexos`
    [(nome, bytes, tipo)] e `responder_para` (Reply-To)."""
    conta, msg = mensagem(para, assunto, texto, html, anexos, responder_para)
    falso = os.environ.get("CC_EMAIL_FAKE")
    if falso:
        with open(falso, "a", encoding="utf-8") as f:
            f.write(json.dumps({"from": CAIXAS[conta], "to": para, "subject": assunto, "text": texto,
                                **({"html": html} if html else {}), **({"reply_to": responder_para} if responder_para else {}),
                                **({"attachments": [{"filename": n, "content_type": t, "size": len(b),
                                                     "sha256": hashlib.sha256(b).hexdigest()} for n, b, t in anexos]}
                                   if anexos else {})}) + "\n")
        return f"fake-{os.path.getsize(falso)}"
    try:
        from adminai import google_auth
        tok = google_auth.access_token(conta)
    except Exception as e:                                        # noqa: BLE001 — sem token no VPS
        raise ErroEnvio(f"sem token do Google para {CAIXAS[conta]}: {str(e)[:160]}")
    if anexos:                                   # #114: com anexo, a mensagem inteira pelo upload (sem o teto do JSON)
        req = urllib.request.Request(GMAIL_UPLOAD, data=msg.as_bytes(), method="POST")
        req.add_header("Content-Type", "message/rfc822")
    else:
        corpo = json.dumps({"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).encode()
        req = urllib.request.Request(GMAIL, data=corpo, method="POST")
        req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}").get("id")
    except urllib.error.HTTPError as e:
        raise ErroEnvio(f"Gmail recusou o envio: HTTP {e.code}")
    except urllib.error.URLError as e:
        raise ErroEnvio(f"Gmail sem conexão: {e.reason}")
