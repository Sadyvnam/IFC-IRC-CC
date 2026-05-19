from src.utils import PreIndex,CoreType
from src.excel.types import IssueRow,CategoryRow,CategoryReturn,IndicatorRow
from ifcopenshell import entity_instance
from src.wlca_functions.check_metrics import finalize_category_metrics

# THIS IS OF LIMITED VALIDATION 
# NOT ENOUGH SAMPLE IFCS CONTAININ REG/RES SYSTEMS

# 5.4.1.1 Renewable energy - Electrical generation onsite and building mounted
# 5.4.1.2 Renewable energy - Storage onsite
# 5.4.1 On site renewable energy generation
    
def category_541(ad: CoreType, idx: PreIndex):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "5.4.1"

    gen_candidates = list(ad.by_types(["IfcSolarDevice"]))
    storage_candidates = list(ad.by_types(["IfcElectricFlowStorageDevice"]))

    agg: dict[tuple, CategoryRow] = {}

    n = 0
    n_pdt_ok = n_class_ok = n_class_fields_ok = 0
    n_shape_ok = n_qto_ok = 0
    n_common_ok = n_mat_ok = n_doc_ok = 0
    sum_l4a = 0.0

    relevant_qto_types = {"IfcQuantityCount", "IfcQuantityLength", "IfcQuantityArea", "IfcQuantityVolume"}
    scoped_elements = []

    def assigned_distribution_groups(el) -> list:
        groups = []
        for rel in getattr(el, "HasAssignments", []) or []:
            if not rel or not rel.is_a("IfcRelAssignsToGroup"):
                continue
            group = getattr(rel, "RelatingGroup", None)
            if group and group.is_a("IfcDistributionSystem"):
                groups.append(group)
        return groups

    def type_predefined_type(el):
        for rel in getattr(el, "IsTypedBy", []) or []:
            typ = getattr(rel, "RelatingType", None)
            pdt = getattr(typ, "PredefinedType", None) if typ else None
            if pdt and pdt != "NOTDEFINED":
                return str(pdt).upper()
        pdt = getattr(el, "PredefinedType", None)
        return str(pdt).upper() if pdt else None

    def is_renewable_storage_candidate(el) -> bool:
        return type_predefined_type(el) in {
            "BATTERY",
            "CAPACITOR",
            "CAPACITORBANK",
            "INDUCTOR",
            "INDUCTORBANK",
        }

    def add(el, code: str, heuristic: bool, heuristic_msg: str):
        nonlocal n, n_pdt_ok, n_class_ok, n_class_fields_ok
        nonlocal n_shape_ok, n_qto_ok, n_common_ok, n_mat_ok, n_doc_ok, sum_l4a

        if not el or el.id() in ad.parsedElIds:
            return
        scoped_elements.append(el)

        ifc_class = el.is_a()
        pdt = getattr(el, "PredefinedType", None)

        if heuristic:
            out.issues.append(IssueRow(category_code=code, category_name="", ifc_class=ifc_class, message=heuristic_msg))

        if hasattr(el, "PredefinedType") and ((pdt is None) or (pdt == "NOTDEFINED")):
            out.issues.append(IssueRow(category_code=code, category_name="", ifc_class=ifc_class, message="Missing predefined type"))

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

    # Generation is included only when IFC carries a deterministic renewable device class.
    for el in gen_candidates:
        if not el or el.id() in ad.parsedElIds:
            continue
        add(el, "5.4.1.1", heuristic=False, heuristic_msg="")

    solar_groups = set()
    for solar in gen_candidates:
        solar_groups.update(assigned_distribution_groups(solar))

    for el in storage_candidates:
        if not el or el.id() in ad.parsedElIds:
            continue
        if not is_renewable_storage_candidate(el):
            continue

        storage_groups = set(assigned_distribution_groups(el))
        if storage_groups & solar_groups:
            add(el, "5.4.1.2", heuristic=False, heuristic_msg="")
            continue

        out.issues.append(IssueRow(
            category_code="5.4.1.2",
            category_name="",
            ifc_class=el.is_a(),
            ifc_guid=getattr(el, "GlobalId", ""),
            element_id=str(el.id()),
            message="Electrical storage device is not exported as renewable storage because it is not assigned to the same IfcDistributionSystem as an IfcSolarDevice."
        ))

    out.categories = list(agg.values())

    if not out.categories:
        out.issues.append(IssueRow(
            category_code="5.4.1", category_name="", ifc_class="",
            message="No on-site renewable generation or storage found (expected IfcSolarDevice or renewable-linked IfcElectricFlowStorageDevice)"
        ))

    # overview
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
        {"5.4.1": scoped_elements},
        qto_by_category={"5.4.1": relevant_qto_types},
    )

    return out