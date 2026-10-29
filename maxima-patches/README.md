# Maxima source patches

Base: Maxima v0.14.3, commit `afea420242f282019b1ffd7d9e223d0631d300dc`.
Apply `skullkey-locale.patch` first, then `skullkey-ea-installers.patch`.
The second patch was checked against a fresh copy with the first patch applied.

These are source changes for the next client build. Adding the patch does not
replace the released client: the EA adapter still checks its pinned binary and
release URL. Update those together only when publishing the approved client asset.

## Installer integration

The content downloader passes the owned offer identity to the installer stage.
Legacy keys are requested only if the manifest's installer parameters contain
`{cdkey}` or `%CDKEY%` (case-insensitive). The resolver matches that offer and its
catalog content ID, accepts active unexpired rights, deduplicates identical keys,
and refuses ambiguous values. A missing required key stops the installer explicitly.
Ordinary installer manifests do not query the key API.

Parameters use Windows quoting rules for balanced input, with explicit errors for
malformed quoting and control characters. Substitution preserves a quoted install
path as one argument. Keys are not stored in manifests or exported through Debug
or serialization. Key-bearing installers use a separate runner that drains both
output streams without forwarding or retaining their contents, and disables Wine
traces and Proton command dumps for that invocation. Cancellation is checked before
and after key resolution.

This is an explicit parameter contract, **not** automatic registry injection for
all older games. There is no guessed registry path and no game-specific key mapping.
Battlefield 2142's installer has not been tested; this patch must not be advertised
as a confirmed fix for its CD-key error without that validation.

The CLI now returns a nonzero process status for errors instead of only printing
an error and exiting successfully. The patch propagates terminal
download/installer failures to the CLI, wakes
waiters on success, failure and cancellation, and clears abandoned current/pending
queue entries when resume is disabled. The adapter supports explicit nonzero
Touchup exits only after a fresh installer completion and independent installation
verification; unrelated CLI failures still fail.

## Validation

- 27 Rust regression tests pass (the two account-dependent cloud-sync tests are
  not included in that filter).
- An additional native Windows fixture test passes through Wine with a dummy key.
  The fixture verifies the received argument and writes the dummy value to both
  streams; neither stream is forwarded. It runs only with explicit isolated
  fixture/runtime configuration and is ignored by default.
- The Linux x86-64 musl CLI builds. GUI and native Windows builds are not validated.
- Private Linux CLI qualification: Generals reinstallation succeeds with
  Touchup 0; Battlefield 1942 completes after independent verification with a
  persisted Touchup 3 warning. A controlled CLI failure returns status 1.
- Owned-game key resolution and normal installer compatibility were tested
  separately. These do not establish that every older game's manifest declares
  the supported key input.

Example build checks inside the configured Rust build environment:

```sh
cargo test --locked --release --target x86_64-unknown-linux-musl -p maxima-lib regression
cargo build --locked --release --target x86_64-unknown-linux-musl -p maxima-cli
```

The native fixture test is
`core::manifest::native_installer_key_smoke::key_reaches_windows_fixture_without_forwarding_its_output`.
It requires `SK_EA_NATIVE_KEY_SMOKE_DIR` containing the dummy installer fixture,
plus `MAXIMA_WINE_COMMAND` pointing to an isolated-prefix UMU proxy. Never use an
existing game prefix for this test.
