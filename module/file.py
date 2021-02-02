import base64
import logging

from jsonpath_ng.ext import parse
from mergedeep import Strategy, merge
from nested_lookup import nested_delete
from unflatten import unflatten


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

KEY = 'file'


def resolve_file_values(app_config):
    jsonpath_expr = parse(f'$..{KEY}.`parent`')
    results = jsonpath_expr.find(app_config)
    count = len(results)
    if count > 0:
        logging.info(f'Needs to resolve {count} values by file module')
        resolved = {}
        [merge(resolved, unflatten({f'{match.full_path}': fetch_file(match.value[KEY])}),
               strategy=Strategy.ADDITIVE)for match in results]
        return merge(nested_delete(app_config, KEY), resolved, strategy=Strategy.ADDITIVE)
    else:
        return app_config


def fetch_file(config):
    mode = 'b' if 'binary' in config and config['binary'] else ''
    with open(config['path'], f'r{mode}') as file:
        return file.read()
