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

default_order_draft = {
    "customer_name": "",
    "size": sizes[0],
    "flavor": flavors[0],
    "mix_level": mix_levels[0],
    "toppings": [],
}
if "order_draft" not in st.session_state:
    st.session_state["order_draft"] = default_order_draft.copy()

widget_fields = {
    "pos_customer_name": "customer_name",
    "pos_size": "size",
    "pos_flavor": "flavor",
    "pos_mix_level": "mix_level",
}
if st.session_state.pop("reset_order_form", False):
    st.session_state["order_draft"] = default_order_draft.copy()
    for widget_key, draft_key in widget_fields.items():
        st.session_state[widget_key] = default_order_draft[draft_key]

if st.session_state.get("active_screen") == "toppings":
    st.title("Choose toppings")
    st.caption("Select or deselect each topping, then return to the order.")
    selected_toppings = st.session_state["order_draft"]["toppings"]
    st.caption(
        f"{len(selected_toppings)} selected. The first two are included; "
        f"additional toppings add ${max(0, len(selected_toppings) - 2):.2f}."
    )

    topping_columns = st.columns(3)
    for index, topping in enumerate(toppings):
        is_selected = topping in selected_toppings
        button_label = f"{'✓' if is_selected else '+'} {topping}"
        with topping_columns[index % len(topping_columns)]:
            if st.button(
                button_label,
                key=f"topping_choice_{index}",
                type="primary" if is_selected else "secondary",
                width="stretch",
            ):
                if is_selected:
                    selected_toppings.remove(topping)
                else:
                    selected_toppings.append(topping)
                st.rerun()

    if not toppings:
        st.info("No toppings are listed in the menu.")
    if st.button("Return to order", type="primary", width="stretch"):
        st.session_state["active_screen"] = "order"
        st.rerun()
    st.stop()

for widget_key, draft_key in widget_fields.items():
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state["order_draft"][draft_key]

st.title("Bober Custard POS")
st.caption("Create completed orders and review the order history.")
order_tab, history_tab = st.tabs(["New Order", "Order History"])

with order_tab:
    st.subheader("Build a custard order")
    with st.form("new_order_form", clear_on_submit=False):
        customer_name = st.text_input("Customer name", key="pos_customer_name")
        size_columns = st.columns(3)
        with size_columns[0]:
            selected_size = st.selectbox("Size", sizes, key="pos_size")
        with size_columns[1]:
            selected_flavor = st.selectbox("Flavor", flavors, key="pos_flavor")
        with size_columns[2]:
            selected_mix_level = st.selectbox(
                "Mix level", mix_levels, key="pos_mix_level"
            )
        topping_summary = ", ".join(st.session_state["order_draft"]["toppings"])
        st.caption(f"Toppings: {topping_summary or 'Plain'}")
        choose_toppings, submitted = st.columns(2)
        with choose_toppings:
            open_toppings = st.form_submit_button("Choose toppings", width="stretch")
        with submitted:
            submitted = st.form_submit_button(
                "Complete order", type="primary", width="stretch"
            )

    order_draft = st.session_state["order_draft"]
    order_draft.update(
        {
            "customer_name": customer_name,
            "size": selected_size,
            "flavor": selected_flavor,
            "mix_level": selected_mix_level,
        }
    )
    if open_toppings:
        st.session_state["active_screen"] = "toppings"
        st.rerun()

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
                        0, len(order_draft["toppings"]) - 2
                    )
                    order = {
                        "order_number": f"{order_number:02d}",
                        "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "customer_name": customer_name.strip(),
                        "size": selected_size,
                        "flavor": selected_flavor,
                        "mix_level": selected_mix_level,
                        "toppings": json.dumps(order_draft["toppings"]),
                        "total": f"{total:.2f}",
                        "status": "Complete",
                    }
                    try:
                        save_order(order)
                    except OSError as error:
                        st.error(f"Could not save the order: {error}")
                    else:
                        st.session_state["latest_order"] = order
                        st.session_state["reset_order_form"] = True
                        st.rerun()

    if "latest_order" in st.session_state:
        st.success("Order saved as complete.")
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
