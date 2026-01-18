"""
CoinGecko API Service for fetching live crypto rates
"""
import requests
from decimal import Decimal
from typing import Dict, List, Optional
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class CoinGeckoService:
    """Service to interact with CoinGecko Free API"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # CoinGecko IDs for supported cryptocurrencies
    SUPPORTED_CRYPTOS = [
        'bitcoin',
        'ethereum', 
        'binancecoin',
        'cardano',
        'solana',
        'ripple',
        'polkadot',
        'dogecoin',
        'tether',
        'usd-coin',
    ]
    
    # Symbol mapping
    SYMBOL_MAP = {
        'bitcoin': 'BTC',
        'ethereum': 'ETH',
        'binancecoin': 'BNB',
        'cardano': 'ADA',
        'solana': 'SOL',
        'ripple': 'XRP',
        'polkadot': 'DOT',
        'dogecoin': 'DOGE',
        'tether': 'USDT',
        'usd-coin': 'USDC',
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
        })
        # USD to Cedis rate (can be made dynamic later)
        self.usd_to_cedis = Decimal('12.50')
    
    def get_simple_price(self, crypto_ids: List[str] = None) -> Dict:
        """
        Fetch simple price data for cryptocurrencies
        
        Args:
            crypto_ids: List of crypto IDs. If None, fetches all supported cryptos
            
        Returns:
            Dict with crypto prices
        """
        if crypto_ids is None:
            crypto_ids = self.SUPPORTED_CRYPTOS
        
        try:
            # Join crypto IDs with comma
            ids = ','.join(crypto_ids)
            
            url = f"{self.BASE_URL}/simple/price"
            params = {
                'ids': ids,
                'vs_currencies': 'usd',
                'include_market_cap': 'true',
                'include_24hr_vol': 'true',
                'include_24hr_change': 'true',
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Error fetching prices from CoinGecko: {e}")
            return {}
    
    def get_market_data(self, crypto_ids: List[str] = None) -> Dict:
        """
        Fetch detailed market data for cryptocurrencies
        
        Args:
            crypto_ids: List of crypto IDs
            
        Returns:
            Dict with detailed market data
        """
        if crypto_ids is None:
            crypto_ids = self.SUPPORTED_CRYPTOS
        
        try:
            # Join crypto IDs with comma
            ids = ','.join(crypto_ids)
            
            url = f"{self.BASE_URL}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'ids': ids,
                'order': 'market_cap_desc',
                'sparkline': 'false',
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Error fetching market data from CoinGecko: {e}")
            return []
    
    def parse_price_data(self, price_data: Dict) -> List[Dict]:
        """
        Parse CoinGecko price data into our format
        
        Args:
            price_data: Raw data from CoinGecko simple/price endpoint
            
        Returns:
            List of parsed rate dictionaries
        """
        parsed_rates = []
        
        for crypto_id, data in price_data.items():
            if crypto_id not in self.SUPPORTED_CRYPTOS:
                continue
            
            usd_price = Decimal(str(data.get('usd', 0)))
            cedis_price = usd_price * self.usd_to_cedis
            
            rate_data = {
                'crypto_id': crypto_id,
                'symbol': self.SYMBOL_MAP.get(crypto_id, crypto_id.upper()),
                'usd_price': usd_price,
                'cedis_price': cedis_price,
                'usd_to_cedis_rate': self.usd_to_cedis,
                'market_cap': Decimal(str(data.get('usd_market_cap', 0))) if data.get('usd_market_cap') else None,
                'volume_24h': Decimal(str(data.get('usd_24h_vol', 0))) if data.get('usd_24h_vol') else None,
                'price_change_24h': Decimal(str(data.get('usd_24h_change', 0))) if data.get('usd_24h_change') else None,
                'price_change_percentage_24h': Decimal(str(data.get('usd_24h_change', 0))) if data.get('usd_24h_change') else None,
            }
            
            parsed_rates.append(rate_data)
        
        return parsed_rates
    
    def get_live_rates(self) -> List[Dict]:
        """
        Get live rates for all supported cryptos
        
        Returns:
            List of rate dictionaries
        """
        price_data = self.get_simple_price()
        if not price_data:
            logger.warning("No price data received from CoinGecko")
            return []
        
        return self.parse_price_data(price_data)
    
    def get_single_rate(self, crypto_id: str) -> Optional[Dict]:
        """
        Get live rate for a single cryptocurrency
        
        Args:
            crypto_id: CoinGecko crypto ID
            
        Returns:
            Rate dictionary or None
        """
        if crypto_id not in self.SUPPORTED_CRYPTOS:
            logger.warning(f"Unsupported crypto ID: {crypto_id}")
            return None
        
        price_data = self.get_simple_price([crypto_id])
        if not price_data:
            return None
        
        parsed = self.parse_price_data(price_data)
        return parsed[0] if parsed else None
    
    def calculate_conversion(self, crypto_id: str, amount: Decimal, 
                           direction: str = 'crypto_to_cedis') -> Optional[Decimal]:
        """
        Calculate conversion between crypto and cedis
        
        Args:
            crypto_id: CoinGecko crypto ID
            amount: Amount to convert
            direction: 'crypto_to_cedis' or 'cedis_to_crypto'
            
        Returns:
            Converted amount or None
        """
        rate_data = self.get_single_rate(crypto_id)
        if not rate_data:
            return None
        
        cedis_price = rate_data['cedis_price']
        
        if direction == 'crypto_to_cedis':
            return amount * cedis_price
        elif direction == 'cedis_to_crypto':
            if cedis_price > 0:
                return amount / cedis_price
        
        return None


# Singleton instance
_coingecko_service = None

def get_coingecko_service() -> CoinGeckoService:
    """Get or create CoinGecko service instance"""
    global _coingecko_service
    if _coingecko_service is None:
        _coingecko_service = CoinGeckoService()
    return _coingecko_service
