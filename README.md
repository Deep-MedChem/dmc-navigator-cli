# DMC Navigator CLI

The command-line application for DeepMedChem Navigator. It is built on the chemistry-thin
[`deepmedchem`](https://github.com/Deep-MedChem/deepmedchem-python) platform SDK and contains no
RDKit, models, databases, or proprietary search implementation.

```bash
pipx install dmc-navigator
navigator auth login
navigator search --smiles 'CCO'
navigator search-cheese --smiles 'CCO' --scorer shape
navigator search --smiles 'CCO' --shortlist-multiplier 0
navigator search-cheese --smiles 'CCO' --scorer shape --shortlist-multiplier 0
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

For Python and notebook use, install and import the platform SDK directly:

```python
from deepmedchem import Client

with Client(api_key="...") as dmc:
    neighbors = dmc.search("CCO", database="enamine-real-v5a", limit=20)
    shape_hits = dmc.search_cheese(
        "CCO", database="enamine-real-v5a", scorer="shape", limit=20
    )
    motif_hits = dmc.search_substructure(
        "C(=O)N1CCC1", query_format="smarts", database="enamine-real-v5a"
    )
    molecules = dmc.sample(database="enamine-real-v5a", count=100, seed=12345)
```

`shortlist_multiplier=0` is explicit no-over-fetch mode for Morgan and CHEESE search: exactly
`limit` candidates are proposed and scored. It may return fewer valid unique products because no
extra candidates are available to replace invalid assemblies or duplicates.

Composable selections use a copy-on-write builder that emits the exact public
`molecule-selection/1` document and performs no local chemistry:

```python
from deepmedchem import Client, Run, Selection

selection = (
    Selection.from_database("enamine-real-v5a")
    .sample(distribution="route_product_tuple", seed=42)
    .require_preset("lipinski-ro5/v1")
    .limit(1_000)
    .include("properties", "constraint_evidence", "execution_plan")
)

with Client(api_key="...") as dmc:
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

`deepmedchem.AsyncClient` provides matching async methods and async result/event iterators.
Imports from `dmc_navigator` remain as compatibility aliases for the 0.3 release.

Authentication is read from the constructor, `DMC_API_KEY`, `DMC_NAVIGATOR_TOKEN`, or the OS
credential store populated by `navigator auth login`. Credentials are never included in exception
messages. The canonical documentation is at <https://docs.deepmedchem.com/docs/python/quickstart>.
