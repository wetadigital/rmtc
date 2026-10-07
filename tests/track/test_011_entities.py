# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import (
    URI, 
    Type, 
    Datetime, 
    TypeName,
    Version,
    Logger,
    Factory,
)
from rmtc.system.objects import Data
from rmtc.track.store import Entity
from rmtc.track.entities import (
    Weights,
    Inference,
    Model,
    Asset,
    Solution,
    Run,
    License,
    Dataset,
    Resource,
    Party,
    Jurisdiction,
)
from rmtc.ops.assets import Image, Mesh

from abstract_rmtc_test import AbstractRMTCTest


class MockEntity(Entity):

    def __init__(self, name=None):
        super(MockEntity, self).__init__(name=name)
        self.add_property("number", int)
        self.add_property("dict_test", dict, {})
        self._updated = False
        self._accessed = False

    def property_updated(self, prop):
        self._updated = True
        super(MockEntity, self).property_updated(prop)

    def property_accessed(self, prop):
        self._accessed = True
        super(MockEntity, self).property_accessed(prop)

    @classmethod
    def category(cls):
        return "Mock"


class MockFactory(Factory):

    def __init__(self, log=None, env_manager=None):
        super(MockFactory, self).__init__(
            log=log, 
            env_manager=env_manager
        )

    def register(
        self,
        name,
        display_name,
        description,
        version,
        module,
        category,
        class_path,
        dependencies,
        deprecated=False,
        message="",
        abstract=False,     
    ):
        pass

    def deregister(
        self,
        type_name,
    ):
        pass

    def create(self, type_name, **kwargs):
        return MockEntity()

    def get_type_names(self, category, module=None, abridged=True):
        return [TypeName(string="rmtc_test.Entity.MockEntity-1.0.0")]

    def get_versions(self, unversioned_type_name):
        return [Version(string="1.0.0")]

    def is_registered_type_class(self, type_class):
        return True

    def is_registered_type_name(self, type_name):
        return True

    def get_type_info(self, type_name):
        return {
            "class_path": None,
            "display_name": None,
            "description": None,
            "dependencies": None,
            "deprecated": False,
            "message": None,
            "abstract": False,
        }

    def resolve_inverse(self, cls):
        return TypeName(string="rmtc_test.Entity.MockEntity-1.0.0")

    def resolve(self, type_name, dependencies=None):
        return MockEntity.__class__


