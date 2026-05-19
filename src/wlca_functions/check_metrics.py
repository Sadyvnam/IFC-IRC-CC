from __future__ import annotations
from ifcopenshell import entity_instance
from dataclasses import asdict
from typing import Any, Callable, Iterable, Optional
from src.utils import CoreType
from src.excel.types import CheckMetric, IndicatorRow


LEVEL_WEIGHTS: dict[str, dict[str, float]] = {
    "L1": {
        "l1_identified": 0.30,
        "l1_predefined_type": 0.20,
        "l1_type_object": 0.15,
        "l1_classification_ref": 0.25,
        "l1_classification_fields": 0.10,
    },
    "L2": {
        "l2_shape_representation": 0.25,
        "l2_quantity_available": 0.35,
        "l2_quantity_value_positive": 0.25,
        "l2_functional_unit_compatible": 0.15,
    },
    "L3": {
        "l3_material_association": 0.25,
        "l3_material_density_or_layer": 0.25,
        "l3_common_property_set": 0.15,
        "l3_document_reference": 0.15,
        "l3_service_life": 0.20,
    },
    "L4a": {
        "l4a_environmental_impact_property": 0.25,
        "l4a_gwp_value": 0.25,
        "l4a_element_or_type_epd_reference": 0.25,
        "l4a_epd_quantity_basis_usable": 0.15,
        "l4a_material_external_reference": 0.10,
    },
    "L4b": {
        "l4b_manufacturer_present": 0.25,
        "l4b_product_identifier_present": 0.25,
        "l4b_reversible_without_damage_signal": 0.20,
        "l4b_realizing_connection_element": 0.15,
        "l4b_connection_relationship": 0.10,
        "l4b_system_membership": 0.05,
    },
}

CHECK_TITLES: dict[str, str] = {
    "l1_identified": "In category scope",
    "l1_predefined_type": "Predefined type usable",
    "l1_type_object": "Type object assigned",
    "l1_classification_ref": "Classification reference present",
    "l1_classification_fields": "Classification fields usable",
    "l2_shape_representation": "Shape representation present",
    "l2_quantity_available": "Relevant quantity available",
    "l2_quantity_value_positive": "Quantity is positive",
    "l2_functional_unit_compatible": "Functional unit basis usable",
    "l3_material_association": "Material association present",
    "l3_material_density_or_layer": "Material detail available",
    "l3_common_property_set": "Common property set present",
    "l3_document_reference": "Document reference present",
    "l3_service_life": "Service life present",
    "l4a_environmental_impact_property": "Environmental impact property present",
    "l4a_gwp_value": "Explicit GWP value present",
    "l4a_element_or_type_epd_reference": "Element/type EPD reference present",
    "l4a_epd_quantity_basis_usable": "EPD mapping quantity available",
    "l4a_material_external_reference": "Material external reference present",
    "l4b_manufacturer_present": "Manufacturer present",
    "l4b_product_identifier_present": "Product identifier present",
    "l4b_connection_relationship": "Direct connection modeled",
    "l4b_system_membership": "System/group membership present",
    "l4b_realizing_connection_element": "Connection element modeled",
    "l4b_mechanical_fastener": "Mechanical fastener modeled",
    "l4b_reversible_without_damage_signal": "Reversible fastener cue",
}

