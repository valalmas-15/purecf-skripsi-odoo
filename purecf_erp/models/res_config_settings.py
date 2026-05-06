# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    closing_day = fields.Integer(
        string='Monthly Closing Day',
        config_parameter='purecf_erp.closing_day',
        default=25,
        help="The day of the month when financial reports are closed (e.g., 25th)."
    )
    
    purecf_admin_pin = fields.Char(
        string='Global Admin PIN',
        config_parameter='purecf_erp.admin_pin',
        help="Global PIN for admin overrides in the Flutter POS."
    )
