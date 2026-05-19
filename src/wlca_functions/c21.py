from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 2.1 Frame
# 2.1.1 Frame (Vertical)  - Columns/ structural walls & braces
# 2.1.2 Frame (Horizontal) - Beams, joists & braces
PARTITION_PREDEFINED_TYPES = {"PARTITIONING", "MOVABLE"}


def _unwrap_bool(v):
    if isinstance(v, dict):
        return v.get("value")
    return v


def _boolish(ad: CoreType, v):
    return ad._boolish(_unwrap_bool(v))


def _wall_common_bool(ad: CoreType, wall, prop: str):
    common = ad.get_element_common_pset(wall)
    val = common.get(prop) if common else None
    parsed = _boolish(ad, val)
    if parsed is not None:
        return parsed

    wall_type = ad._type_of(wall)
    if wall_type:
        parsed = _boolish(ad, ad.get_pset_value(wall_type, "Pset_WallCommon", prop))
        if parsed is not None:
            return parsed

    return None


def classify_wall_bec(ad: CoreType, wall) -> tuple[str, list[str]]:
    """
    Route IfcWall/IfcWallStandardCase into the active BEC.

    BEC 2.7 is exported through category_21() routing, not through category_27().
    Ambiguous routes remain traceable through element-level warning messages.
    """
    warnings: list[str] = []
    pdt = str(getattr(wall, "PredefinedType", "") or "").upper()
    load_bearing = _wall_common_bool(ad, wall, "LoadBearing")
    is_external = _wall_common_bool(ad, wall, "IsExternal")

    if load_bearing is True:
        return "2.1.1", warnings

    if load_bearing is False:
        if is_external is True:
            return "2.5", warnings
        if is_external is False:
            return "2.7", warnings
        warnings.append("Wall routed to 2.7 because LoadBearing=False, but IsExternal was not declared")
        return "2.7", warnings

    if pdt in PARTITION_PREDEFINED_TYPES:
        if is_external is True:
            warnings.append("Wall has partition-type evidence but IsExternal=True; routed to 2.5")
            return "2.5", warnings
        warnings.append("Wall routed to 2.7 from partition PredefinedType, but LoadBearing was not declared")
        return "2.7", warnings

    if is_external is True:
        warnings.append("External wall routed to 2.5, but LoadBearing was not declared")
        return "2.5", warnings

    if is_external is False:
        warnings.append("Internal wall routed to 2.7, but LoadBearing and partition-type evidence were missing")
        return "2.7", warnings

    warnings.append("Wall kept in 2.1.1 because LoadBearing, IsExternal, and deterministic partition PredefinedType were not declared")
    return "2.1.1", warnings


def _finalize_indicator(row: IndicatorRow, n: float,
                        n_pdt_ok: float, n_class_ok: float, n_class_fields_ok: float,
                        n_shape_ok: float, n_qto_ok: float,
                        n_common_ok: float, n_mat_ok: float, n_doc_ok: float,
                        l4a_sum: float, n_issues: float):
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


