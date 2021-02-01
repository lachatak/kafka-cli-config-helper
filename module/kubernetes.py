import base64
import logging

from jsonpath_ng.ext import parse
from kubernetes import client, config
from mergedeep import merge
from unflatten import unflatten


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

config.load_kube_config()
v1 = client.CoreV1Api()


def resolve_kubernetes(app_config):
    def add_to_resolved(match):
        return unflatten({f'{match.full_path}': from_kubernetes(match.value['kubernetes'])})

    resolved = {}
    jsonpath_expr = parse('$..kubernetes.`parent`')
    [merge(resolved, add_to_resolved(match)) for match in jsonpath_expr.find(app_config)]
    return resolved


def from_k8s_secret(secret_config):
    secrets = v1.read_namespaced_secret(secret_config['name'], secret_config['namespace']).data
    secret = base64.b64decode(secrets[secret_config['key']])
    return secret.decode("utf-8")


def from_k8s_configmap(configmap_config):
    configs = v1.read_namespaced_config_map(configmap_config['name'], configmap_config['namespace'])
    if 'binary' in configmap_config and configmap_config["binary"]:
        return base64.b64decode(configs.binary_data[configmap_config['key']])
    else:
        return configs.data[configmap_config['key']]


def from_kubernetes(kubernetes_config):
    if 'secret' in kubernetes_config:
        return from_k8s_secret(kubernetes_config['secret'])
    elif 'configmap' in kubernetes_config:
        return from_k8s_configmap(kubernetes_config['configmap'])
    else:
        raise NotImplementedError

