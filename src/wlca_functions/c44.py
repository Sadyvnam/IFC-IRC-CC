from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 4.4 Loose FF&E
def category_44(ad:CoreType):
    returnDict=CategoryReturn()
    returnDict.issues=[]
    returnDict.categories=[]
    returnDict.overview=IndicatorRow()
    returnDict.overview.category="4.4"
    returnDict.issues.append(IssueRow(
        category_code="4.4",
        category_name="",
        scope="category",
        severity="info",
        message="Loose FF&E is not exported in the pipeline because no deterministic IFC category-membership signal has been adopted."
    ))
    returnDict.overview.issues = 0
    finalize_category_metrics(ad, returnDict, {"4.4": []})
    return returnDict