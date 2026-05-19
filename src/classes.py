from enum import Enum
import ifcopenshell
from typing import Any, Generator, Iterable, Optional, Tuple, List, NewType
import ifcopenshell.geom
from ifcopenshell.util import unit
from ifcopenshell.util import shape
from src.excel.types import CategoryRow
from dataclasses import dataclass, field
import ifcopenshell.util.element as ifcEl
from ifcopenshell.util.element import get_psets as _u_get_psets
from ifcopenshell.util.element import get_material as _u_get_material
from ifcopenshell.entity_instance import entity_instance
    
class IdxElements(Enum):
    footings="footings",
    footingTypes="footingTypes",
    piles="piles",
    pilecaps="pilecaps",
    walls="walls",
    wallTypes="wallTypes",
    windows="windows",
    
    roofWindows="roof_windows",
    allOpenings="all_openings",
    
    doors="doors",
    extDoors="ext_doors",
    intDoors="int_doors",
    
    terminals="terminals",
    sanitary='sanitary',
    pipes="pipes",
    pipeSegments="pipe_segments",
    pipeFitting="pipe_fitting",
    
    slabs="slabs",
    roofSlabs="roof_slabs",
    
    coveringsRoof="coverings_roof",
    guarding="guarding",
    parapets="parapets",
    anchors="anchors"
    
PreIndex = NewType('PreIndex',dict[IdxElements, list[entity_instance]])
    
