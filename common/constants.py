
STATUS_STOP    = 0 # Suicide; the test suite is immediately killed
STATUS_PAUSED  = 1 # After the current test is finished, the suite is frozen
STATUS_RUNNING = 2 # The suite is running
STATUS_RESUME  = 3 # Continue the paused tests
STATUS_INVALID = 8 # Invalid status

STATUS_PENDING  = 10 # Not yet run, waiting to start
STATUS_WORKING  = 1  # Is running now
STATUS_PASS     = 2  # Test is finished successful
STATUS_FAIL     = 3  # Test failed
STATUS_SKIPPED  = 4  # When file doesn't exist, or test has flag `runnable = False`
STATUS_ABORTED  = 5  # When test is stopped while running
STATUS_NOT_EXEC = 6  # Not executed, is sent from TC when tests are paused, and then stopped instead of being resumed
STATUS_TIMEOUT  = 7  # When timer expired
STATUS_INVALID  = 8  # When timer expired, the next run
STATUS_WAITING  = 9  # Is waiting for another test

execStatus = {'stopped':STATUS_STOP, 'paused':STATUS_PAUSED, 'running':STATUS_RUNNING, 'resume':STATUS_RESUME,
    'invalid':STATUS_INVALID}

testStatus = {'pending':STATUS_PENDING, 'working':STATUS_WORKING, 'pass':STATUS_PASS, 'fail':STATUS_FAIL,
    'skipped':STATUS_SKIPPED, 'aborted':STATUS_ABORTED, 'not executed':STATUS_NOT_EXEC, 'timeout':STATUS_TIMEOUT,
    'invalid':STATUS_INVALID, 'waiting':STATUS_WAITING}
