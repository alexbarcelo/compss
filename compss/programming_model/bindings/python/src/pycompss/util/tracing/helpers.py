#!/usr/bin/python
#
#  Copyright 2002-2021 Barcelona Supercomputing Center (www.bsc.es)
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

# -*- coding: utf-8 -*-

"""
PyCOMPSs Tracing helpers
=========================
    This file contains a set of context managers and decorators to ease the
    tracing events emission.
"""
import time
from contextlib import contextmanager
from pycompss.util.context import in_master
from pycompss.util.context import in_worker
from pycompss.worker.commons.constants import SYNC_EVENTS
from pycompss.worker.commons.constants import TASK_EVENTS
from pycompss.worker.commons.constants import TASK_CPU_AFFINITY_EVENTS
from pycompss.worker.commons.constants import TASK_CPU_NUMBER_EVENTS
from pycompss.worker.commons.constants import TASK_GPU_AFFINITY_EVENTS
from pycompss.worker.commons.constants import WORKER_EVENTS
from pycompss.worker.commons.constants import WORKER_RUNNING_EVENT
from pycompss.runtime.constants import MASTER_EVENTS

PYEXTRAE = None
TRACING = False


@contextmanager
def dummy_context():
    # type: () -> None
    """ Context which deactivates the tracing flag and nothing else.

    :return: None
    """
    global TRACING
    TRACING = False
    yield


@contextmanager
def trace_multiprocessing_worker():
    # type: () -> None
    """ Sets up the tracing for the multiprocessing worker.

    :return: None
    """
    global PYEXTRAE
    global TRACING
    import pyextrae.multiprocessing as pyextrae  # noqa
    PYEXTRAE = pyextrae
    TRACING = True
    pyextrae.eventandcounters(SYNC_EVENTS, 1)
    pyextrae.eventandcounters(WORKER_EVENTS, WORKER_RUNNING_EVENT)
    yield  # here the worker runs
    pyextrae.eventandcounters(WORKER_EVENTS, 0)
    pyextrae.eventandcounters(SYNC_EVENTS, 0)
    pyextrae.eventandcounters(SYNC_EVENTS, int(time.time()))
    pyextrae.eventandcounters(SYNC_EVENTS, 0)


@contextmanager
def trace_mpi_worker():
    # type: () -> None
    """ Sets up the tracing for the mpi worker.

    :return: None
    """
    global PYEXTRAE
    global TRACING
    import pyextrae.mpi as pyextrae  # noqa
    PYEXTRAE = pyextrae
    TRACING = True
    pyextrae.eventandcounters(SYNC_EVENTS, 1)
    pyextrae.eventandcounters(WORKER_EVENTS, WORKER_RUNNING_EVENT)
    yield  # here the worker runs
    pyextrae.eventandcounters(WORKER_EVENTS, 0)
    pyextrae.eventandcounters(SYNC_EVENTS, 0)
    pyextrae.eventandcounters(SYNC_EVENTS, int(time.time()))
    pyextrae.eventandcounters(SYNC_EVENTS, 0)


@contextmanager
def trace_mpi_executor():
    # type: () -> None
    """ Sets up the tracing for each mpi executor.

    :return: None
    """
    global PYEXTRAE
    global TRACING
    import pyextrae.mpi as pyextrae  # noqa
    PYEXTRAE = pyextrae
    TRACING = True
    yield  # here the mpi executor runs


class emit_event(object):  # noqa

    def __init__(self,
                 event_id,            # type: int
                 master=False,        # type: bool
                 inside=False,        # type: bool
                 cpu_affinity=False,  # type: bool
                 gpu_affinity=False   # type: bool
                 ):                   # type: (...) -> None
        self.event_id = event_id
        self.master = master
        self.inside = inside
        self.cpu_affinity = cpu_affinity
        self.gpu_affinity = gpu_affinity

    def __call__(self, f):
        def wrapped_f(*args, **kwargs):
            if TRACING:
                with event(self.event_id, self.master,
                           self.inside, self.cpu_affinity, self.gpu_affinity):
                    result = f(*args, **kwargs)
            else:
                result = f(*args, **kwargs)
            return result

        return wrapped_f