CHECK_DEFINITIONS: dict[str, dict[str, str]] = {
    "l1_identified": {
        "what": "Checks whether elements were included in the deterministic scope for this category.",
        "evidence": "Element is routed into the category by the active category logic.",
        "not_evidence": "Free-text labels that merely sound similar to the category.",
    },
    "l1_predefined_type": {
        "what": "Checks whether the IFC predefined type is available and usable.",
        "evidence": "A populated PredefinedType that is not NOTDEFINED where the attribute exists.",
        "not_evidence": "Object names or descriptions used as a substitute for PredefinedType.",
    },
    "l1_type_object": {
        "what": "Checks whether the occurrence has an assigned IFC type object.",
        "evidence": "An explicit type-definition relationship.",
        "not_evidence": "Repeated object names without a type relationship.",
    },
    "l1_classification_ref": {
        "what": "Checks whether the element has an explicit classification reference.",
        "evidence": "IfcRelAssociatesClassification or equivalent explicit classification association.",
        "not_evidence": "Classification-like words in names or descriptions.",
    },
    "l1_classification_fields": {
        "what": "Checks whether required classification fields are populated enough to be useful.",
        "evidence": "Usable classification source, name, code, or equivalent explicit fields.",
        "not_evidence": "Blank or placeholder classification fields.",
    },
    "l2_shape_representation": {
        "what": "Checks whether model geometry exists for the element.",
        "evidence": "An explicit shape representation.",
        "not_evidence": "Quantities alone without modeled shape evidence.",
    },
    "l2_quantity_available": {
        "what": "Checks whether a relevant quantity exists for the category.",
        "evidence": "Area, volume, length, count, mass, or another configured quantity type. Pipe/duct common pset dimensions can also count as dimensional quantity evidence.",
        "not_evidence": "Text fields that describe size without a quantity value.",
    },
    "l2_quantity_value_positive": {
        "what": "Checks whether at least one relevant quantity is numeric and greater than zero.",
        "evidence": "Positive numeric quantity values, including accepted pipe/duct common pset dimensions.",
        "not_evidence": "Zero, blank, nonnumeric, or failed quantity values.",
    },
    "l2_functional_unit_compatible": {
        "what": "Checks whether the element has a quantity basis usable for WLCA mapping.",
        "evidence": "Configured units such as m2, m3, kg, m, or pcs. For pipe/duct common psets, length-like properties can support an m-based quantity basis.",
        "not_evidence": "A quantity with no usable unit basis.",
    },
    "l3_material_association": {
        "what": "Checks whether material evidence is associated to the element or type.",
        "evidence": "Explicit IFC material association.",
        "not_evidence": "Material-like words in object or type names.",
    },
    "l3_material_density_or_layer": {
        "what": "Checks whether material detail is rich enough for downstream assessment.",
        "evidence": "Density, material layers, layer thickness, constituents, or equivalent explicit detail.",
        "not_evidence": "A material name alone.",
    },
    "l3_common_property_set": {
        "what": "Checks whether the relevant common property set exists.",
        "evidence": "A recognized common property set on the occurrence or type.",
        "not_evidence": "Unstructured notes or arbitrary labels.",
    },
    "l3_document_reference": {
        "what": "Checks whether explicit document evidence is associated.",
        "evidence": "Document associations on the element or type.",
        "not_evidence": "A document title typed into a description field.",
    },
    "l3_service_life": {
        "what": "Checks whether service-life evidence is present.",
        "evidence": "ReferenceServiceLife in Pset_ServiceLife or equivalent explicit property.",
        "not_evidence": "Assumed design life based on category.",
    },
    "l4a_environmental_impact_property": {
        "what": "Checks whether environmental impact properties are present.",
        "evidence": "Pset_EnvironmentalImpactIndicators or equivalent explicit property set.",
        "not_evidence": "Material names interpreted as environmental evidence.",
    },
    "l4a_gwp_value": {
        "what": "Checks whether an explicit carbon or GWP value is present.",
        "evidence": "GWP, GlobalWarmingPotential, ClimateChange, EmbodiedCarbon, or CO2e values.",
        "not_evidence": "A linked document without an explicit value in the checked fields.",
    },
    "l4a_element_or_type_epd_reference": {
        "what": "Checks whether the element or type has explicit environmental reference evidence.",
        "evidence": "Document, external, or classification association on the element or type.",
        "not_evidence": "Name-token matching for EPD-like wording.",
    },
    "l4a_epd_quantity_basis_usable": {
        "what": "Checks whether environmental reference evidence has a usable quantity basis for mapping.",
        "evidence": "Environmental reference evidence plus a compatible quantity unit.",
        "not_evidence": "A claim that the IFC proves the EPD declared unit is identical.",
    },
    "l4a_material_external_reference": {
        "what": "Checks whether associated material evidence has an external reference.",
        "evidence": "External, document, classification, or library references on associated material entities.",
        "not_evidence": "Material-name matching or treating every material reference as EPD proof.",
    },
    "l4b_manufacturer_present": {
        "what": "Checks whether product traceability includes manufacturer information.",
        "evidence": "Manufacturer in occurrence/type manufacturer property sets or equivalent explicit fields.",
        "not_evidence": "Manufacturer inferred from object naming conventions.",
    },
    "l4b_product_identifier_present": {
        "what": "Checks whether product traceability includes a product identifier.",
        "evidence": "ModelReference, ArticleNumber, GTIN, SerialNumber, BarCode, or equivalent explicit identifier.",
        "not_evidence": "A product-like object name without an identifier field.",
    },
    "l4b_connection_relationship": {
        "what": "Checks whether direct element-to-element connection relationships are modeled.",
        "evidence": "IfcRelConnectsElements, IfcRelConnectsPathElements, or IfcRelConnectsWithRealizingElements.",
        "not_evidence": "Spatial containment, host/fill relations such as IfcRelFillsElement, or port-to-port connections.",
    },
    "l4b_system_membership": {
        "what": "Checks whether the element belongs to an explicit system or group.",
        "evidence": "IfcRelAssignsToGroup where the group is IfcSystem or IfcDistributionSystem.",
        "not_evidence": "Generic building-storey containment.",
    },
    "l4b_realizing_connection_element": {
        "what": "Checks whether a connection relationship has a modeled realizing element.",
        "evidence": "IfcRelConnectsWithRealizingElements with at least one realizing element.",
        "not_evidence": "A direct connection relationship without a realizing element.",
    },
    "l4b_mechanical_fastener": {
        "what": "Checks whether any realizing connection element is modeled as a mechanical fastener.",
        "evidence": "A realizing element explicitly typed as IfcMechanicalFastener.",
        "not_evidence": "Fastener-like words in names or descriptions.",
    },
    "l4b_reversible_without_damage_signal": {
        "what": "Checks for the strict reversible-without-damage cue currently accepted by the report.",
        "evidence": "All direct relevant realizing elements are explicitly IfcMechanicalFastener.",
        "not_evidence": "Adhesive, welded, unknown, or untyped realizing elements.",
    },
}

