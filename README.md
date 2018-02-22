# alexis-project-test

# Table of contents

- [Introduction](#introduction)
    - [Background](#background)
    - [Simple Run](#simple-run)
    - [Requirements](#requirements)
        - [Docker Version](#docker-version)
        - [GitHub and DockerHub Access](#github-and-dockerhub-access)
        - [Config changes](#config-changes)
        - [SSH Key management](#ssh-key-management)
        - [Optional: logging endpoint](#optional-logging-endpoint)
    - [Configuration](#configuration)
    - [Versions](#configuration)
- [Diagrams and Concepts](#diagrams-and-concepts)
    - [Detail of Simple Run](#detail-of-simple-run)
        - [Dynatrace Integration with OpsGenie](#dynatrace-integration-with-opsgenie)
        - [Docker Bind Mounts](#docker-bind-mounts)
        - [Docker Networking](#docker-networking)
        - [API Access](#api-access)
        - [Rule Storage](#rule-storage)
        - [Logging With Reporting in Mind](#logging-with-reporting-in-mind)
        - [Keep A History](#keep-a-history)
    - [Detail of Poller](#detail-of-poller)
    - [Detail of Classifier](#detail-of-classifier)
    - [Detail of Action_Handler](#detail-of-action_handler)


# Introduction

This project shows how the root cause analysis within Dynatrace Problems can drive autoremediation in your environment.

Currently the project focuses on immediate triage and resolution of an issue (Ops) rather than rolling back code (Dev).

But the ideas and the structure of this code can apply to any kind of "event-parse-act" workflow.

### Background

At Dynatrace, we have used OpsGenie as a provider for On-Call responsibilities.

Although we love that we can easily respond to alerts, shouldn't the goal of Operations be that we handle problems **proactively** with _rehearsed code_ rather than **reactively** with _improvised actions_?

At the onset of this project, we wanted to achieve two primary results:
- reduce MTTR (mean time to resolution)
- move from Receiving Alerts to Reviewing Reports (see optional logging endpoint)

We believe that this project satisfies both of those results and more.

### Simple Run

To cut through all of the documentation below, you can download and run with:

```
git clone --progress -v "https://github.com/aarontimko/alexis-project-test.git" alexis-project-test
cd alexis-project-test
docker stack deploy -c .\github_docker-compose.yaml alexis
```

To tear down:

`docker stack rm alexis`

### Requirements

#### Docker Version
- We have tested 17.09.0 on both Windows and Linux
- Some functionality requires the Docker Node to be in Swarm Mode (docker swarm init)

#### GitHub and DockerHub Access
- Pull this repo onto your Windows/Linux machine which has Docker
- The Docker Compose file will also need to pull images from Docker Hub (https://hub.docker.com/u/dynatracealexis/)
  - Note: the documentation on these GitHub images is very minimal

#### Config changes
- If you just want to bring up the Docker Stack of containers, you don't need to change the default configuration from the Git pull
- But if you don't change the default configuration, you can't play with your own data :)

#### SSH Key management
- Currently, this project relies on an SSH key and user to SSH to remote systems and run commands.  This is the `run_command` task_type in the JSON rules in the Classifier conf/rules directory.  This was chosen because the content of the `run_command` can be specified to any one-liner and this keeps autoremediation options very flexible.
  - In `Action_Handler.py`, it would be very easy to create other autoremediation actions like task_type `call_ansible_playbook` or `servicenow_reboot_server`.  The idea was to leave `Action_Handler.py` as a microservice, but it could be extended with extra plugins in the /alexis directory (you can see there is a file specifically there for OpsGenie, named `opsgenie.py`)

#### Optional: logging endpoint
- There is a lot of very intentional logging which allows you to trace behavior in the stack.  To view these logs from CLI, of course you can use `docker container logs`.  But if you output these to a log management system, you can benefit from a wealth of logging data which helps extensively with debugging.  And if you get more clever, you can even build reports which tell you the number of autoremediation actions, the average duration of each action, failed autoremediation actions, and more.

### Configuration

There are three primary configuration files.
YAML was chosen because it is easy to document in-line, so do check out these files first.
Each of these correspond to 3 Python services:
- docker/github/poller/conf/alexis.conf.yaml
- docker/github/classifier/conf/alexis.conf.yaml
- docker/github/action_handler/conf/alexis.conf.yaml

There is a very important 'rules' directory.
These rules are the main logic which will evaluate incoming data:
- docker/github/classifier/conf/rules

For full autoremediation, you will need to make the following changes:

1. `github_docker-compose.yaml`: replace the content of `/docker/github/keys/my_autoremediation_id_rsa` with your own SSH key which has access to remote systems.  The file name and the user of this should match the name of the key in action_handler's YAML file.
1. **Poller**: Change your authentication keys in `authentication_list`
1. **Poller**: Change your feed url in `feed_list`
1. **Classifier**: Change your authentication keys in `authentication_list`
1. **Classifier**: Create rules in the **rules** directory which match the tags and events in your environment
1. **Classifier**: Create a 'team' in OpsGenie which matches your value of `default_remediation_queue`
1. **Classifier**: Create a 'team' in OpsGenie which matches your value of `default_investigation_queue`
1. **Action_Handler**: Change your authentication keys in `authentication_list`
1. **Action_Handler**: SSH configuration --> Leave "/run/secrets" as the directory where Docker will place your key. But `ssh_key` and `ssh_user` should match your authentication key in `github_docker-compose.yaml`
1. **Remote systems**: be sure to configure your `ssh_user` and corresponding `ssh_key` on remote systems


### Versions

v1.01 - Initial commit

# Diagrams and Concepts

This section describes the Alexis stack in greater detail and will explain the thought process behind the design.

## Detail of Simple Run

![Diagram: Detail of Simple Run](/images/diagram-detail-of-simple-run.png)

### Dynatrace Integration with OpsGenie

This is straightforward to send outbound Problems from Dynatrace and receive that data in OpsGenie.

1. Create a Dynatrace Integration in OpsGenie and record the key.
1. Create an OpsGenie Integration in Dynatrace and enter the key.


_Note: OpsGenie supporting Dynatrace tags is a significant feature which enables Alexis to interact programmatically via existing CI/CD metadata rather than parsing string fields with regex, using hostname syntax, etc._

### Docker Bind Mounts

The Docker images are configured to use your local filesystem in order to reach the Conf directories.
e.g.
```
    volumes:
      - type: bind
        source: ./docker/github/poller/conf
        target: /usr/src/app/conf
```

If you update a `alexis.conf.yaml` configuration on your local filesystem, restart the corresponding container.
However, if you update or add a Rule to the classifier/conf/rules directory, this does not require a restart of the Classifier.  Rules are retrieved at each execution of the Classifier API.

### Docker Networking

With Docker, you can create internal networks which never have to leave the Docker context.

We chose to use an internal Docker network as the default communication to improve portability of Alexis, but ports are also exposed for the Classifier and Action_Handler APIs on the Docker Host.

### API Access

After some consideration, we chose _not_ to implement a message queue like RabbitMQ or Kafka, and instead designed APIs for component interaction.

This not only reduced components and dependencies, but also allows us to design APIs which can be called directly.

We have already seen this pay off by allowing individuals to easily interface with Alexis and call the Action_Handler API (of course, with their own Authentication Token!)

### Rule Storage

Currently the rules are stored on disk, which is admittedly lazy, but it accomplishes the goal of storing rules.

As a guiding directive, we wanted to focus on making rules powerful and flexible so that it keeps rule storage to a minimum.

For instance, when we realized we accidentally limited the scope of a rule to only one pipeline stage, we refactored the Classifier code so that a single rule for the 'Duplicator' application could accomplish the same autoremediation task across Day, Sprint, and Prod.

### Logging With Reporting in Mind

As a quick and flexible reporting methodology, we are using logging as a data and metrics repository.

When we implement Autoremediation, we need to report against these kinds of questions:

1. What kind of autoremediation tasks are being executed?
1. Are our autoremediation executions successful?
1. What is the duration of our autoremediation tasks?
1. How many times have we executed _X_ autoremediation against _Y_ entity in the past _Z_ hours/days?

The Alexis components log in`key=value` syntax which can be extracted as key-value pairs for reporting.

### Keep A History

We also want to record the high-level history of our autoremediation tasks as close to the original source as possible.
The reporting option via logging should be additional, not primary.

Currently, we post back to the OpsGenie ticket, but we will soon work on posting status back to the Dynatrace Problem as well.
_This will be implemented by March 2018_


## Diagram: Detail of Poller

We wanted the Poller to be kept small and efficient, eliminating any processing or data validation.


![Diagram: Detail of Poller](/images/diagram-detail-of-poller.png)


Section not completed yet.


## Diagram: Detail of Classifier

Section not completed yet.



## Diagram: Detail of Action_Handler

Section not completed yet.
