import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from web3 import Web3
from web3.exceptions import TransactionNotFound, TimeExhausted

from core.redis_client import redis_client
from core.exceptions import WalletError, ValidationError
from config.settings import settings

logger = logging.getLogger(__name__)

class TokenSwapManager:
    """Manage token swaps across multiple DEXs"""
    
    def __init__(self, wallet_manager):
        self.wallet_manager = wallet_manager
        self.dex_routers = {
            'uniswap_v3': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
            'uniswap_v2': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
            'sushiswap': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',
            'pancakeswap': '0x10ED43C718714eb63d5aA57B78B54704E256024E',
            'curve': '0x99a58482BD75cbab83b27EC03CA68fF489b5788f'
        }
        
    async def execute_swap(self, user_id: int, swap_params: Dict) -> Dict:
        """Execute token swap"""
        try:
            # Validate swap parameters
            self._validate_swap_params(swap_params)
            
            # Get user's wallet
            wallet = await self._get_user_wallet(user_id, swap_params['network'])
            if not wallet:
                raise WalletError("Wallet not connected")
            
            # Get best swap route
            best_route = await self._find_best_route(swap_params)
            if not best_route:
                raise ValidationError("No valid swap route found")
            
            # Simulate swap (check if it will succeed)
            simulation = await self._simulate_swap(wallet['address'], best_route)
            if not simulation.get('success'):
                raise ValidationError(f"Swap simulation failed: {simulation.get('error')}")
            
            # In paper trading mode, just record the swap
            if settings.PAPER_TRADING_ONLY:
                return await self._record_paper_swap(user_id, swap_params, best_route, simulation)
            
            # In production, execute actual swap
            # return await self._execute_real_swap(wallet, best_route, swap_params)
            
            # For now, return simulated result
            return {
                'success': True,
                'transaction_hash': '0x' + '0' * 64,  # Mock hash
                'amount_in': swap_params['amount'],
                'amount_out': simulation.get('amount_out', 0),
                'fee': simulation.get('fee', 0),
                'slippage': simulation.get('slippage', 0),
                'network': swap_params['network'],
                'timestamp': datetime.utcnow().isoformat(),
                'note': 'Paper trading mode - swap simulated'
            }
            
        except Exception as e:
            logger.error(f"Swap execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _validate_swap_params(self, params: Dict):
        """Validate swap parameters"""
        required = ['from_token', 'to_token', 'amount', 'network']
        for field in required:
            if field not in params:
                raise ValidationError(f"Missing required field: {field}")
        
        if params['amount'] <= 0:
            raise ValidationError("Amount must be greater than 0")
        
        if params['network'] not in self.wallet_manager.supported_networks:
            raise ValidationError(f"Unsupported network: {params['network']}")
    
    async def _get_user_wallet(self, user_id: int, network: str) -> Optional[Dict]:
        """Get user's connected wallet"""
        cache_key = f"wallet:{user_id}:{network}"
        return await redis_client.cache_get(cache_key)
    
    async def _find_best_route(self, swap_params: Dict) -> Optional[Dict]:
        """Find best swap route across multiple DEXs"""
        routes = []
        
        # Get quotes from different DEXs
        dex_providers = ['uniswap', 'sushiswap']
        if swap_params['network'] == 'bsc':
            dex_providers.append('pancakeswap')
        
        for dex in dex_providers:
            try:
                quote = await self._get_dex_quote(dex, swap_params)
                if quote:
                    routes.append({
                        'dex': dex,
                        'quote': quote,
                        'score': self._calculate_route_score(quote)
                    })
            except Exception as e:
                logger.debug(f"Failed to get quote from {dex}: {e}")
                continue
        
        if not routes:
            return None
        
        # Select route with highest score
        best_route = max(routes, key=lambda x: x['score'])
        return best_route
    
    async def _get_dex_quote(self, dex: str, swap_params: Dict) -> Optional[Dict]:
        """Get swap quote from specific DEX"""
        # Mock implementation
        # In production, integrate with 1inch, Paraswap, or direct DEX APIs
        
        from_token = swap_params['from_token']
        to_token = swap_params['to_token']
        amount = swap_params['amount']
        
        # Mock exchange rates
        rates = {
            ('ETH', 'USDC'): 2500,
            ('USDC', 'ETH'): 0.0004,
            ('ETH', 'USDT'): 2495,
            ('USDT', 'ETH'): 0.000401,
            ('MATIC', 'USDC'): 0.80,
            ('USDC', 'MATIC'): 1.25,
        }
        
        key = (from_token.upper(), to_token.upper())
        if key in rates:
            rate = rates[key]
            
            # DEX-specific fees
            dex_fees = {
                'uniswap': 0.003,  # 0.3%
                'sushiswap': 0.003,
                'pancakeswap': 0.0025,  # 0.25%
            }
            
            fee_percent = dex_fees.get(dex, 0.003)
            amount_out = amount * rate * (1 - fee_percent)
            fee = amount * rate * fee_percent
            
            return {
                'amount_in': amount,
                'amount_out': amount_out,
                'fee': fee,
                'fee_percent': fee_percent * 100,
                'exchange_rate': rate,
                'slippage': 0.5  # 0.5%
            }
        
        return None
    
    def _calculate_route_score(self, quote: Dict) -> float:
        """Calculate route score based on multiple factors"""
        score = 0
        
        # Higher output amount = higher score
        if quote.get('amount_out'):
            score += quote['amount_out'] * 0.1
        
        # Lower fee = higher score
        if quote.get('fee_percent'):
            score += (100 - quote['fee_percent']) * 10
        
        # Lower slippage = higher score
        if quote.get('slippage'):
            score += (100 - quote['slippage']) * 5
        
        return score
    
    async def _simulate_swap(self, wallet_address: str, route: Dict) -> Dict:
        """Simulate swap to check for success"""
        # Mock simulation
        # In production, use Tenderly or local simulation
        
        return {
            'success': True,
            'amount_out': route['quote'].get('amount_out', 0),
            'fee': route['quote'].get('fee', 0),
            'gas_estimate': 150000,  # 150k gas
            'gas_price_gwei': 30,  # 30 Gwei
            'total_cost_eth': 0.0045,  # 150k * 30 Gwei
            'slippage': route['quote'].get('slippage', 0)
        }
    
    async def _record_paper_swap(self, user_id: int, swap_params: Dict, route: Dict, simulation: Dict) -> Dict:
        """Record paper swap for tracking"""
        from core.database import get_db
        
        with get_db() as db:
            from modules.nft_defi.models import PaperSwap
            
            swap = PaperSwap(
                user_id=user_id,
                from_token=swap_params['from_token'],
                to_token=swap_params['to_token'],
                amount_in=swap_params['amount'],
                amount_out=simulation.get('amount_out', 0),
                dex=route.get('dex', 'unknown'),
                network=swap_params['network'],
                fee=simulation.get('fee', 0),
                slippage=simulation.get('slippage', 0),
                status='completed',
                executed_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            
            db.add(swap)
            db.commit()
            
            # Update portfolio value
            await self._update_portfolio_value(user_id, swap_params['network'])
            
            return {
                'success': True,
                'swap_id': swap.id,
                'amount_in': swap.amount_in,
                'amount_out': swap.amount_out,
                'fee': swap.fee,
                'slippage': swap.slippage,
                'network': swap.network,
                'timestamp': swap.executed_at.isoformat(),
                'note': 'Paper trade recorded'
            }
    
    async def _update_portfolio_value(self, user_id: int, network: str):
        """Update user's portfolio value after swap"""
        # This would recalculate portfolio value
        # For now, just clear cache
        cache_key = f"portfolio:{user_id}:{network}"
        await redis_client.redis.delete(cache_key)
    
    async def get_swap_history(self, user_id: int, network: str = None, limit: int = 50) -> List[Dict]:
        """Get user's swap history"""
        from core.database import get_db
        
        with get_db() as db:
            from modules.nft_defi.models import PaperSwap
            
            query = db.query(PaperSwap).filter(PaperSwap.user_id == user_id)
            
            if network:
                query = query.filter(PaperSwap.network == network)
            
            swaps = query.order_by(PaperSwap.executed_at.desc()).limit(limit).all()
            
            return [
                {
                    'swap_id': swap.id,
                    'from_token': swap.from_token,
                    'to_token': swap.to_token,
                    'amount_in': float(swap.amount_in),
                    'amount_out': float(swap.amount_out),
                    'dex': swap.dex,
                    'network': swap.network,
                    'fee': float(swap.fee),
                    'slippage': float(swap.slippage),
                    'status': swap.status,
                    'executed_at': swap.executed_at.isoformat() if swap.executed_at else None
                }
                for swap in swaps
            ]
    
    async def get_liquidity_pools(self, network: str = 'ethereum') -> List[Dict]:
        """Get available liquidity pools"""
        # Mock data
        pools = {
            'ethereum': [
                {
                    'dex': 'uniswap_v3',
                    'pair': 'ETH/USDC',
                    'fee_tier': 0.05,  # 0.05%
                    'tvl_usd': 1250000000,
                    'apr': 12.5,
                    'volume_24h_usd': 85000000
                },
                {
                    'dex': 'uniswap_v3',
                    'pair': 'ETH/USDT',
                    'fee_tier': 0.30,  # 0.3%
                    'tvl_usd': 850000000,
                    'apr': 8.2,
                    'volume_24h_usd': 45000000
                },
                {
                    'dex': 'curve',
                    'pair': '3pool (DAI/USDC/USDT)',
                    'fee_tier': 0.04,
                    'tvl_usd': 950000000,
                    'apr': 3.5,
                    'volume_24h_usd': 28000000
                }
            ],
            'polygon': [
                {
                    'dex': 'uniswap_v3',
                    'pair': 'MATIC/USDC',
                    'fee_tier': 0.30,
                    'tvl_usd': 85000000,
                    'apr': 15.2,
                    'volume_24h_usd': 12000000
                }
            ],
            'bsc': [
                {
                    'dex': 'pancakeswap',
                    'pair': 'BNB/BUSD',
                    'fee_tier': 0.25,
                    'tvl_usd': 450000000,
                    'apr': 28.5,
                    'volume_24h_usd': 85000000
                }
            ]
        }
        
        return pools.get(network, [])