QTO_NAMES = (
    "NetVolume", "GrossVolume", "Volume",
    "NetArea", "GrossArea", "Area",
    "Length", "NetLength", "GrossLength",
    "Mass", "Weight", "Count",
    "CrossSectionArea",
)

PRODUCT_ID_PROPS = (
    "ModelReference",
    "ArticleNumber",
    "GlobalTradeItemNumber",
    "SerialNumber",
    "BarCode",
)

MANUFACTURER_PSETS = (
    "Pset_ManufacturerOccurrence",
    "Pset_ManufacturerTypeInformation",
)

MEP_COMMON_DIMENSION_PSETS = (
    "Pset_PipeSegmentCommon",
    "Pset_PipeSegmentTypeCommon",
    "Pset_PipeFittingCommon",
    "Pset_PipeFittingTypeCommon",
    "Pset_DuctSegmentCommon",
    "Pset_DuctSegmentTypeCommon",
    "Pset_DuctFittingCommon",
    "Pset_DuctFittingTypeCommon",
)

MEP_COMMON_LENGTH_PROPS = (
    "Length",
    "NetLength",
    "GrossLength",
    "NominalLength",
    "SegmentLength",
)

MEP_COMMON_DIMENSION_PROPS = MEP_COMMON_LENGTH_PROPS + (
    "NominalDiameter",
    "Diameter",
    "InnerDiameter",
    "OuterDiameter",
    "InsideDiameter",
    "OutsideDiameter",
    "NominalWidth",
    "NominalHeight",
    "Width",
    "Height",
)


def extend_report_metrics(report, category_return) -> None:
    report.check_metrics.extend(getattr(category_return, "check_metrics", []))


