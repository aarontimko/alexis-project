


incoming_data = "values"


# OPTION 1a: Poller class inside a module

import alexis.dynatrace as dynatrace

feed = {}
feed['type'] = 'dynatrace'

m = globals()[feed['type']].poller
m.process_data(m, )



# OPTION 1b: Function inside module

import alexis.dynatrace as dynatrace

feed = {}
feed['type'] = 'dynatrace'


m = globals()[feed['type']]
m.process_data()



# OPTION 2

def dynatrace_process_data():
    print("Dynatrace process_data with local function")

feed = {}
feed['type'] = 'dynatrace'

z = locals()[feed['type']+'_process_data']

z()


# OPTION 3?

func = getattr(m, 'process_data')()
func()









def run(type):
    print(type)
    def dynatrace():
        print("Dynatrace process_data")
    def opsgenie():
        print("OpsGenie process_data")


my_dynamic_function = {}
my_dynamic_function[feed['type']] = run(type=feed['type'])


my_dynamic_function[feed['type']]





class dynatrace(object):
    def process_data(self):
        print("Dynatrace process_data")

class opsgenie(object):
    def process_data(self):
        print("OpsGenie process_data")











