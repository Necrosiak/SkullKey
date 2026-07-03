# 🗝️ SkeletonKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**A chave que abre todas as lojas.** Joga as tuas bibliotecas Epic Games, GOG e Amazon Games diretamente no modo de jogo em SteamOS / Bazzite — sessão, instalação, arranque. Sem nunca passar pelo modo de secretária.

## Funcionalidades

- 🎮 **100% modo de jogo** — explora, inicia sessão, instala e joga sem tocar na secretária
- 🏪 **Três lojas, grátis** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)) e Amazon Games ([nile](https://github.com/imLinguin/nile))
- 📺 **Media e apps** — secções extra de TV e Vídeo, Música, Jogo na nuvem e Apps e ferramentas (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 apps selecionadas), mantidas atualizadas automaticamente
- 🖼️ **Atalhos com aspeto nativo** — os jogos instalados recebem automaticamente o artwork oficial da Steam (cápsula vertical, hero, logo), com a gamesdb da GOG como recurso
- 📚 **Coleções Steam** — os jogos instalados são agrupados por loja («Epic», «GOG», «Amazon») na tua biblioteca
- ⚙️ **Proton gerido pela Steam** — prefixos, definições por jogo e limites de FPS funcionam exatamente como nos jogos Steam
- 🔄 **Atualização automática** — as novas versões instalam-se silenciosamente em segundo plano (desativável nas Definições)
- 🌐 **9 idiomas** — a interface segue automaticamente o idioma da consola (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Acesso rápido** — cartões coloridos por loja no QAM, atalho opcional L3+R3 para abrir a loja em qualquer lugar

## Instalação

Transfere `SkeletonKey.zip` da [última versão](https://github.com/Necrosiak/SkeletonKey/releases/latest) e instala-o através do Decky Loader (modo de programador → Instalar a partir de ZIP), ou compila a partir do código-fonte:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Depois abre o plugin e instala as dependências das lojas em **Definições → Dependências**.

## Utilização

1. Abre o menu de acesso rápido (…) → SkeletonKey
2. Escolhe um cartão de loja (Epic / GOG / Amazon) e inicia sessão
3. Instala um jogo — chega à tua biblioteca Steam com o seu artwork, numa coleção por loja
4. Joga!

## Créditos

O SkeletonKey é um fork do [Junk-Store](https://github.com/ebenbruyns/junkstore) de **Eben Bruyns** (BSD-3-Clause) — obrigado pelas fundações sólidas. Motores das lojas: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) e [nile](https://github.com/imLinguin/nile).

Projeto comunitário independente, não afiliado ao Junk-Store, Valve, Epic Games, GOG nem Amazon.

## Licença

BSD-3-Clause — ver [LICENSE](LICENSE).