def metric(category: str, level: str, check: str, elements: Iterable[entity_instance],
           predicate: Callable[[entity_instance], bool],
           applicable: Optional[Callable[[entity_instance], bool]] = None) -> CheckMetric:
    elems = list(elements)
    if not elems:
        return CheckMetric(
            category=category,
            level=level,
            check=check,
            title=CHECK_TITLES.get(check, check),
            empty_scope=True,
        )

    scoped = [e for e in elems if applicable(e)] if applicable else elems
    if not scoped:
        return CheckMetric(
            category=category,
            level=level,
            check=check,
            title=CHECK_TITLES.get(check, check),
            empty_scope=True,
        )

    present = 0
    for e in scoped:
        try:
            if predicate(e):
                present += 1
        except Exception:
            pass

    total = len(scoped)
    return CheckMetric(
        category=category,
        level=level,
        check=check,
        title=CHECK_TITLES.get(check, check),
        present=present,
        total=total,
        pct=present / total if total else None,
        empty_scope=False,
    )


def build_category_metrics(
    ad:CoreType,
    category: str,
    elements: Iterable[entity_instance],
    relevant_qto_types: set[str] | None = None,
    expect_units: tuple[str, ...] = ("m2", "m3", "kg", "m", "pcs"),
) -> list[CheckMetric]:
    elems = list(elements)
    relevant_qto_types = relevant_qto_types or {
        "IfcQuantityArea",
        "IfcQuantityVolume",
        "IfcQuantityLength",
        "IfcQuantityCount",
        "IfcQuantityWeight",
    }

    return [
        metric(category, "L1", "l1_identified", elems, lambda e: True),
        metric(category, "L1", "l1_predefined_type", elems, lambda e: ad._valid_predefined_type(e), _has_predefined_attr),
        metric(category, "L1", "l1_type_object", elems, lambda e: ad.has_type_def(e)),
        metric(category, "L1", "l1_classification_ref", elems, lambda e: ad._has_classification_ref(e)),
        metric(category, "L1", "l1_classification_fields", elems, lambda e: ad._classification_required_fields_non_null(e)),
        metric(category, "L2", "l2_shape_representation", elems, lambda e: ad._has_shape_representation(e)),
        metric(category, "L2", "l2_quantity_available", elems, lambda e: _has_quantity_available(ad, e, relevant_qto_types)),
        metric(category, "L2", "l2_quantity_value_positive", elems, lambda e: _has_positive_quantity_value(ad, e)),
        metric(category, "L2", "l2_functional_unit_compatible", elems, lambda e: _has_functional_quantity_basis(ad, e, expect_units)),
        metric(category, "L3", "l3_material_association", elems, lambda e: ad._has_material_association(e)),
        metric(category, "L3", "l3_material_density_or_layer", elems, lambda e: _has_material_detail(ad, e)),
        metric(category, "L3", "l3_common_property_set", elems, lambda e: ad.get_element_common_pset(e) is not None),
        metric(category, "L3", "l3_document_reference", elems, lambda e: _has_document_reference(ad, e)),
        metric(category, "L3", "l3_service_life", elems, lambda e: _has_service_life(ad, e)),
        metric(category, "L4a", "l4a_environmental_impact_property", elems, lambda e: _has_environmental_pset(ad, e)),
        metric(category, "L4a", "l4a_gwp_value", elems, lambda e: _has_gwp_value(ad, e)),
        metric(category, "L4a", "l4a_element_or_type_epd_reference", elems, lambda e: _has_element_or_type_environmental_reference(ad, e)),
        metric(category, "L4a", "l4a_epd_quantity_basis_usable", elems, lambda e: _has_element_or_type_environmental_reference(ad, e) and ad.has_compatible_qto_unit(e, expect_units)),
        metric(category, "L4a", "l4a_material_external_reference", elems, lambda e: _has_material_external_reference(ad, e)),
        metric(category, "L4b", "l4b_manufacturer_present", elems, lambda e: _has_manufacturer(ad, e)),
        metric(category, "L4b", "l4b_product_identifier_present", elems, lambda e: _has_product_identifier(ad, e)),
        metric(category, "L4b", "l4b_connection_relationship", elems, lambda e: bool(_direct_element_connections(e))),
        metric(category, "L4b", "l4b_system_membership", elems, lambda e: _has_system_membership(e)),
        metric(category, "L4b", "l4b_realizing_connection_element", elems, lambda e: bool(_realizing_elements(e))),
        metric(category, "L4b", "l4b_mechanical_fastener", elems, lambda e: any(_is_mechanical_fastener(r) for r in _realizing_elements(e))),
        metric(category, "L4b", "l4b_reversible_without_damage_signal", elems, lambda e: _all_realizing_are_mechanical(e)),
    ]


