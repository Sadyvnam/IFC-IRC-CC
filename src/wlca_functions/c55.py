from src.utils import PreIndex,CoreType
from src.excel.types import IssueRow,CategoryRow,CategoryReturn,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
    # 5.5.1 Life safety
    # 5.5.1.1 Sprinkler system
    # 5.5.1.2 Fire fighting systems
    # 5.5.1.3 Lightning protection/earth bonding
def category_55(ad: CoreType, idx: PreIndex):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "5.5"

    # ---------- helpers ----------
    def get_predef(obj):
        try:
            typed = getattr(obj, "IsTypedBy", None)
            if typed:
                rel_def = list(typed)[0]
                t = getattr(rel_def, "RelatingType", None)
                pt = getattr(t, "PredefinedType", None)
                if pt and pt != "NOTDEFINED":
                    return pt
        except Exception:
            pass
        return getattr(obj, "PredefinedType", None)

    def add_issue(code, ifc_class, msg):
        out.issues.append(IssueRow(category_code=code, category_name="", ifc_class=ifc_class, message=msg))

    # ---------- aggregation + indicators ----------
    agg: dict[tuple, CategoryRow] = {}

    n = 0
    n_pdt_ok = n_class_ok = n_class_fields_ok = 0
    n_shape_ok = n_qto_ok = 0
    n_common_ok = n_mat_ok = n_doc_ok = 0
    sum_l4a = 0.0

    relevant_qto_types = {"IfcQuantityCount", "IfcQuantityLength", "IfcQuantityArea", "IfcQuantityVolume"}
    scoped_elements = []

    def add_row(el, code):
        nonlocal n, n_pdt_ok, n_class_ok, n_class_fields_ok
        nonlocal n_shape_ok, n_qto_ok, n_common_ok, n_mat_ok, n_doc_ok, sum_l4a

        if not el or el.id() in ad.parsedElIds:
            return
        scoped_elements.append(el)

        pdt = get_predef(el)
        ifc_class = el.is_a()

        if hasattr(el, "PredefinedType") and ((pdt is None) or (pdt == "NOTDEFINED")):
            add_issue(code, ifc_class, "Missing predefined type")

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

        key = (row.category_code, row.ifc_class, row.object_type or (pdt or ""), row.material_name or "")
        if key not in agg:
            agg[key] = row
        else:
            a = agg[key]
            a.count += 1
            a.volume_m3 += (row.volume_m3 or 0.0)
            a.area_m2 += (row.area_m2 or 0.0)
            a.count_cantCalcRI += row.count_cantCalcRI

    # ---------- 5.5.1.1 / 5.5.1.2: sprinklers & firefighting ----------
    for el in ad.by_types(["IfcFireSuppressionTerminal"]):
        if not el or el.id() in ad.parsedElIds:
            continue
        pdt = get_predef(el)
        if pdt == "SPRINKLER":
            add_row(el, "5.5.1.1")
        elif pdt in {"FIREHYDRANT", "HOSEREEL", "BREECHINGINLET", "FIREMONITOR"}:
            add_row(el, "5.5.1.2")
        else:
            add_issue("5.5.1.2", el.is_a(), "Fire suppression terminal has unclear type (not SPRINKLER/HYDRANT/HOSEREEL/etc.)")
            add_row(el, "5.5.1.2")

    # ---------- system membership collector ----------
    sys_members = {}  # system_predef -> set(elements)
    systems = ad.by_types(["IfcDistributionSystem"])
    if systems:
        sys_set = set(systems)
        for rel in ad.by_types(["IfcRelAssignsToGroup"]):
            g = getattr(rel, "RelatingGroup", None)
            if g in sys_set:
                st = get_predef(g)
                if not st or st == "NOTDEFINED":
                    continue
                bucket = sys_members.setdefault(st, set())
                for obj in getattr(rel, "RelatedObjects", []) or []:
                    bucket.add(obj)

    # ---------- 5.5.1.3: lightning protection / earth bonding ----------
    for st in ("LIGHTNINGPROTECTION", "EARTHING"):
        for el in sys_members.get(st, []):
            add_row(el, "5.5.1.3")

    # ---------- 5.5.2: fuel installations ----------
    for st in ("FUEL", "GAS", "OIL"):
        for el in sys_members.get(st, []):
            add_row(el, "5.5.2")

    # ---------- 5.5.3: lifts & conveyor installations ----------
    for el in ad.by_types(["IfcTransportElement"]):
        if not el or el.id() in ad.parsedElIds:
            continue
        pdt = get_predef(el)
        if pdt in {"ELEVATOR", "ESCALATOR", "MOVINGWALKWAY", "CRANEWAY", "LIFTINGGEAR"}:
            add_row(el, "5.5.3")
        elif pdt in (None, "NOTDEFINED"):
            add_issue("5.5.3", el.is_a(), "IfcTransportElement missing PredefinedType (cannot classify lift/escalator/moving walkway)")

    for el in sys_members.get("CONVEYING", []):
        add_row(el, "5.5.3")

    # ---------- 5.5.4: waste disposal ----------
    for el in ad.by_types(["IfcWasteTerminal"]):
        add_row(el, "5.5.4")

    for el in ad.by_types(["IfcInterceptor"]):
        add_row(el, "5.5.4")

    for st in ("MUNICIPALSOLIDWASTE", "DISPOSAL"):
        for el in sys_members.get(st, []):
            add_row(el, "5.5.4")

    out.categories = list(agg.values())

    if not out.categories:
        add_issue("5.5", "", "No deterministic 5.5 service elements found (fire terminals, distribution systems, transport elements, waste terminals/interceptors)")

    # ---------- overview ----------
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
        {"5.5": scoped_elements},
        qto_by_category={"5.5": relevant_qto_types},
    )

    return out
