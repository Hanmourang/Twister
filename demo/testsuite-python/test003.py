
import time
import telnetlib

#
# <title>test 003</title>
# <description>This test is connecting to a TELNET host.</description>
#

def test003():
	'''
	Testing Python Telnet library.
	'''

	testName = 'test003.py'
	logMsg('logTest', "\nTestCase:%s starting\n" % testName)
	error_code = "PASS"

	tn = telnetlib.Telnet('134.117.136.48', 23, 60)
	print 'Connected:', tn
	time.sleep(1)

	print tn.read_until('login:', 30)
	tn.write('guest\n')
	time.sleep(1)

	print tn.read_until('any key to continue...', 10)
	tn.write('\n\n')
	time.sleep(1)

	print tn.read_until("'q' to quit", 10)
	tn.write('q\n')
	time.sleep(1)

	print tn.read_until('About the National Capital FreeNet', 10)
	tn.write('1\n')
	time.sleep(1)

	print tn.read_until('Your Choice ==>', 10)
	tn.write('x\n')
	tn.write('y\n')
	time.sleep(1)

	print tn.read_very_eager()

	logMsg('logTest', "TestCase:%s %s\n" % (testName, error_code))
	return error_code

#

_RESULT = test003()
