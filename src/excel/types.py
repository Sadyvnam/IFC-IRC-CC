from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Literal, ClassVar
from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class OverviewRow:
    category:str
    name: str =""
    elementCount:int=0
    has_material:int=0
    has_quantity:int=0
    has_epd:int=0
    nProxies:int=0
@dataclass
class IndicatorRow:
    category: str=''
    l1_score: float=0
    l2_score: float=0
    l3_score: float=0
    l4a_score: float=0
    l4b_score: float=0
    issues: int=0

@dataclass
class CheckMetric:
    category: str = ''
    level: str = ''
    check: str = ''
    title: str = ''
    present: Optional[int] = None
    total: Optional[int] = None
    pct: Optional[float] = None
    empty_scope: bool = False
@dataclass
class Overview:
    file_path: str=''
    schema: str=''
    project_name:str=''
    authors: list = field(default_factory=list)
    #run_timestamp: Optional[datetime]
    indicators: list = field(default_factory=list)
    buildingStories:int=0
    elementsIncluded:int=0
    elementsExcluded:int=0
@dataclass
class IssueRow:
    ifc_guid: str=''
    element_id: Optional[str] = ''
    element_type: str =""
    ifc_class: Optional[str] = ''

    check_id: str=""
    level: str=""
    scope: Literal["element", "category", "model"] = "element"
    category_code: str =""                     # e.g. "1.1", "2.1"
    category_name: Optional[str] = ""     # optional, for readability

    check_code: str = ""
    severity: Literal["info", "warning", "error"] = "warning"
    message: str = ""                       # human-readable description
    whatShouldBeDifferent: str = ""          
    details: str = ''                       # extra context for debugging




from dataclasses import dataclass, field
from typing import Any, Literal, Optional


ElementId = str 

@dataclass
class ConnectionRow:
    # Category context
    category_code: str   =''          
    category_name: Optional[str] = None

    # Joint identity
    joint_id: str        =""               
    joint_type: str      =""              

    connected_element_id: ClassVar[list[str]]=[]

    connected_area_m2: Optional[float] = None
    disassemblable: Optional[bool] = None 

    notes: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)

QualityLevel = Literal["L1", "L2", "L3", "L4a", "L4b"]


@dataclass
class CategoryRow:
    # Category context
    category_code: str     =''              
    category_name: Optional[str] = None     
    subcategory_code: Optional[str] = None  

    # Element identity
    element_id: ElementId = ""
    element_guid: Optional[str] = None
    ifc_class: Optional[str] = None
    description: Optional[str] = None     
    count: int = 1
    count_cantCalcRI: int = 0
    # Core LCA metrics
    material_name: Optional[str] = "" 
    object_type:Optional[str]=""
    volume_m3: float = 0
    area_m2: float = 0
    mass_kg: float = 0    

    # Location/context
    storey: Optional[str] = None
    zone: Optional[str] = None
    system: Optional[str] = None        

    # Quality assessment
    quality_level: Optional[QualityLevel] = None
    missing_material: bool = False
    missing_geometry: bool = False
    other_flags: dict[str, bool] = field(default_factory=dict)

    extra: dict[str, Any] = field(default_factory=dict)

@dataclass
class CategoryReturn:
    issues: list[IssueRow] = field(default_factory=list[IssueRow])
    categories: list[CategoryRow] = field(default_factory=list[CategoryRow])
    connections: list[ConnectionRow] = field(default_factory=list[ConnectionRow])
    overview: IndicatorRow = field(default_factory=IndicatorRow)
    overviews: list[IndicatorRow] = field(default_factory=list[IndicatorRow])
    check_metrics: list[CheckMetric] = field(default_factory=list[CheckMetric])

@dataclass
class Report:
    overview: Overview=field(default_factory=Overview)
    overviewTable: list[OverviewRow]=field(default_factory=list)
    indicators: list[IndicatorRow]=field(default_factory=list)
    issues: list[IssueRow]=field(default_factory=list)
    elements: list[CategoryRow]=field(default_factory=list)
    check_metrics: list[CheckMetric]=field(default_factory=list)
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)
        
        
from typing import Iterable, Optional

def overview_from_category_rows(
    rows: Iterable[CategoryRow],
    *,
    category_name: Optional[str] = None,
    name: Optional[str] = None
) -> OverviewRow:
    """
    Aggregate all CategoryRow entries belonging to ONE category into a single OverviewRow.
    Uses row.count as multiplicity.
    """
    rows = list(rows)

    if category_name is None:
        if rows:
            category_name = rows[0].category_name or rows[0].category_code
        else:
            category_name = ""

    o = OverviewRow(category=category_name,name=name)

    for r in rows:
        n = int(r.count or 0)
        o.elementCount += n

        # material presence
        has_material = (not r.missing_material) and bool((r.material_name or "").strip())
        if has_material:
            o.has_material += n

        # QTO presence
        has_qto = (not r.missing_geometry) and (
            (r.volume_m3 is not None) or (r.area_m2 is not None) or (r.mass_kg is not None)
        )
        if has_qto:
            o.has_quantity += n

        # proxy count
        ifc = (r.ifc_class or "").strip()
        is_proxy = (ifc == "IfcBuildingElementProxy") or ifc.endswith("Proxy")
        if is_proxy:
            o.nProxies += n

        # EPD link: don't have enough info on CategoryRow to compute it deterministically.
        # If `has_epd_link: bool` (or `epd_id: Optional[str]`), then:
        # if r.has_epd_link: o.has_epd += n

    return o
