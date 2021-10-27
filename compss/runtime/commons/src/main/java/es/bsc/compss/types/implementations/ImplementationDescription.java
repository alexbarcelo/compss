/*
 *  Copyright 2002-2021 Barcelona Supercomputing Center (www.bsc.es)
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 *
 */
package es.bsc.compss.types.implementations;

import es.bsc.compss.types.implementations.definition.AbstractMethodImplementationDefinition;
import es.bsc.compss.types.implementations.definition.BinaryDefinition;
import es.bsc.compss.types.implementations.definition.COMPSsDefinition;
import es.bsc.compss.types.implementations.definition.ContainerDefinition;
import es.bsc.compss.types.implementations.definition.DecafDefinition;
import es.bsc.compss.types.implementations.definition.ImplementationDefinition;
import es.bsc.compss.types.implementations.definition.MPIDefinition;
import es.bsc.compss.types.implementations.definition.MethodDefinition;
import es.bsc.compss.types.implementations.definition.MultiNodeDefinition;
import es.bsc.compss.types.implementations.definition.OmpSsDefinition;
import es.bsc.compss.types.implementations.definition.OpenCLDefinition;
import es.bsc.compss.types.implementations.definition.PythonMPIDefinition;
import es.bsc.compss.types.implementations.definition.ServiceDefinition;
import es.bsc.compss.types.resources.MethodResourceDescription;
import es.bsc.compss.types.resources.ServiceResourceDescription;
import es.bsc.compss.types.resources.WorkerResourceDescription;
import es.bsc.compss.util.EnvironmentLoader;

import java.io.Externalizable;
import java.io.IOException;
import java.io.ObjectInput;
import java.io.ObjectOutput;


/**
 * Class that contains all the necessary information to generate the actual implementation object.
 *
 * @param <T> Type of resource description compatible with the implementation
 */
