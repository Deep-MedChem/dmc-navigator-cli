# DMC Navigator Python client and CLI

The supported API-first client for DeepMedChem's hosted chemical-space platform. The package is
chemistry-thin: it contains no RDKit, models, databases, or proprietary search implementation.

```bash
pipx install dmc-navigator
navigator auth login
navigator search --smiles 'CCO'
navigator search-cheese --smiles 'CCO' --scorer shape
navigator search-substructure --query 'C(=O)N1CCC1' --query-format smarts
navigator sample --database enamine-real-v5a --count 100 --seed 12345
```

A file containing more than one molecule always creates one visible durable `selection_batch` run;
the CLI never loops over synchronous searches:

```bash
navigator search --input leads.smi --limit 10 --json
navigator run watch run_01K...
navigator run results run_01K...
```

The Python API exposes the same operations:

```python
from dmc_navigator import DMCClient

with DMCClient(api_key="...") as dmc:
    neighbors = dmc.search("CCO", database="enamine-real-v5a", limit=20)
    shape_hits = dmc.search_cheese(
        "CCO", database="enamine-real-v5a", scorer="shape", limit=20
    )
    motif_hits = dmc.search_substructure(
        "C(=O)N1CCC1", query_format="smarts", database="enamine-real-v5a"
    )
    molecules = dmc.sample(database="enamine-real-v5a", count=100, seed=12345)
```

Composable selections use a copy-on-write builder that emits the exact public
`molecule-selection/1` document and performs no local chemistry:

```python
from dmc_navigator import DMCClient, Run, Selection

selection = (
    Selection.from_database("enamine-real-v5a")
    .sample(distribution="route_product_tuple", seed=42)
    .require_preset("lipinski-ro5/v1")
    .limit(1_000)
    .include("properties", "constraint_evidence", "execution_plan")
)

with DMCClient(api_key="...") as dmc:
    validation = dmc.selections.validate(selection)
    estimate = dmc.selections.estimate(validation.normalized_selection)
    if estimate.execution_tier == "synchronous":
        result = dmc.selections.create(estimate.normalized_selection)
    else:
        run = dmc.runs.create(
            Run.selection(estimate.normalized_selection),
            idempotency_key="lipinski-sample-2026-08-v1",
        )
```

`AsyncDMCClient` provides matching async methods and async result/event iterators.
`NavigatorClient` remains as a deprecated compatibility facade for the 0.3 release.

Authentication is read from the constructor, `DMC_API_KEY`, `DMC_NAVIGATOR_TOKEN`, or the OS
credential store populated by `navigator auth login`. Credentials are never included in exception
messages. The canonical documentation is at <https://docs.deepmedchem.com/docs/python/quickstart>.
