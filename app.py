from uuid import uuid4

from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

# Edit this menu for each restaurant.
MENU = [
    {"name": "Chicken Curry", "price": 95, "cat": "Main"},
    {"name": "Beef Stew", "price": 110, "cat": "Main"},
    {"name": "Rice", "price": 30, "cat": "Sides"},
    {"name": "Salad", "price": 45, "cat": "Sides"},
    {"name": "Coke", "price": 20, "cat": "Drinks"},
    {"name": "Juice", "price": 25, "cat": "Drinks"},
]
ORDERS = []
RESTAURANT = {
    'name': 'Table & Thyme',
    'tagline': 'Good food, good mood',
    # Replace this with the restaurant's real waiter number.
    'waiter_phone': '+27000000000',
}


@app.route('/')
def menu():
    return render_template('index.html', menu=MENU, restaurant=RESTAURANT, table=request.args.get('table', ''), error=request.args.get('error', ''))


@app.post('/order')
def create_order():
    items = []
    for item in MENU:
        try:
            quantity = int(request.form.get(f"qty_{item['name']}", 0))
        except (TypeError, ValueError):
            quantity = 0
        if quantity > 0:
            items.append({**item, 'quantity': quantity})

    if not items:
        return redirect(url_for('menu', error='Choose at least one item first.'))

    service = request.form.get('service', 'table')
    customer = request.form.get('customer', '').strip()
    phone = request.form.get('phone', '').strip()
    table = request.form.get('table', '').strip()
    address = request.form.get('address', '').strip()
    if service == 'table' and not table:
        return redirect(url_for('menu', error='Add your table number so we can serve you.'))
    if service == 'home' and not address:
        return redirect(url_for('menu', error='Add your delivery address so we can bring your order.'))

    order = {
        'id': uuid4().hex[:6].upper(),
        'items': items,
        'total': sum(item['price'] * item['quantity'] for item in items),
        'service': service,
        'customer': customer or 'Guest',
        'phone': phone,
        'table': table,
        'address': address,
    }
    ORDERS.append(order)
    return redirect(url_for('slip', order_id=order['id']))


@app.route('/slip/<order_id>')
def slip(order_id):
    order = next((order for order in ORDERS if order['id'] == order_id), None)
    return render_template('order-slip.html', order_id=order_id, order=order, restaurant=RESTAURANT)


@app.route('/waiter')
def waiter():
    return render_template('waiter.html', orders=ORDERS)


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
