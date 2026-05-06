/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

export class StockManagement extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.user = useService("user");
        this.state = useState({
            activeTab: this.props.action.context.active_tab || 'master_data',
            ingredients: [],
            cart: [],
            opnameSearch: '',
            masterSearch: '',
            masterFilter: 'all',
            opnameHistory: [],
            opnameCart: [],
            expandedReport: null,
            todayReportExists: false,
            stockInSearch: '',
            stockInSelected: null,
            showStockInDropdown: false,
            loading: true,
            warehouseId: null,
            warehouseName: '',
            dialog: {
                show: false,
                id: null,
                name: '',
                uom: '',
                qty: 0,
                old_qty: 0
            }
        });

        onWillStart(async () => {
            const warehouse = await this.orm.call("res.users", "action_get_current_purecf_warehouse", [this.user.userId]);
            this.state.warehouseId = warehouse.id;
            this.state.warehouseName = warehouse.pos_name;
            
            await this._fetchIngredients();
            await this._checkTodayReport();
            if (this.state.activeTab === 'opname_history') {
                await this._fetchOpnameHistory();
            }
        });
    }

    async _checkTodayReport() {
        const today = new Date().toISOString().split('T')[0];
        const count = await this.orm.searchCount("purecf.stock.opname", [["date", "=", today]]);
        this.state.todayReportExists = count > 0;
    }

    async _fetchIngredients() {
        this.state.loading = true;
        try {
            const context = this.state.warehouseId ? { warehouse: this.state.warehouseId } : {};
            const result = await this.orm.searchRead("product.template", 
                ["|", ["x_is_ingredient", "=", true], ["purchase_ok", "=", true]], 
                ["id", "name", "qty_available", "uom_id", "x_min_qty", "standard_price"],
                { context: context }
            );
            this.state.ingredients = result;
        } finally {
            this.state.loading = false;
        }
    }

    async _fetchOpnameHistory() {
        this.state.loading = true;
        try {
            const reports = await this.orm.searchRead("purecf.stock.opname", 
                [], 
                ["id", "name", "date", "admin_id", "create_date", "total_items", "line_ids"],
                { order: "date desc" }
            );

            // Fetch details for each report's lines
            for (const report of reports) {
                const dateObj = new Date(report.date);
                report.formattedDate = {
                    day: dateObj.getDate(),
                    month: dateObj.toLocaleDateString('id-ID', { month: 'short' }),
                    year: dateObj.getFullYear()
                };

                const lines = await this.orm.searchRead("purecf.stock.opname.line",
                    [["report_id", "=", report.id]],
                    ["id", "product_id", "old_qty", "new_qty", "waste"]
                );
                report.line_ids = lines.map(l => ({
                    ...l,
                    product_name: l.product_id[1],
                    uom: this.state.ingredients.find(i => i.id === l.product_id[0])?.uom_id[1] || ''
                }));
            }
            
            this.state.opnameHistory = reports;
        } catch (e) {
            console.error("Failed to fetch opname history", e);
        } finally {
            this.state.loading = false;
        }
    }

    async setActiveTab(tab) {
        this.state.activeTab = tab;
        if (tab === 'opname_history') {
            await this._fetchOpnameHistory();
        }
        if (tab === 'opname') {
            await this._checkTodayReport();
        }
    }

    addToCart() {
        const qtyInput = document.getElementById('input-qty');
        const priceInput = document.getElementById('input-price');
        
        if (!this.state.stockInSelected || !qtyInput.value) {
            this.notification.add("Pilih bahan dan masukkan jumlah", { type: "warning" });
            return;
        }
        
        const ingredient = this.state.stockInSelected;

        this.state.cart.push({
            product_id: ingredient.id,
            name: ingredient.name,
            uom: ingredient.uom_id[1],
            quantity: parseFloat(qtyInput.value),
            price: parseFloat(priceInput.value || 0)
        });

        this.state.stockInSearch = "";
        this.state.stockInSelected = null;
        qtyInput.value = "";
        priceInput.value = "";
    }

    selectIngredient(ing) {
        this.state.stockInSelected = ing;
        this.state.stockInSearch = ing.name;
        this.state.showStockInDropdown = false;
    }

    get filteredStockIn() {
        const query = this.state.stockInSearch.toLowerCase();
        return this.state.ingredients.filter(i => i.name.toLowerCase().includes(query));
    }

    removeFromCart(index) {
        this.state.cart.splice(index, 1);
    }

    async saveStock() {
        this.state.loading = true;
        try {
            for (const item of this.state.cart) {
                await this.orm.call("product.template", "action_add_stock_incoming", [
                    [item.product_id], 
                    item.quantity, 
                    null, 
                    item.price
                ]);
            }
            this.notification.add("Stok berhasil disimpan", { type: "success" });
            this.state.cart = [];
            await this._fetchIngredients();
        } catch (e) {
            this.notification.add("Gagal menyimpan stok: " + e.message, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    openOpnameDialog(ing) {
        this.state.dialog = {
            show: true,
            id: ing.id,
            name: ing.name,
            uom: ing.uom_id[1],
            qty: 0,
            old_qty: ing.qty_available
        };
    }

    closeDialog() {
        this.state.dialog.show = false;
    }

    confirmOpname() {
        const { id, qty, name, old_qty } = this.state.dialog;
        
        // Add to local cart for batch submission
        this.state.opnameCart.push({
            id: id,
            name: name,
            qty: parseFloat(qty),
            old_qty: old_qty
        });
        
        this.closeDialog();
    }

    removeFromOpnameCart(id) {
        this.state.opnameCart = this.state.opnameCart.filter(c => c.id !== id);
    }

    async submitOpnameBatch() {
        this.state.loading = true;
        try {
            // 1. Create Report Header
            const reportId = await this.orm.create("purecf.stock.opname", [{
                date: new Date().toISOString().split('T')[0]
            }]);

            // 2. Create Lines
            for (const item of this.state.opnameCart) {
                await this.orm.create("purecf.stock.opname.line", [{
                    report_id: reportId[0],
                    product_id: item.id,
                    old_qty: item.old_qty,
                    new_qty: item.qty
                }]);
            }

            // 3. Apply the report (Update Odoo Stock & Audit Logs)
            await this.orm.call("purecf.stock.opname", "action_apply_opname", [reportId]);

            this.notification.add("Laporan Opname berhasil disimpan", { type: "success" });
            this.state.opnameCart = [];
            this.state.todayReportExists = true;
            await this._fetchIngredients();
        } catch (e) {
            this.notification.add("Gagal menyimpan laporan: " + e.message, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    toggleReportDetails(reportId) {
        if (this.state.expandedReport === reportId) {
            this.state.expandedReport = null;
        } else {
            this.state.expandedReport = reportId;
        }
    }

    get filteredOpname() {
        const query = this.state.opnameSearch.toLowerCase();
        return this.state.ingredients.filter(i => i.name.toLowerCase().includes(query));
    }

    get filteredMaster() {
        const query = this.state.masterSearch.toLowerCase();
        const filter = this.state.masterFilter;
        
        const filtered = this.state.ingredients.filter(i => {
            const matchesSearch = i.name.toLowerCase().includes(query);
            const isLow = i.qty_available <= i.x_min_qty;
            const isWarning = !isLow && i.qty_available <= (i.x_min_qty * 1.2);
            
            let matchesFilter = true;
            if (filter === 'emergency') matchesFilter = isLow;
            else if (filter === 'warning') matchesFilter = isWarning;
            else if (filter === 'safe') matchesFilter = !isLow && !isWarning;
            
            return matchesSearch && matchesFilter;
        });

        // Sort by status priority: Darurat (0) > Warning (1) > Aman (2)
        return filtered.sort((a, b) => {
            const getScore = (item) => {
                if (item.qty_available <= item.x_min_qty) return 0;
                if (item.qty_available <= item.x_min_qty * 1.2) return 1;
                return 2;
            };
            const scoreA = getScore(a);
            const scoreB = getScore(b);
            
            if (scoreA !== scoreB) return scoreA - scoreB;
            return a.name.localeCompare(b.name);
        });
    }

    async editMinQty(ing) {
        const newVal = prompt('Input Stok Minimum Baru:', ing.x_min_qty);
        if (newVal !== null) {
            await this.orm.write("product.template", [ing.id], { x_min_qty: parseFloat(newVal) });
            await this._fetchIngredients();
        }
    }
}

StockManagement.template = "purecf_erp.StockManagement";

registry.category("actions").add("purecf_stock_management", StockManagement);
