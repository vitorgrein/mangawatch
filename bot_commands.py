#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaWatch — Processador de comandos do Telegram.

Lê as mensagens novas enviadas ao bot (getUpdates), processa os comandos
e responde. Pensado pra rodar no GitHub Actions a cada poucos minutos.
Como NÃO há servidor sempre ligado, os comandos são processados na próxima
rodada agendada (não é instantâneo).

Comandos:
  /add <link>            adiciona uma obra ao monitoramento
  /remove <link|texto>   remove uma obra
  /list                  lista as obras monitoradas
  /check                 força uma verificação imediata
  /help                  mostra a ajuda

Segurança: só obedece a mensagens vindas do TELEGRAM_CHAT_ID configurado.

Variáveis de ambiente:
  TELEGRAM_TOKEN   -> token do bot
  TELEGRAM_CHAT_ID -> seu chat id (dono)
"""

import json
import os
import re
import sys

import cloudscraper
requests = cloudscraper.create_scraper()

import check_manga  # reaproveita ler_lista, obter_ultimo_capitulo, etc.

LISTA_FILE  = "mangas.txt"
OFFSET_FILE = "telegram_offset.json"

AJUDA = (
    "🤖 *MangaWatch — comandos*\n\n"
    "`/add <link>` — adiciona uma obra ao monitoramento\n"
    "`/remove <link ou nome>` — remove uma obra\n"
    "`/list` — mostra as obras monitoradas\n"
    "`/check` — verifica novos capítulos agora\n"
    "`/help` — mostra esta ajuda\n\n"
    "_Os comandos são processados na próxima rodada agendada "
    "(pode levar alguns minutos)._"
)


# ------------------------------------------------------------------
# Telegram
# ------------------------------------------------------------------
def tg(token, method, **params):
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        r = requests.post(url, data=params, timeout=30)
        return r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[!] Erro Telegram ({method}): {e}")
        return {}


def enviar(token, chat_id, texto):
    for parte in dividir(texto):
        tg(
            token,
            "sendMessage",
            chat_id=chat_id,
            text=parte,
            parse_mode="Markdown",
            disable_web_page_preview="true",
        )


def dividir(texto, limite=3900):
    """Quebra mensagens longas no limite do Telegram (4096 chars)."""
    if len(texto) <= limite:
        return [texto]
    partes, atual = [], ""
    for linha in texto.split("\n"):
        if len(atual) + len(linha) + 1 > limite:
            partes.append(atual)
            atual = linha
        else:
            atual = f"{atual}\n{linha}" if atual else linha
    if atual:
        partes.append(atual)
    return partes


# ------------------------------------------------------------------
# Estado do offset (pra não reprocessar mensagens já lidas)
# ------------------------------------------------------------------
def carregar_offset():
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("offset", 0))
        except Exception:  # noqa: BLE001
            return 0
    return 0


def salvar_offset(offset):
    with open(OFFSET_FILE, "w", encoding="utf-8") as f:
        json.dump({"offset": offset}, f)


# ------------------------------------------------------------------
# Leitura/escrita da lista
# ------------------------------------------------------------------
def ler_linhas_brutas():
    if not os.path.exists(LISTA_FILE):
        return []
    with open(LISTA_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def escrever_linhas(linhas):
    with open(LISTA_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


def slug_da_linha(linha):
    """Devolve o slug de uma linha de mangas.txt, ou None se não for obra."""
    s = linha.strip()
    if not s or s.startswith("#"):
        return None
    m = re.match(r"^(.*)/(\d+)/?$", s)
    if not m:
        return None
    return m.group(1).rstrip("/").split("/")[-1]


def normalizar_link(texto):
    """
    Extrai a URL do texto e devolve (linha_formatada, slug, cap).
    Se a URL não terminar em número, cap volta como None (o /add decide
    o ponto de partida consultando a API).
    Retorna (None, None, None) se não houver link válido.
    """
    m = re.search(r"https?://\S+", texto or "")
    if not m:
        return None, None, None
    url = m.group(0).rstrip("/")
    mnum = re.match(r"^(.*)/(\d+)$", url)
    if mnum:
        base, cap = mnum.group(1), int(mnum.group(2))
    else:
        base, cap = url, None
    slug = base.rstrip("/").split("/")[-1]
    if not slug:
        return None, None, None
    return base, slug, cap


# ------------------------------------------------------------------
# Comandos
# ------------------------------------------------------------------
def cmd_add(token, chat_id, arg):
    base, slug, cap = normalizar_link(arg)
    if not slug:
        enviar(
            token, chat_id,
            "❌ Não entendi o link. Use:\n"
            "`/add https://toonlivre.net/nome-do-manga/123`\n"
            "(o número do final é opcional)",
        )
        return

    # já está na lista?
    for _b, _c, s in check_manga.ler_lista():
        if s == slug:
            enviar(
                token, chat_id,
                f"ℹ️ *{check_manga.nome_legivel(slug)}* já está na lista.",
            )
            return

    # sem número informado → começa a partir do capítulo atual,
    # pra você não levar uma enxurrada de avisos retroativos.
    if cap is None:
        atual = check_manga.obter_ultimo_capitulo(slug)
        cap = atual if atual is not None else 0

    escrever_linhas(ler_linhas_brutas() + [f"{base}/{cap}"])
    enviar(
        token, chat_id,
        f"✅ Adicionado: *{check_manga.nome_legivel(slug)}*\n"
        f"Monitorando a partir do capítulo {cap}.",
    )


def cmd_remove(token, chat_id, arg):
    arg = (arg or "").strip()
    if not arg:
        enviar(token, chat_id, "Use: `/remove <link ou parte do nome>`")
        return

    alvo_slug = None
    if re.search(r"https?://\S+", arg):
        _b, alvo_slug, _c = normalizar_link(arg)
    termo = arg.lower()

    linhas = ler_linhas_brutas()
    novas, removidos = [], []
    for linha in linhas:
        slug = slug_da_linha(linha)
        if slug is None:  # comentário/linha em branco — preserva
            novas.append(linha)
            continue
        nome = check_manga.nome_legivel(slug)
        bate = (
            slug == alvo_slug
            if alvo_slug
            else (termo in slug.lower() or termo in nome.lower())
        )
        if bate:
            removidos.append(nome)
        else:
            novas.append(linha)

    if not removidos:
        enviar(token, chat_id, "❌ Não achei nenhuma obra com isso na lista.")
        return
    if len(removidos) > 1:
        lista = "\n".join(f"• {r}" for r in removidos)
        enviar(
            token, chat_id,
            f"⚠️ Isso bate com várias obras:\n{lista}\n\n"
            "Seja mais específico (use o link ou um trecho único do nome).",
        )
        return

    escrever_linhas(novas)
    enviar(token, chat_id, f"🗑️ Removido: *{removidos[0]}*")


def cmd_list(token, chat_id):
    obras = check_manga.ler_lista()
    if not obras:
        enviar(token, chat_id, "A lista está vazia. Use `/add <link>`.")
        return
    estado = check_manga.carregar_estado()
    linhas = []
    for _base, cap_inicial, slug in obras:
        nome  = check_manga.nome_legivel(slug)
        atual = max(cap_inicial, int(estado.get(slug, 0)))
        linhas.append(f"• {nome} — cap. {atual}")
    enviar(
        token, chat_id,
        f"📚 *{len(obras)} obra(s) monitorada(s):*\n\n" + "\n".join(linhas),
    )


def cmd_check(token, chat_id):
    enviar(token, chat_id, "🔎 Verificando agora...")
    total = check_manga.rodar_verificacao(token, chat_id)
    if total == 0:
        enviar(token, chat_id, "✅ Nenhum capítulo novo.")
    else:
        enviar(token, chat_id, f"✅ Pronto — {total} capítulo(s) novo(s).")


# ------------------------------------------------------------------
def main():
    token   = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[!] TELEGRAM_TOKEN/TELEGRAM_CHAT_ID não definidos. Abortando.")
        return 0
    chat_id = str(chat_id)

    offset = carregar_offset()
    resp = tg(token, "getUpdates", offset=offset, timeout=0)
    if not resp.get("ok", False):
        print(f"[!] getUpdates falhou: {resp}")
        return 0

    updates = resp.get("result", [])
    if not updates:
        print("Sem mensagens novas.")
        return 0

    print(f"{len(updates)} update(s) recebido(s).")
    maior = offset

    for upd in updates:
        # avança o offset sempre, mesmo pra mensagens ignoradas,
        # pra não travar a fila com mensagens de estranhos.
        maior = max(maior, int(upd["update_id"]) + 1)

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            continue
        texto = (msg.get("text") or "").strip()
        de_chat = str(msg.get("chat", {}).get("id", ""))

        if de_chat != chat_id:
            print(f"Ignorando mensagem de chat não autorizado: {de_chat}")
            continue
        if not texto.startswith("/"):
            continue

        partes = texto.split(maxsplit=1)
        cmd = partes[0].lower().split("@")[0]  # tira @nomedobot de grupos
        arg = partes[1] if len(partes) > 1 else ""
        print(f"Comando: {cmd} {arg!r}")

        if cmd == "/add":
            cmd_add(token, chat_id, arg)
        elif cmd == "/remove":
            cmd_remove(token, chat_id, arg)
        elif cmd == "/list":
            cmd_list(token, chat_id)
        elif cmd == "/check":
            cmd_check(token, chat_id)
        elif cmd in ("/start", "/help", "/ajuda"):
            enviar(token, chat_id, AJUDA)
        else:
            enviar(token, chat_id, f"❓ Comando desconhecido: `{cmd}`\n\n{AJUDA}")

    salvar_offset(maior)
    print("Concluído.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
