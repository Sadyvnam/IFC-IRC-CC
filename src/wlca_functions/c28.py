from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 2.8 Internal doors
def category_28(ad: CoreType) -> CategoryReturn:
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "2.8"

    doors = ad.by_types(["IfcDoor"])
    agg: dict[tuple, CategoryRow] = {}

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

    relevant_qto_types = {"IfcQuantityArea", "IfcQuantityVolume", "IfcQuantityLength", "IfcQuantityCount"}
    scoped_elements = []

    for d in doors:
        if d.id() in ad.parsedElIds:
            continue

        common = ad.get_element_common_pset(d)
        is_external = common.get("IsExternal") if common else None
        if isinstance(is_external, dict):
            is_external = is_external.get("value")

        # strict internal only
        if is_external is not False:
            continue
        scoped_elements.append(d)

        ifc_class = d.is_a()
        pdt = getattr(d, "PredefinedType", None)

        if (pdt is None) or (pdt == "NOTDEFINED"):
            issue = IssueRow()
            issue.category_code = "2.8"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing predefined type"
            out.issues.append(issue)

        # scoring L1-L3 + L4A
        n += 1
        if ad._valid_predefined_type(d): n_pdt_ok += 1
        if ad._has_classification_ref(d): n_class_ok += 1
        if ad._classification_required_fields_non_null(d): n_class_fields_ok += 1
        if ad._has_shape_representation(d): n_shape_ok += 1
        if ad._has_relevant_qto(d, relevant_qto_types): n_qto_ok += 1

        if common is not None: n_common_ok += 1
        if ad._has_material_association(d): n_mat_ok += 1
        if ad._has_document_association(d): n_doc_ok += 1

        sum_l4a += ad.parse_element_EII(d)["score"]

        # build + aggregate
        row = CategoryRow()
        row.category_code = "2.8"
        row.category_name = ""
        row = ad.build_category_row(d, row)

        key = ("2.8", row.ifc_class, row.object_type or pdt or "", row.material_name or "")
        if key not in agg:
            agg[key] = row
        else:
            a = agg[key]
            a.count += 1
            a.volume_m3 += (row.volume_m3 or 0.0)
            a.area_m2 += (row.area_m2 or 0.0)
            a.count_cantCalcRI += row.count_cantCalcRI

    out.categories = list(agg.values())

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

    out.overview.l1_score = 0.2 * presence + 0.2 * s_pdt + 0.4 * s_class + 0.2 * s_class_fields
    out.overview.l2_score = 0.3 * s_shape + 0.7 * s_qto
    out.overview.l3_score = 0.3 * s_common + 0.3 * s_mat + 0.4 * s_doc
    out.overview.l4a_score = (sum_l4a / n) if n else 0.0
    out.overview.l4b_score = 0.0
    out.overview.issues = len(out.issues)
    finalize_category_metrics(
        ad,
        out,
        {"2.8": scoped_elements},
        qto_by_category={"2.8": relevant_qto_types},
    )

    return out