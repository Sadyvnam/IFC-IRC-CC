from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 3.2 Floor finishes
def category_32(ad: CoreType):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "3.2"

    # 1) floor hosts (by id, deterministic)
    floor_host_ids = set()
    for s in ad.by_types(["IfcSlab"]):
        pdt = getattr(s, "PredefinedType", None)
        if pdt in {"FLOOR", "BASESLAB"}:
            floor_host_ids.add(s.id())

    # 2) coverings linked to floor slabs via IfcRelCoversBldgElements
    floor_coverings = set()
    unlinked_fallback = set()

    for rel in ad.by_types(["IfcRelCoversBldgElements"]):
        host = getattr(rel, "RelatingBuildingElement", None)
        if not host:
            continue
        try:
            if host.id() not in floor_host_ids:
                continue
        except Exception:
            continue

        related = getattr(rel, "RelatedCoverings", [])
        for cov in related:
            if cov:
                floor_coverings.add(cov)

    # 3) fallback: floor-typed coverings not linked to slab (warn)
    finish_types = {"FLOORING"}  # deterministic enum set
    for cov in ad.by_types(["IfcCovering"]):
        if cov.id() in ad.parsedElIds:
            continue
        pdt = getattr(cov, "PredefinedType", None)
        if pdt in finish_types:
            if cov not in floor_coverings:
                unlinked_fallback.add(cov)
            floor_coverings.add(cov)

    # 4) aggregate rows
    agg: dict[tuple, CategoryRow] = {}

    # --- scoring counters ---
    n = 0
    n_pdt_ok = 0
    n_class_ok = 0
    n_class_fields_ok = 0

    n_shape_ok = 0
    n_qto_ok = 0

    n_common_pset_ok = 0
    n_mat_ok = 0
    n_doc_ok = 0
    sum_l4a=0

    relevant_qto_types = {"IfcQuantityArea", "IfcQuantityVolume"}
    scoped_elements = []

    for cov in floor_coverings:
        if cov.id() in ad.parsedElIds:
            continue
        scoped_elements.append(cov)

        ifc_class = cov.is_a()
        pdt = getattr(cov, "PredefinedType", None)

        # Issues
        if (pdt is None) or (pdt == "NOTDEFINED"):
            issue = IssueRow()
            issue.category_code = "3.2"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing IfcCovering.PredefinedType (cannot classify floor finish type)"
            out.issues.append(issue)

        if cov in unlinked_fallback:
            issue = IssueRow()
            issue.category_code = "3.2"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "IfcCovering matches floor-finish PredefinedType but is not linked to a floor slab via IfcRelCoversBldgElements"
            out.issues.append(issue)

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

        # --- build + group rows ---
        row = CategoryRow()
        row.category_code = "3.2"
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
        {"3.2": scoped_elements},
        qto_by_category={"3.2": relevant_qto_types},
    )

    return out


# def c_32_L1_raf_typed_classified(ad, idx):
#     elems = idx["raf"] + idx["raf_pedestals"]
#     ok,f=0,[]
#     for e in elems:
#         typed = (hasattr(e,"PredefinedType") and str(getattr(e.get_info(),"PredefinedType"))!="NOTDEFINED") or e.is_a() in ("IfcPlate","IfcDiscreteAccessory","IfcMechanicalFastener")
#         cls   = ad.has_classification(e) or ad.has_classification(ad.type_of(e))
#         if typed and cls: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing type/classification"})
#     return mk_result("L1-3.2.1-01","RAF/sprung typed & classified",["3.2.1"],["IfcCovering","IfcPlate","IfcDiscreteAccessory"],ok,len(elems),f)

# def c_32_L1_screed_typed(ad, idx):
#     elems = idx["screed"]
#     ok,f=0,[]
#     for e in elems:
#         if getattr(e.get_info(),"PredefinedType",None) and ad.has_classification(e): ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing type/classification"})
#     return mk_result("L1-3.2.2-01","Screed typed & classified",["3.2.2"],["IfcCovering"],ok,len(elems),f)

# def c_32_L1_finish_typed(ad, idx):
#     elems = idx["finishes"] + idx["finish_plates"]
#     ok,f=0,[]
#     for e in elems:
#         typed = (hasattr(e,"PredefinedType") and str(getattr(e.get_info(),"PredefinedType"))!="NOTDEFINED") or e.is_a()=="IfcPlate"
#         cls   = ad.has_classification(e) or ad.has_classification(ad.type_of(e))
#         if typed and cls: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing type/classification"})
#     return mk_result("L1-3.2.3-01","Finishes typed & classified",["3.2.3"],["IfcCovering","IfcPlate"],ok,len(elems),f)