def category_21(ad: CoreType) -> CategoryReturn:
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "2.1"
    out.overviews = []

    # Instance elements only (types excluded)
    columns = ad.by_types(["IfcColumn"])
    beams   = ad.by_types(["IfcBeam"])
    walls   = ad.by_types(["IfcWall", "IfcWallStandardCase"])

    agg: dict[tuple, CategoryRow] = {}
    scoped_by_category = {"2.1": [], "2.7": []}

    counters = {
        "2.1": {
            "n": 0, "pdt": 0, "class": 0, "class_fields": 0,
            "shape": 0, "qto": 0, "common": 0, "mat": 0, "doc": 0,
            "l4a": 0.0, "issues": 0,
        },
        "2.7": {
            "n": 0, "pdt": 0, "class": 0, "class_fields": 0,
            "shape": 0, "qto": 0, "common": 0, "mat": 0, "doc": 0,
            "l4a": 0.0, "issues": 0,
        },
    }
    # frame elements: volume/area/length are all potentially relevant
    relevant_qto_types = {"IfcQuantityVolume", "IfcQuantityArea", "IfcQuantityLength"}

    def add_element(el, default_code: str):
        if el.id() in ad.parsedElIds:
            return

        ifc_class = el.is_a()
        pdt = getattr(el, "PredefinedType", None)

        # Build base row
        row = CategoryRow()
        row.category_code = default_code
        row.category_name = ""
        row = ad.build_category_row(el, row)

        common = ad.get_element_common_pset(el)

        if ifc_class.startswith("IfcWall"):
            row.category_code, routing_warnings = classify_wall_bec(ad, el)
            for message in routing_warnings:
                issue = IssueRow()
                issue.ifc_guid = getattr(el, "GlobalId", "") or ""
                issue.element_id = str(el.id())
                issue.element_type = getattr(el, "ObjectType", "") or ""
                issue.ifc_class = ifc_class
                issue.scope = "element"
                issue.category_code = row.category_code
                issue.category_name = ""
                issue.severity = "warning"
                issue.message = message
                issue.whatShouldBeDifferent = "Declare Pset_WallCommon.LoadBearing and Pset_WallCommon.IsExternal, or provide an explicit partition-style IfcWall.PredefinedType."
                out.issues.append(issue)
                if row.category_code.startswith("2.1"):
                    counters["2.1"]["issues"] += 1
                elif row.category_code == "2.7":
                    counters["2.7"]["issues"] += 1

        # --- issues (keep category_code reflecting where it ends up) ---
        if pdt == "NOTDEFINED" or pdt is None:
            issue = IssueRow()
            issue.category_code = row.category_code
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing predefined type"
            out.issues.append(issue)
            if row.category_code.startswith("2.1"):
                counters["2.1"]["issues"] += 1
            elif row.category_code == "2.7":
                counters["2.7"]["issues"] += 1

        score_bucket = None
        if row.category_code in {"2.1.1", "2.1.2"}:
            score_bucket = counters["2.1"]
        elif row.category_code == "2.7":
            score_bucket = counters["2.7"]

        if score_bucket is not None:
            if row.category_code in {"2.1.1", "2.1.2"}:
                scoped_by_category["2.1"].append(el)
            elif row.category_code == "2.7":
                scoped_by_category["2.7"].append(el)
            score_bucket["n"] += 1
            score_bucket["l4a"] += ad.parse_element_EII(el)["score"]
            if ad._valid_predefined_type(el):
                score_bucket["pdt"] += 1
            if ad._has_classification_ref(el):
                score_bucket["class"] += 1
            if ad._classification_required_fields_non_null(el):
                score_bucket["class_fields"] += 1

            if ad._has_shape_representation(el):
                score_bucket["shape"] += 1
            if ad._has_relevant_qto(el, relevant_qto_types):
                score_bucket["qto"] += 1

            if common is not None:
                score_bucket["common"] += 1

            if ad._has_material_association(el):
                score_bucket["mat"] += 1
            if ad._has_document_association(el):
                score_bucket["doc"] += 1

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

    # --- process elements ---
    for w in walls:
        add_element(w, default_code="2.1.1")  # vertical
    for c in columns:
        add_element(c, default_code="2.1.1")  # vertical
    for b in beams:
        add_element(b, default_code="2.1.2")  # horizontal

    out.categories = list(agg.values())

    ov21 = IndicatorRow(category="2.1")
    c21 = counters["2.1"]
    _finalize_indicator(
        ov21, c21["n"], c21["pdt"], c21["class"], c21["class_fields"],
        c21["shape"], c21["qto"], c21["common"], c21["mat"], c21["doc"],
        c21["l4a"], c21["issues"],
    )

    ov27 = IndicatorRow(category="2.7")
    c27 = counters["2.7"]
    _finalize_indicator(
        ov27, c27["n"], c27["pdt"], c27["class"], c27["class_fields"],
        c27["shape"], c27["qto"], c27["common"], c27["mat"], c27["doc"],
        c27["l4a"], c27["issues"],
    )

    out.overview = ov21
    out.overviews = [ov21, ov27]
    finalize_category_metrics(
        ad,
        out,
        scoped_by_category,
        qto_by_category={"2.1": relevant_qto_types, "2.7": relevant_qto_types},
    )

    return out



# def c_21_L1_cols_typed(ad:CoreType, idx:PreIndex):
#     # columns are usually always present, however,
#     # we need to check the type of them, which category does it belong to.
#     elems = idx["columns"]
#     ok,f=0,[]
#     for e in elems:
#         pt = getattr(e.get_info(),"PredefinedType",None)
#         if pt and str(pt)!="NOTDEFINED" and ad.has_type_def(e): ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"Missing PredefinedType/Type"})
#     return mk_result("L1-2.1.1-01","Columns typed",["2.1.1"],["IfcColumn"],ok,len(elems),f)

