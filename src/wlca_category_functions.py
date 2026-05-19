from typing import Dict
import ifcopenshell

from src.classes import CoreType,PreIndex

TARGETS = {
  # 0 facilitating works -> not possible
    # 0.1.1.1 Toxic/ contaminated material treatment 
    # 0.1.1.2 Demolition works
    # 0.1.1 Toxic/ contaminated material treatment Demolition works
    # 0.1.2.1 Temporary supports
    # 0.1.2.2  Facade retention
    # 0.1.2.3 Specialist groundworks
    # 0.1.2.4 Temporary diversion works
    # 0.1.2.5 Extraordinary site investigations
    # 0.1.2.6 Site preparation
    # 0.1.2 Facilitating works
    
    # 1.1 Foundations and piling
    "L1-1.1": 1, # IfcFooting, IfcFootingType/IfcFootingTypeEnum, IfcSlab, IfcSlabType, IfcSlabTypeEnum exist?
    # 1.2 Basement retaining walls and lowest slab
    "L1-1.2": 1, # IFCWALL, IfcWallTypeEnum, IfcWallType, IfcSlab, IfcSlabType, IfcSlabTypeEnum exist?
    # 1.2.1 Lowest slab
    "L1-1.2.1": 1, # IfcSlab, IfcSlabType, IfcSlabTypeEnum exist?
    "L1-1.2.1_auto": 0, # estimated slab based on y0, if IfcSlab exist
    # 1.2.2 Suspended slabs 
    # not sure? ifc doesnt outline.
    # 1.2.3 Basement retaining walls
    "L1-1.2.3": 1, # IfcSlab, IfcSlabType, IfcSlabTypeEnum exist?
    "L1-1.2.3_auto": 0, # estimated wall based on y0
    
    
    # 2.1 Frame
    # 2.1.1 Frame (Vertical)  - Columns/ structural walls & braces
    "L1-2.1.1": 1, # IfcColumn, IfcColumnType, IfcColumnTypeEnum exist?
    # 2.1.2 Frame (Horizontal) - Beams, joists & braces
    "L1-2.1.2": 1, # IfcBeam, IfcBeamType, IfcBeamTypeEnum exist?
    
    # 2.2 Upper Floors and roof (2.3)
    # 2.2.1 Upper floor and roof - structural slabs
    "L1-2.2.1": 1, # IfcSlab, IfcSlabType, IfcSlabTypeEnum exist?
    # cant really estimate if structural or not?
    "L1-2.2.1_auto": 0, # estimated slab based on y0, if IfcSlab exist
    # 2.2.2 Upper floor and roof - non-structural slabs
    "L1-2.2.2": 1, # IfcSlab, IfcSlabType, IfcSlabTypeEnum exist?
    "L1-2.2.2_auto": 0, # estimated slab based on y0, if IfcSlab exist
    
    # 2.4 Stairs, ramps and safety guarding
    "L1-2.4": 1, # IfcStair, IfcStairType, IfcRamp and IfcRampType, IfcRailing, IfcRailingType exist?
    # 2.4.1 Stairs
    # 2.4.2 Ramps
    # 2.4.3 Safety and access ladders, chutes, slides and guarding
   
    
    # 2.5  External envelope including roof finishes
    "L1-2.5": 1, # IFCWALL exist?
    # 2.5.1 External - opaque walls 

    "L1-2.5.1": 0.95,  # is walls external?
    "L2-2.5.1": 0.95,  # walls: >=2 layers
    "L5-2.5.1": 0.80,  # walls: EPD link
    # 2.5.2 External - full height glazing systems
    "L1-2.5.2-01": 0, # IFCCurtainWAll, IFcCurtainWallType exist? 
    # issue is often this is modelled by building element proxy... and only through layer you "know" the values...
    
    # 2.5.3 External - roof finishes/ coverings
    "L1-2.5.3":0, # IfcCovering with PredefinedType attached, isExternal
    "L2-2.5.3":0, #
    "L3-2.5.3":0, # 
    "L45-2.5.3":0, # IfcDocumentReference with delcated unit m2 and thickness+mass. Pset_ServiceLife.ReferenceServiceLife present. IfcRelConnectsWithRealizingElements + IfcMechanicalFastener/ IfcFastener present. Pset_ManufacturerOccurrence.ModelReference/SerialNumber present
    # 2.5.4 External - safety systems
    
    # 2.6 Windows and ext doors
    "L1-2.6":1, # IfcWindow, IfcWindowType/ IfcWindowTypeEnum exist?
    "L3-2.6":1, # IfcProduct exist, otherwise i cant really say the material composition?
    # 2.6.1 Windows - vertical
    "L1-2.6.1": 1, # IfcWindowType exist? or try to estimate from code?
    # 2.6.2 Windows - roof or horizontal
    # 2.6.3 External doors
    
    # 2.7 Internal walls
    # 2.7.1 Internal walls  - solid
    # 2.7.2 Internal walls  - non-structural glazed walls, windows and vision panels

    # 2.8 Internal doors
    
    # 3.1 Wall finishes 
    # 3.2 Floor finishes
    # 3.2.1 Raised access floor or specialist sprung floors
    # 3.2.2 Non-structural screed
    # 3.2.3 Floor finishes
    # 3.3 Ceiling finishes
    
    # 4 FF&E this is not very feasible.
    # 4.1 General FF&E
    # 4.2 Kitchen  equipment
    # 4.3  Special equipment
    # 4.4 Loose FF&E
    # 4.5 IT
    # 4.6 Audio and visual
  
    # 5.1.1 Sanitaryware
    # 5.1.2  Cold water systems
    # 5.1.2.1  Cold water systems
    # 5.1.2.2  Cold water storage
    # 5.1.3  Drainage and rainwater
    # 5.1.3.1 Surface water/ rainwater/ foul water drainage
    # 5.1.3.2 Water reuse systems
    
    # 5.2.1 Space heating and hot water
    # 5.2.1.1 Heat & Hot water generation equipment
    # 5.2.1.2 Heat & hot water distribution, control, ancillaries, emitters, exchangers/  terminal units
    # 5.2.1.3 Heat storage equipment
    
    # 5.2.2 Dedicated cooling installations
    # 5.2.2.1  Cooling generation equipment
    # 5.2.2.2 Cooling emitter, exchangers/ terminal units, ancillaries and control, distribution, storage
    
    # 5.2.3.1 Air movement
    # 5.2.4 Ventilation air terminals, ductwork and ancillaries, control dampers, attenuation, fire safety related to ventilation equipment
    # 5.2.4.1 Air terminals 
    # 5.2.4.2 Ductwork  & ancilleries  
    # 5.2.4.3 Control dampers, attenuation and fIre safety related to ventilation equipment
    
    # 5.3.1 Lighting
    # 5.3.1.1 Internal lighting
    # 5.3.1.2 External lighting (building mounted)
    # 5.3.1.3 Emergency lighting
    # 5.3.1.4 Other lighting
    
    # 5.3.2 Electrical services for power, communications, security, IT and fire detection,
    # 5.3.2.1 Electrical power
    # 5.3.2.2 ELV/ Communications/ Security
    # 5.3.2.3 IT & Data
    # 5.3.2.4 BMS
    # 5.3.2.5 Electricity back up generation
    # 5.3.2.6  Fire detection & alarm
    
    # 5.4.1.1 Renewable energy - Electrical generation onsite and building mounted
    # 5.4.1.2 Renewable energy - Storage onsite
    # 5.4.1 On site renewable energy generation
    
    # 5.5.1 Life safety
    # 5.5.1.1 Sprinkler system
    # 5.5.1.2 Fire fighting systems
    # 5.5.1.3 Lightning protection/earth bonding
    
    # 5.5.2 Fuel installations
    # 5.5.2.2 Lift, stair lift, lifting platform
    # 5.5.2.3 Escalators and moving walkways
    # 5.5.3 Lift and conveyor installations
    # 5.5.4 Specialised and communal waste disposal
    # 5.5.5 Specialist installations & maintenance
    # 5.5.6 Builders work in connection with services
    
    # 6 Pre-fabricated buildings and building units 
    # 7.1 Alterations 
    # 7.2 Repairs, cleaning, general renovation
    # 7.3 Damp-proof courses/fungus and beetle eradication
    # 7 Works to existing buildings

    # 8.1.1 Roads, paths, pavings, surfaces
    # 8.1.2 Fencing, railings, walls
    # 8.1.3 External fixtures
    # 8.1 Roads, paths, pavings, surfaces Fencing, railings, walls External fixtures
    # 8.2 Soft landscape, planting, irrigation
    # 8.3.1 External drainage
    # 8.3.2 External services
    # 8.3.3 Minor building works, ancillary
    # 8.3 External drainage  External services Minor building works
 
  "L3-2.6-01":   1.00,  # windows/doors: fills opening & host ok
  "L4-5.2.4-01": 0.95,  # ventilation: terminals connected
}

