# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_is_ingredient = fields.Boolean(string='Is Ingredient', default=False, help="Identify raw materials for BoM filters in Flutter.")
    x_vendor_id = fields.Many2one('res.partner', string='Main Vendor', help="Primary source for this ingredient.")
    x_is_purecf_product = fields.Boolean(string='Is Purecf Product', default=False, help="Flag this product to be included in the Purecf Cafe POS.")
    x_min_qty = fields.Float(string='Minimum Quantity', default=0.0, help="Minimum stock level before warning.")

    x_main_bom_id = fields.Many2one('mrp.bom', string="Main BoM", compute='_compute_x_main_bom_id', store=True)
    x_bom_line_ids = fields.One2many(related='x_main_bom_id.bom_line_ids', readonly=False, string="Recipe Lines")

    @api.depends('bom_ids')
    def _compute_x_main_bom_id(self):
        for rec in self:
            if rec.bom_ids:
                rec.x_main_bom_id = rec.bom_ids[0].id
            else:
                rec.x_main_bom_id = False

    def action_create_bom(self):
        self.ensure_one()
        if not self.x_main_bom_id:
            bom = self.env['mrp.bom'].create({
                'product_tmpl_id': self.id,
                'product_qty': 1.0,
                'type': 'phantom',
            })
            self.x_main_bom_id = bom.id

    def action_get_effective_qty(self):
        """
        Calculates how many units of this product can be made based on BoM/ingredients.
        Used for real-time stock sync in Flutter for Kit/BoM products.
        """
        self.ensure_one()
        # For consumables (like water), assume unlimited for POS UI unless it's a kit
        if self.type == 'consu' and not self.env['mrp.bom'].sudo().search([('product_tmpl_id', '=', self.id)], limit=1):
            return 999.0
        
        bom = self.env['mrp.bom'].sudo().search([
            '|', ('product_tmpl_id', '=', self.id), ('product_id', '=', self.product_variant_id.id)
        ], limit=1)
        
        if not bom:
             return self.qty_available or 0.0

        # If it has a BoM (Kit), calculate potential quantity based on ingredients
        potential_qtys = []
        for line in bom.bom_line_ids:
            # We track ingredients that are 'product' type
            component_qty = line.product_id.qty_available or 0.0
            needed_qty = line.product_qty
            if needed_qty > 0:
                # Potential = (Total Component Stock) / (Qty needed for 1 unit of final product)
                potential_qtys.append(component_qty / (needed_qty / (bom.product_qty or 1.0)))
        
        return min(potential_qtys) if potential_qtys else 0.0

    def _get_purecf_stock_location(self):
        """Helper to find the correct stock location based on the user's assigned POS/Warehouse."""
        user = self.env.user
        
        # 1. Try to find via Employee -> POS Config (The "Workplace")
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if employee and employee.x_pos_config_id:
            # Use the assigned POS shop's warehouse
            pos_config = employee.x_pos_config_id
            if pos_config.picking_type_id and pos_config.picking_type_id.warehouse_id:
                return pos_config.picking_type_id.warehouse_id.lot_stock_id
        
        # 2. Fallback to User's direct warehouse assignment
        if user.x_allowed_warehouse_id:
            return user.x_allowed_warehouse_id.lot_stock_id
            
        # 3. Last resort fallback to the first internal location
        return self.env['stock.location'].sudo().search([('usage', '=', 'internal')], limit=1)

    def action_update_stock_manual(self, new_qty, admin_id, location_id=None, opname_id=None):
        """
        Updates the total stock for this product based on count from Flutter.
        Performs an Inventory Adjustment (Stock Opname) and records audit log.
        """
        self.ensure_one()
        product = self.product_variant_id
        if not product:
            return False

        # Only storable products can have quants and inventory adjustments
        if self.type != 'product':
            return True

        # Determine target location
        if not location_id:
            location = self._get_purecf_stock_location()
            location_id = location.id
            
        # Snapshot OLD state SPECIFIC to this location
        old_qty = self.with_context(location=location_id).qty_available

        # Create and apply inventory adjustment in Odoo 17 style
        quant = self.env['stock.quant'].sudo().with_context(inventory_mode=True).search([
            ('product_id', '=', product.id),
            ('location_id', '=', location_id)
        ], limit=1)
        
        if not quant:
            quant = self.env['stock.quant'].sudo().with_context(inventory_mode=True).create({
                'product_id': product.id,
                'location_id': location_id,
                'inventory_quantity': float(new_qty)
            })
        else:
            quant.inventory_quantity = float(new_qty)
            
        # Use sudo() explicitly on the action call to ensure manager bypass
        quant.sudo().action_apply_inventory()
        
        # Record Audit Log
        self.env['purecf.audit.log'].sudo().create({
            'res_model': 'product.template',
            'res_id': self.id,
            'admin_id': admin_id or self.env.uid,
            'change_type': 'stock_adj',
            'old_state': json.dumps({'qty_available': old_qty, 'location_id': location_id}),
            'new_state': json.dumps({'qty_available': float(new_qty), 'location_id': location_id}),
            'note': 'Manual Stock Update from Flutter/Dashboard',
            'opname_id': opname_id
        })
        
        return True

    def action_add_stock_incoming(self, incoming_qty, admin_id, total_price=0.0, note=None):
        """
        Increments the current stock (Belanja/Stock Masuk).
        Also updates standard_price (cost) if price is provided.
        """
        self.ensure_one()
        product = self.product_variant_id
        if not product:
            return False
            
        # Determine target location
        location = self._get_purecf_stock_location()
        if not location:
            return False
            
        # Get old qty SPECIFIC to this location
        old_qty = self.with_context(location=location.id).qty_available
        incoming_qty = float(incoming_qty)
        new_total = old_qty + incoming_qty
        
        # Update cost if price provided
        if total_price and incoming_qty > 0:
            unit_price = float(total_price) / incoming_qty
            self.sudo().write({'standard_price': unit_price})
        
        # Only storable products can have quants and inventory adjustments
        if self.type != 'product':
            return True

        # Use simple quant approach for speed in this demo/skripsi
        quant = self.env['stock.quant'].sudo().with_context(inventory_mode=True).search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id)
        ], limit=1)
        
        if not quant:
            quant = self.env['stock.quant'].sudo().with_context(inventory_mode=True).create({
                'product_id': product.id,
                'location_id': location.id,
                'inventory_quantity': new_total
            })
        else:
            quant.inventory_quantity = new_total
            
        quant.sudo().action_apply_inventory()
        
        # Record Audit Log
        self.env['purecf.audit.log'].sudo().create({
            'res_model': 'product.template',
            'res_id': self.id,
            'admin_id': admin_id or self.env.uid,
            'change_type': 'stock_in',
            'old_state': json.dumps({'qty_available': old_qty, 'cost': self.standard_price, 'location_id': location.id}),
            'new_state': json.dumps({'qty_available': new_total, 'cost': self.standard_price, 'location_id': location.id}),
            'note': note or 'Stock Incoming from Dashboard'
        })

        # AUTO-CASH RECONCILIATION: Create an expense record to deduct cash balance
        if total_price and total_price > 0:
            self.env['purecf.expense'].sudo().create({
                'name': f'Belanja Stok: {self.name}',
                'amount': float(total_price),
                'date': fields.Datetime.now(),
                'note': f'[Bahan Baku] Pembelian {incoming_qty} {self.uom_id.name} {self.name}',
                # If we have a session, link it for reconciliation
                'session_id': self.env['pos.session'].search([('state', '=', 'opened')], limit=1).id
            })

        return True

    def action_update_with_audit(self, vals, admin_id, note=None):
        """
        Granular update method. Only logs fields that actually change.
        Requires Admin PIN (via Controller).
        """
        self.ensure_one()
        old_state = {}
        new_state = {}
        
        for field, new_val in vals.items():
            current_val = getattr(self, field)
            # Simple check for change
            if hasattr(current_val, 'id'): current_val = current_val.id # Handle M2O
            
            if str(current_val) != str(new_val):
                old_state[field] = current_val
                new_state[field] = new_val
        
        if not old_state:
            return True # Nothing changed
            
        # Perform the actual write
        self.write(vals)
        
        # Record Log
        self.env['purecf.audit.log'].sudo().create({
            'res_model': 'product.template',
            'res_id': self.id,
            'admin_id': admin_id or self.env.uid,
            'change_type': 'update',
            'old_state': json.dumps(old_state, default=str),
            'new_state': json.dumps(new_state, default=str),
            'note': note or 'Manual Edit via Admin Validation'
        })
        return True