class TestEntities(AbstractRMTCTest):

    def test_updated_at(self):
        rmtc_sys = self.get_system()
        entity = rmtc_sys.create_resource(name="Test Entity")
        test_time = Datetime()
        entity.add_property("test", int)
        entity.test = 100
        updated_at = entity.updated_at
        self.assertTrue(test_time < updated_at)
        rmtc_sys.push()
        rmtc_sys.clear()
        entity = rmtc_sys.get_entities(name="Test Entity")[0]
        self.assertTrue(entity.updated_at > updated_at)
        updated_at = entity.updated_at
        entity.test = 200
        self.assertTrue(entity.updated_at > updated_at)
        rmtc_sys.push()
        self.assertFalse(entity.requires_update())

    def test_entity_notification(self):
        obj = MockEntity()
        self.assertFalse(obj._accessed)
        obj.number #access number
        self.assertTrue(obj._accessed)
        self.assertFalse(obj._updated)
        obj.number = 10
        self.assertTrue(obj._updated)

    def test_nested_datasets(self):

        # create datasets
        dataset_a = Dataset("A")
        dataset_b = Dataset("B")
        dataset_c = Dataset("C")
        dataset_d = Dataset("D")
        dataset_e = Dataset("E")
        dataset_f = Dataset("F")
        dataset_g = Dataset("G")

        # add assets
        dataset_a.add_assets([Asset("A1"), Asset("A2"), Asset("A3")])
        dataset_b.add_assets([Asset("B1"), Asset("B2"), Asset("B3")])
        dataset_c.add_assets([Asset("C1"), Asset("C2"), Asset("C3")])
        dataset_d.add_assets([Asset("D1"), Asset("D2"), Asset("D3")])
        dataset_e.add_assets([Asset("E1"), Asset("E2"), Asset("E3")])
        dataset_f.add_assets([Asset("F1"), Asset("F2"), Asset("F3")])
        dataset_g.add_assets([Asset("G1"), Asset("G2"), Asset("G3")])

        # nest them in a tree
        dataset_a.add_datasets([dataset_b, dataset_c])
        dataset_b.add_datasets([dataset_d, dataset_e])
        dataset_c.add_datasets([dataset_f, dataset_g])

        # create depth first expected order - ABDECFG
        #      A
        #    /   \
        #   B     C
        #  / \   / \
        # D   E F   G
        names = [
            "A1",
            "A2",
            "A3",
            "B1",
            "B2",
            "B3",
            "D1",
            "D2",
            "D3",
            "E1",
            "E2",
            "E3",
            "C1",
            "C2",
            "C3",
            "F1",
            "F2",
            "F3",
            "G1",
            "G2",
            "G3",
        ]

        # validate
        collected_names = []
        for row in dataset_a:
            collected_names.append(row[0].name)
        self.assertEqual(names, collected_names)            

    def test_uniqueness(self):
        """Does an entity exist uniquely in the system"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_license(name="Apache-2.0")
        rmtc_sys.push()
        rmtc_sys.clear()
        self.assertEqual(len(rmtc_sys.objects.get()), 0)
        rmtc_sys.get_licenses(name="Apache-2.0")
        self.assertEqual(len(rmtc_sys.objects.get()), 1)

    def test_update_push(self):
        """Are the update flags being correctly set and cleared"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        test_a = rmtc_sys.create_license(name="Apache-2.0")
        rmtc_sys.push()
        test_a.add_parties([rmtc_sys.get_create(Party, name="ASWF")])
        self.assertTrue(test_a.requires_update())
        rmtc_sys.push()
        self.assertFalse(test_a.requires_update())
        rmtc_sys.clear()
        test_b = rmtc_sys.get_licenses(name="Apache-2.0")[0]   
        self.assertEqual(test_a.parties[0], test_b.parties[0])

    def test_array_element_edit_dirty(self):
        """Does an in-place array element edit mark the entity for update"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        test_a = rmtc_sys.create_license(name="Apache-2.0")
        test_a.add_parties([rmtc_sys.get_create(Party, name="ASWF"), rmtc_sys.get_create(Party, name="Mozilla")])
        rmtc_sys.push()
        self.assertFalse(test_a.requires_update())
        test_a.properties["parties"].set(rmtc_sys.get_create(Party, name="Linux Foundation"), 1)
        self.assertTrue(test_a.requires_update())
        rmtc_sys.push()
        rmtc_sys.clear()
        test_b = rmtc_sys.get_licenses(name="Apache-2.0")[0]
        self.assertEqual([p.name for p in test_b.parties], ["ASWF", "Linux Foundation"])

    def test_custom_pod_properties(self):
        """Can we add a custom pod type and do a round trip to the DB"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        test_a = rmtc_sys.create_license(name="Apache-2.0")
        test_a.add_property("test_value", int, 123)
        test_a.add_property("test_array", [int], [1, 2, 3])
        test_a.add_property("test_string", str, "Hello World!")
        self.assertTrue(test_a.requires_update())
        rmtc_sys.push()
        self.assertFalse(test_a.requires_update())
        rmtc_sys.clear()
        test_b = rmtc_sys.get_licenses(name="Apache-2.0")[0]
        self.assertEqual(test_a.test_value, test_b.test_value)
        self.assertEqual(test_a.test_array, test_b.test_array)
        self.assertEqual(test_a.test_string, test_b.test_string)

    def test_delete(self):
        """Can we mark an entity for deletion"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        test_a = rmtc_sys.create_license(name="Apache-2.0")
        rmtc_sys.push()
        rmtc_sys.clear()
        test_b = rmtc_sys.get_licenses(name="Apache-2.0")[0]
        self.assertTrue(test_b in rmtc_sys.objects.get())
        test_b.mark_for_delete()
        rmtc_sys.push()
        self.assertFalse(test_b in rmtc_sys.objects.get())
        self.assertTrue(test_b.store is None)

    def test_sync(self):
        """Test sync"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        uri = URI("https://www.apache.org/licenses/LICENSE-2.0.txt")
        test_a = rmtc_sys.create_license(name="Apache-2.0", uri=uri)
        rmtc_sys.push()
        a_id = test_a.obj_id
        rmtc_sys.clear()
        test_b = rmtc_sys.get_licenses(name="Apache-2.0", sync=False)[0]
        b_id = test_b.obj_id
        self.assertEqual(a_id, b_id)
        rmtc_sys.pull([test_b])
        self.assertEqual(test_b.uri, test_a.uri)

    def test_get_order(self):
        """Entities must return in the same order as the input IDs"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        entities = [
            rmtc_sys.create_resource(name="A"),
            rmtc_sys.create_resource(name="B"),
            rmtc_sys.create_resource(name="C"),                       
        ]
        entity_ids = [entity.obj_id for entity in entities]
        rmtc_sys.push()
        rmtc_sys.clear()
        entities = rmtc_sys.get_entities(obj_ids=entity_ids)
        for entity_id, entity in zip(entity_ids, entities):
            self.assertEqual(entity_id, entity.obj_id)

    def test_on_demand(self):
        """Can we have a property update on demand - without a connection"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        uri = URI("https://www.apache.org/licenses/LICENSE-2.0.txt")
        test_a = rmtc_sys.create_license(name="Apache-2.0", uri=uri)
        rmtc_sys.push()
        rmtc_sys.clear()
        test_b = rmtc_sys.get_licenses(name="Apache-2.0", sync=False)[0]
        self.assertEqual(test_b.uri, test_a.uri)

    def test_inferences(self):
        """Do assets and inference relationships make sense"""
        rmtc_sys = self.get_system()
        inputs = []
        for i in range(3):
            inputs.append(rmtc_sys.create_asset())
        inputs = rmtc_sys.create_dataset(assets=inputs)
        result = []
        for i in range(3):
            result.append(rmtc_sys.create_asset())
        outputs = rmtc_sys.create_dataset(assets=result)
        inference = rmtc_sys.create_inference(
            inputs=[inputs],
            outputs=[outputs],
        )
        self.assertEqual(len(inference.outputs[0].assets), 3)
        self.assertEqual(inference.outputs[0].assets, result)
        rmtc_sys.push()
        rmtc_sys.clear()
        self.assertEqual(len(rmtc_sys.objects.get()), 0)
        inferences = rmtc_sys.get_inferences()
        self.assertEqual(len(inferences), 1)

    def _flatten_tree(self, tree):
        result = [tree[0]]
        for value in tree[1]:
            result.extend(self._flatten_tree(value))
        return result

    def _create_provenance(self, rmtc_sys):

        license = rmtc_sys.create_license()
        train_dataset = rmtc_sys.create_dataset()
        train_dataset.license = license

        model = rmtc_sys.create_model()
        model.license = license

        weights = rmtc_sys.create_weights()
        weights.model = model

        solution = rmtc_sys.create_solution()

        run = rmtc_sys.create_run(solution=solution)
        run.model = model
        run.dataset = train_dataset
        run.result_weights = weights

        inputs = rmtc_sys.create_dataset()
        inputs.license = license

        outputs = rmtc_sys.create_dataset(assets=[
            rmtc_sys.create_asset(), 
            rmtc_sys.create_asset(), 
            rmtc_sys.create_asset()
        ])

        inference = rmtc_sys.create_inference(
            inputs=[inputs],
            outputs=[outputs],
            weights=weights,
            model=model,
        )

        return [solution, run, inference, model, license, train_dataset]

    def test_sources(self):
        """Search up"""
        
        rmtc_sys = self.get_system()
        entities = self._create_provenance(rmtc_sys)

        # add it to db
        rmtc_sys.push()
        rmtc_sys.clear()

        # query it directly
        inference = rmtc_sys.get_inferences()[0]
        sources = rmtc_sys.trace_sources(inference)
        flat_sources = self._flatten_tree(sources)
        self.assertTrue(len(flat_sources), 4)

    def test_derivatives(self):
        """Search down"""

        rmtc_sys = self.get_system()        
        entities = self._create_provenance(rmtc_sys)

        # add it to db
        rmtc_sys.push()
        rmtc_sys.clear()

        # query it directly
        solution = rmtc_sys.get_solutions()[0]
        derivatives = rmtc_sys.trace_derivatives(solution)
        flattened = self._flatten_tree(derivatives)
        self.assertTrue(len(flattened), 9)

    def test_factory(self):
        data = Data()
        rmtc_sys = self.get_system()
        prop_type = data.add_property("test_type", Type, License)
        prop_type.value = "rmtc_track.License.License-1.0.0"
        prop_type.value.resolve(rmtc_sys.factory)
        obj = prop_type.value()
        self.assertTrue(isinstance(obj, License))

    def test_reference_disconnect(self):
        """Create connected entities, push, disconnect and push"""
        rmtc_sys = self.get_system()

        # populate
        resource = rmtc_sys.create_resource(Resource, name="Test")
        license1 = rmtc_sys.create_license(name="A")
        license2 = rmtc_sys.create_license(name="B")
        resource.add_licenses([license1, license2])
        rmtc_sys.push()
        rmtc_sys.clear()

        # get and check
        resource = rmtc_sys.get_entities(name="Test")[0]
        licenses = resource.licenses
        self.assertEqual(len(licenses), 2)

        # disconnect & push
        license1 = licenses[0]
        resource.remove_licenses([license1])
        self.assertEqual(len(resource.licenses), 1)
        rmtc_sys.push()
        rmtc_sys.clear()

        # pull and check for only one reference, while the lost reference is still in the store
        resource = rmtc_sys.get_entities(name="Test")[0]
        licenses = resource.licenses
        self.assertEqual(len(licenses), 1)
        license = licenses[0]
        self.assertEqual(license.name, "B")
        self.assertEqual(len(rmtc_sys.get_entities(name="A", categories=["License"])), 1)

    def test_member_disconnect(self):
        """Removing a member object must also delete its node from the graph"""
        sys = self.get_system()
        sys.delete_all()

        # populate
        checkpoint1 = sys.create_checkpoint(name="Removed Checkpoint")
        checkpoint2 = sys.create_checkpoint(name="Kept Checkpoint")
        run = sys.create_run(name="Test Run")
        run.add_result_checkpoints([checkpoint1, checkpoint2])

        # precondition: the fixture property must be a member and array
        prop = run.properties["result_checkpoints"]
        self.assertTrue(prop.is_member())
        self.assertTrue(prop.is_array())

        sys.push()
        sys.clear()

        # get and check settled
        run = sys.get_entities(name="Test Run", categories=["Run"])[0]
        self.assertEqual(len(run.result_checkpoints), 2)
        self.assertFalse(run.requires_update())

        # disconnect & push
        removed = [c for c in run.result_checkpoints if c.name == "Removed Checkpoint"]
        run.remove_result_checkpoints(removed)
        self.assertTrue(run.requires_update())
        sys.push()
        sys.clear()

        # pull and check the member node is gone from the store
        run = sys.get_entities(name="Test Run", categories=["Run"])[0]
        self.assertEqual(len(run.result_checkpoints), 1)
        self.assertEqual(run.result_checkpoints[0].name, "Kept Checkpoint")
        self.assertEqual(
            len(sys.get_entities(name="Removed Checkpoint", categories=["Checkpoint"])), 0
        )
