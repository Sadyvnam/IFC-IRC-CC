from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
from ifcopenshell import entity_instance
# 2.5  External envelope including roof finishes
# 2.5 External envelope (2.5.2 glazing systems, 2.5.3 roof finishes/coverings, 2.5.4 safety systems)
def category_25(ad: CoreType):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "2.5"

    # elements we might route into 2.5.* (opaque walls handled in 2.1)
    relevant = ad.by_types(["IfcCurtainWall", "IfcMember", "IfcPlate", "IfcCovering", "IfcChimney"])

    agg: dict[tuple, CategoryRow] = {}

    # --- scoring counters over all elements accepted into 2.5 ---
    n = 0
    n_pdt_ok = 0
    n_class_ok = 0
    n_class_fields_ok = 0

    n_shape_ok = 0
    n_qto_ok = 0

    n_common_pset_ok = 0
    n_mat_ok = 0
    n_doc_ok = 0
    sum_l4a=0.0
    # generic geometry/quantity types for envelope elements
    relevant_qto_types = {"IfcQuantityArea", "IfcQuantityVolume", "IfcQuantityLength"}
    scoped_by_category = {"2.5": []}

    for e in relevant:
        if e.id() in ad.parsedElIds:
            continue

        ifc_class = e.is_a()
        subcat = None

        # --- routing into 2.5 subcategories (deterministic) ---
        if ifc_class == "IfcCurtainWall":
            subcat = "2.5.2"  # full height glazing systems
        elif ifc_class in {"IfcPlate", "IfcMember"}:
            # only if deterministically connected to a curtain wall
            if _belongs_to_curtain_wall(e, ad):
                subcat = "2.5.2"
            elif ifc_class == "IfcMember" and ad.is_facade_member_candidate(e):
                issue = IssueRow()
                issue.ifc_guid = getattr(e, "GlobalId", "") or ""
                issue.element_id = str(e.id())
                issue.element_type = getattr(e, "ObjectType", "") or ""
                issue.ifc_class = ifc_class
                issue.scope = "element"
                issue.category_code = "2.5"
                issue.category_name = ""
                issue.severity = "warning"
                issue.message = "Facade-framing member lacks deterministic curtain-wall host or system evidence"
                issue.whatShouldBeDifferent = (
                    "Provide explicit curtain-wall or facade-system parent, nesting, group, type, "
                    "classification, or document linkage for this member."
                )
                issue.details = "; ".join(ad.curtain_wall_gap_reasons(e))
                out.issues.append(issue)
                continue
            else:
                continue  # plates/members not part of glazing system -> not 2.5
        elif ifc_class == "IfcCovering":
            if _is_roof_covering(e):
                subcat = "2.5.3"  # roof finishes/coverings
            else:
                continue
        elif ifc_class == "IfcChimney":
            subcat = "2.5.4" 
        else:
            continue

        scoped_by_category.setdefault("2.5", []).append(e)

        # --- predefined type issue (deterministic enum presence) ---
        pdt = getattr(e, "PredefinedType", None)
        if pdt == "NOTDEFINED":
            issue = IssueRow()
            issue.category_code = subcat  # precise subcategory
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing predefined type"
            out.issues.append(issue)

        # --- scoring for overview (element included in 2.5 scope) ---
        n += 1
        sum_l4a += ad.parse_element_EII(e)["score"]
        try:
            if ad._valid_predefined_type(e):
                n_pdt_ok += 1
            if ad._has_classification_ref(e):
                n_class_ok += 1
            if ad._classification_required_fields_non_null(e):
                n_class_fields_ok += 1
        except:
            print(e)
        if ad._has_shape_representation(e):
            n_shape_ok += 1
        if ad._has_relevant_qto(e, relevant_qto_types):
            n_qto_ok += 1

        common = ad.get_element_common_pset(e)
        if common is not None:
            n_common_pset_ok += 1
        if ad._has_material_association(e):
            n_mat_ok += 1
        if ad._has_document_association(e):
            n_doc_ok += 1

        # --- build and aggregate category rows (keep subcategory code) ---
        row = CategoryRow()
        row.category_code = subcat
        row.category_name = ""  # optional
        row = ad.build_category_row(e, row)

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

    # --- compute weighted overview scores for 2.5 (union of accepted elements) ---
    presence = 1.0 if n > 0 else 0.0
    if n > 0:
        s_pdt = n_pdt_ok / n
        s_class = n_class_ok / n
        s_class_fields = n_class_fields_ok / n

        s_shape = n_shape_ok / n
        s_qto = n_qto_ok / n

        s_common = n_common_pset_ok / n
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
        scoped_by_category,
        qto_by_category={"2.5": relevant_qto_types},
    )

    return out


def _belongs_to_curtain_wall(e:entity_instance, ad: CoreType | None = None, max_depth: int = 6) -> bool:
    if ad is not None:
        return ad.belongs_to_curtain_wall_explicitly(e, max_depth=max_depth)

    if not e or not hasattr(e, "is_a"):
        return False
    if e.is_a("IfcCurtainWall"):
        return True

    current = e
    depth = 0
    visited = set()
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
            parent:entity_instance|None = getattr(rel, "RelatingObject", None)
            if not parent:
                continue
            if parent.is_a("IfcCurtainWall"):
                return True
            current = parent
            stepped = True
            break
        if not stepped:
            break

    current = e
    depth = 0
    visited = set()
    while current and depth < max_depth:
        depth += 1
        try:
            cid = current.id()
            if cid in visited:
                break
            visited.add(cid)
        except Exception:
            pass

        rels = getattr(current, "Nests", [])
        stepped = False
        for rel in rels:
            parent = getattr(rel, "RelatingObject", None)
            if not parent:
                continue
            if parent.is_a("IfcCurtainWall"):
                return True
            current = parent
            stepped = True
            break
        if not stepped:
            break

    for rel in getattr(e, "HasAssignments", []):
        if not rel or not rel.is_a("IfcRelAssignsToGroup"):
            continue
        grp = getattr(rel, "RelatingGroup", None)
        if grp and grp.is_a("IfcCurtainWall"):
            return True

    return False

def _is_roof_covering(covering:entity_instance) -> bool:
    if not covering.is_a("IfcCovering"):
        return False

    pdt = getattr(covering, "PredefinedType", None)
    if pdt == "ROOFING":
        return True

    return False
