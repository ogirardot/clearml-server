from apierrors.errors.bad_request import InvalidModelId
from config import config
from tests.automated import TestService


log = config.logger(__file__)


class TestTasksEdit(TestService):
    def setUp(self, **kwargs):
        super().setUp(version=2.5)

    def new_task(self, **kwargs):
        return self.create_temp(
            "tasks", type="testing", name="test", input=dict(view=dict()), **kwargs
        )

    def new_model(self):
        return self.create_temp("models", name="test", uri="file:///a/b", labels={})

    def test_edit_model_ready(self):
        task = self.new_task()
        model = self.new_model()
        self.api.tasks.edit(task=task, execution=dict(model=model))

    def test_edit_model_not_ready(self):
        task = self.new_task()
        model = self.new_model()
        self.api.models.edit(model=model, ready=False)
        self.assertFalse(self.api.models.get_by_id(model=model).model.ready)
        self.api.tasks.edit(task=task, execution=dict(model=model))

    def test_edit_had_model_model_not_ready(self):
        ready_model = self.new_model()
        self.assert_(self.api.models.get_by_id(model=ready_model).model.ready)
        task = self.new_task(execution=dict(model=ready_model))
        not_ready_model = self.new_model()
        self.api.models.edit(model=not_ready_model, ready=False)
        self.assertFalse(self.api.models.get_by_id(model=not_ready_model).model.ready)
        self.api.tasks.edit(task=task, execution=dict(model=not_ready_model))

    def test_task_with_model_reset(self):
        # on task reset output model deleted
        task = self.new_task()
        self.api.tasks.started(task=task)
        model_id = self.api.models.update_for_task(task=task, uri="file:///b")["id"]
        self.api.tasks.reset(task=task)
        with self.api.raises(InvalidModelId):
            self.api.models.get_by_id(model=model_id)

        # unless it is input of some task
        task = self.new_task()
        self.api.tasks.started(task=task)
        model_id = self.api.models.update_for_task(task=task, uri="file:///b")["id"]
        task_2 = self.new_task(execution=dict(model=model_id))
        self.api.tasks.reset(task=task)
        self.api.models.get_by_id(model=model_id)

    def test_clone_task(self):
        script = dict(
            binary="python",
            requirements=dict(pip=["six"]),
            repository="https://example.come/foo/bar",
            entry_point="test.py",
            diff="foo",
        )
        execution = dict(parameters=dict(test="Test"))
        tags = ["hello"]
        system_tags = ["development", "test"]
        task = self.new_task(
            script=script, execution=execution, tags=tags, system_tags=system_tags
        )

        new_name = "new test"
        new_tags = ["by"]
        execution_overrides = dict(framework="Caffe")
        new_task_id = self._clone_task(
            task=task,
            new_task_name=new_name,
            new_task_tags=new_tags,
            execution_overrides=execution_overrides,
            new_task_parent=task,
        )
        new_task = self.api.tasks.get_by_id(task=new_task_id).task
        self.assertEqual(new_task.name, new_name)
        self.assertEqual(new_task.type, "testing")
        self.assertEqual(new_task.tags, new_tags)
        self.assertEqual(new_task.status, "created")
        self.assertEqual(new_task.script, script)
        self.assertEqual(new_task.parent, task)
        self.assertEqual(new_task.execution.parameters, execution["parameters"])
        self.assertEqual(new_task.execution.framework, execution_overrides["framework"])
        self.assertEqual(new_task.system_tags, [])

    def test_model_check_in_clone(self):
        model = self.new_model()
        task = self.new_task(execution=dict(model=model))

        # task with deleted model still can be copied
        self.api.models.delete(model=model, force=True)
        self._clone_task(task=task, new_task_name="clone test")

        # unless check for refs is done
        with self.api.raises(InvalidModelId):
            self._clone_task(
                task=task, new_task_name="clone test2", validate_references=True
            )

        # if the model is overriden then it is always checked
        with self.api.raises(InvalidModelId):
            self._clone_task(
                task=task,
                new_task_name="clone test3",
                execution_overrides=dict(model="not existing"),
            )

    def _clone_task(self, task, **kwargs):
        new_task = self.api.tasks.clone(task=task, **kwargs).id
        self.defer(
            self.api.tasks.delete, task=new_task, move_to_trash=False, force=True
        )
        return new_task