def apply_metrics_to_overview(overview: IndicatorRow, metrics: Iterable[CheckMetric]) -> None:
    by_level: dict[str, dict[str, CheckMetric]] = {}
    for m in metrics:
        by_level.setdefault(m.level, {})[m.check] = m

    overview.l1_score = _weighted_score(by_level.get("L1", {}), LEVEL_WEIGHTS["L1"])
    overview.l2_score = _weighted_score(by_level.get("L2", {}), LEVEL_WEIGHTS["L2"])
    overview.l3_score = _weighted_score(by_level.get("L3", {}), LEVEL_WEIGHTS["L3"])
    overview.l4a_score = _weighted_score(by_level.get("L4a", {}), LEVEL_WEIGHTS["L4a"])
    overview.l4b_score = _weighted_score(by_level.get("L4b", {}), LEVEL_WEIGHTS["L4b"])


def finalize_category_metrics(ad:CoreType, out, category_to_elements: dict[str, list[entity_instance]],
                              qto_by_category: Optional[dict[str, set[str]]] = None,
                              units_by_category: Optional[dict[str, tuple[str, ...]]] = None) -> None:
    all_metrics: list[CheckMetric] = []
    qto_by_category = qto_by_category or {}
    units_by_category = units_by_category or {}

    for category, elements in category_to_elements.items():
        metrics = build_category_metrics(
            ad,
            category,
            list(elements),
            relevant_qto_types=qto_by_category.get(category),
            # TODO this is to be updated. to support more robust implementation
            expect_units=units_by_category.get(category, ("m2", "m3", "kg", "m", "pcs")),
        )
        all_metrics.extend(metrics)

        targets = [ov for ov in (getattr(out, "overviews", None)) if ov.category == category]
        if getattr(out, "overview", None) and out.overview.category == category:
            targets.append(out.overview)
        for ov in targets:
            apply_metrics_to_overview(ov, metrics)

    out.check_metrics = all_metrics


def metrics_to_indicator_rows(
    indicators: Iterable[IndicatorRow],
    metrics: Iterable[CheckMetric],
    category_context: Optional[dict[str, dict[str, Any]]] = None,
) -> list[dict]:
    rows = {}
    for ind in indicators:
        category = _clean_category(getattr(ind, "category", ""))
        row = asdict(ind)
        row["category"] = category
        row = _add_category_context(row, category, category_context, include_count=False)
        rows[category] = row
    for m in metrics:
        category = _clean_category(m.category)
        rows.setdefault(
            category,
            _add_category_context({"category": category}, category, category_context, include_count=False),
        )
        rows[category][f"{m.check}_pct"] = m.pct
    return list(rows.values())


def metrics_to_count_rows(
    indicators: Iterable[IndicatorRow],
    metrics: Iterable[CheckMetric],
    category_context: Optional[dict[str, dict[str, Any]]] = None,
) -> list[dict]:
    rows = {}
    for ind in indicators:
        category = _clean_category(getattr(ind, "category", ""))
        rows[category] = _add_category_context({"category": category}, category, category_context)
    for m in metrics:
        category = _clean_category(m.category)
        rows.setdefault(category, _add_category_context({"category": category}, category, category_context))
        rows[category][f"{m.check}_present"] = m.present
    return list(rows.values())


