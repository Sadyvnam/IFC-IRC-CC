from src.utils import PreIndex,CoreType
from src.excel.types import IssueRow,CategoryRow,CategoryReturn,IndicatorRow

# FEW PUBLIC IFCs TO VALIDATE

# 5.3.2 Electrical services for power, communications, security, IT and fire detection,
# 5.3.2.1 Electrical power
# 5.3.2.2 ELV/ Communications/ Security
# 5.3.2.3 IT & Data
# 5.3.2.4 BMS
# 5.3.2.5 Electricity back up generation
# 5.3.2.6  Fire detection & alarm
from collections import defaultdict
from ifcopenshell import entity_instance
from src.wlca_functions.check_metrics import finalize_category_metrics

# helper: safely get system/circuit groups assigned to an element
def _assigned_distribution_groups(el:entity_instance):
    groups = []
    for rel in getattr(el, "HasAssignments", []) or []:
        if rel.is_a("IfcRelAssignsToGroup"):
            g:entity_instance | None = getattr(rel, "RelatingGroup", None)
            if g and (g.is_a("IfcDistributionSystem") or g.is_a("IfcDistributionCircuit")):
                groups.append(g)
    return groups

def _system_type_of_group(g:entity_instance):
    # In IFC4x3, IfcDistributionSystem has PredefinedType, but it may be set at the type object
    # ("NOTE If object has associated IfcTypeObject with a PredefinedType, then this attribute shall not be used.")
    # prefer: type-object predefined, else occurrence predefined.
    try:
        # IfcRelDefinesByType inverse: IsTypedBy (0..1)
        typed = getattr(g, "IsTypedBy", None)
        if typed:
            # IsTypedBy is SET[0:1] of IfcRelDefinesByType
            rel_def = list(typed)[0]
            t = getattr(rel_def, "RelatingType", None)
            pt = getattr(t, "PredefinedType", None)
            if pt and pt != "NOTDEFINED":
                return pt
    except Exception:
        pass

    pt = getattr(g, "PredefinedType", None)
    return pt

def _subcategory_from_system_types(system_types: set[str]) -> str | None:
    # priority order matters (backup gen shouldn’t be swallowed by ELECTRICAL if both exist)
    if "POWERGENERATION" in system_types:
        return "5.3.2.5"
    if system_types & {"CONTROL", "MONITORINGSYSTEM"}:
        return "5.3.2.4"
    if system_types & {"DATA", "FIXEDTRANSMISSIONNETWORK", "MOBILENETWORK"}:
        return "5.3.2.3"
    if system_types & {"SECURITY", "COMMUNICATION", "TELEPHONE", "TV", "AUDIOVISUAL", "ELECTROACOUSTIC"}:
        return "5.3.2.2"
    if system_types & {"ELECTRICAL", "EARTHING", "LIGHTNINGPROTECTION"}:
        return "5.3.2.1"
    return None

def _is_fire_detection_or_alarm(el:entity_instance) -> bool:
    if el.is_a("IfcSensor"):
        pt = getattr(el, "PredefinedType", None)
        return pt in {"SMOKESENSOR", "FIRESENSOR", "HEATSENSOR"}
    if el.is_a("IfcAlarm"):
        # Alarm "type" enum lives on IfcAlarmTypeEnum (often via type object)
        # IfcAlarm occurrence as fire-detection candidate unless proven otherwise,
        return True
    return False

def category_532(ad: CoreType, idx: PreIndex):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "5.3.2"
    # includes subtypes
    dist_elements = ad.by_types(["IfcDistributionElement"]) 

    agg: dict[tuple, CategoryRow] = {}

    n = 0
    n_pdt_ok = n_class_ok = n_class_fields_ok = 0
    n_shape_ok = n_qto_ok = 0
    n_common_ok = n_mat_ok = n_doc_ok = 0
    sum_l4a = 0.0

    relevant_qto_types = {"IfcQuantityCount", "IfcQuantityLength", "IfcQuantityArea", "IfcQuantityVolume"}
    scoped_elements = []

    def _add(el:entity_instance, sub_code: str):
        nonlocal n, n_pdt_ok, n_class_ok, n_class_fields_ok
        nonlocal n_shape_ok, n_qto_ok, n_common_ok, n_mat_ok, n_doc_ok, sum_l4a

        if not el or el.id() in ad.parsedElIds:
            return
        scoped_elements.append(el)

        ifc_class = el.is_a()
        pdt = getattr(el, "PredefinedType", None)

        # issues 
        if hasattr(el, "PredefinedType") and ((pdt is None) or (pdt == "NOTDEFINED")):
            out.issues.append(IssueRow(
                category_code=sub_code, category_name="", ifc_class=ifc_class,
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
        row.category_code = sub_code  # store final subcategory as main code
        row.category_name = "5.3.2"
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

    for el in ad.by_types(["IfcSensor", "IfcAlarm"]):
        if not el or el.id() in ad.parsedElIds:
           continue
        if _is_fire_detection_or_alarm(el):
            if el.is_a("IfcSensor") and getattr(el, "PredefinedType", None) in (None, "NOTDEFINED"):
                out.issues.append(IssueRow(
                    category_code="5.3.2.6", category_name="", ifc_class=el.is_a(),
                    message="Fire detection sensor missing PredefinedType (e.g., SMOKESENSOR/FIRESENSOR/HEATSENSOR)"
                ))
            _add(el, "5.3.2.6")
    # Pass 1: system/circuit based classification
    for el in dist_elements:
        if not el or el.id() in ad.parsedElIds:
            continue

        sys_types = set()
        missing_sys_type = False

        for g in _assigned_distribution_groups(el):
            st = _system_type_of_group(g)
            if st and st != "NOTDEFINED":
                sys_types.add(st)
            else:
                missing_sys_type = True

        sub = _subcategory_from_system_types(sys_types)

        if missing_sys_type:
            out.issues.append(IssueRow(
                category_code="5.3.2", category_name="", ifc_class=el.is_a(),
                message="Element assigned to distribution group with missing/NOTDEFINED system PredefinedType"
            ))

        if sub:
            _add(el, sub)

   

    out.categories = list(agg.values())

    # overview (scores aggregated over all included 5.3.2.* elements)
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
        {"5.3.2": scoped_elements},
        qto_by_category={"5.3.2": relevant_qto_types},
    )

    return out