public class ImplementationDescription<T extends WorkerResourceDescription, D extends ImplementationDefinition>
    implements Externalizable {

    /**
     * Runtime Objects have serialization ID 1L.
     */
    private static final long serialVersionUID = 1L;

    private String signature;
    private T constraints;
    private D implDefinition;


    /**
     * Creates a new implementation from the given parameters.
     *
     * @param <T> Type of resource description compatible with the implementation
     * @param implType Implementation type.
     * @param implSignature Implementation signature.
     * @param implConstraints Implementation constraints.
     * @param implTypeArgs Implementation specific arguments.
     * @return A new implementation definition from the given parameters.
     * @throws IllegalArgumentException If the number of specific parameters does not match the required number of
     *             parameters by the implementation type.
     */
    @SuppressWarnings("unchecked")
    public static final <T extends WorkerResourceDescription, D extends ImplementationDefinition>
        ImplementationDescription<T, D> defineImplementation(String implType, String implSignature, T implConstraints,
            String... implTypeArgs) throws IllegalArgumentException {

        ImplementationDescription<T, D> id = null;

        if (implType.toUpperCase().compareTo(TaskType.SERVICE.toString()) == 0) {
            if (implTypeArgs.length != ServiceDefinition.NUM_PARAMS) {
                throw new IllegalArgumentException("Incorrect parameters for type SERVICE on " + implSignature);
            }
            String namespace = EnvironmentLoader.loadFromEnvironment(implTypeArgs[0]);
            String serviceName = EnvironmentLoader.loadFromEnvironment(implTypeArgs[1]);
            String operation = EnvironmentLoader.loadFromEnvironment(implTypeArgs[2]);
            String port = EnvironmentLoader.loadFromEnvironment(implTypeArgs[3]);

            id = new ImplementationDescription<>((D) new ServiceDefinition(namespace, serviceName, operation, port),
                implSignature, (T) new ServiceResourceDescription(serviceName, namespace, port, 1));
        } else {
            MethodType mt;
            try {
                mt = MethodType.valueOf(implType);
            } catch (IllegalArgumentException iae) {
                throw new IllegalArgumentException("Unrecognised method type " + implType);
            }

            switch (mt) {
                case METHOD:
                    if (implTypeArgs.length != MethodDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException("Incorrect parameters for type METHOD on " + implSignature);
                    }

                    id = new ImplementationDescription<>((D) new MethodDefinition(implTypeArgs, 0), implSignature,
                        implConstraints);
                    break;

                case PYTHON_MPI:
                    if (implTypeArgs.length < PythonMPIDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException(
                            "Incorrect parameters for type PYTHON_MPI on " + implSignature);
                    }
                    PythonMPIDefinition pyMPIDef = new PythonMPIDefinition(implTypeArgs, 0);
                    implConstraints.scaleUpBy(pyMPIDef.getPPN());
                    id = new ImplementationDescription<>((D) pyMPIDef, implSignature, implConstraints);
                    break;

                case CONTAINER:
                    if (implTypeArgs.length != ContainerDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException(
                            "Incorrect parameters for type CONTAINER on " + implSignature);
                    }
                    id = new ImplementationDescription<>((D) new ContainerDefinition(implTypeArgs, 0), implSignature,
                        implConstraints);
                    break;

                case BINARY:
                    if (implTypeArgs.length != BinaryDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException("Incorrect parameters for type BINARY on " + implSignature);
                    }

                    id = new ImplementationDescription<>((D) new BinaryDefinition(implTypeArgs, 0), implSignature,
                        implConstraints);
                    break;

                case MPI:
                    if (implTypeArgs.length != MPIDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException("Incorrect parameters for type MPI on " + implSignature);
                    }
                    MPIDefinition mpiDef = new MPIDefinition(implTypeArgs, 0);
                    implConstraints.scaleUpBy(mpiDef.getPPN());
                    id = new ImplementationDescription<>((D) mpiDef, implSignature, implConstraints);
                    break;

                case COMPSs:
                    if (implTypeArgs.length != COMPSsDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException("Incorrect parameters for type MPI on " + implSignature);
                    }
                    id = new ImplementationDescription<>((D) new COMPSsDefinition(implTypeArgs, 0), implSignature,
                        implConstraints);
                    break;

                case DECAF:
                    if (implTypeArgs.length != DecafDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException("Incorrect parameters for type DECAF on " + implSignature);
                    }

                    id = new ImplementationDescription<>((D) new DecafDefinition(implTypeArgs, 0), implSignature,
                        implConstraints);
                    break;

                case OMPSS:
                    if (implTypeArgs.length != OmpSsDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException("Incorrect parameters for type OMPSS on " + implSignature);
                    }

                    id = new ImplementationDescription<>((D) new OmpSsDefinition(implTypeArgs, 0), implSignature,
                        implConstraints);
                    break;

                case OPENCL:
                    if (implTypeArgs.length != OpenCLDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException("Incorrect parameters for type OPENCL on " + implSignature);
                    }

                    id = new ImplementationDescription<>((D) new OpenCLDefinition(implTypeArgs, 0), implSignature,
                        implConstraints);
                    break;

                case MULTI_NODE:
                    if (implTypeArgs.length != MultiNodeDefinition.NUM_PARAMS) {
                        throw new IllegalArgumentException(
                            "Incorrect parameters for type MultiNode on " + implSignature);
                    }
                    id = new ImplementationDescription<>((D) new MultiNodeDefinition(implTypeArgs, 0), implSignature,
                        implConstraints);
                    break;
            }
        }
        return id;
    }

    public ImplementationDescription() {
        // For serialization
    }

    /**
     * Constructs a new ImplementationDefinition with the signature and the requirements passed in as parameters.
     *
     * @param signature Signature of the implementation.
     * @param constraints requirements to run the implementation
     */
    public ImplementationDescription(D implDefinition, String signature, T constraints) {
        this.signature = signature;
        this.constraints = constraints;
        this.implDefinition = implDefinition;
    }

    /**
     * Returns the implementation signature.
     *
     * @return The implementation signature.
     */
    public String getSignature() {
        return signature;
    }

    /**
     * Returns the requirements to run the implementation.
     *
     * @return description of the resource features required to run the implementation
     */
    public T getConstraints() {
        return constraints;
    }

    /**
     * Returns the associated implementation with core Id {@code coreId} and implementation Id {@code implId}.
     *
     * @param coreId Core Id.
     * @param implId Implementation Id.
     * @return The associated implementation.
     */
    @SuppressWarnings("unchecked")
    public Implementation getImpl(int coreId, int implId) {
        if (implDefinition.getTaskType().equals(TaskType.METHOD)) {
            return new AbstractMethodImplementation(coreId, implId,
                (ImplementationDescription<MethodResourceDescription, AbstractMethodImplementationDefinition>) this);
        } else {
            return new ServiceImplementation(coreId, implId,
                (ImplementationDescription<ServiceResourceDescription, ServiceDefinition>) this);
        }
    }

    public D getDefinition() {
        return implDefinition;
    }

    @SuppressWarnings("unchecked")
    @Override
    public void readExternal(ObjectInput in) throws IOException, ClassNotFoundException {
        this.signature = (String) in.readObject();
        this.constraints = (T) in.readObject();
        this.implDefinition = (D) in.readObject();

    }

    @Override
    public void writeExternal(ObjectOutput out) throws IOException {
        out.writeObject(this.signature);
        out.writeObject(this.constraints);
        out.writeObject(this.implDefinition);
    }

    @Override
    public String toString() {
        return this.implDefinition.toShortFormat();
    }
}
