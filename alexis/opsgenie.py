import requests
import calendar

import alexis.common
from alexis.common import *


#   -----------------------------------   #
#            GENERIC FUNCTIONS
#   -----------------------------------   #

def pass_app_conf(primary_app_conf):
    # Pass app_conf from primary app to this module
    global app_conf
    app_conf = primary_app_conf


def try_request(f_url, f_headers, log_category, error_msg,
                log_key, log_value, f_dict, json_data="", m="get"):
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
        if json_data == "":
            response = requests_type(f_url, headers=f_headers)
        else:
            response = requests_type(f_url, headers=f_headers, json=json_data)
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
        if f_dict['statusCode'] >= 400:
            log_to_disk(log_category, lvl="ERROR",
                        msg="RequestsResults "+log_key+"="+log_value,
                        kv=kvalue(requests_content=f_dict['results'].content))
            return False

        # Check for HTTP 2xx response
        if 200 <= f_dict['statusCode'] <= 299:
            f_dict['elapsed'] = \
                str(f_dict['results'].elapsed.microseconds)[:-3]

            # Error handling for json in results.content
            try:
                f_dict['json'] = json.loads(f_dict['results'].content)
            except ValueError:
                f_dict['json'] = "{}"

            # Optional development logging: output raw f_dict['json']
            if app_conf['debug'] is True:
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


def try_obtain_feed_headers(feed, authentication_list):
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


#   -----------------------------------   #
#            POLLER FUNCTIONS
#   -----------------------------------   #


def build_feed_lookback_url(base_url, feed_url,
                            lookback, lookback_unit="s", epoch_unit="ms"):
    """
    The OpsGenie API has the ability to specify a epochms time
    in the search parameters, so we have allowed for specifying
    'lookback' values

    Takes a url with "$lookback" as a variable placeholder
    Takes a lookback value (default lookback_unit is:"sec")
    Calculates epoch calculated from now (default epoch_unit="ms")
    Returns url with epoch time in place of "$lookback"

    Attributes:
        base_url (str): a url string (https://www.domain.com)
        feed_url (str): a url string with '$base_url' and '$lookback'
        lookback (int): number of time to subtract from now()
        lookback_unit (str): defines unit of lookback: s|m|h
        epoch_unit (str): defines unit of lookback: ms|s
    """

    # Check incoming parameters
    if lookback_unit not in ["s", "m", "h"]:
        return "ERROR: lookback_unit is not: s|m|h"

    if epoch_unit not in ["ms", "s"]:
        return "ERROR: lookback_unit is not: ms|s"

    if "$lookback" not in feed_url:
        return "ERROR: url must contain the variable: '$lookback'"

    if "$base_url" not in feed_url:
        return "ERROR: feed_url must contain the variable: '$base_url'"

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
    url = feed_url.\
        replace("$base_url", base_url).\
        replace('$lookback', epoch)

    return url


def get_feed_data(feed_response):
    # Return the appropriate location of the list of problems/alerts
    # ['json'] is the json.loads of all returned HTTP content
    # OpsGenie places all of its returned alerts in ['data']
    return feed_response['json']['data']


def get_problem_id(problem):
    # Return the location of the unique_id which identifies each problem/alert
    # OpsGenie uses 'tinyId' as the unique_id for each alert
    return problem['tinyId']


def build_individual_url(base_url, individual_url, uniqueid):
    """
    Takes a url with "$uniqueid" as a variable placeholder
    Returns url with the specified $uniqueid

    Attributes:
        url (str): a url string with '$uniqueid" within that string
        id (str): id of event
    """

    if "$base_url" not in individual_url:
        return "ERROR: individual_url must contain the variable: '$base_url'"

    # String replacement for variable
    url = individual_url.\
        replace("$base_url", base_url).\
        replace('$uniqueid', uniqueid)

    return url


def poll_individual_url(problem_id, f_url, f_headers):
    # OpsGenie requires polling the individual_url

    # ATTEMPT TO POLL INDIVIDUAL ITEM
    item = {}
    item_response = False
    item_response = \
        try_request(f_url=f_url,
                    f_headers=f_headers,
                    log_category='Poll',
                    error_msg='GetFailure '
                              'Unable to get individual_url',
                    log_key='problem_id',
                    log_value=problem_id,
                    f_dict=item)

    # declare how to locate the the main data block
    if item_response == True:
        item['data'] = item['json']['data']

        # Final data to POST
        post_item = item['data']

        return post_item


#   -----------------------------------   #
#            CLASSIFIER FUNCTIONS
#   -----------------------------------   #

