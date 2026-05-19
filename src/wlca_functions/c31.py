from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 3.1 Wall finishes 
def category_31(ad: CoreType):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "3.1"

    wall_hosts = ad.by_types(["IfcWall", "IfcWallStandardCase", "IfcCurtainWall"])
    wall_host_ids = {w.id() for w in wall_hosts}

    # IfcRelCoversBldgElements IS 2x3 ONLY CAN IGNORE FOR IFC4
    wall_coverings = set()         # actual objects
    unlinked_fallback = set()      # actual objects flagged as fallback

    for rel in ad.by_types(["IfcRelCoversBldgElements"]):
        host = getattr(rel, "RelatingBuildingElement", None)
        if not host:
            continue
        try:
            if host.id() not in wall_host_ids:
                continue
        except Exception:
            continue

        related = getattr(rel, "RelatedCoverings", [])
        for cov in related:
            if cov:
                wall_coverings.add(cov)

    # --- 3) conservative fallback: include coverings by PredefinedType but warn if not linked ---
    finish_types = {"CLADDING", "INSULATION", "MEMBRANE", "WRAPPING"}  # deterministic enum set
    for cov in ad.by_types(["IfcCovering"]):
        if cov.id() in ad.parsedElIds:
            continue
        pdt = getattr(cov, "PredefinedType", None)
        if pdt in finish_types:
            if cov not in wall_coverings:
                unlinked_fallback.add(cov)
            wall_coverings.add(cov)

    # --- aggregation dict ---
    agg: dict[tuple, CategoryRow] = {}

    # --- scoring counters over all included wall_coverings ---
    n = 0
    n_pdt_ok = 0
    n_class_ok = 0
    n_class_fields_ok = 0

    n_shape_ok = 0
    n_qto_ok = 0

    n_common_pset_ok = 0
    n_mat_ok = 0
    n_doc_ok = 0
    sum_l4a =0
    
    relevant_qto_types = {"IfcQuantityArea", "IfcQuantityVolume"}
    scoped_elements = []

    for cov in wall_coverings:
        if cov.id() in ad.parsedElIds:
            continue
        scoped_elements.append(cov)

        ifc_class = cov.is_a()
        pdt = getattr(cov, "PredefinedType", None)

        # Issues
        if (pdt is None) or (pdt == "NOTDEFINED"):
            issue = IssueRow()
            issue.category_code = "3.1"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing IfcCovering.PredefinedType (cannot classify wall finish type)"
            out.issues.append(issue)

        # if cov in unlinked_fallback:
        #     issue = IssueRow()
        #     issue.category_code = "3.1"
        #     issue.category_name = ""
        #     issue.ifc_class = ifc_class
        #     issue.message = "IfcCovering matches wall-finish PredefinedType but is not linked to a wall via IfcRelCoversBldgElements"
        #     out.issues.append(issue)

        # --- scoring (element included) ---
        n += 1
        sum_l4a += ad.parse_element_EII(cov)["score"]
        if ad._valid_predefined_type(cov):
            n_pdt_ok += 1
        if ad._has_classification_ref(cov):
            n_class_ok += 1
        if ad._classification_required_fields_non_null(cov):
            n_class_fields_ok += 1

        if ad._has_shape_representation(cov):
            n_shape_ok += 1
        if ad._has_relevant_qto(cov, relevant_qto_types):
            n_qto_ok += 1

        common = ad.get_element_common_pset(cov)
        if common is not None:
            n_common_pset_ok += 1

        if ad._has_material_association(cov):
            n_mat_ok += 1
        if ad._has_document_association(cov):
            n_doc_ok += 1

        # --- build rows + aggregate ---
        row = CategoryRow()
        row.category_code = "3.1"
        row.category_name = ""
        row = ad.build_category_row(cov, row)

        key = (
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

    # --- compute weighted scores ---
    presence = 1.0 if n > 0 else 0.0
    if n > 0:
        s_pdt = n_pdt_ok / n
        s_class = n_class_ok / n
        s_class_fields = n_class_fields_ok / n

        s_shape = n_shape_ok / n
        s_qto = n_qto_ok / n

        s_common = n_common_pset_ok / n
        s_mat = n_mat_ok / n
        s_doc = n_doc_ok / n
    else:
        s_pdt = s_class = s_class_fields = 0.0
        s_shape = s_qto = 0.0
        s_common = s_mat = s_doc = 0.0

    out.overview.l1_score = (
        0.2 * presence +
        0.2 * s_pdt +
        0.4 * s_class +
        0.2 * s_class_fields
    )
    out.overview.l2_score = 0.3 * s_shape + 0.7 * s_qto
    out.overview.l3_score = 0.3 * s_common + 0.3 * s_mat + 0.4 * s_doc

    out.overview.l4a_score = (sum_l4a / n) if n else 0.0
    out.overview.l4b_score = 0.0
    out.overview.issues = len(out.issues)
    finalize_category_metrics(
        ad,
        out,
        {"3.1": scoped_elements},
        qto_by_category={"3.1": relevant_qto_types},
    )

    return out

# def c_31_L1_entities_typed(ad, idx):
#     elems = idx["finishes_wall"] + idx["finishes_space"] + idx["plates"] + idx["trims"]
#     ok,f=0,[]
#     for e in elems:
#         pt  = getattr(e.get_info(),"PredefinedType",None) if hasattr(e,"PredefinedType") else "NA"
#         typed = (pt and str(pt)!="NOTDEFINED") or e.is_a() in ("IfcPlate","IfcMember")
#         cls = ad.has_classification(e) or ad.has_classification(ad.type_of(e))
#         if typed and cls: ok += 1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing type/classification"})
#     return mk_result("L1-3.1-01","Wall finishes typed & classified",["3.1"],
#                       ["IfcCovering","IfcPlate","IfcMember"], ok, len(elems), f)

# def c_31_L1_internal_host_resolvable(ad, idx):
#     elems = idx["finishes_wall"] + idx["plates"] + idx["trims"]
#     ok,f=0,[]
#     for e in elems:
#         host = ad.covers_host(e) or ad.attached_host(e)
#         if host and host.is_a().startswith("IfcWall") and ad.is_external(host) is False:
#             ok += 1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Host not resolvably internal wall"})
#     return mk_result("L1-3.1-02","Internal host resolvable",["3.1"],["IfcCovering","IfcPlate","IfcMember"], ok, len(elems), f)


# def c_31_L2_finish_area_thickness(ad, idx):
#     elems = idx["finishes_wall"] + idx["finishes_space"]
#     ok,f=0,[]
#     for e in elems:
#         A = ad.qto_area(e) or ad.geom_area(e)
#         t = ad.layer_thickness(e) or ad.qto_value(e,"Thickness")
#         if A and A>0 and t and t>0: ok += 1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing/zero area or thickness"})
#     return mk_result("L2-3.1-01","Finish area & thickness",["3.1"],["IfcCovering"], ok, len(elems), f)

# def c_31_L2_panels_and_trims_qto(ad, idx):
#     ok,f=0,[]
#     for p in idx["plates"]:
#         A = ad.qto_area(p) or ad.geom_area(p)
#         if A and A>0: ok += 1
#         else: f.append({"entity_guid":p.GlobalId,"entity_type":p.is_a(),"message":"Panel area missing"})
#     for m in idx["trims"]:
#         L = ad.qto_length(m) or ad.geom_length_path(m)
#         if L and L>0: ok += 1
#         else: f.append({"entity_guid":m.GlobalId,"entity_type":m.is_a(),"message":"Trim length missing"})
#     total = len(idx["plates"]) + len(idx["trims"])
#     return mk_result("L2-3.1-02","Panels/trims quantities",["3.1"],["IfcPlate","IfcMember"], ok, total, f)


# def c_31_L3_materials_density_sl(ad, idx):
#     elems = idx["finishes_wall"] + idx["finishes_space"] + idx["plates"] + idx["trims"]
#     ok,f=0,[]
#     for e in elems:
#         mats = ad.materials(e); dens = ad.material_density(e)
#         sl   = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         if mats and sl and (dens or e.is_a()=="IfcMember"):  # trims can pass without density if unit is length
#             ok += 1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing material/density/service life"})
#     return mk_result("L3-3.1-01","Materials & service life",["3.1"],["IfcCovering","IfcPlate","IfcMember"], ok, len(elems), f)

# def c_31_L3_finish_specific_props(ad, idx):
#     # Optional but useful: VOC class / coating type / acoustic rating for panels
#     elems = idx["finishes_wall"] + idx["plates"]
#     ok,f=0,[]
#     for e in elems:
#         voc  = ad.pset(e,"Pset_CoveringCommon","EmissivityClass") or ad.pset(e,"Pset_CoveringCommon","FinishType")
#         acou = ad.pset(e,"Pset_Acoustic","SoundAbsorptionAverage") or ad.pset(e,"Pset_CoveringCommon","AcousticRating")
#         if voc or acou: ok += 1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No VOC/finish/acoustic info"})
#     return mk_result("L3-3.1-02","Finish-specific props",["3.1"],["IfcCovering","IfcPlate"], ok, len(elems), f)


# def c_31_L4_covers_relation(ad, idx):
#     elems = idx["finishes_wall"] + idx["plates"] + idx["trims"]
#     ok,f=0,[]
#     for e in elems:
#         # prefer explicit relation; for trims allow host attachment
#         ok_rel = ad.covers_host(e) is not None or ad.has_rel_covers_bldg_elements(e) or ad.attached_host(e) is not None
#         if ok_rel: ok += 1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No cover/attach relation to wall"})
#     return mk_result("L4-3.1-01","Covers/attach relation present",["3.1"],["IfcCovering","IfcPlate","IfcMember"], ok, len(elems), f)

# def c_31_L4_coverage_ratio(ad, idx, target=0.85):
#     # How much of internal wall surface is finished?
#     wallA = sum((ad.qto_area(w) or ad.geom_area(w) or 0) for w in idx["walls_int"])
#     finA  = sum((ad.qto_area(e) or ad.geom_area(e) or 0) for e in (idx["finishes_wall"] + idx["plates"]))
#     if wallA <= 0:
#         return mk_result("L4-3.1-02","Coverage ratio",["3.1"],["IfcCovering","IfcPlate"], ok_count=1, total=1, findings=[], kind="consistency")
#     ratio = finA / max(wallA, 1e-6)
#     ok = ratio >= target
#     findings = [] if ok else [{"entity_guid":"-","entity_type":"-","message":f"coverage={ratio:.2f} (<{target})"}]
#     return mk_result("L4-3.1-02","Coverage ratio",["3.1"],["IfcCovering","IfcPlate"], ok_count=1 if ok else 0, total=1, findings=findings, kind="consistency")


# def c_31_L5_epd_linkability(ad, idx):
#     elems = idx["finishes_wall"] + idx["plates"] + idx["trims"]
#     ok,f=0,[]
#     for e in elems:
#         link = ad.epd_link(e) or ad.type_epd_link(e) or ad.material_mappable(e)
#         # typical units: coatings/linings/panels → m2 or kg; trims → kg or kg/m
#         unit_ok = ad.has_compatible_qto_unit(e, expect=("m2","kg","kg/m"))
#         sl = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         if link and unit_ok and sl: ok += 1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing EPD/doc, unit hint, or service life"})
#     return mk_result("L5-3.1-01","EPD linkability (presence)",["3.1"],["IfcCovering","IfcPlate","IfcMember"], ok, len(elems), f)

# def c_31_L5_reversibility(ad, idx):
#     # Mechanically fixed panels/linings score; fully bonded/plastered score low
#     elems = idx["plates"] + idx["finishes_wall"]
#     ok,f=0,[]
#     for e in elems:
#         mech = ad.has_realizing_fasteners(e) or ad.is_mechanically_fixed(e)
#         bonded = ad.name_contains(e, ("adhesive","glued","bonded","skim")) or ad.pset(e,"Pset_Connection","Bonded") is True
#         if mech and not bonded: ok += 1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No mechanical fixing evidence (likely bonded)"})
#     total = len(elems) if elems else 1
#     return mk_result("L5-3.1-02","Reversibility (demountable linings)",["3.1"],["IfcCovering","IfcPlate"], ok, total, f)
