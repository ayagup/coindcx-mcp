import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .client import CoinDCXClient


load_dotenv()

# Configure logging to stderr so it doesn't interfere with MCP protocol
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

app = Server("coindcx-mcp")

# Log server startup
logger.info("CoinDCX MCP Server starting up...")

# Global client instance
client: Optional[CoinDCXClient] = None


def get_client() -> CoinDCXClient:
    """Get or create CoinDCX client instance."""
    global client
    if client is None:
        api_key = os.getenv("COINDCX_API_KEY", "")
        secret_key = os.getenv("COINDCX_SECRET_KEY", "")
        base_url = os.getenv("COINDCX_BASE_URL", "https://api.coindcx.com")
        
        if not api_key or not secret_key:
            raise ValueError("CoinDCX API credentials not found. Please set COINDCX_API_KEY and COINDCX_SECRET_KEY environment variables.")
        
        client = CoinDCXClient(api_key, secret_key, base_url)
    
    return client


@app.list_tools()
async def list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="get_ticker",
            description="Get ticker data for all markets on CoinDCX",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_markets",
            description="Get all available trading markets on CoinDCX",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_market_details",
            description="Get detailed information about a specific trading pair",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Trading pair symbol (e.g., 'B-BTC_USDT')"
                    }
                },
                "required": ["pair"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_trades",
            description="Get recent trades for a specific market",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Trading pair symbol (e.g., 'B-BTC_USDT')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of trades to retrieve (default: 30, max: 5000)",
                        "minimum": 1,
                        "maximum": 5000
                    }
                },
                "required": ["pair"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_order_book",
            description="Get order book (bids and asks) for a specific market",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Trading pair symbol (e.g., 'B-BTC_USDT')"
                    }
                },
                "required": ["pair"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_active_instruments",
            description="Get list of all active futures instruments on CoinDCX",
            inputSchema={
                "type": "object",
                "properties": {
                    "margin_currency": {
                        "type": "string",
                        "description": "Futures margin mode: 'USDT' (default) or 'INR'",
                        "enum": ["USDT", "INR"]
                    }
                },
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_instrument_details",
            description="Get detailed information about a specific futures instrument, including leverage limits, fees, price/quantity increments, funding frequency, and order types",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Futures instrument pair (e.g., 'B-BTC_USDT')"
                    },
                    "margin_currency": {
                        "type": "string",
                        "description": "Futures margin mode: 'USDT' (default) or 'INR'",
                        "enum": ["USDT", "INR"]
                    }
                },
                "required": ["pair"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_instrument_trades",
            description="Get real-time trade history for a specific futures instrument",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Futures instrument pair (e.g., 'B-BTC_USDT')"
                    }
                },
                "required": ["pair"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_instrument_orderbook",
            description="Get order book (bids and asks) for a specific futures instrument",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Futures instrument pair (e.g., 'B-BTC_USDT')"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Order book depth (default: 50)",
                        "enum": [10, 20, 50]
                    }
                },
                "required": ["pair"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_instrument_candlesticks",
            description="Get candlestick (OHLCV) data for a specific futures instrument",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Futures instrument pair (e.g., 'B-BTC_USDT')"
                    },
                    "resolution": {
                        "type": "string",
                        "description": "Candle resolution: '1' (1min), '5' (5min), '60' (1hour), '1D' (1day)",
                        "enum": ["1", "5", "60", "1D"]
                    },
                    "from_time": {
                        "type": "integer",
                        "description": "EPOCH start timestamp in seconds"
                    },
                    "to_time": {
                        "type": "integer",
                        "description": "EPOCH end timestamp in seconds"
                    }
                },
                "required": ["pair", "resolution", "from_time", "to_time"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_candles",
            description="Get candlestick/OHLCV data for a specific market. If start_time/end_time are not available or invalid, returns most recent candles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Trading pair symbol (e.g., 'BTCUSDT')"
                    },
                    "interval": {
                        "type": "string",
                        "description": "Candle interval (1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 1d, 3d, 1w, 1M)",
                        "enum": ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "1d", "3d", "1w", "1M"]
                    },
                    "start_time": {
                        "type": "integer",
                        "description": "Start timestamp in milliseconds (optional - if not provided or invalid, returns recent data)"
                    },
                    "end_time": {
                        "type": "integer",
                        "description": "End timestamp in milliseconds (optional - if not provided or invalid, returns recent data)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of candles to retrieve (default: 100, max: 1000)",
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "required": ["pair", "interval"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_balances",
            description="Get account balances for all assets",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_user_info",
            description="Get user account information",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="create_order",
            description="Create a new buy or sell order",
            inputSchema={
                "type": "object",
                "properties": {
                    "side": {
                        "type": "string",
                        "description": "Order side",
                        "enum": ["buy", "sell"]
                    },
                    "order_type": {
                        "type": "string",
                        "description": "Order type",
                        "enum": ["market_order", "limit_order", "stop_order"]
                    },
                    "market": {
                        "type": "string",
                        "description": "Trading pair (e.g., 'BTCUSDT')"
                    },
                    "price": {
                        "type": "number",
                        "description": "Price per unit (required for limit orders)"
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Quantity to buy/sell"
                    },
                    "total_quantity": {
                        "type": "number",
                        "description": "Total quantity (for market orders)"
                    },
                    "client_order_id": {
                        "type": "string",
                        "description": "Custom order ID for tracking"
                    }
                },
                "required": ["side", "order_type", "market"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_order_status",
            description="Get status of a specific order",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order ID to check status for"
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="cancel_order",
            description="Cancel an existing order",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order ID to cancel"
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_active_orders",
            description="Get all active orders",
            inputSchema={
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "description": "Filter by trading pair (optional)"
                    },
                    "side": {
                        "type": "string",
                        "description": "Filter by order side (optional)",
                        "enum": ["buy", "sell"]
                    }
                },
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_order_history",
            description="Get historical orders",
            inputSchema={
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "description": "Filter by trading pair (optional)"
                    },
                    "side": {
                        "type": "string",
                        "description": "Filter by order side (optional)",
                        "enum": ["buy", "sell"]
                    },
                    "from_timestamp": {
                        "type": "integer",
                        "description": "Start timestamp in milliseconds (optional)"
                    },
                    "to_timestamp": {
                        "type": "integer",
                        "description": "End timestamp in milliseconds (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of orders to retrieve (default: 500, max: 1000)",
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_orders",
            description="List futures orders filtered by status and side",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Comma-separated order statuses (e.g. 'open' or 'open,filled'). Valid values: open, filled, partially_filled, partially_cancelled, cancelled, rejected, untriggered"
                    },
                    "side": {
                        "type": "string",
                        "description": "Order side",
                        "enum": ["buy", "sell"]
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                        "minimum": 1
                    },
                    "size": {
                        "type": "integer",
                        "description": "Number of records per page (default: 10)",
                        "minimum": 1
                    },
                    "margin_currencies": {
                        "type": "array",
                        "description": "Futures margin modes (default: ['USDT']). Possible values: 'USDT', 'INR'",
                        "items": {
                            "type": "string",
                            "enum": ["USDT", "INR"]
                        }
                    }
                },
                "required": ["status", "side"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="create_futures_order",
            description="Create a new futures order (limit, market, stop, or take-profit)",
            inputSchema={
                "type": "object",
                "properties": {
                    "side": {
                        "type": "string",
                        "description": "Order side",
                        "enum": ["buy", "sell"]
                    },
                    "pair": {
                        "type": "string",
                        "description": "Futures instrument pair (e.g., 'B-BTC_USDT')"
                    },
                    "order_type": {
                        "type": "string",
                        "description": "Order type",
                        "enum": ["market_order", "limit_order", "stop_limit", "stop_market", "take_profit_limit", "take_profit_market"]
                    },
                    "total_quantity": {
                        "type": "number",
                        "description": "Order quantity"
                    },
                    "price": {
                        "type": "number",
                        "description": "Limit price. Required for limit_order, stop_limit, take_profit_limit. Must be omitted for market orders."
                    },
                    "stop_price": {
                        "type": "number",
                        "description": "Trigger price. Required for stop_limit, stop_market, take_profit_limit, take_profit_market."
                    },
                    "leverage": {
                        "type": "integer",
                        "description": "Leverage for the position. Should match existing position leverage."
                    },
                    "notification": {
                        "type": "string",
                        "description": "Notification preference (default: 'no_notification')",
                        "enum": ["no_notification", "email_notification"]
                    },
                    "time_in_force": {
                        "type": "string",
                        "description": "Time in force. Must be omitted for market orders.",
                        "enum": ["good_till_cancel", "fill_or_kill", "immediate_or_cancel"]
                    },
                    "margin_currency": {
                        "type": "string",
                        "description": "Futures margin mode (default: 'USDT')",
                        "enum": ["USDT", "INR"]
                    },
                    "position_margin_type": {
                        "type": "string",
                        "description": "Position margin type. Defaults to the existing position margin type.",
                        "enum": ["isolated", "crossed"]
                    },
                    "take_profit_price": {
                        "type": "number",
                        "description": "Take profit trigger price (for limit_order and market_order only)"
                    },
                    "stop_loss_price": {
                        "type": "number",
                        "description": "Stop loss trigger price (for limit_order and market_order only)"
                    }
                },
                "required": ["side", "pair", "order_type", "total_quantity"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="cancel_futures_order",
            description="Cancel an existing futures order by order ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the futures order to cancel"
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="list_futures_positions",
            description="List futures positions with optional margin currency filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                        "minimum": 1
                    },
                    "size": {
                        "type": "integer",
                        "description": "Number of records per page (default: 10)",
                        "minimum": 1
                    },
                    "margin_currencies": {
                        "type": "array",
                        "description": "Futures margin modes to filter by (default: ['USDT']). Possible values: 'USDT', 'INR'",
                        "items": {
                            "type": "string",
                            "enum": ["USDT", "INR"]
                        }
                    }
                },
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_currency_conversion",
            description="Get the fixed USDT/INR conversion price used for INR-margined futures trading. This rate is set by CoinDCX and may change periodically due to extreme market movements.",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="change_futures_position_margin_type",
            description="Change the margin type of a futures position between 'isolated' and 'crossed'. Only supported for USDT-margined futures. The position must have no active quantity and no open orders.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Instrument pair name, e.g. 'B-BTC_USDT'"
                    },
                    "margin_type": {
                        "type": "string",
                        "enum": ["isolated", "crossed"],
                        "description": "New margin type: 'isolated' or 'crossed'"
                    }
                },
                "required": ["pair", "margin_type"]
            }
        ),
        types.Tool(
            name="edit_futures_order",
            description="Edit an open USDT-margined futures limit order. Updates the total quantity and/or price. Optionally update take profit and stop loss trigger prices. Only works for orders in open status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the futures order to edit"
                    },
                    "total_quantity": {
                        "type": "number",
                        "description": "New total quantity for the order"
                    },
                    "price": {
                        "type": "number",
                        "description": "New limit price for the order"
                    },
                    "take_profit_price": {
                        "type": "number",
                        "description": "Optional new take profit trigger price (market/limit orders only)"
                    },
                    "stop_loss_price": {
                        "type": "number",
                        "description": "Optional new stop loss trigger price (market/limit orders only)"
                    }
                },
                "required": ["order_id", "total_quantity", "price"]
            }
        ),
        types.Tool(
            name="get_futures_wallet_transactions",
            description="Get a paginated list of futures wallet transactions (credits and debits) for USDT and INR futures wallets. Includes transfers, order-related transactions, and funding events.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {
                        "type": "integer",
                        "description": "Page number (default: 1)"
                    },
                    "size": {
                        "type": "integer",
                        "description": "Number of records per page (default: 1000)"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_futures_wallet_details",
            description="Get futures wallet details for both USDT and INR wallets, including balance, locked margin, and cross-margin breakdowns. Total wallet balance = balance + locked_balance.",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="transfer_futures_wallet",
            description="Transfer funds between the spot wallet and the futures wallet. Use transfer_type='deposit' to move funds into the futures wallet, or 'withdraw' to move them back to the spot wallet. Supports USDT and INR currencies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "transfer_type": {
                        "type": "string",
                        "enum": ["deposit", "withdraw"],
                        "description": "Direction of transfer: 'deposit' into futures wallet, 'withdraw' from futures wallet"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount to transfer"
                    },
                    "currency_short_name": {
                        "type": "string",
                        "enum": ["USDT", "INR"],
                        "description": "Currency to transfer. Default: 'USDT'"
                    }
                },
                "required": ["transfer_type", "amount"]
            }
        ),
        types.Tool(
            name="get_futures_cross_margin_details",
            description="Get cross margin account details for USDT-margined futures, including unrealised PnL, margin ratios, wallet balances, and available balances. Cross margin is not supported for INR-margined futures.",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_pair_stats",
            description="Get statistics for a futures pair including price change percentages (1H/1D/1W/1M), high/low data, and long/short position sentiment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Instrument pair, e.g. 'B-ETH_USDT' or 'B-BTC_USDT'."
                    }
                },
                "required": ["pair"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_current_prices_rt",
            description="Get real-time current prices for all active futures instruments, including last price, mark price, high, low, volume, price change percent, and funding rate.",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_trades",
            description="Get futures trade history for a specific pair within a date range, optionally filtered by order ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Instrument pair, e.g. 'B-ID_USDT'."
                    },
                    "from_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format, e.g. '2024-01-01'."
                    },
                    "to_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format, e.g. '2024-01-31'."
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number (default: 1).",
                        "minimum": 1
                    },
                    "size": {
                        "type": "integer",
                        "description": "Number of records per page (default: 10).",
                        "minimum": 1
                    },
                    "order_id": {
                        "type": "string",
                        "description": "Optional order ID to filter trades for a specific order."
                    },
                    "margin_currencies": {
                        "type": "array",
                        "description": "Futures margin modes to filter by (default: ['USDT']). Possible values: 'USDT', 'INR'.",
                        "items": {
                            "type": "string",
                            "enum": ["USDT", "INR"]
                        }
                    }
                },
                "required": ["pair", "from_date", "to_date"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_transactions",
            description="Get futures transactions filtered by stage (funding, default, exit, tpsl_exit, liquidation, or all).",
            inputSchema={
                "type": "object",
                "properties": {
                    "stage": {
                        "type": "string",
                        "description": "Transaction stage: 'funding' (funding transactions), 'default' (standard order transactions), 'exit' (quick exit transactions), 'tpsl_exit' (full-position TP/SL exit transactions), 'liquidation' (liquidation transactions), 'all' (all types).",
                        "enum": ["funding", "default", "exit", "tpsl_exit", "liquidation", "all"]
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number (default: 1).",
                        "minimum": 1
                    },
                    "size": {
                        "type": "integer",
                        "description": "Number of records per page (default: 10).",
                        "minimum": 1
                    },
                    "margin_currencies": {
                        "type": "array",
                        "description": "Futures margin modes to filter by (default: ['USDT']). Possible values: 'USDT', 'INR'.",
                        "items": {
                            "type": "string",
                            "enum": ["USDT", "INR"]
                        }
                    }
                },
                "required": ["stage"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="create_futures_tpsl",
            description="Create Take Profit and/or Stop Loss orders for a futures position. Provide at least one of take_profit or stop_loss.",
            inputSchema={
                "type": "object",
                "properties": {
                    "position_id": {
                        "type": "string",
                        "description": "The position ID to attach TP/SL orders to."
                    },
                    "take_profit": {
                        "type": "object",
                        "description": "Take profit order parameters.",
                        "properties": {
                            "stop_price": {
                                "type": "string",
                                "description": "Trigger price for the take profit order."
                            },
                            "order_type": {
                                "type": "string",
                                "description": "Order type for take profit.",
                                "enum": ["take_profit_market", "take_profit_limit"]
                            },
                            "limit_price": {
                                "type": "string",
                                "description": "Limit price (required for take_profit_limit orders)."
                            }
                        },
                        "required": ["stop_price", "order_type"],
                        "additionalProperties": False
                    },
                    "stop_loss": {
                        "type": "object",
                        "description": "Stop loss order parameters.",
                        "properties": {
                            "stop_price": {
                                "type": "string",
                                "description": "Trigger price for the stop loss order."
                            },
                            "order_type": {
                                "type": "string",
                                "description": "Order type for stop loss.",
                                "enum": ["stop_market", "stop_limit"]
                            },
                            "limit_price": {
                                "type": "string",
                                "description": "Limit price (required for stop_limit orders)."
                            }
                        },
                        "required": ["stop_price", "order_type"],
                        "additionalProperties": False
                    }
                },
                "required": ["position_id"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="exit_futures_position",
            description="Exit a futures position entirely by placing a market close order. Large positions may be auto-split; use the returned group_id to track all child orders.",
            inputSchema={
                "type": "object",
                "properties": {
                    "position_id": {
                        "type": "string",
                        "description": "The position ID to exit."
                    }
                },
                "required": ["position_id"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="cancel_all_futures_open_orders_for_position",
            description="Cancel all open orders for a specific futures position identified by its position ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "position_id": {
                        "type": "string",
                        "description": "The position ID whose open orders should be cancelled."
                    }
                },
                "required": ["position_id"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="cancel_all_futures_open_orders",
            description="Cancel all open futures orders across all positions for the specified margin mode(s).",
            inputSchema={
                "type": "object",
                "properties": {
                    "margin_currencies": {
                        "type": "array",
                        "description": "Futures margin modes to cancel orders for (default: ['USDT']). Possible values: 'USDT', 'INR'.",
                        "items": {
                            "type": "string",
                            "enum": ["USDT", "INR"]
                        }
                    }
                },
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="remove_futures_margin",
            description="Remove margin from a futures position to increase its effective leverage. Removing margin raises liquidation risk.",
            inputSchema={
                "type": "object",
                "properties": {
                    "position_id": {
                        "type": "string",
                        "description": "The position ID to remove margin from."
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount of margin to remove. In USDT for USDT-margined futures, in INR for INR-margined futures."
                    }
                },
                "required": ["position_id", "amount"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="add_futures_margin",
            description="Add margin to a futures position to decrease its effective leverage and update the liquidation price.",
            inputSchema={
                "type": "object",
                "properties": {
                    "position_id": {
                        "type": "string",
                        "description": "The position ID to add margin to."
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount of margin to add. In USDT for USDT-margined futures, in INR for INR-margined futures."
                    }
                },
                "required": ["position_id", "amount"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="update_futures_position_leverage",
            description="Update the leverage for a futures position. Use either pair or position_id to target the position, not both.",
            inputSchema={
                "type": "object",
                "properties": {
                    "leverage": {
                        "type": "string",
                        "description": "New leverage value, e.g. '5'"
                    },
                    "pair": {
                        "type": "string",
                        "description": "Instrument pair, e.g. 'B-LTC_USDT'. Use this OR position_id."
                    },
                    "position_id": {
                        "type": "string",
                        "description": "Position ID. Use this OR pair."
                    },
                    "margin_currency": {
                        "type": "string",
                        "description": "Futures margin mode (default: 'USDT').",
                        "enum": ["USDT", "INR"]
                    }
                },
                "required": ["leverage"],
                "additionalProperties": False,
            }
        ),
        types.Tool(
            name="get_futures_positions_by_filter",
            description="Get futures positions filtered by specific pair(s) or position ID(s). Use either pairs or position_ids, not both.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pairs": {
                        "type": "string",
                        "description": "Comma-separated instrument pairs (e.g. 'B-BTC_USDT' or 'B-BTC_USDT,B-ETH_USDT'). Use this OR position_ids."
                    },
                    "position_ids": {
                        "type": "string",
                        "description": "Comma-separated position IDs. Use this OR pairs."
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                        "minimum": 1
                    },
                    "size": {
                        "type": "integer",
                        "description": "Number of records per page (default: 10)",
                        "minimum": 1
                    },
                    "margin_currencies": {
                        "type": "array",
                        "description": "Futures margin modes to filter by (default: ['USDT']). Possible values: 'USDT', 'INR'",
                        "items": {
                            "type": "string",
                            "enum": ["USDT", "INR"]
                        }
                    }
                },
                "additionalProperties": False,
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool calls."""
    logger.info(f"Calling tool: {name} with arguments: {arguments}")
    try:
        client = get_client()
        result = None
        
        if name == "get_ticker":
            result = client.get_ticker()
        elif name == "get_markets":
            result = client.get_markets()
        elif name == "get_market_details":
            result = client.get_market_details(arguments["pair"])
        elif name == "get_trades":
            limit = arguments.get("limit", 30)
            result = client.get_trades(arguments["pair"], limit)
        elif name == "get_order_book":
            result = client.get_order_book(arguments["pair"])
        elif name == "get_futures_active_instruments":
            margin_currency = arguments.get("margin_currency", "USDT")
            result = client.get_futures_active_instruments(margin_currency)
        elif name == "get_futures_instrument_details":
            margin_currency = arguments.get("margin_currency", "USDT")
            result = client.get_futures_instrument_details(arguments["pair"], margin_currency)
        elif name == "get_futures_instrument_trades":
            result = client.get_futures_instrument_trades(arguments["pair"])
        elif name == "get_futures_instrument_orderbook":
            depth = arguments.get("depth", 50)
            result = client.get_futures_instrument_orderbook(arguments["pair"], depth)
        elif name == "get_futures_instrument_candlesticks":
            result = client.get_futures_instrument_candlesticks(
                arguments["pair"],
                arguments["resolution"],
                arguments["from_time"],
                arguments["to_time"]
            )
        elif name == "get_candles":
            limit = arguments.get("limit", 100)
            # Provide default time range if not specified
            current_time = int(__import__('time').time() * 1000)
            default_start_time = current_time - (24 * 60 * 60 * 1000)  # 24 hours ago
            default_end_time = current_time
            
            start_time = arguments.get("start_time", default_start_time)
            end_time = arguments.get("end_time", default_end_time)
            
            result = client.get_candles(
                arguments["pair"],
                arguments["interval"],
                start_time,
                end_time,
                limit
            )
        elif name == "get_balances":
            result = client.get_balances()
        elif name == "get_user_info":
            result = client.get_user_info()
        elif name == "create_order":
            result = client.create_order(
                arguments["side"],
                arguments["order_type"],
                arguments["market"],
                arguments.get("price"),
                arguments.get("quantity"),
                arguments.get("total_quantity"),
                arguments.get("client_order_id")
            )
        elif name == "get_order_status":
            result = client.get_order_status(arguments["order_id"])
        elif name == "cancel_order":
            result = client.cancel_order(arguments["order_id"])
        elif name == "get_active_orders":
            result = client.get_active_orders(
                arguments.get("market"),
                arguments.get("side")
            )
        elif name == "get_order_history":
            result = client.get_order_history(
                arguments.get("market"),
                arguments.get("side"),
                arguments.get("from_timestamp"),
                arguments.get("to_timestamp"),
                arguments.get("limit", 500)
            )
        elif name == "get_futures_orders":
            result = client.get_futures_orders(
                arguments["status"],
                arguments["side"],
                arguments.get("page", 1),
                arguments.get("size", 10),
                arguments.get("margin_currencies")
            )
        elif name == "create_futures_order":
            result = client.create_futures_order(
                arguments["side"],
                arguments["pair"],
                arguments["order_type"],
                arguments["total_quantity"],
                arguments.get("notification", "no_notification"),
                arguments.get("price"),
                arguments.get("stop_price"),
                arguments.get("leverage"),
                arguments.get("time_in_force"),
                arguments.get("margin_currency", "USDT"),
                arguments.get("position_margin_type"),
                arguments.get("take_profit_price"),
                arguments.get("stop_loss_price")
            )
        elif name == "cancel_futures_order":
            result = client.cancel_futures_order(arguments["order_id"])
        elif name == "list_futures_positions":
            result = client.list_futures_positions(
                arguments.get("page", 1),
                arguments.get("size", 10),
                arguments.get("margin_currencies")
            )
        elif name == "get_futures_currency_conversion":
            result = client.get_futures_currency_conversion()
        elif name == "change_futures_position_margin_type":
            result = client.change_futures_position_margin_type(
                pair=arguments["pair"],
                margin_type=arguments["margin_type"]
            )
        elif name == "edit_futures_order":
            result = client.edit_futures_order(
                order_id=arguments["order_id"],
                total_quantity=arguments["total_quantity"],
                price=arguments["price"],
                take_profit_price=arguments.get("take_profit_price"),
                stop_loss_price=arguments.get("stop_loss_price")
            )
        elif name == "get_futures_wallet_transactions":
            result = client.get_futures_wallet_transactions(
                page=arguments.get("page", 1),
                size=arguments.get("size", 1000)
            )
        elif name == "get_futures_wallet_details":
            result = client.get_futures_wallet_details()
        elif name == "transfer_futures_wallet":
            result = client.transfer_futures_wallet(
                transfer_type=arguments["transfer_type"],
                amount=arguments["amount"],
                currency_short_name=arguments.get("currency_short_name", "USDT")
            )
        elif name == "get_futures_cross_margin_details":
            result = client.get_futures_cross_margin_details()
        elif name == "get_futures_pair_stats":
            result = client.get_futures_pair_stats(
                arguments["pair"]
            )
        elif name == "get_futures_current_prices_rt":
            result = client.get_futures_current_prices_rt()
        elif name == "get_futures_trades":
            result = client.get_futures_trades(
                arguments["pair"],
                arguments["from_date"],
                arguments["to_date"],
                arguments.get("page", 1),
                arguments.get("size", 10),
                arguments.get("order_id"),
                arguments.get("margin_currencies")
            )
        elif name == "get_futures_transactions":
            result = client.get_futures_transactions(
                arguments["stage"],
                arguments.get("page", 1),
                arguments.get("size", 10),
                arguments.get("margin_currencies")
            )
        elif name == "create_futures_tpsl":
            result = client.create_futures_tpsl(
                arguments["position_id"],
                arguments.get("take_profit"),
                arguments.get("stop_loss")
            )
        elif name == "exit_futures_position":
            result = client.exit_futures_position(
                arguments["position_id"]
            )
        elif name == "cancel_all_futures_open_orders_for_position":
            result = client.cancel_all_futures_open_orders_for_position(
                arguments["position_id"]
            )
        elif name == "cancel_all_futures_open_orders":
            result = client.cancel_all_futures_open_orders(
                arguments.get("margin_currencies")
            )
        elif name == "remove_futures_margin":
            result = client.remove_futures_margin(
                arguments["position_id"],
                arguments["amount"]
            )
        elif name == "add_futures_margin":
            result = client.add_futures_margin(
                arguments["position_id"],
                arguments["amount"]
            )
        elif name == "update_futures_position_leverage":
            result = client.update_futures_position_leverage(
                arguments["leverage"],
                arguments.get("pair"),
                arguments.get("position_id"),
                arguments.get("margin_currency", "USDT")
            )
        elif name == "get_futures_positions_by_filter":
            result = client.get_futures_positions_by_filter(
                arguments.get("page", 1),
                arguments.get("size", 10),
                arguments.get("pairs"),
                arguments.get("position_ids"),
                arguments.get("margin_currencies")
            )
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str)
        )]
    
    except Exception as e:
        error_msg = f"Error calling {name}: {str(e)}"
        return [types.TextContent(type="text", text=error_msg)]


async def main():
    """Main entry point for the server."""
    logger.info("Starting MCP server with stdio transport...")
    async with stdio_server() as streams:
        logger.info("Server is running and ready to accept connections")
        await app.run(streams[0], streams[1], app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())