#TARGETS: dict[str, float] = {}  # e.g., {"L1-1.1-01": 0.9}

def mk_result(
    check_id: str,
    title: str,
    cats: list[str],
    entities: list[str],
    # legacy positional (ok, total, findings)
    ok: int | None = None,
    total: int | None = None,
    findings: list[dict] | None = None,
    *,
    # preferred keyword args
    ok_count: int | None = None,
    severity: str = "major",
    kind: str = "coverage",
    target: float | None = None,
    method: str | None = None,
):
    """
    Build a normalized result payload.
    Accepts either:
      mk_result(..., ok, total, findings)            # legacy positional
      mk_result(..., ok_count=..., total=..., findings=[...])  # keyword style
    """
    # ---- normalize inputs ----
    if ok_count is None and ok is not None:
        ok_count = ok
    if total is None:
        # total might come via keyword or legacy positional
        # leave None if not provided
        pass
    if findings is None:
        findings = []

    # guard
    ok_count = int(ok_count or 0)
    total    = int(total or 0)

    # target lookup / override
    tgt = float(TARGETS.get(check_id, 1.0) if target is None else target)

    # actual coverage
    if total <= 0:
        actual = 1.0  # empty scope treated as pass-by-scope (no violations possible)
        empty_scope = True
    else:
        actual = ok_count / total
        empty_scope = False

    # status
    if empty_scope:
        status = "not_applicable" 
    else:
        status = "pass" if actual >= tgt else ("partial" if ok_count > 0 else "fail")

    # payload
    return {
        "check_id": check_id,
        "title": title,
        "category_codes": cats,
        "entities": entities,
        "method": method or title,  # short human spec
        "metric": {
            "kind": kind,
            "target": round(tgt, 3),
            "actual": round(actual, 3),
            "ok": ok_count,
            "total": total,
            "missing": max(total - ok_count, 0),
            "coverage_pct": round(actual * 100.0, 1),
            "empty_scope": empty_scope,
        },
        "severity": severity,
        "status": status,
        "findings": findings,  # list[ {entity_guid, entity_type, message, ...} ]
    }