# def c_32_L2_raf_qto(ad, idx):
#     ok,f=0,[]
#     for e in idx["raf"]:
#         A = ad.qto_area(e) or ad.geom_area(e)
#         t = ad.layer_thickness(e) or ad.qto_value(e,"Thickness")
#         if A and A>0 and (t or 0) >= 0.0: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing area/thickness"})
#     # pedestals counted as pcs/linear if modeled
#     for p in idx["raf_pedestals"]:
#         q = ad.qto_count(p) or 1
#         if q>=1: ok+=1
#         else: f.append({"entity_guid":p.GlobalId,"entity_type":p.is_a(),"message":"Pedestal count missing"})
#     total = len(idx["raf"]) + len(idx["raf_pedestals"])
#     return mk_result("L2-3.2.1-01","RAF areas & pedestals",["3.2.1"],["IfcCovering","IfcPlate","IfcDiscreteAccessory"],ok,total,f)

# def c_32_L2_screed_qto(ad, idx, t_max=0.08):
#     elems = idx["screed"]
#     ok,f=0,[]
#     for e in elems:
#         A = ad.qto_area(e) or ad.geom_area(e)
#         t = ad.layer_thickness(e) or ad.qto_value(e,"Thickness")
#         if A and A>0 and t and 0<t<=t_max: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing area or thickness not in screed range"})
#     return mk_result("L2-3.2.2-01","Screed area & thinness",["3.2.2"],["IfcCovering"],ok,len(elems),f)

# def c_32_L2_finishes_qto(ad, idx):
#     elems = idx["finishes"] + idx["finish_plates"]
#     ok,f=0,[]
#     for e in elems:
#         A = ad.qto_area(e) or ad.geom_area(e)
#         t = ad.layer_thickness(e) or ad.qto_value(e,"Thickness")
#         if A and A>0 and (t is None or t>=0): ok+=1  
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing area (or invalid thickness)"})
#     return mk_result("L2-3.2.3-01","Finish areas (and thickness if available)",["3.2.3"],["IfcCovering","IfcPlate"],ok,len(elems),f)


# def c_32_L3_raf_props(ad, idx):
#     elems = idx["raf"]
#     ok,f=0,[]
#     for e in elems:
#         mats = ad.materials(e); dens = ad.material_density(e)
#         sl   = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         ant  = ad.pset(e,"Pset_CoveringCommon","Antistatic") or ad.pset(e,"Pset_CoveringCommon","FinishType")
#         if mats and sl and (dens or ad.is_panelized_system(e)): ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing material/density/service life"})
#     return mk_result("L3-3.2.1-01","RAF materials & SL",["3.2.1"],["IfcCovering","IfcPlate"],ok,len(elems),f)

# def c_32_L3_screed_props(ad, idx):
#     elems = idx["screed"]
#     ok,f=0,[]
#     for e in elems:
#         mats = ad.materials(e); dens = ad.material_density(e)
#         sl   = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         if mats and dens and sl: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing material/density/service life"})
#     return mk_result("L3-3.2.2-01","Screed materials & SL",["3.2.2"],["IfcCovering"],ok,len(elems),f)

# def c_32_L3_finish_props(ad, idx):
#     elems = idx["finishes"] + idx["finish_plates"]
#     ok,f=0,[]
#     for e in elems:
#         mats = ad.materials(e)
#         dens = ad.material_density(e)  # may be None for carpet; acceptable
#         sl   = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         voc  = ad.pset(e,"Pset_CoveringCommon","EmissivityClass") or ad.pset(e,"Pset_CoveringCommon","FinishType")
#         if mats and sl: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing materials/service life"})
#     return mk_result("L3-3.2.3-01","Finish materials & SL",["3.2.3"],["IfcCovering","IfcPlate"],ok,len(elems),f)


# def c_32_L4_hosting_relations(ad, idx):
#     # Every finish/screed should cover an internal floor slab or space
#     elems = idx["raf"] + idx["screed"] + idx["finishes"] + idx["finish_plates"]
#     ok,f=0,[]
#     for e in elems:
#         host = ad.covers_host(e) or ad.covers_space(e) or ad.attached_host(e)
#         if host and (host in idx["slabs_int"] or ad.is_internal_floor(host) or ad.covers_space(e)): ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No valid host (internal floor/space)"})
#     return mk_result("L4-3.2-01","Covers/host relations",["3.2"],["IfcCovering","IfcPlate"],ok,len(elems),f)

