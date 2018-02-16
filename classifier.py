from bottle import run, request, route, post, get, abort, default_app, HTTPResponse
import re
import requests
import alexis.common
from alexis.common import *
from alexis.opsgenie import *
import threading


#   -----------------------------------   #
#            LOCAL FUNCTIONS
#   -----------------------------------   #


def build_rule_list(data_type, directory, enabled_status="true"):
    # Initiate rule_list
    rule_list = []

    # Iterate through rules directory
    for rule_file in os.listdir(directory):
        rule_file = os.fsdecode(rule_file)

        # Only grab .json files
        if rule_file.endswith(".json"):

            # Grab json for rule
            # os.path.join for platform-independent operations
            rule_path = os.path.join(directory, rule_file)
            rule_json = grab_json_from_disk(rule_path)

            # only grab rules for the data_type of API endpoint
            if rule_json['alert_feed'] == data_type \
                    and rule_json['enabled'] == enabled_status:
                rule_list.append(rule_json)
            continue
        else:
            continue

    return rule_list


#   -----------------------------------   #
#            VARIABLES
#   -----------------------------------   #

# TODO: rename 'alexis' to 'common' and 'common.py' to 'main.py'

# GENERAL VARIABLES
alexis.common.app_name = "Classifier"
alexis.common.app_logdir = "log"

# app_name_2017-11-06.log
app_logfile_string = alexis.common.app_name.lower() + \
                 "_" + str(get_date()) + ".log"

alexis.common.app_logfile = os.path.join(alexis.common.app_logdir,
                                         app_logfile_string)


# INTERNAL VARIABLES

# M2M VARIABLES

# RUNTIME VARIABLES
conf_dir = 'conf'
conf_file = 'alexis.conf.yaml'
alexis_conf = grab_yaml_from_disk(os.path.join(conf_dir,conf_file))
app_conf = alexis_conf[alexis.common.app_name.lower()]
app_host = app_conf['listener']['hostname']
app_port = app_conf['listener']['port']
rules_dir = 'rules'
action_handler_dest = app_conf['action_handler_destinations']
token_conf = app_conf['tokens']
token_runtime_file = os.path.join(conf_dir, str(token_conf['directory']), str(token_conf['runtime']))
authentication_list = alexis_conf['authentication_list']

# TODO: Iterate through authentication_list
authentication = authentication_list[0]
headers = authentication['headers']
headers = json.loads(headers.replace("'", '"'))


# DEV AND DEBUG VARIABLES

# Check for Debug flag, default to False if it is not set in app_conf
if 'debug' in app_conf:
    if app_conf['debug'] is True:
        alexis.common.app_debug = True
    else:
        alexis.common.app_debug = False
else:
    alexis.common.app_debug = False


#   -----------------------------------   #
#            BOTTLE LISTENERS
#   -----------------------------------   #


@get('/v1/ping')
def index():

    # ENSURE TOKEN IS AVAILABLE
    log_to_disk('Token',
                msg='GrabbingToken',
                debug=True,
                kv=kvalue(token_runtime_file=token_runtime_file))
    token_runtime = None
    token_runtime = grab_runtime_from_disk(token_runtime_file)

    # Return error and quit
    if token_runtime is None:
        # QUIT SCRIPT
        abort(401, "Unable to access runtime_token:"+token_runtime_file)
    else:
        log_to_disk('Pong', msg='App is alive and runtime token is okay')


        # GO AHEAD AND PING ACTION_HANDLER TO ENSURE IT IS ALIVE
        ping_action_handler = app_conf['action_handler_destinations'][
                              'linux'] + '/ping'

        log_to_disk('Ping',
                    msg='HealthCheck - Pinging action_handler',
                    debug=True,
                    kv=kvalue(ping_action_handler=ping_action_handler))

        # ATTEMPT TO PING
        ping_results = None

        try:
            ping_results = requests.get(ping_action_handler)
        except requests.exceptions.RequestException as e:
            log_to_disk('Ping', lvl='ERROR',
                        msg='HealthCheckError',
                        kv=kvalue(exception=e))
            log_to_disk('Ping', lvl="ERROR",
                        msg='HealthCheckError Unable to ping',
                        kv=kvalue(ping_action_handler=ping_action_handler))

        if ping_results is not None:
            ping_statuscode = ping_results.status_code
            log_to_disk('Ping', msg="HTTPResponse",
                        kv=kvalue(ping_action_handler=ping_action_handler,
                                  ping_statuscode=ping_statuscode))

