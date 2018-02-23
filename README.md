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
    - [Detail of Alexis Stack](#detail-of-alexis-stack)
        - [Guiding Principle: Declarative Monitoring as Code](#guiding-principle-declarative-monitoring-as-code)
        - [Diagram: Explicit Rules vs Monitoring as Code](#diagram-explicit-rules-vs-monitoring-as-code)
        - [Other Guiding Principles](#other-guiding-principles)
        - [Diagram: Detail of Alexis Stack](#diagram-detail-of-alexis-stack)
        - [Dynatrace Integration with OpsGenie](#dynatrace-integration-with-opsgenie)
        - [Docker Bind Mounts](#docker-bind-mounts)
        - [Docker Networking](#docker-networking)
        - [API Access](#api-access)
        - [SSL for API Endpoints](#ssl-for-api-endpoints)
        - [Scaling out the Docker stack in Swarm](#scaling-out-the-docker-stack-in-swarm)
        - [Rule Storage](#rule-storage)
        - [Logging With Reporting in Mind](#logging-with-reporting-in-mind)
        - [Keep A History](#keep-a-history)
    - [Detail of Poller](#detail-of-poller)
    - [Detail of Classifier](#detail-of-classifier)
    - [Detail of Action_Handler](#detail-of-action_handler)
    - [Alexis Deploy and Automation Testing](#alexis-deploy-and-automation-testing)
        - [Code Integration Tests into the Foundation](#code-integration-tests-into-the-foundation)
        - [Develop Automated Functional Testing](#develop-automated-functional-testing)


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
- There is a lot of intentional logging which allows you to trace behavior in the stack.  To view these logs from CLI, of course you can use `docker container logs`.  But if you output these to a log management system, you can benefit from a wealth of logging data which helps extensively with debugging.  And if you get more clever, you can even build reports which tell you the number of autoremediation actions, the average duration of each action, failed autoremediation actions, and more.

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

This section describes the Alexis stack in greater detail, includes diagrams, and explains the concepts behind the design.


## Detail of Alexis Stack

### Guiding Principle: Declarative Monitoring as Code

The team which designed the initial blueprint for this Alexis project had worked on various automation, monitoring, and alerting projects in the past.

The most important principle was to do the following:

- _*Design with declarative monitoring-as-code which can be re-used for infinite possibilities*_

In Site Reliability Engineering and automation efforts, it is a common pitfall to code in "single-use" programs.  Similar problems might be solved a dozen times before the team starts considering that it could be have been designed comprehensively *one time as an engine*, with *dozens of configurations* to drive it.

As an example of how this plays out in coding, the Classifer Rule could have simply allowed `description` or `message` or `entity` as the keys which can be searched.
Most of the time, this would probably be sufficient for OpsGenie.

But, hard-coding "description|message|entity" into our applications would have limited the potential to only those 3 keys.

So, instead, the Classifier's Rules specify `search_key` and `search_text`.

As long as the `search_key` exists in the incoming alert, we can search for any text within that key's value.

This is a significant departure from only thinking of 1-3 possible use cases and limiting the code to only those _currently-imaginable keys_.

_@aarontimko --> An acknowledgement is needed here as I have borrowed my colleague Andi Grabner's terminology of "monitoring as code" in this documentation [GitHub: grabnerandi](https://github.com/grabnerandi) [Twitter: grabnerandi](https://twitter.com/grabnerandi)_


### Diagram: Explicit Rules vs Monitoring as Code

![Diagram: Explicit Rules](/images/diagram-explicit-rules.png)

![Diagram: Declarative Monitoring as Code](/images/diagram-declarative-monitoring-as-code.png)

---------------------------------------------------------

### Other Guiding Principles

Here are some of other ideas and principles:

- Separate configuration from code
- Share only the bare minimum code between Alexis components
- Design with portability in mind
- Include CI/CD concepts in the dev/build/deploy/test pipeline
  - See [Alexis Deploy and Automation Testing](#alexis-deploy-and-automation-testing))
- Consolidate to a few technologies and languages
  - e.g. do not over-complicate with extra technologies (Nginx, message queue, MongoDB) whose presence add a higher degree of complexity than the tangible valued gained by their addition.
- Log all activity with reporting in mind, especially remember to log the unique id of the incoming data
  - e.g. OpsGenie has a 'tinyId' which is unique to each alert and this tinyId value is logged on the majority of log statements during autoremediation

That last principle is often deprioritized in Operations automation projects.  There are many autoremediation products which perform tasks but never allow easy reporting on what was performed, how often, and when.

From the point of view of this Alexis project, reporting about automation tasks should always be easy to locate and included from the foundation of the code.

### Diagram: Detail of Alexis Stack

![Diagram: Detail of Alexis Stack](/images/diagram-detail-of-alexis-stack.png)

### Dynatrace Integration with OpsGenie

It is a straightforward task to send outbound Problems from Dynatrace and receive that data in OpsGenie.

1. Create a Dynatrace Integration in OpsGenie and record the Integration key.
1. Create an OpsGenie Integration in Dynatrace and enter the OpsGenie Integration key.

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

You can see this in the diagram above:
- Classifier: http://docker_host:8083/v1
- Action Handler: http://docker_host:8084/v1

### API Access

After some consideration, we chose _not_ to implement a message queue like RabbitMQ or Kafka, and instead designed APIs for component interaction.

This decision reduced components and dependencies, which was a core directive of this project.
In previous endeavors, we have seen automation projects take on a life of their own, leading to underused databases and technologies which then have to be maintained, secured, upgraded, and so on.

Focusing on API development, we have already seen this pay off by allowing individuals to easily interface with Alexis and call the Action_Handler API (of course, with their own Authentication Token!)

The APIs for Classifier and Action_Handler run on uWSGI with a Bottle framework (see https://uwsgi-docs.readthedocs.io and https://bottlepy.org/docs/dev/)
See the Dockerfiles for Classifier and Action_Handler to examine the default process and thread settings.

### SSL for API Endpoints

SSL certificates can be implemented with uWSGI.
This project is not designed to handle the implementation and troubleshooting of SSL in your environment.
But you would need to do these basic steps:

1. Create new Dockerfiles for Classifier and Action_Handler with the steps below.
1. `ADD` your certs to the `WORKDIR /usr/src/app` location (e.g. `/usr/src/app/certs/your-company.crt` and `/usr/src/app/certs/your-company.key`)
1. Add these options to the `CMD` uWSGI execution:
```
"--https", "0.0.0.0:80,certs/your-company.crt,certs/your-company.key"
```

The Docker Host's exposed ports can still remain on 8083 and 8084:
- Classifier: https://docker_host:8083/v1
- Action Handler: https://docker_host:8084/v1

### Scaling out the Docker stack in Swarm

This project has not been tested to run multiple instances of Poller, Classifier, and Action_Handler.
For this reason, the docker-compose file specifies `replicas:1`

The main reason we went with Swarm mode was to enable the use of Secrets for the autoremediation user's SSH key.  As of Feb 2018, Docker secrets are only available to swarm services.
https://docs.docker.com/engine/swarm/secrets 

### Rule Storage

In alignment with our decision to not implement a message queue (see [API Access](#api-access)), we wanted to avoid using a database unless it was technically mandatory.
Therefore, currently the Classifier rules are stored on disk, which admittedly is not robust, but it accomplishes the goal of simple rule storage.

Also, as a guiding directive we wanted to focus on making rules powerful and flexible so that it keeps rule storage to a minimum.

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


## Detail of Poller

### Introduction to Poller

**Purpose**

The purpose of the Poller is to process one or more feeds and push those feeds in JSON format to another endpoint.

**Lean and Performant**

We wanted to keep the Poller small and efficient, so there is no logic to parse or understand the incoming data.

Theoretically, the Poller can poll multiple feeds and deliver the content of those feeds to identical or distinct Classifiers.


![Diagram: Detail of Poller](/images/diagram-detail-of-poller.png)

### Configuration of Poller

The configuration file is located here: `./docker/github/poller/conf/alexis.conf.yaml`

### Methodology of Poller

There are two important considerations for polling a feed of alerts or problems:

- Limit the lookback timeframe (e.g. don't look for All Problems)
- Only poll for Problems which have not been sent on for autoremediation.
  - This is where [Keep A History](#keep-a-history) is important because we post back to the original Problem feed whether we are working on a Problem already or not

With both OpsGenie and Dynatrace APIs, there is an _API for a Summary of Problems_ and there is an _API for the verbose Problem details_.

Whether you are polling OpsGenie or Dynatrace, you will need to account for this and perform an initial poll for the list, then invidivual calls for the verbose details.


## Detail of Classifier

### Introduction to Classifier

**Purpose**

The purpose of the Classifier is to receive incoming data in JSON and compare that properties of that data against a rule set which is also in JSON.  If there is a rule match, the Classifier combines the incoming JSON and rule JSON and pushes the merged JSON to an Action_Handler endpoint.

**Declarative**

The Classifier is designed with declarative programming concepts so that a simple rule file can "tell" the Classifier how to classify and route incoming data.

**Classify and Route**

The Classifier serves both the purpose of being a Classifier and a Router.

We wanted to allow engineers to program their own Classifier functions which could route to their own Action_Handlers.

For instance, if someone wants to design a Classifier schema for ServiceNow, they can also design an Action_Handler which could receive the routed alert and call the ServiceNow APIs.

![Diagram: Detail of Classifier](/images/diagram-detail-of-classifier.png)

### Configuration of Classifier

The configuration file is located here: `./docker/github/classifier/conf/alexis.conf.yaml`

### Methodology of Classifier

As mentioned above, rule storage is currently on disk.
You can find examples rules in: `./docker/github/classifier/conf/rules`

The most important feature behind the Classifier is described in detail in this section: 
[Guiding Principle: Declarative Monitoring as Code](#guiding-principle-declarative-monitoring-as-code)


## Detail of Action_Handler

### Introduction to Action Handler

**Purpose**

The purpose of the Action_Handler is to receive incoming, merged Alert+Rule JSON and to take actions based upon the declarative logic in the Rule portion of the incoming JSON.

**Extensible**

Currently, the Action_Handler's primary **"action"** is performing an SSH connection and running a one-liner on a remote host.  

However, the code is structured to allow extension with new functions to handle new Actions.

In future releases, we aim to make these extensibility similar to the "plugin" concept.

![Diagram: Detail of Action_Handler](/images/diagram-detail-of-action-handler.png)

### Configuration of Action Handler

The configuration file is located here: `./docker/github/action_handler/conf/alexis.conf.yaml`

### Methodology of Action Handler

The current Action Handler plugin does basic error handling for the remote SSH call.  It also will log the return output from the SSH command in order to report on success or to diagnose problems.

Here is an excerpt of logged statements by the Action Handler's SSH handler:

```
2018-02-18 01:28:13,654 [INFO]  Action_Handler::Action - ActionStart (Thread-5) 
entity="wayvsymdup01.dev.saasapm.com" command="sudo systemctl restart duplicator; 
sudo systemctl status duplicator | grep Active:" key="/run/secrets/autoremediation_id_rsa" 
user="autoremediation" tinyId="3292"
2018-02-18 01:28:21,484 [INFO]  Action_Handler::Action - ActionResult (Thread-5) 
result="[b'   Active: active (running) since Sun 2018-02-18 01:28:21 UTC; 21ms ago\n']" 
tinyId="3292"
2018-02-18 01:28:21,484 [INFO]  Action_Handler::Action - ActionFinished (Thread-5) 
rule_name="hostvalue_duplicator_garbagecollection_restartservice" 
entity="wayvsymdup01.dev.saasapm.com" action="restart_service" 
action_reason="garbage_collection_or_memory_exhausted" action_status="success" 
app_elapsed_ms="7831" tinyId="3292" 
result="[b'   Active: active (running) since Sun 2018-02-18 01:28:21 UTC; 21ms ago\n']"
```

Note these important steps:

1. `ActionStart`: we can see the `entity` we are running the command against, the `command`, and the OpsGenie `tinyId` can tie back to the original Problem
1. `ActionResult`: this is the raw text returned by the SSH function in Python, note the OpsGenie `tinyId` can tie back to the original Problem
1. `ActionFinished`: this is where we have basic error handling to determine `action_status="success"`, we are logging the `action_reason` and `rule_name`, and the OpsGenie `tinyId` can tie back to the original Problem

This is where you can observe "logging" as one of the [Guiding Principles](#other-guiding-principles) and [Logging With Reporting in Mind](#logging-with-reporting-in-mind).

Even by simply grepping for a tinyId through the Alexis stack, you can observe the progress of autoremediation all the way to the final stage.

If the SSH connection bombs out, the "ActionResult" line will show `ERROR connection failed` which the SSH plugin will catch and report back in the `ActionFinished` log event: `action_status="failed"`

And if we want to graph the `app_elapsed_ms` for all occurrences of `action=restart_service`, we can send our logs to a log management platform with key-value pair extraction capabilities.

- _*In sum, a well-defined Action Handler plugin should always provide Answers which are readily available any time we want to pose Questions to our data.*_

.

## Alexis Deploy and Automation Testing

With this project, coding new features needed to be quick and deployment/testing needed to be near-effortless.

We were overhauling a bunch of old code and bringing in new ideas, so we knew there were going to be mistakes and gaps in our coding.

From our [Guiding Principles](#guiding-principles), we were separating configuration from code early in the development process.

- Code in Python, build with Dockerfile into a Docker image (**code**)
- Store YAML and JSON in Git, push/pull (**configuration**)

Since this is a modular (and still small) project, we also wanted to reduce the emphasis on extensive unit testing, relying instead on integration and functional testing.

This is how we are accomplishing efficient integration and functional testing today.

### Code Integration Tests into the Foundation

_Section not completed yet._

### Develop Automated Functional Testing

_Section not completed yet._