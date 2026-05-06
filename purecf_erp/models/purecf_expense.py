# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class PurecfExpense(models.Model):
    _name = 'purecf.expense'
    _description = 'Store/Cafe Expense'
    _order = 'date desc'

    session_id = fields.Many2one('pos.session', string='Session', ondelete='cascade')
    amount = fields.Float(string='Amount', required=True)
    note = fields.Char(string='Note', required=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now)
    config_id = fields.Many2one('pos.config', string='Branch', default=lambda self: self._get_default_config_id())
    user_id = fields.Many2one('res.users', string='Inputted By', default=lambda self: self.env.user)

    def _get_default_config_id(self):
        # Try to get from Employee's assigned POS
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if employee and employee.x_pos_config_id:
            return employee.x_pos_config_id.id
        return False