@post('/v1/opsgenie')
def index():
    # BEGIN LOGGING AND START APP TIMER
    start(app_component="Receive")

    # TOKEN VERIFICATION
    allowed_clients_file = \
        os.path.join(conf_dir, str(token_conf['directory']),
                     str(token_conf['allowed_clients']))
    allowed_clients = grab_json_from_disk(allowed_clients_file)
    incoming_token = request.query.token

    # Set token_match to False, then iterate through allowed_clients
    token_match = False
    for token in allowed_clients['token_list']:
        token = token['token']
        if incoming_token == token['id']:
            token_match = True
            client_token = token
            break

    # Final token verification steps and logging
    if token_match is False:
        log_to_disk('Auth', lvl="ERROR",
                    msg='AuthFailure Unable to authenticate client',
                    kv=kvalue(incoming_token=incoming_token))
        # Wrap up script
        wrap_up_app(app_component="Receive")
        # Return error and quit
        abort(401, "Sorry, access denied for token="+incoming_token)
    else:
        log_to_disk('Auth', msg='AuthSuccess',
                    kv=kvalue(incoming_token=incoming_token,
                              client_token=client_token))

        # Error handling for JSON loading
        # already performed in Bottle web framework
        incoming_data = request.json

        # Output full incoming data
        log_to_disk('Data', "json="+incoming_data.__str__())

        # Output message and tags
        log_to_disk('Data', msg='IncomingData',
                    kv=kvalue(tinyId=incoming_data['tinyId'],
                              message=incoming_data['message'],
                              tags=incoming_data['tags']))

        # SEND TO THREAD FOR PROCESSING DATA

        # Spawn thread to process the data
        t = threading.Thread(target=process_data, args=(incoming_data,))
        t.setDaemon(True)
        t.start()

        wrap_up_app(app_component="Receive")

        return HTTPResponse(status=200, body='{"received"="'
                                             + incoming_data['tinyId']+'"}')


