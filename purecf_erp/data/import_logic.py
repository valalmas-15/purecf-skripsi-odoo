import json
from datetime import datetime, timedelta

# 1. Load data yang sudah disiapkan tadi (path dalam container)
json_path = '/mnt/extra-addons/purecf_erp/data/excel_data.json'
with open(json_path, 'r') as f:
    data = json.load(f)

df_trans = data['trans']
df_detail = data['detail']

# Mapping produk yang sudah ada di Odoo
products = env['product.product'].search([])
product_map = {p.name.lower().strip(): p.id for p in products}

# Mengelompokkan detail berdasarkan ID Transaksi agar pencarian cepat
detail_by_order = {}
for d in df_detail:
    oid = str(d['Id Transaksi'])
    if oid not in detail_by_order:
        detail_by_order[oid] = []
    detail_by_order[oid].append(d)

# Mengelompokkan transaksi berdasarkan tanggal (untuk buat sesi harian)
trans_by_date = {}
for t in df_trans:
    date_str = str(t['date_only'])
    if date_str == 'nan': continue
    if date_str not in trans_by_date:
        trans_by_date[date_str] = []
    trans_by_date[date_str].append(t)

# Konfigurasi POS dan Metode Pembayaran
try:
    config = env.ref('purecf_erp.shop_lahat')
except Exception:
    config = env['pos.config'].search([('name', '=', 'Purecf Lahat')], limit=1)

if not config:
    raise ValueError("POS Config 'Purecf Lahat' tidak ditemukan!")

# Pastikan Payment Methods ada dan terpasang di config
pm_names = ['Cash', 'QRIS', 'Bank']
payment_method_map = {}

for name in pm_names:
    # 1. Cari yang sudah terpasang di config ini
    pm = config.payment_method_ids.filtered(lambda p: p.name.lower() == name.lower())
    if pm:
        payment_method_map[name.lower()] = pm[0].id
        continue
    
    # 2. Cari yang ada di sistem
    pm = env['pos.payment.method'].search([('name', '=', name)], limit=1)
    
    # 3. Jika cash dan sudah dipakai di POS lain, harus buat baru (khusus Odoo 17+)
    if pm and pm.is_cash_count:
        other_configs = env['pos.config'].search([('payment_method_ids', 'in', pm.ids), ('id', '!=', config.id)])
        if other_configs:
            pm = None # Force create new one for this POS
            new_name = f"{name} - {config.name}"
            # Cari lagi dengan nama spesifik jika pernah dibuat sebelumnya
            pm = env['pos.payment.method'].search([('name', '=', new_name)], limit=1)
            name = new_name
            
    if not pm:
        pm = env['pos.payment.method'].create({
            'name': name,
            'is_cash_count': True if 'cash' in name.lower() else False,
        })
        
    # Map back to original name for lookup from data
    orig_name = name.split(' - ')[0].lower()
    payment_method_map[orig_name] = pm.id
    
    # Tambahkan ke config jika belum ada
    if pm.id not in config.payment_method_ids.ids:
        config.write({'payment_method_ids': [(4, pm.id)]})

config_id = config.id
sorted_dates = sorted(trans_by_date.keys())

for date_str in sorted_dates:
    print(f"Memproses Tanggal: {date_str}")
    
    # Cari sesi yang sudah ada
    session = env['pos.session'].sudo().search([
        ('config_id', '=', config_id),
        ('start_at', '>=', f"{date_str} 00:00:00"),
        ('start_at', '<=', f"{date_str} 23:59:59"),
        ('x_is_purecf_session', '=', True)
    ], limit=1)

    if not session:
        session = env['pos.session'].sudo().create({
            'config_id': config_id,
            'user_id': env.uid,
            'start_at': f"{date_str} 04:00:00",
            'x_is_purecf_session': True,
        })
        session.sudo().write({'state': 'opened', 'start_at': f"{date_str} 04:00:00"})
    
    success_count = 0
    
    for t in trans_by_date[date_str]:
        oid = str(t['Id Transaksi'])
        
        try:
            with env.cr.savepoint():
                details = detail_by_order.get(oid, [])
                lines = []
                for d in details:
                    p_name = str(d['Nama Barang'])
                    p_name_lower = p_name.lower().strip()
                    
                    # Verifikasi produk masih ada (handle rollback dari order sebelumnya)
                    p_id = product_map.get(p_name_lower)
                    if p_id:
                        p_exists = env['product.product'].search_count([('id', '=', p_id)])
                        if not p_exists:
                            p_id = None
                    
                    if not p_id:
                        # Cari berdasarkan nama lagi
                        p = env['product.product'].sudo().search([('name', '=', p_name)], limit=1)
                        if not p:
                            p = env['product.product'].sudo().create({
                                'name': p_name,
                                'type': 'consu',
                                'available_in_pos': True,
                                'list_price': d['Harga'],
                            })
                        product_map[p_name_lower] = p.id
                        p_id = p.id
                    
                    lines.append((0, 0, {
                        'product_id': p_id,
                        'qty': d['Qty'],
                        'price_unit': d['Harga'],
                        'price_subtotal': d['Qty'] * d['Harga'],
                        'price_subtotal_incl': d['Qty'] * d['Harga'],
                        'full_product_name': p_name,
                    }))
                
                dt_utc = datetime.strptime(t['dt_parsed'], '%Y-%m-%d %H:%M:%S') - timedelta(hours=7)
                
                pm_id = payment_method_map.get(str(t['Metode Bayar']).lower().strip(), payment_method_map.get('cash'))
                order_vals = {
                    'session_id': session.id,
                    'date_order': dt_utc.strftime('%Y-%m-%d %H:%M:%S'),
                    'x_offline_id': oid,
                    'lines': lines,
                    'payment_ids': [(0, 0, {
                        'payment_method_id': pm_id, 
                        'amount': t['Total Bayar'], 
                        'payment_date': t['dt_parsed']
                    })],
                    'amount_total': t['Total Bayar'],
                    'amount_paid': t['Total Bayar'],
                    'amount_return': 0.0,
                    'amount_tax': 0.0,
                }
                
                res = env['pos.order'].sudo().sync_from_flutter(order_vals)
                if res.get('status') in ['success', 'already_exists']:
                    success_count += 1
                else:
                    print(f"Peringatan pada order {oid}: {res.get('message', 'Unknown error')}")
                    
        except Exception as e:
            print(f"Gagal pada order {oid}: {e}")
            
    # Commit transaksi dulu agar tersimpan jika penutupan sesi error
    env.cr.commit()
    
    # Tutup Sesi secara benar
    if session.state == 'opened':
        # Ambil total cash dari session
        total_cash = sum(session.order_ids.mapped('payment_ids').filtered(lambda p: p.payment_method_id.is_cash_count).mapped('amount'))
        
        # Set saldo akhir riil sama dengan saldo sistem + saldo awal
        # Lalu paksa tutup state
        session.sudo().write({
            'cash_register_balance_end_real': session.cash_register_balance_start + total_cash,
            'state': 'closed',
            'stop_at': f"{date_str} 16:00:00"
        })
    
    env.cr.commit()
    print(f"Selesai: {success_count} transaksi masuk untuk tanggal {date_str}")

print("SEMUA PROSES SELESAI")

