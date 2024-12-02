"""An Azure RM Python Pulumi program"""

from pulumi_azure_native import resources
from pulumi_azure_native import network
from pulumi_azure_native import compute

import pulumi

resource_group_name = "resource-group-a8"
# Create an Azure Resource Group
resource_group = resources.ResourceGroup(
    "resource-group",
    resource_group_name=resource_group_name,
    location="westeurope",
)

vnet = network.VirtualNetwork(
    "v-net",
    resource_group_name=resource_group.name.apply(
        lambda name: name,
    ),
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
    subnet_name=pulumi.Output.concat(
        resource_group.name,
        "-subnet",
    ),
    address_prefix="10.0.1.0/24",
)

network_security_group = network.NetworkSecurityGroup(
    "network-security-group",
    network_security_group_name=pulumi.Output.concat(
        resource_group.name,
        "-nsg",
    ),
    resource_group_name=resource_group.name,
    location=resource_group.location,
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
    location=resource_group.location,
    sku=network.PublicIPAddressSkuArgs(
        name="Standard"  # Ensure Standard SKU is used
    ),
    public_ip_allocation_method=network.IpAllocationMethod.STATIC,
)

load_balancer = network.LoadBalancer(
    "load-balancer",
    resource_group_name=resource_group.name,
    load_balancer_name="load-balancer",
    sku=network.LoadBalancerSkuArgs(name="Standard"),
    frontend_ip_configurations=[
        network.FrontendIPConfigurationArgs(
            name="frontend-ip",
            public_ip_address=network.PublicIPAddressArgs(id=public_ip.id),
        )
    ],
    backend_address_pools=[
        network.BackendAddressPoolArgs(
            name="backend-pool",
        )
    ],
    probes=[
        network.ProbeArgs(
            name="probe",
            protocol="Http",
            port=80,
            request_path="/",
            interval_in_seconds=10,
            number_of_probes=2,
        ),
    ],
    load_balancing_rules=[
        network.LoadBalancingRuleArgs(
            name="load-balancing-rule",
            frontend_ip_configuration=network.SubResourceArgs(
                id="/subscriptions/f0225753-f6de-42b8-b862-8c4003ccf2be/resourceGroups/resource-group-a8/providers/Microsoft.Network/loadBalancers/load-balancer/frontendIPConfigurations/frontend-ip",
            ),
            backend_address_pool=network.SubResourceArgs(
                id="/subscriptions/f0225753-f6de-42b8-b862-8c4003ccf2be/resourceGroups/resource-group-a8/providers/Microsoft.Network/loadBalancers/load-balancer/backendAddressPools/backend-pool",
            ),
            probe=network.SubResourceArgs(
                id="/subscriptions/f0225753-f6de-42b8-b862-8c4003ccf2be/resourceGroups/resource-group-a8/providers/Microsoft.Network/loadBalancers/load-balancer/probes/probe",
            ),
            protocol="Tcp",
            frontend_port=80,
            backend_port=80,
            idle_timeout_in_minutes=4,
            enable_floating_ip=False,
            load_distribution=network.LoadDistribution.DEFAULT,
        ),
    ],
)

nics = []

for i in range(1, 3):
    nics.append(
        network.NetworkInterface(
            f"nic-{i}",
            resource_group_name=resource_group_name,
            network_interface_name=f"nic-{i}",
            ip_configurations=[
                network.NetworkInterfaceIPConfigurationArgs(
                    name=f"ipconfig-{i}",
                    subnet=network.SubnetArgs(id=subnet.id),
                    private_ip_allocation_method=network.IpAllocationMethod.DYNAMIC,
                    load_balancer_backend_address_pools=[
                        network.SubResourceArgs(
                            id=pulumi.Output.concat(
                                load_balancer.id,
                                "/backendAddressPools/backend-pool",
                            )
                        )
                    ],
                )
            ],
            network_security_group=network.NetworkSecurityGroupArgs(
                id=network_security_group.id,
            ),
        )
    )

vms = []

for i in range(1, 3):
    vms.append(
        compute.VirtualMachine(
            f"vm-{i}",
            resource_group_name=resource_group.name,
            vm_name=f"vm-{i}",
            network_profile={
                "network_interfaces": [
                    {
                        "id": nics[i - 1].id,
                    }
                ],
            },
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
                computer_name=f"vm-{i}",
                admin_username="adminuser",
                admin_password="Password@secure1234!",
            ),
        )
    )

for i in range(1, 3):
    compute.VirtualMachineExtension(
        f"vm-extension-{i}",
        resource_group_name=resource_group.name,
        vm_name=vms[i - 1].name.apply(
            lambda name: name,
        ),
        vm_extension_name=f"vm-extension-{i}",
        publisher="Microsoft.Azure.Extensions",
        type="CustomScript",
        type_handler_version="2.1",
        auto_upgrade_minor_version=True,
        settings={
            "commandToExecute": f"sudo apt-get update && sudo apt-get install -y nginx && echo '<head><title>Web server {i}</title></head><body><h1>Web Portal</h1><p>Web server {i}</p></body>' > /var/www/html/index.html && sudo systemctl start nginx"
        },
    )

pulumi.export("public_ip", public_ip.ip_address)
