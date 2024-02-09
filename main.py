import gradio as gr
import pandas as pd
import re

from order_matcher import compute_trades, convert_messages_to_orders
from parsing import extract_in_out, extract_type, extract_ticker, extract_expiry, extract_strike, extract_fill
from util import trim_message, load_strings_from_json, load_state_file, save_state_file

STATE_FILE = 'data/state.json'
messages = load_strings_from_json('data/messages.json')

labeled_messages = {}
open_orders = []

users = {
    "user": {
        "index": 0,
    },
    "user2": {
        "index": 1000
    }
}


def load_ui(user_id):
    load_server_state()
    idx = users[user_id]["index"] if user_id in users else 0

    return load_message(idx + 1, user_id)


def load_message(idx, user_id):
    if idx < len(messages):
        next_string = trim_message(messages[idx]["content"])
    else:
        raise KeyError("No message")

    if user_id not in users:
        print("Created new user")
        users[user_id] = {
            "index": idx
        }

    # parsing logic
    entities = []

    next_in_out = extract_in_out(next_string, entities)
    next_type = extract_type(next_string, entities)
    next_ticker = extract_ticker(next_string, entities)
    next_expiry = extract_expiry(next_string, entities)
    next_strike = extract_strike(next_string, entities)
    next_price = extract_fill(next_string, entities)
    next_risky = re.search(r'\b(RISKY)\b', next_string.upper()) is not None

    global_orders = convert_messages_to_orders(labeled_messages)
    trades = compute_trades(global_orders)

    wins = len([trade for trade in trades if trade[5] > 0])
    loses = len([trade for trade in trades if trade[5] < 0])
    stat = f"trades {len(trades)} \nwins {wins} \nloses {loses}"

    # already labeled message
    if f"{idx}" in labeled_messages:
        next_ticker = labeled_messages[f"{idx}"]["ticker"]
        next_price = labeled_messages[f"{idx}"]["fill"]
        next_type = labeled_messages[f"{idx}"]["type"]

    orders_df = pd.DataFrame(global_orders, columns=["index", "timestamp", "type", "ticker", "fill", "matched"])
    orders_df['timestamp'] = pd.to_datetime(orders_df['timestamp'])
    orders_df['fill'] = orders_df['fill'].astype(float)
    orders_df['matched'] = orders_df['matched'].astype(bool)

    return {
        message_text: {"text": next_string, "entities": entities},
        msg_meta: f"{messages[idx]['timestamp'][:10]}",
        raw_text: messages[idx]["content"],
        index_in: idx,
        in_out_ui: next_in_out,
        ticker_in: next_ticker,
        price_in: next_price,
        expiry_in: next_expiry,
        strike_in: next_strike,
        category_opt: next_type,
        risky_chk: next_risky,
        orders_ui: orders_df,
        prog: len(labeled_messages),
        saved_chk: f"{idx}" in labeled_messages,
        stats: stat,
    }


def save_message(user_id, idx, direction, ticker, price, expiry, strike, cat, risky):
    print(f"{user_id} labeled #[{idx}] as {direction} {cat} {ticker}{strike}@{price} {'RISKY' if risky else ''}")

    labeled_messages[f"{idx}"] = {
        "user_id": user_id,
        "timestamp": messages[idx]["timestamp"],
        "direction": direction.upper(),
        "type": cat,
        "risky": risky,
        "ticker": ticker.lstrip('$').upper(),
        "fill": float(price.lstrip('$')) if price else 0,
        "expiry": expiry,
        "strike": strike.upper(),
    }

    if user_id not in users:
        print("Created new user")
        users[user_id] = {
            "open_orders": [],
            "index": idx
        }

    users[user_id]["index"] = idx
    save_server_state()

    return idx + 1  # maybe should be next unlabeled message?


def save_server_state():
    state = {
        "users": users,
        "labeled_messages": labeled_messages
    }

    save_state_file(state, STATE_FILE)


def load_server_state():
    global users
    global labeled_messages

    state = load_state_file(STATE_FILE)

    if state is not None:
        users = state["users"]
        labeled_messages = state["labeled_messages"]
    else:
        save_server_state()


def on_order_select(orders_opt):
    return orders_opt, "OUT"


def load_next(idx, user_id):
    return load_message(idx + 1 if idx < len(messages) - 2 else len(messages) - 1, user_id)


def load_prev(idx, user_id):
    return load_message(idx - 1 if idx > 0 else 0, user_id)


def view_message(a, evt: gr.SelectData):
    idx = a.iloc[evt.index[0], 0]

    return messages[idx]["content"]


def on_message_click(category_opt, ticker_ui, fill_ui, expiry_ui, evt: gr.SelectData):
    # cat selector
    if evt.selected and evt.value[1].startswith('type'):
        return [evt.value[0].upper(), ticker_ui, fill_ui, expiry_ui]

    # fill selector
    if evt.selected and evt.value[1].startswith('fill'):
        return [category_opt, ticker_ui, evt.value[0].lstrip('$'), expiry_ui]

    # expiry selector
    if evt.selected and evt.value[1].startswith('expiry'):
        return [category_opt, ticker_ui, fill_ui, evt.value[0]]

    # ticker selector
    if evt.value[0] is not None:
        if evt.selected and evt.value[1] is None or evt.value[1] == 'ticker' and bool(re.match(r'^\s*\$?[a-zA-Z :]+\s*$', evt.value[0])):
            clean_word = re.sub(r'[^a-zA-Z]', '', evt.value[0])
            ticker = f"${clean_word.upper()}"

            return [category_opt, ticker, fill_ui, expiry_ui]

    return [category_opt, ticker_ui, fill_ui, expiry_ui]