def category_context_from_overview(overview_rows: Iterable[object]) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for row in overview_rows:
        category = _clean_category(getattr(row, "category", ""))
        if not category:
            continue
        context[category] = {
            "category_name": getattr(row, "name", "") or "",
            "element_count": getattr(row, "elementCount", None),
        }
    return context


def check_definition_rows() -> list[dict[str, str]]:
    rows = []
    for level, weights in LEVEL_WEIGHTS.items():
        for check in weights:
            rows.append(_definition_row(level, check))
        if level == "L4b":
            rows.append(_definition_row(level, "l4b_mechanical_fastener"))
    return rows


def methodology_notes() -> list[dict[str, str]]:
    return [
        {"Topic": "Blank check cells", "Note": "Blank means the category/check has no applicable elements in scope."},
        {"Topic": "Percentages", "Note": "Check percentages are stored as 0-1 ratios and formatted as Excel percentages."},
        {"Topic": "Category count", "Note": "The Check Counts sheet uses category_element_count as the shared denominator for check present counts."},
        {"Topic": "L1", "Note": "L1 asks whether elements can be placed in the right category using explicit IFC evidence."},
        {"Topic": "L2", "Note": "L2 asks whether elements have usable geometry or quantity evidence."},
        {"Topic": "L3", "Note": "L3 asks whether elements have material, property, service-life, or documentation evidence."},
        {"Topic": "L4a", "Note": "L4a asks whether elements expose environmental impact or EPD-link evidence."},
        {"Topic": "L4b", "Note": "L4b asks whether elements expose traceability or reversible-connection cues."},
        {"Topic": "Deterministic boundary", "Note": "Checks use explicit IFC relationships, entity/type fields, and explicit property/reference values only."},
        {"Topic": "No token inference", "Note": "Names, labels, descriptions, material category names, and classification titles are not parsed for implicit meaning."},
        {"Topic": "Material external references", "Note": "Material external references indicate low-significance readiness evidence, not EPD proof."},
        {"Topic": "L4b reversibility", "Note": "Reversibility checks inspect only direct relevant relationships and do not recurse."},
        {"Topic": "Mechanical fastener", "Note": "IfcMechanicalFastener is the only accepted deterministic reversible-without-damage fastener signal."},
        {"Topic": "Legacy scores", "Note": "Legacy L1-L4b scores are weighted aggregates of the deterministic check columns."},
    ]


def _clean_category(category: object) -> str:
    return " ".join(str(category or "").split())


def _add_category_context(
    row: dict[str, Any],
    category: str,
    category_context: Optional[dict[str, dict[str, Any]]],
    include_count: bool = True,
) -> dict[str, Any]:
    context = (category_context or {}).get(category, {})
    out: dict[str, Any] = {"category": category}
    if "category_name" in context:
        out["category_name"] = context.get("category_name", "")
    if include_count:
        out["category_element_count"] = context.get("element_count")
    for key, value in row.items():
        if key != "category":
            out[key] = value
    return out


def _definition_row(level: str, check: str) -> dict[str, str]:
    definition = CHECK_DEFINITIONS.get(check, {})
    return {
        "level": level,
        "percentage_column": f"{check}_pct",
        "count_column": f"{check}_present",
        "short_label": CHECK_TITLES.get(check, check),
        "what_it_checks": definition.get("what", ""),
        "counts_as_evidence": definition.get("evidence", ""),
        "does_not_count": definition.get("not_evidence", ""),
    }


def _weighted_score(metrics: dict[str, CheckMetric], weights: dict[str, float]) -> float:
    num = 0.0
    den = 0.0
    for check, weight in weights.items():
        m = metrics.get(check)
        if not m or m.pct is None:
            continue
        num += m.pct * weight
        den += weight
    return num / den if den else 0.0


def _has_predefined_attr(e:entity_instance) -> bool:
    return hasattr(e, "PredefinedType")


def _has_quantity_available(ad:CoreType, e:entity_instance, relevant_qto_types: set[str]) -> bool:
    try:
        if ad._has_relevant_qto(e, relevant_qto_types):
            return True
    except Exception:
        pass
    return _has_mep_common_dimension(ad, e)


