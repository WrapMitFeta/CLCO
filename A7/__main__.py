"""An Azure RM Python Pulumi program"""

from pulumi_azure_native import (
    network,
)
import pulumi_azure_native as azure_native

# Configurations
location = "westeurope"

resource_group = azure_native.resources.ResourceGroup(
    "resource-group-cool",
    location=location,
)

# Create a Virtual Network
virtual_network = network.VirtualNetwork(
    "vnet",
    resource_group_name=resource_group.name,
    location=location,
    address_space=network.AddressSpaceArgs(
        address_prefixes=["10.0.0.0/16"],
    ),
)

# Create a subnet for the Web App
web_subnet = network.Subnet(
    "web-subnet",
    resource_group_name=resource_group.name,
    virtual_network_name=virtual_network.name,
    address_prefix="10.0.1.0/24",
    delegations=[
        network.DelegationArgs(
            name="delegation",
            service_name="Microsoft.Web/serverFarms",
        )
    ],
    private_endpoint_network_policies=network.VirtualNetworkPrivateEndpointNetworkPolicies.ENABLED,
)

# Create a subnet for the AI Service
ai_subnet = network.Subnet(
    "ai-subnet",
    resource_group_name=resource_group.name,
    virtual_network_name=virtual_network.name,
    address_prefix="10.0.2.0/24",
    private_endpoint_network_policies=network.VirtualNetworkPrivateEndpointNetworkPolicies.DISABLED,
)


# Create a private DNS zone
dns_zone = network.PrivateZone(
    "private-dns-zone",
    resource_group_name=resource_group.name,
    location="global",
    private_zone_name="privatelink.cognitiveservices.azure.com",
)

lang_service_account = azure_native.cognitiveservices.Account(
    "lang-service-account",
    account_name="a7-language-account-6",
    resource_group_name=resource_group.name,
    kind="TextAnalytics",
    location=location,
    sku={
        "name": "F0",
    },
    properties=azure_native.cognitiveservices.AccountPropertiesArgs(
        public_network_access=azure_native.cognitiveservices.PublicNetworkAccess.DISABLED,
        custom_sub_domain_name="a7-language-account-6-sub-domain",
    ),
)


# Invoke the list_account_keys function
account_keys = azure_native.cognitiveservices.list_account_keys_output(
    resource_group_name=resource_group.name,
    account_name=lang_service_account.name,
)

# Link the DNS zone to the virtual network
dns_zone_link = network.VirtualNetworkLink(
    "dns-zone-link",
    resource_group_name=resource_group.name,
    private_zone_name=dns_zone.name,
    virtual_network=network.SubResourceArgs(
        id=virtual_network.id,
    ),
    registration_enabled=False,
    location="global",
)

# Create a private endpoint for the AI service
ai_private_endpoint = network.PrivateEndpoint(
    "ai-private-endpoint",
    resource_group_name=resource_group.name,
    location=location,
    subnet=network.SubnetArgs(id=ai_subnet.id),
    private_link_service_connections=[
        network.PrivateLinkServiceConnectionArgs(
            name="ai-service-connection",
            private_link_service_id=lang_service_account.id,
            group_ids=["account"],
        )
    ],
)

dns_zone_group = network.PrivateDnsZoneGroup(
    "dns-zone-group",
    name="dns-zone-group-name",
    resource_group_name=resource_group.name,
    private_endpoint_name=ai_private_endpoint.name,
    private_dns_zone_configs=[
        network.PrivateDnsZoneConfigArgs(
            name="dns-zone-config-name",
            private_dns_zone_id=dns_zone.id,
        ),
    ],
)

app_service_plan = azure_native.web.AppServicePlan(
    "web-app-service-plan",
    resource_group_name=resource_group.name,
    location=location,
    sku=azure_native.web.SkuDescriptionArgs(
        name="B1",
        tier="Basic",
    ),
    kind="linux",
    reserved=True,
)

web_app = azure_native.web.WebApp(
    "web-app",
    virtual_network_subnet_id=web_subnet.id,
    resource_group_name=resource_group.name,
    location=location,
    server_farm_id=app_service_plan.id,
    https_only=True,
    kind="app,linux",
    site_config=azure_native.web.SiteConfigArgs(
        linux_fx_version="PYTHON|3.9",
        app_settings=[
            {
                "name": "AZ_ENDPOINT",
                "value": lang_service_account.properties.endpoint,
            },
            {
                "name": "AZ_KEY",
                "value": account_keys.apply(lambda keys: keys.key1),
            },
            {
                "name": "WEBSITE_RUN_FROM_PACKAGE",
                "value": "0",
            },
        ],
        always_on=True,
        ftps_state=azure_native.web.FtpsState.DISABLED,
    ),
)

source_control = azure_native.web.WebAppSourceControl(
    "web-app-source-control",
    name=web_app.name,
    resource_group_name=resource_group.name,
    repo_url="https://github.com/WrapMitFeta/clco-demo",
    branch="main",
    is_manual_integration=True,
    deployment_rollback_enabled=False,
    is_git_hub_action=False,
)
