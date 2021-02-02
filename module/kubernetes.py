import base64
import logging

from jsonpath_ng.ext import parse
from kubernetes import client, config
from mergedeep import Strategy, merge
from nested_lookup import nested_delete
from unflatten import unflatten


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def resolve_k8s_values(app_config):
    jsonpath_expr = parse('$..kubernetes.`parent`')
    results = jsonpath_expr.find(app_config)
    count = len(results)
    if count > 0:
        logging.info(f'Needs to resolve {count} values by kubernetes module')
        config.load_kube_config()
        v1_api = client.CoreV1Api()
        resolved = {}
        [merge(resolved, unflatten({f'{match.full_path}': from_kubernetes(match.value['kubernetes'], v1_api)}), strategy=Strategy.ADDITIVE)
         for match in results]
        return merge(nested_delete(app_config, 'kubernetes'), resolved, strategy=Strategy.ADDITIVE)
    else:
        return app_config


def from_k8s_secret(secret_config, v1_api):
    secrets = v1_api.read_namespaced_secret(secret_config['name'], secret_config['namespace']).data
    secret = base64.b64decode(secrets[secret_config['key']])
    return secret.decode("utf-8")


def from_k8s_configmap(configmap_config, v1_api):
    configs = v1_api.read_namespaced_config_map(configmap_config['name'], configmap_config['namespace'])
    if 'binary' in configmap_config and configmap_config["binary"]:
        return base64.b64decode(configs.binary_data[configmap_config['key']])
    else:
        return configs.data[configmap_config['key']]


def from_kubernetes(kubernetes_config, v1_api):
    if 'secret' in kubernetes_config:
        return from_k8s_secret(kubernetes_config['secret'], v1_api)
    elif 'configmap' in kubernetes_config:
        return from_k8s_configmap(kubernetes_config['configmap'], v1_api)
    else:
        raise NotImplementedError

