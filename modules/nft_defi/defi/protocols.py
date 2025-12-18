import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import aiohttp
from decimal import Decimal

from core.redis_client import redis_client
from config.settings import settings

logger = logging.getLogger(__name__)

class DeFiManager:
    """Manage DeFi protocol integrations"""
    
    def __init__(self):
        self.protocols = {
            'uniswap': UniswapV3(),
            'aave': AaveV3(),
            'compound': CompoundV3(),
            'pancakeswap': PancakeSwap(),
            'curve': CurveFinance(),
            'balancer': BalancerV2()
        }
        
    async def get_wallet_positions(self, wallet_address: str, network: str = 'ethereum') -> Dict:
        """Get all DeFi positions for a wallet"""
        try:
            cache_key = f"defi_positions:{wallet_address}:{network}"
            cached = await redis_client.cache_get(cache_key)
            if cached:
                return cached
            
            positions = {
                'lending': [],
                'liquidity': [],
                'staking': [],
                'yield_farming': [],
                'total_value_usd': 0
            }
            
            # Get lending positions
            lending_positions = await self.get_lending_positions(wallet_address, network)
            positions['lending'] = lending_positions
            
            # Get liquidity positions
            liquidity_positions = await self.get_liquidity_positions(wallet_address, network)
            positions['liquidity'] = liquidity_positions
            
            # Get staking positions
            staking_positions = await self.get_staking_positions(wallet_address, network)
            positions['staking'] = staking_positions
            
            # Calculate total value
            for position_type in ['lending', 'liquidity', 'staking']:
                for position in positions[position_type]:
                    positions['total_value_usd'] += position.get('value_usd', 0)
            
            positions['timestamp'] = datetime.utcnow().isoformat()
            
            # Cache for 2 minutes
            await redis_client.cache_set(cache_key, positions, expire=120)
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get DeFi positions: {e}")
            return {
                'lending': [],
                'liquidity': [],
                'staking': [],
                'yield_farming': [],
                'total_value_usd': 0,
                'error': str(e)
            }
    
    async def get_lending_positions(self, wallet_address: str, network: str = 'ethereum') -> List[Dict]:
        """Get lending/borrowing positions from Aave and Compound"""
        positions = []
        
        try:
            # Aave positions
            aave_positions = await self.protocols['aave'].get_positions(wallet_address, network)
            positions.extend(aave_positions)
            
            # Compound positions
            compound_positions = await self.protocols['compound'].get_positions(wallet_address, network)
            positions.extend(compound_positions)
            
        except Exception as e:
            logger.error(f"Failed to get lending positions: {e}")
        
        return positions
    
    async def get_liquidity_positions(self, wallet_address: str, network: str = 'ethereum') -> List[Dict]:
        """Get liquidity provider positions"""
        positions = []
        
        try:
            # Uniswap positions
            uniswap_positions = await self.protocols['uniswap'].get_positions(wallet_address, network)
            positions.extend(uniswap_positions)
            
            # Curve positions
            curve_positions = await self.protocols['curve'].get_positions(wallet_address, network)
            positions.extend(curve_positions)
            
            # Balancer positions
            balancer_positions = await self.protocols['balancer'].get_positions(wallet_address, network)
            positions.extend(balancer_positions)
            
        except Exception as e:
            logger.error(f"Failed to get liquidity positions: {e}")
        
        return positions
    
    async def get_staking_positions(self, wallet_address: str, network: str = 'ethereum') -> List[Dict]:
        """Get staking positions"""
        positions = []
        
        try:
            # Check for popular staking tokens
            staking_tokens = [
                ('0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84', 'stETH', 'Lido Staked ETH'),
                ('0x5E8422345238F34275888049021821E8E08CAa1f', 'frxETH', 'Frax ETH'),
                ('0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0', 'wstETH', 'Wrapped stETH')
            ]
            
            for token_address, symbol, name in staking_tokens:
                try:
                    # Check balance
                    balance = await self._get_token_balance(wallet_address, token_address, network)
                    if balance > 0:
                        # Get staking APR
                        apr = await self._get_staking_apr(symbol, network)
                        
                        positions.append({
                            'protocol': 'Lido' if 'stETH' in symbol else 'Frax',
                            'token': symbol,
                            'token_address': token_address,
                            'name': name,
                            'balance': balance,
                            'value_usd': balance * 2500,  # Mock ETH price
                            'apr': apr,
                            'estimated_rewards_usd': (balance * 2500) * (apr / 100) / 365,  # Daily
                            'network': network
                        })
                        
                except Exception as e:
                    logger.debug(f"Failed to get staking position for {symbol}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Failed to get staking positions: {e}")
        
        return positions
    
    async def get_token_swap_quote(self, from_token: str, to_token: str, amount: float, network: str = 'ethereum') -> Dict:
        """Get token swap quote from multiple DEXs"""
        try:
            quotes = []
            
            # Get quote from Uniswap
            uniswap_quote = await self.protocols['uniswap'].get_swap_quote(from_token, to_token, amount, network)
            if uniswap_quote:
                quotes.append(uniswap_quote)
            
            # Get quote from PancakeSwap (for BSC)
            if network == 'bsc':
                pancakeswap_quote = await self.protocols['pancakeswap'].get_swap_quote(from_token, to_token, amount, network)
                if pancakeswap_quote:
                    quotes.append(pancakeswap_quote)
            
            # Find best quote
            if quotes:
                best_quote = max(quotes, key=lambda x: x.get('amount_out', 0))
                best_quote['all_quotes'] = quotes
                return best_quote
            
            return {'error': 'No quotes available'}
            
        except Exception as e:
            logger.error(f"Failed to get swap quote: {e}")
            return {'error': str(e)}
    
    async def get_yield_opportunities(self, network: str = 'ethereum') -> List[Dict]:
        """Get top yield farming opportunities"""
        try:
            cache_key = f"yield_opportunities:{network}"
            cached = await redis_client.cache_get(cache_key)
            if cached:
                return cached
            
            opportunities = []
            
            # Get from various protocols
            protocols_to_check = ['aave', 'compound', 'curve', 'balancer']
            
            for protocol_name in protocols_to_check:
                try:
                    protocol_opportunities = await self.protocols[protocol_name].get_yield_opportunities(network)
                    opportunities.extend(protocol_opportunities)
                except Exception as e:
                    logger.debug(f"Failed to get opportunities from {protocol_name}: {e}")
                    continue
            
            # Sort by APR (highest first)
            opportunities.sort(key=lambda x: x.get('apr', 0), reverse=True)
            
            # Cache for 5 minutes
            await redis_client.cache_set(cache_key, opportunities, expire=300)
            
            return opportunities[:10]  # Return top 10
            
        except Exception as e:
            logger.error(f"Failed to get yield opportunities: {e}")
            return []
    
    async def _get_token_balance(self, wallet_address: str, token_address: str, network: str) -> float:
        """Get token balance (simplified)"""
        # In production, use actual contract calls
        return 0.0
    
    async def _get_staking_apr(self, token_symbol: str, network: str) -> float:
        """Get staking APR (simplified)"""
        aprs = {
            'stETH': 4.2,
            'frxETH': 3.8,
            'wstETH': 4.1
        }
        return aprs.get(token_symbol, 3.0)

