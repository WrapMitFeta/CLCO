"""An Azure RM Python Pulumi program"""

from pulumi_azure_native import storage
from pulumi_azure_native import resources
from pulumi_azure_native import compute
from pulumi_azure_native import network
from pulumi_azure_native import insights
import pulumi
import random

random_number = str(random.random())[2:10]


resource_group_name = "resource-group-a12"
storage_account_name = "metricstoragea12"  # f"metricsstorage{random_number}"
# Create an Azure Resource Group
resource_group = resources.ResourceGroup(
    "resource_group",
    resource_group_name=resource_group_name,
)

storage_account = storage.StorageAccount(
    "storage_account",
    account_name=storage_account_name,
    resource_group_name=resource_group.name,
    sku=storage.SkuArgs(
        name=storage.SkuName.STANDARD_LRS,
    ),
    kind=storage.Kind.STORAGE_V2,
)

subnet_name = f"{resource_group_name}-subnet"
nsg_name = f"{resource_group_name}-nsg"
v_net_name = f"{resource_group_name}-vnet"

vnet = network.VirtualNetwork(
    "v-net",
    resource_group_name=resource_group.name,
    virtual_network_name=pulumi.Output.concat(
        resource_group.name,
        "-vnet",
    ),
    address_space=network.AddressSpaceArgs(
        address_prefixes=["10.0.0.0/16"],
    ),
)

subnet = network.Subnet(
    "subnet",
    resource_group_name=resource_group.name,
    virtual_network_name=vnet.name,
    subnet_name=subnet_name,
    address_prefix="10.0.1.0/24",
)

network_security_group = network.NetworkSecurityGroup(
    "network-security-group",
    network_security_group_name=nsg_name,
    resource_group_name=resource_group.name,
)

security_rule = network.SecurityRule(
    "security-rule",
    name="allow-80-inbound",
    network_security_group_name=network_security_group.name.apply(
        lambda name: name,
    ),
    resource_group_name=resource_group.name,
    priority=110,
    source_address_prefix="*",
    source_port_range="*",
    destination_address_prefix="*",
    destination_port_range="80",
    access=network.SecurityRuleAccess.ALLOW,
    direction=network.SecurityRuleDirection.INBOUND,
    protocol=network.SecurityRuleProtocol.TCP,
)

public_ip = network.PublicIPAddress(
    "public-ip",
    resource_group_name=resource_group.name,
    public_ip_address_name="public-ip",
    sku=network.PublicIPAddressSkuArgs(
        name="Standard",
    ),
    public_ip_allocation_method=network.IpAllocationMethod.STATIC,
)

nic = network.NetworkInterface(
    "nic",
    resource_group_name=resource_group_name,
    network_interface_name="nic",
    ip_configurations=[
        network.NetworkInterfaceIPConfigurationArgs(
            name="ipconfig-1",
            subnet=network.SubnetArgs(
                id=subnet.id,
            ),
            private_ip_allocation_method=network.IpAllocationMethod.DYNAMIC,
        )
    ],
    network_security_group=network.NetworkSecurityGroupArgs(
        id=network_security_group.id,
    ),
)

virtual_machine = compute.VirtualMachine(
    "monitored-linux-vm",
    resource_group_name=resource_group.name,
    vm_name="monitored-linux-vm",
    network_profile={
        "network_interfaces": [
            {
                "id": nic.id,
            }
        ],
    },
    diagnostics_profile=compute.DiagnosticsProfileArgs(
        boot_diagnostics=compute.BootDiagnosticsArgs(
            storage_uri=storage_account.primary_endpoints.apply(
                lambda endpoints: endpoints.blob
            ),
        ),
    ),
    hardware_profile=compute.HardwareProfileArgs(
        vm_size=compute.VirtualMachineSizeTypes.STANDARD_DS1_V2,
    ),
    storage_profile=compute.StorageProfileArgs(
        image_reference=compute.ImageReferenceArgs(
            publisher="Canonical",
            offer="0001-com-ubuntu-server-jammy",
            sku="22_04-lts",
            version="latest",
        ),
    ),
    os_profile=compute.OSProfileArgs(
        computer_name="monitored-linux-vm",
        admin_username="azureuser",
        admin_password="Password@secure1234!",
    ),
)

vm_extension = compute.VirtualMachineExtension(
    "vm-extension",
    resource_group_name=resource_group.name,
    vm_name=virtual_machine.name.apply(
        lambda name: name,
    ),
    vm_extension_name="vm-extension",
    publisher="Microsoft.Azure.Extensions",
    type="CustomScript",
    type_handler_version="2.1",
    auto_upgrade_minor_version=True,
    settings={
        "commandToExecute": "sudo apt-get update && sudo apt-get install -y nginx && echo '<head><title>Web server monitored-linux-vm</title></head><body><h1>Web Portal</h1><p>Web server monitored-linux-vm</p></body>' > /var/www/html/index.html && sudo systemctl start nginx"
    },
)

action_group = insights.ActionGroup(
    "action-group",
    location="global",
    resource_group_name=resource_group.name,
    action_group_name=f"{resource_group_name}-action-group",
    group_short_name="action-short",
    enabled=True,
    email_receivers=[
        insights.EmailReceiverArgs(
            name="super email",
            email_address="wi22b114@technikum-wien.at",
        )
    ],
)

cpu_metric_alert = insights.MetricAlert(
    "cpu-metric-alert",
    resource_group_name=resource_group.name,
    rule_name="high cpu alert",
    description="Alert when CPU usage exceeds 80 percent over a 5-minute period",
    severity=3,
    enabled=True,
    location="global",
    scopes=[
        virtual_machine.id.apply(lambda id: id),
    ],
    criteria=insights.MetricAlertSingleResourceMultipleMetricCriteriaArgs(
        odata_type="Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria",
        all_of=[
            insights.MetricCriteriaArgs(
                criterion_type="StaticThresholdCriterion",
                name="high cpu usage",
                metric_name="Percentage CPU",
                metric_namespace="Microsoft.Compute/virtualMachines",
                time_aggregation=insights.AggregationTypeEnum.AVERAGE,
                operator=insights.ConditionOperator.GREATER_THAN,
                threshold=80,
            )
        ],
    ),
    actions=[
        insights.MetricAlertActionArgs(
            action_group_id=action_group.id.apply(lambda id: id),
        )
    ],
    evaluation_frequency="PT1M",
    window_size="PT5M",
)
