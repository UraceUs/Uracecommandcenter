#!/usr/bin/env python3
"""Administração pela linha de comando.

    python3 -m command_center.manage create-admin      # primeiro usuário
    python3 -m command_center.manage set-password EMAIL
    python3 -m command_center.manage list-users
    python3 -m command_center.manage conferir-chat [DIAS]   # o que não foi e o que não chegou
    python3 -m command_center.manage suits-suspeitos        # pedidos de Suits que não parecem de macacão (só lê)
    python3 -m command_center.manage suits-descartar ID [ID ...] [--motivo TEXTO]   # tira das listas e da ponte
    python3 -m command_center.manage suits-restaurar ID [ID ...]
    python3 -m command_center.manage selo-waiver criar      # #110: raiz e selo da waiver nativa (nunca sobrescreve)
    python3 -m command_center.manage selo-waiver conferir   # sela um PDF de teste com a TSA configurada e valida
    python3 -m command_center.manage selo-waiver conferir ARQUIVO.pdf   # confere o selo de uma waiver assinada
"""
import sys
from getpass import getpass

from command_center.api import auth
from command_center.db import aplicar_schema, conectar, todos, um


def _conferir_chat(con, dias):
    """Lê a conversa de cada lead no Kommo e confronta com a do painel. Só leitura."""
    from command_center.providers import conferencia
    r = conferencia.conferir(con, dias=dias)
    quando = r["desde"][:16].replace("T", " ")
    print(f"Conferência do chat — desde {quando} (UTC), {len(r['leads'])} conversa(s), "
          f"{r['eventos']} evento(s) de conversa lidos da conta\n")
    cegos = []
    for c in r["leads"]:
        l = c["lead"]
        nome = (l.get("name") or l["external_id"])[:34]
        if c["erro"]:
            print(f"⚠ {nome:<34} não deu para ler no Kommo: {c['erro']}"); continue
        if c["cego_saida"]:
            cegos.append((nome, l, c["cego_saida"]))
        if not (c["nao_chegou"] or c["nao_foi"] or c["pendentes"]):
            continue
        print(f"— {nome}  (lead {l['external_id']}{' · ' + l['source'] if l.get('source') else ''})")
        for m in c["nao_foi"]:
            print(f"    NÃO FOI     {str(m['at'])[:16].replace('T', ' ')}  {(m['text'] or '')[:60]}")
        for m in c["pendentes"]:
            print(f"    NA FILA     {str(m['at'])[:16].replace('T', ' ')}  {(m['text'] or '')[:60]}  [{m['status']}]")
        for k in c["nao_chegou"]:
            print(f"    NÃO CHEGOU  {str(k.get('em'))[:16].replace('T', ' ')}  {(k.get('texto') or '(o Kommo não deu o texto)')[:60]}")
        if l.get("link"):
            print(f"    no Kommo: {l['link']}")
        print()
    if cegos:
        print("Não dá para dizer (o Kommo não mostra resposta nossa nestas conversas — a ausência")
        print("aqui não é prova de que não chegou; é falta de dado):")
        for nome, l, ms in cegos:
            print(f"  · {nome} (lead {l['external_id']}): "
                  + ", ".join(f"{str(m['at'])[:16].replace('T', ' ')} \"{(m['text'] or '')[:28]}\"" for m in ms[:3])
                  + (f" e mais {len(ms) - 3}" if len(ms) > 3 else ""))
        print()
    print(f"Total: {r['nao_foi']} não foi(ram) · {r['nao_chegou']} não chegou(aram) · "
          f"{r['pendentes']} ainda na fila · {r['cego_saida']} sem como dizer · "
          f"{r['sem_dados']} conversa(s) que o Kommo devolveu vazia · {r['erros']} que não deu para ler")
    print("Lembre: a API do Kommo não devolve o texto de toda mensagem de chat, e o que é anterior")
    print("à integração não vem pela API. Onde ela não enxerga, a conferência diz que não sabe —")
    print("nunca conta silêncio como mensagem perdida.")
    return 0


