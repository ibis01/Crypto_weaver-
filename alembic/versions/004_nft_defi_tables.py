import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from modules.nft_defi.wallet.manager import WalletManager
from modules.nft_defi.nft.marketplace import NFTMarketplace
from modules.nft_defi.defi.protocols import DeFiManager
from modules.nft_defi.defi.swaps import TokenSwapManager

@pytest.mark.asyncio
async def test_wallet_connection():
    """Test wallet connection"""
    manager = WalletManager()
    
    user_id = 1
    wallet_address = "0x742d35Cc6634C0532925a3b844Bc9e34EF4303ab"
    network = 'ethereum'
    
    with patch('modules.nft_defi.wallet.manager.get_db') as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        # Mock wallet query
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        # Mock Redis
        with patch('modules.nft_defi.wallet.manager.redis_client.cache_set', new_callable=AsyncMock):
            with patch('modules.nft_defi.wallet.manager.redis_client.publish', new_callable=AsyncMock):
                # Mock Web3 balance check
                with patch.object(manager, 'get_balance', new_callable=AsyncMock) as mock_balance:
                    mock_balance.return_value = {
                        'native_balance': 1.5,
                        'native_currency': 'ETH',
                        'total_value_usd': 3750
                    }
                    
                    result = await manager.connect_wallet(user_id, wallet_address, network)
                    
                    assert result['success'] == True
                    assert result['wallet_address'] == wallet_address
                    assert result['network'] == network
                    assert mock_session.add.called

@pytest.mark.asyncio
async def test_nft_fetching():
    """Test NFT fetching"""
    marketplace = NFTMarketplace()
    
    wallet_address = "0x742d35Cc6634C0532925a3b844Bc9e34EF4303ab"
    network = 'ethereum'
    
    with patch.object(marketplace, '_get_alchemy_nfts', new_callable=AsyncMock) as mock_alchemy:
        mock_alchemy.return_value = [
            {
                'token_id': '123',
                'contract_address': '0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D',
                'name': 'Bored Ape #123',
                'image_url': 'https://example.com/ape.png',
                'collection': {'name': 'Bored Ape Yacht Club'}
            }
        ]
        
        with patch('modules.nft_defi.nft.marketplace.redis_client.cache_get', new_callable=AsyncMock) as mock_cache:
            mock_cache.return_value = None
            
            nfts = await marketplace.get_nfts_by_wallet(wallet_address, network)
            
            assert len(nfts) > 0
            assert nfts[0]['name'] == 'Bored Ape #123'
            assert 'image_url' in nfts[0]

@pytest.mark.asyncio
async def test_defi_positions():
    """Test DeFi position fetching"""
    defi_manager = DeFiManager()
    
    wallet_address = "0x742d35Cc6634C0532925a3b844Bc9e34EF4303ab"
    network = 'ethereum'
    
    with patch.object(defi_manager, 'get_lending_positions', new_callable=AsyncMock) as mock_lending:
        mock_lending.return_value = [
            {
                'protocol': 'Aave V3',
                'type': 'supply',
                'token': 'USDC',
                'amount': 1000,
                'value_usd': 1000
            }
        ]
        
        with patch.object(defi_manager, 'get_liquidity_positions', new_callable=AsyncMock) as mock_liquidity:
            mock_liquidity.return_value = []
            
            with patch.object(defi_manager, 'get_staking_positions', new_callable=AsyncMock) as mock_staking:
                mock_staking.return_value = []
                
                with patch('modules.nft_defi.defi.protocols.redis_client.cache_get', new_callable=AsyncMock) as mock_cache:
                    mock_cache.return_value = None
                    
                    positions = await defi_manager.get_wallet_positions(wallet_address, network)
                    
                    assert 'lending' in positions
                    assert 'liquidity' in positions
                    assert 'staking' in positions
                    assert len(positions['lending']) > 0

@pytest.mark.asyncio
async def test_token_swap():
    """Test token swap execution"""
    wallet_manager = MagicMock()
    swap_manager = TokenSwapManager(wallet_manager)
    
    user_id = 1
    swap_params = {
        'from_token': 'ETH',
        'to_token': 'USDC',
        'amount': 1.0,
        'network': 'ethereum'
    }
    
    with patch.object(swap_manager, '_get_user_wallet', new_callable=AsyncMock) as mock_wallet:
        mock_wallet.return_value = {'address': '0x123'}
        
        with patch.object(swap_manager, '_find_best_route', new_callable=AsyncMock) as mock_route:
            mock_route.return_value = {
                'dex': 'uniswap',
                'quote': {'amount_out': 2490, 'fee': 7.5, 'slippage': 0.5}
            }
            
            with patch.object(swap_manager, '_simulate_swap', new_callable=AsyncMock) as mock_sim:
                mock_sim.return_value = {'success': True, 'amount_out': 2490}
                
                with patch('modules.nft_defi.defi.swaps.settings') as mock_settings:
                    mock_settings.PAPER_TRADING_ONLY = True
                    
                    with patch.object(swap_manager, '_record_paper_swap', new_callable=AsyncMock) as mock_record:
                        mock_record.return_value = {'success': True, 'swap_id': 123}
                        
                        result = await swap_manager.execute_swap(user_id, swap_params)
                        
                        assert result['success'] == True
                        assert 'swap_id' in result or 'transaction_hash' in result

# Performance test for Web3 operations
@pytest.mark.performance
@pytest.mark.asyncio
async def test_web3_performance():
    """Test Web3 operation performance"""
    import time
    
    wallet_manager = WalletManager()
    
    # Test multiple balance checks
    addresses = [f"0x{'0' * 40}{i}" for i in range(10)]
    
    start_time = time.time()
    
    tasks = []
    for address in addresses:
        task = asyncio.create_task(
            wallet_manager.get_balance(address, 'ethereum')
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    
    successful = len([r for r in results if 'error' not in r])
    avg_time = (end_time - start_time) / len(addresses) * 1000  # ms per request
    
    print(f"\n🔗 Web3 Performance Test:")
    print(f"Addresses checked: {len(addresses)}")
    print(f"Successful: {successful}")
    print(f"Average time per request: {avg_time:.1f}ms")
    
    assert avg_time < 1000  # Should be under 1 second per request