def update_orders(df):
    for index, row in df.iterrows():
        idx = f"{row['index']}"
        if idx in labeled_messages and labeled_messages[idx]['fill'] != row['fill']:
            print(f"updated message {idx} fill from {labeled_messages[idx]['fill']} to {row['fill']}")
            labeled_messages[idx]['fill'] = row['fill']

    save_server_state()


# User Interface
with (gr.Blocks(css="ui/style.css") as demo):
    gr.Markdown("## Message Annotation")

    with gr.Tab("Annotation") as tab_annotation:
        # message index
        with gr.Row():
            with gr.Column(scale=0, min_width=150):
                with gr.Group():
                    with gr.Row():
                        back_btn = gr.Button(value="", size="sm", icon="ui/left-arrow.png", elem_classes="", min_width=50)
                        forward_btn = gr.Button(value="", size="sm", icon="ui/right-arrow.png", elem_classes=["button_nav", "pull-right"], min_width=50)
                    index_in = gr.Number(value=0, minimum=0, maximum=len(messages), container=False, elem_id="no-spinners")
                    load_btn = gr.Button('Load', size="sm")

                saved_chk = gr.Checkbox(value=False, label="Saved", container=True)

                with gr.Group():
                    stats = gr.TextArea(show_label=True, label="stats", lines=6, max_lines=6, container=True, show_copy_button=True, interactive=False)

            # message text
            with gr.Column():
                with gr.Group():
                    with gr.Row():
                        msg_meta = gr.Textbox(value="date", show_label=False, lines=1, max_lines=1, container=False, scale=0, min_width=100)
                        raw_text = gr.TextArea("Raw message", lines=1, max_lines=1, show_label=False, container=False)
                    message_text = gr.HighlightedText(
                        combine_adjacent=True,
                        label="",
                        show_label=False,
                        show_legend=False,
                        elem_id="highlight-message",
                        interactive=False,
                        color_map={
                            "fill": "green",
                            "fill2": "green",
                            "ticker": "red",
                            "type": "yellow",
                            "in_out": "yellow",
                            "expiry": "blue",
                            "expiry2": "white"
                        }
                    )

                # inputs
                with gr.Row(elem_id="inputs"):
                    in_out_ui = gr.Radio(choices=["IN", "OUT", "SKIP"], show_label=False, scale=0, min_width=235, container=False)
                    with gr.Group(elem_id="fill_container"):
                        with gr.Row(variant="compact", equal_height=False):
                            ticker_in = gr.Textbox(label="ticker", scale=0, max_lines=1, text_align="right", min_width=100, container=True)
                            expiry_in = gr.Textbox(label="expires", scale=0, max_lines=1, text_align="right", min_width=100, container=True)
                            strike_in = gr.Textbox(label="strike", scale=0, max_lines=1, text_align="right", min_width=100, container=True)
                            price_in = gr.Textbox(label="fill", scale=0, max_lines=1, text_align="right", min_width=100, container=True)
                    category_opt = gr.Radio(choices=["SCALP", "SWING", "NONE"], label="type", scale=0, interactive=True, value="SCALP", min_width=290, container=False)
                    risky_chk = gr.Checkbox(label='Risky', container=False, scale=0)

                # save
                with gr.Row():
                    submit = gr.Button(value='Save', variant="primary", size="lg", elem_classes=["button_huge", "center"])

    # statistics
    with gr.Tab("Running Sum"):
        with gr.Row():
            message_view = gr.TextArea("View message", lines=1, max_lines=1, show_label=False, container=False)

        with gr.Accordion("Parsed Messages"):
            with gr.Column():
                with gr.Group():
                    orders_ui = gr.Dataframe(type="pandas", col_count=(6, "fixed"), height=900, interactive=True)
                    save_order_btn = gr.Button("Save")

    # server options
    with gr.Tab("Server"):
        user_name = gr.Dropdown(value="alex", choices=["alex", "ankita"], label="Username", min_width=150)
        prog = gr.Slider(label="index",minimum=0, maximum=len(messages))
        save_server = gr.Button('Save Server State')

    ui_outputs = [
        message_text,
        msg_meta,
        raw_text,
        index_in,
        in_out_ui,
        ticker_in,
        price_in,
        expiry_in,
        strike_in,
        category_opt,
        risky_chk,
        orders_ui,
        prog,
        saved_chk,
        stats
    ]

    submit.click(
        fn=save_message,
        inputs=[
            user_name,
            index_in,
            in_out_ui,
            ticker_in,
            price_in,
            expiry_in,
            strike_in,
            category_opt,
            risky_chk
        ],
        outputs=[index_in]
    ).then(
        fn=load_message,
        inputs=[index_in, user_name],
        outputs=ui_outputs)

    demo.load(fn=load_ui, inputs=[user_name], outputs=ui_outputs)
    load_btn.click(fn=load_message, inputs=[index_in, user_name], outputs=ui_outputs)

    forward_btn.click(load_next, [index_in, user_name], ui_outputs)
    back_btn.click(load_prev, [index_in, user_name], ui_outputs)

    save_server.click(save_server_state)

    orders_ui.select(view_message, inputs=orders_ui, outputs=message_view)
    orders_ui.input(update_orders, orders_ui, None)

    message_text.select(fn=on_message_click, inputs=[category_opt, ticker_in, price_in, expiry_in], outputs=[category_opt, ticker_in, price_in, expiry_in])

demo.queue()
demo.launch()
