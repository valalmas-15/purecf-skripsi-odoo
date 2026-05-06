/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PurecfDashboard extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.actionService = useService("action");

        const today = new Date().toISOString().split('T')[0];

        this.state = useState({
            loading: true,
            dateFrom: today,
            dateTo: today,
            showPicker: false,
            configId: null,
            branches: [],
            summary: {
                sales: 0,
                cost: 0,
                profit: 0,
                hpp_percent: 0,
                total_orders: 0,
                avg_order: 0,
                waste_cost: 0,
                trends: {
                    sales: 0,
                    orders: 0,
                    avg_order: 0
                },
                comparison_label: "vs Periode Sebelumnya"
            },
            chartData: [],
            maxChartValue: 0,
            topProductsFlattened: [],
            topWaste: [],
            topBranches: [],
            usageAnalysis: [],
            paymentMethods: []
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        try {
            const params = {
                date_from: this.state.dateFrom,
                date_to: this.state.dateTo,
                config_id: this.state.configId
            };
            const response = await this.rpc("/api/purecf/report/financial", params);

            if (response.status === 'success') {
                this.state.summary = response.summary;
                this.state.chartData = response.chart_data || [];
                this.state.paymentMethods = response.payment_methods || [];
                this.state.branches = response.branches || [];
                this.state.topBranches = response.top_branches || [];
                this.state.topWaste = response.top_waste || [];
                this.state.usageAnalysis = response.usage_analysis || [];

                if (this.state.chartData.length > 0) {
                    this.state.maxChartValue = Math.max(...this.state.chartData.map(d => d.value));
                }

                let allProds = [];
                (response.top_products_categorized || []).forEach(cat => {
                    allProds = allProds.concat(cat.products);
                });
                this.state.topProductsFlattened = allProds
                    .sort((a, b) => b.qty - a.qty)
                    .slice(0, 5);
            }
        } catch (error) {
            console.error("Failed to load dashboard data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    onDateChange(field, ev) {
        this.state[field] = ev.target.value;
        this.loadDashboardData();
    }

    onBranchChange(ev) {
        this.state.configId = ev.target.value === 'all' ? null : ev.target.value;
        this.loadDashboardData();
    }

    togglePicker() {
        this.state.showPicker = !this.state.showPicker;
    }

    formatCurrency(value) {
        const val = parseFloat(value) || 0;
        return new Intl.NumberFormat('id-ID', {
            style: 'currency',
            currency: 'IDR',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(val);
    }

    get formattedDateRange() {
        const d1 = new Date(this.state.dateFrom).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
        const d2 = new Date(this.state.dateTo).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
        return `${d1} - ${d2}`;
    }

    get niceMax() {
        const actualMax = this.state.maxChartValue || 100000;
        const magnitude = Math.pow(10, Math.floor(Math.log10(actualMax)));
        const fraction = actualMax / magnitude;
        let niceFraction;
        if (fraction <= 1.0) niceFraction = 1.0;
        else if (fraction <= 2.0) niceFraction = 2.0;
        else if (fraction <= 5.0) niceFraction = 5.0;
        else niceFraction = 10.0;
        return niceFraction * magnitude;
    }

    get chartLinePath() {
        if (!this.state.chartData.length) return "";
        const width = 1000;
        const height = 200;
        const max = this.niceMax;
        const step = width / (this.state.chartData.length - 1);

        let path = "";
        this.state.chartData.forEach((d, i) => {
            const x = i * step;
            const y = height - (d.value / max * height);

            if (i === 0) {
                path = `M ${x} ${y}`;
            } else {
                const prevX = (i - 1) * step;
                const prevY = height - (this.state.chartData[i - 1].value / max * height);
                const cp1x = prevX + (x - prevX) / 2;
                const cp2x = prevX + (x - prevX) / 2;
                path += ` C ${cp1x} ${prevY}, ${cp2x} ${y}, ${x} ${y}`;
            }
        });
        return path;
    }

    get chartAreaPath() {
        const linePath = this.chartLinePath;
        if (!linePath) return "";
        return `${linePath} L 1000 200 L 0 200 Z`;
    }

    get chartYLabels() {
        const max = this.niceMax;
        const labels = [];
        for (let i = 5; i >= 0; i--) {
            const val = (max / 5) * i;
            let text;
            if (val >= 1000000) text = (val / 1000000).toFixed(1) + 'M';
            else if (val >= 1000) text = (val / 1000).toFixed(0) + 'K';
            else text = val.toString();

            labels.push({
                text: text,
                y: 200 - (200 / max) * val
            });
        }
        return labels;
    }

    get chartPoints() {
        const width = 1000;
        const height = 200;
        const max = this.niceMax;
        const step = width / (this.state.chartData.length - 1);
        return this.state.chartData.map((d, i) => ({
            x: i * step,
            y: height - (d.value / max * height),
            value: d.value,
            label: d.label
        }));
    }

    exportMonthlyReport() {
        // Extract month and year from dateFrom
        const date = new Date(this.state.dateFrom);
        const month = date.getMonth() + 1;
        const year = date.getFullYear();
        const url = `/api/purecf/report/export_monthly?month=${month}&year=${year}`;
        window.location.href = url;
    }
}

PurecfDashboard.template = "purecf_erp.Dashboard";
registry.category("actions").add("purecf_dashboard", PurecfDashboard);
