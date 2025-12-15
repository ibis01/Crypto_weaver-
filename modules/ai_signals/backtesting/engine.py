import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum
import asyncio

from core.database import get_db
from modules.market_data.models import PriceHistory

logger = logging.getLogger(__name__)

class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

@dataclass
class Trade:
    signal_type: SignalType
    entry_price: float
    exit_price: float = None
    entry_time: datetime = None
    exit_time: datetime = None
    quantity: float = 1.0
    profit_loss: float = 0.0
    profit_loss_pct: float = 0.0

class BacktestingEngine:
    """Backtesting engine for AI signals"""
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = []
        self.trades = []
        self.performance_metrics = {}
        
    async def backtest_signal_strategy(self, symbol: str, 
                                     signal_generator,
                                     start_date: datetime,
                                     end_date: datetime,
                                     timeframe: str = '1h') -> Dict:
        """Backtest a signal generation strategy"""
        # Load historical data
        historical_data = await self._load_historical_data(symbol, start_date, end_date, timeframe)
        
        if len(historical_data) < 100:
            return {'error': 'Insufficient historical data'}
        
        # Initialize backtesting
        self.capital = self.initial_capital
        self.positions = []
        self.trades = []
        
        # Run backtest
        for i in range(len(historical_data)):
            if i < 50:  # Need enough data for analysis
                continue
                
            current_data = historical_data.iloc[:i+1]
            current_price = current_data.iloc[-1]['close']
            current_time = current_data.index[-1]
            
            # Generate signal for this point in time
            signal = await signal_generator(current_data)
            
            # Execute trades based on signal
            await self._execute_trades(signal, current_price, current_time)
            
            # Update existing positions
            await self._update_positions(current_price, current_time)
        
        # Close all remaining positions
        await self._close_all_positions(historical_data.iloc[-1]['close'], historical_data.index[-1])
        
        # Calculate performance metrics
        metrics = self._calculate_performance_metrics()
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'period': f"{start_date.date()} to {end_date.date()}",
            'trades': len(self.trades),
            'performance': metrics,
            'equity_curve': self._generate_equity_curve(),
            'trades_list': self._format_trades_for_output()
        }
    
    async def _load_historical_data(self, symbol: str, 
                                  start_date: datetime, 
                                  end_date: datetime,
                                  timeframe: str) -> pd.DataFrame:
        """Load historical price data for backtesting"""
        with get_db() as db:
            prices = db.query(
                PriceHistory.timestamp,
                PriceHistory.price.label('close'),
                PriceHistory.volume,
                PriceHistory.high,
                PriceHistory.low
            ).filter(
                PriceHistory.symbol == symbol,
                PriceHistory.timestamp >= start_date,
                PriceHistory.timestamp <= end_date
            ).order_by(PriceHistory.timestamp.asc()).all()
            
            if not prices:
                return pd.DataFrame()
            
            df = pd.DataFrame(prices, columns=['timestamp', 'close', 'volume', 'high', 'low'])
            df.set_index('timestamp', inplace=True)
            
            # Resample based on timeframe
            if timeframe == '1h':
                df = df.resample('1H').agg({
                    'close': 'last',
                    'volume': 'sum',
                    'high': 'max',
                    'low': 'min'
                })
            elif timeframe == '4h':
                df = df.resample('4H').agg({
                    'close': 'last',
                    'volume': 'sum',
                    'high': 'max',
                    'low': 'min'
                })
            elif timeframe == '1d':
                df = df.resample('1D').agg({
                    'close': 'last',
                    'volume': 'sum',
                    'high': 'max',
                    'low': 'min'
                })
            
            df.dropna(inplace=True)
            return df
    
    async def _execute_trades(self, signal: Dict, current_price: float, current_time: datetime):
        """Execute trades based on signal"""
        if signal['action'] == SignalType.BUY.value and self.capital > 0:
            # Calculate position size (use 90% of capital for simplicity)
            position_size = self.capital * 0.9
            
            # Record buy
            trade = Trade(
                signal_type=SignalType.BUY,
                entry_price=current_price,
                entry_time=current_time,
                quantity=position_size / current_price
            )
            
            self.positions.append(trade)
            self.capital -= position_size
            
        elif signal['action'] == SignalType.SELL.value and self.positions:
            # Close all positions
            for position in self.positions:
                if position.exit_price is None:  # Not yet closed
                    position.exit_price = current_price
                    position.exit_time = current_time
                    position.profit_loss = (
                        (current_price - position.entry_price) * position.quantity
                    )
                    position.profit_loss_pct = (
                        (current_price - position.entry_price) / position.entry_price * 100
                    )
                    
                    self.trades.append(position)
                    self.capital += (
                        position.entry_price * position.quantity + position.profit_loss
                    )
            
            # Clear positions
            self.positions = []
    
    async def _update_positions(self, current_price: float, current_time: datetime):
        """Update existing positions (for stop loss/take profit)"""
        # Implement stop loss and take profit logic
        for position in self.positions:
            if position.exit_price is None:
                # Check for stop loss (5%)
                stop_loss_price = position.entry_price * 0.95
                if current_price <= stop_loss_price:
                    position.exit_price = current_price
                    position.exit_time = current_time
                    position.profit_loss = (
                        (current_price - position.entry_price) * position.quantity
                    )
                    position.profit_loss_pct = (
                        (current_price - position.entry_price) / position.entry_price * 100
                    )
                    
                    self.trades.append(position)
                    self.capital += (
                        position.entry_price * position.quantity + position.profit_loss
                    )
                
                # Check for take profit (10%)
                take_profit_price = position.entry_price * 1.10
                if current_price >= take_profit_price:
                    position.exit_price = current_price
                    position.exit_time = current_time
                    position.profit_loss = (
                        (current_price - position.entry_price) * position.quantity
                    )
                    position.profit_loss_pct = (
                        (current_price - position.entry_price) / position.entry_price * 100
                    )
                    
                    self.trades.append(position)
                    self.capital += (
                        position.entry_price * position.quantity + position.profit_loss
                    )
        
        # Remove closed positions
        self.positions = [p for p in self.positions if p.exit_price is None]
    
    async def _close_all_positions(self, current_price: float, current_time: datetime):
        """Close all remaining positions at end of backtest"""
        for position in self.positions:
            if position.exit_price is None:
                position.exit_price = current_price
                position.exit_time = current_time
                position.profit_loss = (
                    (current_price - position.entry_price) * position.quantity
                )
                position.profit_loss_pct = (
                    (current_price - position.entry_price) / position.entry_price * 100
                )
                
                self.trades.append(position)
                self.capital += (
                    position.entry_price * position.quantity + position.profit_loss
                )
        
        self.positions = []
    
    def _calculate_performance_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        if not self.trades:
            return {'error': 'No trades executed'}
        
        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.profit_loss > 0]
        losing_trades = [t for t in self.trades if t.profit_loss <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_profit = sum(t.profit_loss for t in self.trades)
        average_profit = total_profit / total_trades if total_trades > 0 else 0
        
        # Risk metrics
        profits = [t.profit_loss_pct for t in self.trades]
        if profits:
            sharpe_ratio = self._calculate_sharpe_ratio(profits)
            max_drawdown = self._calculate_max_drawdown(profits)
            profit_factor = (
                sum(t.profit_loss for t in winning_trades) / 
                abs(sum(t.profit_loss for t in losing_trades))
                if losing_trades else float('inf')
            )
        else:
            sharpe_ratio = 0
            max_drawdown = 0
            profit_factor = 0
        
        # Portfolio metrics
        final_value = self.capital
        total_return = ((final_value - self.initial_capital) / self.initial_capital) * 100
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate * 100,
            'total_profit': total_profit,
            'average_profit': average_profit,
            'total_return_pct': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown_pct': max_drawdown * 100,
            'profit_factor': profit_factor,
            'final_capital': final_value,
            'initial_capital': self.initial_capital
        }
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate / 252  # Daily risk-free rate
        
        if np.std(excess_returns) == 0:
            return 0
        
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        return sharpe
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not returns:
            return 0
        
        cumulative = np.cumprod(1 + np.array(returns) / 100)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        
        return abs(np.min(drawdown))
    
    def _generate_equity_curve(self) -> List[Dict]:
        """Generate equity curve data for charting"""
        if not self.trades:
            return []
        
        # Sort trades by exit time
        sorted_trades = sorted(self.trades, key=lambda x: x.exit_time)
        
        equity_curve = []
        current_equity = self.initial_capital
        
        for trade in sorted_trades:
            current_equity += trade.profit_loss
            equity_curve.append({
                'timestamp': trade.exit_time.isoformat(),
                'equity': current_equity,
                'return_pct': ((current_equity - self.initial_capital) / self.initial_capital) * 100
            })
        
        return equity_curve
    
    def _format_trades_for_output(self) -> List[Dict]:
        """Format trades for readable output"""
        return [
            {
                'entry_time': t.entry_time.isoformat(),
                'exit_time': t.exit_time.isoformat() if t.exit_time else None,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'quantity': t.quantity,
                'profit_loss': t.profit_loss,
                'profit_loss_pct': t.profit_loss_pct,
                'type': t.signal_type.value
            }
            for t in self.trades
          ]
