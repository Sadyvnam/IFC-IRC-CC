from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
from ifcopenshell import entity_instance
# 3.3 Ceiling finishes
def category_33(ad: CoreType):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "3.3"

    # 2) Ceiling finishes = IfcCovering with PredefinedType == CEILING
    ceiling_coverings:list[entity_instance] = []
    for cov in ad.by_types(["IfcCovering"]):
        if cov.id() in ad.parsedElIds:
            continue
        pdt = getattr(cov, "PredefinedType", None)
        if pdt == "CEILING":
            ceiling_coverings.append(cov)

    # 3) Aggregate + scoring
    agg: dict[tuple, CategoryRow] = {}

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

    for cov in ceiling_coverings:
        if cov.id() in ad.parsedElIds:
            continue
        scoped_elements.append(cov)

        pdt = getattr(cov, "PredefinedType", None)

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
        row.category_code = "3.3"
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

    # 4) Overview indicator scores
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
        {"3.3": scoped_elements},
        qto_by_category={"3.3": relevant_qto_types},
    )

    return out

# def c_33_L1_typed_classified(ad, idx):
#     elems = idx["coverings"] + idx["plates"] + idx["grid"] + idx["hangers"]
#     ok,f=0,[]
#     for e in elems:
#         typed = (hasattr(e,"PredefinedType") and str(getattr(e.get_info(),"PredefinedType"))!="NOTDEFINED") or e.is_a() in ("IfcPlate","IfcMember","IfcDiscreteAccessory","IfcMechanicalFastener")
#         cls   = ad.has_classification(e) or ad.has_classification(ad.type_of(e))
#         if typed and cls: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing type/classification"})
#     return mk_result("L1-3.3-01","Ceiling finishes typed & classified",["3.3"],["IfcCovering","IfcPlate","IfcMember","IfcDiscreteAccessory"],ok,len(elems),f)

# def c_33_L1_internal_host_resolvable(ad, idx):
#     elems = idx["coverings"] + idx["plates"]
#     ok,f=0,[]
#     for e in elems:
#         host = ad.covers_space(e) or ad.covers_host(e)
#         if host: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No space/host relation (internal)"})
#     return mk_result("L1-3.3-02","Internal host/space resolvable",["3.3"],["IfcCovering","IfcPlate"],ok,len(elems),f)


# def c_33_L2_finish_area_thickness(ad, idx):
#     elems = idx["coverings"]
#     ok,f=0,[]
#     for e in elems:
#         A = ad.qto_area(e) or ad.geom_area(e)
#         t = ad.layer_thickness(e) or ad.qto_value(e,"Thickness")
#         if A and A>0 and (t is None or t>=0): ok+=1  # allow paint-like thin layers
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing/zero area (or invalid thickness)"})
#     return mk_result("L2-3.3-01","Covering area/thickness",["3.3"],["IfcCovering"],ok,len(elems),f)

# def c_33_L2_panels_grid_hangers_qto(ad, idx):
#     ok,f=0,[]
#     for p in idx["plates"]:
#         A = ad.qto_area(p) or ad.geom_area(p)
#         if A and A>0: ok+=1
#         else: f.append({"entity_guid":p.GlobalId,"entity_type":p.is_a(),"message":"Panel area missing"})
#     for g in idx["grid"]:
#         L = ad.qto_length(g) or ad.geom_length_path(g)
#         if L and L>0: ok+=1
#         else: f.append({"entity_guid":g.GlobalId,"entity_type":g.is_a(),"message":"Grid length missing"})
#     for h in idx["hangers"]:
#         q = ad.qto_count(h) or 1
#         if q>=1: ok+=1
#         else: f.append({"entity_guid":h.GlobalId,"entity_type":h.is_a(),"message":"Hanger count missing"})
#     total = len(idx["plates"]) + len(idx["grid"]) + len(idx["hangers"])
#     return mk_result("L2-3.3-02","Panels/grid/hangers quantities",["3.3"],["IfcPlate","IfcMember","IfcDiscreteAccessory"],ok,total,f)


