from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
from ifcopenshell import entity_instance
 # 2.4 Stairs, ramps and safety guarding
 # 2.4 Stairs, ramps and safety guarding
def category_24(ad: CoreType) -> CategoryReturn:
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "2.4"

    # Core scope
    elems = []
    elems.extend(ad.by_types(["IfcStair", "IfcRamp", "IfcRailing"]))

    # Members only if they deterministically belong to stair/ramp/railing (guards/handrails often modeled this way)
    for m in ad.by_types(["IfcMember"]):
        if _belongs_to_24_system(m):
            elems.append(m)
    scoped_elements = []

    agg: dict[tuple, CategoryRow] = {}

    # --- scoring counters ---
    n = 0
    n_pdt_ok = 0
    n_class_ok = 0
    n_class_fields_ok = 0

    n_shape_ok = 0
    n_qto_ok = 0

    n_common_ok = 0
    n_mat_ok = 0
    n_doc_ok = 0
    sum_l4a = 0.0
    # relevant quantities: length is common (handrails), area/volume may exist for ramps/stairs
    relevant_qto_types = {"IfcQuantityLength", "IfcQuantityArea", "IfcQuantityVolume", "IfcQuantityCount"}

    for el in elems:
        if el.id() in ad.parsedElIds:
            continue
        scoped_elements.append(el)

        ifc_class = el.is_a()
        pdt = getattr(el, "PredefinedType", None)

        # QA: missing PredefinedType (deterministic)
        if (pdt is None) or (pdt == "NOTDEFINED"):
            issue = IssueRow()
            issue.category_code = "2.4"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing predefined type"
            out.issues.append(issue)

        # --- scoring ---
        n += 1
        sum_l4a += ad.parse_element_EII(el)["score"]
        if ad._valid_predefined_type(el):
            n_pdt_ok += 1
        if ad._has_classification_ref(el):
            n_class_ok += 1
        if ad._classification_required_fields_non_null(el):
            n_class_fields_ok += 1

        if ad._has_shape_representation(el):
            n_shape_ok += 1
        if ad._has_relevant_qto(el, relevant_qto_types):
            n_qto_ok += 1

        common = ad.get_element_common_pset(el)
        if common is not None:
            n_common_ok += 1

        if ad._has_material_association(el):
            n_mat_ok += 1
        if ad._has_document_association(el):
            n_doc_ok += 1

        # --- build + aggregate ---
        row = CategoryRow()
        row.category_code = "2.4"
        row.category_name = ""
        row = ad.build_category_row(el, row)

        key = (
            row.category_code,
            row.ifc_class,
            row.object_type or pdt or "",
            row.material_name or "",
        )

        if key not in agg:
            agg[key] = row
        else:
            a = agg[key]
            a.count += 1
            a.volume_m3 += (row.volume_m3 or 0.0)
            a.area_m2 += (row.area_m2 or 0.0)
            a.count_cantCalcRI += row.count_cantCalcRI

    out.categories = list(agg.values())

    # --- compute weighted overview scores ---
    presence = 1.0 if n > 0 else 0.0
    if n > 0:
        s_pdt = n_pdt_ok / n
        s_class = n_class_ok / n
        s_class_fields = n_class_fields_ok / n

        s_shape = n_shape_ok / n
        s_qto = n_qto_ok / n

        s_common = n_common_ok / n
        s_mat = n_mat_ok / n
        s_doc = n_doc_ok / n
    else:
        s_pdt = s_class = s_class_fields = 0.0
        s_shape = s_qto = 0.0
        s_common = s_mat = s_doc = 0.0

    out.overview.l1_score = (
        0.2 * presence +
        0.2 * s_pdt +
        0.4 * s_class +
        0.2 * s_class_fields
    )
    out.overview.l2_score = 0.3 * s_shape + 0.7 * s_qto
    out.overview.l3_score = 0.3 * s_common + 0.3 * s_mat + 0.4 * s_doc

    out.overview.l4a_score = (sum_l4a / n) if n else 0.0
    out.overview.l4b_score = 0.0
    out.overview.issues = len(out.issues)
    finalize_category_metrics(
        ad,
        out,
        {"2.4": scoped_elements},
        qto_by_category={"2.4": relevant_qto_types},
    )

    return out

def _belongs_to_24_system(e:entity_instance, max_depth: int = 6) -> bool:
    if e.is_a() in {"IfcStair", "IfcRamp", "IfcRailing"}:
        return True

    # Walk decomposition parents: Decomposes -> RelatingObject
    current = e
    depth = 0
    visited = set()
    rel:entity_instance
    while current and depth < max_depth:
        depth += 1
        try:
            cid = current.id()
            if cid in visited:
                break
            visited.add(cid)
        except Exception:
            pass

        rels = getattr(current, "Decomposes", [])
        stepped = False
        for rel in rels:
            parent:entity_instance | None = getattr(rel, "RelatingObject", None)
            if not parent:
                continue
            if parent.is_a() in {"IfcStair", "IfcRamp", "IfcRailing"}:
                return True
            current = parent
            stepped = True
            break
        if not stepped:
            break

    # Group assignment: IfcRelAssignsToGroup
    assigns = getattr(e, "HasAssignments", [])
    
    for rel in assigns:
        if not rel or not rel.is_a("IfcRelAssignsToGroup"):
            continue
        grp:entity_instance | None = getattr(rel, "RelatingGroup", None)
        if grp and grp.is_a() in {"IfcStair", "IfcRamp", "IfcRailing"}:
            return True

    return False
