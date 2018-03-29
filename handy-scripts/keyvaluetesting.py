import json

text = "{'seen': False, 'id': '697cdc72-2d8d-4af8-9c51-f4496f025199-1515783801378', 'tinyId': '2187', 'alias': '697cdc72-2d8d-4af8-9c51-f4496f025199-1515783801378', 'message': '[DAY] [Dynatrace]: Test Automation: Catfile', 'status': 'open', 'acknowledged': False, 'isSeen': False, 'tags': ['syn.automation', 'syn.day'], 'snoozed': False, 'count': 1, 'lastOccurredAt': '2018-01-12T19:03:21.378Z', 'createdAt': '2018-01-12T19:03:21.378Z', 'updatedAt': '2018-01-12T19:03:21.52Z', 'source': '69.84.208.222', 'owner': '', 'priority': 'P3', 'teams': [{'id': 'abf1e895-2db2-4da6-a810-bab020076336'}], 'integration': {'id': '2178cef3-63e3-4a80-b6e7-0b3b804319b9', 'name': 'Dynatrace_Day', 'type': 'Ruxit'}, 'actions': [], 'entity': 'Catfile on remote host', 'description': 'Hey there,<br> I Gotta do some catting around here<br>Thanks!', 'details': {'dynatrace_tenant': 'day', 'host_regex': 'wadventspkhf01.regex.com'}, 'rule': {'enabled': 'true', 'os_type': 'linux', 'rule_name': 'day_wadventspkhf01_catfile', 'rule_description': 'Cats a file on a remote system', 'rule_version': '1.01', 'alert_feed': 'OpsGenie', 'evaluation_list': [{'evaluation': {'tags': ['syn.day'], 'search_key': 'description', 'search_text': 'Gotta do some catting', 'duration': '0m', 'task_type': 'run_command'}}], 'task_list': [{'task': {'task_type': 'remote_ssh', 'run_command': 'cat /home/autoremediation/testautomation/day_catfile.txt', 'delay_after': '30s', 'action': 'catfile', 'action_reason': 'testautomation'}}], 'entities': 'wadventspkhf01.dev.saasapm.com', 'route_to_team': 'test_email_aaron', 'delay_escalation': '20m'}}"
text2 = text.replace("'",'"').replace("False",'"False"')

print(text2)

incoming_data = json.loads(text2)

rule = incoming_data['rule']

print(rule)

myrule = ["details","host_regex"]
print(myrule[0])

myrule = ["details"]
print(myrule[0])

if len(myrule) == 2:
    host_regex = incoming_data[myrule[0]][myrule[1]]
    print(host_regex)

if len(myrule) == 1:
    host_regex = incoming_data[myrule[0]]
    print(host_regex)

if isinstance(host_regex, str):
    print("host_regex IS A STRING")
    list_host_regex = [host_regex]
    if isinstance(list_host_regex, list):
        print("list_host_regex IS A LIST")
        for entity in list_host_regex:
            print(entity)


if 'entities' in rule:
    print("YES - THERE ARE ENTITIES IN THE RULE")
    print(rule['entities'])
    print(len(rule['entities']))
    if isinstance(rule['entities'], list):
        print("IT IS A LIST")