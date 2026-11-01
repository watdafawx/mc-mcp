@echo off
REM Builds with a portable JDK 21: toolchain\ here, else the one in ..\foxs-tweaks\toolchain.
setlocal
for /d %%D in ("%~dp0toolchain\jdk-*") do set "JAVA_HOME=%%D"
if not defined JAVA_HOME for /d %%D in ("%~dp0..\foxs-tweaks\toolchain\jdk-*") do set "JAVA_HOME=%%D"
if not defined JAVA_HOME (
    echo No JDK found. Set JAVA_HOME to a JDK 21 and run gradlew build.
    exit /b 1
)
echo Using JDK: %JAVA_HOME%
call "%~dp0gradlew.bat" %*
