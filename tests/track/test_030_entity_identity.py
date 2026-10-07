# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

from rmtc.system import Datetime, Version, RMTCException
from rmtc.system.objects import Property, Unlocked
from rmtc.track.store import MergeType
from rmtc.track.entities import Resource, Run, License, Solution

from abstract_rmtc_test import AbstractRMTCTest


class TestInstantiatedAt(AbstractRMTCTest):
    """Creation identity - stamping, immutability and persistence"""

    def test_instantiated_at_is_set_at_construction(self):
        """The stamp is taken when the object is built, not when it is written"""
        before = Datetime()
        entity = Resource(name="Stamp Test")
        after = Datetime()
        self.assertTrue(before <= entity.instantiated_at)
        self.assertTrue(entity.instantiated_at <= after)

    def test_instantiated_at_is_readonly(self):
        """Every mutation path must be refused, not just attribute assignment"""
        entity = Resource(name="Readonly Test")
        created = entity.instantiated_at

        with self.assertRaises(RMTCException):
            entity.instantiated_at = Datetime()
        with self.assertRaises(RMTCException):
            entity.properties["instantiated_at"].value = Datetime()
        with self.assertRaises(RMTCException):
            entity.properties["instantiated_at"][0] = Datetime()

        self.assertEqual(entity.instantiated_at, created)

    def test_unlocked_permits_assignment_and_restores(self):
        """The sanctioned bypass must put the flag back"""
        entity = Resource(name="Unlocked Test")
        prop = entity.properties["instantiated_at"]
        self.assertTrue(prop.readonly)

        stamp = Datetime()
        with Unlocked(prop):
            self.assertFalse(prop.readonly)
            prop.value = stamp

        self.assertTrue(prop.readonly)
        self.assertEqual(entity.instantiated_at, stamp)

    def test_unlocked_restores_on_exception(self):
        """A raise inside the block must not leave the property writable"""
        entity = Resource(name="Unlocked Raise Test")
        prop = entity.properties["instantiated_at"]
        try:
            with Unlocked(prop):
                raise RMTCException("forced")
        except RMTCException:
            pass
        self.assertTrue(prop.readonly)

    def test_instantiated_at_round_trip(self):
        """instantiated_at must be written on create and read back on fetch"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        entity = rmtc_sys.create_resource(name="Round Trip")
        created = entity.instantiated_at
        rmtc_sys.push()
        rmtc_sys.clear()
        fetched = rmtc_sys.get_entities(name="Round Trip")[0]
        self.assertEqual(fetched.instantiated_at, created)

    def test_instantiated_at_survives_update(self):
        """An update writes every property - the stamp must not move"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        entity = rmtc_sys.create_resource(name="Update Stamp")
        created = entity.instantiated_at
        rmtc_sys.push()
        self.assertFalse(entity.requires_update())

        entity.author = "test_author"
        self.assertTrue(entity.requires_update())
        rmtc_sys.push()
        rmtc_sys.clear()

        fetched = rmtc_sys.get_entities(name="Update Stamp")[0]
        self.assertEqual(fetched.instantiated_at, created)
        self.assertEqual(fetched.author, "test_author")

    def test_pushed_at_is_independent_of_instantiated_at(self):
        """_pushed_at is a fresh write-time stamp, not a copy of the
        entity's own instantiated_at - the two may agree closely but are not
        the same moment by construction, and neither is required to equal
        the other"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        entity = rmtc_sys.create_resource(name="Pushed At Column")
        rmtc_sys.push()

        connection = rmtc_sys.track.open()
        results = connection.read_query(
            """
            MATCH (e) WHERE e._obj_id=$obj_id AND e._store=$store
            RETURN e._pushed_at AS pushed_at, e.instantiated_at AS instantiated_at
            """,
            obj_id=entity.obj_id,
            store=rmtc_sys.track.store.name,
        )
        connection.close()

        self.assertEqual(len(results), 1)
        pushed_at = Datetime(string=results[0]["pushed_at"])
        instantiated_at = Datetime(string=results[0]["instantiated_at"])
        self.assertTrue(pushed_at >= instantiated_at)

    def test_duplicate_restamps(self):
        """A duplicate is a new entity and must carry its own creation time"""
        entity = Resource(name="Duplicate Source")
        dupe = entity.duplicate()
        self.assertNotEqual(dupe.obj_id, entity.obj_id)
        self.assertTrue(dupe.instantiated_at > entity.instantiated_at)
        self.assertTrue(dupe.properties["instantiated_at"].readonly)

    def test_merge_does_not_move_instantiated_at(self):
        """Readonly properties are identity and never merge"""
        source = Resource(name="Merge Source")
        target = Resource(name="Merge Target")
        created = target.instantiated_at

        target.merge(source, strategy=MergeType.OTHER)

        self.assertEqual(target.name, "Merge Source")
        self.assertEqual(target.instantiated_at, created)
        self.assertTrue(target.requires_update())

    def test_merge_keeps_property_objects(self):
        """Merging assigns through the setter, it does not replace properties"""
        source = Resource(name="Property Source")
        target = Resource(name="Property Target")
        target.merge(source, strategy=MergeType.OTHER)
        for name, prop in target.properties.items():
            self.assertTrue(
                isinstance(prop, Property), f"{name} is not a Property after merge"
            )

    def test_readonly_property_cannot_be_redeclared(self):
        """add_property must refuse to shadow a readonly property with a
        fresh writable one"""
        entity = Resource(name="Redeclare Test")
        with self.assertRaises(RMTCException):
            entity.add_property("instantiated_at", Datetime, Datetime())
        self.assertTrue(entity.properties["instantiated_at"].readonly)

    def test_setitem_assigns_through_the_property(self):
        """Dictionary assignment must go through the value setter, never
        replace the Property object with a bare value"""
        entity = Resource(name="Setitem Test")
        entity["name"] = "Setitem Renamed"
        self.assertIsInstance(entity.properties["name"], Property)
        self.assertEqual(entity.name, "Setitem Renamed")

    def test_setitem_respects_readonly(self):
        entity = Resource(name="Setitem Readonly")
        with self.assertRaises(RMTCException):
            entity["instantiated_at"] = Datetime()

    def test_instantiated_at_round_trip_create_only(self):
        """A create-only write and a bare fetch - no update write and no full
        sync that could self-heal a broken create path (the masking pattern
        that hid the metrics persistence bug)"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        entity = rmtc_sys.create_resource(name="Bare Round Trip")
        created = entity.instantiated_at
        entity.reset_update()
        rmtc_sys.push()
        rmtc_sys.clear()
        fetched = rmtc_sys.get_entities(name="Bare Round Trip", sync=False)[0]
        self.assertEqual(fetched.instantiated_at, created)


