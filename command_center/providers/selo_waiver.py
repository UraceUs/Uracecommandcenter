"""Selo PAdES e carimbo de tempo RFC 3161 no PDF da waiver assinada aqui (#110, lacunas D-2 e G-3).

Antes, a única prova de que o PDF não mudou era o hash guardado no nosso próprio banco. Agora o PDF final sai
**selado**: uma assinatura digital PAdES (SHA-256) com o certificado de selo da URACE, de **certificação** (DocMDP
"nenhuma alteração"), no campo `URACE-Seal`, com o **carimbo de tempo de uma TSA externa** (RFC 3161, PAdES-B-T).
Mudar 1 byte do arquivo quebra o selo, e a hora do carimbo vem de terceiro, não do relógio do VPS.

Dono, 06/10 (#110): *certificado próprio da URACE + carimbo de tempo gratuito*. O Adobe mostra a identidade do
certificado próprio como "desconhecida" (não está na lista dele); a integridade e o carimbo aparecem válidos. O
certificado pago reconhecido pelo Adobe fica para depois.

- **Chave e certificados** em `~/.urace/waivers/selo/` (ou `CC_WAIVER_SEAL_DIR`), **nunca no repositório**:
  `seal-key.pem` (0600), `seal-cert.pem` e `root-cert.pem`. Quem gera é `manage.py selo-waiver criar`, no VPS.
  A chave da raiz é usada uma vez, para emitir o certificado de selo, e **não é guardada**: ninguém (nem quem
  invadir o VPS) emite outro selo com essa raiz. A raiz pública basta para conferir os PDFs, mesmo os antigos.
- **TSAs** em `CC_WAIVER_TSA` (lista separada por vírgula; padrão DigiCert e, se falhar, FreeTSA), 10 s cada.
- **Sem chave, ou com todas as TSAs fora**, a assinatura não acontece (`SeloIndisponivel`): o cliente lê
  "Online signing is temporarily unavailable…" e nada é gravado.
- A chave fica **fora do backup do SQLite** (#299): o backup dela é à parte (playbook geral, Site › Waiver).
"""
import hashlib
import io
import os
from datetime import datetime, timedelta, timezone

CAMPO = "URACE-Seal"
TSAS_PADRAO = ("http://timestamp.digicert.com", "https://freetsa.org/tsr")
TIMEOUT_TSA = 10                       # segundos por TSA
RESERVA = 65536                        # espaço do /Contents, em hex: até 32 KB de CMS (ele fica em 3 a 10 KB)
ARQUIVOS = {"chave": "seal-key.pem", "selo": "seal-cert.pem", "raiz": "root-cert.pem"}
ORGANIZACAO = "URACE.US INC"
VALIDADE_RAIZ_ANOS = 20
VALIDADE_SELO_ANOS = 10
MENSAGEM = ("Online signing is temporarily unavailable. Please try again in a few minutes, "
            "or sign the waiver in person at the track.")


class SeloIndisponivel(Exception):
    """O selo não está configurado ou nenhuma TSA respondeu. `motivo` é para a equipe (auditoria, Site › Waiver);
    o cliente lê só `MENSAGEM` (a rota devolve 503)."""

    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


def pasta():
    if os.environ.get("CC_WAIVER_SEAL_DIR"):
        return os.environ["CC_WAIVER_SEAL_DIR"]
    from command_center.providers import waiver_nativa
    return os.path.join(waiver_nativa.pasta(), "selo")


def tsas():
    lista = [u.strip() for u in (os.environ.get("CC_WAIVER_TSA") or "").split(",") if u.strip()]
    return lista or list(TSAS_PADRAO)


def _caminho(nome, onde=None):
    return os.path.join(onde or pasta(), ARQUIVOS[nome])


def _sha_der(cert):
    from cryptography.hazmat.primitives import serialization
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def impressao(sha):
    """O fingerprint como os programas mostram: AB:CD:… (maiúsculas, de 2 em 2)."""
    return ":".join(sha[i:i + 2] for i in range(0, len(sha), 2)).upper()


