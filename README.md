# alexis-project-test

This project shows how the root cause analysis within Dynatrace Problems can drive autoremediation in your environment.

Currently the project focuses on immediate triage and resolution of an issue (Ops) rather than rolling back code (Dev).

But the ideas and the structure of this code can apply to any kind of "event-parse-act" workflow.

## Background

At Dynatrace, we have used OpsGenie as a provider for On-Call responsibilities.

Although we love that we can easily respond to alerts, shouldn't the goal of Operations be that we handle problems **proactively** with _rehearsed code_ rather than **reactively** with _improvised actions_?

At the onset of this project, we wanted to achieve two primary results:
- reduce MTTR (mean time to resolution)
- move from Receiving Alerts to Reviewing Reports (see optional logging endpoint)

We believe that this project satisfies both of those results and more.

## Simple Run

To cut through all of the documentation below, you can download and run with:

```
git clone --progress -v "https://github.com/aarontimko/alexis-project-test.git" alexis-project-test \
cd alexis-project-test \
docker stack deploy -c .\github_docker-compose.yaml alexis \
```

To tear down:

`docker stack rm alexis`

## Requirements

#### Docker
- We have tested 17.09.0 on both Windows and Linux
- The Docker Compose file will also need to pull images from Docker Hub (https://hub.docker.com/u/dynatracealexis/)
  - Note: the documentation on these is very minimal 
- Some functionality requires the Docker Node to be in Swarm Mode (docker swarm init)

#### GitHub
- Pull this repo onto your Windows/Linux machine which has Docker

#### Config changes
- If you just want to bring up the Docker Stack of containers, you don't need to change the default configuration from the Git pull
- But if you don't change the default configuration, you can't play with your own data :)

#### SSH Key management
- Currently, this project relies on an SSH key and user to SSH to remote systems and run commands.  This is the `run_command` task_type in the JSON rules in the Classifier conf/rules directory.  This was chosen because the content of the `run_command` can be specified to any one-liner and this keeps autoremediation options very flexible.
  - In `Action_Handler.py`, it would be very easy to create other autoremediation actions like task_type `call_ansible_playbook` or `servicenow_reboot_server`.  The idea was to leave `Action_Handler.py` as a microservice, but it could be extended with extra plugins in the /alexis directory (you can see there is a file specifically there for OpsGenie, named `opsgenie.py`)

#### Optional: logging endpoint
- There is a lot of very intentional logging which allows you to trace behavior in the stack.  To view these logs from CLI, of course you can use `docker container logs`.  But if you output these to a log management system, you can benefit from a wealth of logging data which helps extensively with debugging.  And if you get more clever, you can even build reports which tell you the number of autoremediation actions, the average duration of each action, failed autoremediation actions, and more.

## Configuration

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


## Versions

v1.01 - Initial commit