# def c_21_L1_vert_classified(ad:CoreType, idx:PreIndex):
#     # basically this functions checks for the presence of a deeper knowledge
#     # about the classification of an item IfcClassification, 
#     # like Source, edition, name, description, specification (url) 
#     elems = idx["columns"] + idx["struct_walls"] + idx["braces"]
#     ok,f=0,[]
#     for e in elems:
#         if ad.has_classification(e): ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"No classification"})
#     return mk_result("L1-2.1.1-02","Vertical classified",["2.1.1"],["IfcColumn","IfcWall","IfcMember"],ok,len(elems),f)

# def c_21_L1_beams_typed(ad:CoreType, idx:PreIndex):
#     elems = idx["beams"] + idx["joists"]
#     ok,f=0,[]
#     for e in elems:
#         pt = getattr(e.get_info(),"PredefinedType",None)
#         if pt and str(pt)!="NOTDEFINED" and ad.has_type_def(e): ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"Missing PredefinedType/Type"})
#     return mk_result("L1-2.1.2-01","Beams/joists typed",["2.1.2"],["IfcBeam","IfcMember"],ok,len(elems),f)

# def c_21_L1_horiz_classified(ad:CoreType, idx:PreIndex):
#     # basically this functions checks for the presence of a deeper knowledge
#     # about the classification of an item IfcClassification, 
#     # like Source, edition, name, description, specification (url)
#     elems = idx["beams"] + idx["joists"]
#     ok,f=0,[]
#     for e in elems:
#         if ad.has_classification(e): ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"No classification"})
#     return mk_result("L1-2.1.2-02","Horizontal classified",["2.1.2"],["IfcBeam","IfcMember"],ok,len(elems),f)

# def c_21_L2_cols_qto_profile(ad:CoreType, idx:PreIndex):
#     ok,f=0,[]
#     for e in idx["columns"]:
#         L = ad.qto_value(e,"Length") or ad.geom_length_axis(e)
#         A = ad.cross_section_area(e) or ad.profile_area(e)
#         V = ad.qto_volume(e) or (L*A if L and A else None)
#         prof = ad.profile_name(e)
#         if L and L>0 and A and A>0 and V and V>0 and prof: ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"Missing length/area/volume/profile"})
#     return mk_result("L2-2.1.1-01","Columns Qto+profile",["2.1.1"],["IfcColumn"],ok,len(idx["columns"]),f)

# def c_21_L2_beams_qto_profile(ad:CoreType, idx:PreIndex):
#     elems = idx["beams"] + idx["joists"]
#     ok,f=0,[]
#     for e in elems:
#         L = ad.qto_value(e,"Length") or ad.geom_span(e)
#         A = ad.cross_section_area(e) or ad.profile_area(e)
#         V = ad.qto_volume(e) or (L*A if L and A else None)
#         prof = ad.profile_name(e)
#         if L and L>0 and A and A>0 and V and V>0 and prof: ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"Missing length/area/volume/profile"})
#     return mk_result("L2-2.1.2-01","Beams/joists Qto+profile",["2.1.2"],["IfcBeam","IfcMember"],ok,len(elems),f)

# def c_21_L2_struct_walls_qto(ad:CoreType, idx:PreIndex):
#     elems = idx["struct_walls"]
#     ok,f=0,[]
#     for w in elems:
#         A = ad.qto_area(w) or ad.geom_area(w)
#         t = ad.layer_thickness(w) or ad.qto_value(w,"Thickness")
#         V = ad.qto_volume(w) or (A*t if A and t else None)
#         if A and A>0 and t and t>0 and V and V>0: ok+=1
#         else: f.append({"entity_guid":w.id(),"entity_type":w.is_a(),"message":"Missing area/thickness/volume"})
#     return mk_result("L2-2.1.1-02","Structural walls Qto",["2.1.1"],["IfcWall"],ok,len(elems),f)

# def c_21_L3_materials_density(ad:CoreType, idx:PreIndex):
#     elems = idx["columns"] + idx["beams"] + idx["joists"] + idx["struct_walls"]
#     ok,f=0,[]
#     for e in elems:
#         mats = ad.materials(e)
#         dens = ad.material_density(e)
#         if mats and dens: ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"No material or density"})
#     return mk_result("L3-2.1-01","Materials+density",["2.1.1","2.1.2"],["IfcColumn","IfcBeam","IfcWall","IfcMember"],ok,len(elems),f)

