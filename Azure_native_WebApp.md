# Code changes for deploy to native Azure Linux WebApp

REF: https://learn.microsoft.com/en-us/azure/app-service/configure-language-python

## Key concepts
Azure WebApp will make use of "app settings" on build, effectively ENV variables

SCM_DO_BUILD_DURING_DEPLOYMENT

Set to 1 or True will then do the following:

Run pip install -r requirements.txt. The requirements.txt file must be in the project's root folder.

If manage.py is found in the root of the repository (which indicates a Django app), run manage.py collectstatic. However, if the DISABLE_COLLECTSTATIC setting is true, this step is skipped.

PRE_BUILD_COMMAND

Runs commands before build

POST_BUILD_COMMAND

Runs commands after build

## Example App Settings for pexip_policy_router

SCM_DO_BUILD_DURING_DEPLOYMENT : True

POST_BUILD_COMMAND : scripts/postbuild.sh

## Django specic App Settings - access via os.environ['VARNAME']

SECRET_KEY - Can be used as Django Secret key

DEBUG - set to false in production

ALLOWED_HOSTS - Can use [os.environ['WEBSITE_HOSTNAME']] in settings.py to use Azure WebApp hostname

DATABASES - can be used for database connection in a production enviroment

N.B. Django files such as settings.py should be configured to access these via access via "os.environ['VARNAME']"