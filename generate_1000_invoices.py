import os
import random
from generate_pdf import create_kreditantrag_pdf

os.makedirs('invoices', exist_ok=True)

issuers = ['S-Kreditpartner GmbH', 'Sparkasse Berlin', 'Sparkasse München', 'Sparkasse Hamburg', 'Berliner Bank', 'Deutsche Bank', 'Commerzbank']

for i in range(1004, 2004):
    invoice_id = f'INV-{i}'
    total = random.randint(100, 10000)
    tax = round(total * 0.19, 2)
    issuer = random.choice(issuers)
    filename = f'invoices/{invoice_id}.pdf'
    
    create_kreditantrag_pdf(filename, invoice_id, total, tax, issuer)
    
print("Successfully generated 1000 invoices in the 'invoices' directory.")
