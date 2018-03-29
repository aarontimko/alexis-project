import requests
import calendar

import alexis.common
from alexis.common import *

import alexis.dynatrace as dynatrace
import alexis.opsgenie as opsgenie


#   -----------------------------------   #
#            LOCAL FUNCTIONS
#   -----------------------------------   #

def build_url_with_lookback(url, lookback, lookback_unit="s", epoch_unit="ms"):
    """
    Takes a url with "$lookback" as a variable placeholder
    Takes a lookback value (default lookback_unit is:"sec")
    Calculates epoch calculated from now (default epoch_unit="ms")
    Returns url with epoch time in place of "$lookback"

    Attributes:
        url (str): a url string with '$lookback" within that string
        lookback (int): number of time to subtract from now()
        lookback_unit (str): defines unit of lookback: s|m|h
        epoch_unit (str): defines unit of lookback: ms|s
    """

    # Check incoming parameters
    if lookback_unit not in ["s", "m", "h"]:
        return "ERROR: lookback_unit is not: s|m|h"

    if epoch_unit not in ["ms", "s"]:
        return "ERROR: lookback_unit is not: ms|s"

    if "$lookback" not in url:
        return "ERROR: url must contain the variable placeholder: '$lookback'"

    # Grab current time
    now = calendar.timegm(time.gmtime())

    # Calculate lookback_unit
    if lookback_unit == "s":
        lookback_delta = lookback
    if lookback_unit == "m":
        lookback_delta = lookback*60
    if lookback_unit == "h":
        lookback_delta = lookback*3600

    # Calculate lookback_epoch
    epoch = now - int(lookback_delta)

    # Append "000" if epoch_unit == ms
    if epoch_unit == "ms":
        epoch = str(epoch) + '000'
    else:
        epoch = str(epoch)

    # String replacement for variable
    url = url.replace('$lookback', epoch)

    # String replacement for HTML encoding
    # url = url.replace("=", "%3D")
    # url = url.replace(" ", "%20")
    # url = url.replace(">", "%3E")
    # url = url.replace("<", "%3C")

    return url

def build_individual_url(url, uniqueid):
    """
    Takes a url with "$uniqueid" as a variable placeholder
    Returns url with the specified $uniqueid

    Attributes:
        url (str): a url string with '$uniqueid" within that string
        id (str): id of event
    """

    # String replacement for variable (old manner which was opsgenie-specific)
    url = url.replace('$tinyid', uniqueid)

    # String replacement for variable
    url = url.replace('$uniqueid', uniqueid)

    return url

def try_obtain_runtime_token(token_runtime_file):
    """
    Check for runtime token
    Every Alexis app must have a designated token
    which is registered with destination Alexis components

    Attributes:
        token_runtime_file (str): location of token file on disk
    """

    # GRAB TOKEN FOR CONNECTING TO OTHER HOSTS
    log_to_disk('Token',
                msg='GrabbingToken',
                debug=True,
                kv=kvalue(token_runtime_file=token_runtime_file))
    token_runtime = None
    token_runtime = grab_runtime_from_disk(token_runtime_file)

    if token_runtime is None:
        # Wrap up script
        wrap_up_app()

        if app_conf['development'] == True:
            quit_app()

    # We have grabbed our token file, we are ready to proceed

    if token_runtime is not None:
        if token_runtime['id']:
            log_to_disk('Token', msg='TokenObtained',
                        kv=kvalue(token_runtime_id=token_runtime['id']))
            return token_runtime

def try_obtain_feed_headers(feed):
    feed_auth = None

    for auth_item in authentication_list:
        if feed['authentication'] in auth_item['unique_name']:
            # Define feed_auth variable for the feed
            feed_auth = auth_item

    if feed_auth == None:
        log_to_disk('Authentication', lvl="ERROR",
                    msg="No authentication named: " + feed['authentication'],
                    kv=kvalue(feed_name=feed['name'])
                    )
        return False
    else:
        # Define feed_headers variable for the feed
        feed_headers = json.loads(feed_auth['headers'].replace("'", '"'))

        return feed_headers