def _has_positive_quantity_value(ad:CoreType, e:entity_instance) -> bool:
    if _has_positive_qto(ad, e):
        return True
    return _has_positive_mep_common_dimension(ad, e)


def _has_functional_quantity_basis(ad:CoreType, e:entity_instance, expect_units: tuple[str, ...]) -> bool:
    try:
        if ad.has_compatible_qto_unit(e, expect_units):
            return True
    except Exception:
        pass
    exp = tuple(s.lower() for s in expect_units)
    if any(unit in exp for unit in ("m", "m1")):
        return _has_positive_mep_common_length(ad, e)
    return False


def _has_positive_qto(ad:CoreType, e:entity_instance) -> bool:
    for name in QTO_NAMES:
        try:
            value = ad.qto_value(e, name)
            if value is not None and float(value) > 0:
                return True
        except Exception:
            continue
    return False


def _has_mep_common_dimension(ad:CoreType, e:entity_instance) -> bool:
    return _mep_common_dimension_value(ad, e, MEP_COMMON_DIMENSION_PROPS) is not None


def _has_positive_mep_common_dimension(ad:CoreType, e:entity_instance) -> bool:
    value = _mep_common_dimension_value(ad, e, MEP_COMMON_DIMENSION_PROPS)
    return _positive_number(value)


def _has_positive_mep_common_length(ad:CoreType, e:entity_instance) -> bool:
    value = _mep_common_dimension_value(ad, e, MEP_COMMON_LENGTH_PROPS)
    return _positive_number(value)


def _mep_common_dimension_value(ad:CoreType, e:entity_instance, prop_names: Iterable[str]) -> Any:
    for target in _targets(ad, e):
        for pset in MEP_COMMON_DIMENSION_PSETS:
            for prop in prop_names:
                try:
                    value = ad.get_pset_value(target, pset, prop)
                except Exception:
                    value = None
                if value not in (None, "", [], {}):
                    return value
    return None


def _positive_number(value: Any) -> bool:
    try:
        return value is not None and float(value) > 0
    except Exception:
        return False


def _has_material_detail(ad:CoreType, e:entity_instance) -> bool:
    try:
        if ad.material_density(e):
            return True
        layers = ad.get_material_layers(e)
        if layers:
            return True
        if ad.layer_thickness(e):
            return True
    except Exception:
        return False
    return False


def _has_document_reference(ad:CoreType, e:entity_instance) -> bool:
    try:
        if ad._has_document_association(e):
            return True
        t = ad._type_of(e)
        return bool(t and ad._has_document_association(t))
    except Exception:
        return False


def _has_service_life(ad:CoreType, e:entity_instance) -> bool:
    return _pset_any(ad, e, ("Pset_ServiceLife",), ("ReferenceServiceLife",))


def _has_environmental_pset(ad:CoreType, e:entity_instance) -> bool:
    for target in _targets(ad, e):
        try:
            psets = ad._psets(target)
        except Exception:
            psets = {}
        if "Pset_EnvironmentalImpactIndicators" in psets:
            return True
    return False


def _has_gwp_value(ad:CoreType, e:entity_instance) -> bool:
    props = (
        "GWP", "GlobalWarmingPotential", "ClimateChange",
        "EmbodiedCarbon", "CarbonDioxideEquivalent",
    )
    return _pset_any(ad, e, ("Pset_EnvironmentalImpactIndicators",), props)


def _has_element_or_type_environmental_reference(ad:CoreType, e:entity_instance) -> bool:
    for target in _targets(ad, e):
        for rel in getattr(target, "HasAssociations", []):
            try:
                if rel and rel.is_a("IfcRelAssociatesDocument"):
                    return True
                if rel and rel.is_a("IfcRelAssociatesExternal"):
                    return True
                if rel and rel.is_a("IfcRelAssociatesClassification"):
                    return True
            except Exception:
                continue
    return False


