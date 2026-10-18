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
- **Só vale carimbo de TSA conhecida** (revisão do #335): as raízes de TSA são **fixas**, a DigiCert Trusted Root G4
  (pela impressão SHA-256, do certifi) e os `.pem` da pasta `tsa/` do selo (ou `CC_WAIVER_TSA_ROOTS`), onde entra a
  raiz pública da FreeTSA. Logo depois de selar, o carimbo é conferido: de TSA desconhecida, ou com a hora a mais de
  5 min do relógio do VPS (um carimbo falso ou atrasado pelo caminho, já que a DigiCert é HTTP), passa para a próxima.
- **Conferir** usa dois contextos: o selo só vale pela raiz da URACE (e o certificado tem de ser emitido por ela); o
  carimbo só pelas raízes de TSA. Uma CA pública qualquer não "sela" uma waiver.
- **Sem chave, ou com todas as TSAs fora**, a assinatura não acontece (`SeloIndisponivel`): o cliente lê
  "Online signing is temporarily unavailable…" e nada é gravado.
- A chave fica **fora do backup do SQLite** (#299): o backup dela é à parte (playbook geral, Site › Waiver).
"""
import hashlib
import io
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

CAMPO = "URACE-Seal"
TSAS_PADRAO = ("http://timestamp.digicert.com", "https://freetsa.org/tsr")
TIMEOUT_TSA = 10                       # segundos por TSA
RESERVA = 65536                        # espaço do /Contents, em hex: até 32 KB de CMS (ele fica em 3 a 10 KB)
ARQUIVOS = {"chave": "seal-key.pem", "selo": "seal-cert.pem", "raiz": "root-cert.pem"}
ORGANIZACAO = "URACE.US INC"
VALIDADE_RAIZ_ANOS = 20
VALIDADE_SELO_ANOS = 10
DESVIO_MAX = timedelta(minutes=5)      # entre a hora do carimbo e o relógio do VPS (e a hora que o selo declara)
# Raízes públicas de TSA aceitas sem arquivo: a da DigiCert (timestamp.digicert.com), pela impressão SHA-256 no certifi.
RAIZES_TSA_FIXAS = {"552f7bdcf1a7af9e6ce672017f4f12abf77240c78e761ac203d1d9d20ac89988": "DigiCert Trusted Root G4"}
MENSAGEM = ("Online signing is temporarily unavailable. Please try again in a few minutes, "
            "or sign the waiver in person at the track.")


class SeloIndisponivel(Exception):
    """O selo não está configurado ou nenhuma TSA respondeu. `motivo` é para a equipe (auditoria); `codigo` é o que a
    tela traduz (Site › Waiver); o cliente lê só `MENSAGEM` (a rota devolve 503)."""

    def __init__(self, motivo, codigo="tsa"):
        super().__init__(motivo)
        self.motivo = motivo
        self.codigo = codigo


def pasta():
    if os.environ.get("CC_WAIVER_SEAL_DIR"):
        return os.environ["CC_WAIVER_SEAL_DIR"]
    from command_center.providers import waiver_nativa
    return os.path.join(waiver_nativa.pasta(), "selo")


def tsas():
    lista = [u.strip() for u in (os.environ.get("CC_WAIVER_TSA") or "").split(",") if u.strip()]
    return lista or list(TSAS_PADRAO)


def sem_credencial(texto):
    """A URL da TSA (ou uma mensagem de erro com ela) sem usuário e senha: `https://***@host/…`. É o que a tela, a
    trilha e a auditoria mostram."""
    import re
    return re.sub(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s]*@", r"\1***@", str(texto))


def pasta_raizes_tsa():
    return os.environ.get("CC_WAIVER_TSA_ROOTS") or os.path.join(pasta(), "tsa")


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
    existem = [n for n in ARQUIVOS.values() if os.path.exists(os.path.join(onde, n))]
    if existem:
        raise FileExistsError(f"já existe em {onde}: {', '.join(existem)}. Nada foi mudado.")
    os.chmod(onde, 0o700)                                       # só depois de ver que a pasta é nova para o selo
    k_raiz = ec.generate_private_key(ec.SECP256R1())
    raiz = emitir(_nome("URACE.US Waiver Seal Root"), _nome("URACE.US Waiver Seal Root"), k_raiz.public_key(), k_raiz,
                  VALIDADE_RAIZ_ANOS, ca=True)
    k_selo = ec.generate_private_key(ec.SECP256R1())
    selo = emitir(_nome("URACE.US Waiver Document Seal"), raiz.subject, k_selo.public_key(), k_raiz, VALIDADE_SELO_ANOS,
                  emissor_cert=raiz)
    del k_raiz                                                  # a chave da raiz não sai da memória
    gravados = []
    try:                                                        # os três ou nenhum: chave sem certificado travaria o criar
        for nome, dados, modo in (
                ("chave", k_selo.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()), 0o600),
                ("selo", selo.public_bytes(serialization.Encoding.PEM), 0o644),
                ("raiz", raiz.public_bytes(serialization.Encoding.PEM), 0o644)):
            _gravar(_caminho(nome, onde), dados, modo)
            gravados.append(_caminho(nome, onde))
    except BaseException:
        for c in gravados:
            try:
                os.chmod(c, 0o600)
                os.remove(c)
            except OSError:
                pass
        raise
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
                               "(rode python3 -m command_center.manage selo-waiver criar)", "missing")
    if os.stat(_caminho("chave", onde)).st_mode & 0o077:
        raise SeloIndisponivel(f"a chave do selo ({_caminho('chave', onde)}) pode ser lida por outros usuários: chmod 600",
                               "key_open")
    try:
        with open(_caminho("chave", onde), "rb") as f:
            chave = serialization.load_pem_private_key(f.read(), password=None)
        with open(_caminho("selo", onde), "rb") as f:
            selo = x509.load_pem_x509_certificate(f.read())
        with open(_caminho("raiz", onde), "rb") as f:
            raiz = x509.load_pem_x509_certificate(f.read())
    except (OSError, ValueError, TypeError) as e:
        raise SeloIndisponivel(f"os arquivos do selo não abrem: {type(e).__name__}: {str(e)[:160]}", "unreadable")
    if not isinstance(chave, (ec.EllipticCurvePrivateKey, rsa.RSAPrivateKey)):
        raise SeloIndisponivel("a chave do selo não é EC nem RSA", "unreadable")
    pub = serialization.PublicFormat.SubjectPublicKeyInfo
    if chave.public_key().public_bytes(serialization.Encoding.DER, pub) != selo.public_key().public_bytes(serialization.Encoding.DER, pub):
        raise SeloIndisponivel("a chave do selo não é a do certificado de selo", "key_mismatch")
    try:
        selo.verify_directly_issued_by(raiz)
    except Exception:                                           # assinatura, emissor ou algoritmo que não batem
        raise SeloIndisponivel("o certificado de selo não foi emitido pela raiz guardada", "wrong_root")
    agora = datetime.now(timezone.utc)
    if not (selo.not_valid_before_utc <= agora <= selo.not_valid_after_utc):
        raise SeloIndisponivel(f"o certificado de selo está fora da validade ({selo.not_valid_after_utc:%Y-%m-%d})", "expired")
    return chave, selo, raiz


def estado(onde=None):
    """O que Site › Waiver mostra e o que `ligar()` confere. Não fala com a TSA (isso é `selo-waiver conferir`)."""
    base = {"dir": onde or pasta(), "tsa": [sem_credencial(u) for u in tsas()], "field": CAMPO,
            "tsa_roots": [r["name"] for r in _raizes_tsa_descritas()]}
    try:
        _chave, selo, raiz = _carregar(onde)
    except SeloIndisponivel as e:
        return {**base, "configured": False, "code": e.codigo, "reason": e.motivo}
    return {**base, "configured": True, "code": "ok", "reason": "selo configurado",
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
        rotulo = sem_credencial(url)
        try:
            saida = signers.PdfSigner(meta, signer=assinante, timestamper=carimbador).sign_pdf(
                IncrementalPdfFileWriter(io.BytesIO(pdf)), bytes_reserved=RESERVA)
            selado = saida.getvalue()
            der, tst, tok = _token(selado)
            _carimbo_confere(selado, raiz)       # revisão do #335: TSA conhecida e hora perto da nossa
        except Exception as e:                    # rede, resposta ruim, TSA desconhecida, hora fora: tenta a próxima
            erros.append(f"{rotulo}: {type(e).__name__}: {sem_credencial(str(e))[:200]}")
            continue
        tsa = _cert_da_tsa(tok)
        info = {"standard": "PAdES-B-T", "field": CAMPO, "certification": "DocMDP: no changes allowed",
                "digest": "SHA-256", "tsa_url": rotulo,
                "gen_time": tst["gen_time"].native.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "serial": str(tst["serial_number"].native), "policy": tst["policy"].native,
                "token_sha256": hashlib.sha256(der).hexdigest(),
                "tsa_subject": tsa.subject.human_friendly if tsa else None,
                "seal_cert_sha256": _sha_der(selo), "root_cert_sha256": _sha_der(raiz)}
        return selado, info, der
    raise SeloIndisponivel("nenhuma TSA deu um carimbo de tempo que confere: " + " | ".join(erros or ["nenhuma TSA configurada"]))


def _carimbo_confere(selado, raiz):
    """Logo depois de selar: o carimbo é de uma TSA das raízes fixas e a hora dele está a até `DESVIO_MAX` do relógio
    do VPS. Senão, `ValueError` (o `selar` passa para a próxima TSA)."""
    v = validar(selado, raiz=raiz)
    ts = v.get("timestamp") or {}
    if not (ts.get("intact") and ts.get("valid") and ts.get("trusted")):
        raise ValueError(f"carimbo de TSA desconhecida ou que não confere (raízes de TSA: {pasta_raizes_tsa()} e "
                         f"{', '.join(RAIZES_TSA_FIXAS.values())})")
    hora = datetime.fromisoformat(ts["time"].replace("Z", "+00:00"))
    if abs(datetime.now(timezone.utc) - hora) > DESVIO_MAX:
        raise ValueError(f"hora do carimbo ({ts['time']}) a mais de {DESVIO_MAX.seconds // 60} min do relógio do VPS")
    if not v["ok"]:
        raise ValueError(f"o selo recém-feito não confere: {v['reason']}")


# ------------------------------------------------------------------ conferir
@lru_cache(maxsize=1)
def _raizes_publicas():
    """As raízes do certifi (as mesmas que o `requests` usa). Daqui só saem as de `RAIZES_TSA_FIXAS`."""
    try:
        import certifi
        from asn1crypto import pem, x509 as ax509
        with open(certifi.where(), "rb") as f:
            return [ax509.Certificate.load(der) for _t, _h, der in pem.unarmor(f.read(), multiple=True)]
    except Exception:
        return []


def _raizes_tsa_descritas():
    """[{name, sha256, cert}] das raízes de TSA aceitas: as fixas do certifi e os .pem de `pasta_raizes_tsa()`."""
    from asn1crypto import pem, x509 as ax509
    saida = [{"name": RAIZES_TSA_FIXAS[c.sha256.hex()], "sha256": c.sha256.hex(), "cert": c}
             for c in _raizes_publicas() if c.sha256.hex() in RAIZES_TSA_FIXAS]
    d = pasta_raizes_tsa()
    for nome in sorted(os.listdir(d)) if os.path.isdir(d) else ():
        if not nome.endswith((".pem", ".crt")):
            continue
        try:
            with open(os.path.join(d, nome), "rb") as f:
                dados = f.read()
            ders = [der for _t, _h, der in pem.unarmor(dados, multiple=True)] if pem.detect(dados) else [dados]
            for der in ders:
                c = ax509.Certificate.load(der)
                saida.append({"name": f"{c.subject.native.get('common_name') or nome} ({nome})", "sha256": c.sha256.hex(),
                              "cert": c})
        except Exception:                          # arquivo que não é certificado: não entra (e não derruba nada)
            continue
    return saida


def raizes_tsa():
    return [r["cert"] for r in _raizes_tsa_descritas()]


def _raiz_guardada():
    if not os.path.isfile(_caminho("raiz")):
        return None
    from cryptography import x509
    with open(_caminho("raiz"), "rb") as f:
        return x509.load_pem_x509_certificate(f.read())


def carregar_raiz(caminho):
    """Uma raiz de selo de um arquivo PEM (para conferir PDFs de antes de trocar o selo: `--raiz`)."""
    from cryptography import x509
    with open(caminho, "rb") as f:
        return x509.load_pem_x509_certificate(f.read())


def validar(pdf, raiz=None, raizes_tsa_extra=None):
    """Confere o selo como o `pyhanko sign validate`, com DOIS contextos (revisão do #335):
    - o selo só vale pela raiz da URACE (`raiz`, ou a guardada), e o certificado tem de ser emitido direto por ela;
    - o carimbo só vale pelas raízes de TSA (`raizes_tsa()` e `raizes_tsa_extra`), e a hora dele tem de bater (até
      `DESVIO_MAX`) com a que o selo declara.
    `ok` exige tudo: íntegro, válido, confiável, cobertura do arquivo inteiro, DocMDP e carimbo confiável."""
    from cryptography import x509
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    raiz = raiz or _raiz_guardada()
    if raiz is None:
        return {"ok": False, "intact": None, "reason": "sem a raiz do selo para conferir (selo-waiver criar ou --raiz)"}
    try:
        sigs = PdfFileReader(io.BytesIO(pdf)).embedded_signatures
        if len(sigs) != 1:
            return {"ok": False, "intact": False, "reason": f"{len(sigs)} assinaturas no PDF; esperava 1"}
        s = sigs[0]
        do_selo = ValidationContext(trust_roots=[_asn1(raiz)], allow_fetching=False)
        da_tsa = ValidationContext(trust_roots=raizes_tsa() + [_asn1(c) for c in (raizes_tsa_extra or [])], allow_fetching=False)
        st = validate_pdf_signature(s, signer_validation_context=do_selo, ts_validation_context=da_tsa)
    except Exception as e:                       # arquivo mexido a ponto de não abrir: não é íntegro
        return {"ok": False, "intact": False, "reason": f"{type(e).__name__}: {str(e)[:200]}"}
    try:
        x509.load_der_x509_certificate(s.signer_cert.dump()).verify_directly_issued_by(raiz)
        da_urace = True
    except Exception:
        da_urace = False
    ts = st.timestamp_validity
    carimbo = None if ts is None else {"intact": ts.intact, "valid": ts.valid, "trusted": ts.trusted,
                                       "time": ts.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    declarada = getattr(st, "signer_reported_dt", None)
    horas_batem = bool(ts and declarada and abs(ts.timestamp - declarada) <= DESVIO_MAX)
    docmdp = s.docmdp_level.name if s.docmdp_level is not None else None
    cobertura = st.coverage.name if st.coverage is not None else None
    ok = bool(st.intact and st.valid and st.trusted and da_urace and st.docmdp_ok and cobertura == "ENTIRE_FILE"
              and carimbo and carimbo["intact"] and carimbo["valid"] and carimbo["trusted"] and horas_batem)
    if ok:
        motivo = "selo íntegro e válido"
    elif not st.intact:
        motivo = "o arquivo mudou depois de selado"
    elif not (st.trusted and da_urace):
        motivo = "o selo não é da URACE (não vem da raiz do selo)"
    elif not (carimbo and carimbo["trusted"]):
        motivo = "o carimbo de tempo não é de uma TSA conhecida"
    elif not horas_batem:
        motivo = "a hora do carimbo não bate com a do selo"
    else:
        motivo = "selo não confere"
    return {"ok": ok, "field": s.field_name, "intact": st.intact, "valid": st.valid, "trusted": st.trusted,
            "issued_by_root": da_urace, "coverage": cobertura, "docmdp": docmdp, "timestamp": carimbo,
            "times_match": horas_batem, "reason": motivo}


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
