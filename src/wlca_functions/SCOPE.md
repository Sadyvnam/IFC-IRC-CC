# WLCA Category Scope & Implementation Status

## Assessment Level Definitions

| Level   | Focus                                                 | Typical IFC Evidence                                                                                                                                                                                                  |
| ------- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **L1**  | Identification and classification readiness           | IFC entity type, `PredefinedType`, `IfcTypeObject`, `IfcRelAssociatesClassification`, `IfcClassificationReference`                                                                                                    |
| **L2**  | Geometry and quantity readiness                       | shape representation, indexed geometry, `IfcElementQuantity`, `IfcQuantityArea`, `IfcQuantityVolume`, `IfcQuantityLength`; for pipe/duct elements, explicit common-pset dimensions such as length or nominal diameter |
| **L3**  | Material / property / documentation readiness         | `IfcMaterial`, `IfcMaterialLayerSet`, `IfcMaterialConstituentSet`, `MassDensity`, common psets, `Pset_ServiceLife`, `IfcRelAssociatesDocument`                                                                        |
| **L4a** | Environmental linkability / LCA-relevant traceability | `Pset_EnvironmentalImpactIndicators`, `IfcDocumentReference`, EPD-style identifiers, manufacturer/product references, URLs/codes                                                                                      |
| **L4b** | Circularity-related signals                           | `IfcRelConnectsWithRealizingElements`, `IfcMechanicalFastener`, direct element connections, explicit system/group membership, `Pset_ManufacturerOccurrence`, product identifiers, limited disassembly-relevant cues   |

### Interpretation Notes

- **L1–L2** are intended to be the most deterministic levels.
- **L3** is partly deterministic, but may become ambiguous when material naming or pset usage is weak.
- **L4a–L4b** should be interpreted as **readiness / signal detection**, not full proof that an element is environmentally traceable or circular.
- **L4b** does **not** constitute a full reversibility or circularity assessment.
- **Service life** is assessed under **L3** only. It is intentionally excluded from **L4b** scoring and L4b check columns.
- **IfcRelFillsElement** is treated as an opening/fill host relationship and is intentionally excluded from **L4b** direct connection evidence.

---

## Implemented Categories

| BEC Code | Name                                      | File                | Notes                                                                                                                                                                                                      |
| -------- | ----------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1.1      | Foundations and piling                    | `c11.py`            | Main scope includes `IfcFooting`, `IfcPile`.                                                                                                                                                               |
| 1.2      | Basement retaining walls / lowest slab    | `c22.py` / `c12.py` | Active deterministic `BASESLAB` rows are exported through `c22.py`. Standalone `c12.py` retaining-wall/basement-scope export is intentionally deferred until later semi-deterministic logic is defensible. |
| 2.1      | Frame                                     | `c21.py`            | Main structural scope: columns, beams, structural walls. Also acts as the active wall-routing source for top-level 2.7 internal-wall reporting.                                                            |
| 2.2      | Upper floors                              | `c22.py`            | Implemented together with 2.3. Slabs with `PredefinedType == FLOOR` are routed here.                                                                                                                       |
| 2.3      | Roof structure                            | `c22.py`            | Implemented together with 2.2. Slabs with `PredefinedType == ROOF` and direct `IfcRoof` elements are routed here.                                                                                          |
| 2.4      | Stairs, ramps, guarding                   | `c24.py`            | Includes `IfcStair`, `IfcRamp`, `IfcRailing`.                                                                                                                                                              |
| 2.5      | External envelope incl. roof finishes     | `c25.py`            | External walls, curtain walls, roof-related coverings, and envelope-related routing. Some inclusion logic depends on externality heuristics / pset cues.                                                   |
| 2.6      | Windows and external doors                | `c26.py`            | `IfcWindow` and externally classified/routed `IfcDoor`.                                                                                                                                                    |
| 2.7      | Internal walls                            | `c21.py`            | Active top-level reporting is produced through 2.1 wall routing. `c27.py` remains exploratory/future logic and is not the active source of truth.                                                          |
| 2.8      | Internal doors                            | `c28.py`            | `IfcDoor` classified/routed as internal.                                                                                                                                                                   |
| 3.1      | Wall finishes                             | `c31.py`            | Mainly `IfcCovering` and related finish logic.                                                                                                                                                             |
| 3.2      | Floor finishes                            | `c32.py`            | Mainly `IfcCovering` and related finish logic.                                                                                                                                                             |
| 3.3      | Ceiling finishes                          | `c33.py`            | Mainly `IfcCovering` and related finish logic.                                                                                                                                                             |
| 4.1–4.6  | Furniture, fittings, and equipment (FF&E) | `c41.py`–`c46.py`   | Primarily based on `IfcFurniture`, `IfcSystemFurnitureElement`, and related object routing.                                                                                                                |
| 5.1.1    | Sanitary / water / drainage               | `c511.py`           | MEP-focused scope covering sanitary-related entities and associated service logic.                                                                                                                         |
| 5.2–5.5  | Building services (MEP)                   | various `c5*.py`    | Heating, cooling, ventilation, electrical, renewables, life safety, and related service-system categorization. Coverage varies by subcategory and often depends on IFC system assignment quality.          |