def _has_material_external_reference(ad:CoreType, e:entity_instance) -> bool:
    for mat in _associated_materials(ad, e):
        if _entity_has_external_reference(mat):
            return True
        for rel in getattr(mat, "HasExternalReferences", []):
            if rel:
                return True
    return False


def _has_manufacturer(ad:CoreType, e:entity_instance) -> bool:
    return _pset_any(ad, e, MANUFACTURER_PSETS, ("Manufacturer",))


def _has_product_identifier(ad:CoreType, e:entity_instance) -> bool:
    return _pset_any(ad, e, MANUFACTURER_PSETS + ("Pset_Asset",), PRODUCT_ID_PROPS)


def _pset_any(ad:CoreType, e:entity_instance, pset_names: Iterable[str], prop_names: Iterable[str]) -> bool:
    for target in _targets(ad, e):
        for pset in pset_names:
            for prop in prop_names:
                try:
                    value = ad.get_pset_value(target, pset, prop)
                except Exception:
                    value = None
                if value not in (None, "", [], {}):
                    return True
    return False


def _targets(ad:CoreType, e:entity_instance) -> list[entity_instance]:
    targets = [e]
    try:
        t = ad._type_of(e)
    except Exception:
        t = None
    if t:
        targets.append(t)
    return targets


def _associated_materials(ad:CoreType, e:entity_instance) -> list[entity_instance]:
    mats: list[entity_instance] = []
    for target in _targets(ad, e):
        for rel in getattr(target, "HasAssociations", []):
            try:
                if not rel or not rel.is_a("IfcRelAssociatesMaterial"):
                    continue
                mat = getattr(rel, "RelatingMaterial", None)
                if mat:
                    mats.append(mat)
                    mats.extend(_material_children(mat))
            except Exception:
                continue
    return mats


def _material_children(mat) -> list[entity_instance]:
    out: list[entity_instance] = []
    for attr in ("MaterialLayers", "MaterialConstituents", "Materials"):
        for child in getattr(mat, attr, []):
            material = getattr(child, "Material", None) or child
            if material:
                out.append(material)
    return out


def _entity_has_external_reference(e:entity_instance) -> bool:
    if not e:
        return False
    for attr in ("HasExternalReferences", "HasAssociations"):
        for rel in getattr(e, attr, []):
            if rel:
                return True
    return False


def _direct_element_connections(e:entity_instance) -> list[entity_instance]:
    rels: list[entity_instance] = []
    for attr in ("ConnectedTo", "ConnectedFrom"):
        for rel in getattr(e, attr, []):
            try:
                if rel and rel.is_a() in {
                    "IfcRelConnectsElements",
                    "IfcRelConnectsPathElements",
                    "IfcRelConnectsWithRealizingElements",
                }:
                    rels.append(rel)
            except Exception:
                continue
    return rels


def _realizing_elements(e:entity_instance) -> list[entity_instance]:
    realizing: list[entity_instance] = []
    for rel in _direct_element_connections(e):
        try:
            if rel.is_a("IfcRelConnectsWithRealizingElements"):
                realizing.extend(list(getattr(rel, "RealizingElements", [])))
        except Exception:
            continue
    return [r for r in realizing if r]


def _is_mechanical_fastener(e:entity_instance) -> bool:
    try:
        return bool(e and e.is_a("IfcMechanicalFastener"))
    except Exception:
        return False


def _all_realizing_are_mechanical(e:entity_instance) -> bool:
    realizing = _realizing_elements(e)
    if not realizing:
        return False
    return all(_is_mechanical_fastener(r) for r in realizing)


def _has_system_membership(e:entity_instance) -> bool:
    rel:entity_instance
    for rel in getattr(e, "HasAssignments", []):
        try:
            if not rel:
                continue
            if not rel.is_a("IfcRelAssignsToGroup"):
                continue
            group:entity_instance | None = getattr(rel, "RelatingGroup", None)
            if group and (group.is_a("IfcSystem") or group.is_a("IfcDistributionSystem")):
                return True
        except Exception:
            continue
    return False