def _suits_ids(args):
    ids, motivo, i = [], None, 0
    while i < len(args):
        if args[i] == "--motivo" and i + 1 < len(args):
            motivo, i = args[i + 1], i + 2
            continue
        if not args[i].isdigit():
            sys.exit(f"id inválido: {args[i]}")
        ids.append(int(args[i]))
        i += 1
    if not ids:
        sys.exit("diga os números dos pedidos")
    return ids, motivo


def _suits(con, cmd, args):
    """#195: descartar o que não é pedido de macacão (nada é apagado) e listar os suspeitos."""
    from command_center.db import auditar
    from command_center.providers import suits, suits_ponte
    if cmd == "suits-suspeitos":
        lista = suits_ponte.suspeitos(con)
        for s in lista:
            print(f"#{s['id']:<5} {s['title'][:34]:<34} {s['customer_email'] or '—':<34} {'; '.join(s['motivos'])}"
                  + (f"  [{s['assunto'][:60]}]" if s.get("assunto") else ""))
        print(f"{len(lista)} suspeito(s). Nada foi mudado: para tirar, rode suits-descartar com os números.")
        return 0
    ids, motivo = _suits_ids(args)
    for pid in ids:
        p = um(con, "SELECT id, title, customer_email, discarded_at FROM suit_orders WHERE id=?", (pid,))
        if not p:
            print(f"#{pid}: não existe"); continue
        if cmd == "suits-descartar":
            feito = suits.descartar(con, pid, motivo)
            if feito:
                auditar(con, "suit.discarded", "manage", entity_type="suit_order", entity_id=pid,
                        detail={"motivo": motivo or suits.MOTIVO_PADRAO})
            print(f"#{pid} {p['title']} <{p['customer_email'] or '—'}>: " + ("descartado" if feito else "já estava descartado"))
        else:
            feito = suits.restaurar(con, pid)
            if feito:
                auditar(con, "suit.restored", "manage", entity_type="suit_order", entity_id=pid)
            print(f"#{pid} {p['title']}: " + ("restaurado" if feito else "não estava descartado"))
    con.commit()
    return 0


def _conferir_pdf(sw, caminho):
    """O selo de um PDF já assinado (só lê): íntegro, válido, pela raiz da URACE, e o carimbo."""
    try:
        with open(caminho, "rb") as f:
            v = sw.validar(f.read())
    except OSError as e:
        print(f"❌ não abre: {e}")
        return 1
    ts = v.get("timestamp") or {}
    print(f"{caminho}: íntegro={v['intact']} válido={v.get('valid')} confiável={v.get('trusted')} cobertura={v.get('coverage')} "
          f"DocMDP={v.get('docmdp')} · carimbo {ts.get('time') or '—'} íntegro={ts.get('intact')} válido={ts.get('valid')} "
          f"confiável={ts.get('trusted')}")
    print("✅ selo e carimbo conferem: o arquivo não mudou desde a assinatura" if v["ok"] else f"❌ {v['reason']}")
    return 0 if v["ok"] else 1