---

## Out-of-Scope Categories

### 5.2.3 Air movement

**Status**: Out of scope as a standalone category.  
**Reason**: Air-movement-related equipment is currently assessed within the broader ventilation scope (5.2.4), using entities such as `IfcAirTerminal`, `IfcDuctSegment`, and related distribution/service objects.

### 6 Pre-fabricated buildings and building units

**Status**: Out of scope.  
**Reason**: Prefabricated units are not reliably identifiable as a distinct assessment category in typical IFC exchanges. In practice, they are usually represented through standard constituent elements (`IfcWall`, `IfcSlab`, etc.), sometimes grouped through `IfcElementAssembly`, but not in a way that consistently supports deterministic category-level readiness assessment as a separate prefab unit.

### 7 Works to existing buildings

- 7.1 Alterations
- 7.2 Repairs, cleaning, general renovation
- 7.3 Damp-proof courses / fungus and beetle eradication

**Status**: Out of scope.  
**Reason**: These categories describe intervention processes or project activities rather than stable element classes that can usually be assessed from IFC object semantics alone. They may be partially documented through phasing, documents, or external project records, but are not generally represented as deterministic element-level quality-assessment targets in exchanged IFC models.

### 8 External works

- 8.1 Roads, paths, pavings, surfaces / fencing, railings, walls / external fixtures
- 8.2 Soft landscape, planting, irrigation
- 8.3 External drainage / external services / minor building works

**Status**: Out of scope.  
**Reason**: These elements are inconsistently modeled in building-focused IFC exchanges and often lack sufficient semantic and quantity detail for robust category-level readiness assessment. Some related IFC classes exist, including `IfcGeographicElement` in IFC4 and expanded infrastructure-oriented entities in IFC4.3, but these are not yet treated as stable scope within the current implementation.

---

## TODO / Partial Categories

### 5.5 active export note

**Status**: Active export currently runs through `c55.py`.  
**Implementation note**: In the active pipeline, `category_55()` currently exports `5.5.2` as fuel installations and `5.5.3` as lifts and conveyor installations.  
**Transport logic**: Lift and conveyor installations are handled deterministically with `IfcTransportElement.PredefinedType` values such as `ELEVATOR`, `ESCALATOR`, `MOVINGWALKWAY`, `CRANEWAY`, and `LIFTINGGEAR`. The former redundant `c552.py` alternate path has been removed.  
**IFC feasibility**: Transport-equipment coverage remains limited and model-dependent, especially when lifts or conveying equipment are exported as generic proxies rather than typed transport entities.

### 1.2 Basement retaining walls (pipeline integration pending)

**Status**: Partial.  
**Reason**: `c12.py` now includes helper checks and a category function, but standalone retaining-wall/basement-scope export is intentionally deferred. The current `category_12()` implementation does not yet collect the relevant element scope for reporting, and the broader basement/retaining-wall use case still depends on semi-deterministic logic that is not ready to stand alone methodologically.  
**Current active subset**: Deterministic lowest-slab handling is exported through routing from `c22.py` when `IfcSlab.PredefinedType == BASESLAB`. The exported category keeps the RICS name "Basement retaining walls and lowest slab" and includes a category-level info issue clarifying that retaining-wall detection is not currently assessed.  
**Planned future state**: BEC 1.2 should become standalone only once the semi-deterministic retaining-wall and basement-scope logic is sufficiently robust and defensible.

### 2.7 Internal walls

**Status**: Top-level BEC `2.7` is active through `category_21()` wall routing.  
**Current active scope**: Non-loadbearing/internal wall cases discovered while processing walls in `c21.py` are exported as `2.7` rows, with a distinct Overview row and Indicator row.  
**Subcategory note**: `2.7.1` / `2.7.2` splitting is not active in the publication-facing report because solid-vs-glazed partition interpretation is reserved for later methodology work. Current routing avoids semantic text-token interpretation and uses deterministic IFC signals such as `LoadBearing`, `IsExternal`, and partition-style `PredefinedType`.  
**Alternate logic**: `c27.py` exists as exploratory/future logic and should not be treated as the release-facing source of truth unless a later implementation pass explicitly promotes or merges it.

---

## Scope Caveats for Future Development

- Category coverage is **not uniformly mature** across all BECs.
- Some categories depend heavily on:
  - `PredefinedType`
  - external/internal classification logic
  - system/group assignments
  - host/covering relationships
  - partially heuristic routing
- MEP categorization is especially sensitive to weak IFC exports, missing `IfcDistributionSystem` assignments, and generic object naming.
- L4a and L4b evidence should be interpreted as **readiness cues**, not as proof of robust environmental or circularity assessment capability.
