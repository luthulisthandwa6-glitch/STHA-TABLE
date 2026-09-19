from uuid import uuid4
import json
import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Flask, Response, abort, redirect, render_template, request, stream_with_context, url_for
from twilio.rest import Client

APP_NAME = 'STHA TABLE'

app = Flask(__name__)
logger = logging.getLogger(__name__)

ORDERS = []
EVENTS = []
NEXT_EVENT_ID = 0
RESTAURANTS = {
    'roco-mamas': {
        'name': 'Roco Mamas',
        'tagline': 'Big burgers, bold flavours, and great vibes',
        'hero_copy': "Explore your Roco Mamas favourites, from loaded burgers to cheesy sides and comforting extras.",
        'note': "Ask your waiter about today's specials and freshly made sides.",
        'waiter_phone': '+27000000000',
        'currency': 'R',
        'menu': [
            {'id': 'boerewors-roll', 'name': 'Boerewors Roll', 'price': 65, 'cat': 'Braai'},
            {'id': 'chicken-bunny-chow', 'name': 'Chicken Bunny Chow', 'price': 110, 'cat': 'Mains'},
            {'id': 'pap', 'name': 'Pap', 'price': 30, 'cat': 'Sides'},
            {'id': 'chakalaka', 'name': 'Chakalaka', 'price': 35, 'cat': 'Sides'},
            {'id': 'rooibos-iced-tea', 'name': 'Rooibos Iced Tea', 'price': 28, 'cat': 'Drinks'},
            {'id': 'koeksister', 'name': 'Koeksister', 'price': 25, 'cat': 'Dessert'},
        ],
    },
}


def chain(name, tagline, menu):
    return {
        'name': name,
        'tagline': tagline,
        'hero_copy': f'Order from {name} without waiting in line. Choose your meal and let the restaurant serve you.',
        'note': 'Contact the cashier if you need help with your order.',
        'waiter_phone': '+27000000000',
        'currency': 'R',
        'menu': menu,
    }


