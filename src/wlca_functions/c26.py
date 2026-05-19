from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 2.6 Windows and ext doors
def category_26(ad: CoreType):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "2.6"

    # Scope: windows + doors (we'll filter to external doors deterministically if possible)
    relevant = ad.by_types(["IfcWindow", "IfcDoor"])

    # Grouping dict (faster than nested loops)
    agg: dict[tuple, CategoryRow] = {}

    # --- scoring counters ---
    n = 0
    n_pdt_ok = 0
    n_class_ok = 0
    n_class_fields_ok = 0

    n_shape_ok = 0
    n_qto_ok = 0

    n_common_pset_ok = 0
    n_mat_ok = 0
    n_doc_ok = 0
    sum_l4a=0
    relevant_qto_types = {"IfcQuantityArea", "IfcQuantityLength", "IfcQuantityVolume"}
    scoped_elements = []

    for e in relevant:
        if e.id() in ad.parsedElIds:
            continue

        ifc_class = e.is_a()
        pdt = getattr(e, "PredefinedType", None)

        # --- deterministic external-door filtering ---
        # Windows: always in-scope
        # Doors: only external if Pset_DoorCommon.IsExternal is explicitly True
        common = ad.get_element_common_pset(e)  # should return dict or None
        is_external = None
        if common:
            is_external = common.get("IsExternal", None)

        if ifc_class == "IfcDoor":
            if is_external is True:
                pass  # keep
            elif is_external is False:
                continue  # internal door -> not part of 2.6
            else:
                # uncertain: keep (optional) and report issue
                issue = IssueRow()
                issue.category_code = "2.6"
                issue.category_name = ""
                issue.ifc_class = ifc_class
                issue.message = "Missing Pset_*Common.IsExternal for IfcDoor; external/internal classification is uncertain"
                out.issues.append(issue)

        scoped_elements.append(e)

        # --- report pdt issue ---
        if pdt == "NOTDEFINED":
            issue = IssueRow()
            issue.category_code = "2.6"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing predefined type"
            out.issues.append(issue)

        # --- scoring (element included) ---
        n += 1
        sum_l4a += ad.parse_element_EII(e)["score"]
        if ad._valid_predefined_type(e):
            n_pdt_ok += 1
        if ad._has_classification_ref(e):
            n_class_ok += 1
        if ad._classification_required_fields_non_null(e):
            n_class_fields_ok += 1

        if ad._has_shape_representation(e):
            n_shape_ok += 1
        if ad._has_relevant_qto(e, relevant_qto_types):
            n_qto_ok += 1

        # L3: common pset present (deterministic presence, no property checks)
        if common is not None:
            n_common_pset_ok += 1

        if ad._has_material_association(e):
            n_mat_ok += 1
        if ad._has_document_association(e):
            n_doc_ok += 1

        # --- build + aggregate CategoryRow output ---
        row = CategoryRow()
        row.category_code = "2.6"
        row.category_name = ""
        row = ad.build_category_row(e, row)

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

    # --- compute weighted overview scores ---
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
        {"2.6": scoped_elements},
        qto_by_category={"2.6": relevant_qto_types},
    )

    return out