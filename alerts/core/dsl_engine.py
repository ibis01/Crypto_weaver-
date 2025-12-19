"""
Domain Specific Language Engine for Advanced Alert System
Supports 20+ trigger types and complex logical expressions
"""
import ast
import operator
import math
import statistics
from typing import Dict, Any, List, Callable, Optional
from enum import Enum
from datetime import datetime, timedelta
import numpy as np
import pandas as pd


class TokenType(Enum):
    """Supported token types in DSL"""
    NUMBER = "NUMBER"
    STRING = "STRING"
    IDENTIFIER = "IDENTIFIER"
    OPERATOR = "OPERATOR"
    COMPARISON = "COMPARISON"
    LOGICAL = "LOGICAL"
    FUNCTION = "FUNCTION"
    KEYWORD = "KEYWORD"


class DSLFunction:
    """Base class for DSL functions"""
    
    def __init__(self, name: str, func: Callable, description: str = ""):
        self.name = name
        self.func = func
        self.description = description
    
    def __call__(self, *args):
        return self.func(*args)


class DSLEngine:
    """Advanced DSL Engine with 20+ trigger types support"""
    
    def __init__(self):
        self.operators = self._init_operators()
        self.functions = self._init_functions()
        self.keywords = self._init_keywords()
        self.market_indicators = self._init_market_indicators()
        
    def _init_operators(self) -> Dict[type, Callable]:
        """Initialize all supported operators"""
        return {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
            ast.BitAnd: operator.and_,
            ast.BitOr: operator.or_,
            ast.BitXor: operator.xor,
            ast.Invert: operator.invert,
        }
    
    def _init_functions(self) -> Dict[str, DSLFunction]:
        """Initialize all supported functions"""
        functions = {
            # Math functions
            'abs': DSLFunction('abs', abs, "Absolute value"),
            'round': DSLFunction('round', round, "Round to nearest integer"),
            'floor': DSLFunction('floor', math.floor, "Floor function"),
            'ceil': DSLFunction('ceil', math.ceil, "Ceiling function"),
            'sqrt': DSLFunction('sqrt', math.sqrt, "Square root"),
            'log': DSLFunction('log', math.log, "Natural logarithm"),
            'log10': DSLFunction('log10', math.log10, "Base-10 logarithm"),
            'exp': DSLFunction('exp', math.exp, "Exponential"),
            'pow': DSLFunction('pow', pow, "Power function"),
            
            # Statistical functions
            'min': DSLFunction('min', min, "Minimum value"),
            'max': DSLFunction('max', max, "Maximum value"),
            'sum': DSLFunction('sum', sum, "Sum of values"),
            'mean': DSLFunction('mean', lambda x: sum(x)/len(x) if x else 0, "Mean average"),
            'median': DSLFunction('median', statistics.median, "Median value"),
            'std': DSLFunction('std', lambda x: np.std(x) if len(x) > 1 else 0, "Standard deviation"),
            'var': DSLFunction('var', lambda x: np.var(x) if len(x) > 1 else 0, "Variance"),
            
            # Time functions
            'now': DSLFunction('now', lambda: datetime.utcnow(), "Current UTC time"),
            'timestamp': DSLFunction('timestamp', lambda: datetime.utcnow().timestamp(), "Current timestamp"),
            'days_ago': DSLFunction('days_ago', lambda days: datetime.utcnow() - timedelta(days=days), "Date n days ago"),
            
            # Technical indicators
            'sma': DSLFunction('sma', self._calculate_sma, "Simple Moving Average"),
            'ema': DSLFunction('ema', self._calculate_ema, "Exponential Moving Average"),
            'rsi': DSLFunction('rsi', self._calculate_rsi, "Relative Strength Index"),
            'macd': DSLFunction('macd', self._calculate_macd, "Moving Average Convergence Divergence"),
            'bollinger': DSLFunction('bollinger', self._calculate_bollinger_bands, "Bollinger Bands"),
            'atr': DSLFunction('atr', self._calculate_atr, "Average True Range"),
            
            # String functions
            'lower': DSLFunction('lower', str.lower, "Convert to lowercase"),
            'upper': DSLFunction('upper', str.upper, "Convert to uppercase"),
            'contains': DSLFunction('contains', lambda s, sub: sub in s, "Check if string contains substring"),
            'starts_with': DSLFunction('starts_with', lambda s, prefix: s.startswith(prefix), "Check if string starts with prefix"),
            
            # Array functions
            'len': DSLFunction('len', len, "Length of array"),
            'first': DSLFunction('first', lambda x: x[0] if x else None, "First element"),
            'last': DSLFunction('last', lambda x: x[-1] if x else None, "Last element"),
            'slice': DSLFunction('slice', lambda x, start, end: x[start:end], "Slice array"),
            
            # Financial functions
            'returns': DSLFunction('returns', self._calculate_returns, "Calculate returns"),
            'volatility': DSLFunction('volatility', self._calculate_volatility, "Calculate volatility"),
            'sharpe': DSLFunction('sharpe', self._calculate_sharpe_ratio, "Sharpe Ratio"),
            'max_drawdown': DSLFunction('max_drawdown', self._calculate_max_drawdown, "Maximum Drawdown"),
        }
        return functions
    
    def _init_keywords(self) -> Dict[str, Any]:
        """Initialize DSL keywords"""
        return {
            'true': True,
            'false': False,
            'null': None,
            'pi': math.pi,
            'e': math.e,
        }
    
    def _init_market_indicators(self) -> List[str]:
        """List of available market indicators"""
        return [
            'price', 'open', 'high', 'low', 'close', 'volume',
            'market_cap', 'circulating_supply', 'total_supply',
            'change_24h', 'change_7d', 'change_30d',
            'volume_24h', 'high_24h', 'low_24h',
            'rsi', 'macd', 'signal', 'histogram',
            'bb_upper', 'bb_middle', 'bb_lower',
            'ema_9', 'ema_21', 'ema_50', 'ema_200',
            'sma_20', 'sma_50', 'sma_200',
            'vwap', 'obv', 'adl', 'mfi',
            'stoch_k', 'stoch_d',
            'atr', 'adx', 'cci', 'williams_r',
            'fear_greed', 'social_volume', 'sentiment',
            'funding_rate', 'open_interest', 'liquidations',
            'orderbook_bid', 'orderbook_ask', 'orderbook_spread',
        ]
    
    # Technical indicator calculations
    def _calculate_sma(self, prices: List[float], period: int = 20) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return sum(prices[-period:]) / period
    
    def _calculate_ema(self, prices: List[float], period: int = 20) -> float:
        """Calculate Exponential Moving Average"""
        if not prices:
            return 0
        if len(prices) < period:
            return prices[-1]
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """Calculate MACD"""
        if len(prices) < slow:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        ema_fast = self._calculate_ema(prices, fast)
        ema_slow = self._calculate_ema(prices, slow)
        macd_line = ema_fast - ema_slow
        
        # For signal line, we need history of MACD values
        # Simplified version for DSL
        return {'macd': macd_line, 'signal': 0, 'histogram': 0}
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            sma = prices[-1] if prices else 0
            return {'upper': sma, 'middle': sma, 'lower': sma}
        
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period
        variance = sum((x - sma) ** 2 for x in recent_prices) / period
        std = math.sqrt(variance)
        
        return {
            'upper': sma + (std_dev * std),
            'middle': sma,
            'lower': sma - (std_dev * std)
        }
    
    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(highs) < period or len(lows) < period or len(closes) < period:
            return 0
        
        tr_values = []
        for i in range(1, len(highs)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i-1])
            lc = abs(lows[i] - closes[i-1])
            tr = max(hl, hc, lc)
            tr_values.append(tr)
        
        return sum(tr_values[-period:]) / period
    
    def _calculate_returns(self, prices: List[float], period: int = 1) -> List[float]:
        """Calculate returns over period"""
        if len(prices) < period + 1:
            return [0]
        returns = []
        for i in range(period, len(prices)):
            ret = (prices[i] - prices[i-period]) / prices[i-period]
            returns.append(ret)
        return returns[-10:]  # Return last 10 returns
    
    def _calculate_volatility(self, prices: List[float], period: int = 20) -> float:
        """Calculate volatility (standard deviation of returns)"""
        if len(prices) < period + 1:
            return 0
        returns = self._calculate_returns(prices, 1)
        if len(returns) < 2:
            return 0
        return np.std(returns)
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe Ratio"""
        if not returns or len(returns) < 2:
            return 0
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        if std_return == 0:
            return 0
        # Annualize (assuming daily returns)
        sharpe = (avg_return - risk_free_rate/365) / std_return * math.sqrt(365)
        return sharpe
    
    def _calculate_max_drawdown(self, prices: List[float]) -> float:
        """Calculate Maximum Drawdown"""
        if len(prices) < 2:
            return 0
        
        peak = prices[0]
        max_dd = 0
        
        for price in prices:
            if price > peak:
                peak = price
            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def evaluate(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        """Evaluate an AST node with context"""
        try:
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.Str):
                return node.s
            elif isinstance(node, ast.Name):
                # Check keywords first
                if node.id in self.keywords:
                    return self.keywords[node.id]
                # Then check context
                return context.get(node.id, 0)
            elif isinstance(node, ast.List):
                return [self.evaluate(element, context) for element in node.elts]
            elif isinstance(node, ast.Tuple):
                return tuple(self.evaluate(element, context) for element in node.elts)
            elif isinstance(node, ast.Dict):
                return {
                    self.evaluate(k, context): self.evaluate(v, context)
                    for k, v in zip(node.keys, node.values)
                }
            elif isinstance(node, ast.BinOp):
                left = self.evaluate(node.left, context)
                right = self.evaluate(node.right, context)
                op_type = type(node.op)
                if op_type in self.operators:
                    return self.operators[op_type](left, right)
                raise ValueError(f"Unsupported operator: {op_type}")
            elif isinstance(node, ast.UnaryOp):
                operand = self.evaluate(node.operand, context)
                op_type = type(node.op)
                if op_type in self.operators:
                    return self.operators[op_type](operand)
                raise ValueError(f"Unsupported unary operator: {op_type}")
            elif isinstance(node, ast.Compare):
                left = self.evaluate(node.left, context)
                result = True
                
                for op, right_node in zip(node.ops, node.comparators):
                    right = self.evaluate(right_node, context)
                    
                    if isinstance(op, ast.Eq):
                        result = result and (left == right)
                    elif isinstance(op, ast.NotEq):
                        result = result and (left != right)
                    elif isinstance(op, ast.Lt):
                        result = result and (left < right)
                    elif isinstance(op, ast.LtE):
                        result = result and (left <= right)
                    elif isinstance(op, ast.Gt):
                        result = result and (left > right)
                    elif isinstance(op, ast.GtE):
                        result = result and (left >= right)
                    elif isinstance(op, ast.In):
                        result = result and (left in right)
                    elif isinstance(op, ast.NotIn):
                        result = result and (left not in right)
                    else:
                        raise ValueError(f"Unsupported comparison: {type(op)}")
                    
                    left = right
                
                return result
            elif isinstance(node, ast.BoolOp):
                if isinstance(node.op, ast.And):
                    return all(self.evaluate(value, context) for value in node.values)
                else:  # ast.Or
                    return any(self.evaluate(value, context) for value in node.values)
            elif isinstance(node, ast.Call):
                func_name = node.func.id
                
                if func_name in self.functions:
                    func = self.functions[func_name]
                    args = [self.evaluate(arg, context) for arg in node.args]
                    kwargs = {
                        kw.arg: self.evaluate(kw.value, context)
                        for kw in node.keywords
                    }
                    
                    try:
                        if kwargs:
                            return func(*args, **kwargs)
                        else:
                            return func(*args)
                    except Exception as e:
                        raise ValueError(f"Error calling function {func_name}: {e}")
                else:
                    raise ValueError(f"Unknown function: {func_name}")
            elif isinstance(node, ast.IfExp):
                test = self.evaluate(node.test, context)
                if test:
                    return self.evaluate(node.body, context)
                else:
                    return self.evaluate(node.orelse, context)
            elif isinstance(node, ast.Subscript):
                value = self.evaluate(node.value, context)
                slice_value = self.evaluate(node.slice, context)
                return value[slice_value]
            elif isinstance(node, ast.Index):
                return self.evaluate(node.value, context)
            elif isinstance(node, ast.Constant):
                return node.value
            
            raise ValueError(f"Unsupported AST node type: {type(node)}")
            
        except Exception as e:
            raise ValueError(f"Evaluation error at node {type(node).__name__}: {e}")
    
    def parse_dsl(self, dsl_expression: str, market_data: Dict[str, Any]) -> bool:
        """Parse and evaluate a DSL expression with market data"""
        try:
            # Prepare context with market data
            context = {**market_data}
            
            # Add technical indicators if not present
            if 'prices' in market_data:
                prices = market_data.get('prices', [])
                if len(prices) > 0:
                    context.update({
                        'sma_20': self._calculate_sma(prices, 20),
                        'ema_12': self._calculate_ema(prices, 12),
                        'rsi_14': self._calculate_rsi(prices, 14),
                        'bb': self._calculate_bollinger_bands(prices),
                    })
            
            # Parse the expression
            tree = ast.parse(dsl_expression, mode='eval')
            result = self.evaluate(tree.body, context)
            
            # Ensure boolean result
            return bool(result)
            
        except SyntaxError as e:
            raise ValueError(f"DSL syntax error: {e}")
        except Exception as e:
            raise ValueError(f"DSL evaluation error: {e}")
    
    def validate_dsl(self, dsl_expression: str) -> Dict[str, Any]:
        """Validate DSL expression syntax and semantics"""
        try:
            # Parse to check syntax
            tree = ast.parse(dsl_expression, mode='eval')
            
            # Extract variables used
            variables = set()
            functions = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    if node.id not in self.keywords:
                        variables.add(node.id)
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        functions.add(node.func.id)
            
            # Check if functions exist
            unknown_funcs = [f for f in functions if f not in self.functions]
            
            return {
                'valid': True,
                'variables': list(variables),
                'functions': list(functions),
                'unknown_functions': unknown_funcs,
                'ast_tree': ast.dump(tree),
                'error': None
            }
            
        except SyntaxError as e:
            return {
                'valid': False,
                'variables': [],
                'functions': [],
                'unknown_functions': [],
                'ast_tree': None,
                'error': f"Syntax error: {e}"
            }
        except Exception as e:
            return {
                'valid': False,
                'variables': [],
                'functions': [],
                'unknown_functions': [],
                'ast_tree': None,
                'error': f"Validation error: {e}"
            }
    
    def get_supported_functions(self) -> List[Dict[str, str]]:
        """Get list of all supported functions with descriptions"""
        return [
            {'name': name, 'description': func.description}
            for name, func in self.functions.items()
        ]
    
    def get_supported_operators(self) -> List[str]:
        """Get list of all supported operators"""
        return [
            '+', '-', '*', '/', '//', '%', '**',  # Arith
