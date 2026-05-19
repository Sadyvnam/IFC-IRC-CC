from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
from ifcopenshell import entity_instance
# 2.2 Upper Floors and roof (2.3)
def _finalize_indicator(row: IndicatorRow, n: float,
                        n_pdt_ok: float, n_class_ok: float, n_class_fields_ok: float,
                        n_shape_ok: float, n_qto_ok: float,
                        n_common_ok: float, n_mat_ok: float, n_doc_ok: float,
                        n_issues: int, l4a_sum: float = 0.0):
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

    row.l1_score = 0.2 * presence + 0.2 * s_pdt + 0.4 * s_class + 0.2 * s_class_fields
    row.l2_score = 0.3 * s_shape + 0.7 * s_qto
    row.l3_score = 0.3 * s_common + 0.3 * s_mat + 0.4 * s_doc
    row.l4a_score = (l4a_sum / n) if n else 0.0
    row.l4b_score = 0.0
    row.issues = n_issues


# 2.2 Upper floors and 2.3 Roof
def category_22(ad: CoreType) -> CategoryReturn:
    out = CategoryReturn()
    out.issues = []
    out.categories = []

    # Recommended: store multiple overview rows
    out.overviews = []  # add this field to CategoryReturn if possible

    slabs = ad.by_types(["IfcSlab"])

    agg: dict[tuple, CategoryRow] = {}

    counters = {
        "1.2": {
            "n": 0, "pdt": 0, "class": 0, "class_fields": 0,
            "shape": 0, "qto": 0, "common": 0, "mat": 0, "doc": 0,
            "issues": 0, "l4a": 0.0,
        },
        "2.2": {
            "n": 0, "pdt": 0, "class": 0, "class_fields": 0,
            "shape": 0, "qto": 0, "common": 0, "mat": 0, "doc": 0,
            "issues": 0, "l4a": 0.0,
        },
        "2.3": {
            "n": 0, "pdt": 0, "class": 0, "class_fields": 0,
            "shape": 0, "qto": 0, "common": 0, "mat": 0, "doc": 0,
            "issues": 0, "l4a": 0.0,
        },
    }
    # quantities relevant for slabs: area + volume are typical
    relevant_qto_types = {"IfcQuantityArea", "IfcQuantityVolume", "IfcQuantityLength"}
    scoped_by_category:dict[str, list[entity_instance]] = {"1.2": [], "2.2": [], "2.3": []}

    for slab in slabs:
        if slab.id() in ad.parsedElIds:
            continue

        pdt = getattr(slab, "PredefinedType", None)

        # --- determine code deterministically ---
        if pdt == "ROOF":
            code = "2.3"
        elif pdt in {"FLOOR"}:
            code = "2.2"
        elif pdt in {"BASESLAB"}:
            code = "1.2"
        elif pdt in {"LANDING"}:
            code = "2.4"
        else:
            # conservative: treat unknown slab types as 2.2 but flag
            code = "2.2"
            issue = IssueRow()
            issue.category_code = "2.2"
            issue.category_name = ""
            issue.ifc_class = slab.is_a()
            issue.message = f"Unexpected IfcSlab.PredefinedType={pdt}; treated as 2.2"
            out.issues.append(issue)
            counters["2.2"]["issues"] += 1

        # --- QA: missing predefined type ---
        if (pdt is None) or (pdt == "NOTDEFINED"):
            issue = IssueRow()
            issue.category_code = code
            issue.category_name = ""
            issue.ifc_class = slab.is_a()
            issue.message = "Missing predefined type (IfcSlab.PredefinedType)"
            out.issues.append(issue)
            counters.get(code, counters["2.2"])["issues"] += 1

        # --- scoring counters per code ---
        common = ad.get_element_common_pset(slab)

        score_bucket = counters.get(code)
        if score_bucket is not None:
            scoped_by_category.setdefault(code, []).append(slab)
            score_bucket["n"] += 1
            score_bucket["l4a"] += ad.parse_element_EII(slab)["score"]
            if ad._valid_predefined_type(slab): score_bucket["pdt"] += 1
            if ad._has_classification_ref(slab): score_bucket["class"] += 1
            if ad._classification_required_fields_non_null(slab): score_bucket["class_fields"] += 1
            if ad._has_shape_representation(slab): score_bucket["shape"] += 1
            if ad._has_relevant_qto(slab, relevant_qto_types): score_bucket["qto"] += 1
            if common is not None: score_bucket["common"] += 1
            if ad._has_material_association(slab): score_bucket["mat"] += 1
            if ad._has_document_association(slab): score_bucket["doc"] += 1

        # --- build + aggregate category rows ---
        row = CategoryRow()
        row.category_code = code
        row.category_name = ""
        row = ad.build_category_row(slab, row)

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

    if counters["1.2"]["n"] > 0:
        issue = IssueRow()
        issue.category_code = "1.2"
        issue.category_name = "Basement retaining walls and lowest slab"
        issue.scope = "category"
        issue.severity = "info"
        issue.message = (
            "Active BEC 1.2 export currently includes deterministic BASESLAB routing only; "
            "basement retaining-wall detection is not assessed because no deterministic IFC signal has been adopted."
        )
        out.issues.append(issue)

    # --- finalize overviews ---
    out.overviews = []
    for code in ("1.2", "2.2", "2.3"):
        c = counters[code]
        ov = IndicatorRow()
        ov.category = code
        _finalize_indicator(
            ov, c["n"],
            c["pdt"], c["class"], c["class_fields"],
            c["shape"], c["qto"],
            c["common"], c["mat"], c["doc"],
            int(c["issues"]), c["l4a"],
        )
        out.overviews.append(ov)
    finalize_category_metrics(
        ad,
        out,
        scoped_by_category,
        qto_by_category={code: relevant_qto_types for code in scoped_by_category},
    )
    return out