# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
from datetime import timedelta

class StockUsageAnalysis(models.TransientModel):
    _name = 'purecf.stock.usage.analysis'
    _description = 'Usage vs Sales Analysis'

    date_from = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    date_to = fields.Date(string='End Date', required=True, default=fields.Date.today)
    line_ids = fields.One2many('purecf.stock.usage.analysis.line', 'analysis_id', string='Analysis Lines')

    def action_calculate(self):
        self.line_ids.unlink()
        data = self.get_usage_data(self.date_from, self.date_to)
        lines = []
        for line in data:
            # Create a copy without the extra fields for dashboard
            row = line.copy()
            row.pop('ingredient_name', None)
            row.pop('uom_name', None)
            lines.append((0, 0, row))
        self.write({'line_ids': lines})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purecf.stock.usage.analysis',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def get_usage_data(self, date_from, date_to):
        # 1. Get all ingredients
        ingredients = self.env['product.template'].search([('x_is_ingredient', '=', True)])
        
        results = []
        for ingredient in ingredients:
            # 2. Start Qty
            last_opname_before = self.env['purecf.stock.opname.line'].search([
                ('product_id', '=', ingredient.id),
                ('date', '<', date_from)
            ], order='id desc', limit=1)
            start_qty = last_opname_before.new_qty if last_opname_before else 0.0
            
            # 3. End Qty
            last_opname_end = self.env['purecf.stock.opname.line'].search([
                ('product_id', '=', ingredient.id),
                ('date', '>=', date_from),
                ('date', '<=', date_to)
            ], order='id desc', limit=1)
            end_qty = last_opname_end.new_qty if last_opname_end else ingredient.qty_available
            
            # 4. Stock In
            stock_in_logs = self.env['purecf.audit.log'].search([
                ('res_model', '=', 'product.template'),
                ('res_id', '=', ingredient.id),
                ('change_type', '=', 'stock_in'),
                ('create_date', '>=', fields.Datetime.to_datetime(date_from)),
                ('create_date', '<', fields.Datetime.to_datetime(date_to) + timedelta(days=1))
            ])
            total_in = 0.0
            for log in stock_in_logs:
                try:
                    new_s = json.loads(log.new_state)
                    old_s = json.loads(log.old_state)
                    total_in += (new_s.get('qty_available', 0) - old_s.get('qty_available', 0))
                except: continue

            actual_consumed = start_qty + total_in - end_qty
            
            # 5. Related Sales
            bom_lines = self.env['mrp.bom.line'].search([('product_id', '=', ingredient.product_variant_id.id)])
            product_templates = bom_lines.mapped('bom_id.product_tmpl_id')
            
            sale_details = []
            if product_templates:
                order_lines = self.env['pos.order.line'].search([
                    ('product_id.product_tmpl_id', 'in', product_templates.ids),
                    ('order_id.date_order', '>=', fields.Datetime.to_datetime(date_from)),
                    ('order_id.date_order', '<', fields.Datetime.to_datetime(date_to) + timedelta(days=1)),
                    ('order_id.state', 'in', ['paid', 'done', 'invoiced'])
                ])
                for pt in product_templates:
                    qty = sum(order_lines.filtered(lambda l: l.product_id.product_tmpl_id.id == pt.id).mapped('qty'))
                    if qty > 0:
                        sale_details.append(f"{pt.name} ({int(qty)})")

            if actual_consumed > 0 or sale_details:
                results.append({
                    'ingredient_id': ingredient.id,
                    'ingredient_name': ingredient.name,
                    'uom_name': ingredient.uom_id.name,
                    'start_qty': start_qty,
                    'stock_in': total_in,
                    'end_qty': end_qty,
                    'actual_consumed': actual_consumed,
                    'related_sales': ", ".join(sale_details) or "-"
                })
        return results

class StockUsageAnalysisLine(models.TransientModel):
    _name = 'purecf.stock.usage.analysis.line'
    _description = 'Usage vs Sales Analysis Line'

    analysis_id = fields.Many2one('purecf.stock.usage.analysis', ondelete='cascade')
    ingredient_id = fields.Many2one('product.template', string='Ingredient')
    uom_id = fields.Many2one(related='ingredient_id.uom_id')
    start_qty = fields.Float(string='Stok Awal')
    stock_in = fields.Float(string='Masuk')
    end_qty = fields.Float(string='Stok Akhir')
    actual_consumed = fields.Float(string='Terpakai (Actual)')
    related_sales = fields.Text(string='Produk Terjual (Qty)')
