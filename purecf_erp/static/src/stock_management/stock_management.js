/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

export class StockManagement extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            activeTab: 'stock_in',
            ingredients: [],
            cart: [],
            opnameSearch: '',
            masterSearch: '',
            masterFilter: 'all',
            loading: true,
            dialog: {
                show: false,
                id: null,
                name: '',
                uom: '',
                qty: 0
            }
        });

        onWillStart(async () => {
            await this._fetchIngredients();
        });
    }

    async _fetchIngredients() {
        this.state.loading = true;
        const result = await this.orm.searchRead("product.product", 
            ["|", ["x_is_ingredient", "=", true], ["purchase_ok", "=", true]], 
            ["id", "name", "qty_available", "uom_id", "x_min_qty", "list_price"]
        );
        this.state.ingredients = result;
        this.state.loading = false;
    }

    // Tabs
    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    // Stock In Logic
    addToCart() {
        const select = document.getElementById('material-select');
        const qtyInput = document.getElementById('input-qty');
        const priceInput = document.getElementById('input-price');
        
        if (!select.value || !qtyInput.value) return;
        
        const ingredient = this.state.ingredients.find(i => i.id == select.value);
        if (!ingredient) return;

        this.state.cart.push({
            product_id: ingredient.id,
            name: ingredient.name,
            uom: ingredient.uom_id[1],
            quantity: parseFloat(qtyInput.value),
            price: parseFloat(priceInput.value || 0)
        });

        // Reset inputs
        select.value = "";
        qtyInput.value = "";
        priceInput.value = "";
    }

    removeFromCart(index) {
        this.state.cart.splice(index, 1);
    }

    async saveStock() {
        this.state.loading = true;
        try {
            for (const item of this.state.cart) {
                await this.orm.call("product.template", "action_add_stock_incoming", [
                    item.product_id, 
                    item.quantity, 
                    null, // admin_id (will be taken from env in Python if needed, but here we pass uid)
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

    // Opname Logic
    openOpnameDialog(ing) {
        this.state.dialog = {
            show: true,
            id: ing.id,
            name: ing.name,
            uom: ing.uom_id[1],
            qty: 0
        };
    }

    closeDialog() {
        this.state.dialog.show = false;
    }

    async confirmOpname() {
        const { id, qty } = this.state.dialog;
        this.state.loading = true;
        try {
            await this.orm.call("product.template", "action_update_stock_manual", [
                id, 
                qty, 
                null // admin_id
            ]);
            this.notification.add("Opname berhasil", { type: "success" });
            this.closeDialog();
            await this._fetchIngredients();
        } catch (e) {
            this.notification.add("Gagal update stok: " + e.message, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // Filter Logic
    get filteredOpname() {
        const query = this.state.opnameSearch.toLowerCase();
        return this.state.ingredients.filter(i => i.name.toLowerCase().includes(query));
    }

    get filteredMaster() {
        const query = this.state.masterSearch.toLowerCase();
        const filter = this.state.masterFilter;
        
        return this.state.ingredients.filter(i => {
            const matchesSearch = i.name.toLowerCase().includes(query);
            const isLow = i.qty_available <= i.x_min_qty;
            const isWarning = !isLow && i.qty_available <= (i.x_min_qty * 1.2);
            
            let matchesFilter = true;
            if (filter === 'emergency') matchesFilter = isLow;
            else if (filter === 'warning') matchesFilter = isWarning;
            else if (filter === 'safe') matchesFilter = !isLow && !isWarning;
            
            return matchesSearch && matchesFilter;
        });
    }

    async editMinQty(ing) {
        const newVal = prompt('Input Stok Minimum Baru:', ing.x_min_qty);
        if (newVal !== null) {
            await this.orm.write("product.product", [ing.id], { x_min_qty: parseFloat(newVal) });
            await this._fetchIngredients();
        }
    }
}

StockManagement.template = "purecf_erp.StockManagement";

registry.category("actions").add("purecf_stock_management", StockManagement);