class UniswapV3:
    """Uniswap V3 integration"""
    
    async def get_positions(self, wallet_address: str, network: str) -> List[Dict]:
        """Get Uniswap V3 LP positions"""
        # Simplified - in production use The Graph or Uniswap API
        return []
    
    async def get_swap_quote(self, from_token: str, to_token: str, amount: float, network: str) -> Optional[Dict]:
        """Get swap quote from Uniswap"""
        try:
            # Mock quote
            exchange_rates = {
                ('ETH', 'USDC'): 2500,
                ('USDC', 'ETH'): 0.0004,
                ('ETH', 'USDT'): 2500,
                ('USDT', 'ETH'): 0.0004,
            }
            
            rate = exchange_rates.get((from_token.upper(), to_token.upper()))
            if rate:
                amount_out = amount * rate
                fee = amount_out * 0.003  # 0.3% Uniswap fee
                
                return {
                    'protocol': 'Uniswap V3',
                    'from_token': from_token,
                    'to_token': to_token,
                    'amount_in': amount,
                    'amount_out': amount_out - fee,
                    'fee': fee,
                    'slippage': 0.5,  # 0.5%
                    'network': network,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Uniswap quote error: {e}")
            return None
    
    async def get_yield_opportunities(self, network: str) -> List[Dict]:
        """Get Uniswap yield opportunities"""
        # Mock data
        return [{
            'protocol': 'Uniswap V3',
            'pair': 'ETH/USDC',
            'apr': 12.5,
            'tvl_usd': 1250000000,
            'risk': 'medium',
            'network': network
        }]

class AaveV3:
    """Aave V3 integration"""
    
    async def get_positions(self, wallet_address: str, network: str) -> List[Dict]:
        """Get Aave lending/borrowing positions"""
        # Mock data
        return [{
            'protocol': 'Aave V3',
            'type': 'supply',
            'token': 'USDC',
            'amount': 1000,
            'value_usd': 1000,
            'apy': 3.2,
            'network': network
        }]
    
    async def get_yield_opportunities(self, network: str) -> List[Dict]:
        """Get Aave yield opportunities"""
        return [{
            'protocol': 'Aave V3',
            'token': 'USDC',
            'apy': 3.2,
            'tvl_usd': 850000000,
            'risk': 'low',
            'network': network
        }]

class CompoundV3:
    """Compound V3 integration"""
    
    async def get_positions(self, wallet_address: str, network: str) -> List[Dict]:
        # Mock data
        return []
    
    async def get_yield_opportunities(self, network: str) -> List[Dict]:
        return []

class PancakeSwap:
    """PancakeSwap integration (BSC)"""
    
    async def get_swap_quote(self, from_token: str, to_token: str, amount: float, network: str) -> Optional[Dict]:
        # Mock data for BSC
        return {
            'protocol': 'PancakeSwap',
            'from_token': from_token,
            'to_token': to_token,
            'amount_in': amount,
            'amount_out': amount * 0.99,  # 1% fee
            'fee': amount * 0.01,
            'slippage': 0.3,
            'network': network
        }
    
    async def get_yield_opportunities(self, network: str) -> List[Dict]:
        return [{
            'protocol': 'PancakeSwap',
            'pair': 'BNB/BUSD',
            'apr': 28.5,
            'tvl_usd': 450000000,
            'risk': 'high',
            'network': network
        }]

class CurveFinance:
    """Curve Finance integration"""
    
    async def get_positions(self, wallet_address: str, network: str) -> List[Dict]:
        return []
    
    async def get_yield_opportunities(self, network: str) -> List[Dict]:
        return []

class BalancerV2:
    """Balancer V2 integration"""
    
    async def get_positions(self, wallet_address: str, network: str) -> List[Dict]:
        return []
    
    async def get_yield_opportunities(self, network: str) -> List[Dict]:
        return []
