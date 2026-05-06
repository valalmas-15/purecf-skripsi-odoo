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
*   **Notes:** Mengembalikan `session_id` yang harus dikirim di header/cookie untuk request selanjutnya.

---

## 2. Sync Products & Stock
Mengambil daftar produk jualan beserta stok real-time.

*   **URL:** `/api/purecf/sync_products`
*   **Auth:** `user`
*   **Params:** `{}`
*   **Logic:** Stok (`qty_available`) dihitung otomatis berdasarkan **Allowed Warehouse** pada profil user di Odoo.

---

## 3. Sync Ingredients (Bahan Baku)
Mengambil daftar bahan baku untuk manajemen stok.

*   **URL:** `/api/purecf/sync_ingredients`
*   **Auth:** `user`
*   **Params:** `{}`
*   **Logic:** Mengambil produk yang memiliki flag `x_is_ingredient = True`.

---

## 4. Sync Orders (Real-time Transaction)
Mengirim transaksi dari Flutter ke Odoo.

*   **URL:** `/api/purecf/sync_orders`
*   **Auth:** `user`
*   **Params:**
    *   `orders` (list): Daftar dictionary order.
        *   `x_offline_id` (string): ID unik Flutter.
        *   `amount_total` (float): Total bayar.
        *   `lines` (list): `[{product_id, qty, price_unit}]`.
        *   `x_payment_method` (string): 'Tunai', 'Transfer', dll.

---

## 5. Management Stok (Opname)
Update stok fisik bahan baku secara manual.

*   **URL:** `/api/purecf/update_stock`
*   **Auth:** `user`
*   **Params:**
    *   `product_id` (int): ID bahan baku.
    *   `new_quantity` (float): Stok fisik baru.
    *   `admin_pin` (string): PIN Admin (wajib jika data sudah pernah di-opname di hari yang sama).

---

## 6. Stock Incoming (Belanja)
Input stok masuk hasil belanja bahan baku.

*   **URL:** `/api/purecf/stock/incoming`
*   **Auth:** `user`
*   **Params:**
    *   `items` (list): `[{product_id, quantity, price, note}]`
        *   `price` (float): Total harga beli untuk barang tersebut.
*   **Logic:** Akan mengupdate `standard_price` (Harga Modal) secara otomatis.

---

## 7. Financial Report
Ringkasan Omzet, Cost (HPP), dan Profit.

*   **URL:** `/api/purecf/report/financial`
*   **Auth:** `user`
*   **Params:**
    *   `date_from` (string): `YYYY-MM-DD`.
    *   `date_to` (string): `YYYY-MM-DD`.
    *   `config_id` (int, optional): ID POS/Cabang tertentu.
*   **Response:** Menyertakan tren penjualan, grafik per jam, dan metode pembayaran.

---

## 8. Session Management
*   **Open:** `/api/purecf/session/open` (Params: `cash_start`)
*   **Close:** `/api/purecf/session/close` (Params: `session_id`, `balance`)
*   **Status:** `/api/purecf/session/status` (Mengecek sesi aktif user).

---

## 9. Audit & History
*   **Get Logs:** `/api/purecf/history/audit_logs` (Params: `model`, `res_id`)
*   **Revert:** `/api/purecf/history/revert` (Params: `log_id`, `admin_pin`)

---

## Notes Teknikal
1.  **Stok 0?** Pastikan user Odoo Anda sudah disetting **Allowed Warehouse** di tab 'Purecf Access'.
2.  **Timezone:** API menggunakan UTC secara internal, namun report secara otomatis dikonversi ke `Asia/Jakarta` (WIB).
