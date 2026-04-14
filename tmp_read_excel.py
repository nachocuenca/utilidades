import pandas as pd

# Lee la hoja específica del Excel
excel_path = r"c:/Users/ignac/Desktop/utilidadesgit/data/acreedores benioffi.xlsx"
df = pd.read_excel(excel_path, sheet_name="facturas_20260414_124915")
print(df.columns)
print(df.head(5))
