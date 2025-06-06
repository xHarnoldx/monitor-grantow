# scraper.py - Główny plik agenta monitorującego granty

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Konfiguracja email
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# Strony do monitorowania
WEBSITES_TO_MONITOR = [
    {
        'name': 'Narodowe Centrum Kultury',
        'url': 'https://nck.pl/dotacje-i-stypendia',
        'keywords': ['dziedzictwo', 'digitalizacja', 'archiwum', 'warszawa', 'mazowsze']
    },
    {
        'name': 'Ministerstwo Kultury',
        'url': 'https://www.gov.pl/web/kultura',
        'keywords': ['kultura cyfrowa', 'dziedzictwo', 'edukacja']
    },
    {
        'name': 'Narodowy Instytut Dziedzictwa',
        'url': 'https://nid.pl/pl/',
        'keywords': ['dziedzictwo kulturowe', 'ochrona', 'dokumentacja']
    }
]

# Słowa kluczowe dla filtrowania
GRANT_KEYWORDS = [
    'dziedzictwo kulturowe',
    'digitalizacja',
    'archiwum cyfrowe',
    'historia mówiona',
    'edukacja kulturalna',
    'warszawa',
    'mazowsze',
    'ngo',
    'organizacje pozarządowe',
    'granty',
    'dotacje',
    'konkurs',
    'nabór'
]

def send_email(subject, content):
    """Wysyła email z informacjami o grantach"""
    try:
        # Tworzenie wiadomości
        message = MIMEMultipart()
        message["From"] = EMAIL_ADDRESS
        message["To"] = RECIPIENT_EMAIL
        message["Subject"] = subject
        
        # Dodanie treści HTML
        html_content = f"""
        <html>
        <body>
            <h2>🎯 Nowe możliwości grantowe dla Twojej fundacji</h2>
            {content}
            <hr>
            <p><small>Automatyczne powiadomienie wysłane przez agenta monitorującego granty<br>
            Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
        </body>
        </html>
        """
        
        message.attach(MIMEText(html_content, "html"))
        
        # Wysłanie emaila
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(message)
            
        print("✅ Email wysłany pomyślnie!")
        return True
        
    except Exception as e:
        print(f"❌ Błąd wysyłania emaila: {e}")
        return False

def check_for_keywords(text, keywords):
    """Sprawdza czy tekst zawiera słowa kluczowe"""
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)

