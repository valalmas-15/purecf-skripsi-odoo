# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class ReportHpp(models.TransientModel):
    _name = 'purecf.report.hpp'
    _description = 'Generate HPP Report for Cafe'

    date_from = fields.Date(string='Date From', default=fields.Date.today)
    date_to = fields.Date(string='Date To', default=fields.Date.today)
    summary_data = fields.Text(string='Summary Content')

    def action_generate_report(self):
        """Method to calculate gross profit and HPP based on BoM costs and Sale Prices."""
        domain = [
            ('date_order', '>=', self.date_from),
            ('date_order', '<=', self.date_to),
            ('state', 'in', ['paid', 'done', 'invoiced'])
        ]
        orders = self.env['pos.order'].search(domain)
        
        total_sales = sum(orders.mapped('amount_total'))
        total_cost = 0.0
        
        for order in orders:
            for line in order.lines:
                # Find the cost of the product. 
                # If it's a Kit, the standard_price of the product_template should reflect its roll-up.
                # However, for real-time HPP, we can fetch the 'standard_price'.
                total_cost += line.product_id.standard_price * line.qty
        
        hpp = (total_cost / total_sales * 100) if total_sales > 0 else 0.0
        
        def format_idr(amount):
            return "Rp {:,.0f}".format(amount).replace(",", ".")

        self.summary_data = f"Sales: {format_idr(total_sales)}\nCost: {format_idr(total_cost)}\nHPP: {round(hpp, 2)}%"
        
        # In a real scenario, this could send an email via IR Cron.
        return True

    @api.model
    def action_generate_annual_report(self, year):
        """Generates a summary for a specific calendar year."""
        date_from = fields.Date.to_date(f"{year}-01-01")
        date_to = fields.Date.to_date(f"{year}-12-31")
        
        report = self.create({
            'date_from': date_from,
            'date_to': date_to
        })
        report.action_generate_report()
        return report.summary_data

    @api.model
    def cron_send_daily_report(self):
        """Scheduled action for Admin to receive reports."""
        report = self.create({
            'date_from': fields.Date.today(),
            'date_to': fields.Date.today()
        })
        report.action_generate_report()
        
        admin = self.env['res.users'].search([('x_role_type', '=', 'admin')], limit=1)
        if admin and admin.email:
             _logger.info("Emailing HPP Report to %s: %s", admin.email, report.summary_data)
        return True

    @api.model
    def cron_send_monthly_report(self):
        """Scheduled action using dynamic closing day configuration."""
        admin = self.env['res.users'].search([('x_role_type', '=', 'admin')], limit=1)
        closing_day = admin.x_closing_day if admin else 1
        
        today = fields.Date.today()
        # Logic for custom closing day period
        if today.day == closing_day:
             date_to = today
             # date_from is 1 month ago + 1 day
             # Simplified for skripsi logic:
             date_from = today - timedelta(days=30) 
             
             report = self.create({
                 'date_from': date_from,
                 'date_to': date_to
             })
             report.action_generate_report()
             if admin and admin.email:
                 _logger.info("Emailing Monthly (Day %s) HPP Report to %s: %s", closing_day, admin.email, report.summary_data)
        return True
