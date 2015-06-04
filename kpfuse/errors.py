# coding: utf-8

import os
import json
import logging
import logging.config


class OAuthResponseError(Exception):
    def __init__(self, response=None, description=None):
        """
        :type response: requests.Response
        """
        super(OAuthResponseError, self).__init__(dict(msg=description or response.content,
                                                      response=repr(response)))


class FileNotExistedError(OAuthResponseError):
    pass


class FileExistedError(OAuthResponseError):
    pass


def setup_logging(default_path='logging.json',
                  default_level=logging.DEBUG,
                  env_key='LOG_CFG',
                  log_path=None):
    """Setup logging configuration
    """
    path = os.getenv(env_key, None) or default_path
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = json.load(f)
            if log_path:
                config['handlers']['file_handler']['filename'] = log_path
            logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)

def get_log_handlers_by_name(log, handler_name):
    if isinstance(log, str):
        log = logging.getLogger(log)
    return filter(lambda x: x.name == handler_name, log.handlers)


def remove_log_handler(log_name, handler_name):
    log = logging.getLogger(log_name)
    for h in get_log_handlers_by_name(log, handler_name):
        log.removeHandler(h)
        break