RESTAURANTS.update({
    'nandos': chain("Nando's", 'Peri-peri chicken, South African style', [
        {'id': 'quarter-chicken', 'name': 'Quarter Chicken', 'price': 85, 'cat': 'Chicken'},
        {'id': 'peri-peri-burger', 'name': 'Peri-peri Burger', 'price': 79, 'cat': 'Chicken'},
        {'id': 'peri-chips', 'name': 'Peri-peri Chips', 'price': 35, 'cat': 'Sides'},
    ]),
    'chicken-licken': chain('Chicken Licken', 'Soul food with serious flavour', [
        {'id': 'hotwings', 'name': 'Hotwings', 'price': 69, 'cat': 'Chicken'},
        {'id': 'chicken-burger', 'name': 'Chicken Burger', 'price': 65, 'cat': 'Chicken'},
        {'id': 'chips', 'name': 'Chips', 'price': 30, 'cat': 'Sides'},
    ]),
    'spur': chain('Spur Steak Ranches', 'Family meals and legendary burgers', [
        {'id': 'cheese-burger', 'name': 'Cheese Burger', 'price': 109, 'cat': 'Mains'},
        {'id': 'ribs-chips', 'name': 'Ribs & Chips', 'price': 189, 'cat': 'Mains'},
        {'id': 'onion-rings', 'name': 'Onion Rings', 'price': 45, 'cat': 'Sides'},
    ]),
    'ocean-basket': chain('Ocean Basket', 'Fresh seafood, made for sharing', [
        {'id': 'fish-chips', 'name': 'Fish & Chips', 'price': 135, 'cat': 'Seafood'},
        {'id': 'calamari', 'name': 'Calamari', 'price': 149, 'cat': 'Seafood'},
        {'id': 'greek-salad', 'name': 'Greek Salad', 'price': 65, 'cat': 'Sides'},
    ]),
    'steers': chain('Steers', 'Flame-grilled burgers', [
        {'id': 'classic-burger', 'name': 'Classic Burger', 'price': 79, 'cat': 'Burgers'},
        {'id': 'steak-roll', 'name': 'Steak Roll', 'price': 99, 'cat': 'Mains'},
        {'id': 'chips', 'name': 'Hand-cut Chips', 'price': 32, 'cat': 'Sides'},
    ]),
    'debonairs': chain("Debonairs Pizza", 'Hot, fresh pizza for everyone', [
        {'id': 'regina-pizza', 'name': 'Regina Pizza', 'price': 119, 'cat': 'Pizza'},
        {'id': 'chicken-bar-one', 'name': 'Chicken Bar-One Pizza', 'price': 139, 'cat': 'Pizza'},
        {'id': 'garlic-rolls', 'name': 'Garlic Rolls', 'price': 39, 'cat': 'Sides'},
    ]),
    'wimpy': chain('Wimpy', 'Feel-good meals, any time of day', [
        {'id': 'breakfast', 'name': 'Full Breakfast', 'price': 99, 'cat': 'Breakfast'},
        {'id': 'wimpy-burger', 'name': 'Wimpy Burger', 'price': 89, 'cat': 'Mains'},
        {'id': 'milkshake', 'name': 'Milkshake', 'price': 42, 'cat': 'Drinks'},
    ]),
    'galitos-marshalltown-howard-house': chain("Galito's Marshalltown Howard House", 'Flame-grilled chicken and generous sides', [
        {'id': 'galitos-quarter-chicken-only', 'name': '1/4 Chicken Only', 'price': 65, 'cat': 'Classic Meals'},
        {'id': 'galitos-quarter-chicken-chips', 'name': '1/4 Chicken and Chips', 'price': 85, 'cat': 'Classic Meals'},
        {'id': 'galitos-quarter-chicken-pap', 'name': '1/4 Chicken and Jumbo Pap', 'price': 85, 'cat': 'Classic Meals'},
        {'id': 'galitos-quarter-chicken-rice', 'name': '1/4 Chicken and Rice', 'price': 85, 'cat': 'Classic Meals'},
        {'id': 'galitos-half-chicken-only', 'name': '1/2 Chicken only', 'price': 119, 'cat': 'Classic Meals'},
        {'id': 'galitos-half-chicken-chips', 'name': '1/2 Chicken + chips', 'price': 139, 'cat': 'Classic Meals'},
        {'id': 'galitos-half-chicken-pap', 'name': '1/2 Chicken + Jumbo Pap', 'price': 139, 'cat': 'Classic Meals'},
        {'id': 'galitos-half-time-score', 'name': 'HalfTime Score', 'price': 175, 'cat': 'Classic Meals'},
        {'id': 'galitos-hot-box-3-pap', 'name': 'Hot Box 3 - Pap', 'price': 115, 'cat': 'Hot Box'},
        {'id': 'galitos-hot-box-3-chips', 'name': 'Hot Box 3 - Chips', 'price': 115, 'cat': 'Hot Box'},
        {'id': 'galitos-hot-box-5-pap', 'name': 'Hot Box 5 - Pap', 'price': 165, 'cat': 'Hot Box'},
        {'id': 'galitos-hot-box-5-rice', 'name': 'Hot Box 5 - Rice', 'price': 165, 'cat': 'Hot Box'},
        {'id': 'galitos-livers-pap', 'name': 'Livers and Pap', 'price': 55, 'cat': 'Value Meals'},
        {'id': 'galitos-livers-only', 'name': 'Livers Only', 'price': 39, 'cat': 'Value Meals'},
        {'id': 'galitos-livers-rice', 'name': 'Livers and Rice', 'price': 55, 'cat': 'Value Meals'},
        {'id': 'galitos-snack-roll', 'name': 'Snack Roll', 'price': 39, 'cat': 'Value Meals'},
        {'id': 'galitos-chicken-salad', 'name': 'Chicken Salad', 'price': 95, 'cat': 'Healthy Choice'},
        {'id': 'galitos-garden-salad', 'name': 'Garden Salad', 'price': 65, 'cat': 'Healthy Choice'},
        {'id': 'galitos-chilli-bean', 'name': 'Chilli Bean', 'price': 49, 'cat': 'Sides'},
        {'id': 'galitos-jumbo-pap', 'name': 'Jumbo Pap', 'price': 27, 'cat': 'Sides'},
        {'id': 'galitos-regular-chips', 'name': 'Regular chips', 'price': 35, 'cat': 'Sides'},
        {'id': 'galitos-spicy-rice', 'name': 'Spicy Rice', 'price': 35, 'cat': 'Sides'},
        {'id': 'galitos-cans-330ml', 'name': 'Cappy - Cans 330ml', 'price': 25, 'cat': 'Drinks'},
        {'id': 'galitos-buddy-440ml', 'name': 'Buddy 440ml', 'price': 25, 'cat': 'Drinks'},
        {'id': 'galitos-powerade-500ml', 'name': 'Powerade 500ml', 'price': 35, 'cat': 'Drinks'},
        {'id': 'galitos-valpre-water', 'name': 'Valpre Water Still', 'price': 25, 'cat': 'Drinks'},
        {'id': 'galitos-shis hebo-sauce', 'name': 'Shishebo Sauce', 'price': 15, 'cat': 'Extra'},
        {'id': 'galitos-galimayo', 'name': 'GaliMayo', 'price': 27, 'cat': 'Extra'},
    ]),
    'mimmos-braamfontein': chain('Mimmos Braamfontein', 'Italian favourites and family meals', [
        {'id': 'mimmos-half-chicken', 'name': '1/2 Chicken', 'price': 156, 'cat': 'Featured items'},
        {'id': 'mimmos-bolognese', 'name': 'Bolognese', 'price': 137, 'cat': 'Featured items'},
        {'id': 'mimmos-tutto', 'name': 'Tutto', 'price': 168, 'cat': 'Featured items'},
        {'id': 'mimmos-vegetarian', 'name': 'Vegetarian', 'price': 116, 'cat': 'Classic Pizzas'},
        {'id': 'mimmos-regina', 'name': 'Regina', 'price': 114, 'cat': 'Classic Pizzas'},
        {'id': 'mimmos-hawaiian', 'name': 'Hawaiian', 'price': 114, 'cat': 'Classic Pizzas'},
        {'id': 'mimmos-margherita', 'name': 'Margherita', 'price': 91, 'cat': 'Classic Pizzas'},
        {'id': 'mimmos-tutto-gourmet', 'name': 'Tutto', 'price': 168, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-seafood-pizza', 'name': 'Seafood', 'price': 201, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-chicken-maestro', 'name': 'Chicken Maestro', 'price': 162, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-meat-lovers', 'name': 'Meat Lovers', 'price': 162, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-nacho-cajun-chicken', 'name': 'Nacho Cajun Chicken', 'price': 162, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-mariannas', 'name': "Marianna's", 'price': 155, 'cat': 'Classic Pastas'},
        {'id': 'mimmos-mexicana', 'name': 'Mexicana', 'price': 140, 'cat': 'Classic Pastas'},
        {'id': 'mimmos-napolitana', 'name': 'Napolitana', 'price': 117, 'cat': 'Classic Pastas'},
        {'id': 'mimmos-alfredo-ham', 'name': 'Alfredo Ham', 'price': 138, 'cat': 'Classic Pastas'},
        {'id': 'mimmos-alfredo-chicken', 'name': 'Alfredo Chicken', 'price': 140, 'cat': 'Classic Pastas'},
        {'id': 'mimmos-alla-luca', 'name': 'Alla Luca', 'price': 149, 'cat': 'Gourmet Pastas'},
        {'id': 'mimmos-carni-amore', 'name': 'Carni Amore', 'price': 169, 'cat': 'Gourmet Pastas'},
        {'id': 'mimmos-seafood-ala-crema', 'name': 'Seafood Ala Crema', 'price': 216, 'cat': 'Gourmet Pastas'},
        {'id': 'mimmos-rump-300gm', 'name': 'Rump 300gm', 'price': 226, 'cat': 'Grills'},
        {'id': 'mimmos-ribs', 'name': 'Ribs', 'price': 234, 'cat': 'Grills'},
        {'id': 'mimmos-grilled-hake', 'name': 'Grilled Hake 10/12oz', 'price': 167, 'cat': 'Grills'},
        {'id': 'mimmos-sirloin-steak', 'name': 'Sirloin Steak 200gm', 'price': 183, 'cat': 'Grills'},
        {'id': 'mimmos-chicken-schnitzel', 'name': 'Chicken Schnitzel', 'price': 157, 'cat': 'Grills'},
        {'id': 'mimmos-calamari-main', 'name': 'Calamari Main', 'price': 190, 'cat': 'Grills'},
        {'id': 'mimmos-milkshake', 'name': 'Milkshake', 'price': 60, 'cat': 'Beverages'},
        {'id': 'mimmos-cans-300ml', 'name': 'Cans 300ml', 'price': 35, 'cat': 'Beverages'},
        {'id': 'mimmos-appletiser', 'name': 'Appletiser 330ml', 'price': 47, 'cat': 'Beverages'},
        {'id': 'mimmos-mineral-water', 'name': 'Mineral Water Still - 500ml', 'price': 29, 'cat': 'Beverages'},
        {'id': 'mimmos-ice-cream', 'name': 'Ice Cream and Chocolate Sauce', 'price': 64, 'cat': 'Desserts'},
        {'id': 'mimmos-cheese-burger', 'name': 'Cheese Burger', 'price': 119, 'cat': 'Burgers'},
        {'id': 'mimmos-chicken-cheese-burger', 'name': 'Chicken Cheese Schnitzel Burger', 'price': 130, 'cat': 'Burgers'},
        {'id': 'mimmos-fillet-burger', 'name': 'Fillet Burger', 'price': 143, 'cat': 'Burgers'},
        {'id': 'mimmos-pompeii-double-cheese', 'name': 'Pompeii (Double Cheese)', 'price': 176, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-nacho-mince', 'name': 'Nacho Mince', 'price': 162, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-nacho-vegetarian', 'name': 'Nacho Vegetarian', 'price': 162, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-pork-lovers', 'name': 'Pork Lovers', 'price': 167, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-parigi', 'name': 'Parigi', 'price': 168, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-quatro-stagioni', 'name': 'Quatro Stagioni', 'price': 166, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-four-cheeses', 'name': 'Four Cheeses', 'price': 189, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-beet-supreme', 'name': 'Beet Supreme', 'price': 168, 'cat': 'Gourmet Pizzas'},
        {'id': 'mimmos-pulled-pork-pasta', 'name': 'Pulled Pork 140g Portion', 'price': 140, 'cat': 'Classic Pastas'},
        {'id': 'mimmos-macaroni-cheese-al-forno-plus', 'name': 'Macaroni Cheese Al Forno Plus', 'price': 140, 'cat': 'Classic Pastas'},
        {'id': 'mimmos-sophia', 'name': 'Sophia', 'price': 192, 'cat': 'Gourmet Pastas'},
        {'id': 'mimmos-tikka-chicken-pasta', 'name': 'Tikka Chicken', 'price': 162, 'cat': 'Gourmet Pastas'},
        {'id': 'mimmos-macaroni-cheese-al-forno', 'name': 'Macaroni Cheese Al Forno', 'price': 149, 'cat': 'Wood Fired Pasta'},
        {'id': 'mimmos-lasagne-al-forno', 'name': 'Lasagne Al Forno', 'price': 162, 'cat': 'Wood Fired Pasta'},
        {'id': 'mimmos-one-half-chicken', 'name': '1/2 Chicken', 'price': 156, 'cat': 'Grills'},
        {'id': 'mimmos-t-bone', 'name': 'T-Bone', 'price': 298, 'cat': 'Grills'},
        {'id': 'mimmos-gourmet-shake', 'name': 'Gourmet Shake Death by Chocolate', 'price': 90, 'cat': 'Beverages'},
        {'id': 'mimmos-cans-zero-300ml', 'name': 'Cans Zero 300ml', 'price': 35, 'cat': 'Beverages'},
        {'id': 'mimmos-grapetiser', 'name': 'Grapetiser 330ml', 'price': 47, 'cat': 'Beverages'},
        {'id': 'mimmos-mineral-water-sparkling', 'name': 'Mineral Water Sparkling - 500ml', 'price': 29, 'cat': 'Beverages'},
        {'id': 'mimmos-lipton-iced-tea', 'name': 'Lipton Iced Tea', 'price': 40, 'cat': 'Beverages'},
        {'id': 'mimmos-two-litre-bottle', 'name': '2Lt Bottle', 'price': 48, 'cat': 'Beverages'},
        {'id': 'mimmos-smoothie', 'name': 'Smoothie', 'price': 70, 'cat': 'Beverages'},
        {'id': 'mimmos-fresh-fruit-juice', 'name': 'Fresh Fruit Juice (Prepack 350ml)', 'price': 47, 'cat': 'Beverages'},
        {'id': 'mimmos-freezo-coffee', 'name': 'Freezo Coffee', 'price': 72, 'cat': 'Beverages'},
        {'id': 'mimmos-two-classic-pizzas', 'name': '2 x Classic Pizza Large (30cm)', 'price': 199, 'cat': 'Monday & Tuesday Special'},
        {'id': 'mimmos-three-classic-pasta', 'name': '3 x Classic Pasta', 'price': 299, 'cat': 'Monday & Tuesday Special'},
        {'id': 'mimmos-cheese-bacon-onion-burger', 'name': 'Cheese Bacon & Onion Burger', 'price': 130, 'cat': 'Burgers'},
        {'id': 'mimmos-mushroom-cheese-avo-burger', 'name': 'Mushroom, Cheese & Avo Chicken Schnitzel Burger', 'price': 143, 'cat': 'Burgers'},
    ]),
    'the-smokehouse-and-grill': chain('The Smokehouse and Grill', 'Slow-smoked favourites and bold barbecue flavours', [
        {'id': 'brisket-mac-cheese', 'name': '(New) Brisket Mac & Cheese', 'price': 140, 'cat': 'Mains'},
        {'id': 'smoked-beef-brisket-bun', 'name': 'Smoked Beef Brisket Bun', 'price': 149, 'cat': 'Mains'},
        {'id': 'smoked-pulled-pork-bun', 'name': 'Smoked Pulled Pork Bun', 'price': 135, 'cat': 'Mains'},
        {'id': 'smoked-wings-half-portion', 'name': 'Smoked Wings (Half Portion)', 'price': 120, 'cat': 'Mains'},
        {'id': 'smoked-wings-full-portion', 'name': 'Smoked Wings (Full Portion)', 'price': 200, 'cat': 'Mains'},
        {'id': 'loaded-smoked-potato', 'name': 'Loaded Smoked Potato', 'price': 95, 'cat': 'Mains'},
        {'id': 'spitfire-bombs', 'name': 'Spitfire Bombs', 'price': 70, 'cat': 'Mains'},
        {'id': 'smoked-pork-ribs-half', 'name': 'Smoked Pork Ribs (1/2kg)', 'price': 230, 'cat': 'Mains'},
        {'id': 'smoked-beef-rib-single', 'name': 'Smoked Beef Rib (Single Rib)', 'price': 120, 'cat': 'Mains'},
        {'id': 'smoked-beef-ribs-half', 'name': 'Smoked Beef Ribs (1/2kg)', 'price': 310, 'cat': 'Mains'},
        {'id': 'chicken-mac-cheese', 'name': '(New) Chicken Mac & Cheese', 'price': 110, 'cat': 'Mains'},
        {'id': 'smoked-beef-rib-bun', 'name': 'Smoked Beef Rib Bun', 'price': 149, 'cat': 'Mains'},
    ]),
})


def get_restaurant(slug):
    restaurant = RESTAURANTS.get(slug)
    if restaurant is None:
        abort(404)
    return restaurant


def publish_event(event_type, payload):
    global NEXT_EVENT_ID
    NEXT_EVENT_ID += 1
    EVENTS.append({'id': NEXT_EVENT_ID, 'type': event_type, 'payload': payload})


@app.route('/')
def menu():
    restaurants = [
        {'slug': slug, **restaurant}
        for slug, restaurant in RESTAURANTS.items()
    ]
    return render_template('home.html', restaurants=restaurants, app_name=APP_NAME)


@app.route('/r/<restaurant_slug>')
def restaurant_menu(restaurant_slug):
    return render_template('index.html', restaurant_slug=restaurant_slug, restaurant=get_restaurant(restaurant_slug), table=request.args.get('table', ''), error=request.args.get('error', ''))


@app.post('/order')
def create_order():
    restaurant_slug = request.form.get('restaurant_slug', 'roco-mamas')
    restaurant = get_restaurant(restaurant_slug)
    items = []
    for item in restaurant['menu']:
        try:
            quantity = int(request.form.get(f"qty_{item['id']}", 0))
        except (TypeError, ValueError):
            quantity = 0
        if quantity > 0:
            items.append({**item, 'quantity': quantity})

    if not items:
        return redirect(url_for('restaurant_menu', restaurant_slug=restaurant_slug, error='Choose at least one item first.'))

    service = request.form.get('service', 'table')
    customer = request.form.get('customer', '').strip()
    phone = request.form.get('phone', '').strip()
    table = request.form.get('table', '').strip()
    address = request.form.get('address', '').strip()
    if service == 'table' and not table:
        return redirect(url_for('restaurant_menu', restaurant_slug=restaurant_slug, error='Add your table number so we can serve you.'))
    if service == 'home' and not address:
        return redirect(url_for('restaurant_menu', restaurant_slug=restaurant_slug, error='Add your delivery address so we can bring your order.'))

    order = {
        'id': uuid4().hex[:6].upper(),
        'restaurant_slug': restaurant_slug,
        'restaurant_name': restaurant['name'],
        'currency': restaurant['currency'],
        'items': items,
        'total': sum(item['price'] * item['quantity'] for item in items),
        'service': service,
        'customer': customer or 'Guest',
        'phone': phone,
        'table': table,
        'address': address,
    }
    ORDERS.append(order)
    publish_event('order', order)
    return redirect(url_for('slip', order_id=order['id']))


@app.route('/slip/<order_id>')
def slip(order_id):
    order = next((order for order in ORDERS if order['id'] == order_id), None)
    if order is None:
        abort(404)
    restaurant = get_restaurant(order['restaurant_slug'])
    return render_template('order-slip.html', order_id=order_id, order=order, restaurant=restaurant, restaurant_slug=order['restaurant_slug'])


def send_telegram_notification(bill_request, restaurant):
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not bot_token or not chat_id:
        return 'not_configured'

    message = format_bill_notification(bill_request, restaurant)
    payload = urlencode({'chat_id': chat_id, 'text': message}).encode()
    endpoint = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    try:
        with urlopen(Request(endpoint, data=payload, method='POST'), timeout=10) as response:
            result = json.loads(response.read().decode())
        if not result.get('ok'):
            logger.error('Telegram bill notification failed: %s', result)
            return 'failed'
    except (HTTPError, URLError, TimeoutError, ValueError):
        logger.exception('Telegram bill notification failed')
        return 'failed'
    return 'sent'


def send_bill_notification(bill_request, restaurant):
    telegram_status = send_telegram_notification(bill_request, restaurant)
    if telegram_status != 'not_configured':
        return telegram_status

    twilio_config = {
        'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
        'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
        'from_phone': os.getenv('TWILIO_FROM_PHONE'),
        'to_phone': os.getenv('TWILIO_TO_PHONE') or restaurant['waiter_phone'],
    }
    if not all(twilio_config.values()):
        return 'not_configured'

    message = format_bill_notification(bill_request, restaurant)
    try:
        Client(twilio_config['account_sid'], twilio_config['auth_token']).messages.create(
            body=message,
            from_=twilio_config['from_phone'],
            to=twilio_config['to_phone'],
        )
    except Exception:
        logger.exception('Twilio bill notification failed')
        return 'failed'
    return 'sent'


def format_bill_notification(bill_request, restaurant):
    if bill_request['service'] == 'home':
        location = f"Home delivery - Deliver to: {bill_request['address']}"
    else:
        location = f"Table {bill_request['table']}"
    return (
        f"Bill requested at {restaurant['name']} - "
        f"{location}, {bill_request['customer']}"
    )


def create_bill_request(payload):
    restaurant_slug = str(payload.get('restaurant_slug', 'roco-mamas')).strip()
    restaurant = get_restaurant(restaurant_slug)
    order_id = str(payload.get('order_id', '')).strip()[:32]
    order = next((item for item in ORDERS if item['id'] == order_id and item['restaurant_slug'] == restaurant_slug), None)
    service = order['service'] if order else str(payload.get('service', 'table')).strip()
    bill_request = {
        'id': uuid4().hex[:6].upper(),
        'restaurant_slug': restaurant_slug,
        'restaurant_name': restaurant['name'],
        'order_id': order_id or 'Walk-in',
        'customer': order['customer'] if order else str(payload.get('customer', '')).strip()[:80] or 'Guest',
        'table': order['table'] if order else str(payload.get('table', '')).strip()[:32] or 'Not specified',
        'service': service if service in {'table', 'home'} else 'table',
        'address': order['address'] if order else str(payload.get('address', '')).strip()[:160] or 'Not specified',
    }
    publish_event('bill_request', bill_request)
    notification = send_bill_notification(bill_request, restaurant)
    return bill_request, notification, order


@app.post('/api/request-bill')
def api_request_bill():
    payload = request.get_json(silent=True) if request.is_json else request.form.to_dict()
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'Invalid request.'}, 400
    try:
        bill_request, notification, _ = create_bill_request(payload)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'Invalid bill request.'}, 400
    return {
        'ok': True,
        'bill_request_id': bill_request['id'],
        'notification': notification,
    }, 202


