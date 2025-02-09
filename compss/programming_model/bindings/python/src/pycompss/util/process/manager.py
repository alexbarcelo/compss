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
PyCOMPSs Util - process/manager
============================================
    This file centralizes the multiprocessing management. It helps to
    homogenize the behaviour between linux and mac.

runtime/management/link.py:import multiprocessing----------------------------------------------------
runtime/management/link.py:LINK_PROCESS = multiprocessing.Process()----------------------------------------------------
runtime/management/link.py:IN_QUEUE = multiprocessing.Queue()----------------------------------------------------
runtime/management/link.py:OUT_QUEUE = multiprocessing.Queue()----------------------------------------------------
runtime/management/link.py:        IN_QUEUE = multiprocessing.Queue()----------------------------------------------------
runtime/management/link.py:        OUT_QUEUE = multiprocessing.Queue()----------------------------------------------------
runtime/management/link.py:    LINK_PROCESS = multiprocessing.Process(target=c_extension_link,----------------------------------------------------

tests/runtime/test_link.py:from multiprocessing import Queue----------------------------------------------------

tests/worker/common_piper_tester.py:import multiprocessing----------------------------------------------------
tests/worker/common_piper_tester.py:    worker = multiprocessing.Process(----------------------------------------------------

tests/streams/test_distro_stream_client.py:from multiprocessing import Process----------------------------------------------------

worker/piper/cache/tracker.py:    from multiprocessing.shared_memory import SharedMemory    # noqa----------------------------------------------------
worker/piper/cache/tracker.py:    from multiprocessing.shared_memory import ShareableList   # noqa----------------------------------------------------
worker/piper/cache/tracker.py:    from multiprocessing.managers import SharedMemoryManager  # noqa----------------------------------------------------
worker/piper/cache/setup.py:from multiprocessing import Process----------------------------------------------------
worker/piper/cache/setup.py:from multiprocessing import Queue----------------------------------------------------
worker/piper/cache/setup.py:    from multiprocessing import Manager----------------------------------------------------
worker/piper/piper_worker.py:from multiprocessing import Process----------------------------------------------------
worker/piper/piper_worker.py:from multiprocessing import Queue----------------------------------------------------
"""

import multiprocessing
from multiprocessing import Queue    # Used only for typing
from multiprocessing import Process  # Used only for typing
try:
    from multiprocessing import Manager
    from multiprocessing.shared_memory import SharedMemory    # noqa
    from multiprocessing.shared_memory import ShareableList   # noqa
    from multiprocessing.managers import SharedMemoryManager  # noqa
except ImportError:
    # Unsupported in python < 3.8
    Manager = None
    SharedMemory = None
    ShareableList = None
    SharedMemoryManager = None


def initialize_multiprocessing():
    # type: () -> None
    """ Set global mechanism to start multiprocessing processes.
    https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods  # noqa: E501
    Using fork even in MacOS.

    WARNING: This method must be called only once and at the very beginning.

    :return: None
    """
    try:
        multiprocessing.set_start_method("fork")
    except AttributeError:
        # Unsupported set_start_method (python 2 mainly).
        # Use default start method.
        pass
    except RuntimeError:
        # Already initialized
        pass


def new_process():
    # type: () -> Process
    """ Instantiate a new empty process.

    :return: Empty process
    """
    return multiprocessing.Process()


def new_queue():
    # type: () -> Queue
    """ Instantiate a new queue.

    :return: New queue
    """
    return multiprocessing.Queue()


def new_manager():
    # type: () -> Manager
    """ Instantiate a new empty multiprocessing manager.

    :return: Empty multiprocessing manager
    """
    return Manager()


def create_process(target, args=()):
    # type: (..., tuple) -> Process
    """ Create a new process instance for the given target with the provided
    arguments.

    :param target: Target function to execute in a multiprocessing process
    :param args: Target function arguments
    :return: New process
    """
    process = multiprocessing.Process(target=target,
                                      args=args)
    return process


def create_shared_memory_manager(address, authkey):
    # type: ((str, str), str) -> SharedMemoryManager
    """ Create a new shared memory manager process at the given address with
    the provided authkey.

    :param address: Shared memory manager address (IP, PORT)
    :param authkey: Shared memory manager authentication key
    :return: New process
    """
    smm = SharedMemoryManager(address=address,
                              authkey=authkey)
    return smm
