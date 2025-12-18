import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import hmac
import hashlib
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3, AsyncWeb3
from web3.exceptions import TransactionNotFound
import aiohttp

from core.redis_client import redis_client
from core.database import get_db
from core.exceptions import WalletError, ValidationError
from config.settings import settings

logger = logging.getLogger(__name__)

class WalletManager:
    """Manage multi-chain wallet connections and operations"""
    
    def __init__(self):
        # Initialize Web3 providers for different networks
        self.providers = {
            'ethereum': self._init_ethereum_provider(),
            'polygon': self._init_polygon_provider(),
            'bsc': self._init_bsc_provider(),
            'solana': self._init_solana_provider(),
            'arbitrum': self._init_arbitrum_provider()
        }
        
        # WalletConnect project ID (get from https://cloud.walletconnect.com)
        self.walletconnect_project_id = settings.WALLETCONNECT_PROJECT_ID
        
        # Supported networks
        self.supported_networks = {
            'ethereum': {
                'chain_id': 1,
                'name': 'Ethereum Mainnet',
                'currency': 'ETH',
                'rpc_url': settings.ETH_RPC_URL,
                'explorer': 'https://etherscan.io'
            },
            'polygon': {
                'chain_id': 137,
                'name': 'Polygon',
                'currency': 'MATIC',
                'rpc_url': settings.POLYGON_RPC_URL,
                'explorer': 'https://polygonscan.com'
            },
            'bsc': {
                'chain_id': 56,
                'name': 'BNB Smart Chain',
                'currency': 'BNB',
                'rpc_url': settings.BSC_RPC_URL,
                'explorer': 'https://bscscan.com'
            },
            'arbitrum': {
                'chain_id': 42161,
                'name': 'Arbitrum One',
                'currency': 'ETH',
                'rpc_url': settings.ARBITRUM_RPC_URL,
                'explorer': 'https://arbiscan.io'
            }
        }
        
        # Initialize session for WalletConnect
        self.session = None
    
    def _init_ethereum_provider(self):
        """Initialize Ethereum Web3 provider"""
        if settings.ETH_RPC_URL:
            return Web3(Web3.HTTPProvider(settings.ETH_RPC_URL))
        return None
    
    def _init_polygon_provider(self):
        """Initialize Polygon Web3 provider"""
        if settings.POLYGON_RPC_URL:
            return Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
        return None
    
    def _init_bsc_provider(self):
        """Initialize BSC Web3 provider"""
        if settings.BSC_RPC_URL:
            return Web3(Web3.HTTPProvider(settings.BSC_RPC_URL))
        return None
    
    def _init_arbitrum_provider(self):
        """Initialize Arbitrum Web3 provider"""
        if settings.ARBITRUM_RPC_URL:
            return Web3(Web3.HTTPProvider(settings.ARBITRUM_RPC_URL))
        return None
    
    def _init_solana_provider(self):
        """Initialize Solana provider (placeholder)"""
        # Will be implemented with actual Solana SDK
        return None
    
    async def connect_wallet(self, user_id: int, wallet_address: str, network: str = 'ethereum') -> Dict:
        """Connect user's wallet to the platform"""
        try:
            # Validate wallet address
            if not self.validate_address(wallet_address, network):
                raise ValidationError(f"Invalid {network} wallet address")
            
            # Store wallet connection
            with get_db() as db:
                from modules.nft_defi.models import UserWallet
                
                # Check if wallet already exists
                existing_wallet = db.query(UserWallet).filter(
                    UserWallet.user_id == user_id,
                    UserWallet.network == network
                ).first()
                
                if existing_wallet:
                    # Update existing wallet
                    existing_wallet.address = wallet_address
                    existing_wallet.last_connected = datetime.utcnow()
                    existing_wallet.is_connected = True
                else:
                    # Create new wallet record
                    wallet = UserWallet(
                        user_id=user_id,
                        address=wallet_address,
                        network=network,
                        is_connected=True,
                        last_connected=datetime.utcnow(),
                        created_at=datetime.utcnow()
                    )
                    db.add(wallet)
                
                db.commit()
            
            # Fetch wallet balance
            balance = await self.get_balance(wallet_address, network)
            
            # Cache wallet info
            cache_key = f"wallet:{user_id}:{network}"
            await redis_client.cache_set(cache_key, {
                'address': wallet_address,
                'network': network,
                'balance': balance,
                'connected_at': datetime.utcnow().isoformat()
            }, expire=3600)
            
            # Publish wallet connection event
            await redis_client.publish(
                f"wallet:connected:{user_id}",
                json.dumps({
                    'user_id': user_id,
                    'wallet_address': wallet_address,
                    'network': network,
                    'balance': balance,
                    'timestamp': datetime.utcnow().isoformat()
                })
            )
            
            logger.info(f"User {user_id} connected wallet {wallet_address} on {network}")
            
            return {
                'success': True,
                'wallet_address': wallet_address,
                'network': network,
                'balance': balance,
                'message': 'Wallet connected successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to connect wallet: {e}")
            raise WalletError(f"Failed to connect wallet: {str(e)}")
    
    async def get_balance(self, wallet_address: str, network: str = 'ethereum') -> Dict:
        """Get wallet balance including native token and ERC20 tokens"""
        try:
            provider = self.providers.get(network)
            if not provider:
                raise WalletError(f"Network {network} not supported")
            
            # Get native token balance
            balance_wei = provider.eth.get_balance(wallet_address)
            native_balance = provider.from_wei(balance_wei, 'ether')
            
            # Get ERC20 token balances (top 20 by value)
            erc20_balances = await self.get_erc20_balances(wallet_address, network)
            
            # Get NFT count
            nft_count = await self.get_nft_count(wallet_address, network)
            
            # Calculate total portfolio value (simplified)
            total_value = float(native_balance)
            for token in erc20_balances:
                total_value += token.get('value_usd', 0)
            
            return {
                'native_balance': float(native_balance),
                'native_currency': self.supported_networks[network]['currency'],
                'erc20_tokens': erc20_balances,
                'nft_count': nft_count,
                'total_value_usd': total_value,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {
                'native_balance': 0,
                'native_currency': self.supported_networks[network]['currency'],
                'erc20_tokens': [],
                'nft_count': 0,
                'total_value_usd': 0,
                'error': str(e)
            }
    
    async def get_erc20_balances(self, wallet_address: str, network: str) -> List[Dict]:
        """Get ERC20 token balances using Covalent API"""
        try:
            # Common ERC20 tokens by network
            common_tokens = {
                'ethereum': [
                    {'address': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'symbol': 'USDT', 'decimals': 6},
                    {'address': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'symbol': 'USDC', 'decimals': 6},
                    {'address': '0x6B175474E89094C44Da98b954EedeAC495271d0F', 'symbol': 'DAI', 'decimals': 18},
                    {'address': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', 'symbol': 'WBTC', 'decimals': 8},
                    {'address': '0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0', 'symbol': 'MATIC', 'decimals': 18},
                    {'address': '0x514910771AF9Ca656af840dff83E8264EcF986CA', 'symbol': 'LINK', 'decimals': 18},
                ],
                'polygon': [
                    {'address': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F', 'symbol': 'USDT', 'decimals': 6},
                    {'address': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', 'symbol': 'USDC', 'decimals': 6},
                    {'address': '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063', 'symbol': 'DAI', 'decimals': 18},
                    {'address': '0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6', 'symbol': 'WBTC', 'decimals': 8},
                ],
                'bsc': [
                    {'address': '0x55d398326f99059fF775485246999027B3197955', 'symbol': 'USDT', 'decimals': 18},
                    {'address': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d', 'symbol': 'USDC', 'decimals': 18},
                    {'address': '0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3', 'symbol': 'DAI', 'decimals': 18},
                    {'address': '0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c', 'symbol': 'BTCB', 'decimals': 18},
                ]
            }
            
            balances = []
            provider = self.providers[network]
            
            for token in common_tokens.get(network, []):
                try:
                    # ERC20 ABI for balanceOf
                    erc20_abi = [
                        {
                            "constant": True,
                            "inputs": [{"name": "_owner", "type": "address"}],
                            "name": "balanceOf",
                            "outputs": [{"name": "balance", "type": "uint256"}],
                            "type": "function"
                        },
                        {
                            "constant": True,
                            "inputs": [],
                            "name": "decimals",
                            "outputs": [{"name": "", "type": "uint8"}],
                            "type": "function"
                        }
                    ]
                    
                    # Create contract instance
                    contract = provider.eth.contract(
                        address=provider.to_checksum_address(token['address']),
                        abi=erc20_abi
                    )
                    
                    # Get balance
                    balance = contract.functions.balanceOf(wallet_address).call()
                    decimals = token['decimals']
                    
                    # Convert to readable amount
                    amount = balance / (10 ** decimals)
                    
                    if amount > 0:
                        # Get token price (simplified - in production use price feed)
                        price_usd = await self.get_token_price(token['symbol'], network)
                        
                        balances.append({
                            'symbol': token['symbol'],
                            'address': token['address'],
                            'balance': amount,
                            'value_usd': amount * price_usd if price_usd else 0,
                            'price_usd': price_usd
                        })
                        
                except Exception as e:
                    logger.debug(f"Failed to get balance for {token['symbol']}: {e}")
                    continue
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get ERC20 balances: {e}")
            return []
    
    async def get_token_price(self, symbol: str, network: str) -> Optional[float]:
        """Get token price from CoinGecko (simplified)"""
        # In production, use actual price feeds
        prices = {
            'ETH': 2500, 'MATIC': 0.80, 'BNB': 300,
            'USDT': 1.0, 'USDC': 1.0, 'DAI': 1.0,
            'WBTC': 42000, 'BTCB': 42000, 'LINK': 15
        }
        return prices.get(symbol.upper())
    
    async def get_nft_count(self, wallet_address: str, network: str) -> int:
        """Get NFT count using Alchemy API"""
        try:
            # Use Alchemy NFT API
            if network == 'ethereum' and settings.ALCHEMY_API_KEY:
                url = f"https://eth-mainnet.g.alchemy.com/nft/v2/{settings.ALCHEMY_API_KEY}/getNFTs"
                params = {
                    'owner': wallet_address,
                    'withMetadata': 'false'
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            return len(data.get('ownedNfts', []))
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get NFT count: {e}")
            return 0
    
    def validate_address(self, address: str, network: str) -> bool:
        """Validate wallet address for specific network"""
        try:
            if network in ['ethereum', 'polygon', 'arbitrum']:
                return Web3.is_address(address)
            elif network == 'bsc':
                return Web3.is_address(address)
            elif network == 'solana':
                # Solana address validation
                return len(address) == 44 and address.isalnum()
            return False
        except:
            return False
    
    async def create_walletconnect_session(self, user_id: int) -> Dict:
        """Create WalletConnect v2 session for mobile wallet connection"""
        try:
            # In production, use WalletConnect Cloud API
            # This is a simplified version
            
            session_id = f"wc_{int(time.time())}_{user_id}"
            
            # Create session data
            session_data = {
                'session_id': session_id,
                'user_id': user_id,
                'status': 'pending',
                'expires_at': datetime.utcnow() + timedelta(minutes=15),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Store session
            await redis_client.cache_set(
                f"walletconnect:session:{session_id}",
                session_data,
                expire=900  # 15 minutes
            )
            
            # Generate connection URI (simplified)
            connection_uri = f"wc:{session_id}@1?bridge=https://bridge.walletconnect.org&key=test_key"
            
            # QR code data for Telegram
            qr_data = {
                'session_id': session_id,
                'connection_uri': connection_uri,
                'deep_link': f"https://link.walletconnect.org/wc?uri={connection_uri}",
                'expires_in': 900
            }
            
            return {
                'success': True,
                'session_id': session_id,
                'qr_code_data': qr_data,
                'message': 'Scan QR code with your wallet app'
            }
            
        except Exception as e:
            logger.error(f"Failed to create WalletConnect session: {e}")
            raise WalletError(f"Failed to create wallet connection: {str(e)}")