def try_obtain_problem_tags(problem):
    # OpsGenie puts the tags inside a 'tags' key in list syntax
    # and then inside a list of tags with a CONTEXT and key
    # We only need to perform a basic check for the tags, then return them

    # text = "{'seen': True, 'id': '34385618-7701-43af-b6d5-cbdb16ec8684-1521127493827', 'tinyId': '4082', 'alias': '34385618-7701-43af-b6d5-cbdb16ec8684-1521127493827', 'message': '[TEST] [Dynatrace]: test', 'status': 'open', 'acknowledged': False, 'isSeen': True, 'tags': ['syn.nine', 'syn.other', 'syn.test'], 'snoozed': False, 'count': 1, 'lastOccurredAt': '2018-03-15T15:24:53.827Z', 'createdAt': '2018-03-15T15:24:53.827Z', 'updatedAt': '2018-03-15T15:27:34.381Z', 'source': 'aaron.timko@dynatrace.com', 'owner': '', 'priority': 'P3', 'teams': [{'id': '7d69e284-d2b6-4dd4-b2de-f1b4801a3be9'}], 'responders': [{'type': 'team', 'id': '7d69e284-d2b6-4dd4-b2de-f1b4801a3be9'}], 'integration': {'id': '7d0a77d6-2a12-4d03-bd2e-8af15f6f3058', 'name': 'test_fireinthehole_aaron', 'type': 'API'}, 'actions': [], 'entity': '', 'description': '', 'details': {'dynatrace_tenant': 'fireinthehole', 'host_regex': ''}, 'alexis': {'feed_type': 'opsgenie', 'feed_name': 'Test_OpsGenie_AllOpenAlerts_DaySprint', 'unique_key': 'problem_id', 'unique_value': '4082'}}"
    # text = text.replace("False","'False'").replace("True","'True'")
    # text = text.replace("'",'"')
    # problem = json.loads(text)

    tag_list = []

    if 'tags' in problem:
        if len(problem['tags']) > 0:
            tag_list = problem['tags']

    return tag_list


def try_submit_comment(thread_name, base_url, problem_id,
                       comment_syntax, comment_replacestr, comment_reason,
                       f_headers):

    # OpsGenie has a concept of teams which was the original
    # methodology.  We are going to do a small hack
    # so that we can continue using teams instead of comments

    if comment_reason == 'PushProblemToActionHandler':
        team = app_conf['default_remediation_queue']

    if comment_reason == 'FlagProblemForInvestigation':
        team = app_conf['default_investigation_queue']


    opsgenie_add_team(thread_name,
                      tinyId=problem_id,
                      team=team,
                      f_headers=f_headers)



#   -----------------------------------   #
#        OPSGENIE SPECIFIC FUNCTIONS
#   -----------------------------------   #


def opsgenie_add_team(thread_name,tinyId,team,f_headers,source="",
                      user="Alexis Automation",note=""):
    """
    Adds a team to an existing tinyId

    :param tinyId: target tinyId
    :param team: team to add to target tinyId
    :param user: (optional) override if needed
    :param source: defaults to the running app name
    :param note: defaults to standard message
    :param f_headers: supply your OpsGenie Authorization header
    :return:
    """

    problem_id = tinyId

    # Override default options
    if source == "":
        source = alexis.common.app_name
    if note == "":
        note = "Team:"+team+" was added by Alexis"

    # Build strings
    url = "https://api.opsgenie.com/v2/alerts/" + str(tinyId) \
          + "/teams?identifierType=tiny"
    data = '{"team": {"name": "'+team+'" },"user":"'+user+'","source":"'\
           +source+'","note":"Autoremediation has started"}'

    # Build header
    json_header = {'Content-type': 'application/json'}
    new_headers = append_json_dict(f_headers, "", json_header, "")

    # Attempt POST
    try:
        post = requests.post(url, headers=new_headers, data=data)
    except requests.exceptions.RequestException as e:
        log_to_disk('Poll', lvl='ERROR',
                    msg='PostError ('+thread_name+')',
                    kv=kvalue(problem_id=problem_id, exception=e))
        log_to_disk('Poll', lvl="ERROR",
                    msg='PostError Unable to post ('+thread_name+')',
                    kv=kvalue(url=url, problem_id=problem_id))

        # TODO: this was added after 1.010.01
        post = None
        # TODO: this was added after 1.010.01

    if post is not None:
        # Output result
        log_to_disk('Alert', msg='AddTeamToAlert ('+thread_name+')',
                    kv=kvalue(problem_id=problem_id,
                              team=team,
                              post_results=post))
        # Return result
        return post
