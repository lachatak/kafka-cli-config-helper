import base64
import logging

from jsonpath_ng.ext import parse
from mergedeep import Strategy, merge
from nested_lookup import nested_delete
from unflatten import unflatten

from google.cloud import secretmanager


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

KEY = 'google_secret_manager'


def resolve_secret_manager_values(app_config):
    jsonpath_expr = parse(f'$..{KEY}.`parent`')
    results = jsonpath_expr.find(app_config)
    count = len(results)
    if count > 0:
        logging.info(f'Needs to resolve {count} values by Secret Manager module')
        client = secretmanager.SecretManagerServiceClient()
        resolved = {}
        [merge(resolved, unflatten({f'{match.full_path}': fetch_secret(client, match.value[KEY])}),
               strategy=Strategy.ADDITIVE)for match in results]
        return merge(nested_delete(app_config, KEY), resolved, strategy=Strategy.ADDITIVE)
    else:
        return app_config


def fetch_secret(client, config):
    data = client.access_secret_version(request={"name": config['secret']}).payload.data
    if 'base64' in config and config['base64']:
        return base64.b64decode(data).decode("utf-8")
    else:
        return data


