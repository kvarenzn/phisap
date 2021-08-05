build:
	@./gradlew -p . assembleRelease

install:
	@cp ./build/outputs/apk/release/server-release-unsigned.apk phisap-server

install-remote:
	@adb push phisap-server /data/local/tmp/phisap-server.jar

test: install-remote
	@adb shell CLASSPATH=/data/local/tmp/phisap-server.jar app_process / com.rabbithouse.svr.Server

all: build install test

.PHONY: build install install-remote test all
