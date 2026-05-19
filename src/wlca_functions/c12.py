from src.classes import CoreType,PreIndex,IdxElements
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn, IndicatorRow
from ifcopenshell import entity_instance

# this section is ignored, lowest slab part of another category and no determinstic way to find basement retaining walls, only based on assumptions
# 1.2 Basement retaining walls and lowest slab
def category_12(ad: CoreType) -> CategoryReturn:
    """
    Assess Category 1.2: Basement retaining walls and lowest slabs.
    This category evaluates the WLCA readiness of foundation-level elements including:
      - 1.2.1: Lowest/base slabs (foundation slabs, typically BASESLAB type)
      - 1.2.2: Suspended slabs within basement/retaining area
      - 1.2.3: Retaining walls (walls supporting ground or lateral loads)
    
    Uses L1-L4b assessment levels.
    """
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview = IndicatorRow()
    out.overview.category = "1.2"
    
    # Partial scaffolding only: this function is intentionally not wired into App.py yet.
    # Standalone export needs defensible scope collection for lowest slabs and retaining walls
    # before BEC 1.2 can become a release-facing category.
    
    elems:list[entity_instance] = []
    
    n = 0
    n_pdt_ok = 0
    n_class_ok = 0
    n_shape_ok = 0
    n_qto_ok = 0
    n_mat_ok = 0
    n_doc_ok = 0
    
    for el in elems:
        if el.id() in ad.parsedElIds:
            continue
        
        ifc_class = el.is_a()
        
        # Track element-level issues
        n += 1
        if ad._valid_predefined_type(el):
            n_pdt_ok += 1
        if ad._has_classification_ref(el):
            n_class_ok += 1
        if ad._has_shape_representation(el):
            n_shape_ok += 1
        if ad._has_relevant_qto(el, {"IfcQuantityVolume", "IfcQuantityArea"}):
            n_qto_ok += 1
        if ad._has_material_association(el):
            n_mat_ok += 1
        if ad._has_document_association(el):
            n_doc_ok += 1
    
    out.overview.l1_score = 0.25 * (n_pdt_ok / n) + 0.75 * (n_class_ok / n) if n > 0 else 0.0
    out.overview.l2_score = 0.4 * (n_shape_ok / n) + 0.6 * (n_qto_ok / n) if n > 0 else 0.0
    out.overview.l3_score = 0.4 * (n_mat_ok / n) + 0.6 * (n_doc_ok / n) if n > 0 else 0.0
    out.overview.l4a_score = 0.0
    out.overview.l4b_score = 0.0
    out.overview.issues = len(out.issues)
    
    return out