# ------------------------------------------------------------------ criar (manage.py selo-waiver criar)
def _nome(cn):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    return x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                      x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Florida"),
                      x509.NameAttribute(NameOID.LOCALITY_NAME, "Orlando"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, ORGANIZACAO),
                      x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def emitir(sujeito, emissor, chave_publica, chave_emissor, anos, ca=False, eku=None, emissor_cert=None):
    """Um certificado X.509 (raiz quando `ca`; de selo ou de TSA quando não). Também usado pelos testes."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    agora = datetime.now(timezone.utc)
    b = (x509.CertificateBuilder().subject_name(sujeito).issuer_name(emissor).public_key(chave_publica)
         .serial_number(x509.random_serial_number()).not_valid_before(agora - timedelta(hours=1))
         .not_valid_after(agora + timedelta(days=365 * anos))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=0 if ca else None), critical=True)
         .add_extension(x509.KeyUsage(digital_signature=not ca, content_commitment=not ca and not eku, key_encipherment=False,
                                      data_encipherment=False, key_agreement=False, key_cert_sign=ca, crl_sign=ca,
                                      encipher_only=False, decipher_only=False), critical=True)
         .add_extension(x509.SubjectKeyIdentifier.from_public_key(chave_publica), critical=False))
    if emissor_cert is not None:
        b = b.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(emissor_cert.public_key()), critical=False)
    if eku:
        b = b.add_extension(x509.ExtendedKeyUsage(eku), critical=True)
    return b.sign(chave_emissor, hashes.SHA256())


def _gravar(caminho, dados, modo):
    """Cria o arquivo com a permissão certa desde o primeiro byte, e nunca por cima de um que exista."""
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, modo)
    with os.fdopen(fd, "wb") as f:
        f.write(dados)
    os.chmod(caminho, modo)


def criar(onde=None):
    """Gera a raiz e o certificado de selo (EC P-256) em `onde` (padrão: `pasta()`). Nunca sobrescreve: com
    qualquer um dos três arquivos lá, levanta `FileExistsError` e não mexe em nada. A chave da raiz não é gravada.
    Devolve o que o comando imprime (fingerprints e validade)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    onde = onde or pasta()
    os.makedirs(onde, mode=0o700, exist_ok=True)
    os.chmod(onde, 0o700)
    existem = [n for n in ARQUIVOS.values() if os.path.exists(os.path.join(onde, n))]
    if existem:
        raise FileExistsError(f"já existe em {onde}: {', '.join(existem)}. Nada foi mudado.")
    k_raiz = ec.generate_private_key(ec.SECP256R1())
    raiz = emitir(_nome("URACE.US Waiver Seal Root"), _nome("URACE.US Waiver Seal Root"), k_raiz.public_key(), k_raiz,
                  VALIDADE_RAIZ_ANOS, ca=True)
    k_selo = ec.generate_private_key(ec.SECP256R1())
    selo = emitir(_nome("URACE.US Waiver Document Seal"), raiz.subject, k_selo.public_key(), k_raiz, VALIDADE_SELO_ANOS,
                  emissor_cert=raiz)
    del k_raiz                                                  # a chave da raiz não sai da memória
    _gravar(_caminho("chave", onde), k_selo.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                         serialization.NoEncryption()), 0o600)
    _gravar(_caminho("selo", onde), selo.public_bytes(serialization.Encoding.PEM), 0o644)
    _gravar(_caminho("raiz", onde), raiz.public_bytes(serialization.Encoding.PEM), 0o644)
    return {"dir": onde, "root_sha256": _sha_der(raiz), "seal_sha256": _sha_der(selo),
            "seal_not_after": selo.not_valid_after_utc.strftime("%Y-%m-%d"),
            "root_not_after": raiz.not_valid_after_utc.strftime("%Y-%m-%d")}


