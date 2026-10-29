# Xodus engine for SkullKey

SkullKey's Xbox tab uses the [Xodus](https://github.com/xodus-gaming) engine
(`xodus-cli`, `xodus-service`, GPL-3.0, [LICENSE](LICENSE)) as packaged by
[Xodus Nexus](https://github.com/domsvoboda/xodus-nexus).

The release asset `xodus-engine-skullkey-0.2.13-linux-x86_64.tar.xz` is the
official Nexus backend **0.2.13** source, unmodified, built with one upstream
Cargo feature switched on: `xodus/key-chain-file`. It keeps the Microsoft
sign-in in `~/.xodus-keyring.ron` (mode 600) instead of the Secret Service
(KDE Wallet), whose password prompt cannot be answered in Game Mode.

## Source

- Archive: `xodus-nexus-backend-0.2.13-linux-x86_64-source.tar.xz` from the
  [backend-v0.2.13 release](https://github.com/domsvoboda/xodus-nexus/releases/tag/backend-v0.2.13)
  (checked against its published `.sha512sum`).

## Build

```sh
tar xJf xodus-nexus-backend-0.2.13-linux-x86_64-source.tar.xz
podman run --rm -v "$PWD":/src:Z docker.io/library/rust:1.99-bookworm bash -c '
  apt-get update -qq && apt-get install -y -qq pkg-config libssl-dev protobuf-compiler cmake libdbus-1-dev clang
  cd /src/source
  cargo build --locked --offline --release --no-default-features --features xodus/key-chain-file -p xodus-cli -p xodus-service'
mkdir xodus-engine-skullkey
cp source/target/release/xodus-cli source/target/release/xodus-service source/LICENSE xodus-engine-skullkey/
# BUILD-METADATA.json records the source tag and checksums; SkullKey reads
# its source_tag to know which engine version is installed.
tar -cJf xodus-engine-skullkey-0.2.13-linux-x86_64.tar.xz xodus-engine-skullkey
sha512sum xodus-engine-skullkey-0.2.13-linux-x86_64.tar.xz
```

The SHA-512 of the published asset is pinned in
`defaults/scripts/xbox_tools.py` (`OWN_ENGINE_SHA512`); SkullKey refuses any
other file and falls back to the official engine if the download fails.

Each Nexus runtime names the engine it needs (`requiresBackendVersion` in
`XODUS_NEXUS_PATCH.json`, from
[nexus-runtime](https://github.com/domsvoboda/nexus-runtime)); SkullKey keeps
the previous runtime until the engine fits.
