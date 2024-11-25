import pulumi
import pulumi_azure_native as azure_native
from pulumi_azure_native import insights, operationalinsights

config = pulumi.Config()
azure_native_location = config.get("azure-native:location")
storage_account_name = config.get("storageAccountName")
if storage_account_name is None:
    storage_account_name = "sacf7eb26h"

storage_location = config.get("storageLocation")
if storage_location is None:
    storage_location = "brazilsouth"

storage_sku = config.get("storageSku")
if storage_sku is None:
    storage_sku = "Standard_LRS"

blob_container_name = config.get("blobContainerName")
if blob_container_name is None:
    blob_container_name = "hello-world-container"

blob_name = config.get("blobName")
if blob_name is None:
    blob_name = "hello-world.zip"

resource_group = azure_native.resources.ResourceGroup(
    "resourceGroup",
    location=azure_native_location,
)

sa = azure_native.storage.StorageAccount(
    "sa",
    resource_group_name=resource_group.name,
    location=resource_group.location,
    account_name=storage_account_name,
    sku={
        "name": storage_sku,
    },
    kind=azure_native.storage.Kind.STORAGE_V2,
    allow_blob_public_access=True,
)

storage_account_keys = azure_native.storage.list_storage_account_keys_output(
    resource_group_name=resource_group.name, account_name=sa.name
)

blob_container = azure_native.storage.BlobContainer(
    "blobContainer",
    resource_group_name=resource_group.name,
    account_name=sa.name,
    container_name=blob_container_name,
    public_access=azure_native.storage.PublicAccess.BLOB,
)

app_blob = azure_native.storage.Blob(
    "appBlob",
    type=azure_native.storage.BlobType.BLOCK,
    resource_group_name=resource_group.name,
    account_name=sa.name,
    container_name=blob_container.name,
    blob_name=blob_name,
    source=pulumi.FileAsset("./hello-world.zip"),
)

app_service_plan = azure_native.web.AppServicePlan(
    "appServicePlan",
    resource_group_name=resource_group.name,
    name="service-plan",
    location=resource_group.location,
    sku={
        "name": "B1",
        "tier": "Basic",
    },
    kind="Linux",
    reserved=True,
)

web_app = azure_native.web.WebApp(
    "webApp",
    public_network_access="Enabled",
    resource_group_name=resource_group.name,
    location=resource_group.location,
    server_farm_id=app_service_plan.id,
    site_config={
        "linux_fx_version": "PYTHON|3.13",
        "app_settings": [
            {
                "name": "WEBSITE_RUN_FROM_PACKAGE",
                "value": f"https://{storage_account_name}.blob.core.windows.net/{blob_container_name}/{blob_name}",
            }
        ],
        "app_command_line": "pip install -r /home/site/wwwroot/requirements.txt && gunicorn -w 3 -b 0.0.0.0:8000 app:app",
    },
    client_affinity_enabled=False,
    https_only=True,
)

# Create a Log Analytics Workspace
workspace = operationalinsights.Workspace(
    "logAnalyticsWorkspace",
    resource_group_name=resource_group.name,
    location=resource_group.location,
    sku=operationalinsights.WorkspaceSkuArgs(name="PerGB2018"),
    retention_in_days=1,
)

# Create an Application Insights resource
app_insights = insights.Component(
    "appInsights",
    resource_group_name=resource_group.name,
    application_type="web",
    location=resource_group.location,
    kind="web",
    ingestion_mode="LogAnalytics",
    workspace_resource_id=workspace.id,
)
