/*
 *  Copyright 2002-2019 Barcelona Supercomputing Center (www.bsc.es)
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

package es.bsc.compss.types.implementations.definition;

import es.bsc.compss.types.implementations.DecafImplementation;
import es.bsc.compss.types.implementations.Implementation;
import es.bsc.compss.types.resources.MethodResourceDescription;


/**
 * Class containing all the necessary information to generate a Decaf implementation of a CE.
 */
public class DecafDefinition extends ImplementationDefinition<MethodResourceDescription> {

    private final String dfScript;
    private final String dfExecutor;
    private final String dfLib;
    private final String workingDir;
    private final String mpiRunner;
    private final boolean failByEV;


    protected DecafDefinition(String signature, String dfScript, String dfExecutor, String dfLib, String workingDir,
        String mpiRunner, boolean failByEV, MethodResourceDescription implConstraints) {
        super(signature, implConstraints);
        this.dfScript = dfScript;
        this.dfExecutor = dfExecutor;
        this.dfLib = dfLib;
        this.workingDir = workingDir;
        this.mpiRunner = mpiRunner;
        this.failByEV = failByEV;
    }

    @Override
    public Implementation getImpl(int coreId, int implId) {
        return new DecafImplementation(dfScript, dfExecutor, dfLib, workingDir, mpiRunner, failByEV, coreId, implId,
            this.getSignature(), this.getConstraints());
    }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder();
        sb.append("DECAF Implementation \n");
        sb.append("\t Signature: ").append(this.getSignature()).append("\n");
        sb.append("\t Decaf script: ").append(dfScript).append("\n");
        sb.append("\t Decaf executor: ").append(dfExecutor).append("\n");
        sb.append("\t Decaf lib: ").append(dfLib).append("\n");
        sb.append("\t MPI runner: ").append(mpiRunner).append("\n");
        sb.append("\t Working directory: ").append(workingDir).append("\n");
        sb.append("\t Fail by EV: ").append(this.failByEV).append("\n");
        sb.append("\t Constraints: ").append(this.getConstraints());
        return sb.toString();
    }
}
