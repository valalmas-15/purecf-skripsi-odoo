import xmlrpc.client
import os

url = 'http://localhost:8080'
db = 'odoo' # Assuming 'odoo' based on common defaults, but I should check
username = 'admin'
password = 'admin' # Assuming default

try:
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    uid = common.authenticate(db, username, password, {})
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
    
    # Check if product.list0 exists in ir.model.data
    data = models.execute_kw(db, uid, password, 'ir.model.data', 'search_read',
        [[('module', '=', 'product'), ('name', '=', 'list0')]],
        {'fields': ['res_id', 'model']}
    )
    print(f"ir.model.data for product.list0: {data}")

    # Check for any pricelists
    pricelists = models.execute_kw(db, uid, password, 'product.pricelist', 'search_read',
        [[]],
        {'fields': ['name', 'id']}
    )
    print(f"Available pricelists: {pricelists}")

except Exception as e:
    print(f"Error: {e}")
