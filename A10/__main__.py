import uuid
import pulumi
from pulumi_azuread import get_user
from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient
import pulumi_azure_native.authorization as auth
from pulumi_azure_native import resources

config = pulumi.Config("azure")
subscription_id = config.require("subscriptionId")

email_address = "wi22b114@technikum-wien.at"

user = get_user(user_principal_name=email_address)

scope = f"/subscriptions/{subscription_id}"

# Use azure.mgmt.authorization to get role assignments
# as pulumi does not support this, only `pulumi_azure_native.authorization.get_role_assignment`
# which does not list all
client = AuthorizationManagementClient(
    DefaultAzureCredential(),
    subscription_id,
)


# Use $filter=principalId eq {id} to return all roles
response = client.role_assignments.list_for_subscription(
    filter=f"principalId eq '{user.object_id}'"
)

# Task 1: List Role Assignments for a User

# List all role assignments for the subscription
role_assignments = []
for assignment in response:
    role_assignments.append(
        {
            "roleDefinitionId": assignment.role_definition_id,
            "name": assignment.name,
            "scope": assignment.scope,
            "principalId": assignment.principal_id,
            "id": assignment.id,
        }
    )

# Export the role assignments
pulumi.export("role_assignments", role_assignments)

# Task 2: Assign a Role

# Use azure.mgmt.authorization to get role definitions
# as pulumi does not support this, only `pulumi_azure_native.authorization.get_role_definition`
# which does not list all
role_definitions = client.role_definitions.list(scope=scope)

# Get the role id for the Log Analytics Reader role
reader_id = None
for role in role_definitions:
    if role.role_name == "Log Analytics Reader":
        reader_id = role.id

resource_group = resources.ResourceGroup(
    "resource_group",
    resource_group_name="resource_group_a10",
)

# Create the role assignment
role_assignment = auth.RoleAssignment(
    "reader-role-assignment",
    principal_id=user.object_id,
    role_assignment_name=str(uuid.uuid4()),
    principal_type=auth.PrincipalType.USER,
    role_definition_id=reader_id,
    scope=resource_group.id,
)

pulumi.export("role_assignment_id", role_assignment.id)