@app.post('/request-bill')
def request_bill():
    bill_request, _, order = create_bill_request(request.form)
    order_id = bill_request['order_id'] if order else ''
    return redirect(url_for('slip', order_id=order_id)) if order else redirect(url_for('restaurant_menu', restaurant_slug=bill_request['restaurant_slug']))


@app.route('/waiter')
@app.route('/waiter/<restaurant_slug>')
def waiter(restaurant_slug='roco-mamas'):
    restaurant = get_restaurant(restaurant_slug)
    orders = [order for order in ORDERS if order['restaurant_slug'] == restaurant_slug]
    return render_template('waiter.html', orders=orders, restaurant=restaurant, restaurant_slug=restaurant_slug)


@app.get('/api/orders/<restaurant_slug>/stream')
def order_stream(restaurant_slug):
    get_restaurant(restaurant_slug)
    last_event_id = request.headers.get('Last-Event-ID', '0')
    try:
        last_event_id = max(0, int(last_event_id))
    except ValueError:
        last_event_id = 0

    def events():
        nonlocal last_event_id
        matching_orders = [order for order in ORDERS if order['restaurant_slug'] == restaurant_slug]
        latest_event_id = EVENTS[-1]['id'] if EVENTS else 0
        last_event_id = min(last_event_id, latest_event_id)
        yield f'event: snapshot\nid: {latest_event_id}\ndata: {json.dumps(matching_orders)}\n\n'
        while True:
            new_events = [event for event in EVENTS if event['id'] > last_event_id and event['payload']['restaurant_slug'] == restaurant_slug]
            if new_events:
                for event in new_events:
                    yield f"event: {event['type']}\nid: {event['id']}\ndata: {json.dumps(event['payload'])}\n\n"
                    last_event_id = event['id']
            else:
                yield ': heartbeat\n\n'
            time.sleep(0.25)

    return Response(stream_with_context(events()), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })


class Table:
    """Represents a restaurant table and its current seating/order state."""

    def __init__(self, table_number: int, capacity: int, waiter: str = 'Unassigned'):
        self.table_number = table_number
        self.capacity = capacity
        self.waiter = waiter
        self.guests = []
        self.order = {}

    def add_guest(self, guest_name: str) -> None:
        if len(self.guests) >= self.capacity:
            raise ValueError(f'Table {self.table_number} is full.')
        if guest_name not in self.guests:
            self.guests.append(guest_name)

    def remove_guest(self, guest_name: str) -> None:
        if guest_name not in self.guests:
            raise ValueError(
                f"Guest '{guest_name}' is not seated at table {self.table_number}."
            )
        self.guests.remove(guest_name)

    def add_order_item(self, item_name: str, price: float, quantity: int = 1) -> None:
        if quantity <= 0:
            raise ValueError('Quantity must be greater than zero.')
        if item_name not in self.order:
            self.order[item_name] = {'price': price, 'quantity': 0}
        self.order[item_name]['price'] = price
        self.order[item_name]['quantity'] += quantity

    def clear(self) -> None:
        self.guests.clear()
        self.order.clear()

    def get_total(self) -> float:
        return sum(
            float(item['price']) * int(item['quantity'])
            for item in self.order.values()
        )


if __name__ == '__main__':
    app.run(debug=True)