def scrape_website(website_info):
    """Sprawdza jedną stronę pod kątem nowych grantów"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print(f"🔍 Sprawdzam: {website_info['url']}")
        response = requests.get(website_info['url'], headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Szukanie linków i tekstów zawierających słowa kluczowe
        found_grants = []
        
        # Sprawdzanie linków
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True)
            if len(link_text) > 10:  # Ignoruj bardzo krótkie linki
                if (check_for_keywords(link_text, website_info['keywords']) or 
                    check_for_keywords(link_text, GRANT_KEYWORDS)):
                    
                    href = link.get('href')
                    if href.startswith('/'):
                        # Względny URL - dodaj domenę
                        base_url = f"https://{website_info['url'].split('/')[2]}"
                        href = base_url + href
                    elif not href.startswith('http'):
                        href = website_info['url'] + '/' + href
                    
                    found_grants.append({
                        'title': link_text[:150],  # Ograniczenie długości
                        'url': href,
                        'type': 'link',
                        'source': website_info['name']
                    })
        
        # Sprawdzanie nagłówków
        for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
            header_text = header.get_text(strip=True)
            if len(header_text) > 10:
                if (check_for_keywords(header_text, website_info['keywords']) or 
                    check_for_keywords(header_text, GRANT_KEYWORDS)):
                    found_grants.append({
                        'title': header_text[:150],
                        'url': website_info['url'],
                        'type': 'header',
                        'source': website_info['name']
                    })
        
        # Sprawdzanie paragrafów (ograniczone)
        for paragraph in soup.find_all('p')[:20]:  # Tylko pierwsze 20 paragrafów
            paragraph_text = paragraph.get_text(strip=True)
            if len(paragraph_text) > 50:  # Tylko dłuższe paragrafy
                if (check_for_keywords(paragraph_text, website_info['keywords']) or 
                    check_for_keywords(paragraph_text, GRANT_KEYWORDS)):
                    found_grants.append({
                        'title': paragraph_text[:150],
                        'url': website_info['url'],
                        'type': 'content',
                        'source': website_info['name']
                    })
        
        # Usuwanie duplikatów i ograniczenie wyników
        unique_grants = []
        seen_titles = set()
        
        for grant in found_grants:
            title_key = grant['title'].lower()[:50]  # Pierwsze 50 znaków dla porównania
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_grants.append(grant)
                if len(unique_grants) >= 3:  # Maksymalnie 3 wyniki na stronę
                    break
        
        return unique_grants
        
    except Exception as e:
        print(f"❌ Błąd przy sprawdzaniu {website_info['name']}: {e}")
        return []

def main():
    """Główna funkcja agenta"""
    print(f"🚀 Agent monitorujący granty uruchomiony: {datetime.now()}")
    print(f"📧 Email będzie wysłany na: {RECIPIENT_EMAIL}")
    
    all_found_grants = []
    
    # Sprawdzanie każdej strony
    for website in WEBSITES_TO_MONITOR:
        print(f"\n🔍 Sprawdzam: {website['name']}")
        grants = scrape_website(website)
        
        if grants:
            all_found_grants.extend(grants)
            print(f"✅ Znaleziono {len(grants)} potencjalnych możliwości na {website['name']}")
            for grant in grants:
                print(f"   📝 {grant['title'][:80]}...")
        else:
            print(f"ℹ️ Brak dopasowanych wyników na {website['name']}")
        
        # Pauza między zapytaniami (dobre praktyki)
        time.sleep(3)
    
    # Wysyłanie emaila jeśli znaleziono granty
    if all_found_grants:
        print(f"\n📊 Łącznie znaleziono {len(all_found_grants)} możliwości grantowych")
        
        email_content = f"<h3>Znalezione możliwości grantowe ({len(all_found_grants)}):</h3><ul>"
        
        for grant in all_found_grants:
            email_content += f"""
            <li>
                <strong>{grant['title']}</strong><br>
                <small>Źródło: {grant['source']} | Typ: {grant['type']}</small><br>
                <a href='{grant['url']}' target='_blank'>🔗 Więcej informacji</a>
            </li><br>
            """
        
        email_content += "</ul>"
        email_content += f"<p><strong>Sprawdzone strony:</strong></p><ul>"
        
        for website in WEBSITES_TO_MONITOR:
            email_content += f"<li>{website['name']}: <a href='{website['url']}' target='_blank'>{website['url']}</a></li>"
        
        email_content += "</ul>"
        
        subject = f"🎯 Znaleziono {len(all_found_grants)} nowych możliwości grantowych - {datetime.now().strftime('%Y-%m-%d')}"
        
        if send_email(subject, email_content):
            print(f"📧 Wysłano powiadomienie email o {len(all_found_grants)} możliwościach grantowych")
        else:
            print("❌ Nie udało się wysłać emaila")
            
    else:
        print("\n🔍 Nie znaleziono nowych odpowiednich możliwości grantowych")
        print("ℹ️ To może oznaczać, że:")
        print("   - Brak nowych ogłoszeń")
        print("   - Słowa kluczowe nie pasują do dostępnych treści")
        print("   - Strony mogą być tymczasowo niedostępne")
        
        # Opcjonalnie: wyślij email informujący o braku wyników
        summary_email = f"""
        <h3>Raport agenta monitorującego granty</h3>
        <p>Agent sprawdził {len(WEBSITES_TO_MONITOR)} stron, ale nie znalazł nowych możliwości grantowych 
        odpowiadających kryteriom Twojej fundacji.</p>
        
        <p><strong>Sprawdzone strony:</strong></p>
        <ul>
        """
        
        for website in WEBSITES_TO_MONITOR:
            summary_email += f"<li>{website['name']}: <a href='{website['url']}' target='_blank'>{website['url']}</a></li>"
        
        summary_email += """
        </ul>
        <p><small>Agent będzie kontynuować monitorowanie zgodnie z harmonogramem.</small></p>
        """
        
        send_email(f"📊 Raport agenta grantowego - brak nowych możliwości - {datetime.now().strftime('%Y-%m-%d')}", summary_email)
    
    print(f"\n✅ Agent zakończył pracę: {datetime.now()}")

if __name__ == "__main__":
    main()
