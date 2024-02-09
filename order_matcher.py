from datetime import datetime
from dateutil.relativedelta import relativedelta


def convert_messages_to_orders(labeled_messages):
    out = []

    for idx, message in labeled_messages.items():
        if message["type"] not in ["SKIP"]:
            out.append({
                "index": int(idx),
                "timestamp": message['timestamp'],
                "direction": message['direction'],
                "type": message['type'],
                "risky": message['risky'],
                "ticker": message['ticker'],
                "fill": message['fill'],
                "expiry": message['expiry'],
                "strike": message['strike'],
                "matched": False
            })

    return out


def find_matching_entry(orders, closing_order):
    candidates = []

    for order in orders:
        if (
                # and order['matched'] is False
                order['direction'] == "IN" and
                order['ticker'] == closing_order['ticker'] and
                order['expiry'] == closing_order['expiry'] and
                order['strike'] == closing_order['strike'] and
                order['call_or_put'] == closing_order['call_or_put'] and
                order['index'] < closing_order['index']
        ):
            candidates.append(order)

    if len(candidates) == 0:
        return None

    best_order = max(candidates, key=lambda x: x['index'])

    return best_order


def compute_trades(orders):
    trades = []

    # match up orders
    for closing_order in orders:
        if closing_order["direction"] == "OUT":
            entry = find_matching_entry(orders, closing_order)

            if entry is None:
                print("No match found for ticker " + closing_order['ticker'])
                continue

            trades.append((entry, closing_order))

            entry['matched'] = True
            closing_order['matched'] = True

    return trades


def compute_profits(trades, sizing=1):
    balance = 10
    global_factor = 1
    out = []

    trades.sort(key=lambda t: t[1]['timestamp'], reverse=False)

    for entry, close in trades:
        profit = close['fill'] - entry['fill']
        factor = profit / entry['fill']
        global_factor *= (1 + factor)
        balance = balance + (sizing) * factor

        date_open = datetime.strptime(entry['timestamp'], "%Y/%m/%d")
        date_close = datetime.strptime(close['timestamp'], "%Y/%m/%d")

        duration = (date_close - date_open).days

        out.append({
            "index": close['index'],
            "opened_at": date_open,
            "closed_at": date_close,
            "ticker": entry['ticker'],
            "entry": entry['fill'],
            "close": close['fill'],
            "factor": factor,
            "profit": profit,
            "global_factor": global_factor,
            "balance": balance,
            "duration": duration,
            "message": entry['message']
        })

    return out


def close_abandoned_trades(orders, trades):
    unclosed_trade_count = 0
    last_index = orders[len(orders) - 1]['index']

    for open_order in orders:
        if not open_order['matched']:
            # print(f'unclosed order: {p["ticker"]} {p["expiry"]} {p["strike"]}')
            last_index += 1
            unclosed_trade_count += 1

            date_obj = datetime.strptime(open_order['timestamp'], "%Y/%m/%d")
            new_date_obj = date_obj + relativedelta(days=45)

            close = {
                "index": last_index,
                "timestamp": new_date_obj.strftime("%Y/%m/%d"),  # TODO: fill in years for each expiry and close at expiry
                "direction": "OUT",
                "ticker": open_order['ticker'],
                "expiry": open_order['expiry'],
                "strike": open_order['strike'],
                "fill": 0.5 * open_order['fill'],
                "type": 'SWING',
                "notes": 'unclosed order',
                "matched": True,
                "message": 'fake entry'
            }

            trades.append((open_order, close))

    return unclosed_trade_count
