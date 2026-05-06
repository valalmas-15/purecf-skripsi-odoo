# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    x_can_approve_void = fields.Boolean(string='Void Approval', default=False, help="Manager power to authorize voided transactions.")
    x_employee_pin = fields.Char(string='POS PIN', help="Specific PIN for the Flutter App.")
    x_pos_config_id = fields.Many2one(
        'pos.config',
        string='Toko Penugasan'
    )

    def _sync_user_groups_from_job(self):
        """Sync Odoo Groups and App Role based on Job Position."""
        for employee in self:
            if not employee.user_id or not employee.job_id:
                continue
            
            # Map Job Name -> (Group XML ID, App Role Type)
            job_mapping = {
                'Owner': ('purecf_erp.group_purecf_owner', 'admin'),
                'Supervisor': ('purecf_erp.group_purecf_supervisor', 'manager'),
                'Kasir': ('purecf_erp.group_purecf_kasir', 'cashier'),
            }
            
            job_data = job_mapping.get(employee.job_id.name)
            if job_data:
                group_xml_id, role_type = job_data
                group = self.env.ref(group_xml_id, raise_if_not_found=False)
                
                if group:
                    # Purecf groups to manage (cleanup others)
                    purecf_group_xml_ids = [
                        'purecf_erp.group_purecf_owner',
                        'purecf_erp.group_purecf_supervisor',
                        'purecf_erp.group_purecf_kasir'
                    ]
                    purecf_group_ids = []
                    for xml_id in purecf_group_xml_ids:
                        g = self.env.ref(xml_id, raise_if_not_found=False)
                        if g:
                            purecf_group_ids.append(g.id)
                    
                    # Prepare group commands
                    commands = [(3, gid) for gid in purecf_group_ids if gid != group.id]
                    commands.append((4, group.id))
                    
                    # Update User with sudo to bypass Access Rights restrictions
                    employee.user_id.sudo().write({
                        'groups_id': commands,
                        'x_role_type': role_type
                    })

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._sync_user_groups_from_job()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if 'job_id' in vals or 'user_id' in vals:
            self._sync_user_groups_from_job()
        return res

