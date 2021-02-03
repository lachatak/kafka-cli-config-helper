# Kafka run helper
Running kafka cli tools needs several upfront preparations especially if you want to connect to secured kafka cluster. 

Kafka run helper is a python tool which helps collecting connection properties and credentials from various places and produces necessary files to be able to run kafka cli commands in a docker container locally.

# How to run
## Configuration
You need to provide `yaml` configuration for your setup. See [Config Template](config.yaml.template) and [schema](schema.yaml)

## Run
- log into the google project and k8s cluster you want to resolve values from (if you resolve values from k8s)
- generate
```bash
pip3 install -r requirements.txt
python3 kafka_run_helper.py my-configuartion.yaml
```
It will collect connection properties and credentials based on your configuration and create `.generated/my-configuartion` directory with files needed to be able connect to kafka from you localhost.

- execute. Open `.generated/my-configuartion/README.md`. In the command sections there are several popular kafka actions ready to be used. All you need to do is to copy the command into a terminal window and run. Underlying config file and credentials will be mounted into the docker container.
```bash
docker run -v /tmp/kafka/.generated/my-configuartion:/tmp confluentinc/cp-kafka:latest kafka-topics \
--bootstrap-server localhost:9092  \
--command-config /tmp/kafka.properties \
--list
```

### Limitations
One configuration file can only resolve values from the same google project/k8s cluster/google cloud secret manager. This limitation is fine most of the cases.

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