import requests
import calendar

import alexis.common
from alexis.common import *


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


def build_url_with_tinyid(url, tinyId):
    """
    Takes a url with "$tinyid" as a variable placeholder
    Returns url with specified tinyId of "$lookback"

    Attributes:
        url (str): a url string with '$lookback" within that string
        tinyid (int): id of event in OpsGenie
    """

    # String replacement for variable
    url = url.replace('$tinyid', tinyId)

    # String replacement for HTML encoding
    # url = url.replace("=", "%3D")
    # url = url.replace(" ", "%20")
    # url = url.replace(">", "%3E")
    # url = url.replace("<", "%3C")

    return url


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

# INTERNAL VARIABLES

# M2M VARIABLES

# RUNTIME VARIABLES
conf_dir = 'conf'
conf_file = 'alexis.conf.yaml'
alexis_conf = grab_yaml_from_disk(os.path.join(conf_dir,conf_file))
app_conf = alexis_conf[alexis.common.app_name.lower()]
token_conf = app_conf['tokens']
token_runtime_file = os.path.join(conf_dir, str(token_conf['directory']), str(token_conf['runtime']))
authentication_list = alexis_conf['authentication_list']
feed_list = app_conf['feed_list']

# TODO: Iterate through feed_list and authentication_list
feed = feed_list[0]
authentication = authentication_list[0]
headers = authentication['headers']
headers = json.loads(headers.replace("'", '"'))

# Build new URL with $lookback replacement
feed_lookback_url = \
    build_url_with_lookback(url=feed['url'],
                            lookback=feed['lookback'],
                            lookback_unit=feed['lookback_unit'])


# DEV AND DEBUG VARIABLES

