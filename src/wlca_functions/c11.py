from src.classes import CoreType,PreIndex,IdxElements
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow, IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
 # 1.1 Foundations and piling
 # 1.1 Foundations and piling
def category_11(ad: CoreType, idx: PreIndex) -> CategoryReturn:
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "1.1"

    elems = []
    elems.extend(ad.by_types(["IfcPile"]))
    elems.extend(ad.by_types(["IfcFooting"]))
    scoped_elements = []

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
    relevant_qto_types = {"IfcQuantityVolume", "IfcQuantityArea", "IfcQuantityLength"}

    for el in elems:
        if el.id() in ad.parsedElIds:
            continue
        scoped_elements.append(el)

        ifc_class = el.is_a()
        pdt = getattr(el, "PredefinedType", None)

        if (pdt is None) or (pdt == "NOTDEFINED"):
            issue = IssueRow()
            issue.category_code = "1.1"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing predefined type"
            out.issues.append(issue)

        # scoring L1-L3
        n += 1
        if ad._valid_predefined_type(el): n_pdt_ok += 1
        if ad._has_classification_ref(el): n_class_ok += 1
        if ad._classification_required_fields_non_null(el): n_class_fields_ok += 1
        if ad._has_shape_representation(el): n_shape_ok += 1
        if ad._has_relevant_qto(el, relevant_qto_types): n_qto_ok += 1

        common = ad.get_element_common_pset(el)
        if common is not None: n_common_ok += 1
        if ad._has_material_association(el): n_mat_ok += 1
        if ad._has_document_association(el): n_doc_ok += 1

        # L4A (EI/EPD ladder)
        sum_l4a += ad.parse_element_EII(el)["score"]

        # build + aggregate
        row = CategoryRow()
        row.category_code = "1.1"
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
        {"1.1": scoped_elements},
        qto_by_category={"1.1": relevant_qto_types},
    )

    return out