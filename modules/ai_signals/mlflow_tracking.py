import mlflow
import mlflow.tensorflow
import mlflow.sklearn
from datetime import datetime
from pathlib import Path
import json
import pickle
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class MLflowTracker:
    """Track ML experiments with MLflow"""
    
    def __init__(self, tracking_uri: str = "http://localhost:5000"):
        mlflow.set_tracking_uri(tracking_uri)
        self.experiment_name = "crypto_weaver_ai"
        
        # Create experiment if it doesn't exist
        try:
            self.experiment_id = mlflow.create_experiment(self.experiment_name)
        except:
            self.experiment_id = mlflow.get_experiment_by_name(self.experiment_name).experiment_id
    
    def start_run(self, run_name: str, tags: Dict = None):
        """Start MLflow run"""
        return mlflow.start_run(
            experiment_id=self.experiment_id,
            run_name=run_name,
            tags=tags or {}
        )
    
    def log_model_training(self, model, model_name: str, metrics: Dict, 
                         parameters: Dict, artifacts: Dict = None):
        """Log model training to MLflow"""
        with self.start_run(f"train_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}") as run:
            # Log parameters
            mlflow.log_params(parameters)
            
            # Log metrics
            mlflow.log_metrics(metrics)
            
            # Log model
            if hasattr(model, 'save'):
                # TensorFlow/Keras model
                mlflow.tensorflow.log_model(model, "model")
            else:
                # Scikit-learn model
                mlflow.sklearn.log_model(model, "model")
            
            # Log artifacts
            if artifacts:
                for artifact_name, artifact_data in artifacts.items():
                    if isinstance(artifact_data, dict):
                        artifact_path = f"artifacts/{artifact_name}.json"
                        with open(artifact_path, 'w') as f:
                            json.dump(artifact_data, f)
                        mlflow.log_artifact(artifact_path)
                    elif isinstance(artifact_data, (str, Path)):
                        mlflow.log_artifact(str(artifact_data))
            
            # Log run info
            run_info = {
                'run_id': run.info.run_id,
                'experiment_id': run.info.experiment_id,
                'status': run.info.status,
                'start_time': run.info.start_time,
                'end_time': run.info.end_time
            }
            
            logger.info(f"Logged training run: {run_info}")
            
            return run_info
    
    def log_signal_performance(self, symbol: str, signal_data: Dict, 
                             actual_outcome: Dict):
        """Log signal performance for analysis"""
        with self.start_run(f"signal_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}") as run:
            # Calculate performance metrics
            predicted_action = signal_data.get('action')
            actual_action = actual_outcome.get('action')
            
            correct = predicted_action == actual_action
            
            mlflow.log_metrics({
                'correct_prediction': int(correct),
                'signal_confidence': signal_data.get('confidence', 0),
                'price_change_pct': actual_outcome.get('price_change_pct', 0)
            })
            
            mlflow.log_params({
                'symbol': symbol,
                'predicted_action': predicted_action,
                'actual_action': actual_action,
                'timestamp': signal_data.get('timestamp')
            })
    
    def get_best_model(self, symbol: str, metric: str = 'accuracy') -> Dict:
        """Retrieve best model for symbol based on metric"""
        # Query MLflow for best run
        runs = mlflow.search_runs(
            experiment_ids=[self.experiment_id],
            filter_string=f"tags.symbol='{symbol}'",
            order_by=[f"metrics.{metric} DESC"]
        )
        
        if runs.empty:
            return None
        
        best_run = runs.iloc[0]
        
        # Load model from best run
        model_uri = f"runs:/{best_run.run_id}/model"
        model = mlflow.pyfunc.load_model(model_uri)
        
        return {
            'model': model,
            'run_id': best_run.run_id,
            'metrics': best_run.to_dict(),
            'model_uri': model_uri
        }
    
    def log_strategy_performance(self, strategy_id: str, performance: Dict):
        """Log trading strategy performance"""
        with self.start_run(f"strategy_{strategy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}") as run:
            # Log performance metrics
            mlflow.log_metrics({
                'total_return_pct': performance.get('total_return_pct', 0),
                'sharpe_ratio': performance.get('sharpe_ratio', 0),
                'max_drawdown_pct': performance.get('max_drawdown_pct', 0),
                'win_rate': performance.get('win_rate', 0),
                'profit_factor': performance.get('profit_factor', 0)
            })
            
            # Log strategy parameters
            mlflow.log_params({
                'strategy_id': strategy_id,
                'period': performance.get('period', ''),
                'total_trades': performance.get('total_trades', 0)
            })
            
            # Log equity curve as artifact
            equity_curve = performance.get('equity_curve', [])
            if equity_curve:
                curve_path = f"equity_curve_{strategy_id}.json"
                with open(curve_path, 'w') as f:
                    json.dump(equity_curve, f)
                mlflow.log_artifact(curve_path)
