#!/usr/bin/python
#
#  Copyright 2002-2019 Barcelona Supercomputing Center (www.bsc.es)
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

import os
import sys
import shutil

import pycompss.api.parameter as parameter
from pycompss.api.exceptions import COMPSsException
from pycompss.runtime.task.commons import TaskCommons
from pycompss.runtime.commons import TRACING_HOOK_ENV_VAR
from pycompss.runtime.task.parameter import Parameter
from pycompss.runtime.task.parameter import get_compss_type
from pycompss.runtime.task.arguments import get_varargs_name
from pycompss.runtime.task.arguments import get_name_from_kwarg
from pycompss.runtime.task.arguments import is_vararg
from pycompss.runtime.task.arguments import is_kwarg
from pycompss.runtime.task.arguments import is_return
from pycompss.util.exceptions import PyCOMPSsException
from pycompss.util.objects.properties import create_object_by_con_type
from pycompss.util.storages.persistent import is_psco
from pycompss.util.serialization.serializer import deserialize_from_file
from pycompss.util.serialization.serializer import serialize_to_file
from pycompss.util.serialization.serializer import serialize_to_file_mpienv
from pycompss.util.std.redirects import std_redirector
from pycompss.util.std.redirects import not_std_redirector
from pycompss.util.objects.util import group_iterable
from pycompss.worker.commons.worker import build_task_parameter

import logging
logger = logging.getLogger(__name__)