def try_request(f_url, f_headers, log_category, error_msg,
                log_key, log_value, f_dict, m="get"):
    """
    Custom function to error handle Requests and output logging
    in a standardized format for Alexis

    Attributes:
        f_url (str): url for requests.get
        f_headers (dict): auth header in json format
        log_category (str): for logging, e.g. 'Poll' in "Poller::Poll"
        error_msg (str): descriptive error message if request fails
        log_key (str): key which ties all the log events together for reporting
                    e.g. feed_name, problem_id in Poller
        log_value (str): unique value for the log_key
                    e.g. "Test_AllOpenProblems_Syn.Day" -> feed_name value
                    e.g. "6685385694655871934"          -> problem_id value
        f_dict (dict): dictionary to store results
               note: must be defined before this function is called
        m (str): get, post, put, delete
    """

    # Attempt requests
    response = None

    # Determine method type
    if m == "get":
        requests_type = requests.get
    if m == "post":
        requests_type = requests.post
    if m == "put":
        requests_type = requests.put
    if m == "delete":
        requests_type = requests.delete

    try:
        response = requests_type(f_url, headers=f_headers)
    except requests.exceptions.RequestException as e:
        log_to_disk(log_category, lvl='ERROR',
                    msg="RequestsError "+log_key+"="+log_value,
                    kv=kvalue(exception=e))
        log_to_disk(log_category, lvl="ERROR",
                    msg=error_msg+" "+log_key+"="+log_value,
                    kv=kvalue(url=f_url))

    # If we received response, continue
    if response is not None:
        f_dict['results'] = response
        f_dict['statusCode'] = f_dict['results'].status_code
        log_to_disk(log_category,
                    msg="HTTPResponse "+log_key+"="+log_value,
                    kv=kvalue(requests_status_code=f_dict['statusCode']))

        # Non-HTTP 200 response
        if f_dict['statusCode'] != 200:
            log_to_disk(log_category, lvl="ERROR",
                        msg="RequestsResults "+log_key+"="+log_value,
                        kv=kvalue(requests_content=f_dict['results'].content))
            return False

        # Check for HTTP 200 response
        if f_dict['statusCode'] == 200:
            f_dict['elapsed'] = \
                str(f_dict['results'].elapsed.microseconds)[:-3]
            f_dict['json'] = json.loads(f_dict['results'].content)

            # Optional development logging: output raw f_dict['json']
            if app_conf['development'] is True:
                print(f_dict['json'])

            log_to_disk(log_category,
                        msg="RequestsResults "+log_key+"="+log_value,
                        kv=kvalue(requests_elapsed_ms=f_dict['elapsed'])
                        )
        #return
        return True

    else:
        # response is None and no exception was caught
        log_to_disk(log_category, lvl="ERROR",
                    msg="requests response is None, no exception caught "+\
                        log_key+"="+log_value,
                    kv=kvalue(url=f_url))
        # return
        return False

# TODO: Grab the try_request version from dynatrace.py
# TODO: replace statusCode with status_code for normalization

def try_post_component(f_url, f_json, log_category, log_key, log_value):
    """
    Custom function to error handle requests POST

    Attributes:
        f_url (str): url for requests.post
        j_json (dict): json to POST
        log_category (str): for logging, e.g. 'Poll' in "Poller::Poll"
        error_msg (str): descriptive error message if request fails
        log_key (str): key which ties all the log events together for reporting
                    e.g. problem_id
        log_value (str): unique value for the log_key
                    e.g. "6685385694655871934"          -> problem_id value
    """

    # Try a POST
    post_response = None
    try:
        post_response = requests.post(f_url, json=f_json)
    except requests.exceptions.RequestException as e:
        log_to_disk(log_category, lvl='ERROR',
                    msg="PushError " + log_key + "=" + log_value,
                    kv=kvalue(exception=e))
        log_to_disk(log_category, lvl='ERROR',
                    msg="PushError "+log_key+"="+log_value,
                    kv=kvalue(url_endpoint=f_url,
                              status="failure"))
        return False

    # Checking for a POST result
    if post_response is not None:
        http_content = post_response.content.decode("utf-8")
        if post_response.status_code == 200:
            log_to_disk(log_category,
                        msg="PushSuccess " + log_key + "=" + log_value,
                        kv=kvalue(url_endpoint=f_url,
                                  requests_status_code=post_response.status_code,
                                  status="success",
                                  http_content=http_content)
                        )
            return True
        else:
            log_to_disk(log_category, lvl='ERROR',
                        msg="PushError " + log_key + "=" + log_value,
                        kv=kvalue(url_endpoint=f_url,
                                  requests_status_code=post_response.status_code,
                                  status="failure",
                                  http_content=http_content)
                        )
            return False


