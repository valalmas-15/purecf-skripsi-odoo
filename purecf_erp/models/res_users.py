# -*- coding: utf-8 -*-
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    x_allowed_warehouse_id = fields.Many2one('stock.warehouse', string='Branch Warehouse', help="Warehouse assigned to this cashier's branch.")
    x_role_type = fields.Selection([
        ('cashier', 'Cashier'),
        ('manager', 'Manager'),
        ('admin', 'Admin')
    ], string='App Role', default='cashier', help="Access level in the Flutter POS App.")
    x_admin_pin = fields.Char(string='Admin PIN', size=4, help="4-digit PIN for high-level validation.")
    x_closing_day = fields.Integer(string='Financial Closing Day', default=1, help="Day of the month (1-31) when the financial period ends.")

    def action_get_current_purecf_warehouse(self):
        """Helper to resolve warehouse based on Employee -> POS Config -> Warehouse."""
        self.ensure_one()
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.id)], limit=1)
        if employee and employee.x_pos_config_id:
            pos_config = employee.x_pos_config_id
            wh_id = False
            wh_name = 'General'
            if pos_config.picking_type_id and pos_config.picking_type_id.warehouse_id:
                wh_id = pos_config.picking_type_id.warehouse_id.id
                wh_name = pos_config.picking_type_id.warehouse_id.name
            
            return {
                'id': wh_id, 
                'name': wh_name,
                'pos_name': pos_config.name
            }
        
        if self.x_allowed_warehouse_id:
            return {
                'id': self.x_allowed_warehouse_id.id, 
                'name': self.x_allowed_warehouse_id.name,
                'pos_name': self.x_allowed_warehouse_id.name
            }
            
        return {'id': False, 'name': 'General', 'pos_name': 'Semua Cabang'}