class TaskWorker(TaskCommons):
    """
    Task code for the Worker:

    Process the task decorator and prepare call the user function.
    """

    __slots__ = []

    def __init__(self,
                 decorator_arguments,
                 user_function,
                 on_failure,
                 defaults):
        # Initialize TaskCommons
        super(self.__class__, self).__init__(decorator_arguments,
                                             user_function,
                                             on_failure,
                                             defaults)

    def call(self, *args, **kwargs):
        # type: (tuple, dict) -> (list, list, list)
        """ Main task code at worker side.

        This function deals with task calls in the worker's side
        Note that the call to the user function is made by the worker,
        not by the user code.

        :return: A function that calls the user function with the given
                 parameters and does the proper serializations and updates
                 the affected objects.
        """
        # Grab logger from kwargs (shadows outer logger since it is set by
        # the worker).
        logger = kwargs['logger']  # noqa
        if __debug__:
            logger.debug("Starting @task decorator worker call")

        # Update the on_failure attribute (could be defined by @on_failure)
        self.on_failure = kwargs.pop("on_failure", "RETRY")
        self.defaults = kwargs.pop("defaults", {})

        if __debug__:
            logger.debug("Revealing objects")
        # All parameters are in the same args list. At the moment we only know
        # the type, the name and the "value" of the parameter. This value may
        # be treated to get the actual object (e.g: deserialize it, query the
        # database in case of persistent objects, etc.)
        self.reveal_objects(args, logger,
                            kwargs["compss_python_MPI"],
                            kwargs["compss_collections_layouts"])
        if __debug__:
            logger.debug("Finished revealing objects")
            logger.debug("Building task parameters structures")

        # After this line all the objects in arg have a "content" field, now
        # we will segregate them in User positional and variadic args
        user_args, user_kwargs, ret_params = self.segregate_objects(args)
        num_returns = len(ret_params)

        if __debug__:
            logger.debug("Finished building parameters structures.")

        # Self definition (only used when defined in the task)
        # Save the self object type and value before executing the task
        # (it could be persisted inside if its a persistent object)
        self_type = None
        self_value = None
        has_self = False
        if args and not isinstance(args[0], Parameter):
            if __debug__:
                logger.debug("Detected self parameter")
            # Then the first arg is self
            has_self = True
            self_type = get_compss_type(args[0])
            if self_type == parameter.TYPE.EXTERNAL_PSCO:
                if __debug__:
                    logger.debug("\t - Self is a PSCO")
                self_value = args[0].getID()
            else:
                # Since we are checking the type of the deserialized self
                # parameter, get_compss_type will return that its type is
                # parameter.TYPE.OBJECT, which although it is an object, self
                # is always a file for the runtime. So we must force its type
                # to avoid that the return message notifies that it has a new
                # type "object" which is not supported for python objects in
                # the runtime.
                self_type = parameter.TYPE.FILE
                self_value = 'null'

        # Call the user function with all the reconstructed parameters and
        # get the return values.
        redirect_std = True
        if kwargs['compss_log_files']:
            # Redirect all stdout and stderr during the user code execution
            # to job out and err files.
            job_out, job_err = kwargs['compss_log_files']
        else:
            job_out, job_err = None, None
            redirect_std = False
        if __debug__:
            logger.debug("Redirecting stdout to: " + str(job_out))
            logger.debug("Redirecting stderr to: " + str(job_err))
        with std_redirector(job_out, job_err) if redirect_std else not_std_redirector():  # noqa: E501
            if __debug__:
                logger.debug("Invoking user code")
            # Now execute the user code
            result = self.execute_user_code(user_args,
                                            user_kwargs,
                                            kwargs['compss_tracing'])
            user_returns, compss_exception, default_values = result
            if __debug__:
                logger.debug("Finished user code")

        python_mpi = False
        if kwargs["compss_python_MPI"]:
            python_mpi = True

        # Deal with defaults if any
        if default_values:
            self.manage_defaults(args, default_values)

        # Deal with INOUTs and COL_OUTs
        self.manage_inouts(args, python_mpi)

        # Deal with COMPSsExceptions
        if compss_exception is not None:
            if __debug__:
                logger.warning("Detected COMPSs Exception. Raising.")
            raise compss_exception

        # Deal with returns (if any)
        user_returns = self.manage_returns(num_returns, user_returns,
                                           ret_params, python_mpi)

        # Check old targetDirection
        if 'targetDirection' in self.decorator_arguments:
            target_label = 'targetDirection'
            logger.info("Detected deprecated targetDirection. Please, change it to target_direction")  # noqa: E501
        else:
            target_label = 'target_direction'

        # We must notify COMPSs when types are updated
        new_types, new_values = self.manage_new_types_values(num_returns,
                                                             user_returns,
                                                             args,
                                                             has_self,
                                                             target_label,
                                                             self_type,
                                                             self_value)
        if __debug__:
            logger.debug("Finished @task decorator")

        return new_types, new_values, self.decorator_arguments[target_label]

    def reveal_objects(self, args, logger, python_mpi=False, collections_layouts=None):  # noqa
        # type: (tuple, logger, bool, list) -> None
        """ Get the objects from the args message.

        This function takes the arguments passed from the persistent worker
        and treats them to get the proper parameters for the user function.

        :param args: Arguments.
        :param logger: Logger (shadows outer logger since this is only used
                               in the worker to reveal the parameter objects).
        :param python_mpi: If the task is python MPI.
        :param collections_layouts: Layouts of collections params for python
                                    MPI tasks.
        :return: None
        """
        if self.storage_supports_pipelining():
            if __debug__:
                logger.debug("The storage supports pipelining.")
            # Perform the pipelined getByID operation
            pscos = [x for x in args if
                     x.content_type == parameter.TYPE.EXTERNAL_PSCO]
            identifiers = [x.content for x in pscos]
            from storage.api import getByID  # noqa
            objects = getByID(*identifiers)
            # Just update the Parameter object with its content
            for (obj, value) in zip(objects, pscos):
                obj.content = value

        # Deal with all the parameters that are NOT returns
        for arg in [x for x in args if
                    isinstance(x, Parameter) and not is_return(x.name)]:
            self.retrieve_content(arg, "", python_mpi, collections_layouts)

    @staticmethod
    def storage_supports_pipelining():
        # type: () -> bool
        """ Check if storage supports pipelining.

        Some storage implementations use pipelining
        Pipelining means "accumulate the getByID queries and perform them
        in a single megaquery".
        If this feature is not available (storage does not support it)
        getByID operations will be performed one after the other.

        :return: True if pipelining is supported. False otherwise.
        """
        try:
            import storage.api  # noqa
            return storage.api.__pipelining__
        except (ImportError, AttributeError):
            return False

    def retrieve_content(self, argument, name_prefix,
                         python_mpi, collections_layouts,
                         depth=0):
        # type: (Parameter, str, bool, list, int) -> None
        """ Retrieve the content of a particular argument.

        :param argument: Argument.
        :param name_prefix: Name prefix.
        :param python_mpi: If the task is python MPI.
        :param collections_layouts: Layouts of collections params for python
                                    MPI tasks.
        :param depth: Collection depth (0 if not a collection).
        :return: None
        """
        if __debug__:
            logger.debug("\t - Revealing: " + str(argument.name))
        # This case is special, as a FILE can actually mean a FILE or an
        # object that is serialized in a file
        if is_vararg(argument.name):
            self.param_varargs = argument.name
            if __debug__:
                logger.debug("\t\t - It is vararg")

        content_type = argument.content_type
        type_file = parameter.TYPE.FILE
        type_directory = parameter.TYPE.DIRECTORY
        type_external_stream = parameter.TYPE.EXTERNAL_STREAM
        type_collection = parameter.TYPE.COLLECTION
        type_dict_collection = parameter.TYPE.DICT_COLLECTION
        type_external_psco = parameter.TYPE.EXTERNAL_PSCO

        if content_type == type_file:
            if self.is_parameter_an_object(argument.name):
                # The object is stored in some file, load and deserialize
                f_name = argument.file_name.split(':')[-1]
                if __debug__:
                    logger.debug("\t\t - It is an OBJECT. Deserializing from file: " + str(f_name))  # noqa: E501
                argument.content = deserialize_from_file(f_name)
                if __debug__:
                    logger.debug("\t\t - Deserialization finished")
            else:
                # The object is a FILE, just forward the path of the file
                # as a string parameter
                argument.content = argument.file_name.split(':')[-1]
                if __debug__:
                    logger.debug("\t\t - It is FILE: " + str(argument.content))
        elif content_type == type_directory:
            if __debug__:
                logger.debug("\t\t - It is a DIRECTORY")
            argument.content = argument.file_name.split(":")[-1]
        elif content_type == type_external_stream:
            if __debug__:
                logger.debug("\t\t - It is an EXTERNAL STREAM")
            argument.content = deserialize_from_file(argument.file_name)
        elif content_type == type_collection:
            argument.content = []
            # This field is exclusive for COLLECTION_T parameters, so make
            # sure you have checked this parameter is a collection before
            # consulting it
            argument.collection_content = []
            col_f_name = argument.file_name.split(':')[-1]

            # maybe it is an inner-collection..
            _dec_arg = self.decorator_arguments.get(argument.name, None)
            _col_dir = _dec_arg.direction if _dec_arg else None
            _col_dep = _dec_arg.depth if _dec_arg else depth
            if __debug__:
                logger.debug("\t\t - It is a COLLECTION: " + str(col_f_name))
                logger.debug("\t\t\t - Depth: " + str(_col_dep))

            # Check if this collection is in layout
            # Three conditions:
            # 1- this is a mpi task
            # 2- it has a collection layout
            # 3- the current argument is the layout target
            in_mpi_collection_env = False
            if python_mpi and collections_layouts and \
                    argument.name in collections_layouts:
                in_mpi_collection_env = True
                from pycompss.util.mpi.helper import rank_distributor
                # Call rank_distributor if the current param is the target of
                # the layout for each rank, return its offset(s) in the
                # collection.
                rank_distribution = rank_distributor(collections_layouts[argument.name])
                rank_distr_len = len(rank_distribution)
                if __debug__:
                    logger.debug("Rank distribution is: " + str(rank_distribution))  # noqa: E501

            for (i, line) in enumerate(open(col_f_name, 'r')):
                if in_mpi_collection_env and i not in rank_distribution:
                    # Isn't this my offset? skip
                    continue
                data_type, content_file, content_type = line.strip().split()
                # Same naming convention as in COMPSsRuntimeImpl.java
                sub_name = "%s.%d" % (argument.name, i)
                if name_prefix:
                    sub_name = "%s.%s" % (name_prefix, argument.name)
                else:
                    sub_name = "@%s" % sub_name

                if __debug__:
                    logger.debug("\t\t\t - Revealing element: " +
                                 str(sub_name))

                if not self.is_parameter_file_collection(argument.name):
                    sub_arg, _ = build_task_parameter(int(data_type),
                                                      parameter.IOSTREAM.UNSPECIFIED,  # noqa: E501
                                                      "",
                                                      sub_name,
                                                      content_file,
                                                      argument.content_type, logger=logger)

                    # if direction of the collection is 'out', it means we
                    # haven't received serialized objects from the Master
                    # (even though parameters have 'file_name', those files
                    # haven't been created yet). plus, inner collections of
                    # col_out params do NOT have 'direction', we identify
                    # them by 'depth'..
                    if _col_dir == parameter.DIRECTION.OUT or \
                            ((_col_dir is None) and _col_dep > 0):
                        # if we are at the last level of COL_OUT param,
                        # create 'empty' instances of elements
                        if _col_dep == 1:
                            temp = create_object_by_con_type(content_type)
                            sub_arg.content = temp
                            # In case that only one element is used in this
                            # mpi rank, the collection list is removed
                            if in_mpi_collection_env and rank_distr_len == 1:
                                argument.content = sub_arg.content
                                argument.content_type = sub_arg.content_type
                            else:
                                argument.content.append(sub_arg.content)
                            argument.collection_content.append(sub_arg)
                        else:
                            self.retrieve_content(sub_arg,
                                                  sub_name,
                                                  python_mpi,
                                                  collections_layouts,
                                                  depth=_col_dep - 1)
                            # In case that only one element is used in this mpi
                            # rank, the collection list is removed
                            if in_mpi_collection_env and rank_distr_len == 1:
                                argument.content = sub_arg.content
                                argument.content_type = sub_arg.content_type
                            else:
                                argument.content.append(sub_arg.content)
                            argument.collection_content.append(sub_arg)
                    else:
                        # Recursively call the retrieve method, fill the
                        # content field in our new taskParameter object
                        self.retrieve_content(sub_arg, sub_name,
                                              python_mpi, collections_layouts)
                        # In case only one element is used in this mpi rank,
                        # the collection list is removed
                        if in_mpi_collection_env and rank_distr_len == 1:
                            argument.content = sub_arg.content
                            argument.content_type = sub_arg.content_type
                        else:
                            argument.content.append(sub_arg.content)
                        argument.collection_content.append(sub_arg)
                else:
                    # In case only one element is used in this mpi rank,
                    # the collection list is removed
                    if in_mpi_collection_env and rank_distr_len == 1:
                        argument.content = content_file
                        argument.content_type = parameter.TYPE.FILE
                    else:
                        argument.content.append(content_file)
                    argument.collection_content.append(content_file)
        elif content_type == type_dict_collection:
            argument.content = {}
            # This field is exclusive for DICT_COLLECTION_T parameters, so
            # make sure you have checked this parameter is a dictionary
            # collection before consulting it
            argument.dict_collection_content = {}
            dict_col_f_name = argument.file_name.split(':')[-1]
            # Uncomment if you want to check its contents:
            # print("Dictionary file name: " + str(dict_col_f_name))
            # print("Dictionary file contents:")
            # with open(dict_col_f_name, 'r') as f:
            #     print(f.read())

            # Maybe it is an inner-dict-collection
            _dec_arg = self.decorator_arguments.get(argument.name, None)
            _dict_col_dir = _dec_arg.direction if _dec_arg else None
            _dict_col_dep = _dec_arg.depth if _dec_arg else depth

            with open(dict_col_f_name, 'r') as dict_file:
                lines = dict_file.readlines()
            entries = group_iterable(lines, 2)
            i = 0
            for entry in entries:
                k = entry[0]
                v = entry[1]
                data_type_key, content_file_key, content_type_key = k.strip().split()  # noqa: E501
                data_type_value, content_file_value, content_type_value = v.strip().split()  # noqa: E501
                # Same naming convention as in COMPSsRuntimeImpl.java
                sub_name_key = "%s.%d" % (argument.name, i)
                sub_name_value = "%s.%d" % (argument.name, i)
                if name_prefix:
                    sub_name_key = "%s.%s" % (name_prefix, argument.name)
                    sub_name_value = "%s.%s" % (name_prefix, argument.name)
                else:
                    sub_name_key = "@key%s" % sub_name_key
                    sub_name_value = "@value%s" % sub_name_value

                sub_arg_key, _ = build_task_parameter(int(data_type_key),
                                                      parameter.IOSTREAM.UNSPECIFIED,
                                                      "",
                                                      sub_name_key,
                                                      content_file_key,
                                                      argument.content_type, logger=logger)
                sub_arg_value, _ = build_task_parameter(int(data_type_value),  # noqa: E501
                                                        parameter.IOSTREAM.UNSPECIFIED,
                                                        "",
                                                        sub_name_value,
                                                        content_file_value,
                                                        argument.content_type, logger=logger)

                # if direction of the dictionary collection is 'out', it
                # means we haven't received serialized objects from the
                # Master (even though parameters have 'file_name', those
                # files haven't been created yet). plus, inner dictionary
                # collections of dict_col_out params do NOT have
                # 'direction', we identify them by 'depth'..
                if _dict_col_dir == parameter.DIRECTION.OUT or \
                        ((_dict_col_dir is None) and _dict_col_dep > 0):

                    # if we are at the last level of DICT_COL_OUT param,
                    # create 'empty' instances of elements
                    if _dict_col_dep == 1:
                        temp_k = create_object_by_con_type(content_type_key)    # noqa: E501
                        temp_v = create_object_by_con_type(content_type_value)  # noqa: E501
                        sub_arg_key.content = temp_k
                        sub_arg_value.content = temp_v
                        argument.content[sub_arg_key.content] = sub_arg_value.content  # noqa: E501
                        argument.dict_collection_content[sub_arg_key] = sub_arg_value  # noqa: E501
                    else:
                        self.retrieve_content(sub_arg_key, sub_name_key,
                                              None, None,
                                              depth=_dict_col_dep - 1)
                        self.retrieve_content(sub_arg_value, sub_name_value,
                                              None, None,
                                              depth=_dict_col_dep - 1)
                        argument.content[sub_arg_key.content] = sub_arg_value.content  # noqa: E501
                        argument.dict_collection_content[sub_arg_key] = sub_arg_value  # noqa: E501
                else:
                    # Recursively call the retrieve method, fill the
                    # content field in our new taskParameter object
                    self.retrieve_content(sub_arg_key, sub_name_key, None, None)
                    self.retrieve_content(sub_arg_value, sub_name_value, None, None)
                    argument.content[sub_arg_key.content] = sub_arg_value.content  # noqa: E501
                    argument.dict_collection_content[sub_arg_key] = sub_arg_value  # noqa: E501
        elif not self.storage_supports_pipelining() and \
                content_type == type_external_psco:
            if __debug__:
                logger.debug("\t\t - It is a PSCO")
            # The object is a PSCO and the storage does not support
            # pipelining, do a single getByID of the PSCO
            from storage.api import getByID  # noqa
            argument.content = getByID(argument.content)
            # If we have not entered in any of these cases we will assume
            # that the object was a basic type and the content is already
            # available and properly casted by the python worker

    def segregate_objects(self, args):
        # type: (tuple) -> (list, dict, list)
        """ Split a list of arguments.

        Segregates a list of arguments in user positional, variadic and
        return arguments.

        :return: list of user arguments, dictionary of user kwargs and a list
                 of return parameters.
        """
        # User args
        user_args = []
        # User named args (kwargs)
        user_kwargs = {}
        # Return parameters, save them apart to match the user returns with
        # the internal parameters
        ret_params = []

        for arg in args:
            # Just fill the three data structures declared above
            # Deal with the self parameter (if any)
            if not isinstance(arg, Parameter):
                user_args.append(arg)
            # All these other cases are all about regular parameters
            elif is_return(arg.name):
                ret_params.append(arg)
            elif is_kwarg(arg.name):
                user_kwargs[get_name_from_kwarg(arg.name)] = arg.content
            else:
                if is_vararg(arg.name):
                    self.param_varargs = get_varargs_name(arg.name)
                # Apart from the names we preserve the original order, so it
                # is guaranteed that named positional arguments will never be
                # swapped with variadic ones or anything similar
                user_args.append(arg.content)

        return user_args, user_kwargs, ret_params

    def execute_user_code(self, user_args, user_kwargs, tracing):
        # type: (list, dict, bool) -> (object, COMPSsException)
        """ Executes the user code.

        Disables the tracing hook if tracing is enabled. Restores it
        at the end of the user code execution.

        :param user_args: Function args.
        :param user_kwargs: Function kwargs.
        :param tracing: If tracing enabled.
        :return: The user function returns and the compss exception (if any).
        """
        # Tracing hook is disabled by default during the user code of the task.
        # The user can enable it with tracing_hook=True in @task decorator for
        # specific tasks or globally with the COMPSS_TRACING_HOOK=true
        # environment variable.
        restore_hook = False
        pro_f = None
        if tracing:
            global_tracing_hook = False
            if TRACING_HOOK_ENV_VAR in os.environ:
                hook_enabled = os.environ[TRACING_HOOK_ENV_VAR] == "true"
                global_tracing_hook = hook_enabled
            if self.decorator_arguments['tracing_hook'] or global_tracing_hook:
                # The user wants to keep the tracing hook
                pass
            else:
                # When Extrae library implements the function to disable,
                # use it, as:
                #     import pyextrae
                #     pro_f = pyextrae.shutdown()
                # Since it is not available yet, we manage the tracing hook
                # by ourselves
                pro_f = sys.getprofile()
                sys.setprofile(None)
                restore_hook = True

        user_returns = None
        compss_exception = None
        default_values = None
        if self.decorator_arguments['numba']:
            # Import all supported functionalities
            from numba import jit
            from numba import njit
            from numba import generated_jit
            from numba import vectorize
            from numba import guvectorize
            from numba import stencil
            from numba import cfunc
            numba_mode = self.decorator_arguments['numba']
            numba_flags = self.decorator_arguments['numba_flags']
            if type(numba_mode) is dict:
                # Use the flags defined by the user
                numba_flags['cache'] = True  # Always force cache
                user_returns = jit(self.user_function,
                                   **numba_flags)(*user_args, **user_kwargs)
            elif numba_mode is True or numba_mode == 'jit':
                numba_flags['cache'] = True  # Always force cache
                user_returns = jit(self.user_function,
                                   **numba_flags)(*user_args, **user_kwargs)
                # Alternative way of calling:
                # user_returns = jit(cache=True)(self.user_function) \
                #                   (*user_args, **user_kwargs)
            elif numba_mode == 'generated_jit':
                user_returns = generated_jit(self.user_function,
                                             **numba_flags)(*user_args,
                                                            **user_kwargs)
            elif numba_mode == 'njit':
                numba_flags['cache'] = True  # Always force cache
                user_returns = njit(self.user_function,
                                    **numba_flags)(*user_args, **user_kwargs)
            elif numba_mode == 'vectorize':
                numba_signature = self.decorator_arguments['numba_signature']  # noqa: E501
                user_returns = vectorize(
                    numba_signature,
                    **numba_flags
                )(self.user_function)(*user_args, **user_kwargs)
            elif numba_mode == 'guvectorize':
                numba_signature = self.decorator_arguments['numba_signature']  # noqa: E501
                numba_decl = self.decorator_arguments['numba_declaration']
                user_returns = guvectorize(
                    numba_signature,
                    numba_decl,
                    **numba_flags
                )(self.user_function)(*user_args, **user_kwargs)
            elif numba_mode == 'stencil':
                user_returns = stencil(
                    **numba_flags
                )(self.user_function)(*user_args, **user_kwargs)
            elif numba_mode == 'cfunc':
                numba_signature = self.decorator_arguments['numba_signature']  # noqa: E501
                user_returns = cfunc(
                    numba_signature
                )(self.user_function).ctypes(*user_args, **user_kwargs)
            else:
                raise PyCOMPSsException("Unsupported numba mode.")
        else:
            try:
                # Normal task execution
                user_returns = self.user_function(*user_args, **user_kwargs)
            except COMPSsException as ce:
                # Perform any required action on failure
                user_returns, default_values = self.manage_exception()
                compss_exception = ce
                # Check old targetDirection
                if 'targetDirection' in self.decorator_arguments:
                    target_label = 'targetDirection'
                else:
                    target_label = 'target_direction'
                compss_exception.target_direction = self.decorator_arguments[target_label]  # noqa: E501
            except Exception as exc:  # noqa
                if self.on_failure == "IGNORE":
                    # Perform any required action on failure
                    user_returns, default_values = self.manage_exception()
                else:
                    # Re-raise the exception
                    raise exc

        # Reestablish the hook if it was disabled
        if restore_hook:
            sys.setprofile(pro_f)

        return user_returns, compss_exception, default_values

    def manage_exception(self):
        # type () -> (tuple, dict)
        """ Deal with exceptions (on failure action).

        :return: The default return and values.
        """
        user_returns = None
        default_values = None
        if self.on_failure == "IGNORE":
            # Provide default return
            user_returns = self.defaults.pop("returns", None)
            # Provide defaults to the runtime
            default_values = self.defaults
        return user_returns, default_values

    def manage_defaults(self, args, default_values):
        # type: (tuple, dict) -> None
        """ Deal with default values. Updates args with the appropriate object
        or file.

        :param args: Argument list.
        :param default_values: Dictionary containing the default values.
        :return: None
        """
        if __debug__:
            logger.debug("Dealing with default values")
        for arg in args:
            # Skip non-task-parameters
            if not isinstance(arg, Parameter):
                continue
            # Skip returns
            if is_return(arg.name):
                continue
            if self.is_parameter_an_object(arg.name):
                # Update object
                arg.content = default_values[arg.name]
            else:
                # Update file
                shutil.copyfile(default_values[arg.name], arg.content)

    def manage_inouts(self, args, python_mpi):
        # type: (tuple, bool) -> None
        """ Deal with INOUTS. Serializes the result of INOUT parameters.

        :param args: Argument list.
        :param python_mpi: Boolean if python mpi.
        :return: None
        """
        if __debug__:
            logger.debug("Dealing with INOUTs and OUTS")
            if python_mpi:
                logger.debug("\t - Managing with MPI policy")

        # Manage all the possible outputs of the task and build the return new
        # types and values
        for arg in args:
            # Handle only task parameters that are objects

            # Skip files and non-task-parameters
            if not isinstance(arg, Parameter) or \
                    not self.is_parameter_an_object(arg.name):
                continue

            # File collections are objects, but must be skipped as well
            if self.is_parameter_file_collection(arg.name):
                continue

            # Skip psco: since param.content_type has the old type, we can
            # not use:  param.content_type != parameter.TYPE.EXTERNAL_PSCO
            _is_psco_true = (arg.content_type ==
                             parameter.TYPE.EXTERNAL_PSCO or
                             is_psco(arg.content))
            if _is_psco_true:
                continue

            original_name = get_name_from_kwarg(arg.name)
            param = self.decorator_arguments.get(
                original_name, self.get_default_direction(original_name))

            # skip non-inouts or non-col_outs
            _is_col_out = (arg.content_type == parameter.TYPE.COLLECTION and
                           param.direction == parameter.DIRECTION.OUT)

            _is_dict_col_out = (arg.content_type == parameter.TYPE.DICT_COLLECTION and
                                param.direction == parameter.DIRECTION.OUT)

            _is_inout = (param.direction == parameter.DIRECTION.INOUT or
                         param.direction == parameter.DIRECTION.COMMUTATIVE)

            if not (_is_inout or _is_col_out or _is_dict_col_out):
                continue

            # Now it is 'INOUT' or 'COLLECTION_OUT' or 'DICT_COLLECTION_OUT'
            # object param, serialize to a file.
            if arg.content_type == parameter.TYPE.COLLECTION:
                if __debug__:
                    logger.debug("Serializing collection: " + str(arg.name))
                # handle collections recursively
                for (content, elem) in __get_collection_objects__(arg.content, arg):  # noqa: E501
                    if elem.file_name:
                        f_name = __get_file_name__(elem.file_name)
                        if __debug__:
                            logger.debug("\t - Serializing element: " +
                                         str(arg.name) + " to " + str(f_name))
                        if python_mpi:
                            serialize_to_file_mpienv(content, f_name, False)
                        else:
                            serialize_to_file(content, f_name)
                    else:
                        # It is None --> PSCO
                        pass
            elif arg.content_type == parameter.TYPE.DICT_COLLECTION:
                if __debug__:
                    logger.debug("Serializing dictionary collection: " + str(arg.name))
                # handle dictionary collections recursively
                for (content, elem) in __get_dict_collection_objects__(arg.content, arg):  # noqa: E501
                    if elem.file_name:
                        f_name = __get_file_name__(elem.file_name)
                        if __debug__:
                            logger.debug("\t - Serializing element: " +
                                         str(arg.name) + " to " + str(f_name))
                        if python_mpi:
                            serialize_to_file_mpienv(content, f_name, False)
                        else:
                            serialize_to_file(content, f_name)
                    else:
                        # It is None --> PSCO
                        pass
            else:
                f_name = __get_file_name__(arg.file_name)
                if __debug__:
                    logger.debug("Serializing object: " +
                                 str(arg.name) + " to " + str(f_name))
                if python_mpi:
                    serialize_to_file_mpienv(arg.content, f_name, False)
                else:
                    serialize_to_file(arg.content, f_name)

    @staticmethod
    def manage_returns(num_returns, user_returns, ret_params, python_mpi):
        # type: (int, list, list, bool) -> list
        """ Manage task returns.

        :param num_returns: Number of returns.
        :param user_returns: User returns.
        :param ret_params: Return parameters.
        :param python_mpi: Boolean if is python mpi code.
        :return: User returns.
        """
        if __debug__:
            logger.debug("Dealing with returns: " + str(num_returns))
        if num_returns > 0:
            if num_returns == 1:
                # Generalize the return case to multi-return to simplify the
                # code
                user_returns = [user_returns]
            elif num_returns > 1 and python_mpi:
                user_returns = [user_returns]
                ret_params = __get_ret_rank__(ret_params)
            # Note that we are implicitly assuming that the length of the user
            # returns matches the number of return parameters
            for (obj, param) in zip(user_returns, ret_params):
                # If the object is a PSCO, do not serialize to file
                if param.content_type == parameter.TYPE.EXTERNAL_PSCO \
                        or is_psco(obj):
                    continue
                # Serialize the object
                # Note that there is no "command line optimization" in the
                # returns, as we always pass them as files.
                # This is due to the asymmetry in worker-master communications
                # and because it also makes it easier for us to deal with
                # returns in that format
                f_name = __get_file_name__(param.file_name)
                if __debug__:
                    logger.debug("Serializing return: " + str(f_name))
                if python_mpi:
                    if num_returns > 1:
                        rank_zero_reduce = False
                    else:
                        rank_zero_reduce = True

                    serialize_to_file_mpienv(obj, f_name, rank_zero_reduce)
                else:
                    serialize_to_file(obj, f_name)
        return user_returns

    def is_parameter_an_object(self, name):
        # type: (str) -> bool
        """ Given the name of a parameter, determine if it is an object or not.

        :param name: Name of the parameter.
        :return: True if the parameter is a (serializable) object.
        """
        original_name = get_name_from_kwarg(name)
        # Get the args parameter object
        if is_vararg(original_name):
            return self.get_varargs_direction().content_type is None
        # Is this parameter annotated in the decorator?
        if original_name in self.decorator_arguments:
            annotated = [parameter.TYPE.COLLECTION,
                         parameter.TYPE.DICT_COLLECTION,
                         parameter.TYPE.EXTERNAL_STREAM,
                         None]
            return self.decorator_arguments[original_name].content_type in annotated  # noqa: E501
        # The parameter is not annotated in the decorator, so (by default)
        # return True
        return True

    def is_parameter_file_collection(self, name):
        # type: (str) -> bool
        """ Given the name of a parameter, determine if it is a file
        collection or not.

        :param name: Name of the parameter.
        :return: True if the parameter is a file collection.
        """
        original_name = get_name_from_kwarg(name)
        # Get the args parameter object
        if is_vararg(original_name):
            return self.get_varargs_direction().is_file_collection
        # Is this parameter annotated in the decorator?
        if original_name in self.decorator_arguments:
            return self.decorator_arguments[original_name].is_file_collection
        # The parameter is not annotated in the decorator, so (by default)
        # return False
        return False

    def manage_new_types_values(self,
                                num_returns,   # type: int
                                user_returns,  # type: list
                                args,          # type: tuple
                                has_self,      # type: bool
                                target_label,  # type: str
                                self_type,     # type: str
                                self_value     # type: object
                                ):
        # type: (...) -> (list, list)
        """ Manage new types and values.

        We must notify COMPSs when types are updated
        Potential update candidates are returns and INOUTs
        But the whole types and values list must be returned
        new_types and new_values correspond to "parameters self returns"

        :param num_returns: Number of returns.
        :param user_returns: User returns.
        :param args: Arguments.
        :param has_self: If has self.
        :param target_label: Target label (self, cls, etc.).
        :param self_type: Self type.
        :param self_value: Self value.
        :return: List new types, List new values.
        """
        new_types, new_values = [], []
        if __debug__:
            logger.debug("Building types update")

        def build_collection_types_values(_content, _arg, direction):
            """ Retrieve collection type-value recursively"""
            coll = []
            for (_cont, _elem) in zip(_arg.content, _arg.collection_content):
                if isinstance(_elem, str):
                    coll.append((parameter.TYPE.FILE, 'null'))
                else:
                    if _elem.content_type == \
                            parameter.TYPE.COLLECTION:
                        coll.append(build_collection_types_values(_cont,
                                                                  _elem,
                                                                  direction))
                    elif _elem.content_type == \
                            parameter.TYPE.EXTERNAL_PSCO \
                            and is_psco(_cont) \
                            and direction != parameter.DIRECTION.IN:
                        coll.append((_elem.content_type, _cont.getID()))
                    elif _elem.content_type == \
                            parameter.TYPE.FILE \
                            and is_psco(_cont) \
                            and direction != parameter.DIRECTION.IN:
                        coll.append((parameter.TYPE.EXTERNAL_PSCO,
                                     _cont.getID()))
                    else:
                        coll.append((_elem.content_type, 'null'))
            return coll

        # Add parameter types and value
        params_start = 1 if has_self else 0
        params_end = len(args) - num_returns + 1
        # Update new_types and new_values with the args list
        # The results parameter is a boolean to distinguish the error message.
        for arg in args[params_start:params_end - 1]:
            # Loop through the arguments and update new_types and new_values
            if not isinstance(arg, Parameter):
                raise PyCOMPSsException("ERROR: A task parameter arrived as an"
                                        " object instead as a TaskParameter"
                                        " when building the task result message.")
            else:
                original_name = get_name_from_kwarg(arg.name)
                param = self.decorator_arguments.get(original_name,
                                                     self.get_default_direction(original_name))  # noqa: E501
                if arg.content_type == parameter.TYPE.EXTERNAL_PSCO or \
                        arg.content_type == parameter.TYPE.FILE:
                    # It was originally a persistent object
                    if is_psco(arg.content):
                        new_types.append(parameter.TYPE.EXTERNAL_PSCO)
                        new_values.append(arg.content.getID())
                    else:
                        new_types.append(arg.content_type)
                        new_values.append('null')
                elif arg.content_type == parameter.TYPE.COLLECTION:
                    # There is a collection that can contain persistent objects
                    collection_new_values = \
                        build_collection_types_values(arg.content,
                                                      arg,
                                                      param.direction)
                    new_types.append(parameter.TYPE.COLLECTION)
                    new_values.append(collection_new_values)
                else:
                    # Any other return object: same type and null value
                    new_types.append(arg.content_type)
                    new_values.append('null')

        # Add self type and value if exist
        if has_self:
            if self.decorator_arguments[target_label].direction == parameter.DIRECTION.INOUT:  # noqa: E501
                # Check if self is a PSCO that has been persisted inside the
                # task and target_direction.
                # Update self type and value
                self_type = get_compss_type(args[0])
                if self_type == parameter.TYPE.EXTERNAL_PSCO:
                    self_value = args[0].getID()
                else:
                    # Self can only be of type FILE, so avoid the last update
                    # of self_type
                    if is_psco(args[0]):
                        self_type = parameter.TYPE.EXTERNAL_PSCO
                        self_value = args[0].getID()
                    else:
                        self_type = parameter.TYPE.FILE
                        self_value = 'null'
            new_types.append(self_type)
            new_values.append(self_value)

        # Add return types and values
        # Loop through the rest of the arguments and update new_types and
        #  new_values.
        # assert len(args[params_end - 1:]) == len(user_returns)
        # add_parameter_new_types_and_values(args[params_end - 1:], True)
        if num_returns > 0:
            for ret in user_returns:
                ret_type = get_compss_type(ret)
                if ret_type == parameter.TYPE.EXTERNAL_PSCO:
                    ret_value = ret.getID()
                elif ret_type == parameter.TYPE.COLLECTION:
                    collection_ret_values = []
                    for elem in ret:
                        if elem.type == parameter.TYPE.EXTERNAL_PSCO or \
                                elem.type == parameter.TYPE.FILE:
                            if is_psco(elem.content):
                                collection_ret_values.append(elem.key)
                            else:
                                collection_ret_values.append('null')
                        else:
                            collection_ret_values.append('null')
                    new_types.append(parameter.TYPE.COLLECTION)
                    new_values.append(collection_ret_values)
                else:
                    # Returns can only be of type FILE, so avoid the last
                    # update of ret_type
                    ret_type = parameter.TYPE.FILE
                    ret_value = 'null'
                new_types.append(ret_type)
                new_values.append(ret_value)

        return new_types, new_values


