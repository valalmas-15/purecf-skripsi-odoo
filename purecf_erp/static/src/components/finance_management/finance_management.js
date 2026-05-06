/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class FinanceManagement extends Component {
    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        const now = new Date();
        this.state = useState({
            loading: false,
            view: 'list', // 'list' or 'detail'
            month: now.getMonth() + 1,
            year: now.getFullYear(),
            monthlyList: this._generateMonthlyList(),
            report: {
                income: 0,
                expense: 0,
                profit: 0,
                tax: 0,
                stock_value: 0
            }
        });
    }

    _generateMonthlyList() {
        const months = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ];
        const list = [];
        const now = new Date();
        let currMonth = now.getMonth();
        let currYear = now.getFullYear();

        // Generate last 12 months
        for (let i = 0; i < 12; i++) {
            list.push({
                month: currMonth + 1,
                year: currYear,
                label: `${months[currMonth]} ${currYear}`
            });
            currMonth--;
            if (currMonth < 0) {
                currMonth = 11;
                currYear--;
            }
        }
        return list;
    }

    async selectMonth(month, year) {
        this.state.month = month;
        this.state.year = year;
        this.state.view = 'detail';
        await this._loadFinancialData();
    }

    goBack() {
        this.state.view = 'list';
    }

    async _loadFinancialData() {
        this.state.loading = true;
        try {
            const startOfMonth = `${this.state.year}-${String(this.state.month).padStart(2, '0')}-01 00:00:00`;
            const endOfMonth = new Date(this.state.year, this.state.month, 0).toISOString().split('T')[0] + " 23:59:59";

            const dateDomain = [
                ["date_order", ">=", startOfMonth],
                ["date_order", "<=", endOfMonth]
            ];

            const expenseDomain = [
                ["move_type", "in", ["in_invoice", "in_receipt"]],
                ["state", "=", "posted"],
                ["invoice_date", ">=", `${this.state.year}-${String(this.state.month).padStart(2, '0')}-01`],
                ["invoice_date", "<=", new Date(this.state.year, this.state.month, 0).toISOString().split('T')[0]]
            ];

            // 1. Fetch Monthly Income from POS Orders
            const sales = await this.orm.readGroup("pos.order",
                [["state", "in", ["paid", "done", "invoiced"]], ...dateDomain],
                ["amount_total:sum"],
                []
            );
            const totalSales = sales[0]?.amount_total || 0;

            // 2. Fetch Monthly Expenses from Account Moves
            const expenses = await this.orm.readGroup("account.move",
                expenseDomain,
                ["amount_total:sum"],
                []
            );
            const totalExpenses = expenses[0]?.amount_total || 0;

            // 3. Fetch Total Inventory Value
            const products = await this.orm.searchRead("product.template",
                ["|", ["x_is_ingredient", "=", true], ["purchase_ok", "=", true]],
                ["qty_available", "standard_price"]
            );
            const totalStockValue = products.reduce((acc, p) => acc + (p.qty_available * p.standard_price), 0);

            // 4. Update State
            this.state.report = {
                income: totalSales,
                expense: totalExpenses,
                profit: totalSales - totalExpenses,
                stock_value: totalStockValue,
                tax: totalSales * 0.11,
                expense_percent: totalSales > 0 ? (totalExpenses / totalSales * 100).toFixed(1) : 0,
                profit_percent: totalSales > 0 ? ((totalSales - totalExpenses) / totalSales * 100).toFixed(1) : 0
            };
        } catch (error) {
            console.error("Failed to load financial data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async onMonthChange(ev) {
        this.state.month = parseInt(ev.target.value);
        await this._loadFinancialData();
    }

    async onYearChange(ev) {
        this.state.year = parseInt(ev.target.value);
        await this._loadFinancialData();
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    openAction(xmlid) {
        this.actionService.doAction(xmlid);
    }

    exportExcel() {
        const url = `/api/purecf/report/export_monthly?month=${this.state.month}&year=${this.state.year}`;
        window.location.href = url;
    }
}

FinanceManagement.template = "purecf_erp.FinanceManagement";
registry.category("actions").add("purecf_finance_management", FinanceManagement);
