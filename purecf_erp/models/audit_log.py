# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json

class PurecfAuditLog(models.Model):
    _name = 'purecf.audit.log'
    _description = 'Purecf Audit Log and Data Versioning'
    _order = 'create_date desc'

    res_model = fields.Char(string='Resource Model', required=True, index=True)
    res_id = fields.Integer(string='Resource ID', required=True, index=True)
    admin_id = fields.Many2one('res.users', string='Authorized Admin', required=True)
    change_type = fields.Selection([
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('revert', 'Data Reversion'),
        ('stock_adj', 'Stock Adjustment'),
        ('stock_in', 'Incoming Stock (Inbound)'),
        ('monthly_close', 'Monthly Financial Closing')
    ], string='Action Type', required=True)
    
    old_state = fields.Text(string='Old State (Snaphot)')
    new_state = fields.Text(string='New State (Snaphot)')
    note = fields.Text(string='Note/Reason')
    opname_id = fields.Many2one('purecf.stock.opname', string='Linked Opname Report')
    reverted = fields.Boolean(string='Was Reverted?', default=False)

    def action_revert(self):
        """
        Reverts the target record to the state stored in old_state.
        """
        self.ensure_one()
        if not self.old_state:
            return False
        
        try:
            target_model = self.env[self.res_model].sudo().browse(self.res_id)
            if not target_model.exists():
                return False
            
            vals = json.loads(self.old_state)
            
            # Snaphot current state of ONLY those fields for the Revert log entry
            current_vals = {}
            for field in vals.keys():
                current_vals[field] = getattr(target_model, field)
                # Handle Many2one
                if hasattr(current_vals[field], 'id'):
                    current_vals[field] = current_vals[field].id

            # Record this reversion in a NEW log entry for audit trail purity
            self.env['purecf.audit.log'].sudo().create({
                'res_model': self.res_model,
                'res_id': self.res_id,
                'admin_id': self.env.uid, 
                'change_type': 'revert',
                'old_state': json.dumps(current_vals, default=str),
                'new_state': self.old_state,
                'note': 'Reverted using log ID: %s' % self.id
            })

            target_model.write(vals)
            self.reverted = True
            return True
        except Exception:
            return False
