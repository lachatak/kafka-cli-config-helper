# Kafka run helper
Running kafka cli tools needs several upfront preparations especially if you want to connect to secured kafka cluster. 

Kafka run helper is a python tool which helps collecting connection properties and credentials from various places and produces necessary files to be able to run kafka cli commands in a docker container locally.

# How to run
## Configuration
You need to provide `yaml` configuration for your setup. See [Config Template](config.yaml.template) and [schema](schema.yaml)

## Run
```bash
pip3 install -r requirements.txt
python3 kafka_run_helper.py my-configuartion.yaml
```

It will collect connection properties and credentials based on your configuration and create `.generated/my-configuartion-ENV` directory with files needed to be able connect from you localhost.

## Execute command
Go into the generated directory and see README.md. In the command sections there are several popular kafka actions ready to be used. All you need to do is to copy the command into a terminal window and run. Underlying config file and credentials will be mounted into the docker container.
 
