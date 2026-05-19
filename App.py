import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import traceback
import os

import ifcopenshell
from src.excel.export import export_excel
from src.excel.types import Report, IssueRow, Overview, overview_from_category_rows
from src.process_ifc import process_ifc

from src.wlca_functions.c11 import category_11
from src.wlca_functions.c21 import category_21
from src.wlca_functions.c22 import category_22
from src.wlca_functions.c24 import category_24
from src.wlca_functions.c25 import category_25
from src.wlca_functions.c26 import category_26
from src.wlca_functions.c28 import category_28
from src.wlca_functions.c31 import category_31
from src.wlca_functions.c32 import category_32
from src.wlca_functions.c33 import category_33
from src.wlca_functions.c41 import category_41
from src.wlca_functions.c42 import category_42
from src.wlca_functions.c43 import category_43
from src.wlca_functions.c44 import category_44
from src.wlca_functions.c45 import category_45
from src.wlca_functions.c46 import category_46
from src.wlca_functions.c511 import category_511
from src.wlca_functions.c512 import category_512
from src.wlca_functions.c513 import category_513
from src.wlca_functions.c521 import category_521
from src.wlca_functions.c522 import category_522
from src.wlca_functions.c524 import category_524
from src.wlca_functions.c531 import category_531
from src.wlca_functions.c532 import category_532
from src.wlca_functions.c541 import category_541
from src.wlca_functions.c55 import category_55
from src.wlca_functions.check_metrics import extend_report_metrics

# Release-facing note:
# Only categories wired in this module are exported to the Excel report.
# BEC 1.2 retaining-wall/basement-scope logic is intentionally deferred from
# standalone active export for now. Deterministic BASESLAB rows are exported
# through category_22() slab routing.
# BEC 2.7 is exported through category_21() wall routing, not category_27().
# Active BEC 5.5 numbering is defined by category_55() in c55.py.


def _rows_for_category(rows, category_code: str):
    return [
        row for row in rows
        if row.category_code == category_code or row.category_code.startswith(f"{category_code}.")
    ]

