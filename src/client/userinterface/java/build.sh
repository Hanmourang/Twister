#!/bin/bash
JARSIGNER=/opt/java1.7/bin/jarsigner
JAVAC=/opt/java1.7/bin/javac
JAR=/opt/java1.7/bin/jar
EXTLIBS=extlibs/jsch-0.1.44.jar:\
extlibs/ws-commons-util-1.0.2.jar:\
extlibs/commons-vfs-1.0.jar:\
extlibs/VFSJFileChooser-0.0.3.jar:\
extlibs/jcommon-1.0.16.jar:\
extlibs/jxl.jar:\
extlibs/ws-commons-util-1.0.2.jar:\
extlibs/xmlrpc-client-3.1.3.jar:\
extlibs/xmlrpc-common-3.1.3.jar\ 

$JAVAC -version
$JAVAC -d classes -source 1.6 -target 1.6 -cp $EXTLIBS src/*.java;
cd classes;
$JAR cf ../target/test.jar  Icons  *.class 
$JARSIGNER ../target/test.jar Twister -storepass password