@contextmanager
def event(event_id, master=False, inside=False,
          cpu_affinity=False, gpu_affinity=False, cpu_number=False):
    # type: (int or str, bool, bool, bool, bool, bool) -> None
    """ Emits an event wrapping the desired code.

    Does nothing if tracing is disabled.

    :param event_id: Event identifier to emit.
    :param master: If the event is emitted as master.
    :param inside: If the event is produced inside the worker.
    :param cpu_affinity: If the event is produced inside the worker for
                         cpu affinity.
    :param gpu_affinity: If the event is produced inside the worker for
                         gpu affinity.
    :param cpu_number: If the event is produced inside the worker for
                       cpu number.
    :return: None
    """
    emit = False
    if TRACING and in_master() and master:
        emit = True
    if TRACING and in_worker() and not master:
        emit = True
    if emit:
        event_group, event_id = __get_proper_type_event__(event_id,
                                                          master,
                                                          inside,
                                                          cpu_affinity,
                                                          gpu_affinity,
                                                          cpu_number)
        PYEXTRAE.eventandcounters(event_group, event_id)  # noqa
    yield  # here the code runs
    if emit:
        PYEXTRAE.eventandcounters(event_group, 0)         # noqa


def emit_manual_event(event_id, master=False, inside=False,
                      cpu_affinity=False, gpu_affinity=False,
                      cpu_number=False):
    # type: (int or str, bool, bool, bool, bool, bool) -> (int, int)
    """ Emits a single event with the desired code.

    Does nothing if tracing is disabled.

    :param event_id: Event identifier to emit.
    :param master: If the event is emitted as master.
    :param inside: If the event is produced inside the worker.
    :param cpu_affinity: If the event is produced inside the worker for
                         cpu affinity.
    :param gpu_affinity: If the event is produced inside the worker for
                         gpu affinity.
    :param cpu_number: If the event is produced inside the worker for
                       cpu number.
    :return: None
    """
    if TRACING:
        event_group, event_id = __get_proper_type_event__(event_id,
                                                          master,
                                                          inside,
                                                          cpu_affinity,
                                                          gpu_affinity,
                                                          cpu_number)
        PYEXTRAE.eventandcounters(event_group, event_id)  # noqa


def emit_manual_event_explicit(event_group, event_id):
    # type: (int, int) -> None
    """ Emits a single event with the desired code.

    Does nothing if tracing is disabled.

    :param event_id: Event identifier to emit.
    :param master: If the event is emitted as master.
    :param inside: If the event is produced inside the worker.
    :param cpu_affinity: If the event is produced inside the worker for
                         cpu affinity.
    :param gpu_affinity: If the event is produced inside the worker for
                         gpu affinity.
    :return: None
    """
    if TRACING:
        PYEXTRAE.eventandcounters(event_group, event_id)  # noqa


def __get_proper_type_event__(event_id, master, inside,
                              cpu_affinity, gpu_affinity, cpu_number):
    # type: (int or str, bool, bool, bool, bool, bool) -> (int, int)
    """ Parses the flags to retrieve the appropriate event_group.
    It also parses the event_id in case of affinity since it is received
    as string.

    :param event_id: Event identifier to emit.
    :param master: If the event is emitted as master.
    :param inside: If the event is produced inside the worker.
    :param cpu_affinity: If the event is produced inside the worker for
                         cpu affinity.
    :param gpu_affinity: If the event is produced inside the worker for
                         gpu affinity.
    :param cpu_number: If the event is produced inside the worker for
                       cpu number.
    :return: Retrieves the appropriate event_group and event_id
    """
    if master:
        event_group = MASTER_EVENTS
    else:
        if inside:
            if cpu_affinity:
                event_group = TASK_CPU_AFFINITY_EVENTS
                event_id = __parse_affinity_event_id__(event_id)
            elif gpu_affinity:
                event_group = TASK_GPU_AFFINITY_EVENTS
                event_id = __parse_affinity_event_id__(event_id)
            elif cpu_number:
                event_group = TASK_CPU_NUMBER_EVENTS
                event_id = int(event_id)
            else:
                event_group = TASK_EVENTS
        else:
            event_group = WORKER_EVENTS
    return event_group, event_id


def __parse_affinity_event_id__(event_id):
    # type: (int or str) -> int
    """ Parses the affinity event identifier.

    :param event_id: Event identifier
    :return: The parsed event identifier as integer
    """
    if isinstance(event_id, str):
        try:
            event_id = int(event_id)
        except ValueError:
            # The event_id is a string with multiple cores
            # Get only the first core
            event_id = int(event_id.split(',')[0].split('-')[0])
        event_id += 1  # since it starts with 0
    return event_id


def enable_trace_master():
    # type: () -> None
    """ Enables tracing for the master process.

    :return: None
    """
    global PYEXTRAE
    global TRACING
    import pyextrae.sequential as pyextrae  # noqa
    PYEXTRAE = pyextrae
    TRACING = True
