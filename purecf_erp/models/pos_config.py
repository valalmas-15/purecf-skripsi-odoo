# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PosConfig(models.Model):
    _inherit = 'pos.config'

    x_address = fields.Text(string='Alamat Toko')
    x_phone = fields.Char(string='No. Telepon')
    x_employee_ids = fields.Many2many(
        'hr.employee',
        'pos_config_purecf_employee_rel',
        'config_id',
        'employee_id',
        string='Daftar Karyawan'
    )

    @api.constrains('x_employee_ids')
    def _check_employee_unique_assignment(self):
        for config in self:
            for employee in config.x_employee_ids:
                # Cari apakah karyawan ini sudah ada di toko lain
                other_configs = self.env['pos.config'].search([
                    ('id', '!=', config.id),
                    ('x_employee_ids', 'in', employee.id)
                ])
                if other_configs:
                    raise ValidationError(_(
                        "Karyawan %s sudah terdaftar di toko lain (%s). Satu karyawan hanya boleh bekerja di 1 toko."
                    ) % (employee.name, other_configs[0].name))
