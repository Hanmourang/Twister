#!/usr/bin/perl

#
# version: 3.001
# <title>init file</title>
# <description>Test status</description>
#

use warnings;


sub test001 {
	# Must return one of the statuses:
	# $STATUS_PASS, $STATUS_FAIL, $STATUS_SKIPPED, $STATUS_ABORTED,
	# $STATUS_NOT_EXEC, $STATUS_TIMEOUT, or $STATUS_INVALID
	$error_code = $STATUS_PASS;

	logMsg("logTest", "\nTestCase: $SUITE_NAME::$FILE_NAME starting\n");
	print "Starting test $FILE_NAME ...\n\n";

	$g1 = getGlobal("/Level_A/global1");
	print "Query Globals Level A/ global1  =  $g1 ...\n";

	$g2 = getGlobal("/Level_A/global2");
	print "Query Globals Level A/ global2  =  $g2 ...\n";

	$g3 = getGlobal("/Level_A/global3");
	print "Query Globals Level A/ global3  =  $g3 ...\n";

	print "\nSetting some globals...\n";
	setGlobal("/some_global1", "some string");
	setGlobal("/some_global2",  9999);

	$g0 = getGlobal("/some_global1");
	print "Getting some global 1  =  $g0 ...\n";

	$g0 = getGlobal("/some_global2");
	print "Getting some global 2  =  $g0 ...\n";

	logMsg("logTest", "TestCase: $SUITE_NAME::$FILE_NAME returned $error_code\n");
	return $error_code
}

exit( test001() );
