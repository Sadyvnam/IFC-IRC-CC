from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 4.6 Audio and visual
# all furniture needs to be improved not really deterministic.
def category_46(ad: CoreType):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "4.6"

    # deterministic only.
    include_types = [
        # Devices
        "IfcAudioVisualAppliance",   # IFC4+ (best)
    ]

    candidates = ad.by_types(include_types)

    agg: dict[str, CategoryRow] = {}

    n = 0
    n_pdt_ok = n_class_ok = n_class_fields_ok = 0
    n_shape_ok = n_qto_ok = 0
    n_common_ok = n_mat_ok = n_doc_ok = 0
    sum_l4a = 0.0
    relevant_qto_types = {"IfcQuantityCount", "IfcQuantityLength", "IfcQuantityArea", "IfcQuantityVolume"}
    scoped_elements = []

    for el in candidates:
        if(el.id() in ad.parsedElIds):
            continue
        scoped_elements.append(el)
        pdt = getattr(el, "PredefinedType", None)
        if hasattr(el, "PredefinedType") and ((pdt is None) or (pdt == "NOTDEFINED")):
            issue = IssueRow()
            issue.category_code = "4.6"
            issue.category_name = ""
            issue.ifc_class = el.is_a()
            issue.message = "Missing predefined type"
            out.issues.append(issue)

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

        # --- build row + aggregate ---
        row = CategoryRow()
        row.category_code = "4.6"
        row.category_name = ""
        row = ad.build_category_row(el, row)

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

    # overview scores
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
        {"4.6": scoped_elements},
        qto_by_category={"4.6": relevant_qto_types},
    )

    return out

# def c_46_L1_typed_classified(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         typed = (hasattr(e,"PredefinedType") and str(getattr(e.get_info(),"PredefinedType"))!="NOTDEFINED") or ad.has_type_def(e)
#         cls   = ad.has_classification(e) or ad.has_classification(ad.type_of(e))
#         if typed and cls: ok+=1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),
#                       "message":"Missing PredefinedType/Type or AV classification"})
#     return mk_result("L1-4.6-01","AV devices typed & classified",
#                       ["4.6"],["IfcAudioVisualAppliance","IfcFurnishingElement","IfcElectricAppliance"],ok,len(elems),f)

# def c_46_L1_internal_loc(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         if ad.has_spatial_container(e): ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No spatial container (internal location)"})
#     return mk_result("L1-4.6-02","Internal location resolvable",["4.6"],["Ifc*"],ok,len(elems),f)

# def c_46_L2_nameplate_props(ad, idx):
#     # Optional but helpful: projector lumens, speaker power/SPL, display diagonal
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         lum = ad.pset(e,"Pset_AudioVisualApplianceTypeProjector","LuminousFlux") or ad.name_contains(e, ("lumen","lm"))
#         spl = ad.pset(e,"Pset_AudioDevice","SoundPowerLevel") or ad.name_contains(e, ("w rms","spl"))
#         diag= ad.pset(e,"Pset_AudioVisualApplianceTypeDisplay","ScreenDiagonal") or ad.name_contains(e, ("inch","\"", "in "))
#         if lum or spl or diag: ok+=1
#     total = max(1,len(elems))
#     return mk_result("L2-4.6-02","Nameplate props (lumens/SPL/diagonal)",["4.6"],["Ifc*"],ok,total,[])


# def c_46_L3_service_life_trace(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         sl   = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         mref = ad.pset(e,"Pset_ManufacturerOccurrence","ModelReference") or ad.pset(e,"Pset_ManufacturerOccurrence","ArticleNumber")
#         # Materials are often meaningless for IT/AV casings; don’t require.
#         if sl: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing service life"})
#         if not (mref or ad.has_docref(e) or ad.has_docref(ad.type_of(e))):
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No manufacturer/model reference"})
#     return mk_result("L3-4.6-01","Service life (+trace)",["4.6"],["Ifc*"],ok,len(elems),f)

# def c_46_L3_perf_props(ad, idx):
#     # Optional: acoustic class for speakers/mics; brightness mode for projectors/displays
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         ac  = ad.pset(e,"Pset_AudioDevice","AcousticClass") or ad.name_contains(e, ("directional","cardioid","omni"))
#         br  = ad.pset(e,"Pset_AudioVisualApplianceTypeDisplay","Brightness") or ad.name_contains(e, ("nit","cd/m2"))
#         if ac or br: ok+=1
#     total = max(1,len(elems))
#     return mk_result("L3-4.6-02","Performance props (optional)",["4.6"],["Ifc*"],ok,total,[])


# def c_46_L4_system_membership_and_mounting(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         # AV often in AV or ELV systems; displays/projectors usually need Power + (optionally) Data/Control
#         in_sys = ad.in_distribution_system(e, "AV") or ad.in_distribution_system(e, "ELV") or ad.in_distribution_system(e, "DATA")
#         mounted = ad.has_realizing_fasteners(e) or ad.attached_host(e) or (e in idx["loose"])  # carts acceptable
#         contained = ad.has_spatial_container(e)
#         if in_sys and mounted and contained:
#             ok+=1
#         else:
#             if not in_sys: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Not in AV/ELV/DATA system"})
#             if not mounted: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No mounting/host (or loose status unclear)"})
#             if not contained: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No spatial container"})
#     return mk_result("L4-4.6-01","System membership & mounting/containment",["4.6"],["Ifc*"],ok,len(elems),f)

# def c_46_L4_mount_type_reasonable(ad, idx):
#     # Simple sanity: projectors/speakers should be ceiling/wall-mounted unless explicitly on carts;
#     # displays may be wall/ceiling or on stands.
#     ok,f=0,[]
#     for p in idx["projectors"] + idx["speakers"]:
#         host = ad.attached_host(p)
#         loose = p in idx["loose"]
#         if loose or (host and (host.is_a().startswith("IfcWall") or host.is_a().startswith("IfcSlab"))):
#             ok+=1
#         else:
#             f.append({"entity_guid":p.GlobalId,"entity_type":p.is_a(),"message":"Mounting type unusual for projector/speaker"})
#     total = max(1, len(idx["projectors"]) + len(idx["speakers"]))
#     return mk_result("L4-4.6-02","Mount type reasonable (proj/speaker)",["4.6"],["Ifc*"],ok,total,f)


# def c_46_L5_epd_and_reuse(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         link = ad.epd_link(e) or ad.type_epd_link(e) or ad.material_mappable(e)
#         units_ok = ad.has_compatible_qto_unit(e, expect=("pcs","kg"))
#         sl = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         # AV is typically demountable (brackets/rails) or loose (carts)
#         demount = ad.has_realizing_fasteners(e) or ad.bolted_connection(e) or (e in idx["loose"])
#         if link and units_ok and sl and demount:
#             ok+=1
#         else:
#             msg=[]
#             if not link: msg.append("no EPD/doc link")
#             if not units_ok: msg.append("no compatible unit")
#             if not sl: msg.append("no service life")
#             if not demount: msg.append("not demountable/reusable")
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"; ".join(msg)})
#     return mk_result("L5-4.6-01","EPD linkability & reuse",["4.6"],["Ifc*"],ok,len(elems),f)

# def c_46_L5_asset_traceability(ad, idx):
#     # Presence-only: serial/model fields enable refurb/resale
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         sn = ad.pset(e,"Pset_Asset","SerialNumber") or ad.pset(e,"Pset_ManufacturerOccurrence","ArticleNumber")
#         if sn: ok+=1
#     total = max(1,len(elems))
#     return mk_result("L5-4.6-02","Asset traceability (serial/model)",["4.6"],["Ifc*"],ok,total,[])
