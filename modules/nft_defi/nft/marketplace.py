import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import aiohttp
from urllib.parse import urlencode

from core.redis_client import redis_client
from config.settings import settings

logger = logging.getLogger(__name__)

class NFTMarketplace:
    """Integrate with multiple NFT marketplaces"""
    
    def __init__(self):
        self.marketplaces = {
            'opensea': OpenSeaAPI(),
            'looksrare': LooksRareAPI(),
            'x2y2': X2Y2API(),
            'magiceden': MagicEdenAPI(),  # Solana
            'blur': BlurAPI()
        }
        
    async def get_nfts_by_wallet(self, wallet_address: str, network: str = 'ethereum') -> List[Dict]:
        """Get all NFTs owned by a wallet address"""
        try:
            cache_key = f"nfts:{wallet_address}:{network}"
            cached = await redis_client.cache_get(cache_key)
            if cached:
                return cached
            
            nfts = []
            
            if network in ['ethereum', 'polygon', 'arbitrum']:
                # Use Alchemy NFT API
                alchemy_nfts = await self._get_alchemy_nfts(wallet_address, network)
                nfts.extend(alchemy_nfts)
                
                # Also get OpenSea data for better metadata
                opensea_nfts = await self.marketplaces['opensea'].get_nfts(wallet_address, network)
                nfts = self._merge_nft_data(nfts, opensea_nfts)
                
            elif network == 'solana':
                # Use Magic Eden API for Solana
                solana_nfts = await self.marketplaces['magiceden'].get_nfts(wallet_address)
                nfts.extend(solana_nfts)
            
            # Filter and sort
            nfts = self._filter_and_sort_nfts(nfts)
            
            # Cache results
            await redis_client.cache_set(cache_key, nfts, expire=300)
            
            return nfts
            
        except Exception as e:
            logger.error(f"Failed to get NFTs: {e}")
            return []
    
    async def _get_alchemy_nfts(self, wallet_address: str, network: str) -> List[Dict]:
        """Get NFTs using Alchemy API"""
        if not settings.ALCHEMY_API_KEY:
            return []
        
        try:
            chain_map = {
                'ethereum': 'eth-mainnet',
                'polygon': 'polygon-mainnet',
                'arbitrum': 'arb-mainnet'
            }
            
            chain = chain_map.get(network)
            if not chain:
                return []
            
            url = f"https://{chain}.g.alchemy.com/nft/v2/{settings.ALCHEMY_API_KEY}/getNFTs"
            params = {
                'owner': wallet_address,
                'withMetadata': 'true',
                'pageSize': 100
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_alchemy_nfts(data.get('ownedNfts', []), network)
                    else:
                        return []
                        
        except Exception as e:
            logger.error(f"Alchemy API error: {e}")
            return []
    
    def _parse_alchemy_nfts(self, raw_nfts: List, network: str) -> List[Dict]:
        """Parse Alchemy NFT data"""
        nfts = []
        
        for nft in raw_nfts:
            try:
                metadata = nft.get('metadata', {})
                
                nft_data = {
                    'token_id': nft.get('tokenId'),
                    'contract_address': nft.get('contract', {}).get('address'),
                    'name': metadata.get('name') or f"#{nft.get('tokenId')}",
                    'description': metadata.get('description'),
                    'image_url': self._get_nft_image_url(metadata),
                    'collection': {
                        'name': nft.get('contract', {}).get('name'),
                        'symbol': nft.get('contract', {}).get('symbol')
                    },
                    'network': network,
                    'metadata': metadata,
                    'last_updated': datetime.utcnow().isoformat()
                }
                
                # Get floor price and last sale
                floor_price = self._estimate_floor_price(nft_data)
                if floor_price:
                    nft_data['floor_price'] = floor_price
                
                nfts.append(nft_data)
                
            except Exception as e:
                logger.debug(f"Failed to parse NFT: {e}")
                continue
        
        return nfts
    
    def _get_nft_image_url(self, metadata: Dict) -> Optional[str]:
        """Extract NFT image URL from metadata"""
        image = metadata.get('image')
        
        if not image:
            return None
        
        # Handle IPFS URLs
        if image.startswith('ipfs://'):
            ipfs_hash = image.replace('ipfs://', '')
            return f"https://ipfs.io/ipfs/{ipfs_hash}"
        
        # Handle ARWEAVE URLs
        if image.startswith('ar://'):
            ar_hash = image.replace('ar://', '')
            return f"https://arweave.net/{ar_hash}"
        
        return image
    
    def _estimate_floor_price(self, nft_data: Dict) -> Optional[Dict]:
        """Estimate NFT floor price (simplified)"""
        # In production, fetch from marketplace APIs
        # This is a placeholder
        collection_name = nft_data['collection']['name']
        
        # Mock floor prices for popular collections
        floor_prices = {
            'Bored Ape Yacht Club': {'eth': 30.5, 'usd': 76250},
            'CryptoPunks': {'eth': 45.2, 'usd': 113000},
            'Azuki': {'eth': 8.5, 'usd': 21250},
            'Doodles': {'eth': 4.2, 'usd': 10500},
            'CloneX': {'eth': 3.8, 'usd': 9500},
        }
        
        for collection, prices in floor_prices.items():
            if collection_name and collection in collection_name:
                return prices
        
        return None
    
    async def get_nft_collections(self, wallet_address: str, network: str = 'ethereum') -> List[Dict]:
        """Get NFT collections owned by wallet"""
        nfts = await self.get_nfts_by_wallet(wallet_address, network)
        
        # Group by collection
        collections = {}
        for nft in nfts:
            collection_address = nft['contract_address']
            collection_name = nft['collection']['name']
            
            if collection_address not in collections:
                collections[collection_address] = {
                    'address': collection_address,
                    'name': collection_name,
                    'symbol': nft['collection']['symbol'],
                    'network': network,
                    'nft_count': 0,
                    'estimated_value_eth': 0,
                    'estimated_value_usd': 0,
                    'nfts': []
                }
            
            collections[collection_address]['nft_count'] += 1
            collections[collection_address]['nfts'].append({
                'token_id': nft['token_id'],
                'name': nft['name'],
                'image_url': nft['image_url']
            })
            
            # Add to estimated value
            if 'floor_price' in nft:
                collections[collection_address]['estimated_value_eth'] += nft['floor_price'].get('eth', 0)
                collections[collection_address]['estimated_value_usd'] += nft['floor_price'].get('usd', 0)
        
        return list(collections.values())
    
    async def get_nft_listings(self, collection_address: str, network: str = 'ethereum') -> List[Dict]:
        """Get NFT listings for a collection"""
        try:
            # Try OpenSea first
            listings = await self.marketplaces['opensea'].get_listings(collection_address, network)
            
            # Add LooksRare listings
            if network == 'ethereum':
                looksrare_listings = await self.marketplaces['looksrare'].get_listings(collection_address)
                listings.extend(looksrare_listings)
            
            # Sort by price
            listings.sort(key=lambda x: x.get('price_eth', float('inf')))
            
            return listings[:50]  # Return top 50
            
        except Exception as e:
            logger.error(f"Failed to get NFT listings: {e}")
            return []
    
    async def track_nft_floor(self, collection_address: str, network: str = 'ethereum') -> Dict:
        """Track NFT collection floor price"""
        cache_key = f"nft_floor:{collection_address}:{network}"
        cached = await redis_client.cache_get(cache_key)
        if cached:
            return cached
        
        try:
            listings = await self.get_nft_listings(collection_address, network)
            
            if not listings:
                return {'error': 'No listings found'}
            
            # Calculate floor price
            floor_listings = [l for l in listings if l.get('price_eth')]
            if floor_listings:
                floor_price = min(l['price_eth'] for l in floor_listings)
                
                # Calculate 7-day stats (simplified)
                stats = {
                    'floor_price_eth': floor_price,
                    'floor_price_usd': floor_price * 2500,  # Mock ETH price
                    'listing_count': len(listings),
                    'volume_7d_eth': floor_price * len(listings) * 0.1,  # Mock
                    'avg_price_7d_eth': floor_price * 1.2,  # Mock
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Cache for 5 minutes
                await redis_client.cache_set(cache_key, stats, expire=300)
                
                return stats
            
            return {'error': 'No priced listings found'}
            
        except Exception as e:
            logger.error(f"Failed to track NFT floor: {e}")
            return {'error': str(e)}
    
    def _filter_and_sort_nfts(self, nfts: List[Dict]) -> List[Dict]:
        """Filter and sort NFTs"""
        # Filter out NFTs without images
        nfts = [n for n in nfts if n.get('image_url')]
        
        # Sort by estimated value (highest first)
        nfts.sort(key=lambda x: x.get('floor_price', {}).get('usd', 0), reverse=True)
        
        return nfts
    
    def _merge_nft_data(self, nfts1: List[Dict], nfts2: List[Dict]) -> List[Dict]:
        """Merge NFT data from multiple sources"""
        merged = {}
        
        for nft in nfts1 + nfts2:
            key = f"{nft.get('contract_address')}:{nft.get('token_id')}"
            if key not in merged:
                merged[key] = nft
            else:
                # Merge data (prefer non-null values)
                for k, v in nft.items():
                    if v and not merged[key].get(k):
                        merged[key][k] = v
        
        return list(merged.values())

class OpenSeaAPI:
    """OpenSea API integration"""
    
    async def get_nfts(self, wallet_address: str, network: str = 'ethereum') -> List[Dict]:
        """Get NFTs from OpenSea"""
        try:
            chain = 'ethereum' if network == 'ethereum' else network
            url = f"https://api.opensea.io/api/v2/chain/{chain}/account/{wallet_address}/nfts"
            
            headers = {}
            if settings.OPENSEA_API_KEY:
                headers['X-API-KEY'] = settings.OPENSEA_API_KEY
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_opensea_nfts(data.get('nfts', []))
                    else:
                        return []
                        
        except Exception as e:
            logger.error(f"OpenSea API error: {e}")
            return []
    
    def _parse_opensea_nfts(self, raw_nfts: List) -> List[Dict]:
        """Parse OpenSea NFT data"""
        nfts = []
        
        for nft in raw_nfts:
            try:
                nft_data = {
                    'token_id': nft.get('identifier'),
                    'contract_address': nft.get('contract'),
                    'name': nft.get('name') or f"#{nft.get('identifier')}",
                    'description': nft.get('description'),
                    'image_url': nft.get('image_url'),
                    'collection': {
                        'name': nft.get('collection'),
                        'symbol': nft.get('symbol')
                    },
                    'last_sale': nft.get('last_sale'),
                    'metadata': nft
                }
                
                nfts.append(nft_data)
                
            except Exception as e:
                logger.debug(f"Failed to parse OpenSea NFT: {e}")
                continue
        
        return nfts
    
    async def get_listings(self, collection_address: str, network: str = 'ethereum') -> List[Dict]:
        """Get NFT listings from OpenSea"""
        # Simplified version - in production use actual OpenSea API
        return []

class LooksRareAPI:
    """LooksRare API integration"""
    async def get_listings(self, collection_address: str) -> List[Dict]:
        return []

class X2Y2API:
    """X2Y2 API integration"""
    async def get_listings(self, collection_address: str) -> List[Dict]:
        return []

class MagicEdenAPI:
    """Magic Eden API integration (Solana)"""
    async def get_nfts(self, wallet_address: str) -> List[Dict]:
        return []

class BlurAPI:
    """Blur API integration"""
    async def get_listings(self, collection_address: str) -> List[Dict]:
        return []
