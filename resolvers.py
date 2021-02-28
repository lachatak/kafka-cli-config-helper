import base64
import logging
from abc import ABC, abstractmethod

from jsonpath_ng.ext import parse
from kubernetes import client as k8s_client, config as k8s_config
from mergedeep import Strategy, merge
from nested_lookup import nested_delete
from unflatten import unflatten

from google.cloud import secretmanager


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
            logging.info(f'Needs to resolve {count} values by {self.key} module')
            provider = self.provider()
            resolved = {}
            [merge(resolved, unflatten({f'{match.full_path}': self.fetch(match.value[self.key], provider)}),
                   strategy=Strategy.ADDITIVE) for match in results]
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
        def get_file_content(_path, _mode):
            with open(_path, f'r{_mode}') as file:
                return file.read()

        mode = 'b' if 'binary' in config and config['binary'] else ''
        return get_value(config['path'], lambda key: get_file_content(key, mode))


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
        return get_value(config['key'], lambda key: base64.b64decode(secrets[key]).decode("utf-8"))

    def from_k8s_configmap(self, config, v1_api):
        configs = v1_api.read_namespaced_config_map(config['name'], config['namespace'])
        if 'binary' in config and config["binary"]:
            return base64.b64decode(configs.binary_data[config['key']])
        else:
            return get_value(config['key'], lambda key: configs.data[key])


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


def get_value(key, extractor):
    key_parts = key.split(':', 1)
    value = extractor(key_parts[0])
    if len(key_parts) == 2:
        properties = property_str_to_dict(value)
        return properties[key_parts[1]]
    else:
        return value


def property_str_to_dict(property_str):
    return dict(line.strip().split('=', 1) for line in property_str.splitlines() if not line.startswith("#") and line)