def process_file_upload(path:str, log) -> ifcopenshell.file | None:
    log("Starting IFC processing...")    

    size = os.path.getsize(path)
    log(f"File size: {size:,} bytes")
    model:ifcopenshell.file | None= None

    report2=Report()
    report2.indicators=[]
    report2.elements=[]
    report2.issues=[]
    report2.overviewTable=[]
    report2.overview=Overview()
    
    model = ifcopenshell.open(path)
    report2.overview.schema=model.schema
    report2.overview.buildingStories=len(model.by_type("IFCBUILDINGSTOREY"))
    
    report, ad ,idx = process_ifc(model)
    unknownElements=model.by_type('IfcBuildingElementProxy')
    
    log("Processing for BEC 1.1")    
    category_11_data=category_11(ad,idx)
    report2.overviewTable.append(overview_from_category_rows(category_11_data.categories,category_name="1.1",name="Foundations and piling"))
    report2.elements.extend(category_11_data.categories)
    report2.issues.extend(category_11_data.issues)
    report2.overview.indicators.append(category_11_data.overview)
    extend_report_metrics(report2, category_11_data)
    
    log("BEC 1.2 retaining-wall detection is deferred; deterministic BASESLAB rows are processed through BEC 2.2 slab routing.")
    
    log("Processing for BEC 2.1 and 2.7")  
    category_21_data=category_21(ad)
    category_21_rows = _rows_for_category(category_21_data.categories, "2.1")
    category_27_rows = _rows_for_category(category_21_data.categories, "2.7")
    report2.overviewTable.append(overview_from_category_rows(category_21_rows,category_name="2.1",name="Frame"))
    report2.overviewTable.append(overview_from_category_rows(category_27_rows,category_name="2.7",name="Internal walls"))
    report2.elements.extend(category_21_data.categories)
    report2.issues.extend(category_21_data.issues)
    report2.overview.indicators.extend(category_21_data.overviews)
    extend_report_metrics(report2, category_21_data)
    
    log("Processing for BEC 1.2, 2.2 and 2.3")  
    category_22_data=category_22(ad)
    report2.elements.extend(category_22_data.categories)
    report2.issues.extend(category_22_data.issues)
    category_12_rows = _rows_for_category(category_22_data.categories, "1.2")
    category_22_rows = _rows_for_category(category_22_data.categories, "2.2")
    category_23_rows = _rows_for_category(category_22_data.categories, "2.3")
    report2.overviewTable.append(overview_from_category_rows(category_12_rows,category_name="1.2",name="Basement retaining walls and lowest slab"))
    report2.overviewTable.append(overview_from_category_rows(category_22_rows,category_name="2.2",name="Upper floors"))
    report2.overviewTable.append(overview_from_category_rows(category_23_rows,category_name="2.3",name="Roof structure"))
    report2.overview.indicators.extend(category_22_data.overviews)
    extend_report_metrics(report2, category_22_data)
    
    log("Processing for BEC 2.4")  
    category_24_data=category_24(ad)
    report2.elements.extend(category_24_data.categories)
    report2.issues.extend(category_24_data.issues)
    report2.overviewTable.append(overview_from_category_rows(category_24_data.categories,category_name="2.4",name="Stairs, ramps and safety guarding"))
    report2.overview.indicators.append(category_24_data.overview)
    extend_report_metrics(report2, category_24_data)
    
    log("Processing for BEC 2.5")  
    category_25_data=category_25(ad)
    report2.elements.extend(category_25_data.categories)
    report2.issues.extend(category_25_data.issues)
    report2.overview.indicators.append(category_25_data.overview)
    extend_report_metrics(report2, category_25_data)
    report2.overviewTable.append(overview_from_category_rows(category_25_data.categories,category_name="2.5",name="External envelope including roof finishes"))
    
    log("Processing for BEC 2.6")  
    category_26_data=category_26(ad)
    report2.elements.extend(category_26_data.categories)
    report2.issues.extend(category_26_data.issues)
    report2.overview.indicators.append(category_26_data.overview)
    extend_report_metrics(report2, category_26_data)
    report2.overviewTable.append(overview_from_category_rows(category_26_data.categories,category_name="2.6",name="Windows and ext doors"))

    log("BEC 2.7 internal walls processed through BEC 2.1 wall routing.")
    
    log("Processing for BEC 2.8")  
    category_28_data=category_28(ad)
    report2.elements.extend(category_28_data.categories)    
    report2.issues.extend(category_28_data.issues)
    report2.overview.indicators.append(category_28_data.overview)
    extend_report_metrics(report2, category_28_data)
    report2.overviewTable.append(overview_from_category_rows(category_28_data.categories,category_name="2.8",name="Internal doors"))
    
    log("Processing for BEC 3.1")  
    category_31_data=category_31(ad)
    report2.elements.extend(category_31_data.categories)    
    report2.issues.extend(category_31_data.issues)
    report2.overview.indicators.append(category_31_data.overview)
    extend_report_metrics(report2, category_31_data)
    report2.overviewTable.append(overview_from_category_rows(category_31_data.categories,category_name="3.1",name="Wall finishes"))
    
    log("Processing for BEC 3.2")  
    category_32_data=category_32(ad)
    report2.elements.extend(category_32_data.categories)    
    report2.issues.extend(category_32_data.issues)
    report2.overview.indicators.append(category_32_data.overview)
    extend_report_metrics(report2, category_32_data)
    report2.overviewTable.append(overview_from_category_rows(category_32_data.categories,category_name="3.2",name="Floor finishes"))
    
    log("Processing for BEC 3.3")
    category_33_data=category_33(ad)
    report2.elements.extend(category_33_data.categories)    
    report2.issues.extend(category_33_data.issues)
    report2.overview.indicators.append(category_33_data.overview)
    extend_report_metrics(report2, category_33_data)
    report2.overviewTable.append(overview_from_category_rows(category_33_data.categories,category_name="3.3",name="Ceiling finishes"))
    
    log("Processing for BEC 4")
    category_41_data=category_41(ad)
    report2.elements.extend(category_41_data.categories)    
    report2.issues.extend(category_41_data.issues)
    report2.overview.indicators.append(category_41_data.overview)
    extend_report_metrics(report2, category_41_data)
    report2.overviewTable.append(overview_from_category_rows(category_41_data.categories,category_name="4.1",name="General Furniture fixtures"))

    log("Processing for BEC 4.2")
    category_42_data=category_42(ad)
    report2.elements.extend(category_42_data.categories)
    report2.issues.extend(category_42_data.issues)
    report2.overview.indicators.append(category_42_data.overview)
    extend_report_metrics(report2, category_42_data)
    report2.overviewTable.append(overview_from_category_rows(category_42_data.categories,category_name="4.2",name="Kitchen equipment"))

    log("Processing for BEC 4.3")
    category_43_data=category_43(ad)
    report2.elements.extend(category_43_data.categories)
    report2.issues.extend(category_43_data.issues)
    report2.overview.indicators.append(category_43_data.overview)
    extend_report_metrics(report2, category_43_data)
    report2.overviewTable.append(overview_from_category_rows(category_43_data.categories,category_name="4.3",name="Special equipment"))

    log("Processing for BEC 4.4")
    category_44_data=category_44(ad)
    report2.elements.extend(category_44_data.categories)
    report2.issues.extend(category_44_data.issues)
    report2.overview.indicators.append(category_44_data.overview)
    extend_report_metrics(report2, category_44_data)
    report2.overviewTable.append(overview_from_category_rows(category_44_data.categories,category_name="4.4",name="Loose FF&E"))

    log("Processing for BEC 4.5")
    category_45_data=category_45(ad)
    report2.elements.extend(category_45_data.categories)
    report2.issues.extend(category_45_data.issues)
    report2.overview.indicators.append(category_45_data.overview)
    extend_report_metrics(report2, category_45_data)
    report2.overviewTable.append(overview_from_category_rows(category_45_data.categories,category_name="4.5",name="IT equipment"))

    log("Processing for BEC 4.6")
    category_46_data=category_46(ad)
    report2.elements.extend(category_46_data.categories)
    report2.issues.extend(category_46_data.issues)
    report2.overview.indicators.append(category_46_data.overview)
    extend_report_metrics(report2, category_46_data)
    report2.overviewTable.append(overview_from_category_rows(category_46_data.categories,category_name="4.6",name="Audio and visual"))

    log("Processing for BEC 5.1.1, 5.1.2, 5.1.3")
    category_511_data=category_511(ad,idx)
    report2.elements.extend(category_511_data.categories)    
    report2.issues.extend(category_511_data.issues)
    report2.overview.indicators.append(category_511_data.overview)
    extend_report_metrics(report2, category_511_data)
    report2.overviewTable.append(overview_from_category_rows(category_511_data.categories,category_name="5.1.1",name="Sanitaryware"))
    category_512_data=category_512(ad,idx)
    report2.elements.extend(category_512_data.categories)    
    report2.issues.extend(category_512_data.issues)
    report2.overview.indicators.append(category_512_data.overview)
    extend_report_metrics(report2, category_512_data)
    report2.overviewTable.append(overview_from_category_rows(category_512_data.categories,category_name="5.1.2",name="Cold water systems"))
    category_513_data=category_513(ad,idx)
    report2.elements.extend(category_513_data.categories)    
    report2.issues.extend(category_513_data.issues)
    report2.overview.indicators.append(category_513_data.overview)
    extend_report_metrics(report2, category_513_data)
    report2.overviewTable.append(overview_from_category_rows(category_513_data.categories,category_name="5.1.3",name="Drainage and rainwater"))
    
    log("Processing for BEC 5.2.1")  
    category_521_data=category_521(ad,idx)
    report2.elements.extend(category_521_data.categories)    
    report2.issues.extend(category_521_data.issues)
    report2.overview.indicators.append(category_521_data.overview)
    extend_report_metrics(report2, category_521_data)
    report2.overviewTable.append(overview_from_category_rows(category_521_data.categories,category_name="5.2.1",name="Space heating and hot water"))
    
    log("Processing for BEC 5.2.2")  
    category_522_data=category_522(ad,idx)
    report2.elements.extend(category_522_data.categories)    
    report2.issues.extend(category_522_data.issues)
    report2.overview.indicators.append(category_522_data.overview)
    extend_report_metrics(report2, category_522_data)
    report2.overviewTable.append(overview_from_category_rows(category_522_data.categories,category_name="5.2.2",name="Dedicated cooling installations"))
    
    log("Processing for BEC 5.2.4")  
    category_524_data=category_524(ad,idx)
    report2.elements.extend(category_524_data.categories)    
    report2.issues.extend(category_524_data.issues)
    report2.overview.indicators.append(category_524_data.overview)
    extend_report_metrics(report2, category_524_data)
    report2.overviewTable.append(overview_from_category_rows(category_524_data.categories,category_name="5.2.4",name="Ventilation equipment"))
    
    log("Processing for BEC 5.3.1,.5.3.2")
    category_531_data=category_531(ad,idx)
    report2.elements.extend(category_531_data.categories)    
    report2.issues.extend(category_531_data.issues)
    report2.overview.indicators.append(category_531_data.overview)
    extend_report_metrics(report2, category_531_data)
    report2.overviewTable.append(overview_from_category_rows(category_531_data.categories,category_name="5.3.1",name="Lighting"))
    category_532_data=category_532(ad,idx)
    report2.elements.extend(category_532_data.categories)    
    report2.issues.extend(category_532_data.issues)
    report2.overview.indicators.append(category_532_data.overview)
    extend_report_metrics(report2, category_532_data)
    report2.overviewTable.append(overview_from_category_rows(category_532_data.categories,category_name="5.3.2",name="Electrical services"))
    
    log("Processing for BEC 5.4.1")
    category_541_data=category_541(ad,idx)
    report2.elements.extend(category_541_data.categories)    
    report2.issues.extend(category_541_data.issues)
    report2.overview.indicators.append(category_541_data.overview)
    extend_report_metrics(report2, category_541_data)
    report2.overviewTable.append(overview_from_category_rows(category_541_data.categories,category_name="5.4.1",name="REG/RES"))
    log("Processing for BEC 5.5 (life safety, fuel, lifts, and waste)")
    category_55_data=category_55(ad,idx)
    report2.elements.extend(category_55_data.categories)    
    report2.issues.extend(category_55_data.issues)
    report2.overview.indicators.append(category_55_data.overview)
    extend_report_metrics(report2, category_55_data)
    report2.overviewTable.append(overview_from_category_rows(category_55_data.categories,category_name="5.5",name="Life safety, fuel, lifts, and waste"))
    
    if(len(unknownElements)):
        unknownIssue=IssueRow()
        unknownIssue.category_code="-"
        unknownIssue.message=f"Excluded generic proxy elements without deterministic category routing: {len(unknownElements)}"
        report2.overview.elementsExcluded=len(unknownElements)
        report2.issues.append(unknownIssue)
    
    log("Exporting excel report...")
    export_excel(report2, path.replace('.ifc','.xlsx'))
    log("Excel report exported in the same directory as the ifc file.")
    log(f"Check finished. See excel report for results {path.replace('.ifc','.xlsx')}")
    return model, report, ad ,idx

