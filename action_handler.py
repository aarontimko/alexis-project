from bottle import run, request, route, post, get, abort, default_app, HTTPResponse
import subprocess
import alexis.common
from alexis.common import *
from alexis.opsgenie import *
import threading

#   -----------------------------------   #
#            LOCAL FUNCTIONS
#   -----------------------------------   #


def simple_ssh(entity, command, key, user):
    # Ports are handled in ~/.ssh/config since we use OpenSSH

    connection = user+'@'+entity

    ssh = subprocess.Popen(["ssh", "-i", key, connection, command],
                           shell=False,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    result = ssh.stdout.readlines()
    if result == []:
        error = ssh.stderr.readlines()
        #print("ERROR:"+error.__str__())
        return "ERROR:"+error.__str__()
    else:
        #print(result)
        return result

def obtain_entities(incoming_data):
    '''
    :param incoming_data: This will normally be the incoming_data
    :return: Returns 'r' dictionary with multiple keys
    '''

    # Grab rule
    rule = incoming_data['rule']

    # Create dictionary to return values
    r = dict()

    # Set our entity_methodology to None
    entity_methodology = None

    # Check if 'entity_type' is a key in the incoming rule
    if 'entity_type' in rule:
        # Check if the entity_type is 'explicit'
        if rule['entity_type'] == "explicit":
            # Check if 'entities' is a key in the incoming rule
            if 'entities' in rule:
                # Set r['entity_list'] to the explicit entities
                r['valid_keys'] = True
                r['entity_list'] = rule['entities']
                r['entity_methodology'] = "explicit"
            else:
                # Report: There is no 'entities' key
                r['success'] = False
                r['valid_keys'] = False
                r['entity_list'] = False
                r['msg'] = "KeyError - There is NO 'entities' key"

        # Check if the entity_type is 'keyvalue'
        if rule['entity_type'] == "keyvalue":
            # Check if 'entity_keyvalue' is a key in the incoming rule
            if 'entity_keyvalue' in rule:
                # Set r['entity_list'] to the keyvalue entities
                r['valid_keys'] = True
                r['entity_methodology'] = "entity_keyvalue"

                kv = rule['entity_keyvalue']
                kv_len = len(kv)

                # This code support the feature of specifying
                # 4 levels deep into the incoming_data structure
                if kv_len > 4:
                    r['entity_list'] = "UNABLETOPARSEENTITIES"
                if kv_len == 4:
                    r['entity_list'] = \
                        incoming_data[kv[0]][kv[1]][kv[2]][kv[3]]
                if kv_len == 3:
                    r['entity_list'] = incoming_data[kv[0]][kv[1]][kv[2]]
                if kv_len == 2:
                    r['entity_list'] = incoming_data[kv[0]][kv[1]]
                if kv_len == 1:
                    r['entity_list'] = incoming_data[kv[0]]

            else:
                # Report: There is no 'entity_keyvalue' key
                r['success'] = False
                r['valid_keys'] = False
                r['entity_list'] = False
                r['msg'] = "KeyError - There is NO 'entity_keyvalue' key"
    else:
        # Report: There is no entity_type in the rule,
        # this is a mandatory field
        r['success'] = False
        r['valid_keys'] = False
        r['entity_list'] = False
        r['msg'] = "KeyError - There is no 'entity_type' key in the rule" \
                   "and this is a mandatory field"

    # Convert a string instance to a list
    if isinstance(r['entity_list'], str):
        r['entity_list'] = [r['entity_list']]

    # Continue with processing the entities
    if r['valid_keys'] is True:
        # Ensure the entities are in an iterable list form
        # and not some other form
        if isinstance(r['entity_list'], list):
            r['success'] = True
            r['msg'] = "ValidEntities - The rule keys for entities are " \
                       "valid and the entities are in a list form"
            r['entity_count'] = len(r['entity_list'])

        else:
            # Report:  The entities are not in a list form
            r['success'] = False
            r['msg'] = "InvalidEntities - The rule keys for entities are " \
                       "valid BUT the entities are NOT in a list form"

    # Final return
        return r



#   -----------------------------------   #
#            VARIABLES
#   -----------------------------------   #


# CLEAR VALUES

# TIME VARIABLES

# GENERAL VARIABLES
alexis.common.app_name = "Action_Handler"
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
token_conf = app_conf['tokens']
token_runtime_file = os.path.join(conf_dir, str(token_conf['directory']), str(token_conf['runtime']))
ssh_key = app_conf['ssh_key']
ssh_user = app_conf['ssh_user']

authentication_list = alexis_conf['authentication_list']

# TODO: Iterate through feed_list and authentication_list
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


@post('/v1/action')
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

        # Output message and tags
        log_to_disk('Data', msg='IncomingData',
                    kv=kvalue(tinyId=incoming_data['tinyId'],
                              message=incoming_data['message'],
                              tags=incoming_data['tags'],
                              rule=incoming_data['rule']))

        # SEND TO THREAD FOR PROCESSING DATA

        # Spawn thread to process the data
        t = threading.Thread(target=process_data, args=(incoming_data,))
        t.start()

        wrap_up_app(app_component="Receive")

        return HTTPResponse(status=200, body='{"received"="'
                                             + incoming_data['tinyId']+'"}')


def process_data(incoming_data):

    # Get Thread name
    thread_name = threading.currentThread().getName()

    # Start of processing
    start(app_component='Process ('+thread_name+')')

    # Grab rule_name and task_list
    rule_name = incoming_data['rule']['rule_name']
    task_list = incoming_data['rule']['task_list']

    # Grab entities using local function
    e_result = obtain_entities(incoming_data)

    # Check if function: obtain_entities was NOT successful
    if e_result['success'] is False:
        log_to_disk('Entities', lvl='ERROR',
                    msg=e_result['msg'],
                    kv=kvalue(success=e_result['success'],
                              valid_keys=e_result['valid_keys'],
                              tinyId=incoming_data['tinyId']))
        wrap_up_app(app_component='Process (' + thread_name + ')',
                    status='failure')
    else:
        # function: obtain_entities was successful
        log_to_disk('Entities',
                   msg=e_result['msg'],
                   kv=kvalue(success=e_result['success'],
                             valid_keys=e_result['valid_keys'],
                             entity_methodology=e_result['entity_methodology'],
                             entity_list=e_result['entity_list'],
                             tinyId=incoming_data['tinyId']))
        # Assign entities
        entities = e_result['entity_list']

    # Iterate through task_list
    for task in task_list:

        # Grab the next level of json
        task = task['task']

        # run_command
        if task['task_type'] == 'remote_ssh':

            for entity in entities:
                log_to_disk('Action', msg='ExecutingAction ('+thread_name+')',
                            kv=kvalue(entity=entity,
                                      run_command=task['run_command'],
                                      tinyId=incoming_data['tinyId']))

                # If we are in Development mode, only output to console
                # and then add route_to_team to alert
                #
                # TESTING: action_status
                #

                if app_conf['development'] == "true":
                    print('simple_ssh:'+kvalue(entity=entity,
                                               action=task['action'],
                                               action_reason=task['action_reason'],
                                               action_status='testing',
                                               command=task['run_command'],
                                               key=ssh_key,
                                               user=ssh_user,
                                               tinyId=incoming_data['tinyId']))

                    # Add route_to_team to alert (includes logging)
                    opsgenie_add_team(
                        thread_name=thread_name,
                        tinyId=incoming_data['tinyId'],
                        team=incoming_data['rule']['route_to_team'],
                        headers=headers)

                # We are NOT in Development mode, continue
                # with live autoremediation
                else:
                    log_to_disk('Action',
                                msg='ActionStart (' + thread_name + ')',
                                kv=kvalue(
                                    entity=entity,
                                    command=task['run_command'],
                                    key=ssh_key,
                                    user=ssh_user,
                                    tinyId=incoming_data['tinyId']))

                    result = simple_ssh(entity=entity,
                                        command=task['run_command'],
                                        key=ssh_key,
                                        user=ssh_user)

                    log_to_disk('Action', msg='ActionResult ('+thread_name+')',
                                kv=kvalue(
                                    result=result,
                                    tinyId=incoming_data['tinyId']))

                    # This means ERROR text occurred in the simple_ssh
                    # execution.  It could be an SSH error or an ERROR
                    # returned by the shell command
                    #
                    # FAILURE: action_status
                    #
                    if 'ERROR' in result:
                        # Wrap up script
                        log_to_disk('Action', lvl='ERROR',
                                    msg='ActionFinished (' + thread_name + ')',
                                    kv=kvalue(entity=entity,
                                    action=task['action'],
                                    action_reason=task['action_reason'],
                                    action_status='failure',
                                    tinyId=incoming_data['tinyId'],
                                    result=result)
                                    )
                        wrap_up_app(app_component='Process ('+thread_name+')',
                                    status='failure')
                    else:
                        #
                        # SUCCESS: action_status
                        #
                        # Log Elapsed time for the successful run
                        log_to_disk('Action', msg='ActionFinished ('+thread_name+')',
                                    kv=kvalue(rule_name=rule_name,
                                              entity=entity,
                                              action=task['action'],
                                              action_reason=task['action_reason'],
                                              action_status='success',
                                              app_elapsed_ms=get_elapsed_ms(),
                                              tinyId=incoming_data['tinyId'],
                                              result=result))

                        # Add route_to_team to alert (includes logging)
                        opsgenie_add_team(
                            thread_name=thread_name,
                            tinyId=incoming_data['tinyId'],
                            team=incoming_data['rule']['route_to_team'],
                            headers=headers)

                        # Wrap up script
                        wrap_up_app(app_component='Process ('+thread_name+')',
                                    status='success')

        # systemctl
        if task['task_type'] == 'restart_service' \
                and task['task_method'] == 'systemctl':
            print("TODO")
            # TODO: Work on systemctl code

    # return successful processing of tinyId
    return incoming_data['tinyId']


# RUN SERVER
if __name__ == "__main__":
    run(host=app_host, port=app_port)
else:
    application = default_app()
