import logging
import subprocess
import sys
import uuid
from os import path
from pathlib import Path

from jinja2 import Template
from progress.bar import Bar
from pykwalify.core import Core

from resolvers import File, GoogleCloudSecretManager, Kubernetes, Value


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

SchemaVersionSupport = '1.0.0'

TemplateValues = {}
Resolved = {}
files_to_parse = sys.argv[1:]
number_of_tasks = (len(files_to_parse) * 7)
bar = Bar('', max=number_of_tasks)


def main():
    for config_name in files_to_parse:
        logger.info("Processing %s", config_name)
        app_config = load_config(config_name)
        resolved = resolve_module_values(app_config)
        generate_output(config_name, resolved)
    bar.finish()


def resolve_module_values(app_config):
    resolvers = [Value(), Kubernetes(), GoogleCloudSecretManager(), File()]
    tmp = app_config
    for resolver in resolvers:
        tmp = resolver.resolve(tmp)
    return tmp


def generate_output(config_name, resolved):
    target_path = make_target_directory(config_name)
    kafka(resolved['kafka'], target_path)
    schema_registry(resolved['schema_registry'])
    write_templates(target_path)


def task(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        bar.next()
        return result

    return wrapper


def log_shell_out(proc):
    def wrapper(*args, **kwargs):
        child = proc(*args, **kwargs)
        stdout, stderr = child.communicate()
        stdoutstr = stdout.decode("utf-8").rstrip()
        stderrstr = stderr.decode("utf-8").rstrip()
        if not stdoutstr == '':
            logger.info(stdoutstr)
        if not stderrstr == '' and not child.returncode == 0:
            logger.error(stderrstr)

    return wrapper


@task
def load_config(config_name):
    with open(config_name) as config_file:
        c = Core(data_file_obj=config_file, schema_files=[
            "schema.yaml",
            "resolvers_schema.yaml"])
        app_config = c.validate(raise_exception=True)
        return app_config


def write_templates(target_path):
    @task
    def write_template(template_file_, target_file):
        with open(template_file_) as file:
            template = Template(file.read())
            write_text(Path(path.join(target_path, target_file)), template.render(TemplateValues))

    for template_file in Path('./templates').iterdir():
        write_template(template_file, path.basename(path.splitext(template_file)[0]))


def add_to_template_values(key, value):
    TemplateValues[key] = value


def target_directory(target_path):
    final_path = Path.cwd().joinpath(Path(path.join('.generated', target_path)))
    add_to_template_values('OUTPUT_DIR', final_path)
    return final_path


@task
def make_target_directory(target_path):
    target = target_directory(path.basename(path.splitext(target_path)[0]))
    if not path.exists(target):
        target.mkdir(parents=True, exist_ok=True)
        logger.info("Target directory %s has been created", target)
    return target


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


@log_shell_out
def generate_keystore(keystore_config, target_path):
    password = uuid.uuid4().hex
    add_keystore_password_template_values(password)
    return subprocess.Popen(['./script/keystore.sh',
                             keystore_config['client_private_key'],
                             keystore_config['client_certificate'],
                             password,
                             target_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            )


def get_keystore(keystore_config, target_path):
    add_keystore_password_template_values(keystore_config['password'])
    write_binary(Path(path.join(target_path, "keystore.p12")), keystore_config["keystore"])


@task
def keystore(keystore_config, target_path):
    if 'generate' in keystore_config:
        generate_keystore(keystore_config['generate'], target_path)
    elif 'binary' in keystore_config:
        get_keystore(keystore_config['binary'], target_path)
    else:
        raise NotImplementedError


def add_truststore_password_template_values(password):
    add_to_template_values('TRUSTSTORE_PASSWORD', password)


@log_shell_out
def generate_truststore(truststore_config, target_path):
    password = uuid.uuid4().hex
    add_truststore_password_template_values(password)
    return subprocess.Popen(['./script/truststore.sh',
                             truststore_config['ca_certificate'],
                             password,
                             target_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            )


def get_truststore(truststore_config, target_path):
    add_truststore_password_template_values(truststore_config['password'])
    write_binary(Path(path.join(target_path, "truststore.jks")), truststore_config["truststore"])


@task
def truststore(truststore_config, target_path):
    if 'generate' in truststore_config:
        generate_truststore(truststore_config['generate'], target_path)
    elif 'binary' in truststore_config:
        get_truststore(truststore_config['binary'], target_path)
    else:
        raise NotImplementedError


def kafka(kafka_config, target_path):
    add_to_template_values('KAFKA_BOOTSTRAP_SERVER', kafka_config['bootstrap_server'])
    keystore(kafka_config['keystore'], target_path)
    truststore(kafka_config['truststore'], target_path)


@task
def schema_registry(schema_registry_config):
    add_to_template_values('SCHEMA_REGISTRY_USERNAME', schema_registry_config['user_name'])
    add_to_template_values('SCHEMA_REGISTRY_PASSWORD', schema_registry_config['password'])
    add_to_template_values('SCHEMA_REGISTRY_URL', schema_registry_config['url'])


def schema_validation(schema_version, rule_obj, path_):
    major, minor, bugfix = SchemaVersionSupport.split('.')
    conf_major, conf_minor, conf_bugfix = schema_version.split('.')
    if major == conf_major and minor >= conf_minor:
        return True
    else:
        raise AssertionError(f'Current version is {SchemaVersionSupport}. {schema_version} is not supported!')


if __name__ == '__main__':
    main()
