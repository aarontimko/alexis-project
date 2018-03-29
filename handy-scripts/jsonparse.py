from bottle import run, request, route, post, get, abort, default_app, HTTPResponse
import re
import requests
import alexis.common
from alexis.common import *
from alexis.opsgenie import *
import threading
import urllib3

# GENERAL VARIABLES
alexis.common.app_name = "JsonParser"
alexis.common.app_logdir = "log"

# app_name_2017-11-06.log
app_logfile_string = alexis.common.app_name.lower() + \
                 "_" + str(get_date()) + ".log"

alexis.common.app_logfile = os.path.join(alexis.common.app_logdir,
                                         app_logfile_string)

json_file = "C:\\Users\\aaron.timko\\Downloads\\usersession_newformat.json"
json_file = "C:\\Users\\aaron.timko\\Downloads\\usersession_singlevisit_multiuseraction.json"
json_file = "C:\\Users\\aaron.timko\\Downloads\\usersession_02.json"



session_export = grab_json_from_disk(json_file)

print("Top-level JSON items: "+str(len(session_export))+
      "     userAction JSON items: "+str(len(session_export['userActions'])))

print(session_export)

visit_header = {}
log_each_record = {}
for k,v in session_export.items():
    if k != 'userActions':
        if k == 'startTime':
            visit_header['visitstartTime'] = v
        elif k == 'endTime':
            visit_header['visitendTime'] = v
        else:
            visit_header[k] = v
    if re.search("userSessionId|startTime|endTime|userActionCount",k):
        log_each_record[k] = v

print(visit_header)
for kv in visit_header.items():
    print(kv)

from alexis.common import *

for split_user_action in session_export['userActions']:
    #print(split_user_action)
    #full_user_action = dict(visit_header, **split_user_action)
    full_user_action = append_json_dict(visit_header, "{'userAction':", split_user_action, "}")
    #prepend_string = "{'userAction':"
    #append_string = "}"
    # dict2 = split_user_action
    # dict2_str = prepend_string + dict2.__str__() + append_string
    # p = re.compile(r"': (?P<unquoted>[A-Za-z]+)")
    # newtext = p.sub(r"': '\g<unquoted>'", dict2_str)
    # newtext = newtext.replace("'", '"')
    # print(newtext)
    # new_json = json.loads(newtext)
    # print(new_json)
    print(full_user_action)

# text = "Index': None, '"
# p = re.compile(r"': (?P<unquoted>[A-Za-z]+)")
# newtext = p.sub(r"': '\g<unquoted>'",text)
# print(newtext)


# REQUESTS

splunk_hec_url = 'https://http-inputs-dynatrace.splunkcloud.com/services/collector/event'
auth_header = {'Authorization': 'Splunk TOKEN'}
json_dict = {"host":"prod-saas.dynatrace-managed.com",
             "event": full_user_action,
             "source":"http-inputs-dynatrace.splunkcloud.com",
             "sourcetype":"dtsaas_usersessions",
             "index":"test_usersessions"}

#r = requests.post(splunk_hec_url, headers=auth_header, json=json_dict, verify=False)
#print(r.text)



# URLLIB3

import urllib3
from urllib.parse import urlencode

json_dict = {"host":"prod-saas.dynatrace-managed.com",
             "event":"hello world",
             "source":"http-inputs-dynatrace.splunkcloud.com",
             "sourcetype":"dtsaas_usersessions",
             "index":"test_usersessions"}


encoded_json_dict = json.dumps(json_dict).encode('utf-8')

http = urllib3.PoolManager()
r = http.request('POST', splunk_hec_url, headers=auth_header, body=encoded_json_dict)
print(json.loads(r.data.decode('utf-8')))


# URLLIB

import urllib.parse
import urllib.request

successful_post_count = 0

splunk_hec_url = 'https://http-inputs-dynatrace.splunkcloud.com/services/collector/event'
auth_header = {'Authorization': 'Splunk TOKEN'}
json_dict = {"host":"prod-saas.dynatrace-managed.com",
             "event": full_user_action,
             "source":"http-inputs-dynatrace.splunkcloud.com",
             "sourcetype":"dtsaas_usersessions",
             "index":"test_usersessions"}

# data = urllib.parse.urlencode(json_dict)
# data = data.encode('ascii')
params = json.dumps(json_dict).encode('utf8')
r = urllib.request.Request(splunk_hec_url, data=params, headers=auth_header)
with urllib.request.urlopen(r) as response:
   result = response.read()
   result_json = json.loads(result)
   if result_json['text'] == "Success":
       successful_post_count += 1

   print(result)

parsed_user_action_count = 8

return_text = '{"success":"True","details":"We processed and posted '+\
              str(parsed_user_action_count)+' userActions"}'
