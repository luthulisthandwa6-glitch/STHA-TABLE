from uuid import uuid4
import json
import logging
import os
import time

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
    'galitos-marshalltown-howard-house': chain("Galito's Marshalltown Howard House", '', []),
    'mimmos-braamfontein': chain('Mimmos Braamfontein', '', []),
    'the-smokehouse-and-grill': chain('The Smokehouse and Grill', '', []),
    'lacasa-spit-shisanyama': chain('LaCasa Spit & Shisanyama', '', []),
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


def send_bill_notification(bill_request, restaurant):
    twilio_config = {
        'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
        'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
        'from_phone': os.getenv('TWILIO_FROM_PHONE'),
        'to_phone': os.getenv('TWILIO_TO_PHONE') or restaurant['waiter_phone'],
    }
    if not all(twilio_config.values()):
        return 'not_configured'

    message = (
        f"Bill requested at {restaurant['name']} - "
        f"Table {bill_request['table']}, {bill_request['customer']}"
    )
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


def create_bill_request(payload):
    restaurant_slug = str(payload.get('restaurant_slug', 'roco-mamas')).strip()
    restaurant = get_restaurant(restaurant_slug)
    order_id = str(payload.get('order_id', '')).strip()[:32]
    order = next((item for item in ORDERS if item['id'] == order_id and item['restaurant_slug'] == restaurant_slug), None)
    bill_request = {
        'id': uuid4().hex[:6].upper(),
        'restaurant_slug': restaurant_slug,
        'restaurant_name': restaurant['name'],
        'order_id': order_id or 'Walk-in',
        'customer': order['customer'] if order else str(payload.get('customer', '')).strip()[:80] or 'Guest',
        'table': order['table'] if order else str(payload.get('table', '')).strip()[:32] or 'Not specified',
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
