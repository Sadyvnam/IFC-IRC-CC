# IFC Model Quality Analyzer

Diagnostic IFC exchange-readiness assessment for sustainability-oriented workflows.

This repository evaluates the extent exchanged IFC model contains usable information for:

1. Whole Life Carbon Assessment (WLCA) inputs
2. Circularity-related checks/ decisionmaking

Please find instructions to run the file at the bottom of this file.

## What This Tool Is

- A rule-based checker for whether IFC exchange data is usable for the above purpose
- A category-based analyzer that groups elements into Building Element Categories (BECs) and evaluates their information readiness, which are from RICS 2.0 WLCA
- A research-oriented diagnostic tool

## What This Tool Is Not

- Not a full LCA engine
- Not a direct EN 15978 calculator
- Not a generic BIM QA/QC suite
- Not a clash detection tool
- Not an AI auto-correction system
- Not a circularity score calculator

## Core Positioning

When extending or interpreting this project, preserve these assumptions:

- The system evaluates decision-readiness, not correctness
- The system evaluates exchanged IFC data, not native authoring-tool fidelity
- Lower assessment levels are intended to be more deterministic
- Higher assessment levels are more limited, partial, heuristic
- Category-specific logic is intentional and should not be flattened without care
- Outputs should be traceable

## Assessment Structure

The analyzer splits the IFC model into Building Element Categories and evaluates each
category across readiness levels:

- `L1`: Identification / classification readiness
- `L2`: Geometry / quantity readiness
- `L3`: Material / property / documentation readiness
- `L4a`: Environmental linkability / traceability
- `L4b`: Circularity / end-of-life / reversibility signals

Interpretation guidance:

- `L1` and most of `L2` are intended to be deterministic presence/absence checks
- `L3` mixes deterministic checks with best-effort interpretation
- `L4a` and especially `L4b` should be treated as signal detection, not proof of
  downstream sustainability performance

## Active Pipeline

```text
App.py -> category_XX() -> Excel export
```

Other legacy pipelines is not the main reporting path for the current Excel output.

Note:

- The exported Excel report includes only categories wired in `App.py`
- BEC `1.2` retaining-wall/basement-scope logic is intentionally not exported through standalone `c12.py` yet
- Deterministic `BASESLAB` rows for BEC `1.2` are exported through `category_22()` slab routing
- Top-level BEC `2.7` internal-wall reporting is exported through `category_21()` wall routing, not through standalone `c27.py`
- Active BEC `5.5` numbering is defined by `category_55()` in `src/wlca_functions/c55.py`

Current category-boundary:

- BEC `1.2` is not yet exported as a standalone `c12.py` category in the main pipeline
- Its deterministic lowest-slab handling is currently absorbed through existing slab routing, especially via `c22.py` when `IfcSlab.PredefinedType == BASESLAB`
- Active BEC `1.2` output from `c22.py` keeps the RICS category name "Basement retaining walls and lowest slab" but includes a category-level info issue noting that retaining-wall detection is not currently assessed
- Top-level BEC `2.7` rows, overview, and indicators are produced from `src/wlca_functions/c21.py` when wall routing identifies internal walls `src/wlca_functions/c27.py` exists as non-authoritative exploratory/future logic, including `2.7.1` / `2.7.2` ideas that are not currently split in the active report
- Active `2.7` routing avoids semantic text-token interpretation and relies on deterministic IFC signals such as `LoadBearing`, `IsExternal`, and partition-style `PredefinedType`
- Exported BEC `5.5` reporting currently comes from `src/wlca_functions/c55.py` via `category_55()`
- Transport equipment is handled deterministically inside `category_55()` using `IfcTransportElement.PredefinedType`

## Typical IFC Signals Used

The checker relies on a mix of:

- IFC class and `PredefinedType`
- Quantity sets and geometry-derived fallbacks
- Material associations
- Classification associations
- Document associations
- System and group assignments
- Host / covering / connection relationships
- Environmental property sets
- Manufacturer and service-life metadata

These are not consistently present across exported IFC files, so absence is common and should be interpreted carefully. Recurring IFC limitations include:

- Generic proxies such as `IfcBuildingElementProxy`
- Missing or weak `PredefinedType`, classification links
- Incomplete or inconsistent quantity sets
- Unrealistic solid modeling that can distort derived quantities
- Double-counting risks across coverings, hosts and decompositions
- Weak or generic material naming
- Document links that exist but are unusable
- Sparse explicit circularity or disassembly information

These are expected modeling constraints, not edge cases.

## Output Philosophy

Outputs are intended to support:

- Diagnosis
- Traceability
- Issue review
- Category-level readiness interpretation
- Future research extension

The tool commonly produces structured Excel outputs containing category
summaries, issue rows, indicators, and element-level extracted data.

Scores, where present, should be read as information-readiness indicators. They do not
represent actual carbon impact or guarantee valid downstream WLCA.

## Running the Tool

Environment used for current validation:

- Python `3.11`

Install dependencies:

```bash
pip install -r requirements.txt
```

Launch the GUI:

```bash
python App.py
```

Representative automated usage:

```python
from App import process_file_upload
## link your ifc file here, the path is example
process_file_upload("src/ARK_NordicLCA_Housing_Timber_BuildingPermit_Revit.ifc", print)
```

## Sample Fixtures And Outputs

- The repository does not nor intends to contain IFC files.
- Example `.xlsx` outputs for some public IFC files are kept in `src/` as reference outputs

## Working Notes

- Category wiring and scope notes: `src/wlca_functions/SCOPE.md`

## Research Context

This codebase supports research on the integration of circularity and decarbonization
principles in the built environment, with a focus on whether IFC-based building models
contain sufficiently usable exchanged data for sustainability-oriented workflows.

Changes should preserve the distinction between:

- readiness assessment and final sustainability assessment
- deterministic checks and heuristic inference
- explicit exchanged data and interpretive assumptions
