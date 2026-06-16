# 📖 Rastreador de capítulos de mangá (vários ao mesmo tempo)

Verifica automaticamente, **2x por dia**, se saiu capítulo novo das suas
obras e te avisa por **Telegram**. Roda de graça na nuvem (GitHub Actions) —
você não precisa deixar nenhum PC ligado. Aguenta dezenas de mangás.

---

## O que tem aqui

| Arquivo | Pra que serve |
|---|---|
| `mangas.txt` | **A sua lista.** Você cola aqui os links, um por linha. |
| `check_manga.py` | O verificador. Roda por toda a lista. |
| `bot_commands.py` | Processa os comandos que você manda pro bot (`/add`, `/list`, etc.). |
| `manga_state.json` | Guarda o progresso (atualizado sozinho; começa vazio). |
| `telegram_offset.json` | Marca quais mensagens já foram lidas (atualizado sozinho). |
| `.github/workflows/check.yml` | Agenda as verificações de capítulo novo. |
| `.github/workflows/bot.yml` | Processa os comandos a cada ~15 min. |

---

## A lista (mangas.txt)

Cole **um link por linha**, com o número do **último capítulo que você já
leu** no final — exatamente como os links estão hoje. Exemplo:

```
https://toonlivre.net/o-retorno-do-cao-de-caca-dos-baskerville/165
https://toonlivre.net/nome-de-outro-manga/42
https://toonlivre.net/mais-um-manga/210
```

- Não precisa digitar título nem nada: o script separa sozinho a base e o
  capítulo, e gera o nome a partir do link.
- Linhas começando com `#` são ignoradas (útil pra desativar um mangá sem
  apagar).
- Pra acompanhar uma obra nova depois, é só adicionar a linha dela.
- Funciona pra qualquer site no formato `endereço/numero`, não só toonlivre.

> **Importante:** depois do primeiro acompanhamento, o progresso real fica
> no `manga_state.json` (atualizado automaticamente). O número no `mangas.txt`
> serve só como ponto de partida — não precisa ficar editando ele à mão.

---

## Comandos pelo Telegram

Agora dá pra gerenciar a lista **mandando mensagem pro próprio bot** — não
precisa mais editar o `mangas.txt` na mão.

| Comando | O que faz |
|---|---|
| `/add <link>` | Adiciona uma obra ao monitoramento. |
| `/remove <link ou nome>` | Remove uma obra da lista. |
| `/list` | Mostra todas as obras monitoradas e o capítulo atual. |
| `/check` | Força uma verificação imediata de capítulos novos. |
| `/help` | Mostra a ajuda. |

**Sobre o `/add`:**
- Pode mandar o link **com** ou **sem** o número no final.
  - Com número (`.../torre-de-deus/652`) → começa a monitorar a partir desse capítulo.
  - Sem número (`.../torre-de-deus`) → o bot consulta o site e começa a partir
    do **capítulo atual**, pra você não levar uma enxurrada de avisos antigos.

> ⏳ **Não é instantâneo.** Como tudo roda de graça no GitHub Actions (sem PC
> ligado), os comandos são processados na próxima rodada do `bot.yml`
> (a cada ~15 min, às vezes um pouco mais — o agendamento do GitHub atrasa).
> O bot responde no Telegram assim que processa.

> 🔒 **Só você manda.** O bot só obedece a mensagens vindas do
> `TELEGRAM_CHAT_ID` cadastrado. Mensagens de qualquer outra pessoa são ignoradas.

> 💡 **Dica:** pra aparecer o menu de comandos no Telegram, fale com o
> **@BotFather**, mande `/setcommands`, escolha seu bot e cole:
> ```
> add - Adiciona um mangá (manda o link junto)
> remove - Remove um mangá (link ou nome)
> list - Lista os mangás monitorados
> check - Verifica capítulos novos agora
> help - Mostra a ajuda
> ```

---

## Passo a passo (uma vez só)

### 1. Criar o bot do Telegram
1. No Telegram, procure por **@BotFather** e mande `/newbot`.
2. Dê um nome e um @usuario pro bot.
3. Ele te devolve um **token** parecido com `123456:ABC-DEF...`. Guarde.

### 2. Descobrir seu Chat ID
1. Mande qualquer mensagem (ex: "oi") pro bot que você criou.
2. Abra no navegador (troque `SEU_TOKEN`):
   `https://api.telegram.org/botSEU_TOKEN/getUpdates`
3. Procure por `"chat":{"id":` — esse número é o seu **chat id**.

### 3. Subir os arquivos no GitHub
1. Crie uma conta em github.com (se não tiver) e clique em **New repository**.
   Pode deixar **Private**.
2. Suba os arquivos mantendo a estrutura de pastas
   (o `check.yml` precisa ficar dentro de `.github/workflows/`).
3. Edite o `mangas.txt` colando seus ~40 links.

### 4. Cadastrar os segredos
No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
Crie dois:
- `TELEGRAM_TOKEN` → o token do passo 1
- `TELEGRAM_CHAT_ID` → o número do passo 2

### 5. Testar
Vá em **Actions → "Verificar capítulo novo" → Run workflow**.
Veja o log; se estiver tudo certo, daí pra frente roda sozinho 2x por dia.

---

## Como saber se está funcionando

O log mostra, pra cada obra, o último capítulo conhecido e se achou algo novo.
Quando sai capítulo novo, você recebe no Telegram (uma mensagem por obra,
agrupando se saíram vários) **e** o `manga_state.json` é atualizado sozinho.

---

## Mudar os horários

No `check.yml`, os horários estão em **UTC** (Brasil = UTC-3):

| Quero rodar (Brasil) | Coloco no cron (UTC) |
|---|---|
| 09:00 | `0 12 * * *` |
| 21:00 | `0 0 * * *` |
| 07:00 e 19:00 | `0 10 * * *` e `0 22 * * *` |

> O agendamento do GitHub Actions às vezes atrasa alguns minutos — é normal.

---

## Se o site bloquear o acesso (status 403/503)

Alguns sites usam proteção anti-bot (tipo Cloudflare). Se no log aparecer
muitos **403/503**, a verificação simples não passa. Solução:

1. Troque `pip install requests` por `pip install requests cloudscraper`
   no `check.yml`.
2. No `check_manga.py`, troque `import requests` por:
   ```python
   import cloudscraper
   requests = cloudscraper.create_scraper()
   ```
   (o resto continua igual.)

Se ainda assim não passar, me avise que partimos pra outra abordagem.
