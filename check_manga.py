#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MangaWatch — Verificador de novos capítulos.

Estratégia: chama a API de cada obra uma vez
(toonlivre.net/api/manga-by-slug/{slug}), pega o maior número de capítulo
disponível e compara com o último conhecido. Sem tentativas cegas de URL.

Variáveis de ambiente:
  TELEGRAM_TOKEN   -> token do bot
  TELEGRAM_CHAT_ID -> chat id
"""

import json
import os
import sys
import time

import cloudscraper
requests = cloudscraper.create_scraper()

LISTA_FILE = "mangas.txt"
STATE_FILE = "manga_state.json"
API_BASE   = "https://toonlivre.net/api/manga-by-slug"

# Pausa entre obras (segundos) — respeita o rate limit da API
DELAY = 2.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": "https://toonlivre.net/",
}


# ------------------------------------------------------------------
def ler_lista():
    """Lê mangas.txt → lista de (base_url, cap_inicial, slug)."""
    import re
    if not os.path.exists(LISTA_FILE):
        print(f"[!] {LISTA_FILE} não encontrado.")
        return []
    obras = []
    with open(LISTA_FILE, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            m = re.match(r"^(.*)/(\d+)/?$", linha)
            if not m:
                print(f"[!] Ignorando (sem número no final): {linha}")
                continue
            base = m.group(1)
            cap  = int(m.group(2))
            slug = base.rstrip("/").split("/")[-1]
            obras.append((base, cap, slug))
    return obras


def carregar_estado():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_estado(estado):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def nome_legivel(slug):
    return slug.replace("-", " ").replace("_", " ").title()


def obter_ultimo_capitulo(slug):
    """
    Chama a API e devolve o número do capítulo mais recente.
    Retorna None em caso de erro.
    """
    url = f"{API_BASE}/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        print(f"    [!] Erro de rede: {e}")
        return None

    if resp.status_code != 200:
        print(f"    [!] API retornou status {resp.status_code}")
        return None

    try:
        data = resp.json()
    except ValueError:
        print("    [!] Resposta não é JSON válido")
        return None

    # Tenta primeiro recentChapters (menor, mais rápido)
    # Se não existir, usa chapters completo
    for campo in ("recentChapters", "chapters"):
        lista = data.get(campo, [])
        if lista:
            try:
                numeros = [int(c["number"]) for c in lista if "number" in c]
                if numeros:
                    return max(numeros)
            except (ValueError, TypeError):
                continue

    print("    [!] Nenhuma lista de capítulos encontrada na resposta")
    return None


def avisar_telegram(token, chat_id, nome, base, novos):
    """novos = lista de números novos (ex: [167, 168])."""
    if not token or not chat_id:
        return
    if len(novos) == 1:
        cabec = f"📖 Capítulo {novos[0]} disponível!"
    else:
        cabec = f"📖 {len(novos)} capítulos novos! ({novos[0]}–{novos[-1]})"

    link = f"{base}/{novos[-1]}"
    texto = f"{cabec}\n\n*{nome}*\n{link}"

    api = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            api,
            data={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"},
            timeout=20,
        )
        if r.status_code != 200:
            print(f"    [!] Telegram erro ({r.status_code}): {r.text}")
    except requests.RequestException as e:
        print(f"    [!] Erro ao enviar Telegram: {e}")


# ------------------------------------------------------------------
def rodar_verificacao(token, chat_id):
    """Percorre a lista, avisa no Telegram e atualiza o estado.

    Retorna a quantidade total de capítulos novos encontrados.
    Reaproveitado pelo comando /check do bot.
    """
    obras = ler_lista()
    if not obras:
        print("Nenhuma obra em mangas.txt.")
        return 0

    estado      = carregar_estado()
    total_novos = 0

    print(f"Verificando {len(obras)} obra(s)...\n")

    for base, cap_inicial, slug in obras:
        nome     = nome_legivel(slug)
        conhecido = max(cap_inicial, int(estado.get(slug, 0)))
        print(f"• {nome}  (último conhecido: {conhecido})")

        ultimo = obter_ultimo_capitulo(slug)

        if ultimo is None:
            print("    → não foi possível verificar, pulando\n")
            time.sleep(DELAY)
            continue

        if ultimo > conhecido:
            novos = list(range(conhecido + 1, ultimo + 1))
            print(f"    → {len(novos)} capítulo(s) novo(s): {novos}")
            avisar_telegram(token, chat_id, nome, base, novos)
            estado[slug] = ultimo
            total_novos += len(novos)
        else:
            print(f"    → sem novidade (último disponível: {ultimo})")

        print()
        time.sleep(DELAY)

    salvar_estado(estado)
    print(f"Resumo: {total_novos} capítulo(s) novo(s) no total.")
    return total_novos


def main():
    token   = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[!] TELEGRAM_TOKEN/TELEGRAM_CHAT_ID não definidos — só log, sem notificação.\n")

    rodar_verificacao(token, chat_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())