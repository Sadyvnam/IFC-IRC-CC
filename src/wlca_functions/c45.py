from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 4.5 IT
def category_45(ad: CoreType):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview=IndicatorRow()
    out.overview.category="4.5"
    #  deterministic only.
    include_types = [
        # Devices
        "IfcCommunicationAppliance",
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
            issue.category_code = "4.5"
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
        row.category_code = "4.5"
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
        {"4.5": scoped_elements},
        qto_by_category={"4.5": relevant_qto_types},
    )

    return out

# def c_45_L1_typed_classified(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         typed = (hasattr(e,"PredefinedType") and str(getattr(e.get_info(),"PredefinedType"))!="NOTDEFINED") or ad.has_type_def(e)
#         cls   = ad.has_classification(e) or ad.has_classification(ad.type_of(e))
#         if typed and cls: ok+=1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),
#                       "message":"Missing PredefinedType/Type or IT classification"})
#     return mk_result("L1-4.5-01","IT devices typed & classified",["4.5"],
#                       ["IfcCommunicationsAppliance","IfcFurnishingElement","IfcElectricAppliance"],ok,len(elems),f)

# def c_45_L1_internal_loc(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         if ad.has_spatial_container(e): ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No spatial container (internal location)"})
#     return mk_result("L1-4.5-02","Internal location resolvable",["4.5"],["Ifc*"],ok,len(elems),f)


# def c_45_L2_rack_u_or_mount_info(ad, idx):
#     # If it's a rack device or server/switch, look for U-size or mounting hint (optional pass)
#     elems = idx["servers"] + idx["switches"]
#     if not elems:
#         return mk_result("L2-4.5-02","Rack U/mount info (if applicable)",["4.5"],["Ifc*"],ok_count=1,total=1,findings=[],kind="consistency")
#     ok,f=0,[]
#     for e in elems:
#         U = ad.pset(e,"Pset_CommunicationsApplianceTypeCommon","RackUnitHeight") or ad.pset(e,"Pset_Asset","NominalHeightUnits")
#         mount = ad.name_contains(e, ("1u","2u","3u","rackmount","rack-mount","19\""))
#         if U or mount: ok+=1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No rack U-size/mount info"})
#     return mk_result("L2-4.5-02","Rack U/mount info (if applicable)",["4.5"],["Ifc*"],ok,len(elems),f)


# def c_45_L3_materials_service_life_trace(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         mats = ad.materials(e)  # may be coarse; still accept
#         sl   = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         mref = ad.pset(e,"Pset_ManufacturerOccurrence","ModelReference") or ad.pset(e,"Pset_ManufacturerOccurrence","ArticleNumber")
#         if (mats or True) and sl:  # allow missing detailed materials; keep SL required
#             ok+=1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing service life (materials optional)"})
#         if not (mref or ad.has_docref(e) or ad.has_docref(ad.type_of(e))):
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No manufacturer/model reference"})
#     return mk_result("L3-4.5-01","Service life (+trace; materials optional)",["4.5"],["Ifc*"],ok,len(elems),f)

# def c_45_L3_nameplate_power_network(ad, idx):
#     # Presence of rated power or PoE + network capability hints
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         pwr = ad.pset(e,"Pset_ElectricalDeviceCommon","RatedPowerInput") or ad.pset(e,"Pset_ElectricalDeviceCommon","InputVoltage")
#         poe = ad.name_contains(e, ("poe","power over ethernet"))
#         lan = ad.pset(e,"Pset_CommunicationsApplianceTypeCommon","NetworkInterface") or ad.name_contains(e, ("ethernet","lan","wifi","wireless"))
#         if pwr or poe or lan: ok+=1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No power/network nameplate hints"})
#     return mk_result("L3-4.5-02","Nameplate: power/network",["4.5"],["Ifc*"],ok,len(elems),f)


# def c_45_L4_system_membership_and_mounting(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         # Expect ELV/DATA system membership for IT; APs may be only ELV/PoE.
#         in_sys = ad.in_distribution_system(e, "DATA") or ad.in_distribution_system(e, "ELV")
#         mounted = ad.has_realizing_fasteners(e) or ad.attached_host(e) or (e in idx["loose"])  # loose desktop devices acceptable
#         contained = ad.has_spatial_container(e)
#         if in_sys and mounted and contained:
#             ok+=1
#         else:
#             if not in_sys:
#                 f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Not in ELV/DATA system"})
#             if not mounted:
#                 f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No mounting or loose routing unclear"})
#             if not contained:
#                 f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No spatial container"})
#     return mk_result("L4-4.5-01","In ELV/DATA system & mounting/containment",["4.5"],["Ifc*"],ok,len(elems),f)

# def c_45_L4_rack_affiliation(ad, idx):
#     # Servers/switches should be in/attached to a rack or cabinet (if racks exist).
#     elems = idx["servers"] + idx["switches"]
#     if not elems or not idx["racks"]:
#         return mk_result("L4-4.5-02","Rack affiliation (if racks present)",["4.5"],["Ifc*"],ok_count=1,total=1,findings=[],kind="consistency")
#     ok,f=0,[]
#     for e in elems:
#         host = ad.attached_host(e) or ad.aggregated_parent(e)
#         in_rack = host in idx["racks"] or ad.name_contains(host, ("rack","cabinet","enclosure")) if host else False
#         if in_rack: ok+=1
#         else:
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Not affiliated with a rack/cabinet"})
#     return mk_result("L4-4.5-02","Rack affiliation (if applicable)",["4.5"],["Ifc*"],ok,len(elems),f)


# def c_45_L5_epd_and_reuse(ad, idx):
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         link = ad.epd_link(e) or ad.type_epd_link(e) or ad.material_mappable(e)
#         units_ok = ad.has_compatible_qto_unit(e, expect=("pcs","kg"))
#         sl = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         # Reuse: rack/desk devices typically demountable (screws/rails) or inherently loose
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
#     return mk_result("L5-4.5-01","EPD linkability & reuse",["4.5"],["Ifc*"],ok,len(elems),f)

# def c_45_L5_it_asset_traceability(ad, idx):
#     # Presence-only: serial/asset tag fields to enable circularity (refurb/resale)
#     elems = idx["elems"]; ok,f=0,[]
#     for e in elems:
#         sn = ad.pset(e,"Pset_Asset","SerialNumber") or ad.pset(e,"Pset_ManufacturerOccurrence","ArticleNumber")
#         if sn: ok+=1
#     total = max(1,len(elems))
#     return mk_result("L5-4.5-02","IT asset traceability (serial/asset tag)",["4.5"],["Ifc*"],ok,total,[])