# def c_33_L3_materials_density_sl(ad, idx):
#     elems = idx["coverings"] + idx["plates"] + idx["grid"] + idx["hangers"]
#     ok,f=0,[]
#     for e in elems:
#         mats = ad.materials(e); dens = ad.material_density(e)
#         sl   = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         if mats and sl and (dens or e.is_a() in ("IfcMember","IfcDiscreteAccessory")):
#             ok+=1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing materials/density/service life"})
#     return mk_result("L3-3.3-01","Materials & service life",["3.3"],["IfcCovering","IfcPlate","IfcMember","IfcDiscreteAccessory"],ok,len(elems),f)

# def c_33_L3_acoustic_light_props(ad, idx):
#     elems = idx["coverings"] + idx["plates"]
#     ok,f=0,[]
#     for e in elems:
#         nrc = ad.pset(e,"Pset_Acoustic","SoundAbsorptionAverage") or ad.pset(e,"Pset_CoveringCommon","AcousticRating")
#         lr  = ad.pset(e,"Pset_Lighting","LightReflectance") or ad.pset(e,"Pset_CoveringCommon","Reflectance")
#         if nrc or lr: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No acoustic/light reflectance info"})
#     return mk_result("L3-3.3-02","Acoustic/reflectance props",["3.3"],["IfcCovering","IfcPlate"],ok,len(elems),f)


# def c_33_L4_covers_relations(ad, idx):
#     elems = idx["coverings"] + idx["plates"]
#     ok,f=0,[]
#     for e in elems:
#         ok_rel = ad.covers_space(e) or ad.has_rel_covers_bldg_elements(e)
#         if ok_rel: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No IfcRelCovers… relation"})
#     return mk_result("L4-3.3-01","Covers relation present",["3.3"],["IfcCovering","IfcPlate"],ok,len(elems),f)

# def c_33_L4_coverage_ratio(ad, idx, target=0.80):
#     # Ceiling coverage vs internal floor area (proxy); acceptable band for sloped/voided ceilings
#     flA = sum((ad.floor_area_of_space(sp) or 0) for sp in idx["spaces_int"])
#     ceilA = sum((ad.qto_area(e) or ad.geom_area(e) or 0) for e in (idx["coverings"] + idx["plates"]))
#     if flA <= 0:
#         return mk_result("L4-3.3-02","Coverage ratio",["3.3"],["IfcCovering"],ok_count=1,total=1,findings=[],kind="consistency")
#     ratio = ceilA / max(flA,1e-6)
#     ok = 0.6 <= ratio <= 1.2 if target is None else (ratio >= target)
#     findings = [] if ok else [{"entity_guid":"-","entity_type":"-","message":f"coverage={ratio:.2f}"}]
#     return mk_result("L4-3.3-02","Coverage ratio",["3.3"],["IfcCovering"],ok_count=1 if ok else 0,total=1,findings=findings,kind="consistency")


# def c_33_L5_epd_linkability(ad, idx):
#     elems = idx["coverings"] + idx["plates"] + idx["grid"] + idx["hangers"]
#     ok,f=0,[]
#     for e in elems:
#         link = ad.epd_link(e) or ad.type_epd_link(e) or ad.material_mappable(e)
#         # typical units: coverings/panels → m2 or kg; grid → kg or kg/m; hangers → kg or pcs
#         unit_ok = ad.has_compatible_qto_unit(e, expect=("m2","kg","kg/m","pcs"))
#         sl = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         if link and unit_ok and sl: ok+=1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing EPD/doc, unit hint, or service life"})
#     return mk_result("L5-3.3-01","EPD linkability (presence)",["3.3"],["IfcCovering","IfcPlate","IfcMember","IfcDiscreteAccessory"],ok,len(elems),f)

# def c_33_L5_reversibility(ad, idx):
#     # Suspended/grid ceilings should be demountable; fully bonded plaster skins are not
#     elems = idx["plates"] + idx["grid"] + idx["coverings"]
#     ok,f=0,[]
#     for e in elems:
#         mech = ad.has_realizing_fasteners(e) or ad.is_mechanically_fixed(e) or ad.name_contains(e, ("clip","grid","suspended"))
#         bonded = ad.name_contains(e, ("adhesive","bonded","skim","plaster skim")) or ad.pset(e,"Pset_Connection","Bonded") is True
#         if mech and not bonded: ok+=1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No mechanical fixing evidence (likely bonded)"})
#     total = len(elems) if elems else 1
#     return mk_result("L5-3.3-02","Reversibility (demountable)",["3.3"],["IfcCovering","IfcPlate","IfcMember"],ok,total,f)
