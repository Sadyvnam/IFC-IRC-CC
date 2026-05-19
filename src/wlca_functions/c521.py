
from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from typing import Dict, List
import ifcopenshell
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
    # 5.2.1 Space heating and hot water
    # 5.2.1.1 Heat & Hot water generation equipment
    # 5.2.1.2 Heat & hot water distribution, control, ancillaries, emitters, exchangers/  terminal units
    # 5.2.1.3 Heat storage equipment
# 5.2.1 Space heating and hot water
# 5.2.1.1 generation, 5.2.1.2 distribution/control/emitters, 5.2.1.3 storage
def category_521(ad: CoreType, idx: PreIndex):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "5.2.1"

    # --- 1) systems (preferred) ---
    systems = []
    for sys in ad.by_types(["IfcDistributionSystem"]):
        if getattr(sys, "PredefinedType", None) in {"HEATING", "DOMESTICHOTWATER"}:
            systems.append(sys)

    if not systems:
        out.issues.append(IssueRow(
            category_code="5.2.1", category_name="", ifc_class="IfcDistributionSystem",
            message="No heating/DHW system found (expected IfcDistributionSystem.PredefinedType=HEATING or DOMESTICHOTWATER)"
        ))
        finalize_category_metrics(ad, out, {"5.2.1": []})
        return out

    # --- 2) members via group assigns ---
    sys_members = []
    if systems:
        sys_set = set(systems)
        for rel in ad.by_types(["IfcRelAssignsToGroup"]):
            grp = getattr(rel, "RelatingGroup", None)
            if grp in sys_set:
                sys_members += list(getattr(rel, "RelatedObjects", []))

    # --- 3) no class-only fallback  ---
    used_fallback = False
    if not sys_members:
        out.issues.append(IssueRow(
            category_code="5.2.1", category_name="", ifc_class="IfcRelAssignsToGroup",
            message="Heating/DHW system exists but has no members assigned via IfcRelAssignsToGroup"
        ))
        finalize_category_metrics(ad, out, {"5.2.1": []})
        return out

    elements = sys_members

    # --- 4) classify into subcodes ---
    def classify(el) -> str:
        cls = el.is_a()
        if cls in {"IfcTank", "IfcFlowStorageDevice"}:
            return "5.2.1.3"
        if cls in {"IfcBoiler", "IfcHeatPump", "IfcFurnace", "IfcBurner", "IfcEnergyConversionDevice"}:
            return "5.2.1.1"
        if cls in {"IfcSpaceHeater", "IfcHeatExchanger", "IfcCoil", "IfcUnitaryEquipment"}:
            return "5.2.1.2"
        if cls in {
            "IfcPipeSegment", "IfcPipeFitting", "IfcFlowFitting",
            "IfcPump", "IfcValve", "IfcFlowController",
            "IfcController", "IfcSensor", "IfcActuator",
        }:
            return "5.2.1.2"
        return "5.2.1.2"

    # --- 5) aggregate + indicators (combined across 5.2.1.*) ---
    agg: dict[tuple, CategoryRow] = {}

    n = 0
    n_pdt_ok = n_class_ok = n_class_fields_ok = 0
    n_shape_ok = n_qto_ok = 0
    n_common_ok = n_mat_ok = n_doc_ok = 0
    sum_l4a = 0.0

    relevant_qto_types = {"IfcQuantityLength", "IfcQuantityArea", "IfcQuantityVolume", "IfcQuantityCount"}
    scoped_elements = []

    for el in elements:
        if not el or el.id() in ad.parsedElIds:
            continue
        scoped_elements.append(el)

        code = classify(el)
        ifc_class = el.is_a()
        pdt = getattr(el, "PredefinedType", None)

        if used_fallback:
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
        {"5.2.1": scoped_elements},
        qto_by_category={"5.2.1": relevant_qto_types},
    )

    return out