# def c_32_L4_raf_system_integrity(ad, idx):
#     # Raised access: panels present + pedestals/stringers modeled (if project models them)
#     has_panels = len(idx["raf"])>0
#     has_peds   = len(idx["raf_pedestals"])>0
#     ok = 1 if has_panels and (has_peds or ad.cfg("raf_allow_no_pedestals", False)) else 0
#     findings = [] if ok else [{"entity_guid":"-","entity_type":"IfcDiscreteAccessory","message":"No pedestals/stringers found"}]
#     return mk_result("L4-3.2.1-02","RAF system integrity",["3.2.1"],["IfcCovering","IfcPlate","IfcDiscreteAccessory"],ok_count=ok,total=1,findings=findings,kind="consistency")

# def c_32_L4_coverage_ratio(ad, idx, target=0.85):
#     # Floor finish coverage vs internal floor area
#     finA = sum((ad.qto_area(e) or ad.geom_area(e) or 0) for e in (idx["finishes"] + idx["raf"] + idx["finish_plates"]))
#     flA  = sum((ad.qto_area(s) or ad.geom_area(s) or 0) for s in idx["slabs_int"])
#     if flA<=0:
#         return mk_result("L4-3.2-03","Coverage ratio",["3.2"],["IfcCovering"],ok_count=1,total=1,findings=[],kind="consistency")
#     ratio = finA/max(flA,1e-6)
#     ok = ratio >= target
#     findings = [] if ok else [{"entity_guid":"-","entity_type":"-","message":f"coverage={ratio:.2f} (<{target})"}]
#     return mk_result("L4-3.2-03","Coverage ratio",["3.2"],["IfcCovering"],ok_count=1 if ok else 0,total=1,findings=findings,kind="consistency")


# def c_32_L5_raf_epd_reversibility(ad, idx):
#     elems = idx["raf"] + idx["raf_pedestals"]
#     ok,f=0,[]
#     for e in elems:
#         link = ad.epd_link(e) or ad.type_epd_link(e) or ad.material_mappable(e)
#         units_ok = ad.has_compatible_qto_unit(e, expect=("m2","kg","kg/m","pcs"))
#         sl = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         reversible = ad.has_realizing_fasteners(e) or ad.is_mechanically_fixed(e)  # demountable panels/pedestals
#         if link and units_ok and sl and reversible: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing EPD/unit/SL or not demountable"})
#     return mk_result("L5-3.2.1-01","RAF EPD & reversibility",["3.2.1"],["IfcCovering","IfcPlate","IfcDiscreteAccessory"],ok,len(elems),f)

# def c_32_L5_screed_epd(ad, idx):
#     elems = idx["screed"]
#     ok,f=0,[]
#     for e in elems:
#         link = ad.epd_link(e) or ad.type_epd_link(e) or ad.material_mappable(e)
#         units_ok = ad.has_compatible_qto_unit(e, expect=("m2","m3","kg"))
#         sl = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         # screed is usually bonded; reversibility not expected—don’t penalize for mechanical lack
#         if link and units_ok and sl: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing EPD/unit or service life"})
#     return mk_result("L5-3.2.2-01","Screed EPD readiness",["3.2.2"],["IfcCovering"],ok,len(elems),f)

# def c_32_L5_finishes_epd_reversibility(ad, idx):
#     elems = idx["finishes"] + idx["finish_plates"]
#     ok,f=0,[]
#     for e in elems:
#         link = ad.epd_link(e) or ad.type_epd_link(e) or ad.material_mappable(e)
#         units_ok = ad.has_compatible_qto_unit(e, expect=("m2","kg"))
#         sl = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         # demountable if click-lock/tiles on mechanical clips; bonded if adhesive/thinset
#         mech = ad.has_realizing_fasteners(e) or ad.is_mechanically_fixed(e) or ad.name_contains(e, ("click","floating"))
#         bonded = ad.name_contains(e, ("adhesive","glue","thinset","mastic"))
#         reversible = mech and not bonded
#         if link and units_ok and sl and reversible: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"EPD/unit/SL missing or not reversible"})
#     return mk_result("L5-3.2.3-01","Finishes EPD & reversibility",["3.2.3"],["IfcCovering","IfcPlate"],ok,len(elems),f)