class TestQueries(AbstractRMTCTest):
    """Fuzzy get - name matching, creation windows and recency"""

    def _seed_ordered(self, rmtc_sys):
        """Three resources in known creation order, oldest first"""
        first = rmtc_sys.create_resource(name="Alpha Resource")
        second = rmtc_sys.create_resource(name="Beta Resource")
        third = rmtc_sys.create_resource(name="Gamma Resource")
        rmtc_sys.push()
        return first, second, third

    def test_exact_name(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        self._seed_ordered(rmtc_sys)
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(name="Beta Resource", categories=["Resource"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Beta Resource")

    def test_exact_name_rejects_substring(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        self._seed_ordered(rmtc_sys)
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(name="Beta", categories=["Resource"])
        self.assertEqual(len(results), 0)

    def test_fuzzy_name_matches_substring(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        self._seed_ordered(rmtc_sys)
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            name="Beta", categories=["Resource"], exact=False
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Beta Resource")

    def test_fuzzy_name_is_case_insensitive(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        self._seed_ordered(rmtc_sys)
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            name="beta resource", categories=["Resource"], exact=False
        )
        self.assertEqual(len(results), 1)

    def test_fuzzy_name_escapes_metacharacters(self):
        """A dot in the term must match a literal dot, not any character"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_resource(name="Apache-2.0")
        rmtc_sys.create_resource(name="Apache-250")
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            name="Apache-2.0", categories=["Resource"], exact=False
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Apache-2.0")

    def test_created_window_lower_bound(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        _, second, _ = self._seed_ordered(rmtc_sys)
        boundary = second.instantiated_at
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            categories=["Resource"], instantiated_after=boundary
        )
        names = sorted(entity.name for entity in results)
        self.assertEqual(names, ["Beta Resource", "Gamma Resource"])

    def test_created_window_upper_bound(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        _, second, _ = self._seed_ordered(rmtc_sys)
        boundary = second.instantiated_at
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            categories=["Resource"], instantiated_before=boundary
        )
        names = sorted(entity.name for entity in results)
        self.assertEqual(names, ["Alpha Resource", "Beta Resource"])

    def test_created_window_pins_a_single_entity(self):
        """name plus instantiated_at is the identity - the window must resolve one"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        _, second, _ = self._seed_ordered(rmtc_sys)
        boundary = second.instantiated_at
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            categories=["Resource"],
            instantiated_after=boundary,
            instantiated_before=boundary,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Beta Resource")

    def test_results_are_newest_first(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        self._seed_ordered(rmtc_sys)
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(categories=["Resource"])
        names = [entity.name for entity in results]
        self.assertEqual(
            names, ["Gamma Resource", "Beta Resource", "Alpha Resource"]
        )

    def test_latest_returns_one(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        self._seed_ordered(rmtc_sys)
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(categories=["Resource"], latest=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Gamma Resource")

    def test_limit_returns_the_most_recent(self):
        """A limit is now ordered, so it is the newest N and not an arbitrary N"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        self._seed_ordered(rmtc_sys)
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(categories=["Resource"], limit=2)
        names = [entity.name for entity in results]
        self.assertEqual(names, ["Gamma Resource", "Beta Resource"])

    def test_latest_applies_across_categories(self):
        """One query runs per category, so latest must be reapplied over the union"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_resource(name="Older Resource")
        rmtc_sys.push()
        rmtc_sys.create_license(name="Newer License")
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            categories=["Resource", "License"], latest=True
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Newer License")

    def test_fuzzy_name_survives_the_category_loop(self):
        """The pattern must be rebuilt per category, never rewritten in place"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_resource(name="Shared Prefix Resource")
        rmtc_sys.create_license(name="Shared Prefix License")
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            categories=["Resource", "License"],
            name="Shared Prefix",
            exact=False,
        )
        self.assertEqual(len(results), 2)

    def test_get_runs_by_name(self):
        """get_runs filtered on an alias its pattern never bound"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.track.create_run(name="Alpha Run")
        rmtc_sys.track.create_run(name="Beta Run")
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_runs(name="Beta Run")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Beta Run")

    def test_get_inferences_by_name(self):
        """Same undefined alias as get_runs"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_inference(name="Alpha Inference")
        rmtc_sys.create_inference(name="Beta Inference")
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_inferences(name="Beta Inference")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Beta Inference")

    def test_get_runs_latest_is_recency_not_metric(self):
        """latest must not be re-ranked by the metric sort"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        better = rmtc_sys.track.create_run(name="Older Better Run")
        better.metric = 0.1
        worse = rmtc_sys.track.create_run(name="Newer Worse Run")
        worse.metric = 0.9
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_runs(latest=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Newer Worse Run")

    def test_get_licenses_forwards_exact(self):
        """System.get_licenses dropped exact on the way through"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_license(name="Apache-2.0")
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_licenses(name="Apache", exact=False)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Apache-2.0")

    def test_get_icenses_forwards_limit(self):
        """System.get_licenses dropped limit on the way through"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        for index in range(3):
            rmtc_sys.create_license(name=f"License {index}")
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_licenses(limit=2)
        self.assertEqual(len(results), 2)

    def test_nodes_without_instantiated_at_fall_outside_a_window(self):
        """Pre migration nodes are invisible to a window query until backfilled"""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        entity = rmtc_sys.create_resource(name="Legacy Node")
        rmtc_sys.push()

        connection = rmtc_sys.track.open()
        connection.write_query(
            """
            MATCH (e) WHERE e._obj_id=$obj_id AND e._store=$store
            REMOVE e.instantiated_at
            """,
            obj_id=entity.obj_id,
            store=rmtc_sys.track.store.name,
        )
        connection.close()
        rmtc_sys.clear()

        windowed = rmtc_sys.get_entities(
            categories=["Resource"],
            instantiated_after=Datetime("2000-01-01T00:00:00+00:00"),
        )
        self.assertEqual(len(windowed), 0)

        unfiltered = rmtc_sys.get_entities(categories=["Resource"])
        self.assertEqual(len(unfiltered), 1)


class TestVersionProperty(AbstractRMTCTest):
    """version is an opt-in identity source, alongside instantiated_at

    version lives in Artifact (required) and
    its subclasses, plus Run and License (both optional). It must not
    reappear on Entity broadly, nor on entities that never had it.
    """

    def test_version_is_present_and_required_on_artifact(self):
        """Resource is an Artifact - version must exist and be required"""
        entity = Resource(name="Version Presence Test")
        self.assertIn("version", entity.properties)
        self.assertTrue(entity.properties["version"].required)

    def test_unset_artifact_version_defaults_to_valid_one_zero_zero(self):
        """required=True must not force callers to supply a value - the
        property system already defaults an unset Version to 1.0.0"""
        entity = Resource(name="Version Default Test")
        self.assertEqual(entity.version, Version("1.0.0"))
        self.assertTrue(entity.version.is_valid())

    def test_explicit_artifact_version_is_honoured(self):
        entity = Resource(name="Version Explicit Test", version=Version("2.5.0"))
        self.assertEqual(entity.version, Version("2.5.0"))

    def test_version_is_present_and_optional_on_run(self):
        run = Run(name="Run Version Test")
        self.assertIn("version", run.properties)
        self.assertFalse(run.properties["version"].required)

    def test_version_is_present_and_optional_on_license(self):
        license_ = License(name="License Version Test")
        self.assertIn("version", license_.properties)
        self.assertFalse(license_.properties["version"].required)

    def test_version_is_present_and_optional_on_solution(self):
        solution_ = Solution(name="Solution Version Test")
        self.assertIn("version", solution_.properties)
        self.assertFalse(solution_.properties["version"].required)

    def test_version_is_absent_from_never_versioned_entities(self):
        from rmtc.track.entities import Jurisdiction, Party, Tag, Right

        for cls in (Jurisdiction, Party, Tag, Right):
            entity = cls(name=f"{cls.__name__} Version Test")
            self.assertNotIn(
                "version",
                entity.properties,
                f"{cls.__name__} must not carry a version property",
            )

        # Filter is abstract - use a concrete subclass to check the base
        # class doesn't add a version property
        from rmtc.core.track.filters.logic import Truth

        entity = Truth()
        self.assertNotIn(
            "version",
            entity.properties,
            "Filter must not carry a version property",
        )

    def test_version_survives_push_and_fetch_round_trip(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        entity = rmtc_sys.create_resource(
            name="Version Round Trip", version=Version("3.1.4")
        )
        rmtc_sys.push()
        rmtc_sys.clear()
        fetched = rmtc_sys.get_entities(name="Version Round Trip")[0]
        self.assertEqual(fetched.version, Version("3.1.4"))

    def test_instantiated_at_and_version_coexist_on_the_same_entity(self):
        """Both identity mechanisms are present at once - selecting one for
        path/identity purposes elsewhere does not require dropping the
        other"""
        entity = Resource(name="Coexist Test", version=Version("1.2.0"))
        self.assertIsNotNone(entity.instantiated_at)
        self.assertEqual(entity.version, Version("1.2.0"))


class TestVersionQueryFiltering(AbstractRMTCTest):
    """version= exact-match filtering, additive alongside the existing
    instantiated_after/instantiated_before/latest windowing - not a replacement"""

    def test_get_entities_exact_version_match(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_resource(name="Alpha", version=Version("1.0.0"))
        rmtc_sys.create_resource(name="Beta", version=Version("2.0.0"))
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            categories=["Resource"], version=Version("2.0.0")
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Beta")

    def test_get_entities_version_filter_excludes_non_matching(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_resource(name="Alpha", version=Version("1.0.0"))
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            categories=["Resource"], version=Version("9.9.9")
        )
        self.assertEqual(len(results), 0)

    def test_get_models_forwards_version(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_model(name="Old Model", version=Version("1.0.0"))
        rmtc_sys.create_model(name="New Model", version=Version("5.0.0"))
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_models(version=Version("5.0.0"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "New Model")

    def test_get_licenses_forwards_version(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_license(name="Apache", version=Version("2.0.0"))
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_licenses(version=Version("2.0.0"))
        self.assertEqual(len(results), 1)

    def test_get_runs_forwards_version(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.track.create_run(name="Versioned Run", version=Version("1.0.0"))
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_runs(version=Version("1.0.0"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Versioned Run")

    def test_get_datasets_forwards_version(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_dataset(name="Versioned Dataset", version=Version("1.0.0"))
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_datasets(version=Version("1.0.0"))
        self.assertEqual(len(results), 1)

    def test_get_inferences_forwards_version(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_inference(name="Versioned Inference")
        rmtc_sys.push()
        rmtc_sys.clear()
        # Inference itself carries no version - the filter must simply have
        # no matches rather than raising, confirming version= is accepted
        # even on categories that don't expose the property.
        results = rmtc_sys.get_inferences(version=Version("1.0.0"))
        self.assertEqual(len(results), 0)

    def test_version_filter_combines_with_instantiated_after(self):
        """version= and instantiated_after together narrow the same query - the
        two identity mechanisms are additive filters."""
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_resource(name="Early Alpha", version=Version("1.0.0"))
        rmtc_sys.push()
        boundary = Datetime()
        later = rmtc_sys.create_resource(name="Later Alpha", version=Version("1.0.0"))
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            categories=["Resource"],
            version=Version("1.0.0"),
            instantiated_after=boundary,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Later Alpha")

    def test_version_filter_combines_with_latest(self):
        rmtc_sys = self.get_system()
        rmtc_sys.delete_all()
        rmtc_sys.create_resource(name="First Match", version=Version("1.0.0"))
        rmtc_sys.push()
        rmtc_sys.create_resource(name="Second Match", version=Version("1.0.0"))
        rmtc_sys.push()
        rmtc_sys.create_resource(name="Different Version", version=Version("9.0.0"))
        rmtc_sys.push()
        rmtc_sys.clear()
        results = rmtc_sys.get_entities(
            categories=["Resource"], version=Version("1.0.0"), latest=True
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Second Match")