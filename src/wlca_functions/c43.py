from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 4.3  Special equipment
def category_43(ad:CoreType):
    returnDict=CategoryReturn()
    returnDict.issues=[]
    returnDict.categories=[]
    returnDict.overview=IndicatorRow()
    returnDict.overview.category="4.3"
    returnDict.issues.append(IssueRow(
        category_code="4.3",
        category_name="",
        scope="category",
        severity="info",
        message="Special equipment is not exported in the pipeline because no deterministic IFC category-membership signal has been adopted."
    ))
    returnDict.overview.issues = 0
    finalize_category_metrics(ad, returnDict, {"4.3": []})
    return returnDict