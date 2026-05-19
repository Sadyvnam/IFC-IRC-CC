import logging
import orjson
from typing import Callable
import ifcopenshell

from src.utils import adapt, preindex

logger = logging.getLogger(__name__)

def process_ifc(
    model: ifcopenshell.file,
    run_exploratory_checks: bool = False,
    write_debug_report: bool = False,
):
    ad = adapt(model)
    idx = preindex(ad)

    report = {
        "meta": {
            "schema": ad.schema(),
            "file": ad.file_name(),
            "size_bytes": ad.file_size_bytes(),
        },
        "sections": {}
    }

    if write_debug_report:
        with open("report.json","wb") as f:
            f.write(orjson.dumps(report))
    return report, ad ,idx
