import io
import xlsxwriter
from odoo import http, fields, _
from odoo.http import request, content_disposition
import logging
import json
import pytz
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class PurecfApiController(http.Controller):

    def _check_admin_pin(self, pin):
        """Helper to validate if a PIN belongs to an Admin user or matches the Employee's POS PIN."""
        if not pin:
            return False, "PIN is required for this action."
        
        # 1. Check if it's an Admin PIN
        admin = http.request.env['res.users'].sudo().search([
            ('x_role_type', '=', 'admin'),
            ('x_admin_pin', '=', str(pin))
        ], limit=1)
        
        if admin:
            return admin, "Success (Admin)"
            
        # 2. Check if it's the current user's Employee PIN (or any employee for flexibility)
        employee = http.request.env['hr.employee'].sudo().search([
            ('x_employee_pin', '=', str(pin))
        ], limit=1)
        
        if employee and employee.user_id:
            return employee.user_id, "Success (Employee)"
            
        return False, "Invalid PIN."

    def _check_supervisor_pin(self, pin, pos_config_id):
        """Check if PIN belongs to a Supervisor assigned to this POS."""
        if not pin:
            return False, "PIN Supervisor diperlukan untuk menyetujui selisih kas."
            
        # 1. Check if it's an Owner PIN (Owner can always approve)
        admin = http.request.env['res.users'].sudo().search([
            ('x_role_type', '=', 'owner'),
            ('x_admin_pin', '=', str(pin))
        ], limit=1)
        if admin:
            return admin, "Success (Owner)"

        # 2. Find employee with this PIN and assigned to this POS
        employee = http.request.env['hr.employee'].sudo().search([
            ('x_employee_pin', '=', str(pin)),
            ('x_pos_config_id', '=', pos_config_id)
        ], limit=1)
        
        if not employee:
            return False, "PIN tidak valid atau Anda bukan Supervisor di Toko ini."
        
        # Check if they have Supervisor or Owner group
        user = employee.user_id
        if user.has_group('purecf_erp.group_purecf_supervisor') or user.has_group('purecf_erp.group_purecf_owner'):
            return user, "Success (Supervisor)"
            
        return False, "Hanya Supervisor yang dapat menyetujui selisih kas."

    def _get_current_warehouse_id(self, user):
        """Helper to resolve warehouse ID based on Employee -> POS Config -> Warehouse."""
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if employee and employee.x_pos_config_id:
            pos_config = employee.x_pos_config_id
            if pos_config.picking_type_id and pos_config.picking_type_id.warehouse_id:
                return pos_config.picking_type_id.warehouse_id.id
        
        return user.x_allowed_warehouse_id.id if user.x_allowed_warehouse_id else False

    def _utc_to_wib_str(self, utc_dt):
        """Convert UTC datetime to WIB (Asia/Jakarta) string."""
        if not utc_dt:
            return ''
        if isinstance(utc_dt, str):
            utc_dt = fields.Datetime.from_string(utc_dt)
        # Odoo datetimes are native but UTC
        wib_dt = utc_dt.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Jakarta'))
        return wib_dt.strftime('%Y-%m-%d %H:%M:%S')

    @http.route('/api/purecf/auth', type='json', auth='none', methods=['POST'], csrf=False)
    def authenticate(self, db, login, password):
        """
        Custom authentication for Flutter POS.
        Returns session_id and user profile info.
        """
        try:
            request.session.authenticate(db, login, password)
            user = request.env.user
            _logger.info("Authenticating user: %s (ID: %s)", user.login, user.id)
            
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            config = employee.x_pos_config_id if employee and employee.x_pos_config_id else False
            _logger.info("Employee: %s, POS Config: %s", employee.name if employee else 'None', config.name if config else 'None')

            # Restriction: Kasir and Supervisor must be assigned to a POS Workplace
            # Using ref to be absolutely sure about the group
            group_kasir = request.env.ref('purecf_erp.group_purecf_kasir')
            group_supervisor = request.env.ref('purecf_erp.group_purecf_supervisor')
            
            is_restricted = user.has_group('purecf_erp.group_purecf_kasir') or user.has_group('purecf_erp.group_purecf_supervisor')
            _logger.info("Is restricted role: %s", is_restricted)

            if is_restricted and not config:
                _logger.warning("Access denied for %s: No POS assigned", user.login)
                request.session.logout()
                # Raising AccessDenied will make Odoo return a JSON-RPC error
                from odoo.exceptions import AccessDenied
                raise AccessDenied('Login Gagal: Akun Kasir/Supervisor Anda belum ditugaskan ke Toko manapun. Harap hubungi Admin.')
            
            # Get warehouse based on the new logic (Workplace first)
            warehouse_name = 'General'
            if config and config.picking_type_id and config.picking_type_id.warehouse_id:
                warehouse_name = config.picking_type_id.warehouse_id.name
            elif user.x_allowed_warehouse_id:
                warehouse_name = user.x_allowed_warehouse_id.name
            
            return {
                'status': 'success',
                'session_id': request.session.sid,
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'role': user.x_role_type or 'cashier',
                    'warehouse': warehouse_name,
                    'pos_config_id': config.id if config else False,
                    'pos_config_name': config.name if config else False,
                    'admin_pin': employee.x_employee_pin if employee else (user.x_admin_pin if user.x_admin_pin else False),
                }
            }
        except Exception as e:
            _logger.error("Auth Failure: %s", str(e))
            # Pass the actual error message if it's one of our custom ones
            error_msg = str(e) if "Login Gagal" in str(e) else "Login Gagal: Periksa Email/Password."
            return {'status': 'error', 'message': error_msg}

    @http.route('/api/purecf/sync_products', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_products(self, **kwargs):
        """
        Fetch saleable products and kits from Odoo.
        """
        try:
            # Force clear Odoo's internal cache for stock quantities 
            # to ensure real-time accuracy after a transaction.
            request.env['product.template'].sudo().invalidate_model(['qty_available'])
            request.env['product.product'].sudo().invalidate_model(['qty_available'])
            
            user = request.env.user
            # Get warehouse context for accurate stock (Prioritize POS Workplace)
            warehouse_id = self._get_current_warehouse_id(user)
            ctx = dict(request.env.context, warehouse=warehouse_id)

            # Fetch products from Odoo with warehouse context
            products_rec = request.env['product.template'].sudo().with_context(ctx).search(
                [('sale_ok', '=', True), ('x_is_purecf_product', '=', True)]
            )
            # Force Odoo to recompute quantities to ensure real-time accuracy
            products_rec.sudo().with_context(ctx)._compute_quantities()
            
            products_data = []
            for p in products_rec:
                # Align with master_data.xml: Use POS Categories (pos_categ_ids)
                pos_category_id = p.pos_categ_ids[0].id if p.pos_categ_ids else False
                
                products_data.append({
                    'id': p.id,
                    'name': p.name,
                    'list_price': p.list_price,
                    'categ_id': pos_category_id,
                    'uom_id': p.uom_id.id,
                    'qty_available': p.action_get_effective_qty(),
                })
            
            # Fetch POS Categories
            categories = request.env['pos.category'].sudo().search_read([], ['id', 'name'])
            
            return {
                'status': 'success',
                'products': products_data,
                'categories': categories
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/get_product_details', type='json', auth='user', methods=['POST'], csrf=False)
    def get_product_details(self, product_id, **kwargs):
        """Fetch full details of a product including its BoM (Recipe)"""
        try:
            product = request.env['product.template'].sudo().browse(product_id)
            if not product.exists():
                return {'status': 'error', 'message': 'Product not found'}

            # Find BoM
            bom = request.env['mrp.bom'].sudo().search([
                '|', ('product_tmpl_id', '=', product.id), ('product_id', '=', product.product_variant_id.id)
            ], limit=1)

            bom_data = []
            if bom:
                for line in bom.bom_line_ids:
                    bom_data.append({
                        'id': line.id,
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.name,
                        'qty': line.product_qty,
                        'uom_name': line.product_uom_id.name
                    })

            # Fetch all available ingredients and purchasable products for selection
            ingredients = request.env['product.product'].sudo().search_read(
                ['|', ('x_is_ingredient', '=', True), ('purchase_ok', '=', True)],
                ['id', 'name', 'uom_id']
            )

            # Categories for the dropdown
            categories = request.env['pos.category'].sudo().search_read([], ['id', 'name'])

            return {
                'status': 'success',
                'id': product.id,
                'name': product.name,
                'list_price': product.list_price,
                'pos_category_id': product.pos_categ_ids[0].id if product.pos_categ_ids else False,
                'bom_id': bom.id if bom else False,
                'resep': bom_data,
                'available_ingredients': ingredients,
                'categories': categories
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/update_product_details', type='json', auth='user', methods=['POST'], csrf=False)
    def update_product_details(self, product_id, name, price, category_id, resep, **kwargs):
        """Update product info and its recipe lines"""
        try:
            product = request.env['product.template'].sudo().browse(product_id)
            if not product.exists():
                return {'status': 'error', 'message': 'Product not found'}

            # Update Product Template
            product.sudo().write({
                'name': name,
                'list_price': float(price),
                'pos_categ_ids': [(6, 0, [int(category_id)])] if category_id else []
            })

            # Update BoM
            bom = request.env['mrp.bom'].sudo().search([
                '|', ('product_tmpl_id', '=', product.id), ('product_id', '=', product.product_variant_id.id)
            ], limit=1)

            if not bom and resep:
                # Create new BoM if it doesn't exist
                bom = request.env['mrp.bom'].sudo().create({
                    'product_tmpl_id': product.id,
                    'product_qty': 1.0,
                    'type': 'phantom' # Default to Kit for Cafe
                })

            if bom:
                # Update lines: simpler to replace for this skripsi/demo
                bom.sudo().bom_line_ids.unlink()
                for line in resep:
                    request.env['mrp.bom.line'].sudo().create({
                        'bom_id': bom.id,
                        'product_id': int(line['product_id']),
                        'product_qty': float(line['qty'])
                    })

            return {'status': 'success', 'message': 'Product and Recipe updated successfully'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/sync_orders', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_orders(self, orders, **kwargs):
        """
        Process incoming real-time transactions from Flutter.
        """
        results = []
        for order_data in orders:
            try:
                # Use our custom model method for processing
                res = request.env['pos.order'].sudo().sync_from_flutter(order_data)
                
                if isinstance(res, dict) and 'status' in res:
                    # If it returns already_exists or error dict, pass it through but fix date if possible
                    if res.get('date_order'):
                        res['date_order'] = self._utc_to_wib_str(res['date_order'])
                    results.append(res)
                else:
                    # It's a record or success dict
                    results.append({
                        'status': 'success',
                        'id': res.id,
                        'name': res.name,
                        'date_order': self._utc_to_wib_str(res.date_order),
                        'total': res.amount_total
                    })

            except Exception as e:
                _logger.error("Order Sync Failure: %s", str(e))
                results.append({
                    'status': 'error', 
                    'offline_id': order_data.get('x_offline_id'), 
                    'message': str(e)
                })
        
        return {
            'status': 'finished', 
            'results': results
        }

    @http.route('/api/purecf/history', type='json', auth='user', methods=['POST'], csrf=False)
    def history(self, date=None, **kwargs):
        """
        Fetch daily transaction history for current cashier/warehouse.
        Prioritizes the current open session if available.
        """
        try:
            user = request.env.user
            
            # 1. Try to find an active session for the current user
            # We prioritize the active session ONLY if no specific date is requested
            active_session = False
            if not date:
                active_session = request.env['pos.session'].sudo().search([
                    ('state', '=', 'opened'),
                    ('user_id', '=', user.id)
                ], limit=1)
            
            if active_session:
                # If session is open, show ONLY orders from this session
                domain = [('session_id', '=', active_session.id)]
            else:
                # 2. Fallback to date-based if no active session OR if a specific date was requested
                target_date = date or fields.Date.today()
                domain = [
                    ('date_order', '>=', f"{target_date} 00:00:00"),
                    ('date_order', '<=', f"{target_date} 23:59:59")
                ]
                # Filter by warehouse/POS config to ensure users only see their own branch's history
                employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
                if employee and employee.x_pos_config_id:
                    domain.append(('session_id.config_id', '=', employee.x_pos_config_id.id))
                elif user.x_role_type == 'cashier':
                    domain.append(('user_id', '=', user.id))
            
            orders = request.env['pos.order'].sudo().search(domain, order='date_order desc')
            res_orders = []
            for order in orders:
                res_orders.append({
                    'id': order.id,
                    'name': order.name,
                    'amount_total': order.amount_total,
                    'date_order': self._utc_to_wib_str(order.date_order),

                    'state': order.state,
                    'payment_method': 'Cash' if (order.x_payment_method or 'Tunai').lower() in ['cash', 'tunai'] else (order.x_payment_method or 'Tunai'), # Simplified payment method info
                    'cashier': order.user_id.name, # Added cashier name
                    'lines': [{
                        'name': line.product_id.name,
                        'qty': line.qty,
                        'price_unit': line.price_unit,
                        'price_total': line.price_subtotal_incl,
                        'note': line.x_note,
                    } for line in order.lines]
                })
            return {
                'status': 'success',
                'orders': res_orders
            }
        except Exception as e:
            _logger.error("History Fetch Failure: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/create_product', type='json', auth='user', methods=['POST'], csrf=False)
    def create_product(self, name, price, admin_pin, category_id=None, **kwargs):
        """
        Create a new product from Flutter.
        Requires Admin PIN validation.
        """
        try:
            admin, msg = self._check_admin_pin(admin_pin)
            if not admin:
                return {'status': 'error', 'message': msg}

            vals = {
                'name': name,
                'list_price': float(price),
                'sale_ok': True,
                'x_is_purecf_product': True,
                'type': 'consu',  # Consumable by default for cafe items
                'available_in_pos': True,
                'pos_categ_ids': [(4, int(category_id))] if category_id else []
            }
            
            product = request.env['product.template'].sudo().create(vals)
            
            # Record Audit Log
            request.env['purecf.audit.log'].sudo().create({
                'res_model': 'product.template',
                'res_id': product.id,
                'admin_id': admin.id,
                'change_type': 'create',
                'new_state': json.dumps(vals, default=str),
                'note': 'Product created via Flutter POS'
            })

            return {
                'status': 'success',
                'id': product.id,
                'name': product.name
            }
        except Exception as e:
            _logger.error("Product Creation Failure: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/session/status', type='json', auth='user', methods=['POST'], csrf=False)
    def session_status(self, **kwargs):
        """Check if there is an open session for the assigned POS."""
        try:
            user = request.env.user
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            config = employee.x_pos_config_id if employee and employee.x_pos_config_id else False
            
            if not config:
                return {
                    'status': 'no_session', 
                    'message': 'Akun Anda belum ditugaskan ke Toko manapun. Harap hubungi Admin.',
                    'no_config': True
                }

            # Check for sessions that are actually "active" for the cashier
            session = request.env['pos.session'].sudo().search([
                ('config_id', '=', config.id),
                ('state', 'in', ['opened', 'opening_control']),
                ('user_id', '=', request.env.uid)
            ], limit=1)
            
            if session:
                # Get last closing cash from the previous closed session for this config
                last_session = request.env['pos.session'].sudo().search([
                    ('config_id', '=', config.id),
                    ('state', '=', 'closed')
                ], order='id desc', limit=1)
                
                return {
                    'status': 'open',
                    'session_id': session.id,
                    'session_name': session.name,
                    'user_id': session.user_id.id,
                    'user_name': session.user_id.name,
                    'state': session.state,
                    'last_closing_cash': last_session.cash_register_balance_end_real if last_session else 0.0
                }
                
            # If no active session, still return last closing cash for opening modal
            last_session = request.env['pos.session'].sudo().search([
                ('config_id', '=', config.id),
                ('state', '=', 'closed')
            ], order='id desc', limit=1)

            return {
                'status': 'no_session', 
                'message': 'No open session found.',
                'last_closing_cash': last_session.cash_register_balance_end_real if last_session else 0.0
            }
        except Exception as e:
            _logger.error("Session Status Error: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/session/open', type='json', auth='user', methods=['POST'], csrf=False)
    def session_open(self, cash_start=0.0):
        """Open a new POS session for the assigned shop."""
        try:
            user = request.env.user
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            config = employee.x_pos_config_id if employee and employee.x_pos_config_id else False
            
            if not config:
                # Fallback for admin
                config = request.env['pos.config'].sudo().search([], limit=1)

            if not config:
                return {'status': 'error', 'message': 'Akun Anda belum ditugaskan ke Toko manapun.'}

            # Check for existing open session for this POS (Must be 'closed' to open new one)
            existing = request.env['pos.session'].sudo().search([
                ('config_id', '=', config.id),
                ('state', '!=', 'closed')
            ], limit=1)
            
            if existing:
                # If it's already in opening_control and it belongs to current user, try to open it
                if existing.state == 'opening_control' and existing.user_id.id == request.env.uid:
                    if cash_start > 0:
                        existing.sudo().write({'cash_register_balance_start': float(cash_start)})
                    existing.action_pos_session_open()
                    return {'status': 'success', 'id': existing.id, 'message': 'Session opened.'}
                
                # If it belongs to someone else, we cannot use it
                if existing.user_id.id != request.env.uid:
                    return {
                        'status': 'error', 
                        'message': 'POS sedang digunakan oleh %s. Harap tutup sesi tersebut terlebih dahulu.' % existing.user_id.name
                    }
                
                return {'status': 'success', 'id': existing.id, 'message': 'Session already active.'}
            
            # Create and open session using Odoo's internal logic
            session = request.env['pos.session'].sudo().create({
                'user_id': request.env.uid,
                'config_id': config.id,
                'x_is_purecf_session': True, # Tag for background validation
            })
            
            if cash_start > 0:
                session.sudo().write({'cash_register_balance_start': float(cash_start)})
            
            session.action_pos_session_open()
            
            return {
                'status': 'success',
                'id': session.id,
                'name': session.name
            }
        except Exception as e:
            _logger.error("Session Open Failure: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/session/close', type='json', auth='user', methods=['POST'], csrf=False)
    def session_close(self, session_id=None, balance=None, supervisor_pin=None, expenses=None, stocks=None, **kwargs):
        """Close and validate the current session with expenses and stock opname."""
        try:
            session = False
            if session_id:
                try:
                    session = request.env['pos.session'].sudo().browse(int(session_id))
                    if not session.exists():
                        session = False
                except (ValueError, TypeError):
                    session = False
            
            if not session:
                session = request.env['pos.session'].sudo().search([
                    ('user_id', '=', request.env.uid),
                    ('state', '!=', 'closed')
                ], limit=1)
            
            if not session or session.state == 'closed':
                 return {'status': 'error', 'message': 'Tidak ada sesi aktif yang ditemukan untuk ditutup.'}

            # 1. Handle Expenses (Sent from Flutter local storage)
            if expenses and isinstance(expenses, list):
                for exp in expenses:
                    request.env['purecf.expense'].sudo().create({
                        'session_id': session.id,
                        'amount': float(exp.get('amount', 0)),
                        'note': exp.get('note', ''),
                        'date': fields.Datetime.now()
                    })
            
            # 2. Auto-validate any remaining draft orders before closing
            # This ensures payments are recorded and reflected in cash_register_balance_end
            draft_orders = session.order_ids.filtered(lambda o: o.state == 'draft')
            for d_order in draft_orders:
                try:
                    if not d_order.payment_ids:
                        pm = session.config_id.payment_method_ids[:1]
                        if pm:
                            d_order.add_payment({
                                'amount': d_order.amount_total,
                                'payment_date': fields.Datetime.now(),
                                'payment_method_id': pm.id,
                                'pos_order_id': d_order.id,
                                'session_id': session.id,
                            })
                    d_order.action_pos_order_paid()
                except Exception as e:
                    _logger.error("Could not auto-validate draft order %s during session close: %s", d_order.name, str(e))

            # Recalculate session fields to ensure theoretical balance is up to date
            session.sudo()._compute_total_expense()
            session.sudo().invalidate_recordset(['cash_register_balance_end'])
            # Odoo 17 uses _compute_cash_balance
            if hasattr(session, '_compute_cash_balance'):
                session.sudo()._compute_cash_balance()

            # 3. Variance Check
            if balance is not None:
                actual = float(balance)
                
                # Persist the actual balance to Odoo session record
                session.sudo().write({'cash_register_balance_end_real': actual})
                
                # Manually calculate theoretical cash using the same logic as the dashboard (name-based)
                cash_methods = session.config_id.payment_method_ids.filtered(
                    lambda m: 'cash' in m.name.lower() or 'tunai' in m.name.lower() or m.is_cash_count
                )
                cash_payments = session.order_ids.filtered(lambda o: o.state in ['paid', 'done', 'invoiced']).payment_ids.filtered(lambda p: p.payment_method_id in cash_methods)
                total_cash_payments = sum(cash_payments.mapped('amount'))
                
                theoretical = session.cash_register_balance_start + total_cash_payments - session.x_total_expense
                difference = theoretical - actual
                
                if abs(difference) > 1.0:
                    success, msg = self._check_supervisor_pin(supervisor_pin, session.config_id.id)
                    if not success:
                        return {
                            'status': 'error',
                            'error_code': 'supervisor_required',
                            'message': 'Selisih Rp %s (Sistem: %s vs Aktual: %s). Detail: Awal %s + Jual %s - Biaya %s.' % (
                                f"{abs(difference):,.0f}", 
                                f"{theoretical:,.0f}", 
                                f"{actual:,.0f}",
                                f"{session.cash_register_balance_start:,.0f}",
                                f"{total_cash_payments:,.0f}",
                                f"{session.x_total_expense:,.0f}"
                            )
                        }

                # 4. Generate Daily Report HTML for Odoo Backend Visibility
                # First, build a full payment map for the report
                p_map = {'Cash': 0.0, 'QRIS': 0.0, 'Transfer': 0.0}
                for payment in session.order_ids.payment_ids:
                    orig_name = payment.payment_method_id.name.lower()
                    if 'cash' in orig_name or 'tunai' in orig_name: pm_name = 'Cash'
                    elif 'qris' in orig_name: pm_name = 'QRIS'
                    elif 'transfer' in orig_name or 'bank' in orig_name: pm_name = 'Transfer'
                    else: continue
                    p_map[pm_name] = p_map.get(pm_name, 0.0) + payment.amount

                status_color = '#d9534f' if abs(difference) > 1.0 else '#5cb85c'
                status_text = '⚠️ ADA SELISIH' if abs(difference) > 1.0 else '✅ REKONSILIASI OK'

                report_html = f"""
                    <div style="font-family: sans-serif; max-width: 600px; border: 1px solid #eee; padding: 20px; border-radius: 12px; background: #fff;">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #D4A373; padding-bottom: 10px; margin-bottom: 20px;">
                            <h2 style="color: #D4A373; margin: 0;">Laporan Rekonsiliasi Kasir</h2>
                            <span style="background: {status_color}; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">{status_text}</span>
                        </div>
                        
                        <div style="margin-bottom: 20px;">
                            <h4 style="margin-bottom: 8px; color: #666; border-left: 4px solid #D4A373; padding-left: 8px;">1. Rekonsiliasi Kas (Cash)</h4>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr><td style="padding: 4px 0;">Modal Awal</td><td style="text-align: right;">Rp {session.cash_register_balance_start:,.0f}</td></tr>
                                <tr><td style="padding: 4px 0;">Total Jual Tunai</td><td style="text-align: right;">Rp {total_cash_payments:,.0f}</td></tr>
                                <tr><td style="padding: 4px 0; color: #d9534f;">Total Pengeluaran (-)</td><td style="text-align: right; color: #d9534f;">Rp {session.x_total_expense:,.0f}</td></tr>
                                <tr style="border-top: 1px solid #eee; font-weight: bold;">
                                    <td style="padding: 8px 0;">Saldo Teoretis</td><td style="text-align: right; padding: 8px 0;">Rp {theoretical:,.0f}</td></tr>
                                <tr style="font-weight: bold; color: #D4A373;">
                                    <td style="padding: 8px 0;">Saldo Aktual (Input)</td><td style="text-align: right; padding: 8px 0;">Rp {actual:,.0f}</td></tr>
                                <tr style="border-top: 1px double #eee; font-weight: bold; color: {status_color};">
                                    <td style="padding: 8px 0;">Selisih</td><td style="text-align: right; padding: 8px 0;">Rp {difference:,.0f}</td></tr>
                            </table>
                        </div>

                        <div style="margin-bottom: 20px;">
                            <h4 style="margin-bottom: 8px; color: #666;">2. Pembayaran Non-Tunai</h4>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr><td style="padding: 4px 0;">QRIS</td><td style="text-align: right;">Rp {p_map['QRIS']:,.0f}</td></tr>
                                <tr><td style="padding: 4px 0;">Transfer</td><td style="text-align: right;">Rp {p_map['Transfer']:,.0f}</td></tr>
                            </table>
                        </div>

                        <div>
                            <h4 style="margin-bottom: 8px; color: #666;">3. Rincian Pengeluaran</h4>
                            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                """
                
                for exp in session.x_expense_ids:
                    report_html += f'<tr><td style="padding: 4px 0;">• {exp.note}</td><td style="text-align: right;">Rp {exp.amount:,.0f}</td></tr>'
                
                if not session.x_expense_ids:
                    report_html += '<tr><td colspan="2" style="color: #999; font-style: italic; padding: 4px 0;">Tidak ada pengeluaran</td></tr>'

                report_html += """
                            </table>
                        </div>
                    </div>
                """
                
                session.sudo().write({
                    'x_flutter_daily_report': report_html,
                    'x_is_purecf_session': True
                })

            session.action_pos_session_closing_control()
            
            # Optionally validate immediately if supervisor approved or no difference
            # session.action_pos_session_validate()
            
            return {
                'status': 'closed', 
                'message': 'Sesi kasir telah selesai dan pengeluaran telah dicatat.'
            }
        except Exception as e:
            _logger.error("Session Close Failure: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/sync_ingredients', type='json', auth='user', methods=['POST'], csrf=False)
    def sync_ingredients(self, **kwargs):
        """Fetch all raw materials (ingredients) for stock management."""
        try:
            user = request.env.user
            warehouse_id = self._get_current_warehouse_id(user)
            ctx = dict(request.env.context, warehouse=warehouse_id)

            ingredients_rec = request.env['product.template'].sudo().with_context(ctx).search_read(
                ['|', ('x_is_ingredient', '=', True), ('purchase_ok', '=', True)],
                ['id', 'name', 'qty_available', 'uom_id', 'x_min_qty']
            )
            
            # Map keys to match Flutter expectations (qty, uom, min_qty)
            ingredients = []
            for ing in ingredients_rec:
                ingredients.append({
                    'id': ing['id'],
                    'name': ing['name'],
                    'qty': ing['qty_available'],
                    'qty_available': ing['qty_available'], # Keep for compatibility
                    'uom': ing['uom_id'][1] if isinstance(ing['uom_id'], (list, tuple)) else '',
                    'uom_id': ing['uom_id'],
                    'min_qty': ing['x_min_qty'],
                    'x_min_qty': ing['x_min_qty'], # Keep for compatibility
                })

            return {
                'status': 'success',
                'ingredients': ingredients
            }
        except Exception as e:
            _logger.error("Sync Ingredients Error: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/update_stock', type='json', auth='user', methods=['POST'], csrf=False)
    def update_stock(self, product_id, new_quantity, admin_pin=None, location_id=None):
        """Perform a manual stock adjustment for an ingredient."""
        try:
            session = request.env['pos.session'].sudo().search([
                ('user_id', '=', request.env.uid),
                ('state', '=', 'opened')
            ], limit=1)
            
            if not session:
                 return {'status': 'error', 'message': 'Cannot update stock if no session is open.'}

            product = request.env['product.template'].sudo().browse(int(product_id))
            if not product.exists():
                return {'status': 'error', 'message': 'Product not found.'}

            existing_log = request.env['purecf.audit.log'].sudo().search([
                ('res_model', '=', 'product.template'),
                ('res_id', '=', product.id),
                ('change_type', '=', 'stock_adj'),
                ('create_date', '>=', session.start_at)
            ], limit=1)
            
            admin_id = request.env.uid
            if existing_log:
                admin, msg = self._check_admin_pin(admin_pin)
                if not admin:
                    return {'status': 'error', 'message': 'Sudah di-opname. Perlu PIN Admin untuk mengubah data: %s' % msg}
                admin_id = admin.id

            res = product.action_update_stock_manual(new_quantity, admin_id, location_id)
            
            if res:
                return {
                    'status': 'success',
                    'message': 'Stock updated to %s' % new_quantity,
                    'new_qty': product.qty_available
                }
            return {'status': 'error', 'message': 'Failed to update stock.'}
        except Exception as e:
            _logger.error("Stock Update Failure: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/report/financial', type='json', auth='user', methods=['POST'], csrf=False)
    def get_financial_report(self, date_from=None, date_to=None, config_id=None, **kwargs):
        """Fetch Sales, Cost, and Profit data with charts (Session-based)."""
        try:
            date_from = date_from or fields.Date.today()
            date_to = date_to or fields.Date.today()
            
            # Fetch all available branches for the dropdown
            available_configs = request.env['pos.config'].sudo().search_read([], ['id', 'name'])
            
            user_tz_name = request.env.user.tz or 'Asia/Jakarta'
            user_tz = pytz.timezone(user_tz_name)
            
            _logger.info("Generating Financial Report from %s to %s for config %s", date_from, date_to, config_id)

            # 1. Determine Order Domain (Prioritize Active Session if viewing today)
            today = fields.Date.today()
            active_session = False
            
            # If viewing today and no specific multi-branch filter is applied, look for active session
            if fields.Date.from_string(date_from) == today and fields.Date.from_string(date_to) == today and (not config_id or config_id == 'all'):
                active_session = request.env['pos.session'].sudo().search([
                    ('user_id', '=', request.env.uid),
                    ('state', '=', 'opened')
                ], limit=1)

            if active_session:
                _logger.info("DASHBOARD: Using Active Session %s", active_session.name)
                order_domain = [
                    ('session_id', '=', active_session.id),
                    ('state', 'in', ['paid', 'done', 'invoiced'])
                ]
                # Define boundaries for charts and expenses based on session
                start_dt = active_session.start_at
                end_dt = fields.Datetime.now()
            else:
                # Fallback to date range logic
                start_dt = user_tz.localize(datetime.combine(fields.Date.from_string(date_from), datetime.min.time())).astimezone(pytz.UTC)
                end_dt = user_tz.localize(datetime.combine(fields.Date.from_string(date_to), datetime.max.time())).astimezone(pytz.UTC)
                
                order_domain = [
                    ('date_order', '>=', fields.Datetime.to_string(start_dt)),
                    ('date_order', '<=', fields.Datetime.to_string(end_dt)),
                    ('state', 'in', ['paid', 'done', 'invoiced'])
                ]
                if config_id and config_id != 'all':
                    order_domain.append(('session_id.config_id', '=', int(config_id)))
            
            if config_id and config_id != 'all':
                order_domain.append(('session_id.config_id', '=', int(config_id)))
            
            _logger.info("DASHBOARD DEBUG - Order Domain: %s", order_domain)
            orders = request.env['pos.order'].sudo().search(order_domain)
            _logger.info("DASHBOARD DEBUG - Found Orders Count: %s", len(orders))

            # Fetch Cash Balance robustly
            cash_journal = request.env['account.journal'].sudo().search([('type', '=', 'cash')], limit=1)
            cash_balance = cash_journal.default_account_id.current_balance if cash_journal and cash_journal.default_account_id else 0.0

            total_sales = sum(orders.mapped('amount_total'))
            total_untaxed_sales = total_sales - sum(orders.mapped('amount_tax'))
            total_cost = 0.0
            
            # 1.5 Calculate Cash Variance and Opening Cash from Sessions
            if active_session:
                sessions_in_period = active_session
            else:
                session_domain = [
                    ('start_at', '>=', fields.Datetime.to_string(start_dt)),
                    ('start_at', '<=', fields.Datetime.to_string(end_dt)),
                ]
                if config_id and config_id != 'all':
                    session_domain.append(('config_id', '=', int(config_id)))
                sessions_in_period = request.env['pos.session'].sudo().search(session_domain)
                
            total_cash_variance = sum(sessions_in_period.filtered(lambda s: s.state == 'closed').mapped('cash_register_difference'))
            total_opening_cash = sum(sessions_in_period.mapped('cash_register_balance_start'))

            # 2. Hourly Chart Data (Adjusted for Local Time WIB - UTC+7)

            hourly_map = {h: 0.0 for h in range(24)}
            for order in orders:
                # Odoo stores in UTC, we convert to local for the chart
                order_date_utc = order.date_order.replace(tzinfo=pytz.UTC)
                order_date_local = order_date_utc.astimezone(user_tz)
                hour = order_date_local.hour
                hourly_map[hour] += order.amount_total
                
                for line in order.lines:
                    # Correct COGS: Convert POS quantity to Product Base UoM for accurate costing
                    # This prevents high HPP when selling in Cups/Servings but costing in Kg/Grams
                    qty_in_base_uom = line.product_uom_id._compute_quantity(line.qty, line.product_id.uom_id)
                    total_cost += (line.product_id.standard_price or 0.0) * qty_in_base_uom
            
            chart_data = [{"label": f"{h:02}:00", "value": hourly_map[h]} for h in range(24)]
            
            # 2. Payment Methods - Hardcoded to only 3 categories as requested
            payment_map = {
                'Cash': 0.0,
                'QRIS': 0.0,
                'Transfer': 0.0
            }

            # Fetch all payments for the orders found to get accurate methods
            order_ids = orders.ids
            if order_ids:
                payments = request.env['pos.payment'].sudo().search([('pos_order_id', 'in', order_ids)])
                for payment in payments:
                    orig_name = payment.payment_method_id.name.lower()
                    if 'cash' in orig_name or 'tunai' in orig_name: pm_name = 'Cash'
                    elif 'qris' in orig_name: pm_name = 'QRIS'
                    elif 'transfer' in orig_name or 'bank' in orig_name: pm_name = 'Transfer'
                    else: pm_name = payment.payment_method_id.name
                    payment_map[pm_name] = payment_map.get(pm_name, 0.0) + payment.amount
            
            # If no payments found (e.g. historical data or sync issues), fallback to x_payment_method
            elif orders:
                for order in orders:
                    orig_name = (order.x_payment_method or 'Cash').lower()
                    if 'cash' in orig_name or 'tunai' in orig_name: pm_name = 'Cash'
                    elif 'qris' in orig_name: pm_name = 'QRIS'
                    elif 'transfer' in orig_name or 'bank' in orig_name: pm_name = 'Transfer'
                    else: pm_name = order.x_payment_method or 'Cash'
                    payment_map[pm_name] = payment_map.get(pm_name, 0.0) + order.amount_total

            
            # Search expenses directly by session if active, else by date
            if active_session:
                expense_domain = [('session_id', '=', active_session.id)]
            else:
                expense_domain = [
                    ('date', '>=', fields.Datetime.to_string(start_dt)),
                    ('date', '<=', fields.Datetime.to_string(end_dt))
                ]
                if config_id and config_id != 'all':
                    expense_domain.append(('config_id', '=', int(config_id)))
            
            total_expenses = sum(request.env['purecf.expense'].sudo().search(expense_domain).mapped('amount'))

            payment_methods = []
            colors = ["0xFFD4A373", "0xFF1D976C", "0xFF1B1B2F", "0xFFE76F51", "0xFF264653"]
            idx = 0
            for pm, val in payment_map.items():
                percent = round((val / total_sales * 100), 1) if total_sales > 0 else 0
                payment_methods.append({
                    "name": pm,
                    "value": val,
                    "percentage": percent,
                    "color": colors[idx % len(colors)]
                })
                idx += 1
                
            # 3. Top Products per Category
            cat_map = {}
            for order in orders:
                for line in order.lines:
                    # Get POS Category name
                    cat_rec = line.product_id.pos_categ_ids
                    cat_name = cat_rec[0].name if cat_rec else "Lainnya"
                    
                    if cat_name not in cat_map: cat_map[cat_name] = {}
                    p_id = line.product_id.id
                    if p_id not in cat_map[cat_name]:
                        cat_map[cat_name][p_id] = {"name": line.product_id.name, "qty": 0, "total": 0.0}
                    
                    cat_map[cat_name][p_id]["qty"] += line.qty
                    cat_map[cat_name][p_id]["total"] += line.price_subtotal_incl

            top_products_categorized = []
            for cat, prods in cat_map.items():
                # Sort by quantity sold
                sorted_prods = sorted(prods.values(), key=lambda x: x['qty'], reverse=True)[:3]
                top_products_categorized.append({
                    "category": cat,
                    "products": sorted_prods
                })

            profit = total_untaxed_sales - total_cost
            hpp_percent = (total_cost / total_untaxed_sales * 100) if total_untaxed_sales > 0 else 0.0
            avg_order = (total_sales / len(orders)) if len(orders) > 0 else 0.0

            # 3.5 Calculate Waste Cost for the period
            waste_domain = [
                ('change_type', '=', 'stock_adj'),
                ('create_date', '>=', fields.Datetime.to_string(start_dt)),
                ('create_date', '<=', fields.Datetime.to_string(end_dt))
            ]
            waste_logs = request.env['purecf.audit.log'].sudo().search(waste_domain)
            total_waste_cost = 0.0
            waste_map = {}
            for log in waste_logs:
                product = request.env['product.template'].sudo().browse(log.res_id)
                if product.exists():
                    try:
                        old_qty = json.loads(log.old_state or '{}').get('qty_available', 0)
                        new_qty = json.loads(log.new_state or '{}').get('qty_available', 0)
                        diff = old_qty - new_qty
                        if diff > 0:
                            cost = diff * product.standard_price
                            total_waste_cost += cost
                            p_id = product.id
                            if p_id not in waste_map:
                                waste_map[p_id] = {'name': product.name, 'qty': 0, 'total': 0.0, 'uom': product.uom_id.name}
                            waste_map[p_id]['qty'] += diff
                            waste_map[p_id]['total'] += cost
                    except:
                        pass
            
            top_waste = sorted(waste_map.values(), key=lambda x: x['total'], reverse=True)[:5]
            
            # 4. Top Branches (Point of Sales)
            top_branches = []
            if not config_id:
                branch_map = {}
                for order in orders:
                    cfg = order.session_id.config_id
                    cfg_id = cfg.id
                    if cfg_id not in branch_map:
                        branch_map[cfg_id] = {"name": cfg.name, "sales": 0.0, "orders": 0}
                    branch_map[cfg_id]["sales"] += order.amount_total
                    branch_map[cfg_id]["orders"] += 1
                
                # Sort by sales descending
                top_branches = sorted(branch_map.values(), key=lambda x: x['sales'], reverse=True)

            # 5. Previous Period Comparison
            date_from_dt = fields.Date.from_string(date_from)
            date_to_dt = fields.Date.from_string(date_to)
            delta = (date_to_dt - date_from_dt).days + 1
            
            prev_date_to = date_from_dt - timedelta(days=1)
            prev_date_from = prev_date_to - timedelta(days=delta-1)

            prev_start_dt = user_tz.localize(datetime.combine(prev_date_from, datetime.min.time())).astimezone(pytz.UTC)
            prev_end_dt = user_tz.localize(datetime.combine(prev_date_to, datetime.max.time())).astimezone(pytz.UTC)

            prev_order_domain = [
                ('date_order', '>=', fields.Datetime.to_string(prev_start_dt)),
                ('date_order', '<=', fields.Datetime.to_string(prev_end_dt)),
                ('state', 'in', ['paid', 'done', 'invoiced'])
            ]
            if config_id:
                prev_order_domain.append(('session_id.config_id', '=', int(config_id)))
            
            prev_orders = request.env['pos.order'].sudo().search(prev_order_domain)
            prev_sales = sum(prev_orders.mapped('amount_total'))
            prev_total_orders = len(prev_orders)
            
            avg_order = (total_sales / len(orders)) if len(orders) > 0 else 0.0
            prev_avg_order = (prev_sales / prev_total_orders) if prev_total_orders > 0 else 0.0

            def calc_trend(current, previous):
                if previous == 0:
                    return 100.0 if current > 0 else 0.0
                return round(((current - previous) / previous) * 100, 1)

            # Previous Period Variance for trend
            prev_sessions = request.env['pos.session'].sudo().search([
                ('start_at', '>=', fields.Datetime.to_string(prev_start_dt)),
                ('start_at', '<=', fields.Datetime.to_string(prev_end_dt)),
                ('state', '=', 'closed')
            ] + ([('config_id', '=', int(config_id))] if config_id else []))
            prev_cash_variance = sum(prev_sessions.mapped('cash_register_difference'))

            trends = {
                'sales': calc_trend(total_sales, prev_sales),
                'orders': calc_trend(len(orders), prev_total_orders),
                'avg_order': calc_trend(avg_order, prev_avg_order),
                'cash_variance': calc_trend(abs(total_cash_variance), abs(prev_cash_variance))
            }

            # (Already calculated above using direct search)

            return {
                'status': 'success',
                'summary': {
                    'sales': total_sales,
                    'cost': total_cost,
                    'waste_cost': total_waste_cost,
                    'expenses': total_expenses,
                    'cash_variance': total_cash_variance,
                    'profit': profit - total_waste_cost + total_cash_variance - total_expenses,
                    'hpp_percent': round(hpp_percent, 2),
                    'total_orders': len(orders),
                    'avg_order': round(avg_order, 2),
                    'opening_cash': total_opening_cash,
                    'cash_balance': cash_balance,
                    'trends': trends,
                    'comparison_label': "vs Periode Sebelumnya"
                },

                'chart_data': chart_data,
                'payment_methods': payment_methods,
                'top_products_categorized': top_products_categorized,
                'top_waste': top_waste,
                'top_branches': top_branches,
                'usage_analysis': request.env['purecf.stock.usage.analysis'].sudo().get_usage_data(date_from, date_to),
                'branches': available_configs
            }
        except Exception as e:
            _logger.error("Financial Report Generation Failed: %s", str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/report/session_dates', type='json', auth='user', methods=['POST'], csrf=False)
    def get_session_dates(self, **kwargs):
        """Fetch all unique dates that have sessions."""
        try:
            sessions = request.env['pos.session'].sudo().search([])
            dates = sorted(list(set([self._utc_to_wib_str(s.start_at)[:10] for s in sessions if s.start_at])), reverse=True)
            return {'status': 'success', 'dates': dates}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/admin_validate', type='json', auth='user', methods=['POST'], csrf=False)
    def admin_validate(self, pin, **kwargs):
        """Validate Admin PIN for generic Flutter use."""
        admin, msg = self._check_admin_pin(pin)
        if admin:
            return {'status': 'success', 'admin_name': admin.name}
        return {'status': 'error', 'message': msg}

    @http.route('/api/purecf/history/audit_logs', type='json', auth='user', methods=['POST'], csrf=False)
    def get_audit_logs(self, model=None, res_id=None, **kwargs):
        """Fetch audit trail/history logs."""
        try:
            domain = []
            if model: domain.append(('res_model', '=', model))
            if res_id: domain.append(('res_id', '=', int(res_id)))
            
            logs = request.env['purecf.audit.log'].sudo().search_read(domain, [
                'id', 'res_model', 'res_id', 'admin_id', 'change_type', 
                'old_state', 'new_state', 'note', 'reverted', 'create_date'
            ])
            for l in logs:
                l['create_date'] = self._utc_to_wib_str(l['create_date'])
            return {'status': 'success', 'logs': logs}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/finance/closings', type='json', auth='user', methods=['POST'], csrf=False)
    def get_monthly_closings(self, **kwargs):
        """Fetch list of historical monthly closings."""
        try:
            closings = request.env['purecf.monthly.close'].sudo().search_read([], [
                'id', 'year', 'month', 'date_from', 'date_to', 
                'total_sales', 'total_cost', 'total_profit', 'admin_id'
            ])
            return {'status': 'success', 'closings': closings}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/report/export_monthly', type='http', auth='user', methods=['GET'], csrf=False)
    def export_monthly_report(self, month, year, **kwargs):
        """
        Export a structured monthly report in Excel format.
        """
        try:
            month = int(month)
            year = int(year)
            
            # 1. Define Periods
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
            
            # Previous Period for trends
            prev_start = (start_date - timedelta(days=1)).replace(day=1)
            prev_end = start_date - timedelta(seconds=1)

            # 2. Category IDs for Food vs Drink
            # In a real system we'd use external IDs or a config, here we use names from master_data
            food_cats = request.env['pos.category'].sudo().search([
                ('name', 'in', ['BUBUR KETAN HITAM', 'MAIN COURSE', 'SIDE DISH'])
            ]).ids
            drink_cats = request.env['pos.category'].sudo().search([
                ('name', 'in', ['BASIC COFFEE', 'ICED COFFEE', 'SIGNATURE', 'MILK BASE', 'MOCKTAIL', 'TEA BASE'])
            ]).ids

            def get_data_for_period(s_date, e_date):
                domain = [
                    ('date_order', '>=', s_date.strftime('%Y-%m-%d 00:00:00')),
                    ('date_order', '<=', e_date.strftime('%Y-%m-%d 23:59:59')),
                    ('state', 'in', ['paid', 'done', 'invoiced'])
                ]
                orders = request.env['pos.order'].sudo().search(domain)
                
                revenue = sum(orders.mapped('amount_total'))
                untaxed_revenue = revenue - sum(orders.mapped('amount_tax'))
                guest_count = len(orders) # Proxy for guest count
                avg_check = revenue / guest_count if guest_count > 0 else 0
                
                food_sales = 0
                drink_sales = 0
                total_cost = 0
                
                for order in orders:
                    for line in order.lines:
                        # Check Category
                        cat_ids = line.product_id.pos_categ_ids.ids
                        if any(c in food_cats for c in cat_ids):
                            food_sales += line.price_subtotal_incl
                        elif any(c in drink_cats for c in cat_ids):
                            drink_sales += line.price_subtotal_incl
                        
                        # Correct COGS with UoM conversion
                        qty_in_base = line.product_uom_id._compute_quantity(line.qty, line.product_id.uom_id)
                        total_cost += (line.product_id.standard_price or 0) * qty_in_base
                
                return {
                    'revenue': revenue,
                    'untaxed_revenue': untaxed_revenue,
                    'guest_count': guest_count,
                    'avg_check': avg_check,
                    'food_sales': food_sales,
                    'drink_sales': drink_sales,
                    'cost': total_cost,
                    'orders': orders
                }

            curr = get_data_for_period(start_date, end_date)
            prev = get_data_for_period(prev_start, prev_end)

            # Calculate Trends
            revenue_trend = ((curr['revenue'] - prev['revenue']) / prev['revenue'] * 100) if prev['revenue'] > 0 else 0
            
            # Product Analysis
            lines = curr['orders'].mapped('lines')
            prod_stats = {}
            for line in lines:
                p_id = line.product_id.id
                if p_id not in prod_stats:
                    prod_stats[p_id] = {
                        'name': line.product_id.name,
                        'qty': 0,
                        'revenue': 0,
                        'profit': 0
                    }
                prod_stats[p_id]['qty'] += line.qty
                prod_stats[p_id]['revenue'] += line.price_subtotal_incl
                prod_stats[p_id]['profit'] += (line.price_unit - (line.product_id.standard_price or 0)) * line.qty

            best_sellers = sorted(prod_stats.values(), key=lambda x: x['qty'], reverse=True)[:5]
            most_profitable = sorted(prod_stats.values(), key=lambda x: x['profit'], reverse=True)[:5]
            slow_moving = sorted(prod_stats.values(), key=lambda x: x['qty'])[:5]

            # Wastage
            waste_logs = request.env['purecf.audit.log'].sudo().search([
                ('change_type', '=', 'stock_adj'),
                ('create_date', '>=', start_date.strftime('%Y-%m-%d')),
                ('create_date', '<=', end_date.strftime('%Y-%m-%d'))
            ])
            total_waste_val = 0
            for log in waste_logs:
                product = request.env['product.template'].sudo().browse(log.res_id)
                if product.exists():
                    try:
                        old_qty = json.loads(log.old_state or '{}').get('qty_available', 0)
                        new_qty = json.loads(log.new_state or '{}').get('qty_available', 0)
                        diff = old_qty - new_qty
                        if diff > 0:
                            total_waste_val += diff * product.standard_price
                    except: pass

            # Generate Excel
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Laporan Bulanan')

            # --- COLOR PALETTE ---
            PRI_COLOR = '#1B1B2F' # Dark Blue
            SEC_COLOR = '#D4A373' # Tan/Gold
            ACC_COLOR = '#FAEDCD' # Light Cream
            TEXT_WH = '#FFFFFF'
            TEXT_BK = '#333333'
            RED = '#E76F51'
            GREEN = '#2A9D8F'

            # --- FORMATS ---
            # Title & Header
            title_fmt = workbook.add_format({'bold': True, 'font_size': 20, 'align': 'center', 'valign': 'vcenter', 'bg_color': PRI_COLOR, 'font_color': TEXT_WH})
            info_fmt = workbook.add_format({'font_size': 10, 'align': 'center', 'italic': True, 'font_color': TEXT_BK})
            
            # Section Header
            section_fmt = workbook.add_format({'bold': True, 'font_size': 12, 'bg_color': SEC_COLOR, 'font_color': TEXT_WH, 'border': 1, 'align': 'left', 'valign': 'vcenter'})
            
            # Table Headers
            table_head_fmt = workbook.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
            
            # Data Rows
            data_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter'})
            data_zebra_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter', 'bg_color': '#FBFAF5'})
            
            # Currencies
            curr_fmt = workbook.add_format({'border': 1, 'num_format': '"Rp "#,##0', 'valign': 'vcenter'})
            curr_zebra_fmt = workbook.add_format({'border': 1, 'num_format': '"Rp "#,##0', 'valign': 'vcenter', 'bg_color': '#FBFAF5'})
            
            # Percentages
            perc_fmt = workbook.add_format({'border': 1, 'num_format': '0.0%', 'valign': 'vcenter', 'align': 'center'})
            perc_zebra_fmt = workbook.add_format({'border': 1, 'num_format': '0.0%', 'valign': 'vcenter', 'align': 'center', 'bg_color': '#FBFAF5'})
            
            # Conditional (Trends)
            trend_up_fmt = workbook.add_format({'border': 1, 'font_color': GREEN, 'bold': True, 'align': 'center'})
            trend_down_fmt = workbook.add_format({'border': 1, 'font_color': RED, 'bold': True, 'align': 'center'})

            # Set Column Widths
            sheet.set_column('A:A', 35)
            sheet.set_column('B:D', 22)
            sheet.set_row(0, 40) # Title height

            # --- START WRITING ---
            # Title
            sheet.merge_range('A1:D1', "MONTHLY PERFORMANCE REPORT", title_fmt)
            sheet.merge_range('A2:D2', f"Periode: {start_date.strftime('%B %Y')} | Dihasilkan pada: {datetime.now().strftime('%d/%m/%Y %H:%M')}", info_fmt)
            
            row = 3
            
            # 1. RINGKASAN EKSEKUTIF
            sheet.merge_range(row, 0, row, 3, "  1. RINGKASAN EKSEKUTIF", section_fmt)
            row += 1
            summary_items = [
                ('Total Pendapatan', curr['revenue'], f"{'+' if revenue_trend >=0 else ''}{revenue_trend:.1f}% vs Bln Lalu"),
                ('Total Tamu (Guest Count)', curr['guest_count'], "Orang"),
                ('Average Check (Per Orang)', curr['avg_check'], "Rata-rata"),
                ('HPP Riil (COGS)', curr['cost'] / curr['untaxed_revenue'] if curr['untaxed_revenue'] > 0 else 0, "Target: 32%"),
            ]
            
            for i, (label, val, note) in enumerate(summary_items):
                fmt = data_zebra_fmt if i % 2 == 0 else data_fmt
                val_fmt = curr_zebra_fmt if (i % 2 == 0 and 'Total' in label) or 'Check' in label else (perc_zebra_fmt if 'HPP' in label else (data_zebra_fmt if i % 2 == 0 else data_fmt))
                
                sheet.write(row, 0, label, fmt)
                sheet.write(row, 1, val, val_fmt)
                
                if 'Pendapatan' in label:
                    t_fmt = trend_up_fmt if revenue_trend >= 0 else trend_down_fmt
                    sheet.merge_range(row, 2, row, 3, note, t_fmt)
                else:
                    sheet.merge_range(row, 2, row, 3, note, fmt)
                row += 1

            # 2. PERFORMA FINANSIAL
            row += 1
            sheet.merge_range(row, 0, row, 3, "  2. PERFORMA FINANSIAL (P&L SUMMARY)", section_fmt)
            row += 1
            headers = ['Kategori Akuntansi', 'Aktual (IDR)', 'Target (IDR)', 'Varians (%)']
            for col, h in enumerate(headers):
                sheet.write(row, col, h, table_head_fmt)
            
            perf_data = [
                ('Penjualan Makanan', curr['food_sales'], curr['revenue'] * 0.45),
                ('Penjualan Minuman', curr['drink_sales'], curr['revenue'] * 0.55),
                ('Total Gross Sales', curr['revenue'], curr['revenue']),
                ('Harga Pokok Penjualan (HPP)', curr['cost'], curr['revenue'] * 0.32),
                ('Biaya Tenaga Kerja (Placeholder)', curr['revenue'] * 0.15, curr['revenue'] * 0.15)
            ]

            for i, (label, val, target) in enumerate(perf_data):
                row += 1
                fmt = data_zebra_fmt if i % 2 == 1 else data_fmt
                v_fmt = curr_zebra_fmt if i % 2 == 1 else curr_fmt
                p_fmt = perc_zebra_fmt if i % 2 == 1 else perc_fmt
                
                sheet.write(row, 0, label, fmt)
                sheet.write(row, 1, val, v_fmt)
                sheet.write(row, 2, target, v_fmt)
                
                var = (val - target) / target if target > 0 else 0
                sheet.write(row, 3, var, p_fmt)

            # 3. ANALISIS PRODUK
            row += 2
            sheet.merge_range(row, 0, row, 1, "  3. TOP 5 BEST SELLER", section_fmt)
            sheet.merge_range(row, 2, row, 3, "  MOST PROFITABLE", section_fmt)
            row += 1
            sheet.write(row, 0, "Nama Produk", table_head_fmt)
            sheet.write(row, 1, "Qty Terjual", table_head_fmt)
            sheet.write(row, 2, "Nama Produk", table_head_fmt)
            sheet.write(row, 3, "Gross Profit", table_head_fmt)
            
            for i in range(5):
                row += 1
                fmt = data_zebra_fmt if i % 2 == 1 else data_fmt
                v_fmt = curr_zebra_fmt if i % 2 == 1 else curr_fmt
                
                # Best Sellers
                if i < len(best_sellers):
                    sheet.write(row, 0, best_sellers[i]['name'], fmt)
                    sheet.write(row, 1, best_sellers[i]['qty'], fmt)
                else:
                    sheet.write(row, 0, "-", fmt); sheet.write(row, 1, "-", fmt)
                
                # Most Profitable
                if i < len(most_profitable):
                    sheet.write(row, 2, most_profitable[i]['name'], fmt)
                    sheet.write(row, 3, most_profitable[i]['profit'], v_fmt)
                else:
                    sheet.write(row, 2, "- ", fmt); sheet.write(row, 3, "-", fmt)

            # 4. WASTAGE & INVENTORY
            row += 2
            sheet.merge_range(row, 0, row, 3, "  4. MANAJEMEN INVENTARIS & WASTAGE", section_fmt)
            row += 1
            sheet.write(row, 0, "Total Wastage Value", data_fmt)
            sheet.write(row, 1, total_waste_val, curr_fmt)
            sheet.merge_range(row, 2, row, 3, "Penyebab: Kesalahan takaran & expired.", data_fmt)
            row += 1
            sheet.write(row, 0, "Tindakan Perbaikan", data_fmt)
            sheet.merge_range(row, 1, row, 3, "Memperketat FIFO dan pelatihan ulang staff kitchen.", data_fmt)


            # Finalize
            workbook.close()
            output.seek(0)
            
            file_name = f"Laporan_Bulanan_{start_date.strftime('%m_%Y')}.xlsx"
            return request.make_response(
                output.getvalue(),
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', content_disposition(file_name))
                ]
            )

        except Exception as e:
            _logger.error("Export Failed: %s", str(e), exc_info=True)
            return request.make_response(str(e), status=500)

            workbook.close()
            output.seek(0)
            
            file_name = f"Laporan_Bulanan_{start_date.strftime('%m_%Y')}.xlsx"
            return request.make_response(
                output.getvalue(),
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', content_disposition(file_name))
                ]
            )

        except Exception as e:
            _logger.error("Export Failed: %s", str(e), exc_info=True)
            return request.make_response(str(e), status=500)
            total_sales = sum(orders.mapped('amount_total'))
            total_cost = 0.0
            for order in orders:
                for line in order.lines:
                    total_cost += (line.product_id.standard_price or 0.0) * line.qty
            
            vals = {
                'year': int(year),
                'month': int(month),
                'date_from': date_from,
                'date_to': date_to,
                'total_sales': total_sales,
                'total_cost': total_cost,
                'total_profit': total_sales - total_cost,
                'admin_id': admin.id
            }
            
            closing = request.env['purecf.monthly.close'].sudo().create(vals)
            return {
                'status': 'success', 
                'id': closing.id,
                'summary': {
                    'sales': total_sales,
                    'cost': total_cost,
                    'profit': total_sales - total_cost
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/finance/config', type='json', auth='user', methods=['POST'], csrf=False)
    def get_finance_config(self, **kwargs):
        """Get financial configuration."""
        try:
            config = request.env['purecf.config'].sudo().get_config()
            return {
                'status': 'success',
                'closing_day': config.closing_day
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/finance/config/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_finance_config(self, closing_day, **kwargs):
        """Update financial configuration."""
        try:
            config = request.env['purecf.config'].sudo().get_config()
            config.write({'closing_day': int(closing_day)})
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/history/revert', type='json', auth='user', methods=['POST'], csrf=False)
    def revert_data(self, log_id, admin_pin):
        """Revert a record to a previous state using a log entry."""
        try:
            admin, msg = self._check_admin_pin(admin_pin)
            if not admin:
                return {'status': 'error', 'message': msg}
            
            log = request.env['purecf.audit.log'].sudo().browse(int(log_id))
            if not log.exists():
                return {'status': 'error', 'message': 'Log entry not found.'}
            
            res = log.action_revert()
            if res:
                return {'status': 'success', 'message': 'Data successfully reverted.'}
            return {'status': 'error', 'message': 'Reversion failed.'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/update_record', type='json', auth='user', methods=['POST'], csrf=False)
    def update_record(self, model, res_id, vals, pin=None, **kwargs):
        """Generic endpoint to update a record with optional PIN validation."""
        try:
            if pin:
                admin, msg = self._check_admin_pin(pin)
                if not admin:
                    return {'status': 'error', 'message': msg}
            
            record = request.env[model].sudo().browse(int(res_id))
            if not record.exists():
                return {'status': 'error', 'message': 'Record not found.'}
            
            record.write(vals)
            return {'status': 'success'}
        except Exception as e:
            _logger.error("Update Record Failure: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/purecf/stock/incoming', type='json', auth='user', methods=['POST'], csrf=False)
    def stock_incoming(self, items, **kwargs):
        """Receive new stock (Belanja) for multiple items."""
        try:
            for item in items:
                product_id = item.get('product_id')
                quantity = item.get('quantity', 0)
                price = item.get('price', 0.0)
                note = item.get('note')

                product = request.env['product.template'].sudo().browse(int(product_id))
                if product.exists():
                    product.action_add_stock_incoming(quantity, request.env.uid, price, note)
            
            return {'status': 'success'}
        except Exception as e:
            _logger.error("Stock Incoming Failure: %s", str(e))
            return {'status': 'error', 'message': str(e)}
