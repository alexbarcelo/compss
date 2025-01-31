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
PyCOMPSs Binding - Interactive API
==================================
    Provides the current start and stop for the use of PyCOMPSs interactively.
"""

import os
import sys
import logging
import time
import tempfile

import pycompss.util.context as context
import pycompss.util.interactive.helpers as interactive_helpers
from pycompss.runtime.binding import get_log_path
from pycompss.runtime.management.object_tracker import OT_is_pending_to_synchronize        # noqa: E501
from pycompss.runtime.management.object_tracker import OT_clean_object_tracker
from pycompss.runtime.management.classes import Future
from pycompss.runtime.commons import DEFAULT_SCHED
from pycompss.runtime.commons import DEFAULT_CONN
from pycompss.runtime.commons import DEFAULT_JVM_WORKERS
from pycompss.runtime.commons import RUNNING_IN_SUPERCOMPUTER
from pycompss.runtime.commons import INTERACTIVE_FILE_NAME
from pycompss.runtime.commons import set_temporary_directory
from pycompss.util.environment.configuration import export_current_flags
from pycompss.util.environment.configuration import prepare_environment
from pycompss.util.environment.configuration import prepare_loglevel_graph_for_monitoring  # noqa: E501
from pycompss.util.environment.configuration import updated_variables_in_sc
from pycompss.util.environment.configuration import prepare_tracing_environment
from pycompss.util.environment.configuration import check_infrastructure_variables         # noqa: E501
from pycompss.util.environment.configuration import create_init_config_file
from pycompss.util.logger.helpers import get_logging_cfg_file
from pycompss.util.logger.helpers import init_logging
from pycompss.util.interactive.events import setup_event_manager
from pycompss.util.interactive.events import release_event_manager
from pycompss.util.interactive.flags import check_flags
from pycompss.util.interactive.flags import print_flag_issues
from pycompss.util.interactive.utils import parameters_to_dict
from pycompss.util.interactive.outwatcher import STDW
from pycompss.util.interactive.graphs import show_graph
from pycompss.util.interactive.state import show_tasks_info
from pycompss.util.interactive.state import show_tasks_status
from pycompss.util.interactive.state import show_statistics
from pycompss.util.interactive.state import show_resources_status
from pycompss.util.interactive.state import check_monitoring_file
from pycompss.util.process.manager import initialize_multiprocessing

# Tracing imports
from pycompss.util.tracing.helpers import emit_manual_event
from pycompss.runtime.constants import APPLICATION_RUNNING_EVENT

# Storage imports
from pycompss.util.storages.persistent import master_init_storage
from pycompss.util.storages.persistent import master_stop_storage

# Streaming imports
from pycompss.streams.environment import init_streaming
from pycompss.streams.environment import stop_streaming


# GLOBAL VARIABLES
APP_PATH = INTERACTIVE_FILE_NAME
PERSISTENT_STORAGE = False
STREAMING = False
LOG_PATH = tempfile.mkdtemp()
GRAPHING = False
LINE_SEPARATOR = "********************************************************"


# Initialize multiprocessing
initialize_multiprocessing()


def start(log_level="off",                     # type: str
          debug=False,                         # type: bool
          o_c=False,                           # type: bool
          graph=False,                         # type: bool
          trace=False,                         # type: bool
          monitor=None,                        # type: int
          project_xml=None,                    # type: str
          resources_xml=None,                  # type: str
          summary=False,                       # type: bool
          task_execution="compss",             # type: str
          storage_impl=None,                   # type: str
          storage_conf="null",                 # type: str
          streaming_backend=None,              # type: str
          streaming_master_name=None,          # type: str
          streaming_master_port=None,          # type: str
          task_count=50,                       # type: int
          app_name=INTERACTIVE_FILE_NAME,      # type: str
          uuid=None,                           # type: str
          base_log_dir=None,                   # type: str
          specific_log_dir=None,               # type: str
          extrae_cfg=None,                     # type: str
          comm="NIO",                          # type: str
          conn=DEFAULT_CONN,                   # type: str
          master_name="",                      # type: str
          master_port="",                      # type: str
          scheduler=DEFAULT_SCHED,             # type: str
          jvm_workers=DEFAULT_JVM_WORKERS,     # type: str
          cpu_affinity="automatic",            # type: str
          gpu_affinity="automatic",            # type: str
          fpga_affinity="automatic",           # type: str
          fpga_reprogram="",                   # type: str
          profile_input="",                    # type: str
          profile_output="",                   # type: str
          scheduler_config="",                 # type: str
          external_adaptation=False,           # type: bool
          propagate_virtual_environment=True,  # type: bool
          mpi_worker=False,                    # type: bool
          worker_cache=False,                  # type: bool or str
          shutdown_in_node_failure=False,      # type: bool
          io_executors=0,                      # type: int
          env_script="",                       # type: str
          reuse_on_block=True,                 # type: bool
          nested_enabled=False,                # type: bool
          tracing_task_dependencies=False,     # type: bool
          trace_label=None,                    # type: str
          extrae_cfg_python=None,              # type: str
          wcl=0,                               # type: int
          cache_profiler=False,                # type: bool
          verbose=False                        # type: bool
          ):  # NOSONAR
    # type: (...) -> None
    """ Start the runtime in interactive mode.

    :param log_level: Logging level [ "trace"|"debug"|"info"|"api"|"off" ]
                      (default: "off")
    :param debug: Debug mode [ True | False ]
                  (default: False) (overrides log-level)
    :param o_c: Objects to string conversion [ True|False ]
                (default: False)
    :param graph: Generate graph [ True|False ]
                  (default: False)
    :param trace: Generate trace [ True|False|"scorep"|"arm-map"|"arm-ddt" ]
                  (default: False)
    :param monitor: Monitor refresh rate
                    (default: None)
    :param project_xml: Project xml file path
                        (default: None)
    :param resources_xml: Resources xml file path
                          (default: None)
    :param summary: Execution summary [ True | False ]
                    (default: False)
    :param task_execution: Task execution
                           (default: "compss")
    :param storage_impl: Storage implementation path
                         (default: None)
    :param storage_conf: Storage configuration file path
                         (default: None)
    :param streaming_backend: Streaming backend
                              (default: None)
    :param streaming_master_name: Streaming master name
                                  (default: None)
    :param streaming_master_port: Streaming master port
                                  (default: None)
    :param task_count: Task count
                       (default: 50)
    :param app_name: Application name
                     default: INTERACTIVE_FILE_NAME)
    :param uuid: UUId
                 (default: None)
    :param base_log_dir: Base logging directory
                         (default: None)
    :param specific_log_dir: Specific logging directory
                             (default: None)
    :param extrae_cfg: Extrae configuration file path
                       (default: None)
    :param comm: Communication library
                 (default: NIO)
    :param conn: Connector
                 (default: DefaultSSHConnector)
    :param master_name: Master Name
                        (default: "")
    :param master_port: Master port
                        (default: "")
    :param scheduler: Scheduler (see runcompss)
                      (default: es.bsc.compss.scheduler.loadbalancing.LoadBalancingScheduler)  # noqa: E501
    :param jvm_workers: Java VM parameters
                        (default: "-Xms1024m,-Xmx1024m,-Xmn400m")
    :param cpu_affinity: CPU Core affinity
                         (default: "automatic")
    :param gpu_affinity: GPU affinity
                         (default: "automatic")
    :param fpga_affinity: FPGA affinity
                          (default: "automatic")
    :param fpga_reprogram: FPGA repogram command
                           (default: "")
    :param profile_input: Input profile
                          (default: "")
    :param profile_output: Output profile
                           (default: "")
    :param scheduler_config: Scheduler configuration
                             (default: "")
    :param external_adaptation: External adaptation [ True|False ]
                                (default: False)
    :param propagate_virtual_environment: Propagate virtual environment [ True|False ]  # noqa: E501
                                          (default: False)
    :param mpi_worker: Use the MPI worker [ True|False ]
                       (default: False)
    :param worker_cache: Use the worker cache [ True | int(size) | False]
                         (default: False)
    :param shutdown_in_node_failure: Shutdown in node failure [ True | False]
                                     (default: False)
    :param io_executors: <Integer> Number of IO executors
    :param env_script: <String> Environment script to be sourced in workers
    :param reuse_on_block: Reuse on block [ True | False]
                           (default: True)
    :param nested_enabled: Nested enabled [ True | False]
                           (default: True)
    :param tracing_task_dependencies: Include task dependencies in trace
                                      [ True | False] (default: False)
    :param trace_label: <String> Add trace label
    :param extrae_cfg_python: <String> Extrae configuration file for the
                              workers
    :param wcl: <Integer> Wall clock limit. Stops the runtime if reached.
                0 means forever.
    :param cache_profiler: Use the cache profiler [ True | False]
                         (default: False)
    :param verbose: Verbose mode [ True|False ]
                    (default: False)
    :return: None
    """
    # Export global variables
    global GRAPHING

    if context.in_pycompss():
        print("The runtime is already running")
        return None

    GRAPHING = graph
    __export_globals__()

    interactive_helpers.DEBUG = debug
    if debug:
        log_level = "debug"

    __show_flower__()

    # Let the Python binding know we are at master
    context.set_pycompss_context(context.MASTER)
    # Then we can import the appropriate start and stop functions from the API
    from pycompss.api.api import compss_start

    ##############################################################
    # INITIALIZATION
    ##############################################################

    # Initial dictionary with the user defined parameters
    all_vars = parameters_to_dict(log_level,
                                  debug,
                                  o_c,
                                  graph,
                                  trace,
                                  monitor,
                                  project_xml,
                                  resources_xml,
                                  summary,
                                  task_execution,
                                  storage_impl,
                                  storage_conf,
                                  streaming_backend,
                                  streaming_master_name,
                                  streaming_master_port,
                                  task_count,
                                  app_name,
                                  uuid,
                                  base_log_dir,
                                  specific_log_dir,
                                  extrae_cfg,
                                  comm,
                                  conn,
                                  master_name,
                                  master_port,
                                  scheduler,
                                  jvm_workers,
                                  cpu_affinity,
                                  gpu_affinity,
                                  fpga_affinity,
                                  fpga_reprogram,
                                  profile_input,
                                  profile_output,
                                  scheduler_config,
                                  external_adaptation,
                                  propagate_virtual_environment,
                                  mpi_worker,
                                  worker_cache,
                                  shutdown_in_node_failure,
                                  io_executors,
                                  env_script,
                                  reuse_on_block,
                                  nested_enabled,
                                  tracing_task_dependencies,
                                  trace_label,
                                  extrae_cfg_python,
                                  wcl,
                                  cache_profiler)
    # Save all vars in global current flags so that events.py can restart
    # the notebook with the same flags
    export_current_flags(all_vars)

    # Check the provided flags
    flags, issues = check_flags(all_vars)
    if not flags:
        print_flag_issues(issues)
        return None

    # Prepare the environment
    env_vars = prepare_environment(True, o_c, storage_impl,
                                   "undefined", debug, trace, mpi_worker)
    all_vars.update(env_vars)

    # Update the log level and graph values if monitoring is enabled
    monitoring_vars = prepare_loglevel_graph_for_monitoring(monitor,
                                                            graph,
                                                            debug,
                                                            log_level)
    all_vars.update(monitoring_vars)

    # Check if running in supercomputer and update the variables accordingly
    # with the defined in the launcher and exported in environment variables.
    if RUNNING_IN_SUPERCOMPUTER:
        updated_vars = updated_variables_in_sc()
        if verbose:
            print("- Overridden project xml with: %s" %
                  updated_vars["project_xml"])
            print("- Overridden resources xml with: %s" %
                  updated_vars["resources_xml"])
            print("- Overridden master name with: %s" %
                  updated_vars["master_name"])
            print("- Overridden master port with: %s" %
                  updated_vars["master_port"])
            print("- Overridden uuid with: %s" %
                  updated_vars["uuid"])
            print("- Overridden base log dir with: %s" %
                  updated_vars["base_log_dir"])
            print("- Overridden specific log dir with: %s" %
                  updated_vars["specific_log_dir"])
            print("- Overridden storage conf with: %s" %
                  updated_vars["storage_conf"])
            print("- Overridden log level with: %s" %
                  str(updated_vars["log_level"]))
            print("- Overridden debug with: %s" %
                  str(updated_vars["debug"]))
            print("- Overridden trace with: %s" %
                  str(updated_vars["trace"]))
        all_vars.update(updated_vars)

    # Update the tracing environment if set and set the appropriate trace
    # integer value
    tracing_vars = prepare_tracing_environment(all_vars["trace"],
                                               all_vars["extrae_lib"],
                                               all_vars["ld_library_path"])
    all_vars["trace"], all_vars["ld_library_path"] = tracing_vars

    # Update the infrastructure variables if necessary
    inf_vars = check_infrastructure_variables(all_vars["project_xml"],
                                              all_vars["resources_xml"],
                                              all_vars["compss_home"],
                                              all_vars["app_name"],
                                              all_vars["file_name"],
                                              all_vars["external_adaptation"])
    all_vars.update(inf_vars)

    # With all this information, create the configuration file for the
    # runtime start
    create_init_config_file(**all_vars)

    # Start the event manager (ipython hooks)
    ipython = globals()['__builtins__']['get_ipython']()
    setup_event_manager(ipython)

    ##############################################################
    # RUNTIME START
    ##############################################################

    print("* - Starting COMPSs runtime...                         *")
    sys.stdout.flush()  # Force flush
    compss_start(log_level, all_vars["trace"], True)

    global LOG_PATH
    LOG_PATH = get_log_path()
    set_temporary_directory(LOG_PATH)
    print("* - Log path : " + LOG_PATH)

    # Setup logging
    binding_log_path = get_log_path()
    log_path = os.path.join(all_vars["compss_home"],
                            "Bindings",
                            "python",
                            str(all_vars["major_version"]),
                            "log")
    set_temporary_directory(binding_log_path)
    logging_cfg_file = get_logging_cfg_file(log_level)
    init_logging(os.path.join(log_path, logging_cfg_file), binding_log_path)
    logger = logging.getLogger("pycompss.runtime.launch")

    __print_setup__(verbose, all_vars)

    logger.debug("--- START ---")
    logger.debug("PyCOMPSs Log path: %s" % LOG_PATH)

    logger.debug("Starting storage")
    global PERSISTENT_STORAGE
    PERSISTENT_STORAGE = master_init_storage(all_vars["storage_conf"], logger)

    logger.debug("Starting streaming")
    global STREAMING
    STREAMING = init_streaming(all_vars["streaming_backend"],
                               all_vars["streaming_master_name"],
                               all_vars["streaming_master_port"])

    # Start monitoring the stdout and stderr
    STDW.start_watching()

    # MAIN EXECUTION
    # let the user write an interactive application
    print("* - PyCOMPSs Runtime started... Have fun!              *")
    print(LINE_SEPARATOR)

    # Emit the application start event (the 0 is in the stop function)
    emit_manual_event(APPLICATION_RUNNING_EVENT)


def __show_flower__():
    # type: () -> None
    """ Shows the flower and version through stdout.

    :return: None
    """
    print(LINE_SEPARATOR)                                              # NOSONAR # noqa
    print("**************** PyCOMPSs Interactive ******************")  # NOSONAR # noqa
    print(LINE_SEPARATOR)                                              # NOSONAR # noqa
    print("*          .-~~-.--.           _____      __   ______  *")  # NOSONAR # noqa
    print("*         :         )         |____ \    /  | /  __  \ *")  # NOSONAR # noqa
    print("*   .~ ~ -.\       /.- ~~ .     ___) |  /_  | | |  | | *")  # NOSONAR # noqa
    print("*   >       `.   .'       <    / ___/     | | | |  | | *")  # NOSONAR # noqa
    print("*  (         .- -.         )  | |___   _  | | | |__| | *")  # NOSONAR # noqa
    print("*   `- -.-~  `- -'  ~-.- -'   |_____| |_| |_| \______/ *")  # NOSONAR # noqa
    print("*     (        :        )           _ _ .-:            *")  # NOSONAR # noqa
    print("*      ~--.    :    .--~        .-~  .-~  }            *")  # NOSONAR # noqa
    print("*          ~-.-^-.-~ \_      .~  .-~   .~              *")  # NOSONAR # noqa
    print("*                   \ \ '     \ '_ _ -~                *")  # NOSONAR # noqa
    print("*                    \`.\`.    //                      *")  # NOSONAR # noqa
    print("*           . - ~ ~-.__\`.\`-.//                       *")  # NOSONAR # noqa
    print("*       .-~   . - ~  }~ ~ ~-.~-.                       *")  # NOSONAR # noqa
    print("*     .' .-~      .-~       :/~-.~-./:                 *")  # NOSONAR # noqa
    print("*    /_~_ _ . - ~                 ~-.~-._              *")  # NOSONAR # noqa
    print("*                                     ~-.<             *")  # NOSONAR # noqa
    print(LINE_SEPARATOR)                                              # NOSONAR # noqa


def __print_setup__(verbose, all_vars):
    # type: (bool, dict) -> None
    """ Print the setup variables through stdout (only if verbose is True).

    :param verbose: Verbose mode [True | False]
    :param all_vars: Dictionary containing all variables.
    :return: None
    """
    logger = logging.getLogger(__name__)
    output = ""
    output += LINE_SEPARATOR + "\n"
    output += " CONFIGURATION: \n"
    for k, v in sorted(all_vars.items()):
        output += "  - {0:20} : {1} \n".format(k, v)
    output += LINE_SEPARATOR
    if verbose:
        print(output)
    logger.debug(output)


def stop(sync=False, _hard_stop=False):
    # type: (bool, bool) -> None
    """ Runtime stop.

    :param sync: Scope variables synchronization [ True | False ]
                 (default: False)
    :param _hard_stop: Stop compss when runtime has died [ True | False ].
                       (default: False)
    :return: None
    """
    logger = logging.getLogger(__name__)
    ipython = globals()['__builtins__']['get_ipython']()

    if not context.in_pycompss():
        return __hard_stop__(interactive_helpers.DEBUG, sync, logger, ipython)

    from pycompss.api.api import compss_stop

    print(LINE_SEPARATOR)
    print("*************** STOPPING PyCOMPSs ******************")
    print(LINE_SEPARATOR)
    # Wait 5 seconds to give some time to process the remaining messages
    # of the STDW and check if there is some error that could have stopped
    # the runtime before continuing.
    print("Checking if any issue happened.")
    time.sleep(5)
    messages = STDW.get_messages()
    if messages:
        for message in messages:
            sys.stderr.write("".join((message, '\n')))

    # Uncomment the following lines to see the ipython dictionary
    # in a structured way:
    #   import pprint
    #   pprint.pprint(ipython.__dict__, width=1)
    if sync and not _hard_stop:
        sync_msg = "Synchronizing all future objects left on the user scope."
        print(sync_msg)
        logger.debug(sync_msg)
        from pycompss.api.api import compss_wait_on
        reserved_names = ('quit', 'exit', 'get_ipython',
                          'APP_PATH', 'ipycompss', 'In', 'Out')
        raw_code = ipython.__dict__['user_ns']
        for k in raw_code:
            obj_k = raw_code[k]
            if not k.startswith('_'):   # not internal objects
                if type(obj_k) == Future:
                    print("Found a future object: %s" % str(k))
                    logger.debug("Found a future object: %s" % str(k))
                    new_obj_k = compss_wait_on(obj_k)
                    if new_obj_k == obj_k:
                        print("\t - Could not retrieve object: %s" % str(k))
                        logger.debug("\t - Could not retrieve object: %s" % str(k))
                    else:
                        ipython.__dict__['user_ns'][k] = new_obj_k
                elif k not in reserved_names:
                    try:
                        if OT_is_pending_to_synchronize(obj_k):
                            print("Found an object to synchronize: %s" % str(k))       # noqa: E501
                            logger.debug("Found an object to synchronize: %s" % (k,))  # noqa: E501
                            ipython.__dict__["user_ns"][k] = compss_wait_on(obj_k)     # noqa: E501
                    except TypeError:
                        # Unhashable type: List - could be a collection
                        if isinstance(obj_k, list):
                            print("Found a list to synchronize: %s" % str(k))
                            logger.debug("Found a list to synchronize: %s" % (k,))     # noqa: E501
                            ipython.__dict__["user_ns"][k] = compss_wait_on(obj_k)     # noqa: E501
    else:
        print("Warning: some of the variables used with PyCOMPSs may")
        print("         have not been brought to the master.")

    # Stop streaming
    if STREAMING:
        stop_streaming()

    # Stop persistent storage
    if PERSISTENT_STORAGE:
        master_stop_storage(logger)

    # Emit the 0 for the APPLICATION_RUNNING_EVENT emitted on start function.
    emit_manual_event(0)

    # Stop runtime
    compss_stop(_hard_stop=_hard_stop)

    # Cleanup events and files
    release_event_manager(ipython)
    __clean_temp_files__()

    # Stop watching stdout and stderr
    STDW.stop_watching(clean=True)
    # Retrieve the remaining messages that could have been captured.
    last_messages = STDW.get_messages()
    if last_messages:
        for message in last_messages:
            print(message)

    # Let the Python binding know we are not at master anymore
    context.set_pycompss_context(context.OUT_OF_SCOPE)

    print(LINE_SEPARATOR)
    logger.debug("--- END ---")

    # --- Execution finished ---


def __hard_stop__(debug, sync, logger, ipython):
    # type: (bool, bool, ..., ...) -> None
    """ The runtime has been stopped by any error and this method stops the
    remaining things in the binding.

    :param debug: If debugging.
    :param sync: Scope variables synchronization [ True | False ].
    :param logger: Logger where to put the logging messages.
    :param ipython: Ipython instance.
    :return: None
    """
    print("The runtime is not running.")
    # Check that everything is stopped as well:

    # Stop streaming
    if STREAMING:
        stop_streaming()

    # Stop persistent storage
    if PERSISTENT_STORAGE:
        master_stop_storage(logger)

    # Clean any left object in the object tracker
    OT_clean_object_tracker()

    # Cleanup events and files
    release_event_manager(ipython)
    __clean_temp_files__()

    # Stop watching stdout and stderr
    STDW.stop_watching(clean=not debug)
    # Retrieve the remaining messages that could have been captured.
    last_messages = STDW.get_messages()
    if last_messages:
        for message in last_messages:
            print(message)

    if sync:
        print("* Can not synchronize any future object.")
    return None


def current_task_graph(fit=False, refresh_rate=1, timeout=0):
    # type: (bool, int, int) -> ...
    """ Show current graph.

    :param fit: Fit to width [ True | False ] (default: False)
    :param refresh_rate: Update the current task graph every "refresh_rate"
                         seconds. Default 1 second if timeout != 0.
    :param timeout: Time during the current task graph is going to be updated.
    :return: None
    """
    if GRAPHING:
        return show_graph(log_path=LOG_PATH,
                          name="current_graph",
                          fit=fit,
                          refresh_rate=refresh_rate,
                          timeout=timeout)
    else:
        print("Oops! Graph is not enabled in this execution.")
        print("      Please, enable it by setting the graph flag when" +
              " starting PyCOMPSs.")


def complete_task_graph(fit=False, refresh_rate=1, timeout=0):
    # type: (bool, int, int) -> ...
    """ Show complete graph.

    :param fit: Fit to width [ True | False ] (default: False)
    :param refresh_rate: Update the current task graph every "refresh_rate"
                         seconds. Default 1 second if timeout != 0
    :param timeout: Time during the current task graph is going to be updated.
    :return: None
    """
    if GRAPHING:
        return show_graph(log_path=LOG_PATH,
                          name="complete_graph",
                          fit=fit,
                          refresh_rate=refresh_rate,
                          timeout=timeout)
    else:
        print("Oops! Graph is not enabled in this execution.")
        print("      Please, enable it by setting the graph flag when" +
              " starting PyCOMPSs.")
        return None


def tasks_info():
    # type: () -> None
    """ Show tasks info.

    :return: None
    """
    if check_monitoring_file(LOG_PATH):
        show_tasks_info(LOG_PATH)
    else:
        print("Oops! Monitoring is not enabled in this execution.")
        print("      Please, enable it by setting the monitor flag when" +
              " starting PyCOMPSs.")
        return None


def tasks_status():
    # type: () -> None
    """ Show tasks status.

    :return: None
    """
    if check_monitoring_file(LOG_PATH):
        show_tasks_status(LOG_PATH)
    else:
        print("Oops! Monitoring is not enabled in this execution.")
        print("      Please, enable it by setting the monitor flag when" +
              " starting PyCOMPSs.")
        return None


def statistics():
    # type: () -> None
    """ Show statistics info.

    :return: None
    """
    if check_monitoring_file(LOG_PATH):
        show_statistics(LOG_PATH)
    else:
        print("Oops! Monitoring is not enabled in this execution.")
        print("      Please, enable it by setting the monitor flag when" +
              " starting PyCOMPSs.")
        return None


def resources_status():
    # type: () -> None
    """ Show resources status info.

    :return: None
    """
    if check_monitoring_file(LOG_PATH):
        show_resources_status(LOG_PATH)
    else:
        print("Oops! Monitoring is not enabled in this execution.")
        print("      Please, enable it by setting the monitor flag when" +
              " starting PyCOMPSs.")
        return None


# ########################################################################### #
# ########################################################################### #
# ########################################################################### #


def __export_globals__():
    # type: () -> None
    """ Export globals into interactive environment.

    :return: None
    """
    global APP_PATH
    # Super ugly, but I see no other way to define the APP_PATH across the
    # interactive execution without making the user to define it explicitly.
    # It is necessary to define only one APP_PATH because of the two decorators
    # need to access the same information.
    # if the file is created per task, the constraint will not be able to work.
    # Get ipython globals
    ipython = globals()["__builtins__"]["get_ipython"]()
    # import pprint
    # pprint.pprint(ipython.__dict__, width=1)
    # Extract user globals from ipython
    user_globals = ipython.__dict__["ns_table"]["user_global"]
    # Inject APP_PATH variable to user globals so that task and constraint
    # decorators can get it.
    temp_app_filename = "".join((os.path.join(os.getcwd(),
                                              INTERACTIVE_FILE_NAME),
                                 '_',
                                 str(time.strftime("%d%m%y_%H%M%S")),
                                 ".py"))
    user_globals["APP_PATH"] = temp_app_filename
    APP_PATH = temp_app_filename


def __clean_temp_files__():
    # type: () -> None
    """ Remove any temporary files that may exist.

    Currently: APP_PATH, which contains the file path where all interactive
               code required by the worker is.

    :return: None
    """
    try:
        if os.path.exists(APP_PATH):
            os.remove(APP_PATH)
        if os.path.exists(APP_PATH + 'c'):
            os.remove(APP_PATH + 'c')
    except OSError:
        print("[ERROR] An error has occurred when cleaning temporary files.")
