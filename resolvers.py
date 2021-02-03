import base64
import logging
from abc import ABC, abstractmethod

from jsonpath_ng.ext import parse
from kubernetes import client as k8s_client, config as k8s_config
from mergedeep import Strategy, merge
from nested_lookup import nested_delete
from unflatten import unflatten

from google.cloud import secretmanager


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class Resolver(ABC):

    @property
    @abstractmethod
    def key(self):
        pass

    def provider(self):
        pass

    @abstractmethod
    def fetch(self, config, provider):
        pass

    def resolve(self, app_config):
        jsonpath_expr = parse(f'$..{self.key}.`parent`')
        results = jsonpath_expr.find(app_config)
        count = len(results)
        if count > 0:
            logging.info(f'Needs to resolve {count} values by file module')
            provider = self.provider()
            resolved = {}
            [merge(resolved, unflatten({f'{match.full_path}': self.fetch(match.value[self.key], provider)}),
                   strategy=Strategy.ADDITIVE)for match in results]
            return merge(nested_delete(app_config, self.key), resolved, strategy=Strategy.ADDITIVE)
        else:
            return app_config


class Value(Resolver):

    @property
    def key(self):
        return 'value'

    def fetch(self, config, provider):
        return config


class File(Resolver):

    @property
    def key(self):
        return 'file'

    def fetch(self, config, provider):
        mode = 'b' if 'binary' in config and config['binary'] else ''
        with open(config['path'], f'r{mode}') as file:
            return file.read()


class Kubernetes(Resolver):

    @property
    def key(self):
        return 'kubernetes'

    def provider(self):
        k8s_config.load_kube_config()
        return k8s_client.CoreV1Api()

    def fetch(self, config, v1_api):
        if 'secret' in config:
            return self.from_k8s_secret(config['secret'], v1_api)
        elif 'configmap' in config:
            return self.from_k8s_configmap(config['configmap'], v1_api)
        else:
            raise NotImplementedError

    def from_kubernetes(self, config, v1_api):
        if 'secret' in config:
            return self.from_k8s_secret(config['secret'], v1_api)
        elif 'configmap' in config:
            return self.from_k8s_configmap(config['configmap'], v1_api)
        else:
            raise NotImplementedError

    def from_k8s_secret(self, config, v1_api):
        secrets = v1_api.read_namespaced_secret(config['name'], config['namespace']).data
        secret = base64.b64decode(secrets[config['key']])
        return secret.decode("utf-8")

    def from_k8s_configmap(self, config, v1_api):
        configs = v1_api.read_namespaced_config_map(config['name'], config['namespace'])
        if 'binary' in config and config["binary"]:
            return base64.b64decode(configs.binary_data[config['key']])
        else:
            return configs.data[config['key']]


class GoogleCloudSecretManager(Resolver):

    @property
    def key(self):
        return 'google_cloud_secret_manager'

    def provider(self):
        return secretmanager.SecretManagerServiceClient()

    def fetch(self, config, client):
        data = client.access_secret_version(request={"name": config['secret']}).payload.data
        if 'base64' in config and config['base64']:
            return base64.b64decode(data).decode("utf-8")
        else:
            return data
