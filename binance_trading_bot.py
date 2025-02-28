import os
import logging
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')

# Set up Binance client
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def get_symbol_info(symbol):
    exchange_info = client.futures_exchange_info()
    symbol_info = next(item for item in exchange_info['symbols'] if item['symbol'] == symbol)
    return symbol_info

def round_step_size(quantity, step_size):
    return round(quantity - (quantity % step_size), 8)

def place_order(symbol, side, quantity, leverage):
    symbol_info = get_symbol_info(symbol)
    step_size = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', symbol_info['filters']))['stepSize'])
    quantity = round_step_size(quantity, step_size)

    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
            positionSide='BOTH'
        )
        return order
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise

def set_take_profit(symbol, side, quantity, price):
    symbol_info = get_symbol_info(symbol)
    tick_size = float(next(filter(lambda f: f['filterType'] == 'PRICE_FILTER', symbol_info['filters']))['tickSize'])
    price = round_step_size(price, tick_size)
    
    client.futures_create_order(
        symbol=symbol,
        side=side,
        type=ORDER_TYPE_TAKE_PROFIT_MARKET,
        quantity=quantity,
        stopPrice=price,
        positionSide='BOTH'
    )

def set_stop_loss(symbol, side, quantity, price):
    symbol_info = get_symbol_info(symbol)
    tick_size = float(next(filter(lambda f: f['filterType'] == 'PRICE_FILTER', symbol_info['filters']))['tickSize'])
    price = round_step_size(price, tick_size)

    client.futures_create_order(
        symbol=symbol,
        side=side,
        type=ORDER_TYPE_STOP_MARKET,
        quantity=quantity,
        stopPrice=price,
        positionSide='BOTH'
    )

def main():
    while True:
        symbol = input("Enter the token symbol (e.g., BTCUSDT): ").upper()
        try:
            leverage = 5
            total_amount_usdt = 10

            symbol_info = get_symbol_info(symbol)
            mark_price = float(client.futures_mark_price(symbol=symbol)['markPrice'])
            quantity = total_amount_usdt / mark_price

            print(f"Placing long and short orders for {symbol} with leverage {leverage}...")

            # Place long and short orders
            long_order = place_order(symbol, SIDE_BUY, quantity, leverage)
            short_order = place_order(symbol, SIDE_SELL, quantity, leverage)

            long_price = float(long_order['fills'][0]['price'])
            short_price = float(short_order['fills'][0]['price'])

            # Set take profit orders
            set_take_profit(symbol, SIDE_SELL, quantity, long_price * 1.10)
            set_take_profit(symbol, SIDE_BUY, quantity, short_price * 0.90)

            print(f"Long order placed at {long_price}, take profit at {long_price * 1.10}")
            print(f"Short order placed at {short_price}, take profit at {short_price * 0.90}")

            # Monitor positions and set stop loss if necessary
            while True:
                positions = client.futures_position_information(symbol=symbol)
                for position in positions:
                    if float(position['positionAmt']) != 0:
                        entry_price = float(position['entryPrice'])
                        mark_price = float(position['markPrice'])
                        if (position['positionSide'] == 'LONG' and mark_price >= entry_price * 1.10) or (position['positionSide'] == 'SHORT' and mark_price <= entry_price * 0.90):
                            remaining_position = position['positionSide']
                            remaining_quantity = abs(float(position['positionAmt']))
                            stop_loss_price = entry_price * 0.95 if remaining_position == 'LONG' else entry_price * 1.05
                            set_stop_loss(symbol, SIDE_SELL if remaining_position == 'LONG' else SIDE_BUY, remaining_quantity, stop_loss_price)
                            print(f"Take profit triggered. Setting stop loss at {stop_loss_price} for remaining {remaining_position} position.")
                            return
        except BinanceAPIException as e:
            print(f"Error: {e}")
            print("Please enter a valid token symbol.")
        except Exception as e:
            print(f"Unexpected error: {e}")
            break

if __name__ == '__main__':
    main()