def ping_component(component, component_health_url):
    log_to_disk('Ping',
                msg='HealthCheck - Pinging '+component,
                debug=True,
                kv=kvalue(component_health_url=component_health_url))

    # ATTEMPT TO PING
    response = None

    try:
        response = requests.get(component_health_url)
    except requests.exceptions.RequestException as e:
        log_to_disk('Ping', lvl='ERROR',
                    msg='HealthCheckError',
                    kv=kvalue(exception=e))
        log_to_disk('Ping', lvl="ERROR",
                    msg='HealthCheckError Unable to ping',
                    kv=kvalue(component_health_url=component_health_url))

    if response is not None:
        requests_status_code = response.status_code
        log_to_disk('Ping', msg="HTTPResponse",
                    kv=kvalue(component_health_url=component_health_url,
                              requests_status_code=requests_status_code))


#   -----------------------------------   #
#            VARIABLES
#   -----------------------------------   #

# GENERAL VARIABLES
alexis.common.app_name = "Poller"
alexis.common.app_logdir = "log"

# app_name_2017-11-06.log
app_logfile_string = alexis.common.app_name.lower() + \
                 "_" + str(get_date()) + ".log"

alexis.common.app_logfile = os.path.join(alexis.common.app_logdir,
                                         app_logfile_string)

# RUNTIME VARIABLES
conf_dir = 'conf'
conf_file = 'alexis.conf.yaml'
alexis_conf = grab_yaml_from_disk(os.path.join(conf_dir,conf_file))
app_conf = alexis_conf[alexis.common.app_name.lower()]
token_conf = app_conf['tokens']
token_runtime_file = os.path.join(conf_dir, str(token_conf['directory']), str(token_conf['runtime']))
authentication_list = alexis_conf['authentication_list']
feed_list = app_conf['feed_list']


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
#            SCRIPT ACTIONS
#   -----------------------------------   #


