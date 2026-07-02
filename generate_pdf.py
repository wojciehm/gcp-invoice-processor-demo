from fpdf import FPDF
import random

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(80)
        self.cell(30, 10, 'S-Kreditpartner Kreditantrag & Rechnung', 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}/{{nb}}', 0, 0, 'C')

def create_kreditantrag_pdf(filename, invoice_id, total, tax, issuer):
    pdf = PDF()
    pdf.alias_nb_pages()
    
    # Page 1: Main Invoice Details
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    
    pdf.cell(0, 10, 'KREDITANTRAG (Credit Application)', 0, 1, 'C')
    pdf.ln(10)
    
    pdf.cell(0, 10, f'Aussteller (Issuer): {issuer}', 0, 1)
    pdf.cell(0, 10, f'Rechnungsnummer (Invoice ID): {invoice_id}', 0, 1)
    pdf.cell(0, 10, f'Gesamtbetrag (Total): {total} EUR', 0, 1)
    pdf.cell(0, 10, f'Steuer (Tax): {tax} EUR', 0, 1)
    
    pdf.ln(20)
    pdf.multi_cell(0, 10, 'Sehr geehrte Damen und Herren,\n\nhiermit beantrage ich den oben genannten Kredit. '
                          'Die beigefuegten Seiten enthalten die Allgemeinen Geschaeftsbedingungen (AGB), '
                          'die Datenschutzbestimmungen und die detaillierte Kostenaufstellung.')

    # Page 2: Terms and Conditions
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Allgemeine Geschaeftsbedingungen (AGB)', 0, 1)
    pdf.set_font('Arial', '', 12)
    for i in range(1, 15):
        pdf.multi_cell(0, 10, f'§{i} Dies ist ein Standard-Textblock für die Allgemeinen Geschäftsbedingungen des Kreditvertrags. '
                              f'Der Kreditnehmer verpflichtet sich, alle Bedingungen ordnungsgemäß zu erfüllen. '
                              f'Zusätzliche Klausel zur Rückzahlung und Zinsanpassung.')
        
    # Page 3: Privacy Policy
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Datenschutzbestimmungen', 0, 1)
    pdf.set_font('Arial', '', 12)
    for i in range(1, 15):
        pdf.multi_cell(0, 10, f'Absatz {i}: Wir nehmen den Schutz Ihrer persönlichen Daten sehr ernst. '
                              f'Ihre Daten werden gemäß den geltenden DSGVO-Richtlinien verarbeitet und '
                              f'nicht ohne Ihre ausdrückliche Zustimmung an Dritte weitergegeben.')

    # Page 4: Signature Page
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Unterschriften', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.ln(20)
    
    pdf.cell(0, 10, 'Ich bestätige hiermit die Richtigkeit aller Angaben:', 0, 1)
    pdf.ln(30)
    
    pdf.cell(80, 10, '__________________________', 0, 0)
    pdf.cell(80, 10, '__________________________', 0, 1)
    pdf.cell(80, 10, 'Ort, Datum', 0, 0)
    pdf.cell(80, 10, 'Unterschrift Kreditnehmer', 0, 1)
    
    pdf.output(filename, 'F')
    print(f"Created {filename}")

if __name__ == '__main__':
    create_kreditantrag_pdf('INV-1001.pdf', 'INV-1001', 1500, 300.0, 'S-Kreditpartner GmbH')
    create_kreditantrag_pdf('INV-1002.pdf', 'INV-1002', 3000, 570.0, 'Sparkasse Berlin')
    create_kreditantrag_pdf('INV-1003.pdf', 'INV-1003', 450, 85.5, 'S-Kreditpartner GmbH')
