import requests
import urllib.parse

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


def build_feed_lookback_url(base_url, feed_url):
    '''
    As of March 2018, the Dynatrace API doesn't have a concept
    of a relative time which is calculated (e.g. with epochms)
    So, this is a dummy function which just returns back the url
    (which of course, could have "relativeTime=2hours" if you wanted...)

    Attributes:
        base_url (str): a url string (https://www.domain.com)
        feed_url (str): a url string with '$base_url'
    '''

    if "$base_url" not in feed_url:
        return "ERROR: feed_url must contain the variable: '$base_url'"

    url = feed_url.replace("$base_url", base_url)

    return url


def get_feed_data(feed_response):
    # Return the appropriate location of the list of problems/alerts
    # ['json'] is the json.loads of all returned HTTP content
    # Dynatrace places all of its returned problems in ['result']['problems']
    return feed_response['json']['result']['problems']


def get_problem_id(problem):
    # Return the location of the unique_id which identifies each problem/alert
    return problem['id']


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

    if "$uniqueid" not in individual_url:
        return "ERROR: individual_url must contain the variable: '$uniqueid'"

    # String replacement for variable
    url = individual_url. \
        replace("$base_url", base_url). \
        replace('$uniqueid', uniqueid)

    return url


def poll_individual_url(problem_id, f_url, f_headers):
    # Dynatrace requires polling the individual_url
    # And also the comments API

    # ATTEMPT TO POLL INDIVIDUAL ITEM
    item = {}
    item_response = False
    item_response = \
        try_request(f_url=f_url,
                    f_headers=f_headers,
                    log_category='PollProblem',
                    error_msg='GetFailure '
                              'Unable to get individual_url',
                    log_key='problem_id',
                    log_value=problem_id,
                    f_dict=item)

    # If we have received data from the Problem, continue
    if item_response == True:

        # declare how to locate the the main data block
        item['data'] = item['json']['result']

        # For Dynatrace, go get Comments as well
        # url_comments = f_url + '/comments'
        # comments = {}
        # comments_response = False
        # comments_response = \
        #     try_request(f_url=url_comments,
        #                 f_headers=f_headers,
        #                 log_category='PollProblem',
        #                 error_msg='GetFailure '
        #                           'Unable to get url_comments',
        #                 log_key='problem_id',
        #                 log_value=problem_id,
        #                 f_dict=comments)
        #
        # comment_list = comments['json']['comments']

        # Check if the Alexis user has already commented on Problem
        comment_list = get_problem_comments_with_filter(
            base_url=f_url,
            problem_id=problem_id,
            f_headers=f_headers,
            context='Alexis')

        # If there are no Alexis comments, forward to Classifier
        # TODO: Move this logic to Classifier and use {"Autoremedation Attempt": 1}
        if comment_list == []:

            # Merge the Problem JSON and the comment_list JSON
            merged_problem_and_comments = \
                append_json_dict(item['data'],
                                 "{'comments':",
                                 comment_list,
                                 "}")

            # Final data to POST
            post_item = merged_problem_and_comments

            return post_item


#   -----------------------------------   #
#            CLASSIFIER FUNCTIONS
#   -----------------------------------   #

def try_obtain_problem_tags(problem):
    # Dynatrace puts the tags into 'tagsOfAffectedEntities'
    # and then inside a list of tags with a CONTEXT and key

    # text = "{'id': '240240549795129062', 'startTime': 1521050160000, 'endTime': -1, 'displayName': '62', 'impactLevel': 'INFRASTRUCTURE', 'status': 'OPEN', 'severityLevel': 'RESOURCE_CONTENTION', 'commentCount': 0, 'tagsOfAffectedEntities': [{'context': 'CONTEXTLESS', 'key': 'syn.ca'}, {'context': 'CONTEXTLESS', 'key': 'syn.day'}], 'rankedEvents': [{'startTime': 1521050160000, 'endTime': -1, 'entityId': 'HOST-EFF972585836497E', 'entityName': 'TS1209CA93370.dev.saasapm.com', 'severityLevel': 'RESOURCE_CONTENTION', 'impactLevel': 'INFRASTRUCTURE', 'eventType': 'MEMORY_SATURATED', 'status': 'OPEN', 'severities': [{'context': 'MEMORY_USAGE', 'value': 0.34980297088623047, 'unit': 'Percent (%)'}, {'context': 'PAGE_FAULTS', 'value': 3567.540771484375, 'unit': 'PerSecond (count/s)'}], 'isRootCause': 'False'}], 'comments': [], 'alexis': {'feed_type': 'dynatrace', 'feed_name': 'Test_AllOpenProblems_Syn.Day', 'unique_key': 'feed_id', 'unique_value': '240240549795129062'}}"
    # text = text.replace("'",'"')
    # problem = json.loads(text)

    tag_list = []

    if 'tags' in problem:
        if len(problem['tags']) > 0:
            for tag_data in problem['tagsOfAffectedEntities']:
                tag_list.append(tag_data['key'])

    return tag_list


