@echo off
setlocal enabledelayedexpansion

echo =========================================
echo Cerebrus AWS Secrets Configurator
echo =========================================

:: Path to the Cerebrus AppData directory
set "APP_DATA_DIR=%USERPROFILE%\.gemini\antigravity"
set "SECRETS_FILE=%APP_DATA_DIR%\aws_secrets.json"

:: Check if directory exists, if not create it
if not exist "%APP_DATA_DIR%" (
    mkdir "%APP_DATA_DIR%"
)

:: Define the JSON content to be injected
:: REPLACE THE VALUES BELOW WITH YOUR TEAM'S ACTUAL AWS CREDENTIALS
set "TEAM_KEY_ALIAS=TeamUploadKey"
set "TEAM_ACCESS_KEY=AKIA_REPLACE_ME"
set "TEAM_SECRET_KEY=SECRET_REPLACE_ME"
set "TARGET_BUCKET=cerebrus-assets-bucket"
set "TARGET_REGION=us-east-1"

echo Writing credentials to %SECRETS_FILE%...

(
echo {
echo     "keys": {
echo         "%TEAM_KEY_ALIAS%": {
echo             "alias": "%TEAM_KEY_ALIAS%",
echo             "access_key": "%TEAM_ACCESS_KEY%",
echo             "secret_key": "%TEAM_SECRET_KEY%"
echo         }
echo     },
echo     "buckets": {
echo         "%TARGET_BUCKET%": {
echo             "name": "%TARGET_BUCKET%",
echo             "region": "%TARGET_REGION%",
echo             "key_alias": "%TEAM_KEY_ALIAS%"
echo         }
echo     }
echo }
) > "%SECRETS_FILE%"

echo Configuration complete. You can now launch Cerebrus and use the S3 Uploader plugin.
pause
