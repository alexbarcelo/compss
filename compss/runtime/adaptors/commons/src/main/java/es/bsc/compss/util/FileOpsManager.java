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
package es.bsc.compss.util;

import es.bsc.compss.log.Loggers;

import java.io.File;
import java.io.IOException;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.DirectoryNotEmptyException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import org.apache.commons.io.FileExistsException;
import org.apache.commons.io.FileUtils;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;


public class FileOpsManager {

    private static final Logger LOGGER = LogManager.getLogger(Loggers.COMM);
    public static final boolean DEBUG = LOGGER.isDebugEnabled();

    private static final ExecutorService HIGH_PRIORITY;
    private static final ExecutorService LOW_PRIORITY;

    static {
        if (Tracer.extraeEnabled()) {
            if (Tracer.basicModeEnabled()) {
                Tracer.enablePThreads(2);
            }
        }
        LOW_PRIORITY = Executors.newSingleThreadExecutor();
        HIGH_PRIORITY = Executors.newFixedThreadPool(1);

        Future<Object> low = LOW_PRIORITY.submit(new Callable<Object>() {

            @Override
            public Object call() {
                Thread.currentThread().setPriority(Thread.MIN_PRIORITY);
                Thread.currentThread().setName("Low priority FS");
                if (Tracer.extraeEnabled()) {
                    if (Tracer.basicModeEnabled()) {
                        Tracer.disablePThreads(1);
                    }

                    Tracer.emitEvent(TraceEvent.LOW_FILE_SYS_THREAD_ID.getId(),
                        TraceEvent.LOW_FILE_SYS_THREAD_ID.getType());

                    final TraceEvent teInit = TraceEvent.INIT_FS;
                    Tracer.emitEvent(teInit.getId(), teInit.getType());
                    Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.INIT_FS.getType());
                }

                return new Object();
            }
        });

