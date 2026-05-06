# -*- coding: utf-8 -*-
from odoo import models, fields, api

class PurecfMonthlyClose(models.Model):
    _name = 'purecf.monthly.close'
    _description = 'Financial Snapshot for Closed Month'
    _order = 'year desc, month desc'

    name = fields.Char(string='Nama Laporan', compute='_compute_name', store=True)
    year = fields.Integer(string='Tahun', compute='_compute_period_ints', store=True, readonly=False)
    month = fields.Integer(string='Bulan', compute='_compute_period_ints', store=True, readonly=False)
    
    date_from = fields.Date(string='Periode Awal', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Periode Akhir', required=True, default=lambda self: fields.Date.today())

    @api.depends('date_from', 'date_to')
    def _compute_name(self):
        for rec in self:
            if rec.date_from and rec.date_to:
                df = rec.date_from.strftime('%d/%m/%Y')
                dt = rec.date_to.strftime('%d/%m/%Y')
                rec.name = f"Laporan {df} - {dt}"
            else:
                rec.name = "Draft Laporan"

    @api.depends('date_from')
    def _compute_period_ints(self):
        for rec in self:
            if rec.date_from:
                rec.year = rec.date_from.year
                rec.month = rec.date_from.month
    
    total_sales = fields.Float(string='Total Penjualan', required=True)
    total_cogs = fields.Float(string='Total HPP (Bahan)', required=True)
    total_opex = fields.Float(string='Total Operasional', required=True)
    total_profit = fields.Float(string='Laba Bersih', required=True)
    
    admin_id = fields.Many2one('res.users', string='Authorized By')
    config_id = fields.Many2one('pos.config', string='Cabang/Toko', help="Kosongkan untuk laporan gabungan seluruh cabang.")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('unique_period', 'unique(year, month, config_id, company_id)', 'Laporan untuk periode dan cabang ini sudah ada!')
    ]

    def action_export_excel(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/api/purecf/report/export_monthly?month=%s&year=%s' % (self.month, self.year),
            'target': 'new',
        }

    def action_recalculate(self):
        """Fetch latest sales and cost data for this period using the date range."""
        self.ensure_one()
        from datetime import datetime, time
        
        # Define the exact start and end datetimes for the search
        start_dt = datetime.combine(self.date_from, time.min)
        end_dt = datetime.combine(self.date_to, time.max)

        # 1. Sales and Sales-based HPP (from BoM/Cost)
        domain_pos = [
            ('date_order', '>=', start_dt),
            ('date_order', '<=', end_dt),
            ('state', 'in', ['paid', 'done', 'invoiced'])
        ]
        if self.config_id:
            domain_pos.append(('config_id', '=', self.config_id.id))
            
        orders = self.env['pos.order'].search(domain_pos)
        total_sales = sum(orders.mapped('amount_total'))
        
        # HPP from Sales (captures BoM consumption for Drinks)
        total_hpp_sales = sum(orders.mapped('lines.total_cost'))

        # 2. Costs from account.move (Vendor Bills)
        expenses_move = self.env['account.move'].search([
            ('move_type', 'in', ['in_invoice', 'in_receipt']),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to)
        ])
        total_move = sum(expenses_move.mapped('amount_total'))

        # 3. Costs from purecf.expense (Operating Expenses ONLY)
        expenses_purecf = self.env['purecf.expense'].search([
            ('date', '>=', start_dt),
            ('date', '<=', end_dt)
        ])
        
        cogs_categories = [
            'Bahan Baku', 'Sembako', 'Sayur', 'Food', 'Sirup', 
            'Powder', 'Fruit Base', 'Packaging'
        ]
        
        total_opex_purecf = 0.0
        for exp in expenses_purecf:
            is_cogs_cat = False
            for cat in cogs_categories:
                if f"[{cat}]" in exp.note:
                    is_cogs_cat = True
                    break
            if not is_cogs_cat:
                total_opex_purecf += exp.amount

        # 4. HPP from Daily Stock Opname (Captures Kitchen Usage & Waste)
        domain_opn = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to)
        ]
        if self.config_id:
            domain_opn.append(('report_id.config_id', '=', self.config_id.id))
            
        opname_lines = self.env['purecf.stock.opname.line'].search(domain_opn)
        
        total_hpp_waste = 0.0
        for line in opname_lines:
            # waste is new_qty - old_qty. 
            # If negative, it means something was consumed/lost.
            if line.waste < 0:
                total_hpp_waste += abs(line.waste) * line.product_id.standard_price

        # FINAL CONSOLIDATED HPP
        # For Kitchen (No BoM): hpp_sales = 0, hpp_waste = total usage.
        # For Bar (BoM): hpp_sales = recipe cost, hpp_waste = actual spillage/diff.
        total_cogs = total_hpp_sales + total_hpp_waste
        total_opex = total_opex_purecf

        self.write({
            'total_sales': total_sales,
            'total_cogs': total_cogs,
            'total_opex': total_opex,
            'total_profit': total_sales - (total_cogs + total_opex)
        })
        return True


    @api.model
    def cron_auto_generate_monthly_reports(self):
        """Automatically generate reports when closing day is reached."""
        from datetime import datetime
        import calendar
        
        today = datetime.now()
        config = self.env['purecf.config'].sudo().get_config()
        closing_day = config.closing_day
        
        if today.day == closing_day:
            year = today.year
            month = today.month
            
            existing = self.search([
                ('year', '=', year),
                ('month', '=', month)
            ], limit=1)
            
            if not existing:
                last_day = calendar.monthrange(year, month)[1]
                report = self.create({
                    'year': year,
                    'month': month,
                    'date_from': '%s-%02d-01' % (year, month),
                    'date_to': '%s-%02d-%02d' % (year, month, last_day),
                    'total_sales': 0,
                    'total_cogs': 0,
                    'total_opex': 0,
                    'total_profit': 0,
                    'admin_id': self.env.ref('base.user_root').id
                })
                report.action_recalculate()

class PurecfConfig(models.Model):
    _name = 'purecf.config'
    _description = 'PureCF Global Configuration'

    closing_day = fields.Integer(string='Monthly Closing Day', default=25)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    @api.model
    def get_config(self):
        closing_day = self.env['ir.config_parameter'].sudo().get_param('purecf_erp.closing_day', default=25)
        config = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            config = self.create({'closing_day': int(closing_day)})
        elif config.closing_day != int(closing_day):
            config.closing_day = int(closing_day)
        return config
