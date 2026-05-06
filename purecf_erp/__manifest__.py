# -*- coding: utf-8 -*-
{
    'name': 'Purecf - Cafe ERP',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'summary': 'ERP System for Cafe with Flutter POS Integration (Thesis Project)',
    'description': """
        Features:
        - Real-time POS Sync via JSON-RPC
        - Bill of Materials (BoM) stock deduction
        - Automatic Accounting Journals
        - Automated HPP (COGS) Reporting
        - Flutter Authentication Integration
    """,
    'author': 'Alie',
    'depends': [
        'base',
        'product',
        'stock',
        'account',
        'mrp',
        'uom',
        'point_of_sale',
        'pos_mrp',
        'hr',
        'mail',
        'board',
    ],
    'data': [
        'data/user_data.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/master_data.xml',
        'data/product_cost_data.xml',
        'data/initial_stock_data.xml',
        'data/plastic_data.xml',
        'views/monthly_close_views.xml',
        'views/res_config_settings_views.xml',
        'views/pos_config_views.xml',
        'views/hr_employee_views.xml',
        'views/stock_usage_analysis_views.xml',
        'views/purecf_expense_views.xml',
        'views/purecf_menus.xml',
        'views/product_views.xml',
        'views/pos_session_views.xml',
        'security/purecf_security.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'purecf_erp/static/src/components/stock_management/stock_management.js',
            'purecf_erp/static/src/components/stock_management/stock_management.scss',
            'purecf_erp/static/src/components/stock_management/stock_management.xml',
            'purecf_erp/static/src/components/dashboard/dashboard.js',
            'purecf_erp/static/src/components/dashboard/dashboard.scss',
            'purecf_erp/static/src/components/dashboard/dashboard.xml',
            'purecf_erp/static/src/components/master_data/master_data.js',
            'purecf_erp/static/src/components/master_data/master_data.scss',
            'purecf_erp/static/src/components/master_data/master_data.xml',
            'purecf_erp/static/src/components/finance_management/finance_management.js',
            'purecf_erp/static/src/components/finance_management/finance_management.scss',
            'purecf_erp/static/src/components/finance_management/finance_management.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