        Future<Object> high = HIGH_PRIORITY.submit(new Callable<Object>() {

            @Override
            public Object call() {
                Thread.currentThread().setName("High priority FS");
                if (Tracer.extraeEnabled()) {
                    if (Tracer.basicModeEnabled()) {
                        Tracer.disablePThreads(1);
                    }

                    Tracer.emitEvent(TraceEvent.HIGH_FILE_SYS_THREAD_ID.getId(),
                        TraceEvent.HIGH_FILE_SYS_THREAD_ID.getType());

                    final TraceEvent teInit = TraceEvent.INIT_FS;
                    Tracer.emitEvent(teInit.getId(), teInit.getType());
                    Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.INIT_FS.getType());
                }
                return new Object();
            }
        });

        try {
            low.get();
            high.get();
        } catch (Exception e) {
            // Nothing to do
        }
    }


    public static interface FileOpListener {

        void completed();

        void failed(IOException e);
    }


    private static final FileOpListener IGNORE_LISTENER = new FileOpListener() {

        @Override
        public void completed() {
            // Ignoring completion
        }

        @Override
        public void failed(IOException e) {
            // Ignoring failure
        }
    };


    /**
     * Execute a composed operation as an Asynchronous FS operation.
     *
     * @param composition operation composition
     */
    public static void composedOperationAsync(final Runnable composition) {
        composedOperationAsync(composition, IGNORE_LISTENER);
    }

    /**
     * Execute a composed operation as an Asynchronous FS operation.
     *
     * @param composition operation composition
     * @param listener element to notify on operation end
     */
    public static void composedOperationAsync(final Runnable composition, final FileOpListener listener) {
        HIGH_PRIORITY.execute(composition);
    }

    /**
     * Copy a File Asynchronously.
     *
     * @param src File to copy
     * @param tgt target path
     */
    public static void copyAsync(final File src, final File tgt) {
        copyAsync(src, tgt, IGNORE_LISTENER);
    }

    /**
     * Copy a File Asynchronously.
     *
     * @param src File to copy
     * @param tgt target path
     * @param listener element to notify on operation end
     */
    public static void copyAsync(final File src, final File tgt, final FileOpListener listener) {
        if (src != null) {
            LOW_PRIORITY.execute(new Runnable() {

                @Override
                public void run() {
                    try {
                        copyFile(src, tgt);
                        listener.completed();
                    } catch (IOException ioe) {
                        listener.failed(ioe);
                    }
                }
            });
        }
    }

    /**
     * Copy a File Synchronously.
     *
     * @param src File to copy
     * @param tgt target path
     * @throws java.io.IOException if an I/O error occurs
     */
    public static void copySync(final File src, final File tgt) throws IOException {
        copyFile(src, tgt);
    }

    /**
     * Copy a directory asynchronously.
     *
     * @param src Directory to copy
     * @param tgt target path
     */
    public static void copyDirAsync(final File src, final File tgt) {
        copyDirAsync(src, tgt, IGNORE_LISTENER);
    }

    /**
     * Copy a directory asynchronously.
     *
     * @param src Directory to copy
     * @param tgt target path
     * @param listener element to notify on operation end
     */
    public static void copyDirAsync(final File src, final File tgt, final FileOpListener listener) {
        if (src != null) {
            LOW_PRIORITY.execute(new Runnable() {

                @Override
                public void run() {
                    try {
                        copyDirectory(src, tgt);
                        listener.completed();
                    } catch (IOException ioe) {
                        listener.failed(ioe);
                    }
                }
            });
        }
    }

    /**
     * Copy a directory synchronously.
     *
     * @param src File to copy
     * @param tgt target path
     * @throws java.io.IOException if an I/O error occurs
     */
    public static void copyDirSync(final File src, final File tgt) throws IOException {
        copyDirectory(src, tgt);
    }

    /**
     * Delete a File Asynchronously.
     *
     * @param file File to delete
     */
    public static void deleteAsync(final File file) {
        deleteAsync(file, IGNORE_LISTENER);
    }

    /**
     * Delete a File Asynchronously.
     *
     * @param file File to delete
     * @param listener element to notify on operation end
     */
    public static void deleteAsync(final File file, final FileOpListener listener) {
        if (file != null) {
            LOW_PRIORITY.execute(new Runnable() {

                @Override
                public void run() {
                    try {
                        deleteFile(file);
                        listener.completed();
                    } catch (IOException ioe) {
                        listener.failed(ioe);
                    }
                }
            });
        }
    }

    /**
     * Delete a File Synchronously.
     *
     * @param file File to delete
     * @throws java.io.IOException if an I/O error occurs
     */
    public static void deleteSync(final File file) throws IOException {
        deleteFile(file);
    }

    /**
     * Move a File Asynchronously.
     *
     * @param src File to copy
     * @param tgt target path
     */
    public static void moveAsync(final File src, final File tgt) {
        moveAsync(src, tgt, IGNORE_LISTENER);
    }

    /**
     * Move a File Asynchronously.
     *
     * @param src File to copy
     * @param tgt target path
     * @param listener element to notify on operation end
     */
    public static void moveAsync(final File src, final File tgt, final FileOpListener listener) {
        if (src != null) {
            LOW_PRIORITY.execute(new Runnable() {

                @Override
                public void run() {
                    try {
                        moveFile(src, tgt);
                        listener.completed();
                    } catch (IOException ioe) {
                        listener.failed(ioe);
                    }
                }
            });
        }
    }

    /**
     * Move a File Synchronously.
     *
     * @param src File to copy
     * @param tgt target path
     * @throws java.io.IOException if an I/O error occurs
     */
    public static void moveSync(final File src, final File tgt) throws IOException {
        moveFile(src, tgt);
    }

    /**
     * Move a directory asynchronously.
     *
     * @param src Directory to copy
     * @param tgt target path
     */
    public static void moveDirAsync(final File src, final File tgt) {
        moveDirAsync(src, tgt, IGNORE_LISTENER);
    }

    /**
     * Move a directory asynchronously.
     *
     * @param src Directory to copy
     * @param tgt target path
     * @param listener element to notify on operation end
     */
    public static void moveDirAsync(final File src, final File tgt, final FileOpListener listener) {
        if (src != null) {
            LOW_PRIORITY.execute(new Runnable() {

                @Override
                public void run() {
                    try {
                        moveDirectory(src, tgt);
                        listener.completed();
                    } catch (IOException ioe) {
                        listener.failed(ioe);
                    }
                }
            });
        }
    }

    /**
     * Move a Directory Synchronously.
     *
     * @param src Directory to copy
     * @param tgt target path
     * @throws java.io.IOException if an I/O error occurs
     */
    public static void moveDirSync(final File src, final File tgt) throws IOException {
        moveDirectory(src, tgt);
    }

    /**
     * Serialize object into a file Asynchronously.
     *
     * @param o Object to serialize
     * @param tgt target path
     */
    public static void serializeAsync(final Object o, final String tgt) {
        serializeAsync(o, tgt, IGNORE_LISTENER);
    }

    /**
     * Serialize object into a file Asynchronously.
     *
     * @param o Object to serialize
     * @param tgt target path
     * @param listener element to notify on operation end
     */
    public static void serializeAsync(final Object o, final String tgt, final FileOpListener listener) {
        LOW_PRIORITY.execute(new Runnable() {

            @Override
            public void run() {
                try {
                    serialize(o, tgt);
                    listener.completed();
                } catch (IOException ioe) {
                    listener.failed(ioe);
                }
            }
        });
    }

    /**
     * Serialized object into a file Synchronously.
     *
     * @param o Object to serialize
     * @param tgt target path
     * @throws java.io.IOException Error writing the file.
     */
    public static void serializeSync(final Object o, final String tgt) throws IOException {
        serialize(o, tgt);
    }

    /**
     * Stops the File Operations Manager.
     */
    public static void shutdown() {
        LOW_PRIORITY.shutdown();
        HIGH_PRIORITY.shutdown();

        // this code is comented because the extrae tracer is already off when we reach this point
        // if (Tracer.extraeEnabled()) {
        // Semaphore sem = new Semaphore(0);
        // HIGH_PRIORITY.submit(new Callable<Object>() {
        // public Object call() {
        // Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.FILE_SYS_THREAD_ID.getType());
        // sem.release();
        // return null;
        // }
        // });
        // try {
        // sem.acquire();
        // } catch (InterruptedException e) {
        // WORKER_LOGGER
        // .warn("Tracer could not register end of event " + TraceEvent.FILE_SYS_THREAD_ID.getSignature());
        // }
        // }
    }

    private static void serialize(final Object o, final String target) throws IOException {
        if (DEBUG) {
            LOGGER.debug("Serializing object to " + target);
        }
        if (Tracer.extraeEnabled()) {
            Tracer.emitEvent(TraceEvent.LOCAL_SERIALIZE.getId(), TraceEvent.LOCAL_SERIALIZE.getType());
        }
        try {
            Serializer.serialize(o, target);
        } catch (IOException ioe) {
            throw ioe;
        } finally {
            if (Tracer.extraeEnabled()) {
                Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.LOCAL_SERIALIZE.getType());
            }
        }
    }

    private static void copyFile(final File source, final File target) throws IOException {
        if (DEBUG) {
            LOGGER.debug("Copying file " + source.getAbsolutePath() + " to " + target.getAbsolutePath());
        }
        if (Tracer.extraeEnabled()) {
            Tracer.emitEvent(TraceEvent.LOCAL_COPY.getId(), TraceEvent.LOCAL_COPY.getType());
        }
        Path tgtPath = (target).toPath();
        Path sourcePath = (source).toPath();
        try {
            if (tgtPath.compareTo(sourcePath) != 0) {
                Files.copy(sourcePath, tgtPath, StandardCopyOption.REPLACE_EXISTING);
                Files.walk(sourcePath).forEach((Path content) -> {
                    try {
                        Path fileDest = tgtPath.resolve(sourcePath.relativize(content));
                        Files.copy(content, fileDest, StandardCopyOption.REPLACE_EXISTING);
                    } catch (IOException e) {
                        LOGGER.error("Exception copying file " + content + " to " + tgtPath);
                    }
                });
            }
        } catch (IOException ioe) {
            throw ioe;
        } finally {
            if (Tracer.extraeEnabled()) {
                Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.LOCAL_COPY.getType());
            }
        }
    }

    private static void copyDirectory(final File source, final File target) throws IOException {
        if (DEBUG) {
            LOGGER.debug("Copying directory " + source.getAbsolutePath() + " to " + target.getAbsolutePath());
        }
        if (Tracer.extraeEnabled()) {
            Tracer.emitEvent(TraceEvent.LOCAL_COPY.getId(), TraceEvent.LOCAL_COPY.getType());
        }
        try {
            FileUtils.copyDirectory(source, target);
        } catch (IOException ioe) {
            throw ioe;
        } finally {
            if (Tracer.extraeEnabled()) {
                Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.LOCAL_COPY.getType());
            }
        }
    }

    private static void deleteFile(final File f) throws IOException {

        if (DEBUG) {
            LOGGER.debug("Deleting file " + f.getAbsolutePath());
        }
        if (Tracer.extraeEnabled()) {
            Tracer.emitEvent(TraceEvent.LOCAL_DELETE.getId(), TraceEvent.LOCAL_DELETE.getType());
        }
        try {
            if (!Files.deleteIfExists(f.toPath()) && DEBUG) {
                LOGGER.debug("File " + f.getAbsolutePath() + " not deleted.");
            }
        } catch (DirectoryNotEmptyException dne) {
            // directories must be removed recursively
            Path directory = f.toPath();
            try {
                Files.walkFileTree(directory, new SimpleFileVisitor<Path>() {

                    @Override
                    public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) throws IOException {
                        Files.delete(file);
                        return FileVisitResult.CONTINUE;
                    }

                    @Override
                    public FileVisitResult postVisitDirectory(Path dir, IOException exc) throws IOException {
                        Files.delete(dir);
                        return FileVisitResult.CONTINUE;
                    }
                });
            } catch (IOException e) {
                LOGGER.error("Cannot delete directory " + f.getAbsolutePath(), e);
                throw e;
            } finally {
                if (Tracer.extraeEnabled()) {
                    Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.LOCAL_DELETE.getType());
                }
            }
        } catch (Exception e) {
            LOGGER.error("Cannot delete file " + f.getAbsolutePath(), e);
            throw e;
        } finally {
            if (Tracer.extraeEnabled()) {
                Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.LOCAL_DELETE.getType());
            }
        }
    }

    private static void moveFile(final File source, final File target) throws IOException {
        if (DEBUG) {
            LOGGER.debug("Moving file " + source.getAbsolutePath() + " to " + target.getAbsolutePath());
        }
        if (Tracer.extraeEnabled()) {
            Tracer.emitEvent(TraceEvent.LOCAL_MOVE.getId(), TraceEvent.LOCAL_MOVE.getType());
        }
        Path tgtPath = target.toPath();
        Path sourcePath = source.toPath();
        try {
            if (tgtPath.compareTo(sourcePath) != 0) {
                try {
                    Files.move(sourcePath, tgtPath, StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING);
                } catch (AtomicMoveNotSupportedException amnse) {
                    LOGGER.warn("WARN: AtomicMoveNotSupportedException."
                        + " File cannot be atomically moved. Trying to move without atomic");
                    try {
                        Files.move(sourcePath, tgtPath, StandardCopyOption.REPLACE_EXISTING);
                    } catch (DirectoryNotEmptyException dnee) {
                        LOGGER.warn("WARN: Trying to move a directory as a file");
                        moveDirectory(source, target);
                    }
                }
            }
        } catch (IOException ioe) {
            throw ioe;
        } finally {
            if (Tracer.extraeEnabled()) {
                Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.LOCAL_MOVE.getType());
            }
        }
    }

    private static void moveDirectory(final File source, final File target) throws IOException {
        if (DEBUG) {
            LOGGER.debug("Moving directory " + source.getAbsolutePath() + " to " + target.getAbsolutePath());
        }
        if (Tracer.extraeEnabled()) {
            Tracer.emitEvent(TraceEvent.LOCAL_MOVE.getId(), TraceEvent.LOCAL_MOVE.getType());
        }

        try {
            FileUtils.moveDirectory(source, target);
        } catch (FileExistsException fee) {
            deleteFile(target);
            FileUtils.moveDirectory(source, target);
        } catch (IOException ioe) {
            throw ioe;
        } finally {
            if (Tracer.extraeEnabled()) {
                Tracer.emitEvent(Tracer.EVENT_END, TraceEvent.LOCAL_MOVE.getType());
            }
        }
    }
}
