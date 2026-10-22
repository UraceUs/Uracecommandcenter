// urace-atelie (#383): o OpenClaw só como transporte dos grupos do ateliê no WhatsApp.
//
// Dono, 22/10: "vamos usar o openclaw somente para dar a vps acesso aos grupos internos da urace".
// Este plugin faz duas coisas, e só no WhatsApp:
//   1. before_dispatch: toda mensagem do WhatsApp (grupo da lista, outro grupo ou DM) é "tratada" aqui, sem
//      texto: o agente do OpenClaw NUNCA roda nem responde nesses chats (o agente que age é o do Command Center).
//   2. message_received: a mensagem de um grupo da lista (WA_GRUPO_<PAPEL>_JID do env) vai, com a mídia, para
//      o Command Center em 127.0.0.1 (POST com o segredo WA_GRUPOS_TOKEN). Outro grupo ou pessoa: nada sai.
//      Se o Command Center não responder, a mensagem fica num arquivo da fila (~/.urace/atelie/fila, 600), que o
//      Command Center lê no ciclo seguinte (15 min).
// O env é lido do disco a cada mensagem (mudou a lista de grupos: não precisa reiniciar o gateway).
// Nada de corpo, número ou segredo no log.
import { readFileSync, writeFileSync, mkdirSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { basename, join } from "node:path";

const HOME = homedir();
const URACE = process.env.URACE_DIR || join(HOME, ".urace");
const MIDIA_MAX = 25 * 1024 * 1024;

export function lerEnv(caminho) {
  const saida = {};
  let texto = "";
  try { texto = readFileSync(caminho, "utf8"); } catch { return saida; }
  for (const bruta of texto.split(/\r?\n/)) {
    const linha = bruta.trim();
    if (!linha || linha.startsWith("#") || !linha.includes("=")) continue;
    const i = linha.indexOf("=");
    let v = linha.slice(i + 1).trim();
    if (v.length >= 2 && v[0] === v[v.length - 1] && (v[0] === '"' || v[0] === "'")) v = v.slice(1, -1);
    saida[linha.slice(0, i).trim()] = v;
  }
  return saida;
}

export function gruposDaLista(env) {
  const papeis = (env.WA_GRUPOS || "design,fornecedor").toLowerCase().split(/[,\s]+/).filter(p => /^[a-z_]{2,30}$/.test(p));
  const jids = new Set();
  for (const p of papeis) {
    const jid = (env[`WA_GRUPO_${p.toUpperCase()}_JID`] || "").trim();
    if (jid.endsWith("@g.us")) jids.add(jid);
  }
  return jids;
}

/** O JID do grupo da conversa, de onde o OpenClaw puser (contexto, metadados ou a chave da sessão). */
export function jidDoGrupo(event, ctx) {
  const cands = [ctx?.conversationId, event?.metadata?.to, event?.from, event?.conversationId];
  for (const c of cands) if (typeof c === "string" && c.endsWith("@g.us")) return c;
  const sk = ctx?.sessionKey || event?.sessionKey || "";
  const m = /whatsapp:group:([^:\s]+@g\.us)/.exec(sk);
  return m ? m[1] : null;
}

function eWhatsapp(event, ctx) {
  const c = (ctx?.channelId || event?.channel || event?.metadata?.provider || "").toLowerCase();
  return c === "whatsapp" || c.startsWith("whatsapp");
}

export function montar(event, ctx, jid) {
  const midias = [];
  for (const f of event?.media || []) {
    if (!f?.path) continue;
    try {
      if (statSync(f.path).size > MIDIA_MAX) { midias.push({ nome: basename(f.path), tipo: f.contentType || null, base64: "" }); continue; }
      midias.push({ nome: basename(f.path), tipo: f.contentType || f.kind || null, base64: readFileSync(f.path).toString("base64") });
    } catch { /* arquivo sumiu: segue sem ele */ }
  }
  const md = event?.metadata || {};
  return {
    grupo_jid: jid,
    message_id: event?.messageId || ctx?.messageId || null,
    remetente: event?.senderId || ctx?.senderId || md.senderE164 || md.senderId || null,
    remetente_nome: md.senderName || null,
    texto: event?.content || "",
    at: event?.timestamp ? new Date(Number(event.timestamp) * (Number(event.timestamp) < 1e12 ? 1000 : 1)).toISOString() : null,
    resposta_a: event?.replyToId || ctx?.replyToId || null,
    resposta_texto: event?.replyToBody || ctx?.replyToBody || null,
    de_mim: Boolean(md.fromMe),
    midias,
  };
}

async function mandar(url, token, corpo) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", "x-urace-atelie-token": token },
    body: JSON.stringify(corpo),
    signal: AbortSignal.timeout(20000),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
}

function guardarNaFila(corpo) {
  const pasta = join(URACE, "atelie", "fila");
  mkdirSync(pasta, { recursive: true, mode: 0o700 });
  const nome = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}.json`;
  writeFileSync(join(pasta, nome), JSON.stringify(corpo), { mode: 0o600 });
}

export default {
  id: "urace-atelie",
  name: "URACE ateliê (WhatsApp → Command Center)",
  description: "Leva as mensagens dos grupos do ateliê para o Command Center e cala o agente do OpenClaw no WhatsApp.",
  register(api) {
    const envFile = api?.pluginConfig?.envFile || join(URACE, "whatsapp-grupos.env");
    const log = api?.logger || console;

    api.on("before_dispatch", (event, ctx) => {
      if (eWhatsapp(event, ctx)) return { handled: true };      // silêncio: o OpenClaw não responde no WhatsApp
      return undefined;
    });

    api.on("message_received", async (event, ctx) => {
      if (!eWhatsapp(event, ctx)) return;
      const jid = jidDoGrupo(event, ctx);
      if (!jid) return;                                          // conversa individual: DM é desligada
      const env = lerEnv(envFile);
      if (!gruposDaLista(env).has(jid) || !env.WA_GRUPOS_TOKEN) return;   // grupo fora da lista: nem lê
      const url = env.WA_GRUPOS_CC_URL || "http://127.0.0.1:8790/ops/api/atelie/whatsapp/entrada";
      const corpo = montar(event, ctx, jid);
      try {
        await mandar(url, env.WA_GRUPOS_TOKEN, corpo);
      } catch (e) {
        guardarNaFila(corpo);
        log.warn?.(`urace-atelie: Command Center não recebeu (${e?.name || "erro"}); mensagem guardada na fila`);
      }
    });
  },
};
