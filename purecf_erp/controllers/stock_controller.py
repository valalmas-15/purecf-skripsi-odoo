# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class PurecfStockController(http.Controller):

    @http.route('/purecf/stock', type='http', auth='user', website=True)
    def stock_page(self, **kwargs):
        """
        Renders the custom Flutter-like stock management page.
        """
        # Fetch ingredients for initial load
        ingredients = request.env['product.product'].sudo().search([
            '|', ('x_is_ingredient', '=', True), ('purchase_ok', '=', True)
        ])
        
        # Format ingredients for JS use
        ingredients_data = []
        for p in ingredients:
            ingredients_data.append({
                'id': p.id,
                'name': p.name,
                'qty_available': p.qty_available,
                'uom': p.uom_id.name,
                'min_qty': p.x_min_qty if hasattr(p, 'x_min_qty') else 0, # Assuming this field exists based on Flutter code
                'list_price': p.list_price
            })

        values = {
            'ingredients': ingredients_data,
        }
        return request.render('purecf_erp.stock_management_page', values)
