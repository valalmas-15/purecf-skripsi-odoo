# -*- coding: utf-8 -*-
from odoo import models, fields, api

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    x_unit_cost = fields.Float(string='Cost/Unit', compute='_compute_purecf_costs')
    x_total_cost = fields.Float(string='Total Cost', compute='_compute_purecf_costs')
    currency_id = fields.Many2one('res.currency', related='bom_id.company_id.currency_id', string="Currency")

    @api.depends('product_id', 'product_qty', 'product_uom_id', 'bom_id.company_id.currency_id')
    def _compute_purecf_costs(self):
        for line in self:
            if not line.product_id:
                line.x_unit_cost = 0.0
                line.x_total_cost = 0.0
                continue
            
            # Get the cost of the product (standard_price)
            # standard_price is in the product's default UOM (product_id.uom_id)
            product_cost = line.product_id.standard_price
            
            # If BoM line UOM is different from product UOM, convert cost
            line_unit_cost = product_cost
            if line.product_uom_id and line.product_id.uom_id and line.product_uom_id != line.product_id.uom_id:
                # Convert the cost from product's UOM to BoM line's UOM
                # Example: Product cost is 10.000 / kg. BoM line is in grams (gr).
                # line_unit_cost should be 10 / gr.
                line_unit_cost = line.product_id.uom_id._compute_price(product_cost, line.product_uom_id)
                
            line.x_unit_cost = line_unit_cost
            line.x_total_cost = line_unit_cost * line.product_qty
