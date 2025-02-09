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

import es.bsc.compss.comm.Comm;
import es.bsc.compss.components.impl.AccessProcessor;
import es.bsc.compss.components.impl.DataInfoProvider;
import es.bsc.compss.components.impl.TaskAnalyser;
import es.bsc.compss.components.impl.TaskDispatcher;
import es.bsc.compss.types.data.DataAccessId;
import es.bsc.compss.types.data.DataInstanceId;
import es.bsc.compss.types.data.LogicalData;
import es.bsc.compss.types.data.accessid.RAccessId;
import es.bsc.compss.types.data.accessid.RWAccessId;
import es.bsc.compss.types.data.accessid.WAccessId;
import es.bsc.compss.types.data.location.DataLocation;
import es.bsc.compss.types.data.location.ProtocolType;
import es.bsc.compss.types.data.operation.DataOperation;
import es.bsc.compss.types.data.operation.FileTransferable;
import es.bsc.compss.types.data.operation.OneOpWithSemListener;
import es.bsc.compss.types.uri.SimpleURI;
import es.bsc.compss.util.ErrorManager;

import java.io.IOException;
import java.util.concurrent.Semaphore;


/**
 * The TransferRawFileRequest class represents a request to transfer a file located in a worker to be transferred to
 * another location without register the transfer.
 */
public class TransferOpenFileRequest extends APRequest {

    private final DataAccessId faId;
    private final Semaphore sem;

    private DataLocation location;


    /**
     * Constructs a new TransferOpenFileRequest.
     *
     * @param faId Data Id and version of the requested file.
     * @param sem Semaphore where to synchronize until the operation is done.
     */
    public TransferOpenFileRequest(DataAccessId faId, Semaphore sem) {
        this.faId = faId;
        this.sem = sem;
    }

    /**
     * Returns the semaphore where to synchronize until the operation is done.
     *
     * @return Semaphore where to synchronize until the operation is done.
     */
    public Semaphore getSemaphore() {
        return this.sem;
    }

    /**
     * Returns the data Id and version of the requested file.
     *
     * @return Data Id and version of the requested file.
     */
    public DataAccessId getFaId() {
        return this.faId;
    }

    /**
     * Returns the location where to leave the requested file.
     *
     * @return the location where to leave the requested file.
     */
    public DataLocation getLocation() {
        return this.location;
    }

    /**
     * Sets the location where to leave the requested file.
     *
     * @param location Location where to leave the requested file.
     */
    public void setLocation(DataLocation location) {
        this.location = location;
    }

    @Override
    public void process(AccessProcessor ap, TaskAnalyser ta, DataInfoProvider dip, TaskDispatcher td) {
        LOGGER.debug("Process TransferOpenFileRequest");

        // Get target information
        String targetName;
        String targetPath;
        if (this.faId instanceof WAccessId) {
            // Write mode
            WAccessId waId = (WAccessId) this.faId;
            DataInstanceId targetFile = waId.getWrittenDataInstance();
            targetName = targetFile.getRenaming();
            targetPath = Comm.getAppHost().getTempDirPath() + targetName;
        } else if (this.faId instanceof RWAccessId) {
            // Read write mode
            RWAccessId rwaId = (RWAccessId) this.faId;
            targetName = rwaId.getWrittenDataInstance().getRenaming();
            targetPath = Comm.getAppHost().getTempDirPath() + targetName;
        } else {
            // Read only mode
            RAccessId raId = (RAccessId) this.faId;
            targetName = raId.getReadDataInstance().getRenaming();
            targetPath = Comm.getAppHost().getTempDirPath() + targetName;
        }
        LOGGER.debug("Openning file " + targetName + " at " + targetPath);

        // Create location
        DataLocation targetLocation = null;
        String pscoId = Comm.getData(targetName).getPscoId();

        // Ask for transfer when required
        if (pscoId != null) {
            // It is an external object persisted inside the task
            try {
                SimpleURI targetURI = new SimpleURI(ProtocolType.PERSISTENT_URI.getSchema() + pscoId);
                targetLocation = DataLocation.createLocation(Comm.getAppHost(), targetURI);
            } catch (IOException ioe) {
                ErrorManager.error(DataLocation.ERROR_INVALID_LOCATION + " " + targetPath, ioe);
            }
            Comm.registerLocation(targetName, targetLocation);
            // Register target location
            LOGGER.debug("Setting target location to " + targetLocation);
            setLocation(targetLocation);
            LOGGER.debug("External object detected. Auto-release");
            Comm.registerLocation(targetName, targetLocation);
            this.sem.release();
        } else {
            try {
                SimpleURI targetURI = new SimpleURI(ProtocolType.FILE_URI.getSchema() + targetPath);
                targetLocation = DataLocation.createLocation(Comm.getAppHost(), targetURI);
            } catch (IOException ioe) {
                ErrorManager.error(DataLocation.ERROR_INVALID_LOCATION + " " + targetPath, ioe);
            }
            if (this.faId instanceof WAccessId) {
                LOGGER.debug("Write only mode. Auto-release");
                Comm.registerLocation(targetName, targetLocation);
                // Register target location
                LOGGER.debug("Setting target location to " + targetLocation);
                setLocation(targetLocation);
                this.sem.release();
            } else if (this.faId instanceof RWAccessId) {
                LOGGER.debug("RW mode. Asking for transfer");
                RWAccessId rwaId = (RWAccessId) this.faId;
                LogicalData srcData = rwaId.getReadDataInstance().getData();
                FileTransferable ft = new FileTransferable(rwaId.isPreserveSourceData());
                Comm.getAppHost().getData(srcData, targetName, (LogicalData) null, ft, new CopyListener(ft, this.sem));
            } else {
                LOGGER.debug("Read only mode. Asking for transfer");
                RAccessId raId = (RAccessId) this.faId;
                LogicalData srcData = raId.getReadDataInstance().getData();
                FileTransferable ft = new FileTransferable();
                Comm.getAppHost().getData(srcData, ft, new CopyListener(ft, this.sem));
            }
        }
    }

    @Override
    public APRequestType getRequestType() {
        return APRequestType.TRANSFER_OPEN_FILE;
    }


    private class CopyListener extends OneOpWithSemListener {

        private final FileTransferable reason;


        public CopyListener(FileTransferable reason, Semaphore sem) {
            super(sem);
            this.reason = reason;
        }

        @Override
        public void notifyEnd(DataOperation fOp) {
            String targetPath = this.reason.getDataTarget();
            try {
                SimpleURI targetURI = new SimpleURI(ProtocolType.FILE_URI.getSchema() + targetPath);
                DataLocation targetLocation = DataLocation.createLocation(Comm.getAppHost(), targetURI);
                setLocation(targetLocation);
            } catch (IOException ioe) {
                ErrorManager.error(DataLocation.ERROR_INVALID_LOCATION + " " + targetPath, ioe);
            }

            super.notifyEnd(fOp);
        }
    }
}