def process_data(incoming_data):

    # Get Thread name
    thread_name = threading.currentThread().getName()

    # Start of processing
    start(app_component='Process ('+thread_name+')')

    # Log the Thread
    log_to_disk('Thread', msg='ThreadStart ('+thread_name+')',
                kv=kvalue(thread_name=thread_name))

    # define incoming data_type
    data_type = 'OpsGenie'

    # RULE PROCESSING
    rule_list = build_rule_list(data_type=data_type,
                                directory=os.path.join(conf_dir, rules_dir))
    log_to_disk('Rule', msg='RetrievingRules ('+thread_name+')',
                kv=kvalue(ruleCount=len(rule_list),
                          tinyId=incoming_data['tinyId']))

    # Set alert_matches_rule flag to false
    alert_matches_any_rule = False

    # Output rule_list
    for rule in rule_list:
        log_to_disk('Rule', msg='ProcessingRule ('+thread_name+')',
                    kv=kvalue(rule_name=rule['rule_name'],
                              rule_version=rule['rule_version'],
                              tinyId=incoming_data['tinyId']))

        # We are matching 'message' and 'tags' for each evaluation
        # So the needed evaluation matches is equal to 2x the number
        # of evaluations in the evaluation_list
        needed_evaluation_matches = 2*len(rule['evaluation_list'])
        matched_evaluation_count = 0

        # TODO: Check tag first, then do evaluations
        # TODO: (de-couple tag eval from search_key eval)
        # Check for each evaluation
        for evaluation in rule['evaluation_list']:

            # Check if tags exist on the data,
            # then check if tags on incoming_data match
            if incoming_data['tags'] != "[]":
                list1 = evaluation['evaluation']['tags']
                list2 = incoming_data['tags']

                # This is old behavior to look for an exact match
                #if sorted(list1) == sorted(list2):

                # Check if the Rule Evaluation Tags are a subset
                # of the Incoming Data tags
                # If so, then the Evaluation passes
                if (set(list1).issubset(list2)):
                    log_to_disk('Rule', msg='RuleEvaluation ('+thread_name+')',
                                kv=kvalue(matched="true",
                                          rule_name=rule['rule_name'],
                                          evaluation_tags=list1,
                                          incoming_data_tags=list2,
                                          tinyId=incoming_data['tinyId']))
                    matched_evaluation_count += 1

            # This compares the evaluation.search_text to the value of
            # evaluation.search_key in the incoming_data
            message1 = evaluation['evaluation']['search_text']
            message2 = incoming_data[evaluation['evaluation']['search_key']]
            if re.search(message1, message2) is not None:
                log_to_disk('Rule', msg='RuleEvaluation ('+thread_name+')',
                            kv=kvalue(matched="true",
                                      rule_name=rule['rule_name'],
                                      evaluation_search_text=message1,
                                      evaluation_search_key=evaluation['evaluation']['search_key'],
                                      incoming_data_value=message2,
                                      tinyId=incoming_data['tinyId']))
                matched_evaluation_count += 1

        # HOW WE GOT HERE:
        # All evaluations have been processed for the rule
        # NEXT:
        # If all evaluations were matched, then we need
        # to route this alert to the action_handler
        if needed_evaluation_matches == matched_evaluation_count:

            # Set this flag to True
            alert_matches_any_rule = True

            log_to_disk('Rule', msg='FinishedRule ('+thread_name+')',
                        kv=kvalue(rule_matched_alert='true',
                                  needed_evaluation_matches=needed_evaluation_matches,
                                  matched_evaluation_count=matched_evaluation_count,
                                  rule_name=rule['rule_name'],
                                  message=incoming_data['message'],
                                  tinyId=incoming_data['tinyId']))

            # Merge Rule and Alert into new JSON dict
            merged_alert_and_rule = \
                append_json_dict(incoming_data, "{'rule':", rule, "}")
            log_to_disk('Push', msg='MergedRuleAndAlert ('+thread_name+')',
                        kv=kvalue(tinyId=incoming_data['tinyId'],
                                  json=merged_alert_and_rule))


            # ENSURE TOKEN IS AVAILABLE
            log_to_disk('Token',
                        msg='GrabbingToken ('+thread_name+')',
                        debug=True,
                        kv=kvalue(token_runtime_file=token_runtime_file))
            token_runtime = None
            token_runtime = grab_runtime_from_disk(token_runtime_file)

            # Route to action_handler

            if merged_alert_and_rule['rule']['os_type'] == 'linux':
                # Define action_handler URL
                url_action_handler = action_handler_dest['linux'] \
                                  + '/action' \
                                  + '?token=' \
                                  + token_runtime['id']

                # Try a POST
                post_results = None
                try:
                    post_results = requests.post(url_action_handler,
                                                 json=merged_alert_and_rule,
                                                 verify=False)
                except requests.exceptions.RequestException as e:
                    log_to_disk('Push', lvl='ERROR',
                                msg='PushError ('+thread_name+')',
                                kv=kvalue(action_handler=action_handler_dest['linux'],
                                          status="failure",
                                          tinyId=incoming_data['tinyId']))
                    log_to_disk('Push', lvl='ERROR',
                                msg='PushError ('+thread_name+')',
                                kv=kvalue(tinyId=incoming_data['tinyId'],
                                          exception=e))

            # Checking for a POST result
            if post_results is not None:
                http_content = post_results.content.decode("utf-8")
                if post_results.status_code == 200:

                    # Grab the HTTP content result, which should be the
                    # returned unique ID (e.g. tinyId) which the endpoint
                    # has parsed from the JSON

                    log_to_disk('Push', msg='PushSuccess ('+thread_name+')',
                                kv=kvalue(action_handler=action_handler_dest['linux'],
                                          post_results=post_results.status_code,
                                          status="success",
                                          http_content=http_content))

                    # Add default_queue(team) to alert
                    opsgenie_add_team(thread_name=thread_name,
                                      tinyId=incoming_data['tinyId'],
                                      team=app_conf['default_remediation_queue'],
                                      headers=headers)

                else:
                    log_to_disk('Push', lvl='ERROR',
                                msg='PushError ('+thread_name+')',
                                kv=kvalue(action_handler=action_handler_dest['linux'],
                                          post_results=post_results.status_code,
                                          status="failure",
                                          http_content=http_content,
                                          tinyId=incoming_data['tinyId']))

        # else, the Rule did not match the Alert
        else:
            log_to_disk('Rule', msg='FinishedRule ('+thread_name+')',
                        kv=kvalue(rule_matched_alert='false',
                                  needed_evaluation_matches=needed_evaluation_matches,
                                  matched_evaluation_count=matched_evaluation_count,
                                  rule_name=rule['rule_name'],
                                  message=incoming_data['message'],
                                  tinyId=incoming_data['tinyId']))


    # HOW WE GOT HERE:
    # All rules have been processed
    # NEXT:
    # If no rules were met and this flag is still false,
    # then we will route the alert to a default queue
    if alert_matches_any_rule is False:

        # This is outside of the "for rule in rule_list:" loop
        # so that it does not trigger for every failed rule
        #
        # Add default_investigation_queue team to alert
        opsgenie_add_team(thread_name=thread_name,
                          tinyId=incoming_data['tinyId'],
                          team=app_conf['default_investigation_queue'],
                          headers=headers)


    # Wrap up script
    wrap_up_app(app_component='Process ('+thread_name+')')

    # POSTBACK_URL = 'http://127.0.0.1:8080/postprocessed'
    #
    # @bottle.post('/postprocessed')
    # def postprocessed_handle():
    #     print('Received data at postprocessed')
    #     return bottle.HTTPResponse(status=200, body="Complete postprocessed")

    # print('Finished processing')
    # requests.post(POSTBACK_URL, data=result,
    #               headers={'Content-Type': 'application/json'})


# RUN SERVER
if __name__ == "__main__":
    run(host=app_host, port=app_port)
else:
    application = default_app()
