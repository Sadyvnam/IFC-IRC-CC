  
from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from typing import Dict, List
import ifcopenshell
from ifcopenshell import entity_instance
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 5.1.3  Drainage and rainwater
    # 5.1.3.1 Surface water/ rainwater/ foul water drainage
    # 5.1.3.2 Water reuse systems
# 5.1.3 Drainage and rainwater
# 5.1.3.1 Surface/rain/foul drainage
# 5.1.3.2 Water reuse systems
def category_513(ad: CoreType, idx: PreIndex):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "5.1.3"

    # deterministic only. In the current active
    # pipeline, only explicit IfcWasteTerminal elements are exported for 5.1.3.1.
    drainage_systems:set[entity_instance]= set()
    reuse_systems:set[entity_instance]= set()

    # doesnt function because no schematic predef type for group for waste/sanitary systems
    members_5131, members_5132 = [], []
    for rel in ad.by_types(["IfcRelAssignsToGroup"]):
        grp = getattr(rel, "RelatingGroup", None)
        if grp in drainage_systems:
            members_5131 += list(getattr(rel, "RelatedObjects", []))
        if grp in reuse_systems:
            members_5132 += list(getattr(rel, "RelatedObjects", []))

    used_fallback_5131 = False
    used_fallback_5132 = False

    if not members_5131:
        members_5131.extend(ad.by_types(["IfcWasteTerminal"]))

    # --- 4) aggregate + indicators (over BOTH subcategories combined) ---
    agg: dict[tuple, CategoryRow] = {}

    n = 0
    n_pdt_ok = n_class_ok = n_class_fields_ok = 0
    n_shape_ok = n_qto_ok = 0
    n_common_ok = n_mat_ok = n_doc_ok = 0
    sum_l4a = 0.0

    relevant_qto_types = {"IfcQuantityLength", "IfcQuantityArea", "IfcQuantityVolume", "IfcQuantityCount"}
    scoped_elements = []

    def add(code: str, elements: list, fallback_batch: bool):
        nonlocal n, n_pdt_ok, n_class_ok, n_class_fields_ok
        nonlocal n_shape_ok, n_qto_ok, n_common_ok, n_mat_ok, n_doc_ok, sum_l4a

        for el in elements:
            if not el or el.id() in ad.parsedElIds:
                continue
            scoped_elements.append(el)

            ifc_class = el.is_a()
            pdt = getattr(el, "PredefinedType", None)

            if fallback_batch:
                out.issues.append(IssueRow(
                    category_code=code, category_name="", ifc_class=ifc_class,
                    message="Element included via fallback logic; classification may be uncertain (missing/unused system grouping)"
                ))

            if hasattr(el, "PredefinedType") and ((pdt is None) or (pdt == "NOTDEFINED")):
                out.issues.append(IssueRow(
                    category_code=code, category_name="", ifc_class=ifc_class,
                    message="Missing predefined type"
                ))

            # indicators
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

            sum_l4a += ad.parse_element_EII(el)["score"]

            # category rows
            row = CategoryRow()
            row.category_code = code
            row.category_name = ""
            row = ad.build_category_row(el, row)

            key = (row.category_code, row.ifc_class, row.object_type or pdt or "", row.material_name or "")
            if key not in agg:
                agg[key] = row
            else:
                a = agg[key]
                a.count += 1
                a.volume_m3 += (row.volume_m3 or 0.0)
                a.area_m2 += (row.area_m2 or 0.0)
                a.count_cantCalcRI += row.count_cantCalcRI

    add("5.1.3.1", members_5131, fallback_batch=used_fallback_5131)
    add("5.1.3.2", members_5132, fallback_batch=used_fallback_5132)

    out.categories = list(agg.values())

    presence = 1.0 if n > 0 else 0.0
    if n:
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
        {"5.1.3": scoped_elements},
        qto_by_category={"5.1.3": relevant_qto_types},
    )

    return out
