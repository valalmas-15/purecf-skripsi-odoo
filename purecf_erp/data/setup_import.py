import pandas as pd
import json

# Path file Excel Anda
file_path = 'purecf_erp/data/data transaksi purecf - April.xlsx'

print("Membaca data Excel...")
# Membaca sheet utama dan detail (header ada di baris kedua / index 1)
df_trans = pd.read_excel(file_path, sheet_name='Transaksi', header=1)
df_detail = pd.read_excel(file_path, sheet_name='Detail Transaksi', header=1)

# Format tanggal agar seragam
df_trans['date_only'] = pd.to_datetime(df_trans['Tanggal Transaksi'], dayfirst=True).dt.strftime('%Y-%m-%d')
df_trans['dt_parsed'] = pd.to_datetime(df_trans['Tanggal Transaksi'], dayfirst=True).dt.strftime('%Y-%m-%d %H:%M:%S')
df_detail['dt_parsed'] = pd.to_datetime(df_detail['Tanggal Transaksi'], dayfirst=True).dt.strftime('%Y-%m-%d %H:%M:%S')

data = {
    'trans': df_trans.to_dict(orient='records'),
    'detail': df_detail.to_dict(orient='records')
}

# Simpan ke JSON untuk dibaca oleh Odoo Shell
output_path = 'purecf_erp/data/excel_data.json'
with open(output_path, 'w') as f:
    json.dump(data, f)

print(f"Data siap! File tersimpan di {output_path}")