# ------------------------------------------------------------------ carregar e estado
def _carregar(onde=None):
    """(chave, certificado de selo, raiz) com `cryptography`, conferidos. Levanta `SeloIndisponivel` com o motivo."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    onde = onde or pasta()
    faltam = [n for n in ARQUIVOS.values() if not os.path.isfile(os.path.join(onde, n))]
    if faltam:
        raise SeloIndisponivel(f"selo não configurado: falta {', '.join(faltam)} em {onde} "
                               "(rode python3 -m command_center.manage selo-waiver criar)")
    if os.stat(_caminho("chave", onde)).st_mode & 0o077:
        raise SeloIndisponivel(f"a chave do selo ({_caminho('chave', onde)}) pode ser lida por outros usuários: chmod 600")
    try:
        with open(_caminho("chave", onde), "rb") as f:
            chave = serialization.load_pem_private_key(f.read(), password=None)
        with open(_caminho("selo", onde), "rb") as f:
            selo = x509.load_pem_x509_certificate(f.read())
        with open(_caminho("raiz", onde), "rb") as f:
            raiz = x509.load_pem_x509_certificate(f.read())
    except (OSError, ValueError, TypeError) as e:
        raise SeloIndisponivel(f"os arquivos do selo não abrem: {type(e).__name__}: {str(e)[:160]}")
    if not isinstance(chave, (ec.EllipticCurvePrivateKey, rsa.RSAPrivateKey)):
        raise SeloIndisponivel("a chave do selo não é EC nem RSA")
    pub = serialization.PublicFormat.SubjectPublicKeyInfo
    if chave.public_key().public_bytes(serialization.Encoding.DER, pub) != selo.public_key().public_bytes(serialization.Encoding.DER, pub):
        raise SeloIndisponivel("a chave do selo não é a do certificado de selo")
    try:
        selo.verify_directly_issued_by(raiz)
    except Exception:                                           # assinatura, emissor ou algoritmo que não batem
        raise SeloIndisponivel("o certificado de selo não foi emitido pela raiz guardada")
    agora = datetime.now(timezone.utc)
    if not (selo.not_valid_before_utc <= agora <= selo.not_valid_after_utc):
        raise SeloIndisponivel(f"o certificado de selo está fora da validade ({selo.not_valid_after_utc:%Y-%m-%d})")
    return chave, selo, raiz


def estado(onde=None):
    """O que Site › Waiver mostra e o que `ligar()` confere. Não fala com a TSA (isso é `selo-waiver conferir`)."""
    base = {"dir": onde or pasta(), "tsa": tsas(), "field": CAMPO}
    try:
        _chave, selo, raiz = _carregar(onde)
    except SeloIndisponivel as e:
        return {**base, "configured": False, "reason": e.motivo}
    return {**base, "configured": True, "reason": "selo configurado",
            "seal_subject": selo.subject.rfc4514_string(), "seal_sha256": _sha_der(selo),
            "seal_not_after": selo.not_valid_after_utc.strftime("%Y-%m-%d"), "root_sha256": _sha_der(raiz)}


def exigir():
    """Antes de gastar o código do e-mail: sem selo configurado, `SeloIndisponivel`."""
    _carregar()


# ------------------------------------------------------------------ selar
def _asn1(cert=None, chave=None):
    from asn1crypto import keys as akeys, x509 as ax509
    from cryptography.hazmat.primitives import serialization
    if cert is not None:
        return ax509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))
    return akeys.PrivateKeyInfo.load(chave.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                                         serialization.NoEncryption()))


def _carimbadores():
    """[(url, carimbador)] na ordem de `CC_WAIVER_TSA`. O teste troca por uma TSA falsa local (o CI não tem rede)."""
    from pyhanko.sign.timestamps.requests_client import RequestsHTTPTimeStamper
    return [(u, RequestsHTTPTimeStamper(u, timeout=TIMEOUT_TSA)) for u in tsas()]


def _token(selado):
    """O carimbo de tempo (ContentInfo DER) de dentro da assinatura e o TSTInfo dele."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    s = PdfFileReader(io.BytesIO(selado)).embedded_signatures[0]
    for attr in s.signer_info["unsigned_attrs"] or ():
        if attr["type"].native == "signature_time_stamp_token":
            tok = attr["values"][0]
            return tok.dump(), tok["content"]["encap_content_info"]["content"].parsed, tok
    raise ValueError("a assinatura saiu sem o carimbo de tempo")


def _cert_da_tsa(tok):
    try:
        sid = tok["content"]["signer_infos"][0]["sid"].chosen
        return next(c.chosen for c in tok["content"]["certificates"] if c.chosen.serial_number == sid["serial_number"].native)
    except Exception:                             # sem o certificado no token (certReq atendido de outro jeito)
        return None


