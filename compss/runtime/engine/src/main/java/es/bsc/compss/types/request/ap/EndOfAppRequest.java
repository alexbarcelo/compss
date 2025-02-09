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
package es.bsc.compss.types.request.ap;

import es.bsc.compss.components.impl.AccessProcessor;
import es.bsc.compss.components.impl.DataInfoProvider;
import es.bsc.compss.components.impl.TaskAnalyser;
import es.bsc.compss.components.impl.TaskDispatcher;
import es.bsc.compss.types.Application;
import es.bsc.compss.types.Barrier;
import es.bsc.compss.worker.COMPSsException;
import java.util.concurrent.Semaphore;


public class EndOfAppRequest extends APRequest implements Barrier {

    private final Application app;
    private final Semaphore sem;

    private boolean released;


    /**
     * Creates a new request to end the application.
     * 
     * @param app Application Id.
     */
    public EndOfAppRequest(Application app) {
        this.app = app;
        this.sem = new Semaphore(0);

        this.released = false;
    }

    /**
     * Returns the application of the request.
     * 
     * @return The application of the request.
     */
    public Application getApp() {
        return this.app;
    }

    /**
     * Returns the waiting semaphore of the request.
     * 
     * @return The waiting semaphore of the request.
     */
    public Semaphore getSemaphore() {
        return this.sem;
    }

    @Override
    public void process(AccessProcessor ap, TaskAnalyser ta, DataInfoProvider dip, TaskDispatcher td) {
        LOGGER.info("TA Processes no More tasks for app " + this.app.getId());
        ta.noMoreTasks(this);
        sem.release();
        LOGGER.info("TA Processed no More tasks for app " + this.app.getId());
    }

    @Override
    public APRequestType getRequestType() {
        return APRequestType.END_OF_APP;
    }

    @Override
    public void setException(COMPSsException exception) {
        // EndOfApp does not support exceptions.
    }

    @Override
    public COMPSsException getException() {
        // EndOfApp does not support exceptions.
        return null;
    }

    @Override
    public void release() {
        LOGGER.info("No More tasks for app " + this.app.getId() + " released");
        released = true;
        sem.release();
    }

    /**
     * Waits for all application's tasks to complete releasing and recovering the resources if needed.
     */
    public void waitForCompletion() {
        // Wait for processing
        sem.acquireUninterruptibly();

        boolean stalled = false;
        if (!released) {
            LOGGER.info("No More tasks for app " + this.app.getId() + " becomes stalled");
            this.app.stalled();
            stalled = true;
        }
        // Wait for all tasks completion
        sem.acquireUninterruptibly();

        // Wait for app to have resources
        if (stalled) {
            app.readyToContinue(sem);
            sem.acquireUninterruptibly();
        }
    }

}
