import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional
import httpx
from datetime import datetime


class CoinDCXClient:
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://api.coindcx.com"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC-SHA256 signature for authenticated requests."""
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _make_authenticated_request(self, method: str, endpoint: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make authenticated request to CoinDCX API."""
        timestamp = int(time.time() * 1000)
        
        if payload is None:
            payload = {}
        
        # Add timestamp to payload as required by CoinDCX API
        payload["timestamp"] = timestamp
        
        payload_str = json.dumps(payload, separators=(',', ':'))
        signature = self._generate_signature(payload_str)
        
        headers = {
            'Content-Type': 'application/json',
            'X-AUTH-APIKEY': self.api_key,
            'X-AUTH-SIGNATURE': signature
        }
        
        url = f"{self.base_url}{endpoint}"
        
        # CoinDCX authenticated endpoints are all POST requests
        response = self.client.post(url, headers=headers, data=payload_str)
        
        response.raise_for_status()
        return response.json()

    def _make_public_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make public request to CoinDCX API."""
        url = f"{self.base_url}{endpoint}"
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _make_public_market_data_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make public request to CoinDCX market data API."""
        url = f"https://public.coindcx.com{endpoint}"
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _format_pair_for_public_api(self, pair: str) -> str:
        """Convert pair format from BTCUSDT to B-BTC_USDT for public API."""
        # First, try to find the pair in market details to get the correct format
        try:
            market_details = self.get_market_details(pair)
            if market_details and not market_details.get('error'):
                # Extract the pair format from market details
                api_pair = market_details.get('pair', '')
                if api_pair.startswith('KC-'):
                    # Convert KC-BTC_USDT to B-BTC_USDT
                    return api_pair.replace('KC-', 'B-')
        except:
            pass
        
        # Fallback: manually format common pairs
        if pair.upper().endswith('USDT'):
            base = pair.upper().replace('USDT', '')
            return f"B-{base}_USDT"
        elif pair.upper().endswith('BTC'):
            base = pair.upper().replace('BTC', '')
            return f"B-{base}_BTC"
        elif pair.upper().endswith('INR'):
            base = pair.upper().replace('INR', '')
            return f"I-{base}_INR"
        else:
            # Default fallback
            return f"B-{pair.upper()}"

    # Public endpoints
    def get_ticker(self) -> Dict[str, Any]:
        """Get ticker data for all markets."""
        return self._make_public_request("/exchange/ticker")

    def get_markets(self) -> Dict[str, Any]:
        """Get all available markets."""
        return self._make_public_request("/exchange/v1/markets")

    def get_market_details(self, pair: str = None) -> Dict[str, Any]:
        """Get market details. If pair is specified, filter for that specific trading pair."""
        all_markets = self._make_public_request("/exchange/v1/markets_details")
        
        if pair:
            # Filter for the specific pair
            for market in all_markets:
                if (market.get("coindcx_name", "").upper() == pair.upper() or 
                    market.get("symbol", "").upper() == pair.upper() or
                    market.get("pair", "").upper() == f"KC-{pair.upper().replace('USDT', '_USDT')}" or
                    market.get("pair", "").upper() == f"KC-{pair.upper().replace('BTC', '_BTC')}"):
                    return market
            
            # If not found, return error message
            return {"error": f"Trading pair '{pair}' not found"}
        
        return all_markets

    def get_trades(self, pair: str, limit: int = 30) -> Dict[str, Any]:
        """Get recent trades for a market."""
        # Convert pair format from BTCUSDT to B-BTC_USDT
        formatted_pair = self._format_pair_for_public_api(pair)
        params = {"pair": formatted_pair, "limit": limit}
        return self._make_public_market_data_request("/market_data/trade_history", params)

    def get_order_book(self, pair: str) -> Dict[str, Any]:
        """Get order book for a market."""
        # Convert pair format from BTCUSDT to B-BTC_USDT
        formatted_pair = self._format_pair_for_public_api(pair)
        params = {"pair": formatted_pair}
        return self._make_public_market_data_request("/market_data/orderbook", params)

    def get_futures_active_instruments(self, margin_currency: str = "USDT") -> Dict[str, Any]:
        """Get list of all active futures instruments.
        
        Args:
            margin_currency: Futures margin mode. Either 'USDT' (default) or 'INR'.
        
        Returns:
            List of active futures instrument pair strings (e.g. ['B-BTC_USDT', ...]).
        """
        params = {"margin_currency_short_name[]": margin_currency}
        return self._make_public_request(
            "/exchange/v1/derivatives/futures/data/active_instruments", params
        )

    def get_futures_instrument_details(self, pair: str, margin_currency: str = "USDT") -> Dict[str, Any]:
        """Get detailed information about a specific futures instrument.
        
        Args:
            pair: Instrument pair name (e.g. 'B-BTC_USDT').
            margin_currency: Futures margin mode. Either 'USDT' (default) or 'INR'.
        
        Returns:
            Dict with 'instrument' key containing full instrument details such as
            leverage limits, fees, price/quantity increments, funding frequency, etc.
        """
        params = {
            "pair": pair,
            "margin_currency_short_name": margin_currency
        }
        return self._make_public_request(
            "/exchange/v1/derivatives/futures/data/instrument", params
        )

    def get_futures_instrument_trades(self, pair: str) -> Dict[str, Any]:
        """Get real-time trade history for a specific futures instrument.

        Args:
            pair: Instrument pair name (e.g. 'B-BTC_USDT').

        Returns:
            List of recent trades, each containing:
                - price: Price of the trade
                - quantity: Quantity of the trade
                - timestamp: EPOCH timestamp of the event (ms)
                - is_maker: True if the trade is a maker trade
        """
        params = {"pair": pair}
        return self._make_public_request(
            "/exchange/v1/derivatives/futures/data/trades", params
        )

    def get_futures_instrument_orderbook(self, pair: str, depth: int = 50) -> Dict[str, Any]:
        """Get order book for a specific futures instrument.

        Args:
            pair: Instrument pair name (e.g. 'B-BTC_USDT').
            depth: Order book depth. Valid values: 10, 20, 50 (default: 50).

        Returns:
            Dict containing:
                - ts: Epoch timestamp
                - vs: Version
                - asks: Dict of ask price -> quantity
                - bids: Dict of bid price -> quantity
        """
        if depth not in (10, 20, 50):
            raise ValueError("depth must be one of: 10, 20, 50")
        return self._make_public_market_data_request(
            f"/market_data/v3/orderbook/{pair}-futures/{depth}"
        )

    def get_futures_instrument_candlesticks(self, pair: str, resolution: str,
                                            from_time: int, to_time: int) -> Dict[str, Any]:
        """Get candlestick (OHLCV) data for a specific futures instrument.

        Args:
            pair: Instrument pair name (e.g. 'B-BTC_USDT').
            resolution: Candle resolution. Valid values:
                '1'  -> 1 minute
                '5'  -> 5 minutes
                '60' -> 1 hour
                '1D' -> 1 day
            from_time: EPOCH start timestamp in seconds.
            to_time: EPOCH end timestamp in seconds.

        Returns:
            Dict containing:
                - s: status ('ok' on success)
                - data: list of candles, each with open, high, low, close, volume, time
        """
        valid_resolutions = ('1', '5', '60', '1D')
        if resolution not in valid_resolutions:
            raise ValueError(f"resolution must be one of: {', '.join(valid_resolutions)}")
        params = {
            "pair": pair,
            "from": from_time,
            "to": to_time,
            "resolution": resolution,
            "pcode": "f"
        }
        return self._make_public_market_data_request("/market_data/candlesticks", params)

    def get_candles(self, pair: str, interval: str, start_time: int, end_time: int, limit: int = 1000) -> Dict[str, Any]:
        """Get candlestick data."""
        # Convert pair format from BTCUSDT to B-BTC_USDT
        formatted_pair = self._format_pair_for_public_api(pair)
        params = {
            "pair": formatted_pair,
            "interval": interval,
            "limit": limit
        }
        
        # Only add time parameters if they seem reasonable
        # Check if start_time is not in the future or too far in the past
        current_time = int(time.time() * 1000)
        one_year_ago = current_time - (365 * 24 * 60 * 60 * 1000)
        
        # Add time parameters only if they're within a reasonable range
        if start_time >= one_year_ago and start_time <= current_time and end_time <= current_time:
            params["startTime"] = start_time
            params["endTime"] = end_time
        
        result = self._make_public_market_data_request("/market_data/candles", params)
        
        # If no data returned with time params, try without time constraints
        if isinstance(result, list) and len(result) == 0 and ("startTime" in params or "endTime" in params):
            # Remove time parameters and try again
            params_no_time = {
                "pair": formatted_pair,
                "interval": interval,
                "limit": limit
            }
            result = self._make_public_market_data_request("/market_data/candles", params_no_time)
            
            # Add a note about the fallback
            if isinstance(result, list) and len(result) > 0:
                return {
                    "data": result,
                    "note": f"No data found for specified time range ({start_time} to {end_time}). Returning most recent {len(result)} candles instead.",
                    "requested_start_time": start_time,
                    "requested_end_time": end_time
                }
        
        return result

    # User endpoints
    def get_balances(self) -> Dict[str, Any]:
        """Get account balances."""
        return self._make_authenticated_request("POST", "/exchange/v1/users/balances")

    def get_user_info(self) -> Dict[str, Any]:
        """Get user information."""
        return self._make_authenticated_request("POST", "/exchange/v1/users/info")

    # Order endpoints
    def create_order(self, side: str, order_type: str, market: str, price: float = None, 
                    quantity: float = None, total_quantity: float = None, 
                    client_order_id: str = None) -> Dict[str, Any]:
        """Create a new order."""
        payload = {
            "side": side,
            "order_type": order_type,
            "market": market
        }
        
        if price is not None:
            payload["price_per_unit"] = str(price)  # Convert to string as required by API
        if quantity is not None:
            payload["quantity"] = str(quantity)  # Convert to string as required by API
        if total_quantity is not None:
            payload["total_quantity"] = str(total_quantity)  # Convert to string as required by API
        if client_order_id is not None:
            payload["client_order_id"] = client_order_id
            
        return self._make_authenticated_request("POST", "/exchange/v1/orders/create", payload)

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status."""
        payload = {"id": order_id}
        return self._make_authenticated_request("POST", "/exchange/v1/orders/status", payload)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        payload = {"id": order_id}
        return self._make_authenticated_request("POST", "/exchange/v1/orders/cancel", payload)

    def get_active_orders(self, market: str = None, side: str = None) -> Dict[str, Any]:
        """Get active orders."""
        payload = {}
        if market:
            payload["market"] = market
        if side:
            payload["side"] = side
        return self._make_authenticated_request("POST", "/exchange/v1/orders/active_orders", payload)

    def get_order_history(self, market: str = None, side: str = None, 
                         from_timestamp: int = None, to_timestamp: int = None, 
                         limit: int = 500) -> Dict[str, Any]:
        """Get order history."""
        payload = {"limit": limit}
        if market:
            payload["symbol"] = market  # Use 'symbol' instead of 'market'
        if side:
            payload["side"] = side
        if from_timestamp:
            payload["from_timestamp"] = from_timestamp  # Correct parameter name
        if to_timestamp:
            payload["to_timestamp"] = to_timestamp  # Correct parameter name
        return self._make_authenticated_request("POST", "/exchange/v1/orders/trade_history", payload)

    # Futures order endpoints
    def get_futures_orders(self, status: str, side: str, page: int = 1, size: int = 10,
                           margin_currencies: list = None) -> Dict[str, Any]:
        """List futures orders filtered by status and side.

        Args:
            status: Comma-separated order statuses. Valid values:
                open, filled, partially_filled, partially_cancelled,
                cancelled, rejected, untriggered.
                Example: 'open' or 'open,filled'
            side: Order side. Either 'buy' or 'sell'.
            page: Page number (default: 1).
            size: Number of records per page (default: 10).
            margin_currencies: List of margin modes, e.g. ['USDT'] or ['INR', 'USDT'].
                Defaults to ['USDT'].

        Returns:
            List of futures order objects.
        """
        if margin_currencies is None:
            margin_currencies = ["USDT"]
        payload = {
            "status": status,
            "side": side,
            "page": str(page),
            "size": str(size),
            "margin_currency_short_name": margin_currencies
        }
        return self._make_authenticated_request(
            "POST", "/exchange/v1/derivatives/futures/orders", payload
        )

    def create_futures_order(self, side: str, pair: str, order_type: str,
                             total_quantity: float, notification: str = "no_notification",
                             price: float = None, stop_price: float = None,
                             leverage: int = None, time_in_force: str = None,
                             margin_currency: str = "USDT",
                             position_margin_type: str = None,
                             take_profit_price: float = None,
                             stop_loss_price: float = None) -> Dict[str, Any]:
        """Create a new futures order.

        Args:
            side: Order side. 'buy' or 'sell'.
            pair: Futures instrument pair (e.g. 'B-BTC_USDT').
            order_type: One of: 'market_order', 'limit_order', 'stop_limit',
                'stop_market', 'take_profit_limit', 'take_profit_market'.
            total_quantity: Order quantity.
            notification: 'no_notification' (default) or 'email_notification'.
            price: Limit price. Required for limit, stop_limit, take_profit_limit
                orders. Must be None for market orders.
            stop_price: Trigger price. Required for stop_limit, stop_market,
                take_profit_limit, take_profit_market orders.
            leverage: Leverage for the position. Should match existing position
                leverage to avoid rejection.
            time_in_force: 'good_till_cancel', 'fill_or_kill', or
                'immediate_or_cancel'. Must be None for market orders.
            margin_currency: Futures margin mode. 'USDT' (default) or 'INR'.
            position_margin_type: 'isolated' or 'crossed'. Defaults to the
                existing position margin type if not provided.
            take_profit_price: Take profit trigger price (limit/market orders only).
            stop_loss_price: Stop loss trigger price (limit/market orders only).

        Returns:
            List containing the created futures order object.
        """
        order: Dict[str, Any] = {
            "side": side,
            "pair": pair,
            "order_type": order_type,
            "total_quantity": total_quantity,
            "notification": notification,
        }
        if price is not None:
            order["price"] = price
        if stop_price is not None:
            order["stop_price"] = stop_price
        if leverage is not None:
            order["leverage"] = leverage
        if time_in_force is not None:
            order["time_in_force"] = time_in_force
        if position_margin_type is not None:
            order["position_margin_type"] = position_margin_type
        if take_profit_price is not None:
            order["take_profit_price"] = take_profit_price
        if stop_loss_price is not None:
            order["stop_loss_price"] = stop_loss_price
        if margin_currency != "USDT":
            order["margin_currency_short_name"] = margin_currency

        payload = {"order": order}
        return self._make_authenticated_request(
            "POST", "/exchange/v1/derivatives/futures/orders/create", payload
        )

    def cancel_futures_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an existing futures order.

        Args:
            order_id: The ID of the futures order to cancel.

        Returns:
            Confirmation response from the API.
        """
        payload = {"id": order_id}
        return self._make_authenticated_request(
            "POST", "/exchange/v1/derivatives/futures/orders/cancel", payload
        )

    def list_futures_positions(self, page: int = 1, size: int = 10,
                               margin_currencies: list = None) -> Dict[str, Any]:
        """List futures positions.

        Args:
            page: Page number (default: 1).
            size: Number of records per page (default: 10).
            margin_currencies: List of margin modes to filter by, e.g. ['USDT']
                or ['INR', 'USDT']. Defaults to ['USDT'].

        Returns:
            List of futures position objects, each containing:
                - id: Position id (fixed per pair)
                - pair: Futures pair name
                - active_pos: Position quantity (negative for short)
                - avg_price: Average entry price
                - liquidation_price: Liquidation price (isolated margin only)
                - locked_margin: Margin locked in the position
                - leverage: Position leverage
                - maintenance_margin: Margin required to avoid liquidation
                - mark_price: Mark price at last update
                - margin_type: 'crossed' or 'isolated'
                - margin_currency_short_name: Futures margin mode
                - updated_at: Last updated timestamp
        """
        if margin_currencies is None:
            margin_currencies = ["USDT"]
        payload = {
            "page": str(page),
            "size": str(size),
            "margin_currency_short_name": margin_currencies
        }
        return self._make_authenticated_request(
            "POST", "/exchange/v1/derivatives/futures/positions", payload
        )

    def get_futures_currency_conversion(self) -> Dict[str, Any]:
        """Get the USDT <> INR currency conversion price used for INR-margined futures.

        CoinDCX notionally converts INR to USDT (and vice-versa) at a fixed
        conversion rate for INR futures. This rate may change periodically
        due to extreme market movements.

        Returns:
            List containing conversion rate objects, each with:
                - symbol: Symbol name (e.g. 'USDTINR')
                - margin_currency_short_name: 'INR'
                - target_currency_short_name: 'USDT'
                - conversion_price: Current fixed INR/USDT conversion rate
                - last_updated_at: Timestamp when the rate was last changed
        """
        return self._make_authenticated_request(
            "POST",
            "/api/v1/derivatives/futures/data/conversions",
            {}
        )

    def change_futures_position_margin_type(self, pair: str, margin_type: str) -> Dict[str, Any]:
        """Change the margin type for a futures position between isolated and crossed.

        Only supported for USDT-margined futures. The position must have no
        active quantity and no open orders before the margin type can be changed.

        Args:
            pair: Instrument pair name, e.g. 'B-BTC_USDT'.
            margin_type: New margin type. Either 'isolated' or 'crossed'.

        Returns:
            List containing the updated position object, including:
                - id: Position id
                - pair: Futures pair name
                - active_pos: Current position quantity
                - margin_type: Updated margin type
                - leverage: Position leverage
                - locked_margin, locked_user_margin, locked_order_margin
                - take_profit_trigger, stop_loss_trigger
                - maintenance_margin, mark_price
                - updated_at: Last update timestamp
        """
        payload = {
            "pair": pair,
            "margin_type": margin_type
        }
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/margin_type",
            payload
        )

    def edit_futures_order(self, order_id: str, total_quantity: float, price: float,
                           take_profit_price: float = None,
                           stop_loss_price: float = None) -> Dict[str, Any]:
        """Edit an open futures order's quantity and/or price.

        Only supported for USDT-margined futures. The order must be in open status.

        Args:
            order_id: The ID of the futures order to edit.
            total_quantity: New total quantity for the order.
            price: New limit price for the order.
            take_profit_price: Optional new take profit trigger price.
                Applies only to market_order or limit_order; ignored for
                reduce-only orders (no error raised).
            stop_loss_price: Optional new stop loss trigger price.
                Applies only to market_order or limit_order; ignored for
                reduce-only orders (no error raised).

        Returns:
            List containing the updated futures order object.
        """
        payload: Dict[str, Any] = {
            "id": order_id,
            "total_quantity": total_quantity,
            "price": price
        }
        if take_profit_price is not None:
            payload["take_profit_price"] = take_profit_price
        if stop_loss_price is not None:
            payload["stop_loss_price"] = stop_loss_price
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/orders/edit",
            payload
        )

    def get_futures_wallet_transactions(self, page: int = 1, size: int = 1000) -> Dict[str, Any]:
        """Get a list of futures wallet transactions for both USDT and INR wallets.

        Args:
            page: Page number (default: 1).
            size: Number of records per page (default: 1000).

        Returns:
            List of transaction objects, each containing:
                - derivatives_futures_wallet_id: Futures wallet id
                - transaction_type: 'credit' (into futures wallet) or
                  'debit' (from futures wallet)
                - amount: Transaction amount
                - currency_short_name: Currency of the wallet
                - currency_full_name: Full name of the currency
                - reason: Reason for the transaction:
                    'by_universal_wallet' - transfers between spot and futures
                    'by_futures_order'    - transactions due to a futures order
                    'by_futures_funding'  - funding (cross-margined positions)
                - created_at: Timestamp when the transaction was created
        """
        endpoint = f"/exchange/v1/derivatives/futures/wallets/transactions?page={page}&size={size}"
        return self._make_authenticated_request("POST", endpoint, {})

    def get_futures_wallet_details(self) -> Dict[str, Any]:
        """Get wallet details for the futures account (both USDT and INR wallets).

        Returns:
            List of wallet objects, each containing:
                - id: Futures wallet id
                - currency_short_name: Currency of the wallet ('USDT' or 'INR')
                - balance: Ignore this
                - locked_balance: Total initial margin locked in isolated
                  margined orders and positions
                - cross_order_margin: Total initial margin locked in
                  cross-margined orders
                - cross_user_margin: Total initial margin locked in
                  cross-margined positions

            Note: Total wallet balance = balance + locked_balance
        """
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/wallets",
            {}
        )

    def transfer_futures_wallet(self, transfer_type: str, amount: float,
                                currency_short_name: str = "USDT") -> Dict[str, Any]:
        """Transfer funds between the spot wallet and futures wallet.

        Args:
            transfer_type: Direction of transfer. Use 'deposit' to move funds
                into the futures wallet, or 'withdraw' to move funds out of
                the futures wallet back to the spot wallet.
            amount: Amount to transfer, denominated in `currency_short_name`.
            currency_short_name: Currency to transfer. 'USDT' (default) or 'INR'.

        Returns:
            List containing a wallet snapshot with:
                - id: Futures wallet transaction id
                - currency_short_name: Currency transferred
                - balance: Ignore this
                - locked_balance: Total initial margin locked in isolated orders/positions
                - cross_order_margin: Total initial margin locked in cross-margined orders
                - cross_user_margin: Total initial margin locked in cross-margined positions

            Note: Total wallet balance = balance + locked_balance
        """
        payload = {
            "transfer_type": transfer_type,
            "amount": amount,
            "currency_short_name": currency_short_name
        }
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/wallets/transfer",
            payload
        )

    def get_futures_cross_margin_details(self) -> Dict[str, Any]:
        """Get cross margin account details for USDT-margined futures.

        Returns unrealised PnL, margin ratios, wallet balances, and available
        balances for both cross and isolated margin modes.

        Note: Cross margin mode is not supported on INR-margined futures.

        Returns:
            Dict containing:
                - pnl: Unrealised PnL across all cross margin positions
                - maintenance_margin: Cumulative maintenance margin (cross positions)
                - total_wallet_balance: Total wallet balance (excl. active position PnL)
                - total_initial_margin: Cumulative initial margin (cross + isolated)
                - total_initial_margin_crossed: Initial margin for cross positions only
                - total_open_order_initial_margin_crossed: Margin locked in open orders
                - available_balance_cross: Balance available for cross margin trading
                - available_balance_isolated: Balance available for isolated margin trading
                - margin_ratio_cross: Cross margin ratio (liquidation if >= 1)
                - withdrawable_balance: Balance withdrawable to spot wallet
                - total_account_equity: total_wallet_balance + pnl
        """
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/cross_margin_details",
            {}
        )

    def get_futures_pair_stats(self, pair: str) -> Dict[str, Any]:
        """Get statistics for a specific futures pair.

        Returns price change percentages (1H, 1D, 1W, 1M), high/low data,
        and position sentiment (long/short percentages by count and value).

        Args:
            pair: Instrument pair, e.g. 'B-ETH_USDT'.

        Returns:
            Dict containing:
                - price_change_percent: dict with 1H, 1D, 1W, 1M keys
                - high_and_low: dict with 1D and 1W high/low values
                - position: dict with count_percent and value_percent
                  (each with 'long' and 'short' keys)
        """
        # pair is sent as a URL query parameter; timestamp/signature go in the body
        endpoint = f"/api/v1/derivatives/futures/data/stats?pair={pair}"
        return self._make_authenticated_request("POST", endpoint, {})

    def get_futures_current_prices_rt(self) -> Dict[str, Any]:
        """Get real-time current prices for all active futures instruments.

        Returns a snapshot with per-instrument fields including last price (ls),
        mark price (mp), high (h), low (l), volume (v), price change percent (pc),
        funding rate (fr), and various timestamps.

        Returns:
            Dict with 'ts' (timestamp), 'vs' (version), and 'prices' mapping
            each instrument pair to its current price data.
        """
        return self._make_public_market_data_request(
            "/market_data/v3/current_prices/futures/rt", {}
        )

    def get_futures_trades(self, pair: str, from_date: str, to_date: str,
                            page: int = 1, size: int = 10,
                            order_id: str = None,
                            margin_currencies: list = None) -> Dict[str, Any]:
        """Get futures trade history for a pair within a date range.

        Args:
            pair: Instrument pair, e.g. 'B-ID_USDT'.
            from_date: Start date in 'YYYY-MM-DD' format.
            to_date: End date in 'YYYY-MM-DD' format.
            page: Page number (default: 1).
            size: Number of records per page (default: 10).
            order_id: Optional order ID to filter trades for a specific order.
            margin_currencies: List of margin modes, e.g. ['USDT'] or ['INR', 'USDT'].
                Defaults to ['USDT'].

        Returns:
            List of trade objects with price, quantity, fees, side, etc.
        """
        if margin_currencies is None:
            margin_currencies = ["USDT"]
        payload: Dict[str, Any] = {
            "pair": pair,
            "from_date": from_date,
            "to_date": to_date,
            "page": str(page),
            "size": str(size),
            "margin_currency_short_name": margin_currencies
        }
        if order_id:
            payload["order_id"] = order_id
        return self._make_authenticated_request(
            "POST", "/exchange/v1/derivatives/futures/trades", payload
        )

    def get_futures_transactions(self, stage: str, page: int = 1, size: int = 10,
                                  margin_currencies: list = None) -> Dict[str, Any]:
        """Get a list of futures transactions filtered by stage.

        Args:
            stage: Transaction stage to filter by. Possible values:
                'funding'     - Transactions due to funding.
                'default'     - Transactions for standard orders (non-exit, non-tpsl).
                'exit'        - Transactions for quick exit orders.
                'tpsl_exit'   - Transactions for full-position TP/SL exit orders.
                'liquidation' - Transactions for liquidation orders.
                'all'         - All transaction types.
            page: Page number (default: 1).
            size: Number of records per page (default: 10).
            margin_currencies: List of margin modes, e.g. ['USDT'] or ['INR', 'USDT'].
                Defaults to ['USDT'].

        Returns:
            List of transaction objects.
        """
        if margin_currencies is None:
            margin_currencies = ["USDT"]
        payload = {
            "stage": stage,
            "page": str(page),
            "size": str(size),
            "margin_currency_short_name": margin_currencies
        }
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/transactions",
            payload
        )

    def create_futures_tpsl(self, position_id: str,
                             take_profit: dict = None,
                             stop_loss: dict = None) -> Dict[str, Any]:
        """Create Take Profit and/or Stop Loss orders for a futures position.

        At least one of take_profit or stop_loss must be provided.

        Args:
            position_id: The position ID to attach TP/SL orders to.
            take_profit: Dict with keys:
                - stop_price (str, required): Trigger price for the TP order.
                - order_type (str, required): 'take_profit_market' or
                  'take_profit_limit'.
                - limit_price (str, optional): Limit price (not supported yet).
            stop_loss: Dict with keys:
                - stop_price (str, required): Trigger price for the SL order.
                - order_type (str, required): 'stop_market' or 'stop_limit'.
                - limit_price (str, optional): Limit price for stop_limit orders.

        Returns:
            Dict with 'take_profit' and/or 'stop_loss' order details, including
            a 'success' flag and 'error' message on failure.
        """
        if not take_profit and not stop_loss:
            raise ValueError("At least one of 'take_profit' or 'stop_loss' must be provided.")
        payload: Dict[str, Any] = {"id": position_id}
        if take_profit:
            payload["take_profit"] = take_profit
        if stop_loss:
            payload["stop_loss"] = stop_loss
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/create_tpsl",
            payload
        )

    def exit_futures_position(self, position_id: str) -> Dict[str, Any]:
        """Exit a futures position by placing a market order to close it entirely.

        Large positions may be auto-split into smaller orders; all split parts
        share the same group_id returned in the response.

        Args:
            position_id: The position ID to exit.

        Returns:
            Dict with message, status, code, and data.group_id.
        """
        payload = {
            "id": position_id
        }
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/exit",
            payload
        )

    def cancel_all_futures_open_orders_for_position(self, position_id: str) -> Dict[str, Any]:
        """Cancel all open orders for a specific futures position.

        Args:
            position_id: The position ID whose open orders should be cancelled.

        Returns:
            Dict with message/status/code indicating success.
        """
        payload = {
            "id": position_id
        }
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/cancel_all_open_orders_for_position",
            payload
        )

    def cancel_all_futures_open_orders(self, margin_currencies: list = None) -> Dict[str, Any]:
        """Cancel all open futures orders across all positions.

        Args:
            margin_currencies: List of margin modes to cancel orders for,
                e.g. ['USDT'] or ['INR', 'USDT']. Defaults to ['USDT'].

        Returns:
            Dict with message/status/code indicating success.
        """
        if margin_currencies is None:
            margin_currencies = ["USDT"]
        payload = {
            "margin_currency_short_name": margin_currencies
        }
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/cancel_all_open_orders",
            payload
        )

    def remove_futures_margin(self, position_id: str, amount: float) -> Dict[str, Any]:
        """Remove margin from a futures position to increase effective leverage.

        Args:
            position_id: The position ID to remove margin from.
            amount: Amount of margin to remove. In USDT for USDT-margined futures,
                in INR for INR-margined futures. Removing margin increases the risk
                of the position (liquidation price will be updated).

        Returns:
            Dict with message/status/code indicating success.
        """
        payload = {
            "id": position_id,
            "amount": amount
        }
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/remove_margin",
            payload
        )

    def add_futures_margin(self, position_id: str, amount: float) -> Dict[str, Any]:
        """Add margin to a futures position to decrease effective leverage.

        Args:
            position_id: The position ID to add margin to.
            amount: Amount of margin to add. In USDT for USDT-margined futures,
                in INR for INR-margined futures.

        Returns:
            Dict with message/status/code indicating success.
        """
        payload = {
            "id": position_id,
            "amount": amount
        }
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/add_margin",
            payload
        )

    def update_futures_position_leverage(self, leverage: str,
                                         pair: str = None, position_id: str = None,
                                         margin_currency: str = "USDT") -> Dict[str, Any]:
        """Update the leverage for a futures position.

        Use either `pair` or `position_id` to target the position — not both.

        Args:
            leverage: New leverage value as a string, e.g. '5'.
            pair: Instrument pair, e.g. 'B-LTC_USDT'. Use this OR position_id.
            position_id: Position ID. Use this OR pair.
            margin_currency: Futures margin mode ('USDT' or 'INR'). Default 'USDT'.

        Returns:
            Dict with message/status/code indicating success or failure.
        """
        if pair and position_id:
            raise ValueError("Provide either 'pair' or 'position_id', not both.")
        payload: Dict[str, Any] = {
            "leverage": str(leverage),
            "margin_currency_short_name": margin_currency
        }
        if pair:
            payload["pair"] = pair
        if position_id:
            payload["id"] = position_id
        return self._make_authenticated_request(
            "POST",
            "/exchange/v1/derivatives/futures/positions/update_leverage",
            payload
        )

    def get_futures_positions_by_filter(self, page: int = 1, size: int = 10,
                                        pairs: str = None, position_ids: str = None,
                                        margin_currencies: list = None) -> Dict[str, Any]:
        """Get futures positions filtered by pair(s) or position ID(s).

        Use either `pairs` or `position_ids` — not both.

        Args:
            page: Page number (default: 1).
            size: Number of records per page (default: 10).
            pairs: Comma-separated instrument pairs to filter by,
                e.g. 'B-BTC_USDT' or 'B-BTC_USDT,B-ETH_USDT'.
            position_ids: Comma-separated position IDs to filter by,
                e.g. '7830d2d6-0c3d-11ef-9b57-0fb0912383a7'.
            margin_currencies: List of margin modes, e.g. ['USDT'] or ['INR', 'USDT'].
                Defaults to ['USDT'].

        Returns:
            List of futures position objects matching the filter.
        """
        if pairs and position_ids:
            raise ValueError("Provide either 'pairs' or 'position_ids', not both.")
        if margin_currencies is None:
            margin_currencies = ["USDT"]
        payload: Dict[str, Any] = {
            "page": str(page),
            "size": str(size),
            "margin_currency_short_name": margin_currencies
        }
        if pairs:
            payload["pairs"] = pairs
        if position_ids:
            payload["position_ids"] = position_ids
        return self._make_authenticated_request(
            "POST", "/exchange/v1/derivatives/futures/positions", payload
        )

    def close(self):
        """Close the HTTP client."""
        self.client.close()
