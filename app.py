import csv
import json
import random
from datetime import datetime
from pathlib import Path

import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parent
MENU_FILE = PROJECT_DIR / "menu.txt"
ORDERS_FILE = PROJECT_DIR / "orders.csv"
ORDER_FIELDS = [
    "order_number",
    "completed_at",
    "customer_name",
    "size",
    "flavor",
    "mix_level",
    "toppings",
    "total",
    "status",
]


def read_menu():
    menu = {}
    try:
        lines = MENU_FILE.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        st.error(f"Could not read the menu file: {error}")
        st.stop()

    for line in lines:
        if ":" not in line:
            continue
        category, values = line.split(":", 1)
        menu[category.strip().upper()] = [
            value.strip() for value in values.split(",") if value.strip()
        ]
    return menu


def read_orders():
    if not ORDERS_FILE.exists():
        return []
    with ORDERS_FILE.open("r", newline="", encoding="utf-8") as order_file:
        return list(csv.DictReader(order_file))


def save_order(order):
    write_header = not ORDERS_FILE.exists() or ORDERS_FILE.stat().st_size == 0
    with ORDERS_FILE.open("a", newline="", encoding="utf-8") as order_file:
        writer = csv.DictWriter(order_file, fieldnames=ORDER_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(order)


def toppings_for_display(order):
    try:
        toppings = json.loads(order.get("toppings", "[]"))
        return toppings if isinstance(toppings, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def show_ticket(order):
    order_number = int(order["order_number"])
    toppings = toppings_for_display(order)

    with st.container(border=True):
        st.markdown(f"### Completed order #{order_number:02d}")
        st.caption(order["completed_at"])
        st.write(f"**Customer:** {order['customer_name']}")

        details = st.columns(3)
        details[0].write(f"**Size**\n\n{order['size']}")
        details[1].write(f"**Flavor**\n\n{order['flavor']}")
        details[2].write(f"**Mix level**\n\n{order['mix_level']}")

        st.write("**Toppings**")
        st.write(", ".join(toppings) if toppings else "Plain")
        st.metric("Total", f"${float(order['total']):.2f}")


st.set_page_config(page_title="Bober Custard POS", page_icon="🍦", layout="wide")
st.title("Bober Custard POS")
st.caption("Create completed orders and review the order history.")

menu = read_menu()
sizes = menu.get("SIZES", [])
prices = menu.get("PRICE", [])
flavors = menu.get("FLAVORS", [])
mix_levels = menu.get("MIXED", [])
toppings = [item for item in menu.get("TOPPINGS", []) if item.casefold() != "plain"]

if not sizes or len(sizes) != len(prices):
    st.error("The menu must have a matching price for every size.")
    st.stop()
if not flavors or not mix_levels:
    st.error("The menu must include at least one flavor and mix level.")
    st.stop()

try:
    prices_by_size = {size: float(price) for size, price in zip(sizes, prices)}
except ValueError:
    st.error("Menu prices must be numbers.")
    st.stop()

order_tab, history_tab = st.tabs(["New Order", "Order History"])

with order_tab:
    st.subheader("Build a custard order")
    with st.form("new_order_form", clear_on_submit=True):
        customer_name = st.text_input("Customer name")
        size_columns = st.columns(3)
        with size_columns[0]:
            selected_size = st.selectbox("Size", sizes)
        with size_columns[1]:
            selected_flavor = st.selectbox("Flavor", flavors)
        with size_columns[2]:
            selected_mix_level = st.selectbox("Mix level", mix_levels)
        selected_toppings = st.multiselect("Toppings", toppings)
        st.caption(
            "The first two toppings are included. Each additional topping is $1."
        )
        submitted = st.form_submit_button(
            "Complete order", type="primary", width="stretch"
        )

    if submitted:
        if not customer_name.strip():
            st.error("Enter a customer name to complete the order.")
        else:
            try:
                saved_orders = read_orders()
            except OSError as error:
                st.error(f"Could not read saved orders: {error}")
                saved_orders = None

            if saved_orders is not None:
                used_numbers = set()
                for saved_order in saved_orders:
                    try:
                        used_numbers.add(int(saved_order["order_number"]))
                    except (KeyError, TypeError, ValueError):
                        continue

                available_numbers = [
                    number for number in range(1, 100) if number not in used_numbers
                ]
                if not available_numbers:
                    st.error("All order numbers from 1 to 99 are in use.")
                else:
                    order_number = random.choice(available_numbers)
                    total = prices_by_size[selected_size] + max(
                        0, len(selected_toppings) - 2
                    )
                    order = {
                        "order_number": f"{order_number:02d}",
                        "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "customer_name": customer_name.strip(),
                        "size": selected_size,
                        "flavor": selected_flavor,
                        "mix_level": selected_mix_level,
                        "toppings": json.dumps(selected_toppings),
                        "total": f"{total:.2f}",
                        "status": "Complete",
                    }
                    try:
                        save_order(order)
                    except OSError as error:
                        st.error(f"Could not save the order: {error}")
                    else:
                        st.session_state["latest_order"] = order
                        st.success("Order saved as complete.")

    if "latest_order" in st.session_state:
        show_ticket(st.session_state["latest_order"])

with history_tab:
    st.subheader("Completed orders")
    try:
        orders = read_orders()
    except OSError as error:
        st.error(f"Could not read saved orders: {error}")
        orders = []

    if not orders:
        st.info("Completed orders will appear here.")
    else:
        filter_columns = st.columns(2)
        with filter_columns[0]:
            name_filter = st.text_input("Filter by customer name")
        with filter_columns[1]:
            number_filter = st.text_input("Filter by order number", max_chars=2)

        number_query = number_filter.strip()
        valid_number_query = not number_query or number_query.isdigit()
        filtered_orders = []
        for order in reversed(orders):
            name_matches = (
                name_filter.casefold() in order.get("customer_name", "").casefold()
            )
            try:
                number_matches = not number_query or (
                    valid_number_query
                    and int(order.get("order_number", "-1")) == int(number_query)
                )
            except ValueError:
                number_matches = False
            if name_matches and number_matches:
                filtered_orders.append(order)

        if not valid_number_query:
            st.caption("Enter a number from 1 to 99 to filter by order number.")
        elif not filtered_orders:
            st.info("No completed orders match those filters.")
        else:
            table_rows = []
            for order in filtered_orders:
                try:
                    formatted_number = f"#{int(order['order_number']):02d}"
                    formatted_total = f"${float(order['total']):.2f}"
                except (KeyError, TypeError, ValueError):
                    formatted_number = order.get("order_number", "")
                    formatted_total = order.get("total", "")
                table_rows.append(
                    {
                        "Order #": formatted_number,
                        "Completed": order.get("completed_at", ""),
                        "Customer": order.get("customer_name", ""),
                        "Size": order.get("size", ""),
                        "Flavor": order.get("flavor", ""),
                        "Mix level": order.get("mix_level", ""),
                        "Toppings": ", ".join(toppings_for_display(order)) or "Plain",
                        "Total": formatted_total,
                    }
                )
            st.dataframe(table_rows, width="stretch", hide_index=True)

            selected_order_number = st.selectbox(
                "Review full order ticket",
                [order["order_number"] for order in filtered_orders],
                format_func=lambda number: f"Order #{int(number):02d}",
            )
            selected_order = next(
                order
                for order in filtered_orders
                if order["order_number"] == selected_order_number
            )
            show_ticket(selected_order)
