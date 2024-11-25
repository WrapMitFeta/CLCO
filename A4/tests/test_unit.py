import unittest

import pulumi


class MyMocks(pulumi.runtime.Mocks):
    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        return [args.name + "_id", args.inputs]

    def call(self, args: pulumi.runtime.MockCallArgs):
        return {}


pulumi.runtime.set_mocks(
    MyMocks(),
    preview=False,
)


from resources.resources import storage_location, app_service_plan  # noqa: E402


class TestingWithMocks(unittest.TestCase):
    @pulumi.runtime.test
    def test_check_storage_location(self):
        def checktags(args):
            location = args[0]
            self.assertEqual(location, "WestUS")

        return pulumi.Output.all(storage_location).apply(checktags)

    @pulumi.runtime.test
    def test_check_app_service_plan_sku(self):
        def checktags(args):
            sku = args[0]
            self.assertEqual(sku["name"], "B1")
            self.assertEqual(sku["tier"], "Basic")

        return pulumi.Output.all(app_service_plan.sku).apply(checktags)


if __name__ == "__main__":
    unittest.main()
