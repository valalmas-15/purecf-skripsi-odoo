
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = 'pos.session'

    x_is_purecf_session = fields.Boolean(string='Is Purecf Session', default=False)
    x_flutter_daily_report = fields.Html(string='Laporan Akhir Harian (Flutter)')
    x_expense_ids = fields.One2many('purecf.expense', 'session_id', string='Expenses')
    x_total_expense = fields.Float(string='Total Expense', compute='_compute_total_expense', store=True)

    @api.depends('x_expense_ids.amount')
    def _compute_total_expense(self):
        for session in self:
            session.x_total_expense = sum(session.x_expense_ids.mapped('amount'))


    @api.model
    def cron_validate_closing_sessions(self):
        """
        Scheduled action to automatically validate sessions 
        that were closed from Flutter but are still in 'closing_control' state.
        """
        sessions = self.search([
            ('state', '=', 'closing_control'),
            ('x_is_purecf_session', '=', True) # Only target our mobile sessions
        ])
        
        for session in sessions:
            try:
                _logger.info("Background validating session: %s", session.name)
                session.action_pos_session_validate()
            except Exception as e:
                _logger.error("Background validation failed for %s: %s", session.name, str(e))
                
                # Create an entry in our Audit Log so Admin can see it
                admin = self.env['res.users'].search([('x_role_type', '=', 'admin')], limit=1)
                self.env['purecf.audit.log'].sudo().create({
                    'res_model': 'pos.session',
                    'res_id': session.id,
                    'admin_id': admin.id if admin else self.env.uid,
                    'change_type': 'update',
                    'note': 'GAGAL VALIDASI OTOMATIS: %s. Silakan cek selisih kas atau jurnal di menu Point of Sale.' % str(e)
                })
