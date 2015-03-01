# coding: utf-8

import os
import json
import logging
import logging.config


class KPFuseError(Exception):
    pass


def setup_logging(default_path='logging.json',
                  default_level=logging.DEBUG,
                  env_key='LOG_CFG'):
    """Setup logging configuration
    """
    path = os.getenv(env_key, None) or default_path
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = json.load(f)
            logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)