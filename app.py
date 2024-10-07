from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
import urllib.parse
from unidecode import unidecode
from concurrent.futures import ThreadPoolExecutor

session = requests.Session()  # Reuse session for better performance

def extract_text_with_spacing(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    text_elements = []

    for p in soup.find_all('p'):
        paragraph_text = ' '.join(
            [element.get_text() if element.name == 'a' else element.strip() 
            for element in p.children if element.name is None or element.name == 'a']
        )
        text_elements.append(paragraph_text)

    return ''.join(text_elements)

def extract_actual_url(url):
    key = "image="
    start = url.find(key)
    if start == -1:
        return None
    if 'betting' in url:
        return False 
    elif 'squawka' in url:
        return False
    elif "bit.ly" in url:
        return False
    elif "footballtoday.com" in url:
        return False
    else:
        return urllib.parse.unquote(url[start + len(key):]).replace('width=720', '')

def scrapearticle(article_url, title, image, time, publisher):
    global text_elements
    text_elements = ""
    if article_url:
        article_response = session.get(f"https://onefootball.com/{article_url}")
        article_soup = BeautifulSoup(article_response.text, 'html.parser')
        article_id = article_url[-8:]
        paragraph_divs = article_soup.find_all('div', class_='ArticleParagraph_articleParagraph__MrxYL')
        
        if paragraph_divs:
            text_elements = extract_text_with_spacing(str(paragraph_divs))
        text_elements = unidecode(text_elements)
    
    return {
        'title': title,
        'article_content': text_elements,
        'img_url': image,
        'time':time,
        'article_url': article_url,
        'article_id' :article_id,
        'publisher':publisher
    }

app = Flask(__name__)

@app.route('/scrape', methods=['GET'])
def scrape():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    # Fetch the main page
    response = session.get(url)
    soup1 = BeautifulSoup(response.content, 'html.parser')
    logo_tag = soup1.find('img', class_='EntityTitle_logo__WHQzH')
    logo = logo_tag['src'][66:] if logo_tag else None
    competition = url[40:]

    before_id = request.args.get('before_id', None)  # Pagination ID
    api_url = f'https://api.onefootball.com/web-experience/en/competition/{competition}'
    if before_id:
        api_url += f'?before_id={before_id}'

    api_response = session.get(api_url)
    responsedata = api_response.json()
    teasers = responsedata['containers'][3]['fullWidth']['component']['gallery']['teasers']

    news_items = []
    last_id = None

    # Use a thread pool for concurrent article scraping
    with ThreadPoolExecutor() as executor:
        futures = []
        for teaser in teasers:
            
            image = teaser['imageObject']['path'] if 'imageObject' in teaser else None
            if image:
                title = teaser['title']
                if 'most league assists' in title.lower():
                    continue  # Skip specific titles
                image = teaser['imageObject']['path'] if 'imageObject' in teaser else None
                image = extract_actual_url(image) if image else None
                image = image[:-12] if image else None  # Remove width modification
    
                link = teaser['link']
                time = teaser['publishTime']
                publisher = teaser['publisherName']
                last_id = teaser['id']  # Update last_id for pagination
    
                futures.append(
                    executor.submit(scrapearticle, article_url=link, title=title, image=image, time=time, publisher=publisher)
                )
            else:
                pass
        
        for future in futures:
            news_items.append(future.result())

    return jsonify({
        'news_items': news_items,
        'last_id': last_id,
        'logo': logo
    })

if __name__ == '__main__':
    app.run(debug=True)
