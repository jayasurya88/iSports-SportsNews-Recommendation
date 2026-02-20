from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle
from .models import Ticket
import io

def generate_ticket_pdf(request, ticket_id):
    """
    Generate a PDF ticket resembling the physical ticket design.
    """
    ticket = Ticket.objects.get(ticket_id=ticket_id)
    match = ticket.match
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # --- Ticket Stub Design ---
    # Coordinates (0,0 is bottom-left)
    # Let's draw it in the middle of the page
    ticket_width = 500
    ticket_height = 220
    x_start = (width - ticket_width) / 2
    y_start = (height - ticket_height) / 2
    
    # 1. Main Background (White)
    p.setFillColor(colors.white)
    p.setStrokeColor(colors.black)
    p.setLineWidth(1)
    p.rect(x_start, y_start, ticket_width, ticket_height, fill=1)
    
    # 2. Left Strip (Barcode Area)
    strip_width = 50
    p.fillColor = colors.white
    p.rect(x_start, y_start, strip_width, ticket_height, fill=1, stroke=1)
    
    # Vertical Text (Simulated) - "TICKET ID"
    p.saveState()
    p.translate(x_start + 15, y_start + ticket_height/2)
    p.rotate(90)
    p.setFillColor(colors.darkgrey)
    p.setFont("Courier-Bold", 10)
    p.drawCentredString(0, 0, f"ID: {ticket.ticket_id}")
    p.restoreState()
    
    # Fake Barcode (Lines)
    p.setLineWidth(0.5)
    bar_x = x_start + 30
    bar_y_start = y_start + 20
    bar_y_end = y_start + ticket_height - 20
    
    import random
    current_y = bar_y_start
    while current_y < bar_y_end:
        line_height = random.randint(1, 3)
        gap = random.randint(1, 3)
        p.line(bar_x - 10, current_y, bar_x + 10, current_y)
        current_y += (line_height + gap)

    # 3. Header Band (Black)
    header_height = 40
    p.setFillColor(colors.black)
    p.rect(x_start + strip_width, y_start + ticket_height - header_height, ticket_width - strip_width, header_height, fill=1, stroke=0)
    
    # Header Text (Home Team)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(x_start + strip_width + 20, y_start + ticket_height - 28, match.home_team.name.upper())
    
    # Red Bottom Border for Header
    p.setStrokeColor(colors.red)
    p.setLineWidth(3)
    p.line(x_start + strip_width, y_start + ticket_height - header_height, x_start + ticket_width, y_start + ticket_height - header_height)
    
    # 4. Content Area
    content_x = x_start + strip_width + 20
    content_y_top = y_start + ticket_height - header_height - 30
    
    # Away Team (Large)
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(content_x, content_y_top, match.away_team.name.upper())
    
    # League Small Text
    p.setFillColor(colors.gray)
    p.setFont("Helvetica", 9)
    league_name = match.league if match.league else "PREMIER LEAGUE"
    p.drawString(content_x, content_y_top - 15, league_name.upper())
    
    # Date & Time
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(content_x, content_y_top - 45, "Date & Kick Off")
    
    p.setFont("Helvetica", 14)
    date_str = match.date_time.strftime("%b %d, %Y • %H:%M")
    p.drawString(content_x, content_y_top - 65, date_str)
    
    # Price
    p.setFont("Helvetica-Bold", 14)
    p.drawString(content_x, content_y_top - 100, f"Price: £{ticket.total_price}")
    
    # 5. Right Column (Seat Details)
    # Divider Line
    right_col_x = x_start + ticket_width - 140
    p.setStrokeColor(colors.lightgrey)
    p.setLineWidth(1)
    p.line(right_col_x, y_start + 20, right_col_x, y_start + ticket_height - header_height - 10)
    
    detail_x = right_col_x + 10
    detail_y = content_y_top
    
    p.setFont("Helvetica", 8)
    p.setFillColor(colors.gray)
    p.drawString(detail_x, detail_y, "SEAT LOCATION")
    p.setFont("Helvetica-Bold", 10)
    p.setFillColor(colors.black)
    p.drawString(detail_x, detail_y - 12, f"{ticket.seat_section} Stand")
    
    detail_y -= 40
    
    # Grid of details
    data = [
        ['Turnstile', 'Access'],
        ['B', '11'],
        ['Row', 'Seat'],
        ['G', '42']
    ]
    
    # Simple manual drawing for grid
    p.setFont("Helvetica", 8)
    p.setFillColor(colors.gray)
    p.drawString(detail_x, detail_y, "Turnstile")
    p.drawString(detail_x + 60, detail_y, "Access")
    
    p.setFont("Helvetica-Bold", 10)
    p.setFillColor(colors.black)
    p.drawString(detail_x, detail_y - 12, "B")
    p.drawString(detail_x + 60, detail_y - 12, "11")
    
    detail_y -= 35
    p.setFont("Helvetica", 8)
    p.setFillColor(colors.gray)
    p.drawString(detail_x, detail_y, "Row")
    p.drawString(detail_x + 60, detail_y, "Seat")
    
    p.setFont("Helvetica-Bold", 10)
    p.setFillColor(colors.black)
    p.drawString(detail_x, detail_y - 12, "G")
    p.drawString(detail_x + 60, detail_y - 12, "42")
    
    # 6. Footer Band
    footer_height = 25
    p.setFillColor(colors.white)
    p.setStrokeColor(colors.lightgrey)
    p.rect(x_start + strip_width, y_start, ticket_width - strip_width, footer_height, fill=1, stroke=1)
    
    p.setFont("Helvetica", 8)
    p.setFillColor(colors.gray)
    p.drawString(x_start + strip_width + 10, y_start + 8, "iSports Ticket System • www.isports.com")
    
    # Finish
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')