# Change this if you are in development running manually for solo executions
manual_testing = False

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

    # Initialize variable for flow control
    go_process_results = False

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

        if manual_testing == True:
            quit_app()

    # HOW WE GOT HERE:
    # We have grabbed our token file, we are ready to proceed
    # NEXT:
    # Now we will check the feed and then do error handling
    # If we receive results, we will set flag: go_process_results = True
    # (Including the usual token_runtime['id'] as a basic security check)

    go_poll_feed = False

    if token_runtime is not None:
        if token_runtime['id']:
            log_to_disk('Token', msg='TokenObtained',
                        kv=kvalue(token_runtime_id=token_runtime['id']))
            go_poll_feed = True

    if go_poll_feed is True:
        # LOG THE POLLING VALUES
        log_to_disk('Poll', msg="PollValues",
                    kv=kvalue(feed_name=feed['name'],
                              feed_url=feed_lookback_url,
                              feed_lookback=feed['lookback'],
                              feed_lookback_unit=feed['lookback_unit']))


        # TODO: turn into Unit Test
        # ATTEMPT TO POLL
        feed_response = None
        try:
            feed_response = requests.get(feed_lookback_url, headers=headers)
        except requests.exceptions.RequestException as e:
            log_to_disk('Poll', lvl='ERROR', msg='PollError',
                        kv=kvalue(exception=e))
            log_to_disk('Poll', lvl="ERROR", msg='PollFailure Unable to poll',
                        kv=kvalue(feed_name=feed['name'],
                                  feed_url=feed_lookback_url))
            # QUIT SCRIPT
            wrap_up_app()

            if manual_testing is True:
                quit_app()

        # If we received response, continue
        if feed_response is not None:
            feed['results'] = feed_response
            feed['statusCode'] = feed['results'].status_code
            log_to_disk('Poll', msg="HTTPResponse",
                        kv=kvalue(feed_name=feed['name'],
                                  feed_status_code=feed['statusCode']))

            # Non-HTTP 200 response
            if feed['statusCode'] != 200:
                log_to_disk('Poll', lvl="ERROR", msg="PollResults",
                            kv=kvalue(feed_name=feed['name'],
                                      feed_content=feed['results'].content))
                wrap_up_app()

                if manual_testing is True:
                    quit_app()

            # Check for HTTP 200 response
            if feed['statusCode'] == 200:
                feed['elapsed'] = \
                    str(feed['results'].elapsed.microseconds)[:-3]
                feed['json'] = json.loads(feed['results'].content)
                feed['data'] = feed['json']['data']
                feed['count'] = len(feed['data'])
                log_to_disk('Poll', msg="PollResults",
                            kv=kvalue(feed_name=feed['name'],
                                      feed_elapsed_ms=feed['elapsed'],
                                      feed_count=feed['count']))

                # Check for number of feed results
                if feed['count'] == 0:
                    log_to_disk('Poll',
                                msg='PollResults - No records were located',
                                kv=kvalue(feed_name=feed['name'],
                                          status="nodata",
                                          feed_lookback=feed['lookback'],
                                          feed_lookback_unit=feed[
                                              'lookback_unit']))

                    # GO AHEAD AND PING CLASSIFIER TO ENSURE IT IS ALIVE
                    ping_classifier = app_conf['classifier_destinations'][
                        'opsgenie']+'/ping'

                    log_to_disk('Ping',
                                msg='HealthCheck - Pinging classifier',
                                debug=True,
                                kv=kvalue(ping_classifier=ping_classifier))

                    # ATTEMPT TO PING
                    ping_results = None

                    try:
                        ping_results = requests.get(ping_classifier)
                    except requests.exceptions.RequestException as e:
                        log_to_disk('Ping', lvl='ERROR',
                                    msg='HealthCheckError',
                                    kv=kvalue(exception=e))
                        log_to_disk('Ping', lvl="ERROR",
                                    msg='HealthCheckError Unable to ping',
                                    kv=kvalue(ping_classifier=ping_classifier))

                    if ping_results is not None:
                        ping_statuscode = ping_results.status_code
                        log_to_disk('Ping', msg="HTTPResponse",
                                    kv=kvalue(ping_classifier=ping_classifier,
                                              ping_statuscode=ping_statuscode))

                    # NOW WRAP UP
                    wrap_up_app()

                    if manual_testing is True:
                        quit_app()
                else:

                    # HOW WE GOT HERE:
                    # We have received a response
                    # We have a 200 response code,
                    # We have more than 0 records returned
                    # NEXT:
                    # Set flag to process results

                    go_process_results = True

    # HOW WE GOT HERE:
    # By this point in app, we have processed a feed successfully
    # and all error handling has passed and we have results we need to process
    # NEXT:
    # Now we will process the feed results
    # (Including the usual token_runtime['id'] as a basic security check)

    if token_runtime and go_process_results is True:
        for problem in feed['data']:
            tinyId = problem['tinyId']
            log_to_disk('Push', msg='ProcessingProblems',
                        kv=kvalue(feed_name=feed['name'],
                                  tinyId=tinyId))


            # GRAB FULL DETAILS FOR EACH ITEM IN FEED

            # Build new URL with $tinyid replacement

            tinyid_url = \
                build_url_with_tinyid(url=feed['url_individual'],
                                      tinyId=tinyId)

            requests_return = None
            try:
                requests_return = requests.get(tinyid_url,
                                               headers=headers)
            except requests.exceptions.RequestException as e:
                log_to_disk('Poll', lvl='ERROR', msg='GetError',
                            kv=kvalue(exception=e))
                log_to_disk('Poll', lvl="ERROR",
                            msg='GetFailure Unable to grab TinyId',
                            kv=kvalue(tinyId=tinyId,
                                      item_url=tinyid_url))

            # If we received response, continue
            if requests_return is not None:
                item = {}
                item['results'] = requests_return
                item['statusCode'] = item['results'].status_code
                log_to_disk('Poll', msg="HTTPResponse",
                            kv=kvalue(tinyId=tinyId,
                                      item_status_code=item['statusCode']))

                # Non-HTTP 200 response
                if item['statusCode'] != 200:
                    log_to_disk('Poll', lvl="ERROR", msg="GetResults",
                                kv=kvalue(tinyId=tinyId,
                                          item_content=item[
                                              'results'].content))
                    wrap_up_app()

                    if manual_testing is True:
                        quit_app()

                # Check for HTTP 200 response
                if item['statusCode'] == 200:
                    item['elapsed'] = \
                        str(item['results'].elapsed.microseconds)[:-3]
                    item['json'] = json.loads(item['results'].content)
                    print(item['json'])
                    item['data'] = item['json']['data']
                    log_to_disk('Poll', msg="GetResults",
                                kv=kvalue(tinyId=tinyId,
                                          item_elapsed_ms=item['elapsed']))

            # Determine classifier
            if feed['type'] == "opsgenie":
                feed_classifier = app_conf['classifier_destinations'][
                                      'opsgenie'] \
                                  + '/' \
                                  + feed['type'] + '?token=' \
                                  + token_runtime['id']

            # Try a POST to classifier
            post_results = None
            try:
                post_results = requests.post(feed_classifier, json=item['data'])
            except requests.exceptions.RequestException as e:
                print(e)
                log_to_disk('Push', lvl='ERROR', msg='PushError',
                            kv=kvalue(feed_name=feed['name'],
                                      feed_classifier=feed_classifier,
                                      status="failure",
                                      tinyId=tinyId))
                log_to_disk('Push', lvl='ERROR', msg='PushError',
                            kv=kvalue(tinyId=tinyId, exception=e))

            # Checking for a POST result
            if post_results is not None:
                http_content = post_results.content.decode("utf-8")
                if post_results.status_code == 200:
                    log_to_disk('Push', msg='PushSuccess',
                                kv=kvalue(feed_name=feed['name'],
                                          feed_classifier=feed_classifier,
                                          post_results=post_results.status_code,
                                          status="success",
                                          http_content=http_content))
                else:
                    log_to_disk('Push', lvl='ERROR', msg='PushError',
                                kv=kvalue(feed_name=feed['name'],
                                          feed_classifier=feed_classifier,
                                          post_results=post_results.status_code,
                                          status="failure",
                                          http_content=http_content))

        #print(feed)
        #print(item)

        # QUIT SCRIPT
        wrap_up_app()

        if manual_testing is True:
            quit_app()


# Define loop_interval for app
loop_interval = app_conf['loop_interval']

# Begin loop
while True:
    start_time = time.time()
    main_loop()

    sleep_time = round(loop_interval -
                       ((time.time() - start_time) % loop_interval),3)

    log_to_disk('Sleep', msg="SleepInterval",
                kv=kvalue(sleep_time=sleep_time))

    time.sleep(sleep_time)
