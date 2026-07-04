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

    # Page 2: Terms and Conditions - General & Interest Rates
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Allgemeine Geschaeftsbedingungen (AGB) - Teil 1', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 6, "1. Geltungsbereich\nDiese Allgemeinen Geschäftsbedingungen gelten für alle Kreditverträge, die zwischen der "
                         f"{issuer} (nachfolgend 'Kreditgeber' genannt) und dem Kreditnehmer abgeschlossen werden. "
                         "Abweichende Vereinbarungen bedürfen der Schriftform.\n\n"
                         "2. Zustandekommen des Vertrages\nDer Kreditvertrag kommt durch die beiderseitige Unterzeichnung "
                         "oder durch die rechtsverbindliche elektronische Signatur beider Vertragsparteien zustande.\n\n"
                         "3. Auszahlung des Darlehens\nDie Auszahlung des Darlehens erfolgt auf das vom Kreditnehmer "
                         "angegebene Referenzkonto innerhalb von 3 Werktagen nach Vertragsabschluss und nach erfolgreicher "
                         "Identifikationsprüfung (z.B. PostIdent oder VideoIdent).\n\n"
                         "4. Verzinsung\nDer gebundene Sollzinssatz und der effektive Jahreszins ergeben sich aus dem "
                         "Europäischen Standardinformationen für Verbraucherkredite (ESIS) Dokument. Der Zinssatz ist über "
                         "die gesamte Laufzeit gebunden. Die Berechnung der Zinsen erfolgt nach der kaufmännischen Zinsmethode (30/360).\n\n"
                         "5. Rückzahlung\nDas Darlehen ist in monatlichen Raten gemäß dem beigefügten Tilgungsplan zurückzuzahlen. "
                         "Die Raten sind jeweils am 1. oder 15. eines jeden Monats fällig. Der Kreditnehmer ermächtigt den Kreditgeber, "
                         "die Raten im SEPA-Basislastschriftverfahren vom angegebenen Referenzkonto einzuziehen.")

    # Page 3: Terms and Conditions - Default & Termination
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Allgemeine Geschaeftsbedingungen (AGB) - Teil 2', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 6, "6. Sondertilgungen\nDer Kreditnehmer ist berechtigt, jederzeit Sondertilgungen auf das Darlehen zu leisten "
                         "oder das Darlehen vorzeitig vollständig zurückzuzahlen. In diesem Fall kann der Kreditgeber eine "
                         "Vorfälligkeitsentschädigung gemäß § 502 BGB verlangen, die jedoch auf maximal 1,0 % des vorzeitig "
                         "zurückgezahlten Betrags begrenzt ist.\n\n"
                         "7. Zahlungsverzug\nGerät der Kreditnehmer mit einer Rate ganz oder teilweise in Verzug, "
                         "werden Verzugszinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz berechnet. "
                         "Zudem können Mahngebühren in Höhe von 2,50 EUR pro Mahnschreiben anfallen.\n\n"
                         "8. Kündigung durch den Kreditgeber\nDer Kreditgeber kann den Vertrag außerordentlich kündigen, "
                         "wenn der Kreditnehmer mit mindestens zwei aufeinanderfolgenden Teilzahlungen ganz oder teilweise "
                         "in Verzug ist und der Verzugsbetrag mindestens 10 % des Nennbetrags ausmacht (bzw. 5 % bei einer Laufzeit über 3 Jahren). "
                         "Der Kreditgeber wird dem Kreditnehmer zuvor erfolglos eine zweiwöchige Frist zur Zahlung des rückständigen Betrags setzen.\n\n"
                         "9. Sicherheiten\nZur Absicherung der Ansprüche aus diesem Kreditvertrag tritt der Kreditnehmer "
                         "den pfändbaren Teil seiner gegenwärtigen und zukünftigen Lohn- und Gehaltsansprüche an den Kreditgeber ab (Lohnabtretung).")

    # Page 4: Privacy Policy (Schufa & Data Handling)
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Datenschutzbestimmungen & SCHUFA-Hinweis', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 6, "1. Datenverarbeitung\nWir verarbeiten Ihre personenbezogenen Daten (z.B. Name, Adresse, Geburtsdatum, "
                         "Einkommensverhältnisse, Kontodaten) zum Zwecke der Antragsprüfung, Vertragsabwicklung und Risikobewertung "
                         "gemäß Art. 6 Abs. 1 lit. b DSGVO.\n\n"
                         "2. SCHUFA-Klausel\nIch willige ein, dass der Kreditgeber vor Vertragsabschluss und während der Laufzeit "
                         "Auskünfte über mich bei der SCHUFA Holding AG, Kormoranweg 5, 65201 Wiesbaden, einholt. Ferner willige ich ein, "
                         "dass Daten über nicht vertragsgemäßes Verhalten (z.B. gekündigte Kredite, Zwangsvollstreckungsmaßnahmen) "
                         "an die SCHUFA übermittelt werden. Die SCHUFA berechnet Wahrscheinlichkeitswerte (Scoring) unter "
                         "Einbeziehung von Anschriftendaten.\n\n"
                         "3. Weitergabe von Daten an Dritte\nEine Weitergabe Ihrer Daten an Dritte erfolgt nur, soweit dies "
                         "zur Vertragsabwicklung erforderlich ist (z.B. an Druckdienstleister, Refinanzierungspartner oder "
                         "Inkassounternehmen im Falle des Verzugs). Wir haben mit allen Dienstleistern Auftragsverarbeitungsverträge "
                         "gemäß Art. 28 DSGVO geschlossen.\n\n"
                         "4. Speicherdauer\nWir speichern Ihre Daten für die Dauer der Vertragslaufzeit. Nach Beendigung des "
                         "Vertrages werden die Daten zur Erfüllung gesetzlicher Aufbewahrungsfristen (z.B. nach HGB und AO) "
                         "für in der Regel 10 Jahre aufbewahrt.")


    
    pdf.output(filename, 'F')
    print(f"Created {filename}")

if __name__ == '__main__':
    create_kreditantrag_pdf('INV-1001.pdf', 'INV-1001', 1500, 300.0, 'S-Kreditpartner GmbH')
    create_kreditantrag_pdf('INV-1002.pdf', 'INV-1002', 3000, 570.0, 'Sparkasse Berlin')
    create_kreditantrag_pdf('INV-1003.pdf', 'INV-1003', 450, 85.5, 'S-Kreditpartner GmbH')