# def c_21_L3_grade_fire_coating(ad:CoreType, idx:PreIndex):
#     # this is not really relevant? for the scope of decarbonization or circularity
#     elems = idx["columns"] + idx["beams"]
#     ok,f=0,[]
#     for e in elems:
#         grade = ad.pset(e,"Pset_SteelCommon","Grade") or ad.pset(e,"Pset_TimberCommon","Grade") or ad.pset(e,"Pset_ConcreteCommon","StrengthClass")
#         firer = ad.pset(e,"Pset_BuildingElementCommon","FireRating")
#         coat  = ad.coating_finish(e)  # intumescent/galv/paint if present
#         if grade and (firer or coat): ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"Missing grade and/or fire/coat"})
#     return mk_result("L3-2.1-02","Grade + Fire/Coating",["2.1"],["IfcColumn","IfcBeam"],ok,len(elems),f)

# def c_21_L3_traceability_servicelife(ad:CoreType, idx:PreIndex):
#     elems = idx["columns"] + idx["beams"] + idx["struct_walls"]
#     ok,f=0,[]
#     for e in elems:
#         mref = ad.pset(e,"Pset_ManufacturerOccurrence","ModelReference") or ad.pset(e,"Pset_ManufacturerOccurrence","ArticleNumber")
#         sl   = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         if mref or sl: ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"No manufacturer ref / service life"})
#     return mk_result("L3-2.1-03","Traceability/Service life",["2.1"],["IfcColumn","IfcBeam","IfcWall"],ok,len(elems),f)

# def c_21_L4_containment(ad:CoreType, idx:PreIndex):
#     elems = idx["columns"] + idx["beams"] + idx["struct_walls"]
#     ok,f=0,[]
#     for e in elems:
#         if ad.has_spatial_container(e): ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"No spatial container"})
#     return mk_result("L4-2.1-01","Spatial containment",["2.1"],["IfcColumn","IfcBeam","IfcWall"],ok,len(elems),f)

# def c_21_L4_beam_supports(ad:CoreType, idx:PreIndex):
#     ok,f=0,[]
#     for b in idx["beams"]:
#         supports = ad.connected_supports(b)  # columns/walls/beam-to-beam seats
#         span_ok  = ad.geom_span(b) and ad.geom_span(b) > 0
#         if supports and span_ok: ok+=1
#         else: f.append({"entity_guid":b.id(),"entity_type":b.is_a(),"message":"No supports or zero span"})
#     return mk_result("L4-2.1.2-01","Beams supported",["2.1.2"],["IfcBeam"],ok,len(idx["beams"]),f)

# def c_21_L4_frames_connectivity(ad:CoreType, idx:PreIndex):
#     # simple graph coverage: beams connect to ≥2 supports; columns connect up/down
#     ok,f=0,[]
#     for c in idx["columns"]:
#         up = ad.connected_upwards(c); down = ad.connected_downwards(c)
#         if up or down: ok+=1
#         else: f.append({"entity_guid":c.id(),"entity_type":c.is_a(),"message":"Isolated column"})
#     return mk_result("L4-2.1.1-03","Frame connectivity",["2.1.1"],["IfcColumn"],ok,len(idx["columns"]),f)

# def c_21_L5_epd_linkability(ad:CoreType, idx:PreIndex):
#     elems = idx["columns"] + idx["beams"] + idx["struct_walls"] + idx["braces"] + idx["joists"]
#     ok,f=0,[]
#     for e in elems:
#         link = ad.epd_link(e) or ad.type_epd_link(e) or ad.material_mappable(e)
#         # unit expectations by material class
#         if ad.is_steel(e): unit_ok = ad.unit_ok_profile(e, expect=("kg","kg/m"))
#         elif ad.is_timber(e): unit_ok = ad.unit_ok_timber(e, expect=("m3","kg"))
#         else: unit_ok = ad.has_compatible_qto_unit(e, expect=("m3","kg"))
#         if link and unit_ok: ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"No EPD or incompatible units"})
#     return mk_result("L5-2.1-01","EPD linkability",["2.1"],["IfcColumn","IfcBeam","IfcWall","IfcMember"],ok,len(elems),f)

# def c_21_L5_reversibility(ad:CoreType, idx:PreIndex):
#     # demountable steel/timber frames vs cast-in concrete connection
#     elems = idx["columns"] + idx["beams"] + idx["braces"] + idx["joists"]
#     ok,f=0,[]
#     for e in elems:
#         mech = ad.has_realizing_fasteners(e) or ad.bolted_connection(e)  # IfcRelConnectsWithRealizingElements + fasteners/bolts
#         if mech: ok+=1
#         else: f.append({"entity_guid":e.id(),"entity_type":e.is_a(),"message":"No mechanical (likely cast-in/welded)"})
#     return mk_result("L5-2.1-02","Reversibility/demountable",["2.1"],["IfcColumn","IfcBeam","IfcMember"],ok,len(elems),f)
