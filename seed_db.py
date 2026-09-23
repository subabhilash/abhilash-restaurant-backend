"""
Database initialization and test data seeding script.
"""
from datetime import datetime, timezone, timedelta
from app.database import engine, Base, SessionLocal
import app.models  # noqa: F401
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.subscription import Subscription
from app.models.menu import Category, MenuItem
from app.models.order import RestaurantTable, Order, OrderItem
from app.models.kitchen import KitchenStation, KitchenTicket
from app.models.activity import ActivityLog
from app.services.auth_service import hash_password


def init_and_seed():
    print("1. Creating all database tables if they do not exist...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created successfully!")

    db = SessionLocal()
    try:
        # Check if already seeded
        existing_superadmin = db.query(User).filter_by(email="superadmin@restaurant.com").first()
        if existing_superadmin:
            print("[INFO] Database already contains seed data. Updating / skipping...")
            return

        print("2. Seeding Super Admin...")
        super_admin = User(
            email="superadmin@restaurant.com",
            password_hash=hash_password("Admin@123"),
            full_name="Super Administrator",
            phone="+919876543210",
            role="super_admin",
            restaurant_id=None,
            is_active=True,
        )
        db.add(super_admin)
        db.flush()

        print("3. Seeding Sample Restaurant (Spice Garden Bistro)...")
        restaurant = Restaurant(
            name="Spice Garden Bistro",
            slug="spice-garden",
            owner_id=None,  # updated after owner created
            logo="",
            description="Authentic Indian Cuisine & Multi-Cuisine Fine Dining experience.",
            phone="+919876543211",
            email="contact@spicegarden.com",
            address="Plot 42, Food Street, Hitech City",
            city="Hyderabad",
            state="Telangana",
            country="IN",
            timezone="Asia/Kolkata",
            currency="INR",
            tax_rate=5.00,
            service_charge_rate=2.50,
            allow_online_ordering=True,
            auto_accept_orders=False,
            kitchen_display_enabled=True,
            subscription_plan="professional",
            subscription_status="active",
            is_active=True,
        )
        db.add(restaurant)
        db.flush()

        print("4. Seeding Restaurant Staff & Owner...")
        owner = User(
            email="owner@spicegarden.com",
            password_hash=hash_password("Owner@123"),
            full_name="Rajesh Sharma",
            phone="+919876543212",
            role="admin",
            restaurant_id=restaurant.id,
            is_active=True,
        )
        chef = User(
            email="chef@spicegarden.com",
            password_hash=hash_password("Chef@123"),
            full_name="Vikram Verma (Head Chef)",
            phone="+919876543213",
            role="kitchen",
            restaurant_id=restaurant.id,
            is_active=True,
        )
        waiter = User(
            email="waiter@spicegarden.com",
            password_hash=hash_password("Waiter@123"),
            full_name="Rahul Singh (Lead Server)",
            phone="+919876543214",
            role="waiter",
            restaurant_id=restaurant.id,
            is_active=True,
        )
        db.add_all([owner, chef, waiter])
        db.flush()

        restaurant.owner_id = owner.id
        db.flush()

        print("5. Seeding Subscription...")
        sub = Subscription(
            restaurant_id=restaurant.id,
            plan="professional",
            status="active",
            starts_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            created_by=super_admin.id,
            notes="Annual Professional Plan active",
        )
        db.add(sub)

        print("6. Seeding Kitchen Stations...")
        station_grill = KitchenStation(
            restaurant_id=restaurant.id,
            name="Tandoor & Grill",
            display_color="#EF4444",
            is_active=True,
            display_order=1,
        )
        station_curry = KitchenStation(
            restaurant_id=restaurant.id,
            name="Curries & Mains",
            display_color="#F59E0B",
            is_active=True,
            display_order=2,
        )
        station_starters = KitchenStation(
            restaurant_id=restaurant.id,
            name="Starters & Appetizers",
            display_color="#10B981",
            is_active=True,
            display_order=3,
        )
        station_beverages = KitchenStation(
            restaurant_id=restaurant.id,
            name="Beverages & Bar",
            display_color="#3B82F6",
            is_active=True,
            display_order=4,
        )
        db.add_all([station_grill, station_curry, station_starters, station_beverages])
        db.flush()

        print("7. Seeding Tables...")
        tables = [
            RestaurantTable(
                restaurant_id=restaurant.id,
                table_number="T-01",
                capacity=4,
                qr_token="qr_table_01_spice_garden",
                location_description="Main Dining Hall - Center",
                status="occupied",
                occupied_since=datetime.now(timezone.utc) - timedelta(minutes=25),
            ),
            RestaurantTable(
                restaurant_id=restaurant.id,
                table_number="T-02",
                capacity=2,
                qr_token="qr_table_02_spice_garden",
                location_description="Window Side",
                status="available",
            ),
            RestaurantTable(
                restaurant_id=restaurant.id,
                table_number="T-03",
                capacity=6,
                qr_token="qr_table_03_spice_garden",
                location_description="Family Dining Zone",
                status="available",
            ),
            RestaurantTable(
                restaurant_id=restaurant.id,
                table_number="T-04",
                capacity=4,
                qr_token="qr_table_04_spice_garden",
                location_description="Outdoor Patio",
                status="reserved",
            ),
            RestaurantTable(
                restaurant_id=restaurant.id,
                table_number="T-05",
                capacity=8,
                qr_token="qr_table_05_spice_garden",
                location_description="VIP Lounge",
                status="occupied",
                occupied_since=datetime.now(timezone.utc) - timedelta(minutes=45),
            ),
        ]
        db.add_all(tables)
        db.flush()

        print("8. Seeding Categories & Menu Items...")
        cat_starters = Category(
            restaurant_id=restaurant.id,
            name="Starters & Appetizers",
            description="Crispy and delicious appetizers to begin your meal",
            display_order=1,
            is_active=True,
        )
        cat_tandoor = Category(
            restaurant_id=restaurant.id,
            name="Tandoori Kebabs & Grills",
            description="Clay oven charred fresh tandoori specialties",
            display_order=2,
            is_active=True,
        )
        cat_mains = Category(
            restaurant_id=restaurant.id,
            name="Main Course Curries",
            description="Rich slow-cooked signature gravies and curries",
            display_order=3,
            is_active=True,
        )
        cat_breads = Category(
            restaurant_id=restaurant.id,
            name="Breads & Biryani",
            description="Fresh tandoori rotis, naans, and aromatic biryanis",
            display_order=4,
            is_active=True,
        )
        cat_drinks = Category(
            restaurant_id=restaurant.id,
            name="Beverages & Mocktails",
            description="Chilled drinks, mocktails, and traditional lassi",
            display_order=5,
            is_active=True,
        )
        db.add_all([cat_starters, cat_tandoor, cat_mains, cat_breads, cat_drinks])
        db.flush()

        # Items
        items = [
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_starters.id,
                name="Crispy Chilli Baby Corn",
                description="Tender baby corn tossed with bell peppers and tangy Indo-Chinese chilli glaze.",
                price=240.00,
                display_order=1,
                is_available=True,
                preparation_time_minutes=12,
                calories=320,
                allergens=["Gluten", "Soy"],
                dietary_tags=["Vegetarian", "Chef Special"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_starters.id,
                name="Chicken 65",
                description="Crispy spiced chicken morsels tempered with curry leaves, mustard seeds and green chillies.",
                price=290.00,
                display_order=2,
                is_available=True,
                preparation_time_minutes=15,
                calories=420,
                allergens=["Dairy"],
                dietary_tags=["Non-Veg", "Spicy"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_tandoor.id,
                name="Paneer Tikka Angara",
                description="Cottage cheese marinated in Kashmiri red chilli and smoked in traditional clay oven.",
                price=280.00,
                display_order=1,
                is_available=True,
                preparation_time_minutes=15,
                calories=380,
                allergens=["Dairy"],
                dietary_tags=["Vegetarian", "Gluten-Free"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_tandoor.id,
                name="Murgh Malai Tikka",
                description="Succulent chicken tenders marinated with cream, cheese, cardamom, and gentle spices.",
                price=360.00,
                display_order=2,
                is_available=True,
                preparation_time_minutes=18,
                calories=490,
                allergens=["Dairy", "Nuts"],
                dietary_tags=["Non-Veg", "Bestseller"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_mains.id,
                name="Butter Chicken (Murgh Makhani)",
                description="Classic roasted chicken in velvety tomato, cream and aromatic fenugreek sauce.",
                price=390.00,
                display_order=1,
                is_available=True,
                preparation_time_minutes=20,
                calories=580,
                allergens=["Dairy", "Cashew"],
                dietary_tags=["Non-Veg", "Bestseller"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_mains.id,
                name="Paneer Butter Masala",
                description="Rich cottage cheese cubes cooked in spiced tomato butter gravy.",
                price=320.00,
                display_order=2,
                is_available=True,
                preparation_time_minutes=15,
                calories=480,
                allergens=["Dairy", "Cashew"],
                dietary_tags=["Vegetarian"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_mains.id,
                name="Dal Makhani Imperial",
                description="Slow-simmered whole black lentils, butter, and rich cream for 24 hours.",
                price=260.00,
                display_order=3,
                is_available=True,
                preparation_time_minutes=10,
                calories=410,
                allergens=["Dairy"],
                dietary_tags=["Vegetarian", "Bestseller"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_breads.id,
                name="Butter Garlic Naan",
                description="Layered artisan leavened flatbread baked with chopped garlic and coriander.",
                price=65.00,
                display_order=1,
                is_available=True,
                preparation_time_minutes=8,
                calories=210,
                allergens=["Gluten", "Dairy"],
                dietary_tags=["Vegetarian"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_breads.id,
                name="Hyderabadi Dum Biryani",
                description="Fragrant basmati rice layered with spiced marinated chicken and saffron dum cooked.",
                price=380.00,
                display_order=2,
                is_available=True,
                preparation_time_minutes=20,
                calories=650,
                allergens=["Dairy"],
                dietary_tags=["Non-Veg", "Signature"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_drinks.id,
                name="Mango Kesari Lassi",
                description="Thick artisanal yogurt whipped with Alphonso mango pulp and saffron.",
                price=130.00,
                display_order=1,
                is_available=True,
                preparation_time_minutes=5,
                calories=240,
                allergens=["Dairy"],
                dietary_tags=["Vegetarian", "Refreshing"],
            ),
            MenuItem(
                restaurant_id=restaurant.id,
                category_id=cat_drinks.id,
                name="Mint Mojito Mocktail",
                description="Fresh garden mint, crushed lime, and sparkling soda over crushed ice.",
                price=140.00,
                display_order=2,
                is_available=True,
                preparation_time_minutes=5,
                calories=110,
                allergens=[],
                dietary_tags=["Vegetarian", "Vegan"],
            ),
        ]
        db.add_all(items)
        db.flush()

        print("9. Seeding Active and Completed Orders...")
        # Order 1: In Preparing (Table 1)
        subtotal1 = 280.00 * 2 + 390.00 + 65.00 * 4
        tax1 = round(subtotal1 * 0.05, 2)
        sc1 = round(subtotal1 * 0.025, 2)
        total1 = subtotal1 + tax1 + sc1

        order1 = Order(
            restaurant_id=restaurant.id,
            table_id=tables[0].id,
            order_number="ORD-1001",
            customer_name="Amit Patel",
            customer_phone="+919811223344",
            order_type="dine_in",
            status="preparing",
            payment_status="unpaid",
            special_instructions="Make the paneer tikka extra crispy please.",
            subtotal=subtotal1,
            tax_amount=tax1,
            service_charge=sc1,
            discount_amount=0.00,
            total_amount=total1,
            created_by=waiter.id,
            confirmed_at=datetime.now(timezone.utc) - timedelta(minutes=15),
            preparing_at=datetime.now(timezone.utc) - timedelta(minutes=12),
        )
        db.add(order1)
        db.flush()

        order1_items = [
            OrderItem(
                order_id=order1.id,
                menu_item_id=items[2].id,
                menu_item_name=items[2].name,
                quantity=2,
                unit_price=items[2].price,
                total_price=items[2].price * 2,
                special_instructions="Extra mint chutney",
            ),
            OrderItem(
                order_id=order1.id,
                menu_item_id=items[4].id,
                menu_item_name=items[4].name,
                quantity=1,
                unit_price=items[4].price,
                total_price=items[4].price,
                special_instructions="Medium spice",
            ),
            OrderItem(
                order_id=order1.id,
                menu_item_id=items[7].id,
                menu_item_name=items[7].name,
                quantity=4,
                unit_price=items[7].price,
                total_price=items[7].price * 4,
            ),
        ]
        db.add_all(order1_items)

        ticket1 = KitchenTicket(
            restaurant_id=restaurant.id,
            order_id=order1.id,
            station_id=station_grill.id,
            assigned_to=chef.id,
            status="in_progress",
            priority="normal",
            notes="Extra crispy Paneer Tikka",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=12),
        )
        db.add(ticket1)

        # Order 2: Ready for serving (Table 5)
        subtotal2 = 360.00 + 260.00 + 380.00 + 130.00 * 2
        tax2 = round(subtotal2 * 0.05, 2)
        sc2 = round(subtotal2 * 0.025, 2)
        total2 = subtotal2 + tax2 + sc2

        order2 = Order(
            restaurant_id=restaurant.id,
            table_id=tables[4].id,
            order_number="ORD-1002",
            customer_name="Pooja Mehta",
            customer_phone="+919822334455",
            order_type="dine_in",
            status="ready",
            payment_status="unpaid",
            special_instructions="Less spicy biryani",
            subtotal=subtotal2,
            tax_amount=tax2,
            service_charge=sc2,
            discount_amount=0.00,
            total_amount=total2,
            created_by=waiter.id,
            confirmed_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            preparing_at=datetime.now(timezone.utc) - timedelta(minutes=25),
            ready_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        db.add(order2)
        db.flush()

        order2_items = [
            OrderItem(
                order_id=order2.id,
                menu_item_id=items[3].id,
                menu_item_name=items[3].name,
                quantity=1,
                unit_price=items[3].price,
                total_price=items[3].price,
            ),
            OrderItem(
                order_id=order2.id,
                menu_item_id=items[6].id,
                menu_item_name=items[6].name,
                quantity=1,
                unit_price=items[6].price,
                total_price=items[6].price,
            ),
            OrderItem(
                order_id=order2.id,
                menu_item_id=items[8].id,
                menu_item_name=items[8].name,
                quantity=1,
                unit_price=items[8].price,
                total_price=items[8].price,
            ),
            OrderItem(
                order_id=order2.id,
                menu_item_id=items[9].id,
                menu_item_name=items[9].name,
                quantity=2,
                unit_price=items[9].price,
                total_price=items[9].price * 2,
            ),
        ]
        db.add_all(order2_items)

        ticket2 = KitchenTicket(
            restaurant_id=restaurant.id,
            order_id=order2.id,
            station_id=station_curry.id,
            assigned_to=chef.id,
            status="ready",
            priority="high",
            notes="VIP table order",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=25),
            completed_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        db.add(ticket2)

        # Order 3: Completed & Paid
        subtotal3 = 240.00 + 320.00 + 65.00 * 2 + 140.00
        tax3 = round(subtotal3 * 0.05, 2)
        sc3 = round(subtotal3 * 0.025, 2)
        total3 = subtotal3 + tax3 + sc3

        order3 = Order(
            restaurant_id=restaurant.id,
            table_id=tables[1].id,
            order_number="ORD-1000",
            customer_name="Karan Kapoor",
            customer_phone="+919833445566",
            order_type="dine_in",
            status="completed",
            payment_status="paid",
            subtotal=subtotal3,
            tax_amount=tax3,
            service_charge=sc3,
            discount_amount=0.00,
            total_amount=total3,
            created_by=waiter.id,
            confirmed_at=datetime.now(timezone.utc) - timedelta(minutes=70),
            preparing_at=datetime.now(timezone.utc) - timedelta(minutes=65),
            ready_at=datetime.now(timezone.utc) - timedelta(minutes=45),
            served_at=datetime.now(timezone.utc) - timedelta(minutes=40),
            completed_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db.add(order3)
        db.flush()

        order3_items = [
            OrderItem(
                order_id=order3.id,
                menu_item_id=items[0].id,
                menu_item_name=items[0].name,
                quantity=1,
                unit_price=items[0].price,
                total_price=items[0].price,
            ),
            OrderItem(
                order_id=order3.id,
                menu_item_id=items[5].id,
                menu_item_name=items[5].name,
                quantity=1,
                unit_price=items[5].price,
                total_price=items[5].price,
            ),
            OrderItem(
                order_id=order3.id,
                menu_item_id=items[7].id,
                menu_item_name=items[7].name,
                quantity=2,
                unit_price=items[7].price,
                total_price=items[7].price * 2,
            ),
            OrderItem(
                order_id=order3.id,
                menu_item_id=items[10].id,
                menu_item_name=items[10].name,
                quantity=1,
                unit_price=items[10].price,
                total_price=items[10].price,
            ),
        ]
        db.add_all(order3_items)

        # 10. Activity log
        log = ActivityLog(
            user_id=owner.id,
            restaurant_id=restaurant.id,
            action="restaurant.initialized",
            resource_type="restaurant",
            resource_id=restaurant.id,
            log_data={"message": "Spice Garden Bistro initialized with demo data"},
        )
        db.add(log)

        db.commit()
        print("[OK] Successfully seeded demo data!")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error during seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_and_seed()
