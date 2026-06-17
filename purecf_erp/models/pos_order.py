# -*- coding: utf-8 -*-
from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    x_offline_id = fields.Char(string='Offline Order ID', index=True, help="Unique ID from Flutter POS for sync.")
    x_is_purecf_order = fields.Boolean(string='Is Purecf Order', default=False, help="Identify if this order came from the Flutter App.")
    active = fields.Boolean(string='Active', default=True, help="Set to false to hide the order (Archive) without deleting it.")
    
    # Custom Payment Info for Flutter
    x_payment_method = fields.Char(string='Payment Method (Mobile)')
    x_cashier = fields.Char(string='Nama Kasir (Mobile)')
    x_nominal = fields.Float(string='Nominal Bayar (Mobile)')
    x_kembalian = fields.Float(string='Kembalian (Mobile)')
    
    # Takeaway and Plastic Info
    x_order_type = fields.Selection([
        ('Dine In', 'Dine In'),
        ('Takeaway', 'Takeaway')
    ], string='Order Type', default='Dine In')
    x_plastic_1cup = fields.Integer(string='Plastik Minuman 1 Cup')
    x_plastic_2cup = fields.Integer(string='Plastik Minuman 2 Cup')
    x_plastic_food = fields.Integer(string='Plastik Makanan')

    _sql_constraints = [
        ('x_offline_id_unique', 'unique(x_offline_id)', 'Offline ID must be unique!'),
    ]

    @api.model
    def sync_from_flutter(self, vals):
        """
        Custom method for real-time JSON-RPC sync from Flutter.
        Handles idempotency and immediate validation.
        """
        offline_id = vals.get('x_offline_id')
        if not offline_id:
            raise UserError(_("Missing Offline Order ID."))

        existing = self.search([('x_offline_id', '=', offline_id)], limit=1)
        if existing:
            return {
                'status': 'already_exists',
                'id': existing.id,
                'name': existing.name
            }

        # Ensure session is open
        session_id = vals.get('session_id')
        if not session_id:
            # Fallback to any open session for this user if not provided
            session = self.env['pos.session'].search([
                ('state', 'in', ['opened', 'opening_control']),
                ('user_id', '=', self.env.uid)
            ], limit=1)
            if not session:
                # Fallback to any open session (global) as a last resort
                session = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
            
            if not session:
                raise UserError(_("No open POS session found. Please 'Open Cashier' first."))
            vals['session_id'] = session.id

        # Mark as Purecf Order
        vals['x_is_purecf_order'] = True

        # Ensure full_product_name is set for each line if missing (important for Odoo 17)
        if vals.get('lines'):
            for line_cmd in vals['lines']:
                if isinstance(line_cmd, (list, tuple)) and line_cmd[0] == 0:
                    line_vals = line_cmd[2]
                    if not line_vals.get('full_product_name') and line_vals.get('product_id'):
                        product = self.env['product.product'].browse(line_vals['product_id'])
                        line_vals['full_product_name'] = product.display_name

        # Force date_order to current UTC time to prevent timezone mismatches.
        # Only do this if not explicitly provided (e.g. historical import)
        if not vals.get('date_order'):
            vals['date_order'] = fields.Datetime.now()


        # Create the order
        order = self.create(vals)

        # ── Record Payment Automatically (Crucial for Session Reconciliation) ──
        amount_paid = vals.get('amount_paid', order.amount_total)
        payment_method_name = vals.get('x_payment_method')
        
        if amount_paid > 0 and payment_method_name:
            # Find the corresponding Odoo Payment Method within the session's allowed methods
            session = self.env['pos.session'].browse(vals['session_id'])
            allowed_methods = session.config_id.payment_method_ids
            
            # Map simple names from Flutter to potential Odoo names
            search_names = [payment_method_name.lower()]
            if payment_method_name.lower() == 'cash':
                search_names += ['tunai', 'tunai / cash', 'cashier cash']
            elif payment_method_name.lower() == 'qris':
                search_names += ['qris', 'gopay', 'ovo', 'shopeepay', 'qr']
            elif payment_method_name.lower() == 'transfer':
                search_names += ['transfer', 'bank', 'bank transfer', 'mandiri', 'bca', 'bri', 'bni']
            
            payment_method = allowed_methods.filtered(
                lambda m: m.name.lower() in search_names
            )
            
            if not payment_method:
                # Fallback 1: Partial match (contains)
                payment_method = allowed_methods.filtered(
                    lambda m: any(sn in m.name.lower() for sn in search_names)
                )
            
            if not payment_method:
                # Fallback 2: Take the first available method from the session config
                payment_method = allowed_methods[:1]

            if payment_method:
                payment_method = payment_method[0]
                order.add_payment({
                    'amount': amount_paid,
                    'payment_date': fields.Datetime.now(),
                    'payment_method_id': payment_method.id,
                    'pos_order_id': order.id,
                    'session_id': order.session_id.id,
                })

        # Trigger validation (docks stock, creates journal entries)
        try:
            # Recalculate Odoo total to ensure it matches payments
            order._compute_batch_amount_all()
            
            # If there's a tiny discrepancy (tax rounding, etc), adjust the last payment
            if order.payment_ids and abs(order.amount_total - order.amount_paid) > 0 and abs(order.amount_total - order.amount_paid) < 10:
                last_payment = order.payment_ids[0]
                last_payment.sudo().write({'amount': last_payment.amount + (order.amount_total - order.amount_paid)})
                order._compute_batch_amount_all()

            # Attempt standard Odoo validation
            if order.state == 'draft':
                try:
                    order.action_pos_order_paid()
                except Exception as e:
                    _logger.warning("Standard action_pos_order_paid failed, forcing state: %s", str(e))
                    order.write({'state': 'paid'})
            
            # Fast-Sync: Bypass stock.picking and directly update stock.quant
            if order.state in ['paid', 'done', 'invoiced']:
                # Get location from POS config
                location = False
                if order.session_id and order.session_id.config_id and order.session_id.config_id.picking_type_id:
                    location = order.session_id.config_id.picking_type_id.default_location_src_id
                
                for line in order.lines:
                    self._manual_stock_deduct_fallback(line.product_id, line.qty, location=location)
                
                # Deduct Plastics
                plastic_configs = [
                    ('Plastik Minuman 1 Cup', order.x_plastic_1cup),
                    ('Plastik Minuman 2 Cup', order.x_plastic_2cup),
                    ('Plastik Makanan', order.x_plastic_food),
                ]
                for p_name, p_qty in plastic_configs:
                    if p_qty and p_qty > 0:
                        plastic_product = self.env['product.product'].sudo().search([('name', '=', p_name)], limit=1)
                        if plastic_product:
                            self._manual_stock_deduct_fallback(plastic_product, p_qty, location=location)

            return {
                'status': 'success',
                'id': order.id,
                'name': order.name
            }

        except Exception as e:
            _logger.error("Critical error in order sync for %s: %s", offline_id, str(e))
            # Even on critical error, if we have the record, try to mark it paid so session can close
            if order and order.state == 'draft':
                order.write({'state': 'paid'})
            
            # Final fallback for stock if everything else failed
            location = False
            if order and order.session_id and order.session_id.config_id and order.session_id.config_id.picking_type_id:
                location = order.session_id.config_id.picking_type_id.default_location_src_id
                
            if order:
                for line in order.lines:
                    self._manual_stock_deduct_fallback(line.product_id, line.qty, location=location)
                
                # Deduct Plastics fallback
                plastic_configs = [
                    ('Plastik Minuman 1 Cup', order.x_plastic_1cup),
                    ('Plastik Minuman 2 Cup', order.x_plastic_2cup),
                    ('Plastik Makanan', order.x_plastic_food),
                ]
                for p_name, p_qty in plastic_configs:
                    if p_qty and p_qty > 0:
                        plastic_product = self.env['product.product'].sudo().search([('name', '=', p_name)], limit=1)
                        if plastic_product:
                            self._manual_stock_deduct_fallback(plastic_product, p_qty, location=location)

            return {
                'status': 'created_with_warning',
                'id': order.id if order else False,
                'message': str(e)
            }


    def _manual_stock_deduct_fallback(self, product, qty, location=None):
        """
        Manually deduct stock from the specific location.
        Handles both standard products and Kits (by deducting ingredients).
        """
        try:
            if not location:
                location = self.env['stock.location'].sudo().search([('usage', '=', 'internal')], limit=1)

            # Check if it's a Kit (Phantom BoM)
            bom = self.env['mrp.bom'].sudo().search([
                '|', ('product_tmpl_id', '=', product.product_tmpl_id.id),
                ('product_id', '=', product.id)
            ], limit=1)
            
            if bom and bom.type == 'phantom':
                for bom_line in bom.bom_line_ids:
                    ingredient = bom_line.product_id
                    needed_qty = qty * bom_line.product_qty
                    self._update_quant_manual(ingredient, location, -needed_qty)
            else:
                self._update_quant_manual(product, location, -qty)
        except Exception as e:
            _logger.error("Manual fallback deduction failed: %s", str(e))

    def _update_quant_manual(self, product, location, change_qty):
        """Helper to directly update stock.quant"""
        if product.type != 'product':
            return

        Quant = self.env['stock.quant'].with_env(self.env(user=SUPERUSER_ID))
        quant = Quant.with_context(inventory_mode=True).search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id)
        ], limit=1)
        
        if quant:
            quant.inventory_quantity = quant.quantity + change_qty
        else:
            quant = Quant.with_context(inventory_mode=True).create({
                'product_id': product.id,
                'location_id': location.id,
                'inventory_quantity': change_qty
            })
        quant.action_apply_inventory()

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    x_note = fields.Char(string='Note (Mobile)')
