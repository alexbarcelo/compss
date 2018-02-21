# COMP SUPERSCALAR FRAMEWORK

COMP Superscalar (COMPSs) is a programming model which aims to ease the development of applications for distributed infrastructures,
such as Clusters, Grids and Clouds. COMP superscalar also features a runtime system that exploits the inherent parallelism of 
applications at execution time.


## Documentation

COMPSs documentation can be found at http://compss.bsc.es or at the doc/ folder

  * COMPSs_Installation_Manual.pdf

  * COMPSs_User_Manual_App_Development.pdf
  * COMPSs_User_Manual_App_Execution.pdf

  * COMPSs_Supercomputers_Manual.pdf
  * Tracing_Manual.pdf

  * COMPSs_Developer_Manual.pdf


## Packages
The COMP Superscalar Framework packages are available at our webpage (http://compss.bsc.es) or 
can be found on the builders/packages/ directory


## Sources Structure

  * builders			Packages, scripts for local installations, scripts for supercomputers installation
				and package building scripts
  * compss              	COMPSs Runtime
  * dependencies        	COMPSs embeded dependencies
  * doc                 	COMPSs documentation
  * files			Dependency files (i.e. paraver configurations)


## Sample Applications

You can find extended information about COMPSs Sample applications at the Sample_Applications manual available
at our webpage (http://compss.bsc.es) or at doc/Sample_applications.pdf


## BUILDING COMPSs

* COMPSs Dependencies:
	openjdk-7-jre openjdk-7-jdk graphviz xdg-utils lib2xml lib2xml-dev python (>=2.7) libpython2.7 \
        build-essential autoconf automake autotools-dev libtool libbost-serialization-dev \
	libboost-iostreams-dev gfortran 

* Building dependencies
	wget
	maven		(3.0.x version)


* Building COMPSs for all users
	$ cd builders/
	$ INSTALL_DIR=/opt/COMPSs/
	$ sudo -E ./buildlocal [options] ${INSTALL_DIR}

* Building COMPSs for current user
	$ cd builders/
        $ INSTALL_DIR=$HOME/opt/COMPSs/
        $ ./buildlocal [options] ${INSTALL_DIR}


*************************************
** Department of Computer Science  **
** Barcelona Supercomputing Center **
*************************************

