from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics

# THIS IS ALSO EXPLORATORY
# 5.1.1 Sanitaryware
def category_511(ad: CoreType, idx: PreIndex):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "5.1.1"

    # Deterministic scope
    elements = list(ad.by_types(["IfcSanitaryTerminal"]))
    # elements += list(ad.by_types(["IfcWasteTerminal"]))

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

    relevant_qto_types = {"IfcQuantityCount", "IfcQuantityLength", "IfcQuantityVolume"}
    scoped_elements = []

    for el in elements:
        if el.id() in ad.parsedElIds:
            continue
        scoped_elements.append(el)

        ifc_class = el.is_a()
        pdt = getattr(el, "PredefinedType", None)

        # --- QA issues (deterministic) ---
        if (pdt is None) or (pdt == "NOTDEFINED"):
            issue = IssueRow()
            issue.category_code = "5.1.1"
            issue.category_name = ""
            issue.ifc_class = ifc_class
            issue.message = "Missing predefined type (IfcSanitaryTerminal.PredefinedType)"
            out.issues.append(issue)

        # --- scoring (element included) ---
        n += 1
        sum_l4a += ad.parse_element_EII(el)["score"]
        if ad._valid_predefined_type(el):
            n_pdt_ok += 1
        if ad._has_classification_ref(el):
            n_class_ok += 1
        if ad._classification_required_fields_non_null(el):
            n_class_fields_ok += 1

        if ad._has_shape_representation(el):
            n_shape_ok += 1
        if ad._has_relevant_qto(el, relevant_qto_types):
            n_qto_ok += 1

        common = ad.get_element_common_pset(el)
        if common is not None:
            n_common_pset_ok += 1

        if ad._has_material_association(el):
            n_mat_ok += 1
        if ad._has_document_association(el):
            n_doc_ok += 1

        # --- build + aggregate ---
        row = CategoryRow()
        row.category_code = "5.1.1"
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

    # --- compute weighted overview ---
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
        {"5.1.1": scoped_elements},
        qto_by_category={"5.1.1": relevant_qto_types},
    )

    return out


# # fix elements to actually look for relevant ifc elements for this classification.
# def c_511_L1_typed_classified(ad: CoreType, idx:PreIndex):
#     # ["IfcSanitaryTerminal","IfcFlowTerminal"]
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         typed = ad.has_type_def(e)
#         cls = ad.has_classification(e)
#         if typed and cls: ok += 1
#         else: f.append({"entity_guid": e.GlobalId, "entity_type": e.is_a(),
#                         "message": "Missing Type and/or classification"})
#     return mk_result("L1-5.1.1-01","Sanitary terminals typed & classified",
#                      ["5.1.1"],["IfcSanitaryTerminal","IfcFlowTerminal"], ok, len(elems), f)

# def c_511_L1_kind_resolvable(ad: CoreType, idx:PreIndex):
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         pdt = str(getattr(e,"PredefinedType", "")).upper()
#         has_kind = pdt not in ("","NOTDEFINED","USERDEFINED") or True  # name fallback via _kind in preindex
#         if has_kind: ok += 1
#         else: f.append({"entity_guid": e.GlobalId, "entity_type": e.is_a(), "message":"Fixture kind not resolvable"})
#     return mk_result("L1-5.1.1-02","Fixture kind resolvable",["5.1.1"],["IfcSanitaryTerminal"], ok, len(elems), f)

# def c_511_L2_dims_and_count(ad: CoreType, idx:PreIndex):
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         pcs = ad.qto_value(e, "Count") or 1
#         h = ad.qto_value(e,"OverallHeight") or getattr(e,"OverallHeight", None)
#         w = ad.qto_value(e,"OverallWidth")  or getattr(e,"OverallWidth",  None)
#         d = ad.qto_value(e,"OverallDepth")
#         dims = sum(1 for v in (h,w,d) if v not in (None,0))
#         if pcs>=1 and dims>=2: ok += 1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Missing pcs or ≥2 dims"})
#     return mk_result("L2-5.1.1-01","Quantities & ≥2 dims",["5.1.1"],["IfcSanitaryTerminal"], ok, len(elems), f)

# def c_511_L2_ports_or_flows(ad: CoreType, idx:PreIndex):
#     # accept either ports with expected kinds OR basic flow properties by pset
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         ports = set(ad.port_kinds(e))
#         has_ports = ("Water" in ports) or ("Waste" in ports)
#         flush = ad.pset(e,"Pset_SanitaryTerminalTypeWC","FlushRate") or ad.pset(e,"Pset_SanitaryTerminalTypeWC","FlushVolume")
#         flow  = ad.pset(e,"Pset_SanitaryTerminalTypeCommon","NominalFlowRate")
#         if has_ports or flush or flow: ok += 1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No ports or flow props"})
#     return mk_result("L2-5.1.1-02","Ports (water/waste) or flow props",["5.1.1"],["IfcSanitaryTerminal"], ok, len(elems), f)


