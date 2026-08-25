# DMC Navigator CLI

Thin API-first client for DMC's synthon-native search platform. The base package contains
no RDKit, model, database, or proprietary optimization code.

The Python distribution name is `dmc-navigator` and the command is `navigator`.

```bash
pipx install dmc-navigator
printf '%s' "$DMC_PLATFORM_TOKEN" | navigator auth login --token-stdin
navigator doctor
navigator search --smiles 'CCO' --scorer shape --quality balanced
```

Before the PyPI trusted-publisher gate is approved, attested source/wheel artifacts are
also attached to each GitHub release and can be installed directly with `pipx`.

The MVP uses a scoped platform token read from stdin or `DMC_NAVIGATOR_TOKEN`. Browser PKCE
and device-code login will replace token bootstrap when the identity endpoints are ready.