#######################
# AUXILIARY FUNCTIONS #
#######################

def __get_collection_objects__(content, argument):
    """ Retrieve collection objects recursively generator. """
    if argument.content_type == parameter.TYPE.COLLECTION:
        for (new_con, _elem) in zip(argument.content,
                                    argument.collection_content):
            for sub_el in __get_collection_objects__(new_con, _elem):
                yield sub_el
    else:
        yield content, argument


def __get_dict_collection_objects__(content, argument):
    """ Retrieve dictionary collection objects recursively generator. """
    if argument.content_type == parameter.TYPE.DICT_COLLECTION:
        elements = []
        for k, v in argument.content.items():
            elements.extend([k, v])
        # Prepare dict_collection_content per key
        element_parameters_preproc = {}
        for k, v in argument.dict_collection_content.items():
            element_parameters_preproc[k.content] = [k, v]
        # Ensure that the element parameters are in the same order as
        # argument.content
        elements_parameters = []
        for k in argument.content.keys():
            elements_parameters.extend([element_parameters_preproc[k][0],
                                        element_parameters_preproc[k][1]])
        # Loop recursively
        for (new_con, _elem) in zip(elements,
                                    elements_parameters):
            for sub_el in __get_dict_collection_objects__(new_con, _elem):
                yield sub_el
    else:
        yield content, argument


def __get_file_name__(file_path):
    # type: (str) -> str
    """ Retrieve the file name from an absolute file path.

    :param file_path: Absolute file path.
    :return: File name.
    """
    return file_path.split(':')[-1]


def __get_ret_rank__(_ret_params):
    # type: (list) -> list
    """ Retrieve the rank id within MPI.

    :param _ret_params: Return parameters.
    :return: Integer return rank.
    """
    from mpi4py import MPI
    return [_ret_params[MPI.COMM_WORLD.rank]]
