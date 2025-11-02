# Deploy Pexip Policy Router to Azure

### Azure Services Diagram
![Azure Services](docs/screenshots/python-postgresql-app-architecture-240px.png)

## Azure Services List

- **Web App**    Provides serverless  web services for UI & Policy requests for the Django framework
- **Azure Database for PostgreSQL flexible server**     Provides serverless persistent SQL server used by Django framework
- **App Service Plan**     Provides underlying enviroment (Linux), compute & pricing plan to support the web app

## Deployment

Azure portal can be used for ease of use to create the above resources.

### Reference

https://learn.microsoft.com/en-us/azure/app-service/configure-language-python

https://learn.microsoft.com/en-us/azure/app-service/tutorial-python-postgresql-app-django?tabs=copilot&pivots=azure-portal

### Configure Azure resources

Once the Azure Web App has been deployed enviroment variables are used by the Django app settings:

- **DB_NAME** "postgres" to use default db or as configured in Azure PostgreSQL service
- **DB_USER** SQL amin username configured when creating Azure PostgreSQL service
- **DB_PW** SQL admin password configured when creating Azure PostgreSQL service
- **DB_HOST** SQL endpoint/hostname configured when creating Azure PostgreSQL service e.g. dbname.postgres.database.azure.com
- **DJANGO_SECRET_KEY** Secret key used by Django for encryption and token management
- **POST_BUILD_COMMAND** "python manage.py migrate --settings pexip_policy_router.settings_AzureWebApp"

These enviroment variables can be configured directly in Azure Portal or using VSCode with Azure Extensions

### Deploy app

Use VSCode or GitHub source to deploy the repo to Web App

### Post 1st Deploy

Once app is deployed the database needs to be managed to create the WebUI user

- SSH onto app via Azure Portal

Run database migration & super user commands:

- `python manage.py makemigrations policy_router`
- `python manage.py migrate --settings pexip_policy_router.settings_AzureWebApp`
- `python manage.py createsuperuser --settings pexip_policy_router.settings_AzureWebApp`

N.B. the `manage.py migrate` command will be run automatcilly on deployment via the **POST_BUILD_COMMAND** env variable