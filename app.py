#!/usr/bin/env python3
"""1031 Exchange Calculator - FastHTML version."""

from fasthtml.common import *
from models import Property, AccessLog, init_db, get_session
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Initialize database
init_db()

# Create FastHTML app
app, rt = fast_app()

# ============================================================================
# MORTGAGE CALCULATION LOGIC
# ============================================================================

def calculate_mortgage_payoff(original_amount, annual_rate, mortgage_date, months=30*12):
    """Calculate remaining mortgage balance."""
    if not original_amount or not annual_rate or not mortgage_date:
        return 0

    today = datetime.now().date()
    months_elapsed = (today.year - mortgage_date.year) * 12 + (today.month - mortgage_date.month)

    if months_elapsed >= months:
        return 0

    monthly_rate = annual_rate / 100 / 12

    if monthly_rate == 0:
        return max(0, original_amount - (original_amount * months_elapsed / months))

    try:
        numerator = ((1 + monthly_rate) ** (months - months_elapsed)) - 1
        denominator = ((1 + monthly_rate) ** months) - 1
        remaining = original_amount * (numerator / denominator)
        return max(0, int(round(remaining)))
    except:
        return 0


# ============================================================================
# ROUTES
# ============================================================================

@rt('/')
def calculator(request):
    """Main calculator page - looks up property by Property ID (?ID=...)."""
    property_id = ''
    if request.query_params:
        property_id = (request.query_params.get('ID') or request.query_params.get('id') or '').strip()
    property_data = None
    # Mortgage Pay Off is a fixed constant of $0 per business requirement
    # (postcard-driven properties have no mortgage data to compute a real payoff).
    calculated_mortgage = 0
    error_message = None

    if property_id:
        session = get_session()
        property_data = session.query(Property).filter_by(property_id=property_id).first()

        if not property_data:
            error_message = f"Property with ID {property_id} not found in database."
        else:
            # Log this access
            log = AccessLog(property_id=property_id)
            session.add(log)
            session.commit()

        session.close()

    purchase_price = property_data.sale_price if property_data and property_data.sale_price else 470000
    current_value = property_data.current_home_value if property_data and property_data.current_home_value else 621000
    current_year = datetime.now().year

    return Html(
        Head(
            Meta(charset="UTF-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Title("1031 Exchange Calculator | Fernwood"),
            Link(href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;800&display=swap", rel="stylesheet"),
            Style("""
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: 'Montserrat', sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #e9ecf1 100%); color: #000; line-height: 1.6; padding: 20px; }
                .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07); overflow: hidden; }
                .header { background: linear-gradient(135deg, #2557FF 0%, #508AFF 100%); color: white; padding: 40px 30px; text-align: center; }
                .header h1 { font-size: 32px; font-weight: 700; margin-bottom: 10px; }
                .header p { font-size: 16px; font-weight: 400; opacity: 0.95; }
                .content { padding: 40px 30px; }
                .error-message { background: #fee2e2; border: 2px solid #fca5a5; border-left: 5px solid #dc2626; color: #991b1b; padding: 15px; border-radius: 6px; margin-bottom: 20px; }
                .property-info { background: #ecf2ff; border: 2px solid #bfdbfe; border-left: 5px solid #2557FF; padding: 15px; border-radius: 6px; margin-bottom: 20px; }
                .property-info p { margin: 5px 0; font-size: 14px; }
                .property-info strong { color: #10295f; }
                .input-section { background: #f9fafb; border: 2px solid #e5e7eb; border-radius: 8px; padding: 30px; margin-bottom: 40px; border-left: 5px solid #2557FF; }
                .input-section h2 { font-size: 20px; font-weight: 600; color: #10295f; margin-bottom: 20px; }
                .input-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
                .input-group { display: flex; flex-direction: column; }
                .input-group label { font-weight: 500; margin-bottom: 8px; color: #10295f; font-size: 14px; text-transform: uppercase; }
                .input-group input { padding: 12px 15px; border: 2px solid #d1d5db; border-radius: 6px; font-size: 16px; transition: all 0.3s ease; }
                .input-group input:focus { outline: none; border-color: #2557FF; box-shadow: 0 0 0 3px rgba(37, 87, 255, 0.1); }
                .input-group .help-text { font-size: 12px; color: #6b7280; margin-top: 4px; }
                .button-group { display: flex; gap: 10px; flex-wrap: wrap; }
                .btn { padding: 12px 24px; font-size: 16px; font-weight: 600; border-radius: 6px; border: none; cursor: pointer; transition: all 0.3s ease; }
                .btn-primary { background: linear-gradient(135deg, #2557FF 0%, #1e44cc 100%); color: white; box-shadow: 0 2px 8px rgba(37, 87, 255, 0.3); }
                .btn-primary:hover { transform: translateY(-2px); }
                .btn-secondary { background: white; color: #2557FF; border: 2px solid #2557FF; }
                .results-section { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-top: 40px; }
                @media (max-width: 768px) { .results-section { grid-template-columns: 1fr; } .button-group { flex-direction: column; } .btn { width: 100%; } }
                .scenario { background: #fafbfc; border: 2px solid #e5e7eb; border-radius: 8px; padding: 25px; }
                .scenario h3 { font-size: 18px; font-weight: 600; color: #10295f; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 2px solid #d1d5db; }
                .result-row { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #e5e7eb; font-size: 14px; }
                .result-row:last-child { border-bottom: none; }
                .result-label { font-weight: 500; color: #374151; flex: 1; }
                .result-value { font-weight: 600; color: #2557FF; text-align: right; font-size: 16px; min-width: 130px; }
                .result-row.highlight { background: rgba(37, 87, 255, 0.08); padding: 12px; margin: 0 -12px; border-radius: 4px; border: none; font-weight: 600; }
                .result-row.subtotal { font-weight: 600; margin-top: 15px; padding-top: 15px; border-top: 2px solid #2557FF; }
                .replacement-section { margin-top: 25px; padding-top: 25px; border-top: 2px solid #d1d5db; }
                .replacement-section h4 { font-size: 14px; font-weight: 600; color: #10295f; margin-bottom: 12px; text-transform: uppercase; }
                .note { background: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 15px; margin: 15px 0 0 0; border-radius: 4px; font-size: 12px; color: #78350f; }
                .note strong { color: #10295f; }
                .footer { background: #f3f4f6; padding: 20px 30px; text-align: center; font-size: 12px; color: #6b7280; border-top: 1px solid #e5e7eb; }
                .footer p { margin: 8px 0; }
                .footer a { color: #2557FF; text-decoration: none; }
                .negative { color: #dc2626; }
            """)
        ),
        Body(
            Div(
                Div(
                    H1("1031 Exchange Calculator"),
                    P("Compare selling vs. executing a 1031 exchange for your property"),
                    cls="header"
                ),
                Div(
                    (Div(Strong("⚠️ Notice:"), " ", error_message, cls="error-message") if error_message else ""),
                    (Div(
                        P(Strong("Property ID:"), " ", property_data.property_id),
                        P(Strong("Address:"), " ", property_data.property_address, ", ", property_data.city, ", ", property_data.zip_code),
                        P(Strong("Year Built:"), " ", property_data.year_built, " | ", Strong("Beds:"), " ", property_data.bedrooms, " | ", Strong("Baths:"), " ", property_data.bathrooms),
                        cls="property-info"
                    ) if property_data else ""),

                    Div(
                        H2("Property Information"),
                        Div(
                            Div(Label("Purchase Price", for_="purchasePrice"), Input(type="number", id="purchasePrice", value=purchase_price, step="1000"), Span("Original price paid for property", cls="help-text"), cls="input-group"),
                            Div(Label("Mortgage Pay Off", for_="mortgagePayoff"), Input(type="number", id="mortgagePayoff", value=calculated_mortgage, step="1000"), Span("Outstanding loan balance", cls="help-text"), cls="input-group"),
                            Div(Label("Current Value", for_="currentValue"), Input(type="number", id="currentValue", value=current_value, step="1000"), Span("Today's market value", cls="help-text"), cls="input-group"),
                            Div(Label("Cost to Sell (%)", for_="costToSell"), Input(type="number", id="costToSell", value="6", step="0.5", min="0", max="50"), Span("", id="costToSellError", cls="help-text"), cls="input-group"),
                            cls="input-grid"
                        ),
                        Div(
                            Button("Calculate", id="calculateButton", cls="btn btn-primary"),
                            (Button("Download PDF Report", id="exportPdfButton", cls="btn btn-secondary") if property_data else ""),
                            cls="button-group"
                        ),
                        cls="input-section"
                    ),

                    Div(
                        Div(
                            H3("Scenario 1: If You Sell"),
                            Div(Span("Current Value", cls="result-label"), Span("$0", id="sell-currentValue", cls="result-value"), cls="result-row"),
                            Div(Span("Less: Sale Costs", cls="result-label"), Span("$0", id="sell-saleCosts", cls="result-value negative"), cls="result-row"),
                            Div(Span("Less: Capital Gains Tax (20%)", cls="result-label"), Span("$0", id="sell-gainsTax", cls="result-value negative"), cls="result-row"),
                            Div(Span("Less: Mortgage Payoff", cls="result-label"), Span("$0", id="sell-loanPayoff", cls="result-value negative"), cls="result-row"),
                            Div(Span("Net to Reinvest", cls="result-label"), Span("$0", id="sell-netToReinvest", cls="result-value"), cls="result-row highlight subtotal"),
                            Div(Strong("Note:"), " This assumes a 20% capital gains tax rate on the gain between purchase price and current value. Your actual tax liability may vary.", cls="note"),
                            cls="scenario sell"
                        ),
                        Div(
                            H3("Scenario 2: 1031 Exchange"),
                            Div(Span("Current Value", cls="result-label"), Span("$0", id="exchange-currentValue", cls="result-value"), cls="result-row"),
                            Div(Span("Less: Sale Costs", cls="result-label"), Span("$0", id="exchange-saleCosts", cls="result-value negative"), cls="result-row"),
                            Div(Span("Less: Mortgage Payoff", cls="result-label"), Span("$0", id="exchange-loanPayoff", cls="result-value negative"), cls="result-row"),
                            Div(Span("Net Cash Available", cls="result-label"), Span("$0", id="exchange-netCash", cls="result-value"), cls="result-row highlight subtotal"),
                            Div(
                                H4("Replacement Properties (Example)"),
                                Div(Span("Example Price Per Property", cls="result-label"), Span("$0", id="replacement-pricePerProperty", cls="result-value"), cls="result-row"),
                                Div(Span("Down Payment (30% each)", cls="result-label"), Span("$0", id="replacement-downpayment", cls="result-value"), cls="result-row"),
                                Div(Span("Number of Properties", cls="result-label"), Span("0", id="replacement-count", cls="result-value"), cls="result-row highlight"),
                                Div(Span("Total Mortgage (All Properties)", cls="result-label"), Span("$0", id="replacement-totalMortgage", cls="result-value"), cls="result-row"),
                                Div(Span("Total Asset Value", cls="result-label"), Span("$0", id="replacement-totalAssets", cls="result-value"), cls="result-row highlight subtotal"),
                                cls="replacement-section"
                            ),
                            Div(Strong("Note:"), " Capital gains tax is deferred in a 1031 exchange. You must reinvest the sale proceeds within specified timeframes.", cls="note"),
                            cls="scenario exchange"
                        ),
                        cls="results-section"
                    ),
                    cls="content"
                ),
                Div(
                    P(Strong("License and Disclaimer:"), " By choosing to use this tool and/or information, you are agreeing to the terms on the ", A("license page", href="https://fernwood.team/policies-fees-license-and-disclaimer/", target="_blank"), "."),
                    P(f"© 2005–{current_year} Cleo Li and Eric Fernwood. All Rights Reserved."),
                    cls="footer"
                ),
                cls="container"
            ),
            Script(f"""
                const inputs = {{purchasePrice: document.getElementById('purchasePrice'), mortgagePayoff: document.getElementById('mortgagePayoff'), currentValue: document.getElementById('currentValue'), costToSell: document.getElementById('costToSell')}};
                const propertyId = "{property_id}";
                const sessionStartTime = Date.now();

                function formatCurrency(value) {{return new Intl.NumberFormat('en-US', {{style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 0}}).format(value);}}

                function validateCostToSell() {{
                    const rawValue = parseFloat(inputs.costToSell.value) || 0;
                    const errorDisplay = document.getElementById('costToSellError');
                    if (rawValue < 0) {{ errorDisplay.textContent = '❌ Cannot be negative'; errorDisplay.style.color = '#dc2626'; return 0; }}
                    if (rawValue > 50) {{ errorDisplay.textContent = '❌ Cannot exceed 50%'; errorDisplay.style.color = '#dc2626'; return 50; }}
                    errorDisplay.textContent = '';
                    return rawValue;
                }}

                function calculate() {{
                    const purchasePrice = parseFloat(inputs.purchasePrice.value) || 0;
                    const mortgagePayoff = parseFloat(inputs.mortgagePayoff.value) || 0;
                    const currentValue = parseFloat(inputs.currentValue.value) || 0;
                    const costToSellPercent = validateCostToSell() / 100;

                    const sellCurrentValue = currentValue;
                    const sellCosts = costToSellPercent * currentValue;
                    const gain = currentValue - purchasePrice;
                    const gainsTax = 0.2 * gain;
                    const loanPayoff = mortgagePayoff;
                    const netToReinvestSell = sellCurrentValue - sellCosts - gainsTax - loanPayoff;

                    document.getElementById('sell-currentValue').textContent = formatCurrency(sellCurrentValue);
                    document.getElementById('sell-saleCosts').textContent = formatCurrency(-sellCosts);
                    document.getElementById('sell-gainsTax').textContent = formatCurrency(-gainsTax);
                    document.getElementById('sell-loanPayoff').textContent = formatCurrency(-loanPayoff);
                    document.getElementById('sell-netToReinvest').textContent = formatCurrency(netToReinvestSell);

                    const salePrice = currentValue;
                    const exchangeSaleCosts = costToSellPercent * salePrice;
                    const netCashFromSale = salePrice - exchangeSaleCosts - loanPayoff;
                    const examplePropertyPrice = 400000;
                    const downpaymentPercent = 0.30;
                    const downpaymentPerProperty = downpaymentPercent * examplePropertyPrice;
                    const numProperties = Math.floor(netCashFromSale / downpaymentPerProperty);
                    const totalMortgage = (examplePropertyPrice - downpaymentPerProperty) * numProperties;
                    const totalAssetValue = numProperties * examplePropertyPrice;

                    document.getElementById('exchange-currentValue').textContent = formatCurrency(salePrice);
                    document.getElementById('exchange-saleCosts').textContent = formatCurrency(-exchangeSaleCosts);
                    document.getElementById('exchange-loanPayoff').textContent = formatCurrency(-loanPayoff);
                    document.getElementById('exchange-netCash').textContent = formatCurrency(netCashFromSale);
                    document.getElementById('replacement-pricePerProperty').textContent = formatCurrency(examplePropertyPrice);
                    document.getElementById('replacement-downpayment').textContent = formatCurrency(downpaymentPerProperty);
                    document.getElementById('replacement-count').textContent = numProperties.toString();
                    document.getElementById('replacement-totalMortgage').textContent = formatCurrency(totalMortgage);
                    document.getElementById('replacement-totalAssets').textContent = formatCurrency(totalAssetValue);
                    window.calculatorData = {{property_id: propertyId, property_address: "{property_data.property_address if property_data else 'Unknown'}", purchase_price: purchasePrice, mortgage_payoff: mortgagePayoff, current_value: currentValue, cost_to_sell_pct: validateCostToSell()}};
                }}

                Object.values(inputs).forEach(input => {{ input.addEventListener('input', calculate); input.addEventListener('change', calculate); }});
                inputs.costToSell.addEventListener('blur', () => {{ const value = parseFloat(inputs.costToSell.value) || 0; if (value > 50) inputs.costToSell.value = 50; else if (value < 0) inputs.costToSell.value = 0; validateCostToSell(); calculate(); }});
                document.getElementById('calculateButton').addEventListener('click', calculate);

                const exportButton = document.getElementById('exportPdfButton');
                if (exportButton) {{ exportButton.addEventListener('click', async () => {{ calculate(); if (!propertyId) {{ alert('Cannot export: No property data available'); return; }} exportButton.disabled = true; exportButton.textContent = 'Generating PDF...'; try {{ const response = await fetch('/api/export-pdf', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(window.calculatorData) }}); if (response.ok) {{ const blob = await response.blob(); const url = window.URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `1031-calculator-${{propertyId}}.pdf`; document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(url); document.body.removeChild(a); }} else {{ alert('Error generating PDF'); }} }} catch (error) {{ console.error('PDF export error:', error); alert('Error exporting PDF'); }} finally {{ exportButton.disabled = false; exportButton.textContent = 'Download PDF Report'; }} }}); }}

                window.addEventListener('beforeunload', () => {{ if (propertyId) {{ const durationSeconds = Math.round((Date.now() - sessionStartTime) / 1000); navigator.sendBeacon('/api/log-session', JSON.stringify({{property_id: propertyId, duration_seconds: durationSeconds}})); }} }});
                calculate();
            """)
        )
    )


@rt('/api/property/{property_id}')
def get_property_api(property_id: str):
    """API endpoint to fetch property details."""
    session = get_session()
    prop = session.query(Property).filter_by(property_id=property_id).first()
    session.close()

    if not prop:
        return {"error": "Property not found"}, 404

    mortgage_payoff = calculate_mortgage_payoff(prop.first_mortgage_amt, prop.mortgage_rate, prop.mortgage_date)

    return {'property_id': prop.property_id, 'property_address': prop.property_address, 'city': prop.city, 'zip_code': prop.zip_code, 'sale_price': prop.sale_price, 'sale_date': prop.sale_date.isoformat() if prop.sale_date else None, 'current_home_value': prop.current_home_value, 'mortgage_payoff': mortgage_payoff, 'year_built': prop.year_built, 'bedrooms': prop.bedrooms, 'bathrooms': prop.bathrooms}


@rt('/api/export-pdf', methods=['POST'])
async def export_pdf(request):
    """Generate and download PDF of calculator results."""
    data = await request.json()

    property_id = data.get('property_id', 'N/A')
    property_address = data.get('property_address', 'Unknown Property')
    purchase_price = float(data.get('purchase_price', 0))
    mortgage_payoff = float(data.get('mortgage_payoff', 0))
    current_value = float(data.get('current_value', 0))
    cost_to_sell_pct = float(data.get('cost_to_sell_pct', 6)) / 100

    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#2557FF'), spaceAfter=12, alignment=1)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#10295f'), spaceAfter=8, spaceBefore=8)

    story = []
    story.append(Paragraph("1031 Exchange Calculator Report", title_style))
    story.append(Paragraph(f"Property: {property_address} (Property ID: {property_id})", styles['Normal']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    story.append(Paragraph("Property Information", heading_style))
    prop_data = [['Purchase Price', f"${purchase_price:,.0f}"], ['Current Market Value', f"${current_value:,.0f}"], ['Mortgage Balance', f"${mortgage_payoff:,.0f}"], ['Cost to Sell', f"{cost_to_sell_pct*100:.1f}%"]]
    story.append(Table(prop_data, colWidths=[3*inch, 2*inch]))
    story.append(Spacer(1, 0.2*inch))

    sell_costs = cost_to_sell_pct * current_value
    gain = current_value - purchase_price
    gains_tax = 0.2 * gain
    net_to_reinvest_sell = current_value - sell_costs - gains_tax - mortgage_payoff

    story.append(Paragraph("Scenario 1: If You Sell", heading_style))
    sell_data = [['', 'Amount'], ['Current Value', f"${current_value:,.0f}"], ['Less: Sale Costs', f"-${sell_costs:,.0f}"], ['Less: Capital Gains Tax (20%)', f"-${gains_tax:,.0f}"], ['Less: Mortgage Payoff', f"-${mortgage_payoff:,.0f}"], ['Net to Reinvest', f"${net_to_reinvest_sell:,.0f}"]]

    sell_table = Table(sell_data, colWidths=[3.5*inch, 1.5*inch])
    sell_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2557FF')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 11), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8ebf5')), ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(sell_table)
    story.append(Spacer(1, 0.3*inch))

    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("<b>License and Disclaimer:</b> By choosing to use this tool and/or information, you are agreeing to the terms on the <a href='https://fernwood.team/policies-fees-license-and-disclaimer/'>license page</a>.", styles['Normal']))

    doc.build(story)
    pdf_buffer.seek(0)

    return FileResponse(pdf_buffer, media_type='application/pdf', filename=f'1031-calculator-{property_id}-{datetime.now().strftime("%Y%m%d")}.pdf')


@rt('/api/log-session', methods=['POST'])
async def log_session(request):
    """Log session duration for a Property ID."""
    data = await request.json()
    property_id = data.get('property_id')
    duration = data.get('duration_seconds', 0)

    if property_id:
        session = get_session()
        log = session.query(AccessLog).filter_by(property_id=property_id).order_by(AccessLog.accessed_at.desc()).first()
        if log:
            log.session_duration_seconds = duration
            session.commit()
        session.close()

    return {"status": "logged"}


if __name__ == '__main__':
    import uvicorn
    import os
    port = int(os.environ.get('PORT', 5000))
    uvicorn.run(app, host='0.0.0.0', port=port)
