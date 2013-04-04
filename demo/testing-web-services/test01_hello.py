
# <title> Test 01 - hello </title>

# version: 2.001
# <description> Testing the SOAP server: running Echo function 3 times, the last time with wrong parameters </description>

import time
from suds.client import Client

c = Client('http://localhost:55000/?wsdl')

print '\nConnected to SOAP Server:'
print str(c)[80:-1]

#

print 'Calling HELLO with int:', c.service.say_hello('Echo', 3)
print 'Calling HELLO with str:', c.service.say_hello('Echo', '3')
try:
	print 'Calling HELLO with err: ', c.service.say_hello(1)
except Exception, e:
	print 'Caught error:', e

print time.sleep(1)
print '\nHello function OK!'

_RESULT = 'PASS'

#
