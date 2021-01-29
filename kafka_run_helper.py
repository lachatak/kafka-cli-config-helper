import base64
import sys
from os import path
from pathlib import Path

from kubernetes import client, config
import subprocess
from pykwalify.core import Core
import logging
from jinja2 import Template
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config.load_kube_config()
v1 = client.CoreV1Api()

TemplateValues = {}


def main():
    for config_name in sys.argv[1:]:
        logger.info("Processing %s", config_name)
        with open(config_name) as config_file:
            c = Core(data_file_obj=config_file, schema_files=["schema.yaml"])
            app_config = c.validate(raise_exception=True)
            target_path = make_target_directory(f"{app_config['service']}-{app_config['environment']}")
            kafka(app_config['kafka'], target_path)
            schema_registry(app_config['schema_registry'])
            write_template(target_path)


def write_template(target_path):
    for template_file in Path('./templates').iterdir():
        target_file = path.basename(path.splitext(template_file)[0])
        with open(template_file) as file_:
            template = Template(file_.read())
            write_text(Path(path.join(target_path, target_file)), template.render(TemplateValues))


def add_to_template_values(key, value):
    TemplateValues[key] = value


def target_directory(target_path):
    final_path = Path.cwd().joinpath(Path(path.join('.generated', target_path)))
    add_to_template_values('OUTPUT_DIR', final_path)
    return final_path


def make_target_directory(target_path):
    target = target_directory(target_path)
    if not path.exists(target):
        target.mkdir(parents=True, exist_ok=True)
        logger.info("Target directory %s has been created", target)
    return target


def from_k8s_secret(secret_config):
    secrets = v1.read_namespaced_secret(secret_config['name'], secret_config['namespace']).data
    secret = base64.b64decode(secrets[secret_config['key']])
    if 'binary' in secret_config and secret_config["binary"]:
        return secret
    else:
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
        raise NotImplemented


def from_config(config_):
    if 'kubernetes' in config_:
        return from_kubernetes(config_['kubernetes'])
    elif 'value' in config_:
        return config_['value']
    else:
        raise NotImplemented


def log_shell_out(proc):
    stdout, stderr = proc.communicate()
    stdoutstr = stdout.decode("utf-8").rstrip()
    stderrstr = stderr.decode("utf-8").rstrip()
    if not stdoutstr == '':
        logger.info(stdoutstr)
    if not stderrstr == '':
        logger.info(stderrstr)


def write_binary(file, binary):
    logger.info("Write target file %s", file)
    with open(file, "wb") as file:
        file.write(binary)


def write_text(file, text):
    logger.info("Write target file %s", file)
    with open(file, "w", encoding="utf-8") as file:
        file.write(text)


def add_keystore_password_template_values(password):
    add_to_template_values('KEYSTORE_PASSWORD', password)
    add_to_template_values('KEY_PASSWORD', password)


def generate_keystore(keystore_config, target_path):
    password = uuid.uuid4().hex
    add_keystore_password_template_values(password)
    log_shell_out(subprocess.Popen(['./script/keystore.sh',
                                    from_config(keystore_config['client_private_key']),
                                    from_config(keystore_config['client_certificate']),
                                    password,
                                    target_path],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   )
                  )


def get_keystore(keystore_config, target_path):
    add_keystore_password_template_values(from_config(keystore_config['password']))
    write_binary(Path(path.join(target_path, "keystore.p12")), from_config(keystore_config["keystore"]))


def keystore(keystore_config, target_path):
    if 'generate' in keystore_config:
        generate_keystore(keystore_config['generate'], target_path)
    elif 'binary' in keystore_config:
        get_keystore(keystore_config['binary'], target_path)
    else:
        raise NotImplemented


def add_truststore_password_template_values(password):
    add_to_template_values('TRUSTSTORE_PASSWORD', password)


def generate_truststore(truststore_config, target_path):
    password = uuid.uuid4().hex
    add_truststore_password_template_values(password)
    log_shell_out(subprocess.Popen(['./script/truststore.sh',
                                    from_config(truststore_config['ca_certificate']),
                                    password,
                                    target_path],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   )
                  )


def get_truststore(truststore_config, target_path):
    add_truststore_password_template_values(from_config(truststore_config['password']))
    write_binary(Path(path.join(target_path, "truststore.jks")), from_config(truststore_config["truststore"]))


def truststore(truststore_config, target_path):
    if 'generate' in truststore_config:
        generate_truststore(truststore_config['generate'], target_path)
    elif 'binary' in truststore_config:
        get_truststore(truststore_config['binary'], target_path)
    else:
        raise NotImplemented


def kafka(kafka_config, target_path):
    add_to_template_values('KAFKA_BOOTSTRAP_SERVER', from_config(kafka_config['bootstrap_servers']))
    keystore(kafka_config['keystore'], target_path)
    truststore(kafka_config['truststore'], target_path)


def schema_registry(schema_registry_config):
    add_to_template_values('SCHEMA_REGISTRY_USERNAME', from_config(schema_registry_config['user_name']))
    add_to_template_values('SCHEMA_REGISTRY_PASSWORD', from_config(schema_registry_config['password']))
    add_to_template_values('SCHEMA_REGISTRY_URL', from_config(schema_registry_config['url']))


if __name__ == '__main__':
    main()
