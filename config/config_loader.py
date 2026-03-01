import os
import yaml
from types import SimpleNamespace

def dict_to_sns(d):
    """Convert a dictionary to a SimpleNamespace, recursively."""
    if isinstance(d, dict):
        for k, v in d.items():
            d[k] = dict_to_sns(v)
        return SimpleNamespace(**d)
    elif isinstance(d, list):
        return [dict_to_sns(i) for i in d]
    else:
        return d

def load_config(config_path=None):
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.yaml")

    if not os.path.exists(config_path):
        return SimpleNamespace()
    
    with open(config_path, "r") as f:
        try:
            data = yaml.safe_load(f) or {}
            # Ensure essential keys exist
            if 'log_dir' not in data:
                data['log_dir'] = 'logs'
            return dict_to_sns(data)
        except yaml.YAMLError:
            return SimpleNamespace(log_dir='logs')
