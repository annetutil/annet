import os
from functools import partial
from unittest import mock

from annet.parallel import pool_worker, Parallel, PoolWorkerTask, PoolWorkerTaskType
import pytest
import multiprocessing as mp


@pytest.fixture
def parallel(worker):
    return Parallel(worker)


class TestTruncateTraceback:
    @pytest.fixture
    def worker(self):
        def inner(*_, **__):
            1 / 0

        return inner

    @pytest.mark.parametrize("flag", [0, 1])
    def test_trancate(self, flag, parallel):
        with mock.patch.object(os, "environ", new={"ANN_TRUNCATE_TRACEBACK": f"{flag}"}):
            task_queue = mp.Queue()
            done_queue = mp.Queue()

            task_queue.put_nowait(PoolWorkerTask(PoolWorkerTaskType.INVOKE))
            task_queue.put_nowait(PoolWorkerTask(PoolWorkerTaskType.STOP))

            pool_worker(parallel, 0, task_queue, done_queue, {})
            _, __, ___, exc = done_queue.get()

            tb_lines = list(
                filter(
                    lambda x: x.startswith("File"),
                    map(str.strip, exc.formatted_output.split("\n"))
                )
            )

            assert len(tb_lines) == (1 if flag else 3), tb_lines