# def c_511_L3_materials_and_density(ad: CoreType, idx:PreIndex):
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         mats = ad.materials(e)
#         dens = ad.material_density(e)
#         if mats and dens: ok += 1
#         else: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No materials or density"})
#     return mk_result("L3-5.1.1-01","Materials + density",["5.1.1"],["IfcSanitaryTerminal"], ok, len(elems), f)

# def c_511_L3_service_life_and_efficiency(ad: CoreType, idx:PreIndex):
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         sl  = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         eff = ad.pset(e,"Pset_SanitaryTerminalTypeWC","FlushVolume") or \
#               ad.pset(e,"Pset_SanitaryTerminalTypeCommon","NominalFlowRate")
#         if sl and eff: ok += 1
#         else:
#             msg = []
#             if not sl:  msg.append("no service life")
#             if not eff: msg.append("no efficiency/flow data")
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":", ".join(msg)})
#     return mk_result("L3-5.1.1-02","Service life + efficiency/flow",["5.1.1"],["IfcSanitaryTerminal"], ok, len(elems), f)

# def c_511_L4_system_connectivity(ad: CoreType, idx:PreIndex):
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         wtr = ad.in_distribution_system(e,"WATER") or ad.in_distribution_system(e,"DOMESTIC") \
#               or ad.in_distribution_system(e,"COLD") or ad.in_distribution_system(e,"HOT")
#         wst = ad.in_distribution_system(e,"WASTE") or ad.in_distribution_system(e,"DRAIN") \
#               or ad.in_distribution_system(e,"FOUL") or ad.in_distribution_system(e,"SANITARY")
#         cont = ad.has_spatial_container(e)
#         if wst and cont and (wtr or "URINAL" in str(getattr(e,"PredefinedType","")).upper() or "WC" in str(getattr(e,"PredefinedType","")).upper()):
#             ok += 1
#         else:
#             if not wst: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"Not in drainage/sanitary system"})
#             if not cont: f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"No spatial container"})
#     return mk_result("L4-5.1.1-01","System connectivity (drainage + container)",["5.1.1"],["IfcSanitaryTerminal"], ok, len(elems), f)

# def c_511_L4_room_placement_reasonable(ad: CoreType, idx:PreIndex):
#     # optional sanity: fixture in a sanitary room (name tokens)
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         sp = ad.spatial_container(e)
#         nm = ((getattr(sp,"Name","") or "") + " " + (getattr(sp,"LongName","") or "")).lower() if sp else ""
#         if sp and any(t in nm for t in ("toilet","wc","bath","shower","sanitary","restroom","washroom","bathroom","cloakroom","ensuite")):
#             ok += 1
#     tot = max(1, len(elems))
#     return mk_result("L4-5.1.1-02","Located in sanitary spaces (heuristic)",["5.1.1"],["IfcSpace"], ok, tot, [])

# def c_511_L5_epd_and_units(ad: CoreType, idx:PreIndex):
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         link = ad.epd_link(e) or ad.type_epd_link(e) or ad.material_mappable(e)
#         units_ok = ad.has_compatible_qto_unit(e, expect=("pcs","kg"))
#         sl = ad.pset(e,"Pset_ServiceLife","ReferenceServiceLife")
#         if link and units_ok and sl:
#             ok += 1
#         else:
#             msg=[]
#             if not link: msg.append("no EPD/doc/material mapping")
#             if not units_ok: msg.append("no compatible units (pcs/kg)")
#             if not sl: msg.append("no service life")
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"; ".join(msg)})
#     return mk_result("L5-5.1.1-01","EPD linkability + units + SL",["5.1.1"],["IfcSanitaryTerminal"], ok, len(elems), f)

# def c_511_L5_demount_and_trace(ad: CoreType, idx:PreIndex):
#     elems = idx["elems"]; ok, f = 0, []
#     for e in elems:
#         demount = getattr(ad, "has_realizing_fasteners", lambda *_: False)(e) or \
#                   getattr(ad, "attached_host", lambda *_: None)(e) is not None
#         trace = ad.pset(e,"Pset_ManufacturerOccurrence","ModelReference") or ad.pset(e,"Pset_Asset","SerialNumber")
#         if demount and trace: ok += 1
#         else:
#             msg=[]
#             if not demount: msg.append("not clearly demountable/hosted")
#             if not trace: msg.append("no model/serial reference")
#             f.append({"entity_guid":e.GlobalId,"entity_type":e.is_a(),"message":"; ".join(msg)})
#     return mk_result("L5-5.1.1-02","Demountability + asset trace",["5.1.1"],["IfcSanitaryTerminal"], ok, len(elems), f)