class CoreType:
    parsedElIds: list[int]=field(default_factory=list)
    def __init__(self, model: ifcopenshell.file,*args, **kwargs) -> None: 
        self._m = model
        ignoreIds=kwargs.get('ignoreIds',[])
        self.parsedElIds = ignoreIds or []
        
    def schema(self): return (getattr(self._m, "schema", "unknown")).upper()
    def file_name(self): return getattr(self._m, "filename", "") or getattr(self._m, "path", "") or ""
    def file_size_bytes(self):
      import os; fn = self.file_name(); 
      return os.path.getsize(fn) if fn else 0    
    def has_entity(self, name: str) -> bool:
      try:
          self._m.by_type(name)
          return True
      except RuntimeError:
          return False
    def iter_by_type(self, name: str):
        try:
            return list(self._m.by_type(name))
        except RuntimeError:
            return []  # never crash if the entity doesn't exist in this schema

    def by_types(self, names: list[str])->list[entity_instance]:
        out = []
        for n in names:
            out.extend(self.iter_by_type(n))
        return out
    
    def build_category_row(self, item:entity_instance,baseCategory:CategoryRow) ->CategoryRow:
        row=baseCategory
        self.parsedElIds.append(item.id())
        # find out
        row.area_m2=0
        row.description=""
        row.element_guid= getattr(item,'GlobalId',"")
        row.element_id= str(item.id())
        row.ifc_class=item.is_a()
        row.mass_kg=0
        row.object_type=getattr(item,'ObjectType',None)
        row.count=1
        row.count_cantCalcRI=0
        
        try:
            row.material_name = ' '.join(self.materials(item))
            row.missing_material = not bool(row.material_name.strip())
        except (AttributeError, TypeError) as exc:
            row.missing_material = True
            row.material_name = ""
            
        try:
            val = self.get_net_volume_m3(item, row)
            if val is None:
                raise ValueError("Volume is None")
            row.volume_m3 = float(val)
        except Exception as exc:
            row.volume_m3 = 0
            row.missing_geometry = True
            row.count_cantCalcRI += 1
            
        try:
            # division is relevant to elements which are Plates/Coverings. For them, only 1 side surface area is relevant. 
            # as the elements are very thin it is assumed a "fair" approximation
            val = self.get_net_area_m2(item)
            if val is None:
                raise ValueError("Area is None")
            row.area_m2 = float(val) / 2
        except Exception as exc:
            row.area_m2 = 0
            row.missing_geometry = True
        
        return row
    def get_element_common_pset(self, item:entity_instance)->(Any | dict[str, Any]):
        try:
            classific=item.is_a()
            base=classific[3:]
            if(base.endswith("Type")):
                base=base[:-4]
            pset_name=f"Pset_{base}Common"
            return ifcEl.get_pset(item, pset_name, verbose=True)
        except:
            print(f"Error parsing common pset on element {item.id()}")
            return None

    # ── DETERMINISTIC — direct IFC relation / attribute checks ────────────────
    # Methods here inspect explicit IFC attributes or relations without inference.
    # Positive results indicate the information is present in the exchanged file;
    # they do not imply semantic adequacy beyond that presence.

    def _psets(self, e:entity_instance) -> dict:
        """Return a dict of psets -> {prop: value} (best-effort)."""
        try:
            return _u_get_psets(e) or {}
        except Exception:
            pass
        #  crawl IfcRelDefinesByProperties
        out = {}
        rel: entity_instance
        for rel in getattr(e, "IsDefinedBy", []):
            p:entity_instance | None = getattr(rel, "RelatingPropertyDefinition", None)
            if p and p.is_a("IfcPropertySet"):
                props = {}
                q:entity_instance
                for q in getattr(p.get_info(), "HasProperties", []):
                    if q.is_a("IfcPropertySingleValue"):
                        props[q.Name] = getattr(getattr(q, "NominalValue", None), "wrappedValue", None)
                # havent yet had a failing?
                out[p.get_info().Name] = props
        return out

    def _qto(self, e:entity_instance) -> dict:
        """Return a dict of Qto props name->value across all element quantities."""
        out = {}
        for rel in getattr(e.get_info(), "IsDefinedBy", []):
            qset:entity_instance = getattr(rel.get_info(), "RelatingPropertyDefinition", None)
            if qset and qset.is_a("IfcElementQuantity"):
                for q in getattr(qset.get_info(), "Quantities", []):
                    val = None
                    if hasattr(q.get_info(), "VolumeValue"): val = q.VolumeValue
                    elif hasattr(q.get_info(), "AreaValue"): val = q.AreaValue
                    elif hasattr(q.get_info(), "LengthValue"): val = q.LengthValue
                    elif hasattr(q.get_info(), "CountValue"): val = q.CountValue
                    elif hasattr(q.get_info(), "WeightValue"): val = q.WeightValue
                    elif hasattr(q.get_info(), "TimeValue"): val = q.TimeValue
                    out[q.get_info().Name] = val
        return out

    def _type_of(self, e:entity_instance):
        """Return type object if IsTypedBy is set."""
        #relations: list[entity_instance]=(getattr(e.get_info(), "HasAssociations", [])
        for rel in getattr(e, "IsTypedBy", []):
            t = getattr(rel, "RelatingType", None)
            if t: return t
        return None

    def _class_refs(self, e:entity_instance) -> List[Any]:
        """Return list of IfcClassificationReference associated to element or its type."""
        out = []
        for target in (e, self._type_of(e)):
            if not target: continue
            for rel in getattr(target, "HasAssociations", []):
                c:entity_instance = getattr(rel, "RelatingClassification", None)
                if c and (c.is_a("IfcClassificationReference") or c.is_a("IfcClassification")):
                    out.append(c)
        return out

    def _mat_rel(self, e:entity_instance):
        """Return RelatingMaterial (tree: Single/LayerSet/ConstituentSet…)."""
        relations: list[entity_instance]=(getattr(e, "HasAssociations", []))
        for rel in relations:
            m:entity_instance = getattr(rel, "RelatingMaterial", None)
            if m: return m
        # try type-level
        t:entity_instance = self._type_of(e)
        if t:
            relations: list[entity_instance]=(getattr(t, "HasAssociations", []))
            for rel in getattr(t, "HasAssociations", []):
                m = getattr(rel, "RelatingMaterial", None)
                if m: return m
        return None

    # ── BEST-EFFORT / FALLBACK ─────────────────────────────────────────────────
    # Methods here attempt IFC-schema traversal first, then fall back to
    # geometry computation or alternative parsings. May return None if both fail.

    def get_net_volume_m3(self, element:entity_instance, row:Optional[CategoryRow]):
        """Return element volume in m³. Tries Qto first; falls back to geometry engine."""
        try:
            for rel in getattr(element, "IsDefinedBy", []):
                qset = rel.RelatingPropertyDefinition
                if qset and qset.is_a("IfcElementQuantity"):
                    for q in qset.Quantities:
                        if q.is_a("IfcQuantityVolume") and q.Name in ("NetVolume", "Volume"):
                            return float(q.VolumeValue)
        except Exception:
            pass

        # ── GEOMETRY ENGINE — expensive fallback, invokes ifcopenshell.geom ──
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        shapeThis = ifcopenshell.geom.create_shape(settings, element)
        # this is raw suggestion for calculation, 
        # which seems to "work" better than library one. not sure about correctness however.
        #verts = shapeThis.geometry.verts  # flat [x0,y0,z0, x1,y1,z1, ...]
        #faces = shapeThis.geometry.faces  # flat [i0,j0,k0, i1,j1,k1, ...]
        # Scale to SI (meters) based on IFC units
        # scale = unit.calculate_unit_scale(self._m)  # e.g., 0.001 if model is in mm
        # # Compute signed volume via triangle fan tetrahedra
        # vol = 0.0
        # for f in range(0, len(faces), 3):
        #     i, j, k = faces[f], faces[f+1], faces[f+2]
        #     ax, ay, az = (verts[3*i]   * scale, verts[3*i+1]   * scale, verts[3*i+2]   * scale)
        #     bx, by, bz = (verts[3*j]   * scale, verts[3*j+1]   * scale, verts[3*j+2]   * scale)
        #     cx, cy, cz = (verts[3*k]   * scale, verts[3*k+1]   * scale, verts[3*k+2]   * scale)
        #     # (a · (b × c)) / 6
        #     vol += (ax * (by*cz - bz*cy) - ay * (bx*cz - bz*cx) + az * (bx*cy - by*cx)) / 6.0

        return shape.get_volume(shapeThis.geometry)
    def get_net_area_m2(self, element:entity_instance):
        try:
            for rel in getattr(element, "IsDefinedBy", []):
                qset = rel.RelatingPropertyDefinition
                if qset and qset.is_a("IfcElementQuantity"):
                    for q in qset.Quantities:
                        if q.is_a("IfcQuantityArea") and q.Name in ("NetArea", "Area"):
                            return float(q.AreaValue)
        except Exception:
            pass
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        shapeThis = ifcopenshell.geom.create_shape(settings, element)
        # this works.
        return shape.get_area(shapeThis.geometry)


    def has_type_def(self, e:entity_instance) -> bool:
        """Has an assigned IfcTypeObject?"""
        return bool(self._type_of(e))

    def has_classification(self, e:entity_instance, any_of: Optional[Iterable[str]] = None) -> bool:
        """Has classification reference"""
        refs = self._class_refs(e)
        if not refs:
            return False
        if not any_of:
            return True
        toks = tuple(s.lower() for s in any_of)
        for c in refs:
            name = (getattr(c, "Name", "")) + " " + (getattr(c, "Identification", ""))
            if any(t in name.lower() for t in toks):
                return True
        for c in refs:
            cl = getattr(c, "ReferencedSource", None)
            nm = (getattr(cl, "Name", "")) if cl else ""
            if any(t in nm.lower() for t in toks):
                return True
        return False


    # Qto / quantities 
    # references the big blob but easier to understand externally
    def qto_value(self, e:entity_instance, qname: str) -> Optional[float]:
        """Return value of a quantity by name across all Qto sets."""
        return self._qto(e).get(qname)

    def qto_volume(self, e:entity_instance) -> Optional[float]:
        for key in ("NetVolume", "GrossVolume", "Volume"):
            v = self._qto(e).get(key)
            if v: return v
        return None

    def geom_length_axis(self, e:entity_instance) -> Optional[float]:
        """look for Qto Length first else None, not sure how to compute deterministically """
        for key in ("Length", "NetLength", "GrossLength"):
            v = self._qto(e).get(key)
            if v: return v
        # Some authors store pile length in Pset_PileCommon
        v = self._psets(e).get("Pset_PileCommon", {}).get("Length")
        return float(v) if v not in (None, "") else None

    def cross_section_area(self, e:entity_instance) -> Optional[float]:
        """Qto first"""
        v = self._qto(e).get("CrossSectionArea")
        if v: return v
        # TODO get actual cross section area calculation
        try:
            prof = getattr(e.get_info(), "ObjectType", None)
        except Exception:
            prof = None
        return None

    def aggregated_parts(self, e:entity_instance) -> List[Any]:
        """Return RelatedObjects from IsDecomposedBy (children)."""
        out = []
        for rel in getattr(e.get_info(), "IsDecomposedBy", []):
            kids = getattr(rel, "RelatedObjects", [])
            out.extend(kids)
        return out

    def materials(self, e:entity_instance) -> List[str]:
        # Currently, this is as-documented IFC deterministic parsing
        # In practice, it would be nondeterministcic layer/classification 
        # based guessing from LLMs.
        """
        Return a list of material names (layer set / constituent / single).
        Looks at element first, then its type.
        """
        # util path
        try:
            m = _u_get_material(e)
            if m:
                # m can be IfcMaterial or a tree
                def _collect(mat):
                    names = []
                    if hasattr(mat, "Name") and mat.Name:
                        names.append(mat.Name)
                    # LayerSet
                    ls = getattr(mat, "MaterialLayers", None)
                    if ls:
                        for lyr in ls:
                            if getattr(lyr, "Material", None) and getattr(lyr.Material, "Name", None):
                                names.append(lyr.Material.Name)
                    # Constituents
                    cs = getattr(mat, "MaterialConstituents", None)
                    if cs:
                        for c in cs:
                            if getattr(c, "Material", None) and getattr(c.Material, "Name", None):
                                names.append(c.Material.Name)
                    return names
                return list(dict.fromkeys(_collect(m)))  # unique, keep order
        except Exception:
            pass

        # generic association crawl
        names: list[str] = []
        m = self._mat_rel(e)
        if not m: return names

        if m.is_a("IfcMaterial"):
            if m.Name: names.append(m.Name)

        # IfcMaterialLayerSetUsage / IfcMaterialLayerSet
        for attr in ("ForLayerSet", "MaterialLayers", "MaterialLayerSet"):
            layers = getattr(m, attr, None)
            if layers:
                seq = layers if isinstance(layers, list) else getattr(layers, "MaterialLayers", [])
                for lyr in seq:
                    mat = getattr(lyr, "Material", None)
                    if mat and mat.Name: names.append(mat.Name)

        # IfcMaterialConstituentSet
        cset = getattr(m, "MaterialConstituentSet", None) or getattr(m, "MaterialConstituents", None)
        if cset:
            seq = cset if isinstance(cset, list) else getattr(cset, "MaterialConstituents", [])
            for c in seq:
                mat = getattr(c, "Material", None)
                if mat and mat.Name: names.append(mat.Name)

        if not names:
            t = self._type_of(e)
            if t:
                names = self.materials(t)

        return list(dict.fromkeys(names))

    def material_density(self, e:entity_instance) -> Optional[float]:
        """
        Return mass density (kg/m3) if available on any associated material or its properties.
        Tries (in order): Pset_MaterialCommon.MassDensity, old Ifc*MaterialProperties, and type-level.
        """
        def _density_from_mat(mat) -> Optional[float]:
            for rel in getattr(mat, "HasProperties", []):
                # IfcMaterialProperties is legacy umbrella; try to unwrap properties
                props = getattr(rel, "Properties", [])
                for p in props:
                    if p.is_a("IfcPropertySingleValue") and p.Name in ("MassDensity","Density"):
                        v = getattr(p, "NominalValue", None)
                        return getattr(v, "wrappedValue", None) if v else None
            # IfcMaterial has HasProperties but sometimes densities live in IfcPropertySet
            # attached via associations
            # psets from element referencing material is unreliable
            return None

        m = self._mat_rel(e)
        if m:
            # Single
            if m.is_a("IfcMaterial"):
                d = _density_from_mat(m)
                if d: return d
            # Layer set
            for attr in ("ForLayerSet", "MaterialLayers", "MaterialLayerSet"):
                layers = getattr(m, attr, None)
                if layers:
                    seq = layers if isinstance(layers, list) else getattr(layers, "MaterialLayers", [])
                    # Return first available density
                    for lyr in seq:
                        mat = getattr(lyr, "Material", None)
                        if mat:
                            d = _density_from_mat(mat)
                            if d: return d
            # Constituents
            cset = getattr(m, "MaterialConstituentSet", None) or getattr(m, "MaterialConstituents", None)
            if cset:
                seq = cset if isinstance(cset, list) else getattr(cset, "MaterialConstituents", [])
                for c in seq:
                    mat = getattr(c, "Material", None)
                    if mat:
                        d = _density_from_mat(mat)
                        if d: return d

        # try type-level
        t = self._type_of(e)
        if t and t is not e:
            return self.material_density(t)

        return None

    def get_pset_value(self, e:entity_instance, pset: str, prop: str):
        """Direct single prop fetch."""
        return self._psets(e).get(pset, {}).get(prop)

    def get_material_layers(self, e:entity_instance):
        """Return IfcMaterialLayer list if present (or [])."""
        m = self._mat_rel(e)
        if not m: return []
        for attr in ("ForLayerSet", "MaterialLayers", "MaterialLayerSet"):
            layers = getattr(m, attr, None)
            if layers:
                return layers if isinstance(layers, list) else (getattr(layers, "MaterialLayers", []))
        return []

    def has_rel_fills_opening(self, e:entity_instance) -> bool:
        """Does this element fill an opening (e.g., windows/doors)?"""
        for rel in getattr(e.get_info(), "FillsVoids", []):
            if rel.is_a("IfcRelFillsElement"): return True
        return False

    def host_of_fill(self, e:entity_instance):
        """Return the host element this fill belongs to (wall/roof), if any."""
        for rel in getattr(e.get_info(), "FillsVoids", []):
            o = getattr(rel, "RelatingOpeningElement", None)
            if o:
                host_rel = getattr(o, "VoidsElements", [])
                for r in host_rel:
                    return getattr(r, "RelatingBuildingElement", None)
        return None
    
    # not applied because focus is determinstic
    # def in_distribution_system(self, e:entity_instance, system_token: str) -> bool:
    #     """IfcRelAssignsToGroup → IfcSystem/IfcDistributionSystem membership"""
    #     # potential to update this for system-like 
    #     tok = (system_token or "").lower()
    #     for rel in getattr(e.get_info(), "HasAssignments", []):
    #         grp:entity_instance|None = getattr(rel, "RelatingGroup", None)
    #         if not grp: continue
    #         if grp.is_a("IfcSystem") or grp.is_a("IfcDistributionSystem"):
    #             if tok in (getattr(grp, "Name", "") or "").lower(): return True
    #             if tok in (getattr(grp, "Description", "") or "").lower(): return True
    #             pt = getattr(grp, "PredefinedType", None)
    #             if pt and tok in str(pt).lower(): return True

    #     for port in getattr(e.get_info(), "HasPorts", []):
    #         # IfcRelConnectsPortToElement / IfcRelConnectsPorts exist; try walking Connections
    #         for cp in getattr(port, "ConnectedTo", []):
    #             other = getattr(cp, "RelatedPort", None) or getattr(cp, "RelatingPort", None)
    #             if not other: continue
    #             owner = getattr(other, "ContainedIn", None)
    #             if owner and self.in_distribution_system(owner, system_token):  # recurse
    #                 return True
    #     return False

    def neighbors(self, e:entity_instance, radius_m: float = 2.0) -> List[Any]:
        # this function is bad because it targets spatial containment.
        # spatial containment can have boundary of 2 floors
        # TODO make the neighbors topological.
        cont = self.spatial_container(e)
        if not cont: return []
        out = []
        for rel in getattr(cont.get_info(), "ContainsElements", []):
            for x in rel["RelatedElements"]:
                if x.id() != e.id():
                    out.append(x)
        return out


    # SPECIALIZED IDENTIFIERS      


    # PARAPET DETECTOR
    # this is heuristic by a big part and isnt included in the results of prototype in article
    def is_parapet(self, e:entity_instance) -> bool:
        """
        Heuristics for parapet 
        Returns True based on following order
          A) IfcWall/Type PredefinedType == PARAPET (if authoring tool used it).
          B) Name/classification
          D) External element (IsExternal or space-boundary heuristic).
          E) Roof/balcony context: ancestor roof, roof-slab neighbor, or storey/space name says "roof/terrace/balcony".
        """
        if not hasattr(e, "is_a") or not (e.is_a("IfcWall") or e.is_a("IfcWallStandardCase")):
            return False

        # A) enum on element or its type
        pt = getattr(e.get_info(), "PredefinedType", None)
        if str(pt).upper() == "PARAPET":
            return True
        t = self._type_of(e)
        if t and str(getattr(t, "PredefinedType", None)).upper() == "PARAPET":
            return True

        # D) externality
        ext = self.is_external(e)

        # E) context: roof/balcony
        ctx = False
        # E1: any ancestor is a roof
        for anc in self.aggregated_ancestors(e):
            if hasattr(anc, "is_a") and anc.is_a("IfcRoof"):
                ctx = True; break
        # E2: neighbors include a roof slab / roof object
        # function is bad TODO - uncomment when function makes sense
        # if not ctx:
        #   neighbours=self.neighbors(e)
        #   if(neighbours):
        #     for n in neighbours:
        #         if hasattr(n, "is_a") and (n.is_a("IfcRoof") or self.is_roof_slab(n)):
        #             ctx = True; break
        # E3: storey/space naming hints
        # if not ctx:
        #     cont = self.spatial_container(e)
        #     if cont:
        #         sn = ((getattr(cont, "Name", "") or "") + " " + (getattr(cont, "LongName", "") or "")).lower()
        #         if any(t in sn for t in ("roof", "terrace", "balcony", "rooftop", "stogo", "teras")):
        #             ctx = True
        return False

    def is_in_curtainwall_panel(self, e:entity_instance) -> bool:
        # TODO this function is relevant for window assembly fix the check functions.
        """
        True if itself a curtain-wall panel or lives inside curtain wall assembly.
          A) IfcPlate/Type PredefinedType == CURTAIN_PANEL (IFC4).
          B) Any aggregated ancestor is an IfcCurtainWall.
          C) Classification/name suggest curtain wall panel and ancestor is plate/member.
          D) window/plate filling an opening whose host is an IfcCurtainWall
        """
        if not hasattr(e, "is_a"):
            return False

        # A) direct plate predefined type
        if e.is_a("IfcPlate"):
            pt = getattr(e.get_info(), "PredefinedType", None)
            if str(pt).upper() == "CURTAIN_PANEL":
                return True
            # type-level predefined
            t = self._type_of(e)
            if t and str(getattr(t, "PredefinedType", None)).upper() == "CURTAIN_PANEL":
                return True

        # B) any ancestor is a curtain wall
        for anc in self.aggregated_ancestors(e):
            if hasattr(anc, "is_a") and anc.is_a("IfcCurtainWall"):
                return True

        # C) name/classification + context
        if e.is_a("IfcPlate") or e.is_a("IfcMember") or e.is_a("IfcFillingElement"):
            for anc in self.aggregated_ancestors(e):
                if anc.is_a("IfcCurtainWall") or anc.is_a("IfcPlate") or anc.is_a("IfcMember"):
                    return True

        return False

    # LCA related
    def parse_element_EII(self, el:entity_instance):
        """
        Parse ONLY Pset_EnvironmentalImpactIndicators for one element (instance first, then type),
        and return a concise result incl. L4A score ladder:
        1.0 = numeric EI value + explicit unit (in IFC)
        0.6 = URL reference 
        0.2 = code reference 
        0.0 = none
        """
        TARGET = {"GWP", "GWP_Total", "GlobalWarmingPotential"}

        def _type_obj(x):
            for r in (getattr(x, "IsDefinedBy", [])):
                if r and r.is_a("IfcRelDefinesByType"):
                    return getattr(r, "RelatingType", None)
            return None
        ps = None
        try:
            ps = ifcEl.get_pset(el, "Pset_EnvironmentalImpactIndicators", verbose=True)
            if not ps: ps = ifcEl.get_pset(el, "Pset_EnvironmentalImpactValues", verbose=True)
        except:
            print("error fetching environmental impact pset")
        has_val_unit = False#'ClimateChangePerUnit' in ps# or getattr(ps, 'ClimateChangePerUnit', None)
        has_url=False
        has_code=False
        vals = {}
        if ps:
            has_val_unit = 'ClimateChangePerUnit' in ps
            has_url = 'FunctionalUnitReference' in ps# or getattr(ps, 'FunctionalUnitReference', None) is not None
            has_code = "Reference" in ps or "Name" in ps# or getattr(ps, 'Reference', None) is not None or getattr(ps, 'Name', None) is not None
            for p in (getattr(ps, "HasProperties", [])):
                name = getattr(p, "Name", None)
                if p.is_a("IfcPropertySingleValue"):
                    nom = getattr(p, "NominalValue", None)
                    unit = getattr(p, "Unit", None)
                    v = getattr(nom, "wrappedValue", nom)
                    num = float(v) if isinstance(v, (int, float)) else None
                    vals[name] = {"numeric": num, "has_unit": bool(unit)}

        
        score = 1.0 if has_val_unit else (0.6 if has_url else (0.2 if has_code else 0.0))

        return {
            "score": score,
            "has_pset": bool(ps),
            "pset_source": "Element",
            "has_val_unit": has_val_unit,
            "has_url": has_url,
            "has_code": has_code,
            "values": vals
        }


    def epd_link(self, e:entity_instance) -> Optional[str]:
        """Find a document/url that looks like an EPD (IfcRelAssociatesDocument)."""
        for rel in getattr(e.get_info(), "HasAssociations", []):
            doc = getattr(rel, "RelatingDocument", None)
            if not doc: continue
            if doc.is_a("IfcDocumentReference"):
                loc = getattr(doc, "Location", "")
                name = getattr(doc, "Name", "")
                if "epd" in (loc.lower()+name.lower()):
                    return loc or name
        # type-level document
        t = self._type_of(e)
        if t: return self.epd_link(t)
        return None

    def type_epd_link(self, e:entity_instance) -> Optional[str]:
        t = self._type_of(e)
        return self.epd_link(t) if t else None

    # def material_mappable(self, e:entity_instance) -> bool:\
    # incomplete, but also unused checks thus ignore
    #     return bool(self.materials(e))

    def has_compatible_qto_unit(self, e:entity_instance, expect: Tuple[str, ...]) -> bool:
        """
        Infers unit family from Qto name (e.g., 'NetVolume' m³). Does NOT read IFC unit declarations.
        """
        exp = tuple(s.lower() for s in expect)
        q_names = ("NetVolume","GrossVolume","Volume","Mass","Weight","Count","Length","Area","CrossSectionArea")
        for qn in q_names:
            v = self.qto_value(e, qn)
            if v is not None:
                # map qto to implied unit family
                fam = {
                    "Volume": ("m3",), "NetVolume": ("m3",), "GrossVolume": ("m3",),
                    "Mass": ("kg",), "Weight": ("kg",),
                    "Count": ("pcs",),
                    "Area": ("m2",), "CrossSectionArea": ("m2",),
                    "Length": ("m","m1")
                }.get(qn, ())
                if any(u in exp for u in fam): return True
        # fallbacks: If none found but element has materials, allow
        return False
      
    def spatial_container(self, e:entity_instance):
        """
        Resolve the spatial container (IfcSpace/Storey/Building/Site) of element `e`.
        Strategy:
          1) Direct IfcRelContainedInSpatialStructure (usual case).
          2) Walk up one or more aggregation levels (child parts inherit parent’s container).
          3) If `e` is a filling (window/door), resolve host and use its container.
          4) If `e` itself is spatial, return it.
        Returns the spatial element or None if not resolvable.
        """
        # 1) direct containment
        for rel in getattr(e.get_info(), "ContainedInStructure", []):
            cont = getattr(rel, "RelatingStructure", None)
            if cont:
                return cont

        # 2) climb via decomposition
        parent = self.aggregated_parent(e)
        if parent:
            sc = self.spatial_container(parent)
            if sc:
                return sc

        if hasattr(e, "is_a") and e.is_a().startswith("IfcSpatial"):
            return e

        return None

    # TOKEN BASED GUESSING IS NOT A FOCUS THUS FAR. IGNORE
    # ================== STRING HELPERS USED IN RECOGNITION ==================

    def name_contains(self, e:entity_instance, toks: Iterable[str]) -> bool:
        nm = (getattr(e.get_info(), "Name", "") or "") + " " + (getattr(e.get_info(), "Description", "") or "")
        nml = nm.lower()
        return any(t.lower() in nml for t in toks)


    def _boolish(self, v) -> bool | None:
        """Nested value check attempt to bool conversion."""
        if v is None:
            return None
        # IfcLogical may expose as .value or python bool already
        if isinstance(v, bool):
            return v
        try:
            # if wrapped value
            w = getattr(v, "wrappedValue", v)
        except Exception:
            w = v
        if isinstance(w, bool):
            return w
        if isinstance(w, (int, float)):
            return bool(w)
        s = str(w).strip().lower()
        # unfortunate token checking, I think this is feasible.
        if s in ("true", "t", "yes", "y"):
            return True
        if s in ("false", "f", "no", "n"):
            return False
        return None


    def is_external(self, e:entity_instance) -> bool:
        """
        Resolve whether a building element is external.
        Strategy:
          A) Direct Pset_*Common.IsExternal on element or its Type.
          B) If it's a filling (window/door), inherit from host element (wall/roof/slab).
          C) Space-boundary heuristic: if any side borders exterior (one side missing space, or adjacent space marked external).
        Default False if not resolvable.
        """
        if not hasattr(e, "is_a"):
            return False

        # A) Direct property on element / type (works for Wall/Door/Window/Slab/Roof/Covering/CurtainWall/Proxy)
        psets = (
            "Pset_WallCommon", "Pset_DoorCommon", "Pset_WindowCommon",
            "Pset_SlabCommon", "Pset_RoofCommon", "Pset_CoveringCommon",
            "Pset_CurtainWallCommon", "Pset_BuildingElementProxyCommon"
        )
        for ps in psets:
            v = self.get_pset_value(e, ps, "IsExternal")
            b = self._boolish(v)
            if b is not None:
                return b
        # type-level
        t = self._type_of(e)
        if t:
            for ps in psets:
                v = self.get_pset_value(t, ps, "IsExternal")
                b = self._boolish(v)
                if b is not None:
                    return b

        # B) Fillings inherit host (windows/doors/skylights)
        if self.has_rel_fills_opening(e):
            host = self.host_of_fill(e)
            if host:
                bh = self.is_external(host)
                return bool(bh)

        # As a very last resort: host element type hint
        if e.is_a("IfcRoof"):
            return True

        return False

    # ================== FILL (WINDOW/DOOR) → HOST ELEMENT ==================

    def fill_host(self, e:entity_instance):
        """
        Return the building element that hosts a filling (e.g., IfcDoor/IfcWindow).
        Tries:
          1) e.FillsVoids -> IfcOpeningElement -> VoidsElements -> RelatingBuildingElement
          2) If e is an IfcOpeningElement, step (1) directly.
          3) Walk up aggregation once (in case the filling is a subpart).
        Returns the host element or None if not resolvable.
        """
        # 1) Normal case: filling (door/window/etc.)
        for relfill in getattr(e.get_info(), "FillsVoids", []):
          opening = getattr(relfill, "RelatingOpeningElement", None)
          if not opening:
              continue
          for relvoid in getattr(opening, "VoidsElements", []):
              host = getattr(relvoid, "RelatingBuildingElement", None)
              if host:
                  return host

        # 2) If the input is itself an opening, resolve its host
        if hasattr(e, "is_a") and e.is_a("IfcOpeningElement"):
          for relvoid in getattr(e.get_info(), "VoidsElements", []):
              host = getattr(relvoid, "RelatingBuildingElement", None)
              if host:
                  return host

        # 3) Sometimes the modeled filling is a child of a “window/door” container
        parent = self.aggregated_parent(e)
        if parent:
            return self.fill_host(parent)

        return None

    # safe aggregation
    def aggregated_parent(self, e:entity_instance):
        """
        Return the immediate parent in an IfcRelAggregates relationship,
        or None if the element is a top-level object.
        """
        for rel in getattr(e.get_info(), "Decomposes", []):
            # IfcRelAggregates has attribute RelatingObject
            parent = getattr(rel, "RelatingObject", None)
            if parent:
                return parent
        return None

    def aggregated_ancestors(self, e:entity_instance) -> Generator[entity_instance, entity_instance, None]:
        """
        Walk up the decomposition chain and yield all parents until the root.
        Useful to inherit properties/containment from a container.
        """
        cur = self.aggregated_parent(e)
        while cur is not None:
            yield cur
            cur = self.aggregated_parent(cur)

    def nested_parent(self, e: entity_instance):
        """
        Return the immediate parent in an IfcRelNests relationship, if present.
        """
        for rel in getattr(e, "Nests", []) or []:
            parent = getattr(rel, "RelatingObject", None)
            if parent:
                return parent
        return None

    def nested_ancestors(self, e: entity_instance) -> Generator[entity_instance, entity_instance, None]:
        """
        Walk up the nesting chain and yield all parents until the root.
        """
        cur = self.nested_parent(e)
        while cur is not None:
            yield cur
            cur = self.nested_parent(cur)

    def is_facade_member_candidate(self, e: entity_instance) -> bool:
        """
        Narrow deterministic candidate check for facade framing members.
        """
        if not e or not hasattr(e, "is_a") or not e.is_a("IfcMember"):
            return False
        return str(getattr(e, "PredefinedType", "") or "").upper() in {"MULLION", "TRANSOM"}

    def _group_assignments(self, e: entity_instance) -> List[entity_instance]:
        groups = []
        for rel in getattr(e, "HasAssignments", []) or []:
            if not rel or not rel.is_a("IfcRelAssignsToGroup"):
                continue
            grp = getattr(rel, "RelatingGroup", None)
            if grp:
                groups.append(grp)
        return groups

    def _has_explicit_curtain_wall_type(self, e: entity_instance) -> bool:
        typ = self._type_of(e)
        if not typ:
            return False
        return typ.is_a("IfcCurtainWallType")

    def facade_member_semideterministic_context(self, e: entity_instance) -> dict[str, Any]:
        """
        TODO: For future semi-deterministic / LLM-assisted facade-member review only.
        This helper deliberately collects explicit metadata 
        using them for deterministic category routing.
        """
        typ = self._type_of(e)
        refs = self._class_refs(e)
        docs = []
        for target in (e, typ):
            if not target:
                continue
            for rel in getattr(target, "HasAssociations", []) or []:
                if rel and rel.is_a("IfcRelAssociatesDocument"):
                    doc = getattr(rel, "RelatingDocument", None)
                    if doc:
                        docs.append(
                            {
                                "ifc_class": doc.is_a() if hasattr(doc, "is_a") else "",
                                "name": getattr(doc, "Name", None),
                                "description": getattr(doc, "Description", None),
                                "identification": getattr(doc, "Identification", None),
                                "location": getattr(doc, "Location", None),
                            }
                        )

        groups = self._group_assignments(e)
        return {
            "predefined_type": str(getattr(e, "PredefinedType", "") or ""),
            "name": getattr(e, "Name", None),
            "description": getattr(e, "Description", None),
            "object_type": getattr(e, "ObjectType", None),
            "materials": self.materials(e),
            "is_external": self.is_external(e),
            "spatial_container_class": self.spatial_container(e).is_a() if self.spatial_container(e) else None,
            "aggregated_ancestor_classes": [anc.is_a() for anc in self.aggregated_ancestors(e)],
            "nested_ancestor_classes": [anc.is_a() for anc in self.nested_ancestors(e)],
            "group_classes": [grp.is_a() for grp in groups],
            "type": {
                "ifc_class": typ.is_a() if typ and hasattr(typ, "is_a") else None,
                "name": getattr(typ, "Name", None) if typ else None,
                "description": getattr(typ, "Description", None) if typ else None,
                "element_type": getattr(typ, "ElementType", None) if typ else None,
            },
            "classifications": [
                {
                    "ifc_class": ref.is_a() if hasattr(ref, "is_a") else "",
                    "name": getattr(ref, "Name", None),
                    "description": getattr(ref, "Description", None),
                    "identification": getattr(ref, "Identification", None),
                    "source_name": getattr(getattr(ref, "ReferencedSource", None), "Name", None),
                }
                for ref in refs
            ],
            "documents": docs,
        }

    def belongs_to_curtain_wall_explicitly(self, e: entity_instance, max_depth: int = 6) -> bool:
        """
        Deterministic curtain-wall attribution based only on explicit IFC structure.
        """
        if not e or not hasattr(e, "is_a"):
            return False
        if e.is_a("IfcCurtainWall"):
            return True

        depth = 0
        for ancestor in self.aggregated_ancestors(e):
            if ancestor and ancestor.is_a("IfcCurtainWall"):
                return True
            depth += 1
            if depth >= max_depth:
                break

        depth = 0
        for ancestor in self.nested_ancestors(e):
            if ancestor and ancestor.is_a("IfcCurtainWall"):
                return True
            depth += 1
            if depth >= max_depth:
                break

        for group in self._group_assignments(e):
            if group.is_a("IfcCurtainWall"):
                return True

        return self._has_explicit_curtain_wall_type(e)

    def curtain_wall_gap_reasons(self, e: entity_instance) -> List[str]:
        """
        Compact reason summary for facade-member candidates that lack explicit CW evidence.
        """
        reasons: List[str] = []
        pdt = str(getattr(e, "PredefinedType", "") or "").upper()
        if pdt:
            reasons.append(f"PredefinedType={pdt}")

        has_cw_ancestor = any(anc and anc.is_a("IfcCurtainWall") for anc in self.aggregated_ancestors(e))
        if not has_cw_ancestor:
            reasons.append("no curtain-wall ancestor")

        has_nested_parent = self.nested_parent(e) is not None
        if not has_nested_parent:
            reasons.append("no nesting parent")

        has_group = bool(self._group_assignments(e))
        if not has_group:
            reasons.append("no group assignment")

        if not self._has_explicit_curtain_wall_type(e):
            reasons.append("no explicit curtain-wall type")
        reasons.append("semi-deterministic review required for metadata-only evidence")

        return reasons

    # Need a betterPset, this is a crawler
    # function is just unnecessary generalization and can remove later
    def pset(self, e:entity_instance, pset, prop): return self.get_pset_value(e, pset, prop)
    
    # VECTORS
        # ============== WORLD POSITION (HEURISTIC, NO GEOMETRY ENGINE) ==============

    def _to_float(self, v):
        """Coerce IFC wrapped values / strings to float when possible."""
        if v is None:
            return None
        try:
            w = getattr(v, "wrappedValue", v)
        except Exception:
            w = v
        try:
            return float(w)
        except Exception:
            return None

    def _placement_local_vector(self, plc:entity_instance) -> tuple[float, float, float]:
        """
        Extract local translation vector (x,y,z) from an IfcLocalPlacement's RelativePlacement.
        Ignores rotation; returns (0,0,0) if not resolvable.
        """
        try:
            rp:entity_instance|None = getattr(plc, "RelativePlacement", None)
            if not rp:
                return (0.0, 0.0, 0.0)
            # Axis2Placement3D → Location(Coordinates[3])
            if rp.is_a("IfcAxis2Placement3D"):
                loc = getattr(rp, "Location", None)
                if loc and getattr(loc, "Coordinates", None):
                    coords = loc.Coordinates
                    x = self._to_float(coords[0]) or 0.0
                    y = self._to_float(coords[1]) or 0.0
                    z = self._to_float(coords[2]) or 0.0
                    return (x, y, z)
            # Axis2Placement2D → Location(Coordinates[2])
            if rp.is_a("IfcAxis2Placement2D"):
                loc = getattr(rp, "Location", None)
                if loc and getattr(loc, "Coordinates", None):
                    coords = loc.Coordinates
                    x = self._to_float(coords[0]) or 0.0
                    y = self._to_float(coords[1]) or 0.0
                    return (x, y, 0.0)
        except Exception:
            pass
        return (0.0, 0.0, 0.0)

    def _sum_placement_chain(self, e:entity_instance) -> tuple[float, float, float] | None:
        """
        Walk ObjectPlacement → PlacementRelTo chain, summing local translations.
        Returns (x,y,z) or None if no placement found anywhere (will try fallbacks).
        """
        # climb via aggregated parents if element lacks a placement
        cur = e
        visited = 0
        while cur and visited < 4:  # avoid deep loops; 4 is enough in practice
            plc = getattr(cur.get_info(), "ObjectPlacement", None)
            if plc:
                # sum up the chain
                sx = sy = sz = 0.0
                p = plc
                guard = 0
                while p and guard < 16:
                    x, y, z = self._placement_local_vector(p)
                    sx += x; sy += y; sz += z
                    p = getattr(p, "PlacementRelTo", None)
                    guard += 1
                return (sx, sy, sz)
            # try parent container (parts often inherit container placement)
            cur = self.aggregated_parent(cur)
            visited += 1
        return None

    def _elev_from_storey(self, e) -> float | None:
        """
        As a fallback, use the containing storey elevation if available.
        """
        cont = self.spatial_container(e)
        if cont and hasattr(cont, "is_a") and cont.is_a("IfcBuildingStorey"):
            val = getattr(cont, "Elevation", None)
            return self._to_float(val)
        return None

    def geom_axis(self, e:entity_instance, axis: str = "Z") -> float | None:
        """
        Return world-ish coordinate along axis ('X'/'Y'/'Z') by summing local placements.
        Ignores rotations/scales. Good heuristic for ranking (e.g., lowest slab).
        """
        axis = (axis or "Z").upper()
        vec = self._sum_placement_chain(e)
        if vec is not None:
            if axis == "X": return vec[0]
            if axis == "Y": return vec[1]
            return vec[2]  # Z default
        # fallback: storey elevation (Z only)
        if axis == "Z":
            return self._elev_from_storey(e)
        return None

    def geom_z(self, e) -> float | None:
        return self.geom_axis(e, "Z")

    def geom_y(self, e) -> float | None:
        return self.geom_axis(e, "Y")

    # def building_storey_of(self, e: entity_instance) -> Optional[entity_instance]:
    #     """Return the IfcBuildingStorey that contains `e` (via space/container/ancestors)."""
    #     cont = self.spatial_container(e)
    #     # If element is in a space, climb to the storey
    #     if cont and hasattr(cont, "is_a") and cont.is_a("IfcSpace"):
    #         # Space.Decomposes -> RelatingObject (storey)
    #         for rel in getattr(cont, "Decomposes", []) or []:
    #             st:entity_instance = getattr(rel, "RelatingObject", None)
    #             if st and hasattr(st, "is_a") and st.is_a("IfcBuildingStorey"):
    #                 return st
    #     # If element is directly contained in a storey
    #     if cont and hasattr(cont, "is_a") and cont.is_a("IfcBuildingStorey"):
    #         return cont
    #     # Try ancestors (parts inherit container)
    #     for anc in self.aggregated_ancestors(e):
    #         cont2 = self.spatial_container(anc)
    #         if cont2 and hasattr(cont2, "is_a") and cont2.is_a("IfcBuildingStorey"):
    #             return cont2
    #     return None

    # def storey_elevation(self, storey: entity_instance) -> Optional[float]:
    #     """Get IfcBuildingStorey.Elevation as float (if present)."""
    #     return self._to_float(getattr(storey, "Elevation", None))

    # def _ordered_storeys(self) -> List[entity_instance]:
    #     """All building storeys ordered by Elevation (ascending)."""
    #     sts = list(self.iter_by_type("IfcBuildingStorey"))
    #     pairs = [(st, self.storey_elevation(st)) for st in sts]
    #     pairs = [(st, z if z is not None else 0.0) for st, z in pairs]
    #     pairs.sort(key=lambda t: t[1])
    #     return [st for st, _ in pairs]

    # potential function to figure out semideterministically foundation slab but i couldnt figure out how to properly validate.
    # def has_space_below(self, slab: entity_instance, tol: float = 0.05) -> bool:
    #     """
    #     Heuristic: a slab is 'suspended' if there is a storey/space **below** it.
    #     Strategy:
    #       1) Find the slab's storey and its elevation.
    #       2) Find the next-lower storey (by Elevation).
    #       3) If that lower storey contains any internal IfcSpace → True.
    #     Notes: no geometry; this is a level-to-level test that works well for typical models.
    #     """
    #     if not hasattr(slab, "is_a") or not slab.is_a("IfcSlab"):
    #         return False

    #     st = self.building_storey_of(slab)
    #     if not st:
    #         return False

    #     storeys = self._ordered_storeys()
    #     if not storeys:
    #         return False

    #     # locate current storey index
    #     try:
    #         i = storeys.index(st)
    #     except ValueError:
    #         return False

    #     # pick next lower storey if exists
    #     if i <= 0:
    #         return False
    #     lower = storeys[i - 1]

    #     # sanity: ensure lower really is below current
    #     z_cur = self.storey_elevation(st)
    #     z_low = self.storey_elevation(lower)
    #     if z_cur is None or z_low is None or not (z_low < z_cur - tol):
    #         return False

    #     return True
    
    def _has_shape_representation(self,e:entity_instance,*args) -> bool:
        rep = getattr(e, "Representation", None)
        reps = getattr(rep, "Representations", None) if rep else None
        return bool(reps)  # non-empty list

    def _has_relevant_qto(self,e:entity_instance, relevant_qto_types: set[str]) -> bool:
        # Looks for IfcElementQuantity with at least one IfcQuantityArea/Volume/Length/etc.
        rels:list[entity_instance] = getattr(e, "IsDefinedBy", [])
        for rel in rels:
            if not rel or not rel.is_a("IfcRelDefinesByProperties"):
                continue
            q = getattr(rel, "RelatingPropertyDefinition", None)
            if not q or not q.is_a("IfcElementQuantity"):
                continue
            quants = getattr(q, "Quantities", [])
            for qt in quants:
                if qt and qt.is_a() in relevant_qto_types:
                    return True
        return False

    def _has_classification_ref(self,e:entity_instance,*args) -> bool:
        # IfcRelAssociatesClassification -> IfcClassificationReference
        rels:list[entity_instance] = getattr(e, "HasAssociations", [])
        for rel in rels:
            if not rel or not rel.is_a("IfcRelAssociatesClassification"):
                continue
            rc = getattr(rel, "RelatingClassification", None)
            if rc and rc.is_a("IfcClassificationReference"):
                return True
        return False

    def _classification_required_fields_non_null(self,e:entity_instance,*args) -> bool:
        # Deterministic just check existence of required fields on the IfcClassificationReference
       
        rels:list[entity_instance] = getattr(e, "HasAssociations", [])
        for rel in rels:
            if not rel or not rel.is_a("IfcRelAssociatesClassification"):
                continue
            rc:entity_instance|None = getattr(rel, "RelatingClassification", None)
            if not rc or not rc.is_a("IfcClassificationReference"):
                continue
            identification = getattr(rc, "Identification", None)
            if identification is not None:
                return True
        return False

    def _has_material_association(self,e:entity_instance,*args) -> bool:
        rels:list[entity_instance] = getattr(e, "HasAssociations", [])
        return any(rel and rel.is_a("IfcRelAssociatesMaterial") for rel in rels)

    def _has_document_association(self,e:entity_instance,*args) -> bool:
        rels:list[entity_instance] = getattr(e, "HasAssociations", [])
        return any(rel and rel.is_a("IfcRelAssociatesDocument") for rel in rels)

    def _valid_predefined_type(self,e:entity_instance,*args) -> bool:
        pdt = getattr(e, "PredefinedType", None)
        # deterministic enum presence
        return pdt is not None and pdt != "NOTDEFINED"


    # def qto_area(self, e:entity_instance) -> Optional[float]:
    #     """Return NetArea or Area from element quantities."""
    #     for key in ("NetArea", "GrossArea", "Area"):
    #         v = self._qto(e).get(key)
    #         if v: return float(v)
    #     return None

    # def geom_area(self, e:entity_instance) -> Optional[float]:
    #    total surface area, bad approach
    #     return self.get_net_area_m2(e)

    def layer_thickness(self, e:entity_instance) -> Optional[float]:
        """
        Return the thickness of a layered element (wall/slab/etc.).
        Tries (in order):
          1) Sum of material layer thicknesses.
          2) Pset_*Common.Thickness property.
          3) Qto Thickness.
        """
        # (1) Material layers
        layers = self.get_material_layers(e)
        if layers:
            total_thick = 0.0
            for lyr in layers:
                t = getattr(lyr, "LayerThickness", None)
                if t:
                    total_thick += float(t)
            if total_thick > 0:
                return total_thick

        # (2) Pset_*Common.Thickness (depends on element type)
        for pset_name in ("Pset_WallCommon", "Pset_SlabCommon", "Pset_RoofCommon", "Pset_CoveringCommon", "Pset_DoorCommon", "Pset_WindowCommon"):
            v = self.get_pset_value(e, pset_name, "Thickness")
            if v: return float(v)

        # (3) Qto Thickness
        v = self.qto_value(e, "Thickness")
        if v: return float(v)

        return None

    # def bottom_elev(self, e:entity_instance) -> Optional[float]:
    #     """
    #     Return the bottom (lowest Z) elevation of an element.
    #     Uses the world-position heuristic (placement chain) minus geometry half-height.
    #     Returns None if not determinable.
    #     """
    #     # Get element Z (placement-based estimate of center or top)
    #     z_center = self.geom_z(e)
    #     if z_center is None:
    #         return None

    #     # Try to estimate height/depth to compute bottom
    #     height = self.qto_value(e, "Height") or self.qto_value(e, "OverallHeight")
    #     if height:
    #         return z_center - float(height) / 2.0

    #     # If we only have Z but no height info, assume Z is already at bottom
    #     return z_center

    # potential to check for basement walls semideterminstically but again, but i dont think this approach is good altogether anymore?
    # def connected_to_lowest_slab(self, wall:entity_instance) -> bool:
    #     """
    #     Heuristic: check if a wall (typically retaining) is connected to a lowest/base slab.
    #     Tries:
    #       1) Direct connection to an IfcSlab with PredefinedType == BASESLAB.
    #       2) Connection to any IfcSlab at lowest Z elevation in model.
    #       3) Host/aggregation relationships.
    #     """
    #     def _is_base_slab(s):
    #         if not hasattr(s, "is_a") or not s.is_a("IfcSlab"):
    #             return False
    #         pt = getattr(s, "PredefinedType", None)
    #         return str(pt).upper() in ("BASESLAB", "BASEMENT")

    #     # (1) Direct connection to base slab
    #     for rel in getattr(wall, "ConnectedTo", []) or []:
    #         other = getattr(rel, "RelatedElement", None)
    #         if _is_base_slab(other):
    #             return True
    #     for rel in getattr(wall, "ConnectedFrom", []) or []:
    #         other = getattr(rel, "RelatingElement", None)
    #         if _is_base_slab(other):
    #             return True

    #     # (2) Check if any slab in model is at very low Z and connected
    #     lowest_slabs = []
    #     all_slabs = self.iter_by_type("IfcSlab")
    #     if all_slabs:
    #         z_positions = []
    #         for s in all_slabs:
    #             z = self.geom_z(s)
    #             if z is not None:
    #                 z_positions.append((z, s))
    #         if z_positions:
    #             z_positions.sort(key=lambda x: x[0])
    #             # Pick the lowest few (allow some tolerance)
    #             lowest_z = z_positions[0][0]
    #             lowest_slabs = [s for z, s in z_positions if z <= lowest_z + 0.5]

    #         # Check if wall connects to any of these
    #         for slab in lowest_slabs:
    #             for rel in getattr(wall, "ConnectedTo", []) or []:
    #                 if getattr(rel, "RelatedElement", None) is slab:
    #                     return True
    #             for rel in getattr(wall, "ConnectedFrom", []) or []:
    #                 if getattr(rel, "RelatingElement", None) is slab:
    #                     return True

    #     return False