# Main loop with code
def main_loop():

    # BEGIN LOGGING AND START APP TIMER
    start()

    # LOOP THROUGH FEED LIST
    for feed in feed_list:

        # Define 'm' as the module which matches the feed type
        m = globals()[feed['type']]

        # Pass app_conf to the module
        m.pass_app_conf(primary_app_conf=app_conf)

        # Declare 'go_process_feed_results' for each feed
        # Certain conditions must be met before processing the feed
        go_process_feed_results = False

        # Extend Alexis: feed_type
        # com.dynatrace.alexis.autoremediation.feed_type
        #
        # Some feed types require an authentication header
        # Other feed types rely on a token in the URL parameters
        #

        if 'authentication' in feed:
            feed_headers = m.try_obtain_feed_headers(feed, authentication_list)

        # ------------- End of Extend Alexis -------------

        # Extend Alexis: feed_type
        # com.dynatrace.alexis.autoremediation.feed_type
        # Some feed types have a simple API call which requires few params
        # Other feed types require more parameters and calculated parameters
        #

        if 'lookback' and 'lookback_unit' in feed:
            feed_lookback_url = \
                m.build_feed_lookback_url(
                    base_url=feed['base_url'],
                    feed_url=feed['feed_url'],
                    lookback=feed['lookback'],
                    lookback_unit=feed['lookback_unit'])
        else:
            feed_lookback_url = m.build_feed_lookback_url(
                base_url=feed['base_url'],
                feed_url=feed['feed_url'])


        # Log polling values
        log_to_disk('PollFeed', msg="PollValues",
                    kv=kvalue(feed_name=feed['name'],
                              feed_url=feed_lookback_url))

        # POLL SUMMARY FEED
        feed_response = {}
        initial_feed_response = False
        initial_feed_response = try_request(
            f_url=feed_lookback_url,
            f_headers=feed_headers,
            log_category='PollFeed',
            error_msg='PollFailure Unable to poll',
            log_key='feed_name',
            log_value=feed['name'],
            f_dict=feed_response)

        # CHECK FOR VALID HTTP RESPONSE
        if initial_feed_response == False:
            # Feed did not have valid HTTP response, we cannot continue
            wrap_up_app(status="failure")
            return
        else:
            # Extend Alexis: feed_type
            # com.dynatrace.alexis.autoremediation.feed_type
            # feed['data'] must contain the list of problems, tickets, alerts
            #
            # To add another feed['type'], declare how to locate feed['data']
            # in the HTTP response

            feed['data'] = m.get_feed_data(feed_response)

            # if feed['type'] == 'dynatrace':
            #     feed['data'] = feed_response['json']['result']['problems']    #TODO: call dynatrace.feed_response  feed['type'].feed_response
            # if feed['type'] == 'opsgenie':
            #     feed['data'] = feed_response['json']['data']

            # ------------- End of Extend Alexis -------------

            # Log feed elapsed and feed count
            feed['count'] = len(feed['data'])
            log_to_disk('PollFeed', msg="PollResults",
                        kv=kvalue(feed_name=feed['name'],
                                  feed_count=feed['count']))

        # CHECK FOR FEED COUNT
        if initial_feed_response == True and feed['count'] == 0:
            # Feed was valid but had no records, no need to continue
            log_to_disk('PollFeed',
                        msg='PollResults - No records were located',
                        kv=kvalue(feed_name=feed['name'],
                                  status="nodata",
                                  feed_lookback=feed['lookback'],
                                  feed_lookback_unit=feed[
                                      'lookback_unit']))

            # But we can ping the Classifier as a keep-alive
            component = "Classifier"
            component_health_url = app_conf['classifier_destinations'][
                                     feed['type']] \
                                   + '/ping'
            ping_component(component, component_health_url)
            return
        else:
            go_process_feed_results = True

        if go_process_feed_results == True:
            for problem in feed['data']:

                # Extend Alexis: feed_type
                # com.dynatrace.alexis.autoremediation.feed_type
                # problem_id must contain a unique ID of each problem, ticket
                #
                # If you have added a new feed['type'],
                # declare how to locate the unique id of that feed type

                problem_id = m.get_problem_id(problem)

                log_to_disk('ProcessProblem', msg='Starting',
                            kv=kvalue(feed_name=feed['name'],
                                      problem_id=problem_id))


                # GRAB FULL DETAILS FOR EACH ITEM IN FEED

                # Extend Alexis: feed_type
                # com.dynatrace.alexis.autoremediation.feed_type
                # Most feeds have an API call to return a summary of problems,
                # and a separate API call to return full details of one problem
                #

                individual_url = m.build_individual_url(
                    base_url=feed['base_url'],
                    individual_url=feed['individual_url'],
                    uniqueid=problem_id)


                # Go poll the individual_url for the problem/alert
                # The return dictionary will be posted to the Classifier,
                # so it should contain all verbose data of the problem/alert

                post_item = None

                post_item = m.poll_individual_url(
                    problem_id=problem_id,
                    f_url=individual_url,
                    f_headers=feed_headers)


                if post_item:

                    # Extend Alexis: feed_type
                    # com.dynatrace.alexis.autoremediation.feed_type
                    # we must push the individual problems to a classifier
                    #
                    # there is always a default classifier, but if needed,
                    # you can specify  more granularity
                    #
                    # If you have added a new feed['type'],
                    # declare which classifier to deliver individual problems

                    # Augment post_item with feed details
                    post_item['alexis'] = {}
                    post_item['alexis']['feed_type'] = feed['type']
                    post_item['alexis']['feed_name'] = feed['name']
                    post_item['alexis']['base_url'] = feed['base_url']
                    post_item['alexis']['feed_headers'] = feed_headers
                    post_item['alexis']['unique_key'] = 'problem_id'
                    post_item['alexis']['unique_value'] = problem_id

                    # Determine classifier
                    classifier = app_conf['classifier_destinations'][
                                     feed['type']] \
                                 + '/classifier' \
                                 + '?token=' \
                                 + token_runtime['id']

                    # Optional development: output but do not send to classifier
                    if app_conf['debug'] is True:
                        print("SEND TO CLASSIFIER: " + problem_id)
                        print("SEND TO CLASSIFIER: " + str(post_item))

                    try_post_component(f_url=classifier,
                                       f_json=post_item,
                                       log_category='PushToClassifier',
                                       log_key='problem_id',
                                       log_value=problem_id)

                    log_to_disk('ProcessProblem', msg='Finished',
                                kv=kvalue(feed_name=feed['name'],
                                          problem_id=problem_id))

                else:

                    log_to_disk('ProcessProblem', msg='DontPushProblem',
                                kv=kvalue(feed_name=feed['name'],
                                          problem_id=problem_id))

                    log_to_disk('ProcessProblem', msg='Finished',
                                kv=kvalue(feed_name=feed['name'],
                                          problem_id=problem_id))


                    # ------------- End of Extend Alexis -------------

# END OF main_loop()


# Define loop_interval for app
loop_interval = app_conf['loop_interval']

# Begin loop
while True:
    start_time = time.time()

    # CHECK FOR RUNTIME TOKEN
    token_runtime = None
    token_runtime = try_obtain_runtime_token(token_runtime_file)

    # Do main loop
    if token_runtime is not None:
        main_loop()

    sleep_time = round(loop_interval -
                       ((time.time() - start_time) % loop_interval), 3)

    log_to_disk('Sleep', msg="SleepInterval",
                kv=kvalue(sleep_time=sleep_time))

    if app_conf['single_execution'] == True:
        break
    else:
        time.sleep(sleep_time)
