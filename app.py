from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
import urllib.parse
from unidecode import unidecode


def extract_text_with_spacing(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    text_elements = []
    
    for p in soup.find_all('p'):
        paragraph_text = []
        for element in p.children:
            if element.name == 'a':
                paragraph_text.append(element.get_text())
            elif element.name is None:
                paragraph_text.append(element.strip())
        
        text_elements.append(' '.join(paragraph_text))
    return ''.join(text_elements)

def extract_actual_url(url):
    key = "image="
    start = url.find(key)
    if start == -1:
        return None

    encoded_url = url[start + len(key):]
    actual_url = urllib.parse.unquote(encoded_url)
    actual_url = actual_url.replace('width=720', '')
    
    return actual_url

def scrapearticle(article_url, news_items, img_url, title):
    global text_elements
    if article_url:
        article_response = requests.get(f"https://onefootball.com/{article_url}")
        article_soup = BeautifulSoup(article_response.text, 'html.parser')
        paragraph_divs = article_soup.find_all('div', class_='ArticleParagraph_articleParagraph__MrxYL')
        if paragraph_divs:
            text_elements = extract_text_with_spacing(str(paragraph_divs))
        text_elements = unidecode(text_elements)
    
    news_items.append({
        'title': title,
        'article_content': text_elements,
        'img_url': img_url,
        'article_url': article_url,
    })

app = Flask(__name__)

@app.route('/scrape', methods=['GET'])
def scrape():
    url = request.args.get('url')
    response = requests.get(url)
    soup1 = BeautifulSoup(response.content, 'html.parser')
    logo = soup1.find('img', class_='EntityTitle_logo__WHQzH')
    logo = logo['src']
    logo = logo[66:]
    competition = url[40:]
    before_id = request.args.get('before_id', None)  # Get the before_id parameter, if any
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    news_items = []
    # Check if we're paginating with a before_id
    if before_id:
        response = requests.get(f'https://api.onefootball.com/web-experience/en/competition/{competition}?before_id={before_id}')
    else:
        response = requests.get(f'https://api.onefootball.com/web-experience/en/competition/{competition}')
    
    responsedata = response.json()
    teasers = responsedata['containers'][3]['fullWidth']['component']['gallery']['teasers']
    
    last_id = None  # Initialize last_id to store the ID of the last article
    
    for i in teasers:
        link = i['link']
        title2 = i['title']
        # Skip articles with "most league assists" in the title
        if 'most league assists' in title2.lower():
            continue
        else:
            image = i['imageObject']['path']
            image = urllib.parse.unquote(image) if image else None
            image = extract_actual_url(image) if image else None
            image=image[:-12]
            scrapearticle(article_url=link, news_items=news_items, img_url=image, title=title2)
            
            # Update last_id with the current article's ID (useful for pagination)
            last_id = i['id']
    
    # Return the news items and the last ID for pagination
    return jsonify({
        'news_items': news_items,
        'last_id': last_id,
        'logo':logo  # Return the last ID so it can be used for the next page
    })

if __name__ == '__main__':
    app.run(debug=True)
