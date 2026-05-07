# Purecf ERP - API Documentation (JSON-RPC 2.0)

Dokumentasi ini menjelaskan cara berinteraksi dengan backend Odoo 17 untuk aplikasi Flutter Purecf. Semua request menggunakan protokol **JSON-RPC 2.0**.

**Base URL:** `https://your-cloudflare-url.trycloudflare.com`  
**Header Wajib:** `Content-Type: application/json`

---

## 1. Authentication
Endpoint untuk login dan mendapatkan `session_id`.

*   **URL:** `/api/purecf/auth`
*   **Auth:** `none` (Public)
*   **Params:**
    *   `db` (string): Nama database Odoo.
    *   `login` (string): Email/Username user.
    *   `password` (string): Password user.
*   **Response Success:**
    ```json
    {
      "status": "success",
      "session_id": "...",
      "user": {
        "id": 1,
        "name": "Admin",
        "role": "owner",
        "warehouse": "Gudang Utama",
        "pos_config_id": 1,
        "admin_pin": "1234"
      }
    }
    ```
*   **Notes:** Mengembalikan `session_id` yang harus dikirim di header/cookie untuk request selanjutnya. Role yang tersedia: `owner`, `admin`, `supervisor`, `cashier`.

---

## 2. Sync Products & Categories
Mengambil daftar produk jualan beserta stok real-time dan kategori POS.

*   **URL:** `/api/purecf/sync_products`
*   **Auth:** `user`
*   **Params:** `{}`
*   **Response:** Menyertakan `products` (id, name, list_price, qty_available, categ_id) dan `categories` (id, name).
*   **Logic:** Stok (`qty_available`) dihitung otomatis berdasarkan **Workplace (POS Config)** atau **Allowed Warehouse** pada profil user.

---

## 3. Product & Recipe Details
Manajemen detail produk dan resep (Bill of Materials).

*   **Get Details:** `/api/purecf/get_product_details`
    *   **Params:** `product_id`
    *   **Returns:** Detail produk, daftar resep (`resep`), dan daftar bahan baku yang tersedia untuk dipilih.
*   **Update Details:** `/api/purecf/update_product_details`
    *   **Params:** `product_id`, `name`, `price`, `category_id`, `resep` (list of `{product_id, qty}`).
    *   **Logic:** Mengupdate data produk dan mengganti seluruh baris resep BoM.

---

## 4. Sync Orders (Real-time Transaction)
Mengirim transaksi dari Flutter ke Odoo.

*   **URL:** `/api/purecf/sync_orders`
*   **Auth:** `user`
*   **Params:**
    *   `orders` (list): Daftar dictionary order.
        *   `x_offline_id` (string): ID unik Flutter (untuk mencegah duplikasi).
        *   `amount_total` (float): Total bayar.
        *   `lines` (list): `[{product_id, qty, price_unit, x_note}]`.
        *   `x_payment_method` (string): 'Cash', 'QRIS', 'Transfer'.
*   **Response:** `results` (list) berisi status per order (success/error/already_exists).

---

## 5. Stock Management (Opname & Incoming)
*   **Sync Ingredients:** `/api/purecf/sync_ingredients`
    *   Mengambil produk dengan flag `x_is_ingredient` atau `purchase_ok`.
*   **Update Stock (Opname):** `/api/purecf/update_stock`
    *   **Params:** `product_id`, `new_quantity`, `admin_pin` (optional).
    *   **Logic:** Jika produk sudah pernah di-opname pada hari yang sama, wajib menyertakan `admin_pin`.
*   **Stock Incoming (Belanja):** `/api/purecf/stock/incoming`
    *   **Params:** `items` (list of `{product_id, quantity, price, note}`).
    *   **Logic:** Menambah stok fisik dan mengupdate `standard_price` (Harga Modal) secara otomatis.

---

## 6. Financial Report (Dashboard)
Data ringkasan untuk grafik dan ringkasan finansial.

*   **URL:** `/api/purecf/report/financial`
*   **Auth:** `user`
*   **Params:**
    *   `date_from`, `date_to` (string): `YYYY-MM-DD`.
    *   `config_id` (int/string): ID Cabang atau 'all'.
*   **Response:**
    *   `summary`: `sales`, `cost` (HPP), `waste_cost` (kerugian opname), `expenses`, `cash_variance`, `profit`.
    *   `chart_data`: Data transaksi per jam (WIB).
    *   `payment_methods`: Breakdown % per metode bayar.
    *   `top_products_categorized`: Produk terlaris per kategori.
    *   `top_waste`: Daftar bahan baku dengan kerugian tertinggi.

---

## 7. Session Management
*   **Status:** `/api/purecf/session/status`
    *   Mengecek apakah ada sesi aktif untuk POS yang ditugaskan. Mengembalikan `last_closing_cash`.
*   **Open:** `/api/purecf/session/open`
    *   **Params:** `cash_start` (float).
*   **Close:** `/api/purecf/session/close`
    *   **Params:** `balance` (aktual kas), `supervisor_pin` (wajib jika ada selisih), `expenses` (list), `stocks` (list).
    *   **Logic:** Menutup sesi, mencatat biaya, dan menghasilkan **HTML Daily Report** di backend Odoo.

---

## 8. Audit & History
*   **History Transaksi:** `/api/purecf/history` (Params: `date` optional).
*   **Audit Logs:** `/api/purecf/history/audit_logs` (Params: `model`, `res_id`).
*   **Revert Data:** `/api/purecf/history/revert` (Params: `log_id`, `admin_pin`).

---

## 9. Monthly Reports
*   **Monthly Closings:** `/api/purecf/finance/closings` (Daftar tutup buku bulanan).
*   **Export Excel:** `/api/purecf/report/export_monthly?month=5&year=2024` (Download file Excel).

---

## Notes Teknikal
1.  **Timezone:** API menggunakan UTC internal, namun input/output tanggal untuk report menggunakan `Asia/Jakarta` (WIB).
2.  **PIN Validation:** `admin_pin` dapat berupa PIN User Admin atau PIN Employee. `supervisor_pin` harus milik User dengan group Supervisor/Owner.
3.  **HPP Calculation:** HPP dihitung real-time berdasarkan `standard_price` produk dikalikan jumlah pemakaian bahan baku sesuai resep (BoM).
4.  **Auto-Validation:** Saat sesi ditutup, semua order `draft` akan divalidasi otomatis agar tidak menghambat rekonsiliasi kas.
