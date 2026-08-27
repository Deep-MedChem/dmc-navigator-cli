# DMC Navigator CLI

Thin API-first client for DMC's synthon-native search platform. The base package contains
no RDKit, model, database, or proprietary optimization code.

The Python distribution name is `dmc-navigator` and the command is `navigator`.

```bash
pipx install dmc-navigator
navigator auth login
navigator doctor
navigator search --smiles 'CCO' --scorer shape

# Preset plus a tighter custom window; either side of MIN:MAX may be blank.
navigator search --smiles 'CCO' --scorer morgan \
  --property-preset lipinski-ro5 \
  --property 'MolWt::450' --property 'MolLogP:-1:4'

# Keep the lowest-scoring half under the pinned distilled hERG teacher before
# product assembly. The endpoint IDs available for a release are in `navigator catalog`.
navigator search --smiles 'CCO' --scorer shape \
  --admet-acquisition 'openadmet-herg-pchembl:minimize:0.5'
```

Property requests are applied by the platform as a fast synthon-additive prefilter and,
by default, recalculated exactly on assembled hits. Use
`--no-exact-property-postfilter` only when approximate boundary leakage is acceptable.

`--admet-acquisition` is explicitly a fast, teacher-distilled rank-quantile acquisition
step. It is not a safety claim or an authoritative ADMET filter. Repaired/out-of-domain
synthons are retained rather than silently pruned, and exact assembled-product rescoring
is still required for any reported endpoint value.

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
