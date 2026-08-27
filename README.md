# DMC Navigator CLI

Thin API-first client for DMC's synthon-native search platform. The base package contains
no RDKit, model, database, or proprietary optimization code.

The Python distribution name is `dmc-navigator` and the command is `navigator`.

```bash
pipx install dmc-navigator
navigator auth login
navigator doctor
navigator search --smiles 'CCO' --scorer shape
```

Before the PyPI trusted-publisher gate is approved, attested source/wheel artifacts are
also attached to each GitHub release and can be installed directly with `pipx`.

`navigator auth login` opens CHEESE in a browser. Sign in (or create an account), choose an
existing shared CHEESE API key or let CHEESE create one, and approve the one-time login. The CLI
stores the returned key in the operating-system credential store. It never receives your CHEESE
password or browser session.

For headless automation, pipe a CHEESE API key to `navigator auth login --token-stdin` or provide
`DMC_NAVIGATOR_TOKEN`. API access and search entitlements come from the CHEESE account and key;
Navigator does not introduce a separate license key format.

Search defaults to the Fast operating point: ten Morgan-OR proposals are assembled and
reranked for every requested neighbor, so the default 100-neighbor request uses a shortlist
of 1,000. API users can change that ratio explicitly with `--shortlist-multiplier`; for
example, `--limit 100 --shortlist-multiplier 20` reranks 2,000 proposals.
