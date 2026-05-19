
from src.classes import CoreType,PreIndex
from src.wlca_category_functions import mk_result
from src.excel.types import CategoryReturn,ConnectionRow,CategoryRow,IssueRow,IndicatorRow
from src.wlca_functions.check_metrics import finalize_category_metrics
# 4.2 Kitchen  equipment
# this is kinda nondeterministic
def category_42(ad: CoreType):
    out = CategoryReturn()
    out.issues = []
    out.categories = []
    out.overview=IndicatorRow()
    out.overview.category="4"
    out.overview.category="4.2"
    out.issues.append(IssueRow(
        category_code="4.2",
        category_name="",
        scope="category",
        severity="info",
        message="Kitchen equipment is not exported in because no deterministic IFC category-membership signal has been found."
    ))
    out.overview.issues = 0
    finalize_category_metrics(ad, out, {"4.2": []})
    return out