def selar(pdf):
    """Sela o PDF (PAdES-B-T, certificação sem alterações) com a primeira TSA que responder.
    Devolve (pdf selado, info para a trilha, token DER do carimbo). Sem selo ou sem TSA: `SeloIndisponivel`."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers
    from pyhanko_certvalidator.registry import SimpleCertificateStore
    chave, selo, raiz = _carregar()
    assinante = signers.SimpleSigner(signing_cert=_asn1(selo), signing_key=_asn1(chave=chave),
                                     cert_registry=SimpleCertificateStore.from_certs([_asn1(raiz)]))
    meta = signers.PdfSignatureMetadata(
        field_name=CAMPO, certify=True, docmdp_permissions=fields.MDPPerm.NO_CHANGES,
        subfilter=fields.SigSeedSubFilter.PADES, md_algorithm="sha256", location="Orlando, FL",
        reason="URACE.US tamper-evident seal of the signed waiver", contact_info="support@urace.us")
    erros = []
    for url, carimbador in _carimbadores():
        try:
            saida = signers.PdfSigner(meta, signer=assinante, timestamper=carimbador).sign_pdf(
                IncrementalPdfFileWriter(io.BytesIO(pdf)), bytes_reserved=RESERVA)
            selado = saida.getvalue()
            der, tst, tok = _token(selado)
        except Exception as e:                    # rede, resposta ruim da TSA, token grande demais: tenta a próxima
            erros.append(f"{url}: {type(e).__name__}: {str(e)[:160]}")
            continue
        tsa = _cert_da_tsa(tok)
        info = {"standard": "PAdES-B-T", "field": CAMPO, "certification": "DocMDP: no changes allowed",
                "digest": "SHA-256", "tsa_url": url,
                "gen_time": tst["gen_time"].native.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "serial": str(tst["serial_number"].native), "policy": tst["policy"].native,
                "token_sha256": hashlib.sha256(der).hexdigest(),
                "tsa_subject": tsa.subject.human_friendly if tsa else None,
                "seal_cert_sha256": _sha_der(selo), "root_cert_sha256": _sha_der(raiz)}
        return selado, info, der
    raise SeloIndisponivel("nenhuma TSA deu o carimbo de tempo: " + " | ".join(erros or ["nenhuma TSA configurada"]))


# ------------------------------------------------------------------ conferir
def _raizes_publicas():
    """As raízes do certifi (as mesmas que o `requests` usa), para conferir o carimbo de uma TSA pública."""
    try:
        import certifi
        from asn1crypto import pem, x509 as ax509
        with open(certifi.where(), "rb") as f:
            return [ax509.Certificate.load(der) for _t, _h, der in pem.unarmor(f.read(), multiple=True)]
    except Exception:
        return []


def validar(pdf, raizes=None):
    """Confere o selo como o `pyhanko sign validate`: íntegro, válido, confiável (pela raiz da URACE), cobertura,
    DocMDP e o carimbo. `raizes`: certificados (cryptography) a confiar além da raiz guardada e das públicas."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    confiar = [_asn1(c) for c in (raizes or [])]
    if os.path.isfile(_caminho("raiz")):
        from cryptography import x509
        with open(_caminho("raiz"), "rb") as f:
            confiar.append(_asn1(x509.load_pem_x509_certificate(f.read())))
    try:
        sigs = PdfFileReader(io.BytesIO(pdf)).embedded_signatures
        if len(sigs) != 1:
            return {"ok": False, "intact": False, "reason": f"{len(sigs)} assinaturas no PDF; esperava 1"}
        s = sigs[0]
        vc = ValidationContext(trust_roots=confiar + _raizes_publicas(), allow_fetching=False)
        st = validate_pdf_signature(s, signer_validation_context=vc, ts_validation_context=vc)
    except Exception as e:                       # arquivo mexido a ponto de não abrir: não é íntegro
        return {"ok": False, "intact": False, "reason": f"{type(e).__name__}: {str(e)[:200]}"}
    ts = st.timestamp_validity
    carimbo = None if ts is None else {"intact": ts.intact, "valid": ts.valid, "trusted": ts.trusted,
                                       "time": ts.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    docmdp = s.docmdp_level.name if s.docmdp_level is not None else None
    cobertura = st.coverage.name if st.coverage is not None else None
    # o carimbo tem de estar íntegro e válido; "confiável" depende de a raiz da TSA estar na lista (a FreeTSA tem raiz
    # própria, fora do certifi) e só é informado
    ok = bool(st.intact and st.valid and st.trusted and st.docmdp_ok and cobertura == "ENTIRE_FILE"
              and carimbo and carimbo["intact"] and carimbo["valid"])
    return {"ok": ok, "field": s.field_name, "intact": st.intact, "valid": st.valid, "trusted": st.trusted,
            "coverage": cobertura, "docmdp": docmdp,
            "timestamp": carimbo, "reason": "selo íntegro e válido" if ok else "selo não confere"}


def pdf_de_teste():
    """Um PDF de uma página para `selo-waiver conferir` (não é waiver, não leva dado de ninguém)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=letter)
    cv.setTitle("URACE seal check")
    cv.drawString(72, 720, "URACE.US seal and time-stamp check. Not a waiver.")
    cv.drawString(72, 700, f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    cv.showPage()
    cv.save()
    return buf.getvalue()