def build_comment(comment_syntax, comment_replacestr,
                  user_type, context_type, increment=False):
    '''

    :param comment_syntax: Primary comment with $comment_replacestr variable
    :param comment_replacestr: Replace string inside comment_syntax
    :param user_type: Dynatrace Comment User
    :param context_type: Dynatrace Comment Context
    :param increment: increment with number of times autoremediated

    :return: comment_json (dict): ready for Dynatrace comment
    '''


    # Test for incrementing Autoremediation
    get_last_autoremediation_attempt = "01"
    last_autoremediation_attempt = get_last_autoremediation_attempt

    if increment == True:
        current_autoremediation_attempt = int(last_autoremediation_attempt) + 1
    else:
        current_autoremediation_attempt = 1

    comment_replacestr = '"' + str(comment_replacestr) + '"'

    comment_json = {}
    comment_json['comment'] = comment_syntax.replace('$comment_replacestr',
                                                     comment_replacestr)
    user = {user_type: current_autoremediation_attempt}
    comment_json['user'] = str(user).replace("'",'"')
    comment_json['context'] = context_type

    return comment_json


def try_submit_comment(thread_name, base_url, problem_id,
                       comment_syntax, comment_replacestr,
                       f_headers):


    # thread_name = 'Thread-1'
    # base_url = 'https://zzz00000.live.dynatrace.com'
    # problem_id = '-6387835752591839623'
    # rule_name = 'test_diskspace_commonagent'
    # f_headers = '{"Authorization":"Api-Token sdfj3kvkdrj34kjdfkw35"}'
    # f_headers = json.loads(f_headers)

    # Add Content-type to f_headers
    f_headers['Content-type'] = 'application/json'

    # Optional development logging: output raw f_dict['json']
    if app_conf['debug'] is True:
        print(f_headers)

    # Notification URL
    uri = '/api/v1/problem/details/$pid/comments'.replace('$pid', problem_id)
    comments_url = urllib.parse.urljoin(base_url, uri)

    # Comment Details
    comment_json = build_comment(comment_syntax=comment_syntax,
                  comment_replacestr=comment_replacestr,
                  user_type='Autoremediation Attempt',
                  # context_type = 'Alexis:' + alexis.common.app_name
                  # TODO: Add Component to comment context
                  context_type='Alexis'
                  )

    # Submit Comment
    comments_response = {}
    requests_response = False
    requests_response = try_request(
        f_url=comments_url,
        f_headers=f_headers,
        log_category='SubmitComment ('+thread_name+')',
        error_msg='SubmitComment - Unable to comment ('+thread_name+')',
        log_key='problem_id',
        log_value=problem_id,
        f_dict=comments_response,
        json_data=comment_json,
        m="post")

    # CHECK FOR VALID HTTP RESPONSE
    if requests_response == False:
        # Feed did not have valid HTTP response, we cannot continue
        return False
    else:
        return True


def try_get_comment_list(base_url, problem_id, f_headers):
    '''
    Dynatrace function for retrieving a Problem's comments

    :param base_url: URL of Tenant
    :param problem_id: unique ID of Problem (pid)
    :param f_headers: headers for authentication
    :param f_dict: return dictionary (must be declared before function call)
    :return:
    '''

    # f_headers = '{"Authorization":"Api-Token sdfj3kvkdrj34kjdfkw35"}'
    # f_headers = json.loads(f_headers)
    #
    # base_url = 'https://zzz00000.live.dynatrace.com'
    # problem_id = '-6387835752591839623'

    # Notification URL
    uri = '/api/v1/problem/details/$pid/comments'.replace('$pid', problem_id)
    comments_url = urllib.parse.urljoin(base_url, uri)


    # Submit Comment
    comments_response = {}
    requests_response = False
    requests_response = try_request(
        f_url=comments_url,
        f_headers=f_headers,
        log_category='GetComments',
        error_msg='GetComments - Unable to retrieve comments',
        log_key='problem_id',
        log_value=problem_id,
        f_dict=comments_response)

    # CHECK FOR VALID HTTP RESPONSE
    if requests_response == False:
        # Feed did not have valid HTTP response, we cannot continue
        return False
    else:
        # Store results in f_dict and return True
        comment_list = comments_response['json']['comments']
        return comment_list


