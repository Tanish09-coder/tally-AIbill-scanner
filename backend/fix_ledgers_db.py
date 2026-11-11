import sqlite3

conn = sqlite3.connect('backend/app.db')
c = conn.cursor()
c.execute("UPDATE voucher_previews SET sales_purchase_ledger = 'SALES A/C' WHERE voucher_type = 'Sales' AND sales_purchase_ledger LIKE '%PURCHASE%'")
c.execute("UPDATE voucher_previews SET sales_purchase_ledger = 'PURCHASE A/C' WHERE voucher_type = 'Purchase' AND (sales_purchase_ledger LIKE '%SALES%' OR sales_purchase_ledger = 'Purchase Accounts')")
conn.commit()
print("Updated existing voucher previews in DB successfully!")

