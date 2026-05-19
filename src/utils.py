import ifcopenshell
from src.wlca_category_functions import TARGETS
from src.classes import CoreType, IdxElements, PreIndex

def adapt(model:ifcopenshell.file)->CoreType:
  """Return a tiny adapter obj exposing only what we use."""
  return CoreType(model)

# TODO preindex is unused to maximise determinism
roof_kinds = {"ROOFING","MEMBRANE","FLASHING"}  # FLASHING is IFC4+; harmless if absent
def _predef(e):
    v = getattr(e.get_info(), "PredefinedType", None)
    if v and str(v).upper() not in ("NOTDEFINED","USERDEFINED"):
        return str(v).upper()
    t = None
    for r in getattr(e.get_info(), "IsTypedBy", []) or []:
        t = getattr(r, "RelatingType", None)
        if t: break
    if t:
        tv = getattr(t, "PredefinedType", None)
        if tv and str(tv).upper() not in ("NOTDEFINED","USERDEFINED"):
            return str(tv).upper()
    return None

def preindex(ad:CoreType)-> PreIndex:
  """Collect once, avoid repeated by_type calls and build quick maps."""
  idx:PreIndex = PreIndex({
      IdxElements.footings: []
  })
  idx[IdxElements.footings] = list(ad.iter_by_type("IfcFooting"))
  idx[IdxElements.footingTypes] = list(ad.iter_by_type("IfcFootingType"))
  idx[IdxElements.piles]    = list(ad.iter_by_type("IfcPile"))
  #idx[IdxElements.pilecaps] = [f for f in idx[IdxElements.footings] if ad.is_pilecap(f)] 
  
  idx[IdxElements.walls]   = list(ad.iter_by_type("IfcWall"))
  idx[IdxElements.wallTypes]   = list(ad.iter_by_type("IfcWallType"))
  
  idx[IdxElements.windows] = [w for w in ad.iter_by_type("IfcWindow") if not ad.is_in_curtainwall_panel(w)]
  idx[IdxElements.roofWindows] = [rw for rw in ad.iter_by_type("IfcRoofWindow")] or [w for w in ad.iter_by_type("IfcWindow") if getattr(w,"PredefinedType",None)=="SKYLIGHT"]
  idx[IdxElements.doors] = list(ad.iter_by_type("IfcDoor"))
  
  #curtainWall
  idx[IdxElements.extDoors]=[d for d in idx[IdxElements.doors] if ad.is_external(ad.fill_host(d))]
  idx[IdxElements.intDoors]=[d for d in idx[IdxElements.doors] if ad.is_external(ad.fill_host(d)) == False]
  
  idx[IdxElements.terminals]   = list(ad.iter_by_type("IfcAirTerminal"))
  idx[IdxElements.sanitary]=list(ad.iter_by_type("IfcSanitaryTerminal"))
  
  idx[IdxElements.pipes] = list(ad.iter_by_type("IfcPipe"))
  idx[IdxElements.pipeSegments]=list(ad.iter_by_type("IfcPipeSegment"))
  idx[IdxElements.pipeFitting]=list(ad.iter_by_type("IfcPipeFitting")) # IFCPIPEFITTING
  
  idx[IdxElements.slabs] = list(ad.iter_by_type("IfcSlab"))
  # predefined type idk if its attribute_type()
  idx[IdxElements.coveringsRoof] = [
    c for c in ad.iter_by_type("IfcCovering")
    if (_predef(c) in roof_kinds) or ad.name_contains(c, ("roof","membrane","flashing"))
  ]
  idx[IdxElements.guarding] = list(ad.iter_by_type("IfcRailing"))   
  idx[IdxElements.parapets]= [w for w in ad.iter_by_type("IfcWall") if ad.is_parapet(w)]
  idx[IdxElements.anchors]=  list(ad.iter_by_type("IfcFastener")) + list(ad.iter_by_type("IfcMechanicalFastener"))
  idx[IdxElements.allOpenings]= list(ad.iter_by_type("IfcOpeningElement"))
  # Optionally build GUID→entity, fill→host maps here for O(1) checks
#   p12=_preindex_12(ad,{})
#   for (k,v) in p12.items():
#       idx[k]=v
  return idx