def try_delete_comment(base_url, problem_id, comment_id, f_headers):
    '''
    Dynatrace function for Deleting a single comment

    :param base_url:
    :param problem_id:
    :param f_headers:
    :return:
    '''

    uri = '/api/v1/problem/details/'+problem_id+'/comments/'+comment_id
    delete_url = urllib.parse.urljoin(base_url, uri)

    # Optional development logging: output raw f_dict['json']
    if app_conf['debug'] is True:
        print(delete_url)

    # Delete Comment
    comments_response = {}
    requests_response = False
    requests_response = try_request(
        f_url=delete_url,
        f_headers=f_headers,
        log_category='DeleteComments',
        error_msg='DeleteComments - '
                  'Unable to delete comments',
        log_key='problem_id',
        log_value=problem_id,
        f_dict=comments_response,
        m="delete")

    # CHECK FOR VALID HTTP RESPONSE
    if requests_response == False:
        # Feed did not have valid HTTP response, we cannot continue
        return False
    else:
        if 200 <= comments_response['statusCode'] <= 299:
            log_to_disk("CommentDeletion",
                        msg="Successfully deleted: ",
                        kv=kvalue(problem_id=problem_id,
                                  comment_id=comment_id))
            # return True
            return True


def get_problem_comments_with_filter(base_url, problem_id, f_headers,
                                     user="*", context="*"):
    '''

    :param base_url:
    :param problem_id:
    :param f_headers:
    :param user:
    :param context:
    :return:
    '''

    # Attempt to retrieve comments
    comment_list = try_get_comment_list(base_url=base_url,
                         problem_id=problem_id,
                         f_headers=f_headers)

    # If comment_list is returned, continue
    if comment_list != False:

        # Full list of comments
        if user == "*" and context == "*":
            return comment_list

        # Only user has been specified
        if user != "*" and context == "*":
            filtered_comment_list = []
            for comment in comment_list:
                message1 = user
                message2 = comment['userName']
                if re.search(message1, message2) is not None:
                    filtered_comment_list.append(comment)
            return filtered_comment_list

        # Only comment has been specified
        if user == "*" and context != "*":
            filtered_comment_list = []
            for comment in comment_list:
                message1 = context
                message2 = comment['context']
                if re.search(message1, message2) is not None:
                    filtered_comment_list.append(comment)
            return filtered_comment_list

        # Both user and comment are specified
        if user != "*" and context != "*":
            filtered_comment_list = []
            for comment in comment_list:
                # Check for user match first
                message1 = user
                message2 = comment['userName']
                if re.search(message1, message2) is not None:
                    # Now check for context match
                    message3 = context
                    message4 = comment['context']
                    if re.search(message3, message4) is not None:
                        filtered_comment_list.append(comment)
            return filtered_comment_list






# GENERAL VARIABLES
alexis.common.app_name = "Poller"
alexis.common.app_logdir = "log"

# app_name_2017-11-06.log
app_logfile_string = alexis.common.app_name.lower() + \
                 "_" + str(get_date()) + ".log"

alexis.common.app_logfile = os.path.join(alexis.common.app_logdir,
                                         app_logfile_string)

# RUNTIME VARIABLES
conf_dir = './conf'
conf_file = 'alexis.conf.yaml'
alexis_conf = grab_yaml_from_disk(os.path.join(conf_dir,conf_file))
app_conf = alexis_conf[alexis.common.app_name.lower()]
token_conf = app_conf['tokens']
token_runtime_file = os.path.join(conf_dir, str(token_conf['directory']), str(token_conf['runtime']))
authentication_list = alexis_conf['authentication_list']
feed_list = app_conf['feed_list']

#################################################################



f_headers = '{"Authorization":"Api-Token sdfj3kvkdrj34kjdfkw35"}'
f_headers = json.loads(f_headers)

base_url = 'https://zzz00000.live.dynatrace.com'
problem_id = '-6387835752591839623'


comment_list = get_problem_comments_with_filter(
    base_url=base_url,
    problem_id=problem_id,
    f_headers=f_headers,
    context='Alexis')

import pprint
pp = pprint.PrettyPrinter(indent=4)
pp.pprint(comment_list)


for item in comment_list:

    try_delete_comment(base_url=base_url,
                     problem_id=problem_id,
                     comment_id=item['id'],
                     f_headers=f_headers)

