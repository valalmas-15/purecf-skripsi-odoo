import openpyxl

def inspect_file(path, name):
    print(f"=== {name} ===")
    wb = openpyxl.load_workbook(path, data_only=True)
    sheet = wb.active
    print("Dimensions:", sheet.dimensions)
    for r in range(1, 6):
        row_vals = [sheet.cell(row=r, column=c).value for c in range(1, 10)]
        print(f"Row {r}:", row_vals)

inspect_file('/Users/alle/Projects/Odoo17/purecf_erp/data/StoreCafe Expense (purecf.expense).xlsx', 'StoreCafe Expense')
inspect_file('/Users/alle/Projects/Odoo17/purecf_erp/data/Data Pengeluaran April.xlsx', 'Data Pengeluaran April')
