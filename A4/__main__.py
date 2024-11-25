import pulumi

from resources.resources import (
    storage_account_keys,
    sa,
    web_app,
    resource_group,
)

pulumi.export("primaryStorageKey", storage_account_keys.keys[0].value)
pulumi.export("staticEndpoint", sa.primary_endpoints.web)
pulumi.export(
    "webappUrl",
    {
        "value": web_app.default_host_name.apply(
            lambda default_host_name: f"https://{default_host_name}"
        ),
    },
)
pulumi.export("resourceGroup", resource_group.name)
