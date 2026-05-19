from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
# 2.7 Internal walls this is looked at 2.1 because it also parses walls, just autoexcludes based on isLoadBearing/isExternal.
def category_27(ad: CoreType):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview=IndicatorRow()

    walls = ad.by_types(["IfcWall", "IfcWallStandardCase"]) 

     # Aggregation for output rows
    agg: dict[tuple, CategoryRow] = {}

    # --- scoring counters (deterministic coverage) ---
    n = 0  # number of elements in this category scope (internal + uncertain internal)
    n_pdt_ok = 0
    n_class_ok = 0
    n_class_fields_ok = 0

    n_shape_ok = 0
    n_qto_ok = 0

    n_common_pset_ok = 0
    n_mat_ok = 0
    n_doc_ok = 0
    sum_l4a=0
    relevant_qto_types = {"IfcQuantityArea", "IfcQuantityVolume", "IfcQuantityLength"}
    
    for w in walls:
        if (w.id() in ad.parsedElIds):
            continue

        ifc_class = w.is_a()
        pdt = getattr(w, "PredefinedType", None)

        common = ad.get_element_common_pset(w)
        is_external = None
        if common:
            is_external = common.get("IsExternal", None)

        internal_decision = None
        if isinstance(is_external, bool):
            internal_decision = (is_external is False)
        else:
            if pdt in {"PARTITIONING", "MOVABLE"}:
                internal_decision = True
            elif pdt == "NOTDEFINED" or pdt is None:
                internal_decision = None
            else:
                internal_decision = None

        # Exclude clearly external
        if internal_decision is False:
            continue

        # Issues
        if is_external is None:
            issue = IssueRow()
            issue.category_code = "2.7"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing Pset_*Common.IsExternal; internal/external classification is uncertain"
            out.issues.append(issue)

        if isinstance(is_external, bool) and is_external is True and pdt in {"PARTITIONING", "MOVABLE"}:
            issue = IssueRow()
            issue.category_code = "2.7"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Conflicting semantics: IsExternal=True but PredefinedType suggests partition/movable"
            out.issues.append(issue)

        # --- scoring: include all remaining walls in this category scope ---
        n += 1
        sum_l4a += ad.parse_element_EII(w)["score"]
        # L1 components
        if ad._valid_predefined_type(w):
            n_pdt_ok += 1

        has_class = ad._has_classification_ref(w)
        if has_class:
            n_class_ok += 1
        if ad._classification_required_fields_non_null(w):
            n_class_fields_ok += 1

        # L2 components
        if ad._has_shape_representation(w):
            n_shape_ok += 1
        if ad._has_relevant_qto(w, relevant_qto_types):
            n_qto_ok += 1

        # L3 components
        # deterministic: "common pset present" just means your accessor returned something
        if common is not None:
            n_common_pset_ok += 1
        if ad._has_material_association(w):
            n_mat_ok += 1
        if ad._has_document_association(w):
            n_doc_ok += 1

        row = CategoryRow()
        row.category_code = "2.7"
        row.category_name = ""
        row = ad.build_category_row(w, row)

        key = (
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

    # --- compute weighted scores safely ---
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

    out.overview.l2_score = (
        0.3 * s_shape +
        0.7 * s_qto
    )

    out.overview.l3_score = (
        0.3 * s_common +
        0.3 * s_mat +
        0.4 * s_doc
    )

    # conceptual only for now
    out.overview.l4a_score = (sum_l4a / n) if n else 0.0
    out.overview.l4b_score = 0.0

    # "issues": deterministic choice (no parsing issue.message)
    out.overview.issues = len(out.issues)

    return out