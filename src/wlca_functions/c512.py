
from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
    # 5.1.2  Cold water systems
    # 5.1.2.1  Cold water systems
    # 5.1.2.2  Cold water storage
# I think it was possible semantically to distinguish cold water system by some ifc higher tier group? like there was enum for cold systems no?
def category_512(ad: CoreType, idx: PreIndex):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "5.1.2"

    # --- deterministic: only IFC4+ explicit system type ---
    cold_systems = [s for s in ad.by_types(["IfcDistributionSystem"])
                    if getattr(s, "PredefinedType", None) == "DOMESTICCOLDWATER"]

    if not cold_systems:
        out.issues.append(IssueRow(
            category_code="5.1.2", category_name="", ifc_class="IfcDistributionSystem",
            message="No cold water system found (expected IfcDistributionSystem.PredefinedType=DOMESTICCOLDWATER)"
        ))
        finalize_category_metrics(ad, out, {"5.1.2": []})
        return out

    sys_ids = {s.id() for s in cold_systems}

    members = []
    for rel in ad.by_types(["IfcRelAssignsToGroup"]):
        grp = getattr(rel, "RelatingGroup", None)
        if grp and grp.id() in sys_ids:
            members.extend([x for x in (getattr(rel, "RelatedObjects", [])) if x])

    if not members:
        out.issues.append(IssueRow(
            category_code="5.1.2", category_name="", ifc_class="IfcRelAssignsToGroup",
            message="Cold water system exists but has no members assigned via IfcRelAssignsToGroup"
        ))
        finalize_category_metrics(ad, out, {"5.1.2": []})
        return out

    agg: dict[tuple, CategoryRow] = {}

    n = 0
    n_pdt_ok = n_class_ok = n_class_fields_ok = 0
    n_shape_ok = n_qto_ok = 0
    n_common_ok = n_mat_ok = n_doc_ok = 0
    sum_l4a = 0.0

    relevant_qto_types = {"IfcQuantityLength", "IfcQuantityArea", "IfcQuantityVolume", "IfcQuantityCount"}
    scoped_elements = []

    for el in members:
        if el.id() in ad.parsedElIds:
            continue
        scoped_elements.append(el)

        ifc_class = el.is_a()
        pdt = getattr(el, "PredefinedType", None)

        # --- classify storage vs distribution (deterministic) ---
        is_storage = False
        if ifc_class == "IfcTank":
            is_storage = True  # keep simple + deterministic
        elif ifc_class == "IfcFlowStorageDevice":
            is_storage = True

        code = "5.1.2.2" if is_storage else "5.1.2.1"

        # --- issues ---
        if hasattr(el, "PredefinedType") and ((pdt is None) or (pdt == "NOTDEFINED")):
            out.issues.append(IssueRow(
                category_code=code, category_name="", ifc_class=ifc_class, message="Missing predefined type"
            ))

        # --- indicators ---
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

        # --- build + aggregate ---
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
        {"5.1.2": scoped_elements},
        qto_by_category={"5.1.2": relevant_qto_types},
    )

    return out
