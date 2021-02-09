# Kafka CLI config helper
![Graph](http://kafka-acl-graph.com:5000/api/v1/kafka-acl-graph.svg?include-pattern=boost-balance-service&exclude-topic-pattern=boost_transaction_generated_v1)

![stack Overflow](file:///tmp/fa28ad65cb8f4a1bb9331da23d1c5603.svg)

Every time we need to connect to an SSL secured kafka cluster to do some CLI operations we need to go through the same painful process of collecting credentials as well as creating configuration files and SSL stores. 
- E.g. keystore.p12 and/or truststore.jks
- Configuration file for the kafka CLI commands

The situation is made even more complicated if you have several environments and autonomous teams who are using kafka with their own credentials stored in distinct secret management solutions. 

Kafka CLI config helper is a `python3` tool which through the use of a [configuration](#detailed-configuration-example) file automates the process of collecting connection properties and credentials from various sources and produces a [config file](templates/kafka.properties.template), [README.md](templates/README.md.template) and keystore/truststore that can be used to easily run kafka cli commands locally in a docker container.

# How to run

## Install
You need to have `python3` installed
```bash
git clone git@github.com:lachatak/kafka-cli-config-helper.git
cd kafka-cli-config-helper
pip3 install -r requirements.txt
```

## Configuration
You need to provide a `yaml` configuration file for the application. See [Detailed Configuration Example ](#detailed-configuration-example), [schema](schema.yaml) and [resolvers schema](resolvers_schema.yaml) for example configurations.

## Run
- Log into the GCP project and k8s cluster you want to resolve values from (if you're resolving values from GCP and k8s)
- Generate configuration
```bash
python3 kafka_cli_config_helper.py my-configuration.yaml
```
The tool will collect connection properties and credentials based on the provided configuration file and create a `.generated/my-configuration` directory with the files needed to be able connect to kafka from your machine.

- Open `.generated/my-configuration/README.md`. Under the commands section there are several popular kafka actions ready to be used. All you need to do is to copy the command into a terminal window and run. Underlying config files and credentials will be mounted into the docker container.
```bash
docker run -v /tmp/kafka/.generated/my-configuartion:/tmp confluentinc/cp-kafka:latest kafka-topics \
--bootstrap-server localhost:9092  \
--command-config /tmp/kafka.properties \
--list
```

## Preconfigured commands in the generated README.md
Some commands will need minor changes for your use case - for example changing the topic or group to the one that you are interested in. See the generated README.md
- Viewing topic details
- Viewing consumer group details
- Reset offset for consumer group
- Consume message from topic
- More to come

## Limitations
Any single given configuration file is only capable of resolving values from a single GCP project/k8s cluster/google cloud secret manager.

# Supported resolvers
There are several [resolvers](resolvers.py) supported. 
- Value - Resolves values provided directly in the configuration file 
- Kubernetes - Resolves values from k8s secrets and config maps (plain text, binary)
- File - Resolves values from a file on the local filesystem (plain text, binary)
- GoogleCloudSecretManager - Resolves values from Google Cloud Secret Manager (plain text or base64 encoded)

## Resolver configuration examples
### Value
```yaml
  bootstrap_server:
    value: localhost:9092
```

### Kubernetes
#### Config Map
##### Plaintext
```yaml
  user_name:
    kubernetes:
      configmap:
        namespace: kafka-service
        name: kafka-config
        key: kafka_schema_registry_username
```


##### Binary
```yaml
  truststore:
    kubernetes:
      configmap:
        namespace: kafka-service
        name: kafka-config
        key: truststore.jks
        binary: true
```

#### Secret
```yaml
  password:
    kubernetes:
      secret:
        namespace: kafka-service
        name: kafka-secret
        key: kafka_schema_registry_password
```

### File
#### Plaintext
```yaml
  client_private_key:
    file:
      path: /tmp/client_private_key
```

#### Binary
```yaml
  keystore:
    file:
      path: /tmp/keystore.p12
      binary: true
```

### GoogleCloudSecretManager
#### Plaintext
```yaml
  client_private_key:
    google_cloud_secret_manager:
      secret: projects/XXXXXXXXX/secrets/client_private_key/versions/1
```
#### Base64 encoded
```yaml
  client_private_key:
    google_cloud_secret_manager:
      secret: projects/XXXXXXXXX/secrets/client_private_key/versions/1
      base64: true
```
## Future Resolver Improvements
- GoogleKMS - In progress
- AWSSecretManager - TBD
- ???

# Keystore and truststore generation
There are 2 ways the tool can be used to create a keystore and truststore:
- Generate keystore and/or truststore based on provided certificates configured via resolvers. Passwords for the new keystore/truststore will be generated and stored in the `./generated/my-configuration/kafka.properties` file.
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
- Keystore and/or truststore is already generated, so we just need to fetch it from some external source by configuring a resolver
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

# Detailed Configuration Example 
Generate kafka configuration files for:
- `bootstrap_server` defined in a k8s configmap
- Generate `keystore` using `client_private_key` and `client_certificate` available in plain text files locally. Keystore and password will be generated and stored in the generated `kafka.properties` file
- Use a pre-built `truststore` defined in a k8s configmap as binary data. `password` is available in a Google Cloud Secret Manager in plain text
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
