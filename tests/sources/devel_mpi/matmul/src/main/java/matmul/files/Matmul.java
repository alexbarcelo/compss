package matmul.files;

import java.io.BufferedReader;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.IOException;
import java.util.StringTokenizer;

import mpi.MPI;


public class Matmul {

    private static final byte[] NEW_LINE = "\n".getBytes();

    private static int MSIZE;
    private static int BSIZE;

    private static String[][] AfileNames;
    private static String[][] BfileNames;
    private static String[][] CfileNames;


    private static void usage() {
        System.out.println("    Usage: matmul.files.Matmul <MSize> <BSize>");
    }

    public static void main(String[] args) throws Exception {
        // Check and get parameters
        if (args.length != 2) {
            usage();
            throw new Exception("[ERROR] Incorrect number of parameters");
        }
        MSIZE = Integer.parseInt(args[0]);
        BSIZE = Integer.parseInt(args[1]);

        // Initialize matrices
        System.out.println("[LOG] MSIZE parameter value = " + MSIZE);
        System.out.println("[LOG] BSIZE parameter value = " + BSIZE);
        initializeVariables();
        initializeMatrix(AfileNames, true);
        initializeMatrix(BfileNames, true);
        initializeMatrix(CfileNames, false);
        
        // Wait for runtime
        Thread.sleep(3_000);

        // Compute matrix multiplication C = A x B
        computeMultiplication();

        // Uncomment the following line if you wish to store the result in a file
        // storeMatrix("c_result.txt");

        // End
        System.out.println("[LOG] Main program finished.");
    }

    private static void initializeVariables() {
        AfileNames = new String[MSIZE][MSIZE];
        BfileNames = new String[MSIZE][MSIZE];
        CfileNames = new String[MSIZE][MSIZE];
        for (int i = 0; i < MSIZE; i++) {
            for (int j = 0; j < MSIZE; j++) {
                AfileNames[i][j] = "A." + i + "." + j;
                BfileNames[i][j] = "B." + i + "." + j;
                CfileNames[i][j] = "C." + i + "." + j;
            }
        }
    }

    private static void initializeMatrix(String[][] fileNames, boolean initRand) throws Exception {
        for (int i = 0; i < MSIZE; ++i) {
            for (int j = 0; j < MSIZE; ++j) {
                FileOutputStream fos = null;
                try {
                    fos = new FileOutputStream(fileNames[i][j]);
                    for (int iblock = 0; iblock < BSIZE; ++iblock) {
                        for (int jblock = 0; jblock < BSIZE; ++jblock) {
                            double value = (double) 0.0;
                            if (initRand) {
                                value = (double) (Math.random() * 10.0);
                            }
                            fos.write(String.valueOf(value).getBytes());
                            fos.write(" ".getBytes());
                        }
                        fos.write(NEW_LINE);
                    }
                    fos.write(NEW_LINE);
                } catch (IOException e) {
                    throw new Exception("[ERROR] Error initializing matrix", e);
                } finally {
                    if (fos != null) {
                        try {
                            fos.close();
                        } catch (Exception e) {
                            throw new Exception("[ERROR] Error closing matrix file", e);
                        }
                    }
                }
            }
        }
    }

    private static void computeMultiplication() {
        System.out.println("[LOG] Computing result");
        Integer[][][] exitValues = new Integer[MSIZE][MSIZE][MSIZE];
        
        // Launch tasks
        for (int i = 0; i < MSIZE; i++) {
            for (int j = 0; j < MSIZE; j++) {
                for (int k = 0; k < MSIZE; k++) {
                    exitValues[i][j][k] = MPI.multiplyAccumulative(BSIZE, AfileNames[i][k], BfileNames[k][j], CfileNames[i][j]);
                }
            }
        }
        
        // Wait loop
        for (int i = 0; i < MSIZE; i++) {
            for (int j = 0; j < MSIZE; j++) {
                for (int k = 0; k < MSIZE; k++) {
                    if (exitValues[i][j][k] != 0) {
                        System.err.println("[ERROR] Some task failed with exitValue " + exitValues[i][j][k]);
                    }
                }
            }
        }
    }

    public static void storeMatrix(String fileName) throws Exception {
        try {
            FileOutputStream fos = new FileOutputStream(fileName);
            for (int i = 0; i < MSIZE; ++i) {
                for (int j = 0; j < MSIZE; ++j) {
                    FileReader filereader = new FileReader(CfileNames[i][j]);
                    BufferedReader br = new BufferedReader(filereader);
                    StringTokenizer tokens;
                    String nextLine;
                    for (int iblock = 0; iblock < BSIZE; ++iblock) {
                        nextLine = br.readLine();
                        tokens = new StringTokenizer(nextLine);
                        for (int jblock = 0; jblock < BSIZE && tokens.hasMoreTokens(); ++jblock) {
                            String value = tokens.nextToken() + " ";
                            fos.write(value.getBytes());
                        }
                    }
                    fos.write(NEW_LINE);
                    br.close();
                    filereader.close();
                }
                fos.write(NEW_LINE);
            }
            fos.close();
        } catch (FileNotFoundException fnfe) {
            throw new Exception("[ERROR] Error storing result matrix", fnfe);
        } catch (IOException ioe) {
            throw new Exception("[ERROR] Error storing result matrix", ioe);
        }
    }

}
