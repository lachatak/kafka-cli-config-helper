# Kafka CLI config helper
Running kafka cli command needs several upfront preparations especially if you want to connect to secured kafka cluster. 
- Need to have a keystore.p12 and/or truststore.jks
- Need to have a configuration file to feed it into the kafka cli commands

Kafka CLI config helper is a python tool which automates collecting connection properties and credentials from various places and produces [necessary files](templates) to be able to easily run kafka cli commands locally in a docker container.

# How to run
## Configuration
You need to provide `yaml` configuration for the helper. See [Detailed Configuration Example ](#detailed-configuration-example), [schema](schema.yaml) and [resolvers schema](resolvers_schema.yaml)

## Run
- log into the google project and k8s cluster you want to resolve values from (if you resolve values from google, k8s)
- generate
```bash
pip3 install -r requirements.txt
python3 kafka_cli_config_helper.py my-configuartion.yaml
```
It will collect connection properties and credentials based on your configuration and create `.generated/my-configuartion` directory with files needed to be able connect to kafka from you localhost.

- execute. Open `.generated/my-configuartion/README.md`. In the command sections there are several popular kafka actions ready to be used. All you need to do is to copy the command into a terminal window and run. Underlying config file and credentials will be mounted into the docker container.
```bash
docker run -v /tmp/kafka/.generated/my-configuartion:/tmp confluentinc/cp-kafka:latest kafka-topics \
--bootstrap-server localhost:9092  \
--command-config /tmp/kafka.properties \
--list
```

## Preconfigured commands in the generated README.md
Some command will need minor changes for your use case like update topic or group you are interested in. See the generated README.md
- Viewing topic details
- Viewing consumer group details
- Reset offset for consumer group
- Consume message from topic
- More to add

## Limitations
One configuration file can only resolve values from the same google project/k8s cluster/google cloud secret manager. This limitation is fine most of the cases.

# Detailed Configuration Example 
Generate kafka configuration files for:
- `bootstrap_server` is defined in a k8s configmap
- generate `keystore` using `client_private_key` and `client_certificate` available in plain text files. Keystore and key password will be generated and stored in the generated `kafka.properties` file
- use pre-built `truststore` defined in a k8s configmap as binary data. `password` is available in a Google Cloud Secret Manager in plain text
- schema registry `user_name` is not stored in any external source so it is defined as value
- schema registry `password` is defined in a k8s secret
- schema registry `url` is defined in a k8s configmap as plain text
```yaml
version: 1.0.0
kafka:
  bootstrap_server:
    kubernetes:
      configmap:
        namespace: test-service
        name: kafka-config
        key: BOOTSTRAP_SERVER
  keystore:
    generate:
      client_private_key:
        file:
          path: /tmp/client_private_key
      client_certificate:
        file:
          path: /tmp/client_certificate
  truststore:
    binary:
      truststore:
        kubernetes:
          configmap:
            namespace: test-service
            name: kafka-truststore
            key: truststore.jks
            binary: true
      password:
        google_cloud_secret_manager:
          secret: projects/XXXXXXXXX/secrets/truststore_password/versions/1
          base64: false
schema_registry:
  user_name:
    value: test-service
  password:
    kubernetes:
      secret:
        namespace: test-service
        name: kafka-schema-registry
        key: password
  url:
    kubernetes:
      configmap:
        namespace: test-service
        name: kafka-schema-registry
        key: SCHEMA_REGISTRY_URL
```

# Supported resolvers
There are several [resolvers](resolvers.py) supported. 
- Value - can provide values directly in the config 
- Kubernetes - can resolve value from k8s secret and config map (plain text, binary)
- File - can resolve value from file (plain text, binary)
- GoogleCloudSecretManager - can resolve value from Google Cloud Secret Manager (plain text or base64 encoded)
- GoogleKMS - In progress

## Value
The simples configuration resolver to provide value directly in the yaml file
```yaml
  bootstrap_server:
    value: localhost:9092
```

## Kubernetes
Use Kubernetes resolver to fetch value from k8s configmap or secret

### Config Map
Fetch plain text value from k8s configmap
```yaml
  user_name:
    kubernetes:
      configmap:
        namespace: kafka-service
        name: kafka-config
        key: kafka_schema_registry_username
```

Fetch binary value from k8s configmap
```yaml
  truststore:
    kubernetes:
      configmap:
        namespace: kafka-service
        name: kafka-config
        key: truststore.jks
        binary: true
```

### Secret
Fetch secret value from k8s secret
```yaml
  password:
    kubernetes:
      secret:
        namespace: kafka-service
        name: kafka-secret
        key: kafka_schema_registry_password
```

## File
Use File resolver to fetch value directly from file

Fetch plain text value from file
```yaml
  client_private_key:
    file:
      path: /tmp/client_private_key
```

Fetch binary value from file
```yaml
  keystore:
    file:
      path: /tmp/keystore.p12
      binary: true
```

## GoogleCloudSecretManager
Use GoogleCloudSecretManager resolver to fetch secret value from file [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs)

Fetch plain text value from secret manager
```yaml
  client_private_key:
    google_cloud_secret_manager:
      secret: projects/XXXXXXXXX/secrets/client_private_key/versions/1
```

Fetch base64 encoded text value from secret manager
```yaml
  client_private_key:
    google_cloud_secret_manager:
      secret: projects/XXXXXXXXX/secrets/client_private_key/versions/1
      base64: true
```

# Keystore and truststore generation
There are 2 ways how a keystore and truststore can be created by the helper:
- Generate keystore and/or truststore based on provided certificates configured via resolvers. Passwords for the new keystore/truststore will be generated and stored in the `./generated/my-config/kafka.properties` file.
```yaml
  keystore:
    generate:
      client_private_key:
        kubernetes:
          secret:
            namespace: kafka-service
            name: kafka-certificates
            key: client-private-key
      client_certificate:
        kubernetes:
          secret:
            namespace: kafka-service
            name: kafka-certificates
            key: client-certificate
```
- Keystore and/or truststore is already generated, we just need to fetch it from some source by configuring a resolvers
```yaml
  keystore:
    binary:
      keystore:
        kubernetes:
          configmap:
            namespace: kafka-service
            name: service-config
            key: keystore.p12
            binary: true
      password:
        kubernetes:
          secret:
            namespace: kafka-service
            name: service-config
            key: keystore_password
```