# ---- GUI ----
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IFC Model Quality Analyzer, for WLCA and Circularity")
        self.geometry("600x320")
        self.resizable(False, False)

        self.selected_file = tk.StringVar(value="No file selected")

        tk.Label(self, text="Choose an .ifc file:").pack(anchor="w", padx=12, pady=(12, 4))

        row = tk.Frame(self)
        row.pack(fill="x", padx=12)
        tk.Entry(row, textvariable=self.selected_file, state="readonly").pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Browse", command=self.browse).pack(side="left", padx=(8, 0))

        btn_row = tk.Frame(self)
        btn_row.pack(fill="x", padx=12, pady=8)
        self.run_btn = tk.Button(btn_row, text="Run", command=self.run_clicked)
        self.run_btn.pack(side="left")
        tk.Button(btn_row, text="Quit", command=self.destroy).pack(side="right")

        tk.Label(self, text="Log:").pack(anchor="w", padx=12)
        self.log_box = tk.Text(self, height=10, state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0,12))

    def browse(self):
        path = filedialog.askopenfilename(
            title="Select IFC file",
            filetypes=[("IFC files", "*.ifc"), ("All files", "*.*")]
        )
        if path:
            self.selected_file.set(path)

    def log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.update_idletasks()

    def run_clicked(self):
        path = self.selected_file.get()
        if not path or not os.path.isfile(path):
            messagebox.showerror("Error", "Please select a valid .ifc file first.")
            return

        # Disable button while running
        self.run_btn.config(state="disabled")
        self.log("Running...")

        def worker():
            try:
                process_file_upload(path, self.log)
            except Exception:
                self.log("ERROR:\n" + traceback.format_exc())
                messagebox.showerror("Processing failed", "See log for details.")
            finally:
                self.run_btn.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
