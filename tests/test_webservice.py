from pathlib import Path
from unittest import mock

import pytest
from twisted.web import error

from scrapyd.exceptions import DirectoryTraversalError
from scrapyd.interfaces import IEggStorage
from scrapyd.jobstorage import Job


def fake_list_jobs(*args, **kwargs):
    yield Job('proj1', 'spider-a', 'id1234')


def fake_list_spiders(*args, **kwargs):
    return []


def fake_list_spiders_other(*args, **kwarsg):
    return ['quotesbot', 'toscrape-css']


class TestWebservice:
    def add_test_version(self, root, basename, version):
        egg_path = Path(__file__).absolute().parent / f"{basename}.egg"
        project, version = 'myproject', version
        with open(egg_path, 'rb') as f:
            root.eggstorage.put(f, project, version)

    def test_list_spiders(self, txrequest, site_no_egg):
        self.add_test_version(site_no_egg, "mybot", "r1")
        self.add_test_version(site_no_egg, "mybot2", "r2")

        txrequest.args = {
            b'project': [b'myproject']
        }
        endpoint = b'listspiders.json'
        content = site_no_egg.children[endpoint].render_GET(txrequest)

        assert content['spiders'] == ['spider1', 'spider2', 'spider3']
        assert content['status'] == 'ok'

    def test_list_spiders_nonexistent(self, txrequest, site_no_egg):
        txrequest.args = {
            b'project': [b'nonexistent'],
        }
        endpoint = b'listspiders.json'

        with pytest.raises(error.Error) as exc:
            site_no_egg.children[endpoint].render_GET(txrequest)

        assert exc.value.status == b"200"
        assert exc.value.message == b"project 'nonexistent' not found"

    def test_list_spiders_version(self, txrequest, site_no_egg):
        self.add_test_version(site_no_egg, "mybot", "r1")
        self.add_test_version(site_no_egg, "mybot2", "r2")

        txrequest.args = {
            b'project': [b'myproject'],
            b'_version': [b'r1'],
        }
        endpoint = b'listspiders.json'
        content = site_no_egg.children[endpoint].render_GET(txrequest)

        assert content['spiders'] == ['spider1', 'spider2']
        assert content['status'] == 'ok'

    def test_list_spiders_version_nonexistent(self, txrequest, site_no_egg):
        self.add_test_version(site_no_egg, "mybot", "r1")
        self.add_test_version(site_no_egg, "mybot2", "r2")

        txrequest.args = {
            b'project': [b'myproject'],
            b'_version': [b'nonexistent'],
        }
        endpoint = b'listspiders.json'

        with pytest.raises(error.Error) as exc:
            site_no_egg.children[endpoint].render_GET(txrequest)

        assert exc.value.status == b"200"
        assert exc.value.message == b"version 'nonexistent' not found"

    def test_list_versions(self, txrequest, site_with_egg):
        txrequest.args = {
            b'project': [b'quotesbot'],
        }
        endpoint = b'listversions.json'
        content = site_with_egg.children[endpoint].render_GET(txrequest)

        assert content['versions'] == ['0_1']
        assert content['status'] == 'ok'

    def test_list_versions_nonexistent(self, txrequest, site_no_egg):
        txrequest.args = {
            b'project': [b'quotesbot'],
        }
        endpoint = b'listversions.json'
        content = site_no_egg.children[endpoint].render_GET(txrequest)

        assert content['versions'] == []
        assert content['status'] == 'ok'

    def test_list_projects(self, txrequest, site_with_egg):
        txrequest.args = {
            b'project': [b'quotesbot'],
            b'spider': [b'toscrape-css']
        }
        endpoint = b'listprojects.json'
        content = site_with_egg.children[endpoint].render_GET(txrequest)

        assert content['projects'] == ['quotesbot']

    def test_list_jobs(self, txrequest, site_with_egg):
        txrequest.args = {}
        endpoint = b'listjobs.json'
        content = site_with_egg.children[endpoint].render_GET(txrequest)

        assert set(content) == {'node_name', 'status', 'pending', 'running', 'finished'}

    @mock.patch('scrapyd.jobstorage.MemoryJobStorage.__iter__', new=fake_list_jobs)
    def test_list_jobs_finished(self, txrequest, site_with_egg):
        txrequest.args = {}
        endpoint = b'listjobs.json'
        content = site_with_egg.children[endpoint].render_GET(txrequest)

        assert set(content['finished'][0]) == {
            'project', 'spider', 'id', 'start_time', 'end_time', 'log_url', 'items_url'
        }

    def test_delete_version(self, txrequest, site_with_egg):
        endpoint = b'delversion.json'
        txrequest.args = {
            b'project': [b'quotesbot'],
            b'version': [b'0.1']
        }

        storage = site_with_egg.app.getComponent(IEggStorage)
        version, egg = storage.get('quotesbot')
        if egg:
            egg.close()

        content = site_with_egg.children[endpoint].render_POST(txrequest)
        no_version, no_egg = storage.get('quotesbot')
        if no_egg:
            no_egg.close()

        assert version is not None
        assert content['status'] == 'ok'
        assert 'node_name' in content
        assert no_version is None

    def test_delete_version_nonexistent_project(self, txrequest, site_with_egg):
        endpoint = b'delversion.json'
        txrequest.args = {
            b'project': [b'quotesbot'],
            b'version': [b'nonexistent']
        }

        with pytest.raises(error.Error) as exc:
            site_with_egg.children[endpoint].render_POST(txrequest)

        assert exc.value.status == b"200"
        assert exc.value.message == b"version 'nonexistent' not found"

    def test_delete_version_nonexistent_version(self, txrequest, site_no_egg):
        endpoint = b'delversion.json'
        txrequest.args = {
            b'project': [b'nonexistent'],
            b'version': [b'0.1']
        }

        with pytest.raises(error.Error) as exc:
            site_no_egg.children[endpoint].render_POST(txrequest)

        assert exc.value.status == b"200"
        assert exc.value.message == b"version '0.1' not found"

    def test_delete_project(self, txrequest, site_with_egg):
        endpoint = b'delproject.json'
        txrequest.args = {
            b'project': [b'quotesbot'],
        }

        storage = site_with_egg.app.getComponent(IEggStorage)
        version, egg = storage.get('quotesbot')
        if egg:
            egg.close()

        content = site_with_egg.children[endpoint].render_POST(txrequest)
        no_version, no_egg = storage.get('quotesbot')
        if no_egg:
            no_egg.close()

        assert version is not None
        assert content['status'] == 'ok'
        assert 'node_name' in content
        assert no_version is None

    def test_delete_project_nonexistent(self, txrequest, site_no_egg):
        endpoint = b'delproject.json'
        txrequest.args = {
            b'project': [b'nonexistent'],
        }

        with pytest.raises(error.Error) as exc:
            site_no_egg.children[endpoint].render_POST(txrequest)

        assert exc.value.status == b"200"
        assert exc.value.message == b"project 'nonexistent' not found"

    def test_addversion(self, txrequest, site_no_egg):
        endpoint = b'addversion.json'
        txrequest.args = {
            b'project': [b'quotesbot'],
            b'version': [b'0.1']
        }
        egg_path = Path(__file__).absolute().parent / "quotesbot.egg"
        with open(egg_path, 'rb') as f:
            txrequest.args[b'egg'] = [f.read()]

        storage = site_no_egg.app.getComponent(IEggStorage)
        version, egg = storage.get('quotesbot')
        if egg:
            egg.close()

        content = site_no_egg.children[endpoint].render_POST(txrequest)
        no_version, no_egg = storage.get('quotesbot')
        if no_egg:
            no_egg.close()

        assert version is None
        assert content['status'] == 'ok'
        assert 'node_name' in content
        assert no_version == '0_1'

    def test_schedule(self, txrequest, site_with_egg):
        endpoint = b'schedule.json'
        txrequest.args = {
            b'project': [b'quotesbot'],
            b'spider': [b'toscrape-css']
        }

        content = site_with_egg.children[endpoint].render_POST(txrequest)

        assert site_with_egg.scheduler.calls == [['quotesbot', 'toscrape-css']]
        assert content['status'] == 'ok'
        assert 'jobid' in content

    def test_schedule_nonexistent_project(self, txrequest, site_no_egg):
        endpoint = b'schedule.json'
        txrequest.args = {
            b'project': [b'nonexistent'],
            b'spider': [b'toscrape-css']
        }

        with pytest.raises(error.Error) as exc:
            site_no_egg.children[endpoint].render_POST(txrequest)

        assert exc.value.status == b"200"
        assert exc.value.message == b"project 'nonexistent' not found"

    def test_schedule_nonexistent_version(self, txrequest, site_with_egg):
        endpoint = b'schedule.json'
        txrequest.args = {
            b'project': [b'quotesbot'],
            b'_version': [b'nonexistent'],
            b'spider': [b'toscrape-css']
        }

        with pytest.raises(error.Error) as exc:
            site_with_egg.children[endpoint].render_POST(txrequest)

        assert exc.value.status == b"200"
        assert exc.value.message == b"version 'nonexistent' not found"

    def test_schedule_nonexistent_spider(self, txrequest, site_with_egg):
        endpoint = b'schedule.json'
        txrequest.args = {
            b'project': [b'quotesbot'],
            b'spider': [b'nonexistent']
        }

        with pytest.raises(error.Error) as exc:
            site_with_egg.children[endpoint].render_POST(txrequest)

        assert exc.value.status == b"200"
        assert exc.value.message == b"spider 'nonexistent' not found"

    @pytest.mark.parametrize('endpoint,attach_egg,method', [
        (b'addversion.json', True, 'render_POST'),
        (b'listversions.json', False, 'render_GET'),
        (b'delproject.json', False, 'render_POST'),
        (b'delversion.json', False, 'render_POST'),
    ])
    def test_project_directory_traversal(self, txrequest, site_no_egg, endpoint, attach_egg, method):
        txrequest.args = {
            b'project': [b'../p'],
            b'version': [b'0.1'],
        }

        if attach_egg:
            egg_path = Path(__file__).absolute().parent / "quotesbot.egg"
            with open(egg_path, 'rb') as f:
                txrequest.args[b'egg'] = [f.read()]

        with pytest.raises(DirectoryTraversalError) as exc:
            getattr(site_no_egg.children[endpoint], method)(txrequest)

        assert str(exc.value) == "../p"

        storage = site_no_egg.app.getComponent(IEggStorage)
        version, egg = storage.get('quotesbot')
        if egg:
            egg.close()

        assert version is None

    @pytest.mark.parametrize('endpoint,attach_egg,method', [
        (b'schedule.json', False, 'render_POST'),
        (b'listspiders.json', False, 'render_GET'),
    ])
    def test_project_directory_traversal_runner(self, txrequest, site_no_egg, endpoint, attach_egg, method):
        txrequest.args = {
            b'project': [b'../p'],
            b'spider': [b's'],
        }

        if attach_egg:
            egg_path = Path(__file__).absolute().parent / "quotesbot.egg"
            with open(egg_path, 'rb') as f:
                txrequest.args[b'egg'] = [f.read()]

        with pytest.raises(DirectoryTraversalError) as exc:
            getattr(site_no_egg.children[endpoint], method)(txrequest)

        assert str(exc.value) == "../p"

        storage = site_no_egg.app.getComponent(IEggStorage)
        version, egg = storage.get('quotesbot')
        if egg:
            egg.close()

        assert version is None
