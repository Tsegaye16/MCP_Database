from sqlalchemy.orm import Session
from database import get_db, Base, engine, SessionLocal
from models import User, Product, Order, OrderItem

def seed_data(db: Session):
    # Ensure clean slate (idempotent seeding)
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(Product).delete()
    db.query(User).delete()
    db.commit()

    # Seed users
    users = [
        User(name="john doe", email="john.doe@example.com", hobby="Photography", job="Software Engineer", age=29),
        User(name="jane smith", email="jane.smith@example.com", hobby="Painting", job="Graphic Designer", age=34),
        User(name="alice brown", email="alice.brown@example.com", hobby="Hiking", job="Data Scientist", age=27),
        User(name="bob johnson", email="bob.johnson@example.com", hobby="Cycling", job="Marketing Manager", age=41),
        User(name="carol lee", email="carol.lee@example.com", hobby="Cooking", job="Teacher", age=38),
    ]
    db.add_all(users)
    db.commit()  # commit to persist and assign primary keys

    # Seed products
    products = [
        Product(name="Wireless Mouse", category="Electronics", price=24.99, stock=120),
        Product(name="Mechanical Keyboard", category="Electronics", price=79.99, stock=85),
        Product(name="Noise Cancelling Headphones", category="Electronics", price=129.99, stock=60),
        Product(name="Running Shoes", category="Apparel", price=59.99, stock=150),
        Product(name="Water Bottle", category="Outdoors", price=14.99, stock=200),
    ]
    db.add_all(products)
    db.commit()

    # Create a few orders with items (use relationships to avoid FK nulls)
    order1 = Order(user=users[0], status="completed")
    order2 = Order(user=users[1], status="shipped")
    order3 = Order(user=users[2], status="processing")
    db.add_all([order1, order2, order3])
    db.commit()

    items = [
        OrderItem(order=order1, product=products[0], quantity=2, unit_price=products[0].price),
        OrderItem(order=order1, product=products[4], quantity=1, unit_price=products[4].price),
        OrderItem(order=order2, product=products[1], quantity=1, unit_price=products[1].price),
        OrderItem(order=order2, product=products[3], quantity=1, unit_price=products[3].price),
        OrderItem(order=order3, product=products[2], quantity=1, unit_price=products[2].price),
    ]
    db.add_all(items)

    # Compute totals
    for order in [order1, order2, order3]:
        total = sum(item.quantity * item.unit_price for item in order.items)
        order.total_amount = total

    db.commit()

if __name__ == "__main__":
    # Ensure tables are created before seeding
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()