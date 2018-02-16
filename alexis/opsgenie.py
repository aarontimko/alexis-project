import requests
import alexis.common
from alexis.common import *


def opsgenie_add_team(thread_name,tinyId,team,headers,source="",
                      user="Alexis Automation",note=""):
    """
    Adds a team to an existing tinyId

    :param tinyId: target tinyId
    :param team: team to add to target tinyId
    :param user: (optional) override if needed
    :param source: defaults to the running app name
    :param note: defaults to standard message
    :param headers: supply your OpsGenie Authorization header
    :return:
    """

    # Override default options
    if source == "":
        source = alexis.common.app_name
    if note == "":
        note = "Team:"+team+" was added by Alexis"

    # Build strings
    url = "https://api.opsgenie.com/v2/alerts/" + str(tinyId) \
          + "/teams?identifierType=tiny"
    data = '{"team": {"name": "'+team+'" },"user":"'+user+'","source":"'\
           +source+'","note":"Team:'+team+' was added to Alert"}'

    # Build header
    json_header = {'Content-type': 'application/json'}
    headers = append_json_dict(headers, "", json_header, "")

    # Attempt POST
    try:
        post = requests.post(url, headers=headers, data=data)
    except requests.exceptions.RequestException as e:
        log_to_disk('Poll', lvl='ERROR',
                    msg='PostError ('+thread_name+')',
                    kv=kvalue(tinyId=tinyId, exception=e))
        log_to_disk('Poll', lvl="ERROR",
                    msg='PostError Unable to post ('+thread_name+')',
                    kv=kvalue(url=url, tinyId=tinyId))

        # TODO: this was added after 1.010.01
        post = None
        # TODO: this was added after 1.010.01

    if post is not None:
        # Output result
        log_to_disk('Alert', msg='AddTeamToAlert ('+thread_name+')',
                    kv=kvalue(tinyId=tinyId,
                              team=team,
                              post_results=post))
        # Return result
        return post
