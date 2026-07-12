# 🗝️ SkullKey

> 🌐 [EN](../README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**A chave que abre todas as lojas.** Joga as tuas bibliotecas Epic Games, GOG e Amazon Games diretamente no modo de jogo em SteamOS / Bazzite — sessão, instalação, arranque. Sem nunca passar pelo modo de secretária.

## Funcionalidades

- 🎮 **100% modo de jogo** — explora, inicia sessão, instala e joga sem tocar na secretária
- 🏪 **Quatro lojas, grátis** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)), Amazon Games ([nile](https://github.com/imLinguin/nile)) e **miHoYo/HoYoverse**
- ✨ **Loja miHoYo** — Genshin Impact, Honkai: Star Rail, Zenless Zone Zero e Honkai Impact 3rd, instalados a partir do canal oficial *sophon* da HoYoverse: downloads por chunks em paralelo (~100 MB/s), atualizações que só transferem os ficheiros alterados, retoma após reinício, anti-cheat gerido automaticamente (jadeite) para HI3/HSR
- 🩹 **Extras miHoYo** — atualizações delta (só o diff, ~4× menores), seletor de idioma de dublagem, **verificação e reparação** de integridade, e anti-cheat de Zenless Zone Zero tratado automaticamente
- 🏛️ **Classics Reborn** — 52 ports nativos open source e recompilações de clássicos (Zelda, Mario 64, Perfect Dark, Diablo, Fallout, Doom, C&C Generals, Morrowind, Sonic Unleashed, Unreal Tournament, Freespace 2, LEGO Island…), instalados a partir das releases oficiais de cada projeto, com instruções claras para os seus ficheiros de jogo originais (9 línguas)
- 👥 **Um espaço de lojas por conta Steam (multi-conta)** — cada utilizador Steam da máquina tem os seus próprios logins e bibliotecas Epic/GOG/Amazon; mudar de conta Steam muda tudo automaticamente (os logins existentes ficam com a conta ativa na primeira utilização)
- 📦 **Atualização automática dos jogos** — uma passagem diária em segundo plano mantém todos os jogos instalados atualizados, em todas as lojas e para todas as contas
- 💾 **Backup e restauração de saves** — faça backup do progresso de um jogo pela página dele com uma ação (via [ludusavi](https://github.com/mtkennerly/ludusavi), provisionado automaticamente) e restaure quando quiser — jogos Epic, GOG e Amazon, backups em `~/.local/share/skullkey-saves`
- 📺 **Media e apps** — secções extra de TV e Vídeo, Música, Jogo na nuvem e Apps e ferramentas (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 apps selecionadas), mantidas atualizadas automaticamente
- 🖼️ **Atalhos com aspeto nativo** — os jogos instalados recebem automaticamente o artwork oficial da Steam (cápsula vertical, hero, logo), com a gamesdb da GOG como recurso
- 📚 **Coleções Steam** — os jogos instalados são agrupados por loja («Epic», «GOG», «Amazon») na tua biblioteca
- ⚙️ **Proton gerido pela Steam** — prefixos, definições por jogo e limites de FPS funcionam exatamente como nos jogos Steam
- 🔄 **Atualização automática** — as novas versões instalam-se silenciosamente em segundo plano (desativável nas Definições)
- 🌐 **9 idiomas** — a interface segue automaticamente o idioma da consola (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Acesso rápido** — cartões coloridos por loja no QAM, atalho opcional L3+R3 para abrir a loja em qualquer lugar
- 🐧 **Compatibilidade** — trabalhamos ativamente para suportar todos os SO capazes de executar o Steam em modo de jogo / Big Picture (Linux por agora): deteção portátil, sem suposições específicas de distribuição Notas por distribuição: [docs/OS-NOTES.md](OS-NOTES.md).

## 📸 Capturas de ecrã

<p align="center">
  <img src="img/skullkey-epic.jpg" width="49%" alt="Epic Games library"/>
  <img src="img/skullkey-mihoyo.jpg" width="49%" alt="miHoYo tab"/>
</p>
<p align="center">
  <img src="img/skullkey-classics.jpg" width="49%" alt="Classics Reborn"/>
  <img src="img/skullkey-game-details.jpg" width="49%" alt="Game details"/>
</p>
<p align="center">
  <img src="img/skullkey-steam-collection.jpg" width="49%" alt="Steam collection"/>
  <img src="img/skullkey-steam-game-page.jpg" width="49%" alt="Installed game in Steam"/>
</p>

## Instalação

Via Decky Loader, sem passar pelo desktop:

1. Instale o [Decky Loader](https://decky.xyz/)
2. Ative o **modo de programador** nas definições gerais do Decky
3. Definições do Decky → **Programador** → *Instalar plugin a partir de URL*:
   `https://github.com/Necrosiak/SkullKey/releases/latest/download/SkullKey.zip`

Ou compile a partir do código-fonte:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Depois abre o plugin e instala as dependências das lojas em **Definições → Dependências**.

## Utilização

1. Abre o menu de acesso rápido (…) → SkullKey
2. Escolhe um cartão de loja (Epic / GOG / Amazon) e inicia sessão
3. Instala um jogo — chega à tua biblioteca Steam com o seu artwork, numa coleção por loja
4. Joga!

## 🐛 Issues e ideias — não hesite!

Um bug, algo que trava, um comportamento estranho na sua distribuição? Uma
ideia? **Abra uma [issue](https://github.com/Necrosiak/SkullKey/issues)** —
cada relato orienta diretamente o que será construído a seguir, e nenhum
relato é pequeno demais. Para nos ajudar a corrigir rápido, inclua se puder:

- a sua distribuição e versão (Bazzite 42, CachyOS, Ubuntu 24.04…) e como o Steam roda (modo jogo / Big Picture / desktop)
- a versão do plugin (Definições → Sobre) e a loja/aba envolvida
- o que fez, o que esperava, o que aconteceu em vez disso
- os logs: `~/homebrew/logs/SkullKey/` (problemas de dependências: `ensure_deps.log`)

Pedidos de funcionalidades e relatos de «funciona!» em configurações incomuns
valem tanto quanto — dizem-nos o que suportar a seguir.

## Créditos

O SkullKey é um fork do [Junk-Store](https://github.com/ebenbruyns/junkstore) de **Eben Bruyns** (BSD-3-Clause) — obrigado pelas fundações sólidas. Motores das lojas: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) e [nile](https://github.com/imLinguin/nile).

Projeto comunitário independente, não afiliado ao Junk-Store, Valve, Epic Games, GOG nem Amazon.

## Licença

BSD-3-Clause — ver [LICENSE](../LICENSE).
