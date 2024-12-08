"""Project I: PaaS-Group-10"""

import pulumi
from pulumi_azure_native import (
    network,
    resources,
    cognitiveservices,
    web,
    consumption,
)

subscription_id = "f0225753-f6de-42b8-b862-8c4003ccf2be"

# Create an Azure Resource Group
resource_group = resources.ResourceGroup(
    "resource_group",
    resource_group_name="PaaS_Group_10",
)

# Create a Virtual Network
virtual_network = network.VirtualNetwork(
    "vnet",
    resource_group_name=resource_group.name,
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

# Create a cognitive service account
lang_service_account = cognitiveservices.Account(
    "lang-service-account",
    account_name="PaaS-Group-10-language-account",
    resource_group_name=resource_group.name,
    kind="TextAnalytics",
    sku={
        "name": "F0",
    },
    properties=cognitiveservices.AccountPropertiesArgs(
        public_network_access=cognitiveservices.PublicNetworkAccess.DISABLED,
        custom_sub_domain_name="PaaS-Group-10-language-account-sub-domain",
    ),
)


# Create a private endpoint for the AI service
ai_private_endpoint = network.PrivateEndpoint(
    "ai-private-endpoint",
    resource_group_name=resource_group.name,
    subnet=network.SubnetArgs(
        id=ai_subnet.id,
    ),
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

# Create a service plan for the web app
app_service_plan = web.AppServicePlan(
    "web-app-service-plan",
    resource_group_name=resource_group.name,
    sku=web.SkuDescriptionArgs(
        name="B1",
        tier="Basic",
        capacity=3,  # three web apps workers
    ),
    kind="linux",
    reserved=True,
)

# Invoke the list_account_keys function
account_keys = cognitiveservices.list_account_keys_output(
    resource_group_name=resource_group.name,
    account_name=lang_service_account.name,
)

# Create the web app
web_app = web.WebApp(
    "web-app",
    virtual_network_subnet_id=web_subnet.id,
    resource_group_name=resource_group.name,
    server_farm_id=app_service_plan.id,
    https_only=True,
    kind="app,linux",
    site_config=web.SiteConfigArgs(
        linux_fx_version="PYTHON|3.9",
        app_settings=[
            web.NameValuePairArgs(
                name="AZ_ENDPOINT",
                value=lang_service_account.properties.endpoint,
            ),
            web.NameValuePairArgs(
                name="AZ_KEY",
                value=account_keys.apply(lambda keys: keys.key1),
            ),
            web.NameValuePairArgs(
                name="WEBSITE_RUN_FROM_PACKAGE",
                value="0",
            ),
        ],
        always_on=True,
        ftps_state=web.FtpsState.DISABLED,
    ),
)

source_control = web.WebAppSourceControl(
    "web-app-source-control",
    name=web_app.name,
    resource_group_name=resource_group.name,
    repo_url="https://github.com/WrapMitFeta/clco-demo",
    branch="main",
    is_manual_integration=True,
    deployment_rollback_enabled=False,
    is_git_hub_action=False,
    opts=pulumi.ResourceOptions(
        custom_timeouts={"create": "15m"},
    ),
)


# Create a budget
budget_name = "MonthlyBudget"
budget_amount = 30

team_member_1_email = "wi22b114@technikum-wien.at"
team_member_2_email = "wi22b075@technikum-wien.at"


budget = consumption.Budget(
    resource_name=budget_name,
    scope=pulumi.Output.concat(
        "/subscriptions/",
        subscription_id,
        "/resourceGroups/",
        resource_group.name,
    ),
    amount=budget_amount,
    category=consumption.CategoryType.COST,
    time_grain=consumption.TimeGrainType.MONTHLY,
    time_period=consumption.BudgetTimePeriodArgs(
        start_date="2024-12-01",
        end_date="2024-12-31",
    ),
    notifications={
        consumption.ThresholdType.ACTUAL: consumption.NotificationArgs(
            enabled=True,
            operator=consumption.OperatorType.GREATER_THAN,
            threshold=50,
            contact_emails=[
                team_member_1_email,
                team_member_2_email,
            ],
        ),
        consumption.ThresholdType.FORECASTED: consumption.NotificationArgs(
            enabled=True,
            operator=consumption.OperatorType.GREATER_THAN,
            threshold=50,
            contact_emails=[
                team_member_1_email,
                team_member_2_email,
            ],
        ),
    },
)

pulumi.export("web_app_url", web_app.default_host_name)
