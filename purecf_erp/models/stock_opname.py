# -*- coding: utf-8 -*-
from odoo import models, fields, api

class PurecfStockOpname(models.Model):
    _name = 'purecf.stock.opname'
    _description = 'Inventory Audit Report'
    _order = 'create_date desc'

    name = fields.Char(string='Report Ref', required=True, copy=False, readonly=True, default='New')
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    create_date = fields.Datetime(string='Created On', readonly=True)
    admin_id = fields.Many2one('res.users', string='Supervisor', default=lambda self: self.env.user)
    config_id = fields.Many2one('pos.config', string='Cabang', default=lambda self: self._get_default_config_id())
    line_ids = fields.One2many('purecf.stock.opname.line', 'report_id', string='Opname Details')
    total_items = fields.Integer(string='Total Items', compute='_compute_totals')
    
    @api.depends('line_ids')
    def _compute_totals(self):
        for rec in self:
            rec.total_items = len(rec.line_ids)

    _sql_constraints = [
        ('unique_date', 'unique(date)', 'Laporan opname untuk hari ini sudah ada!')
    ]

    def _get_default_config_id(self):
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if employee and employee.x_pos_config_id:
            return employee.x_pos_config_id.id
        return False

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            prefix = 'OPN/' + fields.Date.today().strftime('%Y%m%d') + '/'
            count = self.search_count([('name', 'like', prefix + '%')])
            vals['name'] = prefix + str(count + 1).zfill(3)
        return super(PurecfStockOpname, self).create(vals)

    def action_apply_opname(self):
        self.ensure_one()
        for line in self.line_ids:
            line.product_id.action_update_stock_manual(
                new_qty=line.new_qty, 
                admin_id=self.admin_id.id,
                opname_id=self.id
            )
        return True

class PurecfStockOpnameLine(models.Model):
    _name = 'purecf.stock.opname.line'
    _description = 'Inventory Audit Report Line'

    report_id = fields.Many2one('purecf.stock.opname', string='Report Reference', ondelete='cascade')
    date = fields.Date(related='report_id.date', store=True, index=True)
    product_id = fields.Many2one('product.template', string='Product', required=True)
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unit of Measure')
    old_qty = fields.Float(string='System Qty')
    new_qty = fields.Float(string='Actual Qty')
    waste = fields.Float(string='Difference (Waste)', compute='_compute_waste', store=True)

    @api.depends('old_qty', 'new_qty')
    def _compute_waste(self):
        for rec in self:
            rec.waste = rec.new_qty - rec.old_qty