def _selo_waiver(con, sub, arquivo=None):
    """#110: o selo PAdES da waiver nativa. `criar` gera a raiz e o selo no VPS (a chave fica em ~/.urace, nunca no
    repositório, e nada que exista é sobrescrito); `conferir` sela um PDF de teste com a TSA de verdade e valida."""
    from datetime import datetime, timezone
    from command_center.db import auditar
    from command_center.providers import selo_waiver as sw
    if sub == "criar":
        try:
            r = sw.criar()
        except FileExistsError as e:
            print(f"⚠ {e}")
            print("  Para conferir o que está lá: python3 -m command_center.manage selo-waiver conferir")
            return 1
        auditar(con, "waiver.seal_created", "manage", detail={k: r[k] for k in ("root_sha256", "seal_sha256", "seal_not_after")})
        print(f"✅ selo da waiver criado em {r['dir']}")
        print(f"   raiz (root-cert.pem), SHA-256: {sw.impressao(r['root_sha256'])}")
        print(f"   selo (seal-cert.pem), SHA-256: {sw.impressao(r['seal_sha256'])} · vale até {r['seal_not_after']}")
        print("   A chave da raiz não foi guardada (ninguém emite outro selo com ela). A chave do selo é seal-key.pem (0600).")
        print("   GUARDE UMA CÓPIA da pasta inteira fora da VPS (no gerenciador de senhas do dono): ela não vai no backup do banco.")
        return 0
    if sub == "conferir" and arquivo:
        return _conferir_pdf(sw, arquivo)
    if sub == "conferir":
        e = sw.estado()
        if not e["configured"]:
            print(f"❌ {e['reason']}")
            return 1
        print(f"selo: {e['seal_subject']} · vale até {e['seal_not_after']}")
        print(f"raiz SHA-256: {sw.impressao(e['root_sha256'])}")
        print(f"TSAs (CC_WAIVER_TSA): {', '.join(e['tsa'])}")
        try:
            selado, info, token = sw.selar(sw.pdf_de_teste())
        except sw.SeloIndisponivel as x:
            print(f"❌ {x.motivo}")
            print("   Sem TSA, nenhuma waiver se assina online (o cliente vê 'temporarily unavailable'). Confira a rede do VPS.")
            return 1
        v = sw.validar(selado)
        ts = v.get("timestamp") or {}
        print(f"carimbo: {info['tsa_url']} · {info['gen_time']} · série {info['serial']} · {len(token)} bytes")
        print(f"validação: íntegro={v['intact']} válido={v['valid']} confiável={v['trusted']} cobertura={v['coverage']} "
              f"DocMDP={v['docmdp']} · carimbo íntegro={ts.get('intact')} válido={ts.get('valid')} confiável={ts.get('trusted')}")
        desvio = abs((datetime.now(timezone.utc) - datetime.fromisoformat(info["gen_time"].replace("Z", "+00:00"))).total_seconds())
        if desvio > 60:
            print(f"⚠ o relógio do VPS está {desvio:.0f} s longe da hora da TSA: confira o NTP (timedatectl)")
        else:
            print(f"relógio do VPS a {desvio:.0f} s da hora da TSA (NTP ok)")
        print("✅ selo e carimbo conferem" if v["ok"] else f"❌ {v['reason']}")
        return 0 if v["ok"] else 1
    print("uso: selo-waiver criar | selo-waiver conferir [ARQUIVO.pdf]")
    return 1


def main(argv):
    con = conectar()
    aplicar_schema(con)
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "create-admin":
        email = input("e-mail: ").strip().lower()
        name = input("nome: ").strip()
        while True:
            s1 = getpass(f"senha (mín. {auth.SENHA_MIN}, não aparece): ")
            if len(s1) < auth.SENHA_MIN:
                print(f"   curta demais: precisa de {auth.SENHA_MIN} ou mais. De novo."); continue
            if s1 != getpass("repita: "):
                print("   as duas não conferem. De novo."); continue
            break
        uid = auth.criar_usuario(con, email, name, "ADMIN", s1)
        print(f"✅ ADMIN criado: {email} (id {uid})")
    elif cmd == "set-password" and len(argv) > 2:
        u = um(con, "SELECT id FROM users WHERE email = ?", (argv[2].strip().lower(),))
        if not u:
            sys.exit("usuário não existe")
        while True:
            s1 = getpass(f"senha nova (mín. {auth.SENHA_MIN}): ")
            if len(s1) < auth.SENHA_MIN:
                print("   curta demais. De novo."); continue
            if s1 != getpass("repita: "):
                print("   as duas não conferem. De novo."); continue
            break
        auth.trocar_senha(con, u["id"], s1, u["id"])
        print("✅ senha trocada; sessões abertas foram derrubadas")
    elif cmd == "list-users":
        for r in todos(con, "SELECT id, email, name, role, active, last_login_at FROM users ORDER BY id"):
            print(f"{r['id']:>3}  {r['email']:<30} {r['role']:<9} {'ativo' if r['active'] else 'INATIVO':<8} {r['last_login_at'] or '—'}")
    elif cmd in ("suits-suspeitos", "suits-descartar", "suits-restaurar"):
        return _suits(con, cmd, argv[2:])
    elif cmd == "selo-waiver":
        return _selo_waiver(con, argv[2] if len(argv) > 2 else "", argv[3] if len(argv) > 3 else None)
    elif cmd == "conferir-chat":
        return _conferir_chat(con, int(argv[2]) if len(argv) > 2 else 7)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
